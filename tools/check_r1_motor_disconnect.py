"""M1 suspended feedback-wire disconnect trial; default is idle preflight only.

Physical action: remove yellow driver TX2 -> CH32 PD9 only, after START.
Green command wire and black common ground must remain connected.
Mechanical stop is a separate human observation, not inferred from TX counts.
"""
from pathlib import Path
import argparse
import datetime
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def run(port, execute):
    sys.path.insert(0, str(Path.home() / 'Documents/ch32-tools/python-support'))
    import serial
    out = ROOT / '知行回路软件/build/r1_motor_stable'
    stamp = datetime.datetime.now().astimezone()
    record = {'recorded_at': stamp.isoformat(), 'firmware': 'r1_motor_stable',
              'scope': 'SUSPENDED_M1_YELLOW_FEEDBACK_WIRE_ONLY',
              'mechanical_stop': 'AWAITING_USER_OBSERVATION',
              'green_command_disconnect': 'NOT_TESTED', 'transcript': []}
    path = out / (('disconnect-' if execute else 'disconnect-preflight-') +
                  stamp.strftime('%Y%m%d-%H%M%S-%f') + '.json')
    with serial.Serial(port, 115200, timeout=.1, write_timeout=1) as link:
        def query(command, prefix):
            link.write(command.encode('ascii') + b'\n')
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                row = link.readline().decode('ascii', errors='replace').strip()
                if row:
                    record['transcript'].append({'command': command, 'reply': row})
                if row.startswith(prefix):
                    return row
            raise TimeoutError(command + ': no blind retry')

        def vals(command, prefix):
            return [int(x) for x in query(command, prefix).split(',')[1:]]

        def require(condition, message):
            if not condition:
                raise RuntimeError(message)

        def upload(enable):
            for _ in range(20):
                reply = query('MOTOR_ENCODER_ON' if enable else 'MOTOR_ENCODER_OFF', 'ENCODER_UPLOAD_')
                if reply == 'ENCODER_UPLOAD_QUEUED':
                    return
                require(reply == 'ENCODER_UPLOAD_BUSY', reply)
                time.sleep(.1)
            raise RuntimeError('Upload unavailable')

        try:
            before = vals('MOTOR_PULSE_STATUS', 'PULSE,')
            health = vals('MOTOR_STATUS', 'MOTOR,')
            fault = vals('MOTOR_FAULT_STATUS', 'MOTORFAULT,')
            record['preflight'] = {'pulse': before, 'health': health, 'fault': fault}
            require(before[0] == 0, 'Motion already active')
            require(health[1:3] == [0, 0], 'UART errors/drops present')
            require(len(fault) == 9, 'Diagnostic firmware not available')
            if not execute:
                record['result'] = 'IDLE_PREFLIGHT_ONLY_NO_MOTION'
                print(record['result'], flush=True)
                return
            upload(True)
            time.sleep(3.5)
            live = vals('MOTOR_LIVE_STATUS', 'MOTORLIVE,')
            require(len(live) == 17 and max(live[1:3]) < 250, 'Feedback not fresh')
            require(all(abs(v) < 20 for v in live[7:11]), 'Wheels not stationary')
            record['live_before'] = live
            ack = query('MOTOR_CLOSED_M1', 'MOTOR_CLOSED_')
            record['start_reply'] = ack
            require(ack == 'MOTOR_CLOSED_STARTED,M1', 'Start not confirmed; no retry')
            print('START: M1 only. Remove YELLOW PD9 now; keep GREEN and GND connected.', flush=True)
            record['samples'] = []
            deadline = time.monotonic() + 13
            while time.monotonic() < deadline:
                live = vals('MOTOR_LIVE_STATUS', 'MOTORLIVE,')
                record['samples'].append(live)
                if not live[13]:
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('Motion exceeded bounded trial')
            time.sleep(.7)
            fault = vals('MOTOR_FAULT_STATUS', 'MOTORFAULT,')
            after = vals('MOTOR_PULSE_STATUS', 'PULSE,')
            record['fault_after'] = fault
            record['pulse_after'] = after
            require(after[0] == 0 and after[2] == before[2] + 3, 'Zero-PWM frames incomplete')
            record['result'] = ('STALE_FEEDBACK_STOP_COMMAND_VERIFIED_MECHANICAL_PENDING'
                                if fault[0] == 4 else 'DISCONNECT_NOT_CONFIRMED')
            print(record['result'], flush=True)
        except BaseException as exc:
            record['result'] = 'STOPPED_EARLY'
            record['error'] = str(exc)
            if execute:
                try:
                    record['emergency_stop'] = query('MOTOR_STOP', 'MOTOR_STOP_')
                except Exception as stop_exc:
                    record['stop_error'] = str(stop_exc)
            raise
        finally:
            if execute:
                try:
                    upload(False)
                    time.sleep(.5)
                    record['final_pulse'] = query('MOTOR_PULSE_STATUS', 'PULSE,')
                except Exception as cleanup_exc:
                    record['cleanup_error'] = str(cleanup_exc)
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print('Evidence:', path, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--execute', action='store_true', help='Only with user ready at yellow PD9; wheels suspended')
    args = parser.parse_args()
    run(args.port, args.execute)
