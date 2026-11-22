#include "vision_export.h"
#include <android/log.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <locale>
#include <mutex>
#include <sstream>
#include <string>

namespace zxr {
static std::mutex result_lock;
static std::string result_json;
static unsigned long long sequence = 0;

void publish(const cv::Mat& image, const std::vector<Object>& objects, double inference_ms) {
    if (image.cols <= 0 || image.rows <= 0) return;
    const auto now = std::chrono::steady_clock::now().time_since_epoch();
    const auto time_ms = std::chrono::duration_cast<std::chrono::milliseconds>(now).count();
    std::ostringstream out;
    out.imbue(std::locale::classic());
    out << std::fixed << std::setprecision(4)
        << "{\"v\":1,\"seq\":" << ++sequence
        << ",\"phone_ms\":" << time_ms
        << ",\"infer_ms\":" << inference_ms
        << ",\"width\":" << image.cols << ",\"height\":" << image.rows
        << ",\"task\":\"coco\",\"objects\":[";
    size_t sent = 0, eligible = 0;
    for (const auto& object : objects) {
        if (object.label < 0 || object.label >= 80 || !std::isfinite(object.prob)
            || object.prob < 0.35f || object.prob > 1.f
            || !std::isfinite(object.rect.x) || !std::isfinite(object.rect.y)
            || !std::isfinite(object.rect.width) || !std::isfinite(object.rect.height)) continue;
        float x1 = std::clamp(object.rect.x, 0.f, float(image.cols));
        float y1 = std::clamp(object.rect.y, 0.f, float(image.rows));
        float x2 = std::clamp(object.rect.x + object.rect.width, 0.f, float(image.cols));
        float y2 = std::clamp(object.rect.y + object.rect.height, 0.f, float(image.rows));
        if (x2 <= x1 || y2 <= y1) continue;
        ++eligible;
        if (sent == 8) continue;
        if (sent++) out << ',';
        out << "{\"cls\":" << object.label << ",\"score\":" << object.prob
            << ",\"cx\":" << (x1+x2)/(2*image.cols)
            << ",\"cy\":" << (y1+y2)/(2*image.rows)
            << ",\"w\":" << (x2-x1)/image.cols
            << ",\"h\":" << (y2-y1)/image.rows << '}';
    }
    out << "],\"truncated\":" << (eligible > sent ? "true" : "false") << '}';
    const std::string message = out.str();
    {
        std::lock_guard<std::mutex> guard(result_lock);
        result_json = message;
    }
    __android_log_write(ANDROID_LOG_INFO, "ZXR_VISION", message.c_str());
}

std::string latest() {
    std::lock_guard<std::mutex> guard(result_lock);
    return result_json;
}
}
