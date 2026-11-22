"""Start/stop/status for the one hidden, persistent USB bridge."""
import argparse
import json
import msvcrt
from pathlib import Path
import subprocess
import sys
import time
from monitor_bridge import LOCK, OUTPUT, STATUS, STOP


def active():
    if not LOCK.exists():
        return False
    with LOCK.open('r+b') as f:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return True
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status'])
    action = parser.parse_args().action
    OUTPUT.mkdir(exist_ok=True, parents=True)
    if action == 'start':
        if not active():
            # Fresh state before child launch; the child owns the singleton lock.
            with (OUTPUT/'monitor-stdout.log').open('w', encoding='utf-8') as stdout, \
                    (OUTPUT/'monitor-stderr.log').open('w', encoding='utf-8') as stderr:
                subprocess.Popen([sys.executable, str(Path(__file__).with_name('monitor_bridge.py'))],
                                 stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                 creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
            for _ in range(50):
                if active():
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('Monitor did not start; inspect monitor-stderr.log')
        print('Persistent monitor running; no automatic expiry.')
    elif action == 'stop':
        if active():
            STOP.write_text('stop\n', encoding='ascii')
            for _ in range(80):
                if not active():
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('Monitor is still stopping; no arbitrary process killed')
        print('Monitor stopped.')
    else:
        data = json.loads(STATUS.read_text(encoding='utf-8')) if STATUS.exists() else {}
        data['singleton_lock_active'] = active()
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
