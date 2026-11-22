package cn.zhixing.dashboard;

/** A correlated negative control reply is not a broken USB connection. */
public final class BoardReplyException extends java.io.IOException {
  public BoardReplyException(String line){super("主控拒绝本次控制："+line);}
  public static boolean rejects(String command,String line){
    return line.startsWith("ERR,")&&(command.startsWith("LINE_TASK_")||command.equals("DRIVE_ARM")||command.startsWith("DRIVE_SET,")||command.startsWith("DRIVE_VECTOR,")||command.startsWith("DRIVE_BRAKE,"));
  }
}
