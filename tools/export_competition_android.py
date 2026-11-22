"""Export current Android/web code and camera dependencies, without personal state."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOFTWARE = ROOT / '知行回路软件'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='A new directory')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists(): parser.error('Use a new output directory; previous candidates are retained.')
    ui = SOFTWARE / 'debug_ui'
    out.mkdir(parents=True)
    shutil.copytree(ui / 'android', out / 'java')
    shutil.copytree(ui / 'assets', out / 'web/assets')
    shutil.copy2(ui / 'index.html', out / 'web/index.html')
    deps = out / 'third_party'
    deps.mkdir()
    with zipfile.ZipFile(ROOT / 'tmp/uvc-android/aar/classes.jar') as src, zipfile.ZipFile(deps / 'uvc-core.jar', 'w') as dst:
        for name in src.namelist():
            if ((name.startswith('com/serenegiant/usb/') and not name.startswith('com/serenegiant/usb/CameraDialog'))
                or name.startswith('com/serenegiant/utils/HandlerThreadHandler')
                or name == 'com/serenegiant/uvccamera/BuildConfig.class'):
                dst.writestr(name, src.read(name))
    native = deps / 'native/arm64-v8a'
    native.mkdir(parents=True)
    for file in (ROOT / 'tmp/uvc-android/aar/jni/arm64-v8a').glob('*.so'):
        origin = ROOT / 'output/onboard_dashboard/camera-compat-20261026/native/libUVCCamera.so' if file.name == 'libUVCCamera.so' else file
        shutil.copy2(origin, native / file.name)
    upstream = ROOT / 'tmp/uvc-compat-1.0.13'
    native_work = Path.home() / '.cache/zhixing-uvc-compat-20261026'
    uvc = deps / 'UVCAndroid'
    shutil.copytree(native_work / 'jni', uvc / 'jni')
    shutil.copytree(native_work / 'prebuilt', uvc / 'prebuilt')
    shutil.copytree(upstream / 'libuvccamera/src/main/java', uvc / 'java')
    for name in ['Android.mk', 'Application.mk']:
        shutil.copy2(native_work / name, uvc / name)
    shutil.copy2(upstream / 'LICENSE', uvc / 'LICENSE')
    shutil.copy2(ROOT / 'tmp/uvc-android/UVCAndroid-1.0.13-sources.jar', deps / 'UVCAndroid-1.0.13-sources.jar')
    notices = out / 'notices'
    notices.mkdir()
    shutil.copy2(upstream / 'LICENSE', notices / 'UVCAndroid-1.0.13-LICENSE.txt')
    (notices / 'UVCAndroid-CHANGES.txt').write_text(
        'Based on shiyinghan/UVCAndroid 1.0.13 (6018c7f20238832929cf61427427bb7828056260). '
        'Modified uncompressed preview dispatch from uvc_yuyv2rgbx to uvc_any2rgbx for YUYV/UYVY compatibility. '
        'Original MJPEG path retained.\n', encoding='utf-8')
    shutil.copy2(SOFTWARE / 'tools/build_competition_android.py', out / 'build.py')
    (out / 'README.md').write_text('''# 知行回路：安卓和网页源码评审候选

java为实际应用源码，web为手机与电脑浏览器共用的前端。入口为MainActivity、GatewayService（HTTP和交互）、TelemetryService（唯一USB工作线程）；LineTaskBroker/DriveBroker/ControlBroker分管巡线、行驶和云台请求。LineCalibration负责现场采样质量、持久保存与主控回读。

## 构建

需要Python 3.9+、JDK17、Android平台API33与build-tools35（本轮实际验证版本）；工具链本身不打包。提供路径后可离线编译，不依赖原作者的缓存目录或phone_vision旧构建脚本：

```powershell
python build.py --android-jar 'SDK/platforms/android-33/android.jar' --build-tools 'SDK/build-tools/35.0.0' --jdk 'JDK17目录'
```

输出在build目录；脚本会创建仅供评审的本地调试签名，不复制本人密钥。该签名与车上已安装应用不同，不能直接当作原应用的无损升级。本轮只构建验证，没有安装或清除车上数据。

## 相机依赖与来源

third_party/uvc-core.jar及native/arm64-v8a是固定版本外部依赖，来自UVCAndroid1.0.13；源代码、LICENSE、修改说明同时保留，不能标成自写模块。UVCAndroid目录包含本次实际使用的已修补JNI源码、Android.mk、Application.mk及原依赖库；Java源代码与原sources.jar也保留。该工程先复用4个原生依赖，只重建UVCCamera桥，原预览/像素分派变更详见notices。

若需要重建桥：进入third_party/UVCAndroid，以Android NDK r29运行 `ndk-build NDK_PROJECT_PATH=. APP_BUILD_SCRIPT=Android.mk NDK_APPLICATION_MK=Application.mk`，再将libs/arm64-v8a/libUVCCamera.so复制到third_party/native/arm64-v8a。桥重建属于独立构建步骤，本次新入口只验证了使用固定依赖的完整APK打包。

本目录不包含真实车况日志、照片、视频、配置存储、运行令牌或原作者签名密钥。源码中的运行时令牌生成逻辑保留，它与导出私人令牌是不同事情。

网页回放只读取历史记录；控制请求仍经手机USB线程和CH32检查。手机/模型/主控职责不能由这份源码导出推断为赛事已认可或实车已验收。
''', encoding='utf-8')
    files = sorted(p for p in out.rglob('*') if p.is_file())
    manifest = {'kind': 'android_web_source_review_candidate', 'installed': False,
                'files': {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (out / 'source-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(out), 'files': len(files), 'java_sources': len(list((out / 'java').glob('*.java')))}, ensure_ascii=False))

if __name__ == '__main__':
    main()
