from pathlib import Path
import shutil
import build_r1_bringup as build
build.STEM='r1_distance_guard'
build.WORK=build.TOOLS/'r1-distance-guard'
build.OUT=build.PROJECT/'知行回路软件/build/r1_distance_guard'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_distance_guard/main.c'
build.EXTRA_INCLUDE_DIRS=['User','ST_API','GuardCore']
build.EXTRA_FLAGS=['-DUSE_I2C_2V8']
build.EXTRA_SOURCES=[Path('User/vl53l0x_platform.c')]+[Path('ST_API')/n for n in ['vl53l0x_api.c','vl53l0x_api_core.c','vl53l0x_api_calibration.c','vl53l0x_api_ranging.c','vl53l0x_api_strings.c']]
build.EXTRA_SOURCES += [Path('SRC/Peripheral/src/ch32v30x_tim.c'),Path('GuardCore/app.c'),Path('GuardCore/guard.c')]

def prepare():
    core=build.WORK/'GuardCore'
    core.mkdir(exist_ok=True)
    for name in ['app.h','guard.h']:
        shutil.copy2(build.PROJECT/'知行回路软件/include'/name,core/name)
    for name in ['app.c','guard.c']:
        shutil.copy2(build.PROJECT/'知行回路软件/src'/name,core/name)
    shutil.copytree(build.PROJECT/'知行回路软件/third_party/st_vl53l0x',build.WORK/'ST_API',dirs_exist_ok=True)
    base=build.PROJECT/'知行回路软件/board/r1_ranging'
    for name in ['vl53l0x_platform.h','vl53l0x_platform.c']:
        shutil.copy2(base/name,build.WORK/'User'/name)
build.PREPARE=prepare
if __name__=='__main__':build.main()
