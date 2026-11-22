"""Persistent self-checking bridge. Heartbeats never fabricate detection frames."""
from pathlib import Path
import argparse
from collections import deque
import datetime
import json
import msvcrt
import os
import queue
import subprocess
import threading
import time
from bridge_ch32 import packet, request, serial
from serial.tools import list_ports
from receive import DEFAULT_ADB, OUTPUT, validate

PACKAGE = 'cn.zhixing.vision'
STATUS = OUTPUT / 'monitor-status.json'
STOP = OUTPUT / 'monitor-stop.request'
LOCK = OUTPUT / 'monitor.lock'


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def adb_run(adb, *args):
    return subprocess.run([str(adb), *args], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=2,
                          creationflags=subprocess.CREATE_NO_WINDOW)


def probe_phone(adb):
    result = adb_run(adb, 'devices')
    if result.returncode:
        return None, None, 'adb_unavailable'
    entries = [x.split() for x in result.stdout.splitlines()[1:] if x.strip()]
    if len(entries) == 1 and len(entries[0]) >= 2 and entries[0][1] == 'unauthorized':
        return None, None, 'phone_usb_unauthorized'
    if len(entries) != 1 or len(entries[0]) < 2 or entries[0][1] != 'device':
        return None, None, 'phone_offline_or_not_authorized'
    device = entries[0][0]  # Routing only; never persist identifiers.
    result = adb_run(adb, '-s', device, 'shell', 'pidof', PACKAGE)
    pid = result.stdout.strip().split()
    return device, pid[0] if result.returncode == 0 and pid else None, 'checked'


def monitor_state(device, pid, probe_age, stream_alive, frame_age, authorization_pending=False):
    if authorization_pending and probe_age <= 5:
        return 4
    if not device or probe_age > 5:
        return 0  # Phone offline or the USB check is no longer fresh.
    if not pid:
        return 1  # App process absent.
    if not stream_alive or frame_age is None or frame_age >= 2:
        return 2  # Process exists, but no fresh inference output.
    return 3


