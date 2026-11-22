"""Run pixel conversion and dynamic-library checks on phone; never opens USB."""
from pathlib import Path
import subprocess,shutil,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
OUT=ROOT/'output/onboard_dashboard/camera-compat-20261026'
work=Path.home()/'.cache/zhixing-uvc-compat-20261026'
src=work/'phone-check.cpp';shutil.copy2(HERE/'uvc_compat_phone_check.cpp',src)
ndk=Path.home()/'.cache/zhixing-android-tools/android-ndk-r29-windows/android-ndk-r29'
clang=ndk/'toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe'
includes=[work/'jni',work/'jni/libuvc/include',work/'jni/libusb/libusb']
subprocess.run([str(clang),'--target=aarch64-linux-android26','-std=c++17','-O2','-static-libstdc++','-DANDROID_NDK','-DLOG_NDEBUG',*['-I'+str(p) for p in includes],str(src),'-ldl','-llog','-o',str(work/'uvc-phone-check')],check=True)
shutil.copy2(work/'uvc-phone-check',OUT/'native/uvc-phone-check')
adb=ROOT/'tmp/android-tools/platform-tools/adb.exe';remote='/data/local/tmp/zhixing_uvc_compat_20261026'
def run(*args):return subprocess.run([str(adb),*args],capture_output=True,timeout=20,check=True)
if run('shell','getprop','ro.board.platform').stdout.decode().strip()!='mt6739':raise RuntimeError('Unexpected phone')
run('shell','mkdir','-p',remote)
run('push',str(work/'uvc-phone-check'),remote+'/uvc-phone-check')
for name in ['libUVCCamera.so','libuvc.so','libusb1.0.so','libjpeg-turbo212.so','libyuv.so']:
    local=OUT/'native'/name if name=='libUVCCamera.so' else ROOT/'tmp/uvc-android/aar/jni/arm64-v8a'/name
    run('push',str(local),remote+'/'+name)
run('shell','chmod','700',remote+'/uvc-phone-check')
p=subprocess.run([str(adb),'shell','env','LD_LIBRARY_PATH='+remote,remote+'/uvc-phone-check',remote],capture_output=True,timeout=20)
(OUT/'phone-pixel-check.stdout.log').write_bytes(p.stdout)
(OUT/'phone-pixel-check.stderr.log').write_bytes(p.stderr)
if p.returncode:
    print(p.stderr.decode(errors='replace')[-2000:]);raise RuntimeError('Phone pixel check failed: '+str(p.returncode))
result=json.loads(p.stdout)
assert result['uyvy_rgbx_nv21_checks']==18 and not result['usb_opened']
(OUT/'phone-pixel-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
