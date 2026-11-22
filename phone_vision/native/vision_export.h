#pragma once
#include "yolov8.h"
#include <string>

namespace zxr {
void publish(const cv::Mat& image, const std::vector<Object>& objects, double inference_ms);
std::string latest();
}
