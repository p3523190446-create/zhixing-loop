package com.tencent.yolov8ncnn;
import android.content.res.AssetManager;
import android.view.Surface;

public class YOLOv8Ncnn {
    static { System.loadLibrary("yolov8ncnn"); }
    public native boolean loadModel(AssetManager assets, int task, int model, int compute);
    public native boolean openCamera(int facing);
    public native boolean closeCamera();
    public native boolean setOutputWindow(Surface surface);
    public native String getDetections();
}
