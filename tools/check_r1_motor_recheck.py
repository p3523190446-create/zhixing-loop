"""Prepared suspended test. Device access happens only in main with --execute.

Do not execute while wheels are being assembled. This does not flash firmware.
The r1_motor_recheck firmware must be installed before using the new diagnostics.
"""
from pathlib import Path
import argparse
import datetime
import json
import math
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
FAULT_CAUSES = {
    0: 'NONE', 1: 'DRIVER_HARD_SPEED_LIMIT', 2: 'CONSECUTIVE_DRIVER_SPEED_LIMIT',
    3: 'COUNT_FILTERED_SPEED_LIMIT', 4: 'STALE_FEEDBACK', 5: 'UART_ERROR',
    6: 'REVERSE_SIGN', 7: 'UNEXPECTED_OTHER_CHANNEL_MOTION',
}


def run(port):
    sys.path.insert(0, str(Path.home()/'Documents/ch32-tools/python-support'))
    import serial
    out = ROOT/'知行回路软件/build/r1_motor_recheck'
    out.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().astimezone()
    target = out/('bench-'+stamp.strftime('%Y%m%d-%H%M%S-%f')+'.json')
    record = {'recorded_at': stamp.isoformat(), 'firmware': 'r1_motor_recheck',
              'scope': 'SUSPENDED_ONLY', 'target_mm_s': 80, 'tests': [],
              'result': 'NOT_RUN', 'direction': 'DEFERRED_BY_USER_NOT_VERIFIED',
              'sample_window_ms': [8000, 11000], 'transcript': []}
    with serial.Serial(port, 115200, timeout=.1, write_timeout=1) as link:
        def query(command, prefix):
            link.write(command.encode('ascii')+b'\n')
            deadline = time.monotonic()+4
            while time.monotonic() < deadline:
                row = link.readline().decode('ascii', errors='replace').strip()
                if row:
                    record['transcript'].append({'command': command, 'reply': row})
                if row.startswith(prefix):
                    return row
            raise TimeoutError(command+'; ambiguous motion commands are not retried')

        def values(command, prefix):
            return [int(x) for x in query(command, prefix).split(',')[1:]]

        def upload(enable):
            for _ in range(30):
                ack = query('MOTOR_ENCODER_ON' if enable else 'MOTOR_ENCODER_OFF', 'ENCODER_UPLOAD_')
                if ack == 'ENCODER_UPLOAD_QUEUED':
                    return
                if ack != 'ENCODER_UPLOAD_BUSY':
                    raise RuntimeError(ack)
                time.sleep(.1)
            raise RuntimeError('Upload control unavailable')

        def health():
            h = values('MOTOR_STATUS', 'MOTOR,')
            if h[1] or h[2]:
                raise RuntimeError('UART errors/drops: stop sequence')
            return h

        def require(condition, message):
            if not condition:
                raise RuntimeError(message)

        try:
            # Verify new diagnostic commands before any motion. Old firmware
            # cannot accidentally run a trial using this script.
            require(len(values('MOTOR_FAULT_STATUS', 'MOTORFAULT,')) == 9, 'Wrong diagnostic firmware')
            require(values('MOTOR_PULSE_STATUS', 'PULSE,')[0] == 0, 'Motion already active')
            for channel in range(1, 5):
                if channel > 1:
                    upload(False)
                    time.sleep(.2)
                upload(True)
                time.sleep(3.5)
                before = values('MOTOR_ENCODER_STATUS', 'ENCODER,')
                pbefore = values('MOTOR_PULSE_STATUS', 'PULSE,')
                live = values('MOTOR_LIVE_STATUS', 'MOTORLIVE,')
                require(len(live) == 17 and max(live[1:3]) < 250, 'Feedback not fresh')
                require(all(abs(v) < 20 for v in live[7:11]), 'Wheel not stationary')
                health()
                trial = {'channel': channel, 'samples': [], 'encoder_before': before}
                record['tests'].append(trial)
                for _ in range(20):
                    ack = query(f'MOTOR_CLOSED_M{channel}', 'MOTOR_CLOSED_')
                    if ack == f'MOTOR_CLOSED_STARTED,M{channel}':
                        break
                    require(ack == 'MOTOR_CLOSED_BUSY_OR_OFFLINE', ack)
                    time.sleep(.1)
                else:
                    raise RuntimeError('Start unavailable')
                print(f'M{channel}: bounded suspended trial started.', flush=True)
                deadline = time.monotonic()+13
                while time.monotonic() < deadline:
                    live = values('MOTOR_LIVE_STATUS', 'MOTORLIVE,')
                    trial['samples'].append({'host_monotonic_s': time.monotonic(), 'values': live})
                    require(len(live) == 17, 'Malformed live telemetry')
                    if not live[13]:
                        break
                    require(max(live[1:3]) < 250, 'Feedback stale during motion')
                    time.sleep(.2)
                else:
                    raise RuntimeError('Motion exceeded test deadline')
                fault = values('MOTOR_FAULT_STATUS', 'MOTORFAULT,')
                trial['fault_snapshot'] = fault
                trial['fault_cause'] = FAULT_CAUSES.get(fault[0], 'UNKNOWN')
                time.sleep(.7)
                pafter = values('MOTOR_PULSE_STATUS', 'PULSE,')
                speed = values('MOTOR_SPEED_STATUS', 'SPEED,')
                window = values('MOTOR_SPEED_WINDOW', 'SPEEDWINDOW,')
                after = values('MOTOR_ENCODER_STATUS', 'ENCODER,')
                trial.update({'pulse_after': pafter, 'speed_status': speed,
                              'count_window': window, 'encoder_after': after, 'health': health()})
                require(pafter[0] == 0 and pafter[1] == pbefore[1]+1 and
                        pafter[2] == pbefore[2]+3 and pafter[5] == channel,
                        'Stop-frame completion mismatch')
                time.sleep(.6)
                settled = values('MOTOR_ENCODER_STATUS', 'ENCODER,')
                trial['settled'] = settled
                require(after[2:6] == settled[2:6], 'Counts changing after stop')
                require(speed[7] == 0, 'Protection stopped trial: '+trial['fault_cause'])
                require(speed[8] >= 35 and window[3]-window[2] >= 2400, 'Incomplete steady-speed window')
                delta = [after[i+2]-before[i+2] for i in range(4)]
                require(delta[channel-1] > 0 and all(delta[i] == 0 for i in range(4) if i != channel-1),
                        'Encoder channel/sign mismatch')
                average = (window[1]-window[0])*math.pi*65/2340*1000/(window[3]-window[2])
                reported = speed[9]/speed[8]
                # Average tracking and short-window fluctuation are distinct gates.
                mean_pass = abs(average-80) <= 15 and abs(reported-80) <= 15 and abs(average-reported) <= 15
                samples = [r['values'] for r in trial['samples']
                           if 8000 <= r['values'][0]-pafter[3] <= 11000]
                equivalents = []
                for a, b in zip(samples, samples[1:]):
                    dt = b[0]-a[0]
                    if dt > 0:
                        equivalents.append((b[channel+2]-a[channel+2])*math.pi*65/2340*1000/dt)
                span_ms = samples[-1][0]-samples[0][0] if len(samples)>1 else 0
                fluctuation_pass = (len(equivalents) >= 3 and span_ms >= 1500 and
                                    speed[11]-speed[10] <= 40 and
                                    max(equivalents)-min(equivalents) <= 40)
                trial.update({'encoder_average_mm_s': average, 'reported_average_mm_s': reported,
                              'short_window_equivalent_mm_s': equivalents,
                              'short_window_span_ms': span_ms,
                              'mean_tracking_pass': mean_pass, 'fluctuation_pass': fluctuation_pass,
                              'result': 'PASS' if mean_pass and fluctuation_pass else 'NEEDS_TUNING'})
                print(f'M{channel}: average {average:.1f}mm/s; {trial["result"]}.', flush=True)
            record['result'] = 'ALL_PASS' if all(t['result'] == 'PASS' for t in record['tests']) else 'NEEDS_TUNING'
        except BaseException as exc:
            record['result'] = 'STOPPED_EARLY'
            record['error'] = str(exc)
            try:
                record['stop_request'] = query('MOTOR_STOP', 'MOTOR_STOP_')
            except Exception as stop_exc:
                record['stop_error'] = str(stop_exc)
            raise
        finally:
            try:
                time.sleep(.7)
                upload(False)
                time.sleep(.4)
                record['final_pulse'] = query('MOTOR_PULSE_STATUS', 'PULSE,')
                record['final_encoder'] = query('MOTOR_ENCODER_STATUS', 'ENCODER,')
            except Exception as cleanup_exc:
                record['cleanup_error'] = str(cleanup_exc)
            target.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print('Evidence:', target, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--execute', action='store_true', help='Run only after user asks to resume; wheels suspended')
    args = parser.parse_args()
    if not args.execute:
        print('Prepared only. No serial port opened and no motion commanded.')
        return
    run(args.port)


if __name__ == '__main__':
    main()
