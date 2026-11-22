from pathlib import Path
import shutil
import build_r1_bringup as build
build.STEM='r1_ranging_corrected'
build.WORK=build.TOOLS/'r1-ranging-corrected'
build.OUT=build.PROJECT/'知行回路软件/build/r1_ranging_corrected'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_ranging_corrected/main.c'
build.EXTRA_INCLUDE_DIRS=['User','ST_API']
build.EXTRA_FLAGS=['-DUSE_I2C_2V8']
build.EXTRA_SOURCES=[Path('User/vl53l0x_platform.c')]+[Path('ST_API')/n for n in ['vl53l0x_api.c','vl53l0x_api_core.c','vl53l0x_api_calibration.c','vl53l0x_api_ranging.c','vl53l0x_api_strings.c']]
def prepare():
    shutil.copytree(build.PROJECT/'知行回路软件/third_party/st_vl53l0x',build.WORK/'ST_API',dirs_exist_ok=True)
    base=build.PROJECT/'知行回路软件/board/r1_ranging'
    for name in ['vl53l0x_platform.h','vl53l0x_platform.c']:
        shutil.copy2(base/name,build.WORK/'User'/name)
build.PREPARE=prepare
if __name__=='__main__':build.main()
