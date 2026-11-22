"""Build the fixed COCO/n-320/CPU test app without Android Studio or Gradle."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
CACHE = Path.home() / '.cache' / 'zhixing-android-tools'
BUILD = Path.home() / '.cache' / 'zhixing-android-build'
APK_NAME = 'zhixing-vision-debug.apk'
PROFILE_DESC = 'COCO YOLOv8n 320 CPU'
REPORT_NAME = 'build-verification.json'
JAVA_SOURCE_DIR = HERE / 'android'


def unique(pattern):
    matches = list(CACHE.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f'Expected one {pattern}, got {matches}')
    return matches[0].resolve()


def run(args, **kwargs):
    print('Running:', Path(str(args[0])).name, flush=True)
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def prepare_native():
    source = BUILD / 'native'
    source.mkdir(parents=True, exist_ok=True)
    for path in (HERE / 'upstream').iterdir():
        shutil.copy2(path, source / path.name)
    for path in (HERE / 'native').iterdir():
        shutil.copy2(path, source / path.name)
    main = source / 'yolov8ncnn.cpp'
    text = main.read_text(encoding='utf-8')
    text = text.replace('#include "yolov8.h"', '#include "yolov8.h"\n#include "vision_export.h"')
    old = '            g_yolov8->detect(rgb, objects);'
    assert text.count(old) == 1
    text = text.replace(old, '''            const double started = ncnn::get_current_time();
            const int detected = g_yolov8->detect(rgb, objects);
            const double inference_ms = ncnn::get_current_time() - started;
            if (detected == 0) zxr::publish(rgb, objects, inference_ms);
            else __android_log_print(ANDROID_LOG_ERROR, "ZXR_VISION", "detection_failed");''')
    text = text.replace('if (taskid < 0 || taskid > 5 || modelid < 0 || modelid > 8 || cpugpu < 0 || cpugpu > 2)',
                        'if (taskid != 0 || modelid != 0 || cpugpu != 0)')
    text = re.sub(r'^\s*if \(taskid == [1-5]\) g_yolov8 = new [^;]+;\n', '', text, flags=re.M)
    old = '                g_yolov8->load(mgr, parampath.c_str(), modelpath.c_str(), use_gpu || use_turnip);'
    assert text.count(old) == 1
    text = text.replace(old, '''                if (g_yolov8->load(mgr, parampath.c_str(), modelpath.c_str(), false) != 0) {
                    delete g_yolov8;
                    g_yolov8 = 0;
                    return JNI_FALSE;
                }''')
    # Report actual camera-open status rather than unconditional success.
    old = '    g_camera->open((int)facing);\n\n    return JNI_TRUE;'
    assert text.count(old) == 1
    text = text.replace(old, '    return g_camera->open((int)facing) == 0 ? JNI_TRUE : JNI_FALSE;')
    offset = text.rfind('\n}')
    text = text[:offset] + '''
JNIEXPORT jstring JNICALL Java_com_tencent_yolov8ncnn_YOLOv8Ncnn_getDetections(JNIEnv* env, jobject) {
    const std::string result = zxr::latest();
    return env->NewStringUTF(result.c_str());
}
''' + text[offset:]
    main.write_text(text, encoding='utf-8')
    (source / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.10)
project(yolov8ncnn LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(OpenCV REQUIRED core imgproc)
find_package(ncnn REQUIRED)
add_library(yolov8ncnn SHARED yolov8ncnn.cpp yolov8.cpp yolov8_det.cpp ndkcamera.cpp vision_export.cpp)
target_link_libraries(yolov8ncnn ncnn ${OpenCV_LIBS} camera2ndk mediandk android log)
''', encoding='utf-8')
    return source


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    ndk = unique('android-ndk-r29-windows/android-ndk-r29')
    cmake = unique('cmake-3.31.5-windows/**/bin/cmake.exe')
    ninja = unique('cmake-3.31.5-windows/**/bin/ninja.exe')
    android_jar = unique('platform-33-ext3_r03/**/android.jar')
    aapt = unique('build-tools_r35_windows/**/aapt2.exe')
    d8 = unique('build-tools_r35_windows/**/lib/d8.jar')
    signer = unique('build-tools_r35_windows/**/lib/apksigner.jar')
    align = unique('build-tools_r35_windows/**/zipalign.exe')
    ncnn_config = unique('ncnn-20260526-android-vulkan/**/arm64-v8a/lib/cmake/ncnn/ncnnConfig.cmake')
    opencv_config = unique('opencv-mobile-4.13.0-android/**/sdk/native/jni/OpenCVConfig.cmake')
    java_home = Path(os.environ['JAVA_HOME'])
    java, javac, keytool = (java_home / 'bin' / (n + '.exe') for n in ['java', 'javac', 'keytool'])
    source = prepare_native()
    native_build = BUILD / 'cmake-build'
    run([cmake, '-S', source, '-B', native_build, '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_MAKE_PROGRAM=' + str(ninja),
         '-DCMAKE_TOOLCHAIN_FILE=' + str(ndk / 'build/cmake/android.toolchain.cmake'),
         '-DANDROID_ABI=arm64-v8a', '-DANDROID_PLATFORM=android-24', '-DANDROID_STL=c++_static',
         '-DOpenCV_DIR=' + str(opencv_config.parent), '-Dncnn_DIR=' + str(ncnn_config.parent)])
    run([cmake, '--build', native_build, '--parallel', '4'])
    native = native_build / 'libyolov8ncnn.so'
    java_sources = BUILD / 'java'
    java_sources.mkdir(exist_ok=True)
    for path in JAVA_SOURCE_DIR.glob('*.java'):
        shutil.copy2(path, java_sources / path.name)
    classes = BUILD / 'classes'; classes.mkdir(exist_ok=True)
    run([javac, '-encoding', 'UTF-8', '-source', '8', '-target', '8', '-bootclasspath', android_jar,
         '-d', classes, *java_sources.glob('*.java')])
    class_jar = BUILD / 'classes.jar'
    with zipfile.ZipFile(class_jar, 'w') as contents:
        for path in classes.rglob('*.class'):
            contents.write(path, path.relative_to(classes).as_posix())
    dex = BUILD / 'dex'; dex.mkdir(exist_ok=True)
    run([java, '-cp', d8, 'com.android.tools.r8.D8', '--min-api', '24', '--lib', android_jar,
         '--output', dex, class_jar])
    base = BUILD / 'base.apk'
    run([aapt, 'link', '-I', android_jar, '--manifest', HERE / 'android/AndroidManifest.xml', '-o', base])
    release = WORKSPACE / 'tmp/android-tools/ncnn-android-yolov8-20260527.f1ac75e.apk'
    if not release.exists() or hashlib.file_digest(release.open('rb'), 'sha256').hexdigest() != 'dfaa20c931918a6281bedcef9292d68895537d1046774fa0c6f4fc32d3bb3be8':
        raise RuntimeError('Pinned upstream APK missing or checksum mismatch; see README')
    with zipfile.ZipFile(base, 'a') as output, zipfile.ZipFile(release) as original:
        output.write(dex / 'classes.dex', 'classes.dex', compress_type=zipfile.ZIP_DEFLATED)
        output.write(native, 'lib/arm64-v8a/libyolov8ncnn.so', compress_type=zipfile.ZIP_DEFLATED)
        for name in ['assets/yolov8n.ncnn.bin', 'assets/yolov8n.ncnn.param']:
            output.writestr(name, original.read(name), compress_type=zipfile.ZIP_STORED)
    aligned = BUILD / 'aligned.apk'
    run([align, '-f', '-p', '4', base, aligned])
    key = CACHE / 'zhixing-debug.keystore'
    if not key.exists():
        run([keytool, '-genkeypair', '-keystore', key, '-storepass', 'android', '-keypass', 'android',
             '-alias', 'zhixing-debug', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '3650',
             '-dname', 'CN=Zhixing Local Debug'])
    output_dir = WORKSPACE / 'output/phone_vision'; output_dir.mkdir(parents=True, exist_ok=True)
    apk = output_dir / APK_NAME
    run([java, '-jar', signer, 'sign', '--ks', key, '--ks-pass', 'pass:android', '--key-pass', 'pass:android',
         '--out', apk, aligned])
    run([java, '-jar', signer, 'verify', '--verbose', apk])
    result = {'apk': str(apk), 'bytes': apk.stat().st_size,
              'sha256': hashlib.file_digest(apk.open('rb'), 'sha256').hexdigest(),
              'package': 'cn.zhixing.vision', 'abi': 'arm64-v8a', 'model': PROFILE_DESC,
              'native_build_passed': True, 'signature_verified': True, 'physical_data_verified': False}
    (output_dir / REPORT_NAME).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
