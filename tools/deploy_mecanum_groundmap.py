"""Reuse the single-owner deployment, preserving calibration and phone settings."""
import deploy_mecanum_integrated as deploy

deploy.OUT = deploy.ROOT / 'output/onboard_dashboard/mecanum-groundmap-20261107'
deploy.FLASHER = deploy.SW / 'tools/flash_r1_mecanum_groundmap.py'
deploy.PHONE_VERSION = '0.26.3'
deploy.EXPECTED_FIRMWARE = 'R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107'
deploy.TARGET_FIRMWARE = 'R1_DRIVE_STARTUP_MANUAL_MECANUM_V3_20261107'

if __name__ == '__main__':
    deploy.main()
