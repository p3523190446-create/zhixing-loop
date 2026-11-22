"""Build an isolated low-load trial; preserve the n320 APK for rollback.

No installation or claim that a system freeze is fixed is made by this script.
"""
from pathlib import Path
import hashlib,json,shutil
import build as base

base.BUILD=Path.home()/'.cache/zhixing-android-build-lowload'
base.APK_NAME='zhixing-vision-lowload.apk'
base.REPORT_NAME='build-lowload-verification.json'
base.PROFILE_DESC='COCO YOLOv8n 256 CPU, 2 threads, inference interval >=750ms'
base.JAVA_SOURCE_DIR=base.BUILD/'java-input'
original_prepare=base.prepare_native

def prepare():
    source=original_prepare()
    p=source/'yolov8ncnn.cpp';s=p.read_text(encoding='utf-8')
    s=s.replace('#include "vision_export.h"','#include "vision_export.h"\n#include <chrono>')
    s=s.replace('int target_size = 320;','int target_size = 256;')
    old='''            std::vector<Object> objects;
            const double started = ncnn::get_current_time();'''
    new='''            // Camera previews continue; no sleeping while holding its mutex.
            // Results are published only after a NEW inference, never refreshed
            // from cached detections. Freshness timeout still means something.
            static double last_detection_started = -10000.0;
            const double now = ncnn::get_current_time();
            if (now - last_detection_started < 750.0) return;
            last_detection_started = now;
            std::vector<Object> objects;
            const double started = ncnn::get_current_time();'''
    assert s.count(old)==1;s=s.replace(old,new)
    # An early return skips only detection/draw for that frame; NdkCameraWindow
    # still copies RGB to the output surface after this callback returns.
    p.write_text(s,encoding='utf-8')
    p=source/'yolov8_det.cpp';s=p.read_text(encoding='utf-8')
    old='''    ex.input("in0", in_pad);

    ncnn::Mat out;
    ex.extract("out0", out);'''
    new='''    if (ex.input("in0", in_pad) != 0) return -1;
    ncnn::Mat out;
    if (ex.extract("out0", out) != 0 || out.empty()) return -1;
    // This pinned COCO head has 64 regression bins and 80 classes.
    // Do not index an incompatible/failed dynamic-shape tensor.
    const int expected_rows = (in_pad.w/8)*(in_pad.h/8)
        + (in_pad.w/16)*(in_pad.h/16) + (in_pad.w/32)*(in_pad.h/32);
    if (out.dims != 2 || out.w != 144 || out.h != expected_rows) return -1;'''
    assert s.count(old)==1;s=s.replace(old,new)
    p.write_text(s,encoding='utf-8')
    p=source/'yolov8.cpp';s=p.read_text(encoding='utf-8')
    old='    yolov8.opt = ncnn::Option();'
    assert s.count(old)==2
    s=s.replace(old,old+'''\n    yolov8.opt.num_threads = 2;
    yolov8.opt.openmp_blocktime = 0;
    cv::setNumThreads(1);''')
    # The upstream load routine ignored errors. Never enter detection after a
    # failed model load, even in this experimental profile.
    s=s.replace('    yolov8.load_param(parampath);\n    yolov8.load_model(modelpath);',
                '    if (yolov8.load_param(parampath) != 0) return -1;\n    if (yolov8.load_model(modelpath) != 0) return -1;')
    s=s.replace('    yolov8.load_param(mgr, parampath);\n    yolov8.load_model(mgr, modelpath);',
                '    if (yolov8.load_param(mgr, parampath) != 0) return -1;\n    if (yolov8.load_model(mgr, modelpath) != 0) return -1;')
    p.write_text(s,encoding='utf-8')
    p=source/'ndkcamera.cpp';s=p.read_text(encoding='utf-8')
    s=s.replace('#include <string>','#include <string>\n#include <chrono>')
    marker='    int32_t format;'
    gate='''    // Drop extra acquired frames promptly instead of converting/rendering
    // all 30 camera frames each second on this small phone.
    using Clock = std::chrono::steady_clock;
    static auto previous_preview = Clock::time_point::min();
    const auto preview_now = Clock::now();
    if (previous_preview != Clock::time_point::min() &&
        std::chrono::duration_cast<std::chrono::milliseconds>(preview_now-previous_preview).count() < 125) {
        AImage_delete(image);
        return;
    }
    previous_preview = preview_now;

'''
    assert s.count(marker)==1;s=s.replace(marker,gate+marker)
    # Always make the existing owned NV21 copy. Return the camera image before
    # inference so that its native buffer is not held for a whole model run.
    a=s.index('    if (u_data == v_data + 1')
    b=s.index('        // construct nv21',a)
    s=s[:a]+'    {\n'+s[b:]
    old='''        ((NdkCamera*)context)->on_image((unsigned char*)nv21, (int)width, (int)height);

        delete[] nv21;
    }

    AImage_delete(image);'''
    new='''        AImage_delete(image);
        image = 0;
        ((NdkCamera*)context)->on_image((unsigned char*)nv21, (int)width, (int)height);
        delete[] nv21;
    }'''
    assert s.count(old)==1;s=s.replace(old,new)
    p.write_text(s,encoding='utf-8')
    base.JAVA_SOURCE_DIR.mkdir(parents=True,exist_ok=True)
    for original in (base.HERE/'android').glob('*.java'):
        s=original.read_text(encoding='utf-8')
        if original.name=='MainActivity.java':
            s=s.replace('CPU · n-320 | 检测','低负载 · n-256 | 检测')
        (base.JAVA_SOURCE_DIR/original.name).write_text(s,encoding='utf-8')
    return source

base.prepare_native=prepare
if __name__=='__main__':
    base.main()
    p=base.WORKSPACE/'output/phone_vision'/base.REPORT_NAME
    d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-07'
    d['changes']=['256 input','2 ncnn threads','OpenMP blocktime 0','1 OpenCV thread',
                  'at most 8 converted preview frames/sec','>=750ms between new inference starts',
                  'release acquired camera image before inference','check model-load errors',
                  'validate inference result and dynamic tensor shape']
    d['root_cause']='UNCONFIRMED'
    d['installed']='NOT_RUN';d['sustained_stability']='NOT_RUN'
    d['native_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest()
                            for x in (base.BUILD/'native').glob('*.cpp')}
    d['references']=['https://github.com/Tencent/ncnn/wiki/faq']
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
