// Local Android benchmark. No camera, microphone, USB device or actuator access.
// Detector implementation: retained upstream BSD-3-Clause yolov8*.cpp/.h.
#include "yolov8.h"
#include <cpu.h>
#include <gpu.h>
#include <opencv2/imgproc.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

static double clock_ms(){return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();}
static double percentile(std::vector<double> values,double fraction){std::sort(values.begin(),values.end());return values[std::min(values.size()-1,(size_t)(values.size()*fraction))];}
class Detector:public YOLOv8_det_coco {
public:
    bool checked_load(const char* param,const char* weights,int threads){
        yolov8.opt=ncnn::Option();yolov8.opt.num_threads=threads;
        yolov8.opt.use_vulkan_compute=false;
        return yolov8.load_param(param)==0 && yolov8.load_model(weights)==0;
    }
};

int main(int argc,char**argv){
    if(argc!=2)return 2;
    std::string dir=argv[1];std::vector<unsigned char> pixels(320*256*3);
    std::ifstream input(dir+"/frame.rgb",std::ios::binary);
    if(!input.read((char*)pixels.data(),pixels.size()))return 3;
    cv::Mat image(256,320,CV_8UC3,pixels.data());
    std::vector<double> color_times;double check=0;
    cv::Mat hsv,mask,gray,small;
    for(int i=0;i<203;i++){
        double start=clock_ms();
        cv::cvtColor(image,hsv,cv::COLOR_RGB2HSV);
        cv::inRange(hsv,cv::Scalar(0,110,80),cv::Scalar(10,255,255),mask);
        cv::morphologyEx(mask,mask,cv::MORPH_OPEN,cv::Mat::ones(3,3,CV_8U));
        std::vector<std::vector<cv::Point>> contours;cv::findContours(mask,contours,cv::RETR_EXTERNAL,cv::CHAIN_APPROX_SIMPLE);
        cv::cvtColor(image,gray,cv::COLOR_RGB2GRAY);cv::resize(gray,small,cv::Size(160,128));
        check+=cv::sum(small)[0];double elapsed=clock_ms()-start;
        if(i>=3)color_times.push_back(elapsed);
    }
    printf("{\"mode\":\"ANDROID_OFFLINE_ALGORITHM_ONLY\",\"camera_capture_included\":false,\"actuator_access\":false,\"cpu_count\":%d,",ncnn::get_cpu_count());
    printf("\"color_pipeline\":{\"iterations\":200,\"median_ms\":%.3f,\"p95_ms\":%.3f,\"checksum\":%.0f},\"models\":[",percentile(color_times,.5),percentile(color_times,.95),check);
    bool first=true;
    for(int threads: {2,4}){
        Detector model;
        if(!model.checked_load((dir+"/yolov8n.ncnn.param").c_str(),(dir+"/yolov8n.ncnn.bin").c_str(),threads))return 4;
        for(int size:{160,224,320}){
            model.set_det_target_size(size);std::vector<double> times;std::vector<Object> objects;
            for(int iteration=0;iteration<15;iteration++){
                double start=clock_ms();int result=model.detect(image,objects);double elapsed=clock_ms()-start;
                if(result!=0)return 5;
                for(const Object&o:objects)if(!std::isfinite(o.prob)||o.label<0||o.label>=80)return 6;
                if(iteration>=3)times.push_back(elapsed);
            }
            if(!first)printf(",");first=false;
            printf("{\"target_size\":%d,\"threads\":%d,\"iterations\":12,\"median_ms\":%.3f,\"p95_ms\":%.3f,\"last_detections\":%zu}",size,threads,percentile(times,.5),percentile(times,.95),objects.size());fflush(stdout);
        }
    }
    printf("]}\n");return 0;
}
