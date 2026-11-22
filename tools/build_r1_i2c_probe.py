"""Compile the separate sensor-ID experiment; no hardware is flashed."""
import build_r1_bringup as build

build.STEM = 'r1_i2c_probe'
build.WORK = build.TOOLS / 'r1-i2c-probe'
build.OUT = build.PROJECT / '知行回路软件/build/r1_i2c_probe'
build.MAIN_SOURCE = build.PROJECT / '知行回路软件/board/r1_i2c_probe/main.c'

if __name__ == '__main__':
    build.main()
