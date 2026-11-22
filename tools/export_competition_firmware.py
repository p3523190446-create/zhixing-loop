"""Export a self-contained review candidate from a verified deployed source snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOFTWARE = ROOT / '知行回路软件'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='A NEW directory; no overwrites')
    parser.add_argument('--baseline', action='store_true', help='Exact last-built source, without refactor overlay')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        parser.error('Output already exists; keep previous candidates and use a new directory.')
    build = SOFTWARE / 'build/r1_line_task'
    snapshot = build / 'source-snapshot'
    record = json.loads((build / 'build_result.json').read_text(encoding='utf-8'))
    deployed = json.loads((ROOT / 'output/onboard_dashboard/phone-line-calibration-20261027/delivery.json').read_text(encoding='utf-8'))
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest(build / 'r1_line_task.bin') == record['binary_sha256'] == deployed['mcu_sha256']
    for name, expected in record['all_source_sha256'].items():
        assert digest(snapshot / name) == expected, 'Snapshot changed: ' + name
    work = Path.home() / 'Documents/ch32-tools/r1-line-task'
    # Check the assembled User tree before reusing its vendor and library dependencies.
    for name, expected in record['all_source_sha256'].items():
        assert digest(work / 'User' / name) == expected, 'Last build workspace changed: ' + name
    out.mkdir(parents=True)
    shutil.copytree(snapshot, out / 'User')
    for folder in ['SRC', 'ST_API', 'GuardCore']:
        shutil.copytree(work / folder, out / folder)
    if not args.baseline:
        for file in (SOFTWARE / 'board/r1_line_task').iterdir():
            if file.suffix in ('.c', '.h'):
                shutil.copy2(file, out / 'User' / file.name)
        for file in [SOFTWARE / 'board/r1_official_tt_full_speed/wheel_control.c',
                     SOFTWARE / 'board/r1_official_tt/driver_profile.c']:
            shutil.copy2(file, out / 'User' / file.name)
        shutil.copy2(SOFTWARE / 'board/r1_line_task/.clang-format', out / 'User/.clang-format')
    base = ['User/main.c', 'User/system_ch32v30x.c', 'User/ch32v30x_it.c',
            'SRC/Core/core_riscv.c', 'SRC/Debug/debug.c']
    base += [f'SRC/Peripheral/src/ch32v30x_{n}.c' for n in ['gpio', 'rcc', 'usart', 'misc', 'dbgmcu']]
    base += ['SRC/Startup/startup_ch32v30x_D8C.S', 'User/vl53l0x_platform.c']
    base += ['ST_API/' + n + '.c' for n in ['vl53l0x_api', 'vl53l0x_api_core', 'vl53l0x_api_calibration', 'vl53l0x_api_ranging', 'vl53l0x_api_strings']]
    base += ['SRC/Peripheral/src/ch32v30x_tim.c', 'GuardCore/app.c', 'GuardCore/guard.c']
    base += ['User/' + n + '.c' for n in ['vision_uart', 'oled_probe', 'oled_display', 'oled_probe2', 'oled_display2',
             'oled_probe3', 'oled_display3', 'storage_probe', 'settings', 'motor_probe', 'ultrasonic', 'servo_probe']]
    base += ['SRC/Peripheral/src/ch32v30x_exti.c', 'User/USB_Device/ch32v30x_usbfs_device.c',
             'User/USB_Device/usb_desc.c', 'User/native_usb.c', 'User/USB_Host/ch32v30x_usbhs_host.c']
    base += ['User/' + n + '.c' for n in ['uvc_bridge', 'remote_drive', 'wheel_control', 'driver_profile',
             'line_protocol', 'line_tracking', 'mpu6050_probe', 'imu_observer', 'line_task', 'line_task_runtime']]
    recipe = {
        'target': 'CH32V307 / CH32V30x_D8C',
        'flags': ['-march=rv32imacxw', '-mabi=ilp32', '-msmall-data-limit=8', '-msave-restore',
                  '-Os', '-g', '-ffunction-sections', '-fdata-sections', '-fno-common',
                  '-DCH32V30x_D8C', '-Wall', '-Wextra', '-DUSE_I2C_2V8', '-DUSBHS_MAX_PACKET_SIZE=512'],
        'includes': ['User', 'SRC/Core', 'SRC/Debug', 'SRC/Peripheral/inc',
                     'ST_API', 'GuardCore', 'User/USB_Device', 'User/UART', 'User/USB_Host'],
        'sources': base, 'linker_script': 'SRC/Ld/Link.ld',
    }
    (out / 'build.json').write_text(json.dumps(recipe, indent=2) + '\n', encoding='utf-8')
    shutil.copy2(SOFTWARE / 'tools/build_competition_firmware.py', out / 'build.py')
    shutil.copy2(SOFTWARE / 'board/r1_line_task/README.md', out / '巡线代码说明.md')
    (out / 'README.md').write_text('''# 知行回路：主控源码评审候选

这是本轮代码整理的候选，不是已烧入车上的固件，也不是四项齐全的最终赛事提交包。

## 直接构建

需要Python 3.9或更新版本，以及支持rv32imacxw的WCH RISC-V GCC。本轮验证的编译器是xPack 8.2.0；普通RISC-V GCC不一定支持该指令集。

```powershell
python build.py --toolchain '你的工具链/bin目录'
```

脚本从本目录的明确源码表build.json直接编译，不导入旧版本、不替换源代码、不下载文件、不连接设备。输出位于build目录，包括ELF、HEX、BIN、map、完整日志和源码指纹报告。

## 从哪里读

User/main.c：初始化和主循环。User/line_task.c：循迹状态机。User/line_task_runtime.c：命令、租约、许可与驱动适配。User/remote_drive.c：执行请求与原保护。User/line_tracking.c：传感器输入。GuardCore：距离判断基础。ST_API：ST测距驱动。SRC：WCH芯片库、启动和链接文件。

build.json是实际参与编译的文件表；SDK/旧头文件按原树保留，不能把目录中每个文件都当作本项目独立编写或实际使用。原厂/开源文件头保留，具体使用来源、修改范围和许可证须随最终总包说明。

地面循迹许可仍为0，独立停止和整车实测尚未验收。本脚本不包含烧录入口。

此候选不含安卓/网页完整源码；提交时须另纳入本次实际使用的手机、操作端及依赖材料。请先看代码审查报告，不要直接发此目录作为全部作品。
''', encoding='utf-8')
    files = sorted(p for p in out.rglob('*') if p.is_file())
    manifest = {'kind': 'baseline' if args.baseline else 'refactor_candidate',
                'deployed_baseline_binary_sha256': record['binary_sha256'],
                'baseline_delivery': '2026-10-27 phone 0.25.5 + line-task calibration firmware',
                'device_deployment': 'NOT_RUN', 'files': {p.relative_to(out).as_posix(): digest(p) for p in files}}
    (out / 'source-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(out), 'kind': manifest['kind'], 'files': len(files), 'translation_units': len(base)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
