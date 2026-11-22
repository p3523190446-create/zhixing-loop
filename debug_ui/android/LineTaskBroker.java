package cn.zhixing.dashboard;

import android.os.SystemClock;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** One task owner and explicit expiring heartbeat, sharing the existing USB worker. */
public final class LineTaskBroker {
  private static final class Job {
    String action;
    JSONObject body, result;
    long deadline;
    final CountDownLatch done = new CountDownLatch(1);
    Exception error;
  }
  private final ArrayBlockingQueue<Job> queue = new ArrayBlockingQueue<>(4);
  private final ConcurrentLinkedQueue<Job> stops = new ConcurrentLinkedQueue<>();
  private String owner;
  private long touched, armedAt;
  private boolean mcuActive;
  private int state, reason, junctions;
  private static int number(JSONObject body, String key, int lo, int hi) {
    Object n = body.opt(key);
    if (!(n instanceof Integer || n instanceof Long) || ((Number) n).longValue() < lo
        || ((Number) n).longValue() > hi)
      throw new IllegalArgumentException("巡线参数无效：" + key);
    return ((Number) n).intValue();
  }
  public synchronized boolean active() {
    return owner != null || mcuActive;
  }
  public synchronized JSONObject publicState() throws JSONException {
    return new JSONObject()
        .put("active", owner != null)
        .put("mcu_active", mcuActive)
        .put("state", state)
        .put("reason", reason)
        .put("junctions", junctions);
  }
  private static long[] status(ControlBroker.Exchange link) throws Exception {
    String[] p = link.call("LINE_TASK_STATUS", "LINE_TASK_STATUS,").split(",", -1);
    if (p.length != 11 || !p[0].equals("LINE_TASK_STATUS"))
      throw new java.io.IOException("巡线状态格式不符");
    long[] v = new long[10];
    for (int i = 0; i < 10; i++) v[i] = Long.parseLong(p[i + 1]);
    if (v[1] < 0 || v[1] > 5 || v[2] < 0 || v[2] > 10)
      throw new java.io.IOException("巡线状态范围不符");
    return v;
  }
  public synchronized void observe(String text) throws Exception {
    if (text == null)
      return;
    String[] p = text.split(",", -1);
    if (p.length != 11)
      throw new java.io.IOException("巡线回传长度不符");
    long ms = Long.parseLong(p[1]);
    state = Integer.parseInt(p[2]);
    reason = Integer.parseInt(p[3]);
    junctions = Integer.parseInt(p[4]);
    mcuActive = state >= 1 && state <= 3;
    if (owner != null && ms >= armedAt && !mcuActive)
      owner = null;
  }
  private static void exact(ControlBroker.Exchange link, String command, String expected)
      throws Exception {
    if (!link.call(command, expected).equals(expected))
      throw new java.io.IOException("巡线回执不符");
  }
  public JSONObject submit(String action, JSONObject body) throws Exception {
    if (!Arrays.asList("start", "heartbeat", "stop").contains(action))
      throw new IllegalArgumentException("没有这个巡线操作");
    if (action.equals("start")) {
      int branch=number(body, "branch", 0, 4);
      number(body, "speed", 40, 100);
      int duration=number(body, "duration_ms", 0, 10000);
      if(duration==0&&branch!=4||duration>0&&duration<1000)throw new IllegalArgumentException("持续运行仅用于环线模式");
      int side = number(body, "x1_left", -1, 1);
      if (side == 0)
        throw new IllegalArgumentException("先确认X1所在车侧");
    }
    Job job = new Job();
    job.action = action;
    job.body = body;
    job.deadline = SystemClock.elapsedRealtime() + 450;
    if (action.equals("stop")) {
      if (stops.size() >= 3)
        throw new IllegalStateException("巡线停止正在处理");
      stops.offer(job);
    } else if (!queue.offer(job))
      throw new IllegalStateException("巡线请求队列忙");
    if (!job.done.await(1800, TimeUnit.MILLISECONDS))
      throw new java.io.IOException("巡线回执超时，需重新开启");
    if (job.error != null)
      throw job.error;
    return job.result;
  }
  private void complete(Job job, JSONObject result, Exception error) {
    job.result = result;
    job.error = error;
    job.done.countDown();
  }
  private void cancelQueued() throws JSONException {
    Job job;
    while ((job = queue.poll()) != null)
      complete(job, null, new IllegalStateException("停止已撤销较旧巡线请求"));
  }
  private void stop(ControlBroker.Exchange link) throws Exception {
    owner = null;
    exact(link, "LINE_TASK_STOP", "LINE_TASK_STOPPED");
    long[] v = status(link);
    state = (int) v[1];
    reason = (int) v[2];
    junctions = (int) v[3];
    mcuActive = state >= 1 && state <= 3;
    if (mcuActive || v[4] != 0 || v[5] != 0)
      throw new java.io.IOException("主控未确认巡线零请求");
  }
  public synchronized void pump(ControlBroker.Exchange link) throws Exception {
    Job job = stops.poll();
    if (job != null) {
      try {
        cancelQueued();
        stop(link);
        complete(job, new JSONObject().put("ok", true).put("stopped", true), null);
      } catch (Exception e) {
        complete(job, null, e);
        disconnect();
        throw e;
      }
      return;
    }
    if (owner != null && SystemClock.elapsedRealtime() - touched >= 450) {
      stop(link);
      cancelQueued();
    }
    job = queue.poll();
    if (job == null)
      return;
    boolean issued = false;
    try {
      if (SystemClock.elapsedRealtime() > job.deadline)
        throw new IllegalStateException("巡线请求已过期，未执行");
      if (job.action.equals("start")) {
        if (active())
          throw new IllegalStateException("已有巡线任务正在运行");
        exact(link,
            "LINE_TASK_CONFIG," + number(job.body, "x1_left", -1, 1) + ","
                + number(job.body, "branch", 0, 4) + "," + number(job.body, "speed", 40, 100) + ","
                + number(job.body, "duration_ms", 0, 10000),
            "LINE_TASK_CONFIGURED");
        if (SystemClock.elapsedRealtime() > job.deadline)
          throw new IllegalStateException("巡线配置超时，未启动");
        issued = true;
        exact(link, "LINE_TASK_START", "LINE_TASK_STARTED");
        long[] v = status(link);
        if (v[1] < 1 || v[1] > 3)
          throw new java.io.IOException("主控未确认巡线开启");
        owner = UUID.randomUUID().toString();
        armedAt = v[0];
        state = (int) v[1];
        reason = (int) v[2];
        junctions = (int) v[3];
        mcuActive = true;
        touched = SystemClock.elapsedRealtime();
        complete(job, new JSONObject().put("ok", true).put("session", owner), null);
      } else {
        if (owner == null || !owner.equals(job.body.optString("session")))
          throw new IllegalStateException("巡线会话已撤销");
        issued = true;
        exact(link, "LINE_TASK_KEEPALIVE", "LINE_TASK_ALIVE");
        touched = SystemClock.elapsedRealtime();
        complete(job, new JSONObject().put("ok", true), null);
      }
    } catch (Exception error) {
      if (issued) {
        try {
          stop(link);
        } catch (Exception stopError) {
          complete(job, null, error);
          disconnect();
          throw stopError;
        }
      }
      complete(job, null, error);
    }
  }
  public synchronized void disconnect() {
    owner = null;
    mcuActive = false;
    armedAt = 0;
    state = reason = junctions = 0;
    Job job;
    while ((job = queue.poll()) != null)
      complete(job, null, new IllegalStateException("巡线链路已关闭"));
    while ((job = stops.poll()) != null)
      complete(job, null, new IllegalStateException("巡线链路已关闭"));
  }
}
