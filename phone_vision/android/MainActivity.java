package com.tencent.yolov8ncnn;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.graphics.PixelFormat;
import android.os.Bundle;
import android.os.Handler;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;

public class MainActivity extends Activity implements SurfaceHolder.Callback {
    private final YOLOv8Ncnn model = new YOLOv8Ncnn();
    private final Handler handler = new Handler();
    private TextView status;
    private int facing = 0;
    private boolean ready = false;
    private boolean resumed = false;
    private final Runnable update = new Runnable() {
        public void run() {
            if (!resumed) return;
            String message = model.getDetections();
            if (ready && message != null && !message.isEmpty()) {
                try {
                    JSONObject frame = new JSONObject(message);
                    JSONArray objects = frame.getJSONArray("objects");
                    status.setText("CPU · n-320 | 检测 " + objects.length() + " 个有效目标\n"
                        + "帧 " + frame.getLong("seq") + " · 单次识别 "
                        + Math.round(frame.getDouble("infer_ms")) + " ms · 识别数据已生成");
                } catch (Exception ignored) { status.setText("检测数据格式异常"); }
            }
            handler.postDelayed(this, 500);
        }
    };

    public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        status = new TextView(this);
        status.setTextSize(14);
        status.setPadding(12, 8, 12, 8);
        status.setText("知行回路视觉 · 正在加载最小模型");
        layout.addView(status);
        Button switchCamera = new Button(this);
        switchCamera.setText("切换前后摄像头");
        switchCamera.setOnClickListener(new View.OnClickListener() {
            public void onClick(View view) {
                model.closeCamera(); facing = 1 - facing; openCamera();
            }
        });
        layout.addView(switchCamera);
        SurfaceView camera = new SurfaceView(this);
        camera.getHolder().setFormat(PixelFormat.RGBA_8888);
        camera.getHolder().addCallback(this);
        layout.addView(camera, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(layout);
        ready = model.loadModel(getAssets(), 0, 0, 0);
        if (!ready) status.setText("模型加载失败，请退出并反馈");
    }

    private void openCamera() {
        if (!ready || !resumed) return;
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, 10);
            return;
        }
        if (!model.openCamera(facing)) status.setText("摄像头打开失败，请反馈");
    }
    public void onResume() {
        super.onResume(); resumed = true; openCamera(); handler.post(update);
    }
    public void onPause() {
        resumed = false; handler.removeCallbacks(update); model.closeCamera(); super.onPause();
    }
    public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        if (code == 10 && results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) openCamera();
        else if (code == 10) status.setText("需要允许摄像头权限才能测试");
    }
    public void surfaceCreated(SurfaceHolder holder) {}
    public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {
        model.setOutputWindow(holder.getSurface());
    }
    public void surfaceDestroyed(SurfaceHolder holder) {}
}
