"""Build a frozen firmware source tree directly. Never flashes or opens a device."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--toolchain', type=Path, help='Directory containing riscv-none-embed-gcc(.exe)')
    parser.add_argument('--output', type=Path, help='Build output, default: SOURCE/build')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    output = (args.output or source / 'build').resolve()
    recipe = json.loads((source / 'build.json').read_text(encoding='utf-8'))
    compiler = 'riscv-none-embed-gcc' + ('.exe' if os.name == 'nt' else '')
    toolchain = args.toolchain or os.environ.get('CH32_GCC_BIN')
    found = Path(toolchain) / compiler if toolchain else shutil.which(compiler)
    if not found or not Path(found).is_file():
        parser.error('Provide --toolchain or CH32_GCC_BIN, or put the WCH RISC-V compiler on PATH.')
    found = Path(found).resolve()
    bindir = found.parent
    suffix = '.exe' if os.name == 'nt' else ''
    for file in recipe['sources']:
        if not (source / file).is_file():
            parser.error('Missing source: ' + file)
    output.mkdir(parents=True, exist_ok=True)
    log = []

    def run(command):
        result = subprocess.run([str(x) for x in command], cwd=source, capture_output=True,
                                text=True, errors='replace', timeout=120)
        log.append(result.stdout + result.stderr)
        (output / 'build.log').write_text('\n'.join(log), encoding='utf-8')
        if result.returncode:
            raise RuntimeError(f'Build failed ({result.returncode}): {command[0]}\n{log[-1]}')
        return result.stdout

    flags = recipe['flags']
    includes = ['-I' + path for path in recipe['includes']]
    objects = []
    for index, file in enumerate(recipe['sources']):
        obj = output / f'{index}_{Path(file).stem}.o'
        run([found, *flags, *includes, '-c', file, '-o', obj])
        objects.append(obj)
    stem = 'r1_line_task'
    elf = output / (stem + '.elf')
    run([found, *flags, '-nostartfiles', '--specs=nano.specs', '--specs=nosys.specs',
         '-Wl,--gc-sections', '-Wl,-Map,' + str(output / (stem + '.map')),
         '-T' + recipe['linker_script'], *objects, '-lm', '-o', elf])
    for kind, extension in [('ihex', 'hex'), ('binary', 'bin')]:
        run([bindir / ('riscv-none-embed-objcopy' + suffix), '-O', kind, elf,
             output / (stem + '.' + extension)])
    size = run([bindir / ('riscv-none-embed-size' + suffix), elf])
    files = [p for folder in ['User', 'SRC', 'ST_API', 'GuardCore']
             for p in (source / folder).rglob('*') if p.is_file()]
    report = {
        'result': 'MCU_COMPILE_PASS',
        'built_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'compiler': run([found, '--version']).splitlines()[0],
        'size_report': size,
        'compiled_translation_units': len(objects),
        'binary_sha256': hashlib.sha256((output / (stem + '.bin')).read_bytes()).hexdigest(),
        'source_sha256': {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(files)},
        'flash': 'NOT_RUN', 'physical_acceptance': 'NOT_RUN',
        'warning_lines': [line for part in log for line in part.splitlines() if 'warning:' in line],
    }
    (output / 'build-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'source_sha256'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
