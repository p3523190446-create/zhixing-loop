package cn.zhixing.dashboard;
import java.util.Map;
/** Explain the same stationary gate used at start and on every follow update. */
final class FollowInterlock {
 static String blocked(Map<String,String> rows,boolean connected,long age,boolean calibrating,boolean lineTask,boolean driveOwner){
  if(!connected)return "请先连接主控并开始记录。";
  if(age<0||age>=1500)return "主控回执已过期，等待新鲜数据。";
  if(calibrating)return "现场标定进行中，请先结束采样。";
  if(lineTask)return "请先停止自动循迹，再开启云台跟随。";
  if(driveOwner)return "请先点击四驱停止，释放手动行驶会话；仅松开摇杆还未释放。";
  String d=rows.get("DRIVE_STATUS"),a=rows.get("DRIVE_ACTUATORS");
  if(d==null||a==null)return "等待车轮状态回执。";
  String[] drive=d.split(",",-1),act=a.split(",",-1);
  if(drive.length!=10||act.length!=11||!drive[0].equals("DRIVE")||!act[0].equals("ACTUATORS"))return "车轮状态格式不符，不能开启跟随。";
  if(!act[10].equals("0"))return "车轮控制器有故障，请先处理或停止行驶。";
  if(!drive[2].equals("0")||!drive[3].equals("0"))return "主控仍处于行驶会话或车轮运动中，请先停止。";
  for(int n=2;n<=9;n++)if(!act[n].equals("0"))return "车轮指令尚未归零，等待停止回执。";
  return null;
 }
}
