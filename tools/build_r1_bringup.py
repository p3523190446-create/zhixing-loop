"""Build the first MCU experiment from WCH EVT; never flashes hardware."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[2]
EVT = PROJECT / '硬件资料/CH32V307资料包/EVT/EXAM'
TOOLS = Path.home() / 'Documents/ch32-tools'
WORK = TOOLS / 'r1-bringup'
BIN = TOOLS / 'gcc/bin'
OUT = PROJECT / '知行回路软件/build/r1_bringup'
STEM = 'r1_bringup'
MAIN_SOURCE = PROJECT / '知行回路软件/board/r1_bringup/main.c'
EXTRA_SOURCES = []
EXTRA_INCLUDE_DIRS = []
EXTRA_FLAGS = []
PREPARE = None

def run(args):
    result = subprocess.run([str(x) for x in args], cwd=WORK,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=90)
    if result.stdout:
        print(result.stdout, end='')
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}): {args[0]}')
    return result.stdout

def main():
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(EVT / 'SRC', WORK / 'SRC', dirs_exist_ok=True)
    shutil.copytree(EVT / 'GPIO/GPIO_Toggle/User', WORK / 'User', dirs_exist_ok=True)
    shutil.copy2(MAIN_SOURCE, WORK / 'User/main.c')
    if PREPARE:
        PREPARE()
    flags = ['-march=rv32imacxw', '-mabi=ilp32', '-msmall-data-limit=8', '-msave-restore',
             '-Os', '-g', '-ffunction-sections', '-fdata-sections', '-fno-common',
             '-DCH32V30x_D8C', '-Wall', '-Wextra', *EXTRA_FLAGS]
    includes = ['-IUser', '-ISRC/Core', '-ISRC/Debug', '-ISRC/Peripheral/inc']
    includes += ['-I'+str(x) for x in EXTRA_INCLUDE_DIRS]
    sources = [Path('User/main.c'), Path('User/system_ch32v30x.c'), Path('User/ch32v30x_it.c'),
               Path('SRC/Core/core_riscv.c'), Path('SRC/Debug/debug.c')]
    sources += [Path(f'SRC/Peripheral/src/ch32v30x_{name}.c')
                for name in ['gpio', 'rcc', 'usart', 'misc', 'dbgmcu']]
    sources += [Path('SRC/Startup/startup_ch32v30x_D8C.S')]
    sources += EXTRA_SOURCES
    objects = []
    for index, source in enumerate(sources):
        obj = f'{index}_{source.stem}.o'
        run([BIN / 'riscv-none-embed-gcc.exe', *flags, *includes, '-c', source, '-o', obj])
        objects.append(obj)
    run([BIN / 'riscv-none-embed-gcc.exe', *flags, '-nostartfiles', '--specs=nano.specs',
         '--specs=nosys.specs', '-Wl,--gc-sections', f'-Wl,-Map,{STEM}.map',
         '-TSRC/Ld/Link.ld', *objects, '-o', f'{STEM}.elf'])
    for kind in ['ihex', 'binary']:
        extension = 'hex' if kind == 'ihex' else 'bin'
        run([BIN / 'riscv-none-embed-objcopy.exe', '-O', kind,
             f'{STEM}.elf', f'{STEM}.{extension}'])
    size = run([BIN / 'riscv-none-embed-size.exe', f'{STEM}.elf'])
    compiler = run([BIN / 'riscv-none-embed-gcc.exe', '--version']).splitlines()[0]
    for extension in ['elf', 'hex', 'bin', 'map']:
        shutil.copy2(WORK / f'{STEM}.{extension}', OUT)
    record = {'date': '2026-10-06', 'result': 'MCU_COMPILE_PASS', 'compiler': compiler,
              'target': 'CH32V307 / CH32V30x_D8C', 'size_report': size,
              'source_sha256': hashlib.sha256((WORK / 'User/main.c').read_bytes()).hexdigest(),
              'binary_sha256': hashlib.sha256((WORK / f'{STEM}.bin').read_bytes()).hexdigest(),
              'flash': 'NOT_RUN', 'physical_led': 'NOT_RUN', 'power_cycle': 'NOT_RUN'}
    (OUT / 'build_result.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print('MCU_COMPILE_PASS')

if __name__ == '__main__':
    main()
