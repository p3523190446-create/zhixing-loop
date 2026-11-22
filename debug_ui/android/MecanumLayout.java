package cn.zhixing.dashboard;

/** Pair the exact firmware identity with its output profile; never mix them. */
final class MecanumLayout {
  static boolean matches(String identity,String chassis){
    if("DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107,1".equals(identity))
      return "DRIVE_CHASSIS,MECANUM_X,FL_RL_FR_RR,250,600".equals(chassis);
    if("DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_MECANUM_V3_20261107,1".equals(identity))
      return "DRIVE_CHASSIS,MECANUM_GROUND_MAP,SWAP_M2_M4,250,600".equals(chassis);
    return false;
  }
}
