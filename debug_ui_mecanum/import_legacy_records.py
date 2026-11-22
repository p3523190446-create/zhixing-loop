"""Verify/package legacy raw records; optionally import into dashboard via ADB.

No uninstall, app-data clearing, foreground switch or MCU command is performed.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import io
import json
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'output/car_phone/readback-20261013-162715'
OUT = ROOT / 'output/onboard_dashboard'
PACKAGE = 'cn.zhixing.dashboard'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_path(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not name or '\\' in name:
        raise ValueError('Invalid record path')
    return p.as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import-device', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((SOURCE / 'import-manifest.json').read_text(encoding='utf-8'))
    records = {}
    for entry in manifest['files']:
        name = validate_path(entry['path'])
        if name in records:
            raise ValueError('Duplicate record path')
        data = (SOURCE / 'files' / name).read_bytes()
        assert len(data) == entry['bytes'] and sha(data) == entry['sha256'], name
        records[name] = data
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / 'legacy-carconsole.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as dst:
        dst.writestr('import-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        for name, data in records.items():
            dst.writestr('files/' + name, data)
    with zipfile.ZipFile(archive) as src:
        for name, data in records.items():
            assert src.read('files/' + name) == data, name
    report = {'source_package': manifest['source_package'], 'destination_package': PACKAGE,
              'files': len(records), 'sessions': len({n.split('/')[1] for n in records if n.startswith('sessions/')}),
              'archive': str(archive), 'archive_sha256': sha(archive.read_bytes()),
              'raw_byte_verification': 'PASS', 'device_import': 'NOT_PERFORMED',
              'contains_video': False, 'existing_app_data': 'PRESERVED'}
    # Save preservation evidence even when no device is connected.
    report_path = OUT / 'legacy-preservation.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.import_device:
        adb = ROOT / 'tmp/android-tools/platform-tools/adb.exe'
        def call(*parts, data=None):
            return subprocess.run([str(adb), *parts], input=data, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, check=True).stdout
        # Stage separately from live sessions. All source bytes are immutable.
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w') as dst:
            for name, data in records.items():
                entry = tarfile.TarInfo('files/imported-carconsole/' + name)
                entry.size = len(data)
                dst.addfile(entry, io.BytesIO(data))
        call('shell', 'run-as', PACKAGE, 'mkdir', '-p', 'files/imported-carconsole')
        # exec-in carries binary stdin without a terminal or shell interpolation.
        call('exec-in', 'run-as', PACKAGE, 'tar', '-xf', '-', data=buffer.getvalue())
        for name, data in records.items():
            actual = call('exec-out', 'run-as', PACKAGE, 'cat', 'files/imported-carconsole/' + name)
            assert actual == data, name
        report['device_import'] = 'PASS_28_FILES_ORIGINAL_BYTES' if len(records) == 28 else 'PASS_ORIGINAL_BYTES'
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
