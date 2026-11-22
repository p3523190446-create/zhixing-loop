"""Build a standalone Android benchmark using already-pinned local toolchains."""
import bootstrap
from pathlib import Path
import hashlib,importlib.util,json,shutil,subprocess,zipfile
import cv2 as cv
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=bootstrap.ROOT
OUT=ROOT/'output/onboard_dashboard/phone-first-20261025'
WORK=Path.home()/'.cache/zhixing-local-bench-20261025'

def main():
    WORK.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('existing_android_build',HERE.parent/'phone_vision/build.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    src=WORK/'src';src.mkdir(exist_ok=True)
    for name in ['yolov8.cpp','yolov8_det.cpp','yolov8.h']:
        shutil.copy2(HERE.parent/'phone_vision/upstream'/name,src/name)
    shutil.copy2(HERE/'phone_bench.cpp',src/'phone_bench.cpp')
    (src/'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.10)
project(zx_local_bench LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(OpenCV REQUIRED core imgproc)
find_package(ncnn REQUIRED)
add_executable(zx_local_bench phone_bench.cpp yolov8.cpp yolov8_det.cpp)
target_link_libraries(zx_local_bench ncnn ${OpenCV_LIBS} android log)
''',encoding='utf-8')
    ndk=helper.unique('android-ndk-r29-windows/android-ndk-r29')
    cmake=helper.unique('cmake-3.31.5-windows/**/bin/cmake.exe')
    ninja=helper.unique('cmake-3.31.5-windows/**/bin/ninja.exe')
    ncnn=helper.unique('ncnn-20260526-android-vulkan/**/arm64-v8a/lib/cmake/ncnn/ncnnConfig.cmake')
    opencv=helper.unique('opencv-mobile-4.13.0-android/**/sdk/native/jni/OpenCVConfig.cmake')
    helper.run([cmake,'-S',src,'-B',WORK/'build','-G','Ninja','-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_MAKE_PROGRAM='+str(ninja),'-DCMAKE_TOOLCHAIN_FILE='+str(ndk/'build/cmake/android.toolchain.cmake'),
        '-DANDROID_ABI=arm64-v8a','-DANDROID_PLATFORM=android-24','-DANDROID_STL=c++_static',
        '-Dncnn_DIR='+str(ncnn.parent),'-DOpenCV_DIR='+str(opencv.parent)])
    helper.run([cmake,'--build',WORK/'build','--parallel','4'])
    shutil.copy2(WORK/'build/zx_local_bench',OUT/'zx_local_bench')
    release=ROOT/'tmp/android-tools/ncnn-android-yolov8-20260527.f1ac75e.apk'
    if hashlib.sha256(release.read_bytes()).hexdigest()!='dfaa20c931918a6281bedcef9292d68895537d1046774fa0c6f4fc32d3bb3be8':
        raise ValueError('Pinned model APK fingerprint changed')
    with zipfile.ZipFile(release) as archive:
        for name in ['yolov8n.ncnn.param','yolov8n.ncnn.bin']:(OUT/name).write_bytes(archive.read('assets/'+name))
    frames=sorted((ROOT/'output/onboard_dashboard/algorithms-20261025').glob('run-*/frame-*.jpg'))
    if not frames:raise ValueError('No archived real camera input')
    raw=frames[-1].read_bytes();image=cv.imdecode(np.frombuffer(raw,np.uint8),cv.IMREAD_COLOR)
    image=cv.cvtColor(cv.resize(image,(320,256)),cv.COLOR_BGR2RGB)
    (OUT/'frame.rgb').write_bytes(image.tobytes())
    metadata=dict(mode='OFFLINE_PHONE_BENCHMARK_NOT_LIVE_CAPTURE',input=str(frames[-1]),
        input_sha256=hashlib.sha256(raw).hexdigest(),source_apk_sha256=hashlib.sha256(release.read_bytes()).hexdigest(),
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file()})
    (OUT/'build.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(OUT),'build':'PASS'}))

if __name__=='__main__':main()
