"""Keep boxes between fresh low-load detections without republishing old results."""
from pathlib import Path
import json,hashlib
import build_lowload as low
base=low.base
base.BUILD=Path.home()/'.cache/zhixing-android-build-steady'
base.JAVA_SOURCE_DIR=base.BUILD/'java-input'
base.APK_NAME='zhixing-vision-steady.apk'
base.REPORT_NAME='build-steady-verification.json'
base.PROFILE_DESC='COCO YOLOv8n 256 CPU, 2 threads, 750ms detection interval, retained preview boxes'
previous_prepare=base.prepare_native

def prepare():
    source=previous_prepare()
    p=source/'yolov8ncnn.cpp';s=p.read_text(encoding='utf-8')
    a=s.index('            // Camera previews continue;')
    marker='            g_yolov8->draw(rgb, objects);'
    b=s.index(marker,a)+len(marker)
    s=s[:a]+'''            static double last_detection_started = -10000.0;
            static double cached_at = -10000.0;
            static int cached_width = 0, cached_height = 0;
            static std::vector<Object> cached_objects;
            const double now = ncnn::get_current_time();
            if (rgb.cols != cached_width || rgb.rows != cached_height) {
                cached_objects.clear();
                last_detection_started = -10000.0;
                cached_width = rgb.cols; cached_height = rgb.rows;
            }
            if (now - last_detection_started >= 750.0) {
                last_detection_started = now;
                std::vector<Object> objects;
                const double started = ncnn::get_current_time();
                const int detected = g_yolov8->detect(rgb, objects);
                const double inference_ms = ncnn::get_current_time() - started;
                if (detected == 0) {
                    cached_objects = objects; // A fresh empty result clears old boxes.
                    cached_at = ncnn::get_current_time();
                    zxr::publish(rgb, objects, inference_ms);
                } else {
                    cached_objects.clear(); cached_at = -10000.0;
                    __android_log_print(ANDROID_LOG_ERROR,"ZXR_VISION","detection_failed");
                }
            }
            // Draw on EVERY rendered preview, but publish only new detections.
            // These are the last measured boxes, not real-time tracking.
            if (ncnn::get_current_time() - cached_at <= 1500.0)
                g_yolov8->draw(rgb, cached_objects);
            else cached_objects.clear();'''+s[b:]
    p.write_text(s,encoding='utf-8')
    return source
base.prepare_native=prepare

if __name__=='__main__':
    base.main()
    p=base.WORKSPACE/'output/phone_vision'/base.REPORT_NAME
    d=json.loads(p.read_text(encoding='utf-8'));d['date']='2026-10-07'
    d['boxes']='Retained until next fresh detection, explicit empty/error clears, expiry1500ms; no tracking'
    d['freshness']='Only a new inference creates a new sequence/timestamp/log packet'
    d['native_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in (base.BUILD/'native').glob('*.cpp')}
    d['installed']='NOT_RUN';d['physical_box_visibility']='PENDING_USER_OBSERVATION'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