class Stream:
    def __init__(self, adb, device, pid):
        self.messages = queue.Queue(maxsize=16)
        self.previous = None
        self.last_frame_at = None
        self.process = subprocess.Popen(
            [str(adb), '-s', device, 'logcat', '--pid=' + pid, '-v', 'raw', '-T', '1', 'ZXR_VISION:I', '*:S'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        for line in self.process.stdout:
            item = (time.monotonic(), line)
            try:
                self.messages.put_nowait(item)
            except queue.Full:
                try:
                    self.messages.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self.messages.put_nowait(item)
                except queue.Full:
                    pass

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)

    def fresh(self, now):
        """Discard historical first log, duplicate sequences and delayed PC queue items."""
        result = None
        while True:
            try:
                arrival, line = self.messages.get_nowait()
            except queue.Empty:
                return result
            if now - arrival > .5 or not line.lstrip().startswith('{'):
                continue
            try:
                frame = validate(json.loads(line))
            except (ValueError, TypeError, KeyError, AttributeError):
                continue
            stamp = (frame['seq'], frame['phone_ms'])
            if self.previous is None:
                self.previous = stamp
                continue
            if stamp[0] <= self.previous[0] or stamp[1] <= self.previous[1]:
                continue
            self.previous = stamp
            self.last_frame_at = arrival
            result = frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', type=Path, default=DEFAULT_ADB)
    parser.add_argument('--duration', type=float, default=0, help='0 = continue until stopped')
    args = parser.parse_args()
    if args.duration < 0:
        raise ValueError('Duration must be nonnegative')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise SystemExit('A monitor is already running')
        STOP.unlink(missing_ok=True)
        shutdown = threading.Event()
        probe = {'at': 0, 'device': None, 'pid': None, 'reason': 'starting'}
        probe_lock = threading.Lock()

        def phone_worker():
            unauthorized_since = None
            last_auth_retry = -10000.0
            while not shutdown.is_set():
                try:
                    device, pid, reason = probe_phone(args.adb)
                    now = time.monotonic()
                    if reason == 'phone_usb_unauthorized':
                        if unauthorized_since is None:
                            unauthorized_since = now
                        # Refresh an offline authorization handshake, never grant permission.
                        # One unique phone only; do not reset healthy/ambiguous devices.
                        if now - unauthorized_since >= 5 and now - last_auth_retry >= 30:
                            last_auth_retry = now
                            adb_run(args.adb, 'reconnect', 'offline')
                    else:
                        unauthorized_since = None
                except (OSError, subprocess.TimeoutExpired):
                    device, pid, reason = None, None, 'usb_check_timeout'
                with probe_lock:
                    probe.update(at=time.monotonic(), device=device, pid=pid, reason=reason)
                shutdown.wait(2)

        threading.Thread(target=phone_worker, daemon=True).start()
        stream = link = None
        key = None
        started = time.monotonic()
        retry_at = heartbeat_at = save_at = 0
        events, targets = deque(maxlen=40), deque(maxlen=100)
        stats = {'pid': os.getpid(), 'date': '2026-10-07', 'running': True,
                 'source': 'live phone ADB -> PC monitor -> WCH UART',
                 'standalone_phone_to_board': False, 'motor_control': False,
                 'frames_acked': 0, 'heartbeats_acked': 0, 'board_connections': 0,
                 'phone_stream_connections': 0, 'last_ack': None}
        previous_status = None
        last_acked_at = None
        last_error = None

        def drop_link():
            nonlocal link, last_acked_at
            if link:
                link.close()
            link = None
            last_acked_at = None

        try:
            while not STOP.exists() and (args.duration == 0 or time.monotonic() - started < args.duration):
                now = time.monotonic()
                with probe_lock:
                    phone = dict(probe)
                current_key = (phone['device'], phone['pid'])
                if current_key != key or (stream and stream.process.poll() is not None):
                    if stream:
                        stream.close()
                    stream = None
                    key = current_key
                    last_acked_at = None
                    if link:
                        try:
                            request(link, b'HELLO\n', 'ZXR,V1')
                        except (OSError, TimeoutError, RuntimeError):
                            drop_link()
                    heartbeat_at = 0
                if not stream and phone['device'] and phone['pid'] and now - phone['at'] < 5:
                    try:
                        stream = Stream(args.adb, *current_key)
                        stats['phone_stream_connections'] += 1
                    except OSError:
                        last_error = 'phone_stream_start_failed'
                if not link and now >= retry_at:
                    retry_at = now + 2
                    ports = [p for p in list_ports.comports() if (p.vid, p.pid) == (0x1A86, 0x8010)]
                    if len(ports) == 1:
                        try:
                            link = serial.Serial(ports[0].device, 115200, timeout=.06, write_timeout=.5)
                            link.reset_input_buffer()
                            request(link, b'HELLO\n', 'ZXR,V1')
                            stats['board_connections'] += 1
                            heartbeat_at = 0
                            last_error = None
                        except (OSError, TimeoutError, RuntimeError):
                            drop_link()
                            last_error = 'board_handshake_failed'
                now = time.monotonic()
                frame = stream.fresh(now) if stream else None
                if frame and link:
                    primary = max(frame['objects'], key=lambda x: x['score'], default=None)
                    values = [frame['seq']] + ([primary['cls']] + [round(primary[k] * 1000) for k in ('score', 'cx', 'cy')]
                                               if primary else [255, 0, 0, 0])
                    body = ','.join(str(x) for x in values)
                    try:
                        if frame['seq'] > 0xFFFFFFFF:
                            raise ValueError('Sequence out of bounds')
                        ack = request(link, packet('V1,' + body), 'ACK,' + body)
                        stats['frames_acked'] += 1
                        stats['last_ack'] = ack
                        last_acked_at = time.monotonic()
                        targets.append({'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                        'phone_seq': frame['seq'], 'phone_ms': frame['phone_ms'],
                                        'cls': primary['cls'] if primary else 255, 'ack': ack})
                    except (OSError, TimeoutError, RuntimeError, ValueError):
                        drop_link(); last_error = 'board_packet_failed'; retry_at = now + 2
                frame_age = now - stream.last_frame_at if stream and stream.last_frame_at else None
                state = monitor_state(phone['device'], phone['pid'], now - phone['at'],
                                      bool(stream and stream.process.poll() is None), frame_age,
                                      phone['reason']=='phone_usb_unauthorized')
                if link and now >= heartbeat_at:
                    try:
                        stats['last_heartbeat_ack'] = request(link, packet('H1,' + str(state)), 'HEART,' + str(state))
                        stats['heartbeats_acked'] += 1
                    except (OSError, TimeoutError, RuntimeError):
                        drop_link(); last_error = 'board_heartbeat_failed'; retry_at = now + 2
                    heartbeat_at = now + 1
                status_key = (bool(link), state)
                if status_key != previous_status:
                    event = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                             'board_connected': bool(link), 'phone_state': state}
                    events.append(event)
                    print(json.dumps(event), flush=True)
                    previous_status = status_key
                if now >= save_at:
                    stats.update(updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                 uptime_seconds=round(now-started, 1), board_connected=bool(link),
                                 phone_connected=bool(phone['device']) and now-phone['at'] <= 5,
                                 app_process_running=bool(phone['pid']) and now-phone['at'] <= 5, phone_state=state,
                                 last_frame_age_seconds=round(frame_age, 2) if frame_age is not None else None,
                                 last_ack_age_seconds=round(now-last_acked_at, 2) if last_acked_at else None,
                                 usb_authorization_pending=state==4, phone_probe_reason=phone['reason'],
                                 last_error=last_error, events=list(events))
                    atomic_json(STATUS, stats)
                    atomic_json(OUTPUT/'monitor-recent-frames.json', list(targets))
                    save_at = now + 1
                time.sleep(.05)
        finally:
            shutdown.set()
            if stream:
                stream.close()
            if link:
                try:
                    request(link, b'HELLO\n', 'ZXR,V1')
                except (OSError, TimeoutError, RuntimeError):
                    pass
                drop_link()
            stats.update(running=False, board_connected=False,
                         updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         events=list(events), stopped_reason='stop_requested' if STOP.exists() else 'duration_or_exception')
            atomic_json(STATUS, stats)
            atomic_json(OUTPUT/'monitor-recent-frames.json', list(targets))
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()
