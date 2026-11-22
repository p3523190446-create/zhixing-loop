"""Calibrate the deployed car's axes from its signed ground observations.

Keep the standard X mixer unchanged. Apply the channel permutation to BOTH
VECTOR and the line task's SET interface, before the per-channel controller.
This is an empirical output profile, not a claim that a rear plug was swapped.
"""
from pathlib import Path
import hashlib
import json
import shutil
import build_r1_mecanum_integrated as previous
from prepare_mecanum import replace

build = previous.build
BASE = build.OUT / 'source-snapshot'
BASE_BINARY = build.OUT / (build.STEM + '.bin')
BASE_WORK = build.WORK
BASE_SHA = '0a2dd5c0a2d27ba8394a7d91b9e822cfd5a18722426b20213dab895536f23d84'
assert hashlib.sha256(BASE_BINARY.read_bytes()).hexdigest() == BASE_SHA
build.STEM = 'r1_mecanum_groundmap'
build.WORK = build.TOOLS / 'r1-mecanum-groundmap'
build.OUT = build.PROJECT / '知行回路软件/build' / build.STEM
OVERLAY = build.PROJECT / '知行回路软件/board' / build.STEM
IDENTITY = 'R1_DRIVE_STARTUP_MANUAL_MECANUM_V3_20261107'
CHASSIS = 'DRIVE_CHASSIS,MECANUM_GROUND_MAP,SWAP_M2_M4,250,600'


def prepare():
    OVERLAY.mkdir(exist_ok=True)
    s = (BASE / 'remote_drive.c').read_text(encoding='utf-8')
    s = replace(s, previous.IDENTITY, IDENTITY)
    s = replace(s, 'DRIVE_CHASSIS,MECANUM_X,FL_RL_FR_RR,250,600', CHASSIS)
    s = replace(s, 'static int32_t desired_wheels[4],desired_forward,desired_strafe,desired_turn;', '''static int32_t desired_wheels[4],desired_forward,desired_strafe,desired_turn;
/* Ground report: old +yaw translates right; old +strafe rotates right.
 * Swapping output channels 2/4 exchanges those basis vectors and preserves
 * forward, zero and the common speed limit. Feedback stays in driver order.
 * Apply once when accepting a target, never repeatedly in the poll loop. */
static void map_ground_channels(void)
{
    int32_t second=desired_wheels[1];
    desired_wheels[1]=desired_wheels[3];desired_wheels[3]=second;
}''')
    s = replace(s, 'memcpy(desired_wheels,targets,sizeof(targets));desired_left=targets[0];desired_right=targets[2];',
                'memcpy(desired_wheels,targets,sizeof(targets));map_ground_channels();desired_left=targets[0];desired_right=targets[2];')
    s = replace(s, 'desired_wheels[0]=desired_wheels[1]=left;desired_wheels[2]=desired_wheels[3]=right;',
                'desired_wheels[0]=desired_wheels[1]=left;desired_wheels[2]=desired_wheels[3]=right;map_ground_channels();')
    (OVERLAY / 'remote_drive.c').write_text(s, encoding='utf-8')
    for name in ('ST_API', 'GuardCore'):
        shutil.copytree(BASE_WORK / name, build.WORK / name, dirs_exist_ok=True)
    shutil.copytree(BASE, build.WORK / 'User', dirs_exist_ok=True)
    shutil.copy2(OVERLAY / 'remote_drive.c', build.WORK / 'User/remote_drive.c')


build.PREPARE = prepare
if __name__ == '__main__':
    build.main()
    snap = build.OUT / 'source-snapshot'
    shutil.copytree(build.WORK / 'User', snap, dirs_exist_ok=True)
    changed = sorted(p.relative_to(snap).as_posix() for p in snap.rglob('*')
                     if p.is_file() and (not (BASE / p.relative_to(snap)).exists()
                     or p.read_bytes() != (BASE / p.relative_to(snap)).read_bytes()))
    assert changed == ['remote_drive.c'], changed
    p = build.OUT / 'build_result.json'
    d = json.loads(p.read_text(encoding='utf-8'))
    d.update(date='2026-11-07', identity=IDENTITY, chassis=CHASSIS,
             scope='Empirical ground-axis correction; unchanged canonical mixer and safety controller',
             channel_permutation=[1, 4, 3, 2],
             calibration_basis='USER_GROUND_REPORT: orange right -> right translation; blue right -> right yaw; forward normal',
             physical_wiring_cause='UNCONFIRMED', baseline_binary_sha256=BASE_SHA,
             changed_sources_vs_deployed=changed, flash='NOT_RUN', physical_acceptance='NOT_RUN',
             all_source_sha256={x.relative_to(snap).as_posix(): hashlib.sha256(x.read_bytes()).hexdigest()
                                for x in snap.rglob('*') if x.is_file()})
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
