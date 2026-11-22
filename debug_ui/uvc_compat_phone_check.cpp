// Offline pixels only: no USB device enumeration/open, camera, board or socket calls.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <initializer_list>
#include "libuvc/libuvc.h"

int main(int argc,char**argv){
  if(argc!=2)return 2;
  char path[1024];snprintf(path,sizeof(path),"%s/libuvc.so",argv[1]);
  void*uvc=dlopen(path,RTLD_NOW|RTLD_GLOBAL);if(!uvc){fprintf(stderr,"libuvc: %s\n",dlerror());return 3;}
  snprintf(path,sizeof(path),"%s/libUVCCamera.so",argv[1]);
  void*bridge=dlopen(path,RTLD_NOW|RTLD_GLOBAL);if(!bridge){fprintf(stderr,"bridge: %s\n",dlerror());return 4;}
  auto allocate=(uvc_frame_t*(*)(size_t))dlsym(uvc,"uvc_allocate_frame");
  auto release=(void(*)(uvc_frame_t*))dlsym(uvc,"uvc_free_frame");
  using Convert=int(*)(uvc_frame_t*,uvc_frame_t*);
  Convert any=(Convert)dlsym(uvc,"uvc_any2rgbx"),legacy=(Convert)dlsym(uvc,"uvc_yuyv2rgbx");
  Convert nv21=(Convert)dlsym(bridge,"_Z16uvc_rgbx_to_nv21P9uvc_frameS0_");
  if(!allocate||!release||!any||!legacy||!nv21)return 5;
  const unsigned char bars[][4]={{128,16,128,235},{90,81,240,81},{54,145,34,145},{240,41,110,41}};
  int checks=0;
  for(int width:{16,640,1920}){
    const int height=2;size_t pixels=(size_t)width*height;
    uvc_frame_t*u=allocate(pixels*2),*y=allocate(pixels*2),*ur=allocate(pixels*4),*yr=allocate(pixels*4),*un=allocate(pixels*3/2),*yn=allocate(pixels*3/2);
    if(!u||!y||!ur||!yr||!un||!yn)return 6;
    u->width=y->width=width;u->height=y->height=height;u->step=y->step=width*2;
    u->frame_format=UVC_FRAME_FORMAT_UYVY;y->frame_format=UVC_FRAME_FORMAT_YUYV;
    auto up=(unsigned char*)u->data,yp=(unsigned char*)y->data;
    for(size_t n=0;n<pixels/2;n++){
      const auto*b=bars[n%4];memcpy(up+n*4,b,4);
      yp[n*4]=b[1];yp[n*4+1]=b[0];yp[n*4+2]=b[3];yp[n*4+3]=b[2];
    }
    if(legacy(u,ur)!=UVC_ERROR_INVALID_PARAM)return 7;checks++;
    if(any(u,ur)||legacy(y,yr))return 8;checks++;
    if(ur->data_bytes!=pixels*4||yr->data_bytes!=pixels*4||memcmp(ur->data,yr->data,pixels*4))return 9;checks++;
    const auto*rgb=(unsigned char*)ur->data;
    if(rgb[0]!=rgb[1]||rgb[1]!=rgb[2]||rgb[3]!=255||rgb[4]<=rgb[0]||rgb[4]!=rgb[5]||rgb[5]!=rgb[6]||rgb[7]!=255)return 10;checks++;
    if(nv21(ur,un)||nv21(yr,yn))return 11;checks++;
    if(un->data_bytes!=pixels*3/2||yn->data_bytes!=pixels*3/2||memcmp(un->data,yn->data,pixels*3/2))return 12;checks++;
    release(u);release(y);release(ur);release(yr);release(un);release(yn);
  }
  printf("{\"scope\":\"PHONE_OFFLINE_PIXEL_COMPATIBILITY_ONLY\",\"bridge_load\":true,\"uyvy_rgbx_nv21_checks\":%d,\"original_yuyv_parity\":true,\"usb_opened\":false,\"live_camera_test\":false,\"actuator_commands\":false}\n",checks);
  return 0;
}
