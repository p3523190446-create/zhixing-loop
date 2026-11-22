"""Build only UVCAndroid 1.0.13's preview bridge; retain existing dependency SOs."""
from pathlib import Path
import hashlib,json,shutil,subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
COMMIT='6018c7f20238832929cf61427427bb7828056260'
source=ROOT/'tmp/uvc-compat-1.0.13'
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==COMMIT
cache=Path.home()/'.cache/zhixing-android-tools'
work=Path.home()/'.cache/zhixing-uvc-compat-20261026'
work.mkdir(parents=True,exist_ok=True)
jni=work/'jni'
shutil.copytree(source/'libuvccamera/src/main/jni',jni,dirs_exist_ok=True)
preview=jni/'UVCCamera/UVCPreview.cpp'
s=preview.read_text(encoding='utf-8')
old='uvc_yuyv2rgbx(frame_yuv, frame);   // YUYV => RGBX'
assert s.count(old)==1
s=s.replace(old,'uvc_any2rgbx(frame_yuv, frame);   // Dispatch YUYV / UYVY by actual frame format')
preview.write_text(s,encoding='utf-8')
libdir=work/'prebuilt'
shutil.copytree(ROOT/'tmp/uvc-android/aar/jni/arm64-v8a',libdir,dirs_exist_ok=True)
headers='$(LOCAL_PATH)/jni/libuvc/include $(LOCAL_PATH)/jni/libuvc/include/libuvc $(LOCAL_PATH)/jni/libusb/libusb $(LOCAL_PATH)/jni/libjpeg-turbo $(LOCAL_PATH)/jni/libyuv/include'
parts=['COMPAT_PATH := $(call my-dir)']
for module in ['usb1.0','uvc','jpeg-turbo212','yuv']:
    parts += ['LOCAL_PATH := $(COMPAT_PATH)','include $(CLEAR_VARS)',f'LOCAL_MODULE := {module}',
              f'LOCAL_SRC_FILES := prebuilt/lib{module}.so',f'LOCAL_EXPORT_C_INCLUDES := {headers}',
              'include $(PREBUILT_SHARED_LIBRARY)']
parts += ['include $(COMPAT_PATH)/jni/UVCCamera/Android.mk']
(work/'Android.mk').write_text('\n'.join(parts)+'\n',encoding='utf-8')
(work/'Application.mk').write_text('APP_ABI := arm64-v8a\nAPP_PLATFORM := android-26\nAPP_STL := c++_static\nAPP_OPTIM := release\nAPP_CFLAGS := -DLOG_NDEBUG\n',encoding='utf-8')
ndk=next(cache.glob('android-ndk-r29-windows/**/ndk-build.cmd'))
log=work/'build.log'
with log.open('w',encoding='utf-8') as stream:
    result=subprocess.run([str(ndk),'NDK_PROJECT_PATH=.', 'APP_BUILD_SCRIPT=Android.mk','NDK_APPLICATION_MK=Application.mk','-j4'],cwd=work,stdout=stream,stderr=subprocess.STDOUT)
if result.returncode:
    print(log.read_text(encoding='utf-8',errors='replace')[-10000:]);raise SystemExit(result.returncode)
out=ROOT/'output/onboard_dashboard/camera-compat-20261026/native'
out.mkdir(parents=True,exist_ok=True)
binary=work/'libs/arm64-v8a/libUVCCamera.so'
shutil.copy2(binary,out/binary.name)
report=dict(upstream=COMMIT,patch='uncompressed preview: uvc_yuyv2rgbx -> uvc_any2rgbx',
            abi='arm64-v8a',api=26,so=str(out/binary.name),sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
            original_dependencies='cached UVCAndroid 1.0.13 SOs; unchanged',device_validation='NOT_RUN',build_log=str(log))
(out/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
