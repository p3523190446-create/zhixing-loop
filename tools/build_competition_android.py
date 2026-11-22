"""Build the Android source kit with explicit SDK/JDK inputs; no install or network."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--android-jar', type=Path, required=True)
    parser.add_argument('--build-tools', type=Path, required=True, help='Android SDK build-tools directory')
    parser.add_argument('--jdk', type=Path, required=True, help='JDK home, containing bin/java and bin/javac')
    args = parser.parse_args()
    args.android_jar = args.android_jar.resolve(strict=True)
    args.build_tools = args.build_tools.resolve(strict=True)
    args.jdk = args.jdk.resolve(strict=True)
    source = args.source.resolve(strict=True)
    output = source / 'build'
    output.mkdir(exist_ok=True)
    # Fresh compiler work avoids stale .class files without deleting any previous build.
    work = Path(tempfile.mkdtemp(prefix='compile-', dir=output))
    classes = work / 'classes'
    dex = work / 'dex'
    classes.mkdir()
    dex.mkdir()
    suffix = '.exe' if os.name == 'nt' else ''
    java = args.jdk / 'bin' / ('java' + suffix)
    tools = args.build_tools
    core = source / 'third_party/uvc-core.jar'
    log = []

    def run(command):
        p = subprocess.run([str(x) for x in command], cwd=source, capture_output=True,
                           text=True, errors='replace', timeout=180)
        log.append(p.stdout + p.stderr)
        (output / 'build.log').write_text('\n'.join(log), encoding='utf-8')
        if p.returncode:
            raise RuntimeError(f'Build failed: {command[0]}\n{log[-1]}')

    run([args.jdk / 'bin' / ('javac' + suffix), '-encoding', 'UTF-8', '--release', '8',
         '-classpath', str(args.android_jar) + os.pathsep + str(core), '-d', classes,
         *sorted((source / 'java').glob('*.java'))])
    jar = work / 'classes.jar'
    with zipfile.ZipFile(jar, 'w') as dst:
        for path in classes.rglob('*.class'):
            dst.write(path, path.relative_to(classes).as_posix())
    run([java, '-cp', tools / 'lib/d8.jar', 'com.android.tools.r8.D8', '--min-api', '26',
         '--lib', args.android_jar, '--output', dex, jar, core])
    base = work / 'base.apk'
    run([tools / ('aapt2' + suffix), 'link', '-I', args.android_jar, '--manifest',
         source / 'java/AndroidManifest.xml', '-o', base])
    with zipfile.ZipFile(base, 'a', compression=zipfile.ZIP_DEFLATED) as dst:
        dst.write(dex / 'classes.dex', 'classes.dex')
        for path in (source / 'web').rglob('*'):
            if path.is_file(): dst.write(path, 'assets/web/' + path.relative_to(source / 'web').as_posix())
        for path in (source / 'notices').iterdir():
            if path.is_file(): dst.write(path, 'assets/notices/' + path.name)
        for path in (source / 'third_party/native/arm64-v8a').glob('*.so'):
            dst.write(path, 'lib/arm64-v8a/' + path.name)
    aligned = work / 'aligned.apk'
    run([tools / ('zipalign' + suffix), '-f', '-p', '4', base, aligned])
    # A fresh local debug key; never include the owner's keystore in the source kit.
    key = output / 'review-debug.keystore'
    if not key.exists():
        run([args.jdk / 'bin' / ('keytool' + suffix), '-genkeypair', '-keystore', key,
             '-storepass', 'android', '-keypass', 'android', '-alias', 'androiddebugkey',
             '-keyalg', 'RSA', '-keysize', '2048', '-validity', '3650',
             '-dname', 'CN=Android Debug,O=Android,C=US'])
    apk = output / 'zhixing-dashboard.apk'
    run([java, '-jar', tools / 'lib/apksigner.jar', 'sign', '--ks', key,
         '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', apk, aligned])
    run([java, '-jar', tools / 'lib/apksigner.jar', 'verify', '--verbose', apk])
    with zipfile.ZipFile(apk) as package:
        dex_hash = hashlib.sha256(package.read('classes.dex')).hexdigest()
    report = {'result': 'APK_BUILD_AND_SIGNATURE_PASS', 'apk_sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
              'dex_sha256': dex_hash, 'installed': False, 'physical_acceptance': 'NOT_RUN',
              'signing': 'local review debug key, not the installed app key'}
    (output / 'build-result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))

if __name__ == '__main__':
    main()
