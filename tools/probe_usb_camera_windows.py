"""Read Windows hub connection/descriptors; no resets, driver changes or video opens.

API layout: Microsoft win32metadata shared/usbiodef.h and usbioctl.h;
enumeration pattern: microsoft/Windows-driver-samples usb/usbview/enum.c.
"""
import argparse,ctypes as c,json,struct,uuid
from ctypes import wintypes as w
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TARGETS={(0x04b4,0x00c3),(0x145f,0x02ec)}
kernel=c.WinDLL('kernel32',use_last_error=True)
setup=c.WinDLL('setupapi',use_last_error=True)
class GUID(c.Structure):_fields_=[('data',c.c_ubyte*16)]
class Interface(c.Structure):_fields_=[('size',w.DWORD),('guid',GUID),('flags',w.DWORD),('reserved',c.c_size_t)]
setup.SetupDiGetClassDevsW.argtypes=[c.POINTER(GUID),w.LPCWSTR,w.HWND,w.DWORD];setup.SetupDiGetClassDevsW.restype=w.HANDLE
setup.SetupDiEnumDeviceInterfaces.argtypes=[w.HANDLE,c.c_void_p,c.POINTER(GUID),w.DWORD,c.POINTER(Interface)];setup.SetupDiEnumDeviceInterfaces.restype=w.BOOL
setup.SetupDiGetDeviceInterfaceDetailW.argtypes=[w.HANDLE,c.POINTER(Interface),c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p];setup.SetupDiGetDeviceInterfaceDetailW.restype=w.BOOL
setup.SetupDiDestroyDeviceInfoList.argtypes=[w.HANDLE]
kernel.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE];kernel.CreateFileW.restype=w.HANDLE
kernel.DeviceIoControl.argtypes=[w.HANDLE,w.DWORD,c.c_void_p,w.DWORD,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p];kernel.DeviceIoControl.restype=w.BOOL
kernel.CloseHandle.argtypes=[w.HANDLE]
INVALID=c.c_void_p(-1).value

def hubs():
    guid=GUID((c.c_ubyte*16).from_buffer_copy(uuid.UUID('f18a0e88-c30c-11d0-8815-00a0c906bed8').bytes_le))
    devices=setup.SetupDiGetClassDevsW(c.byref(guid),None,None,0x12)
    if devices==INVALID:raise c.WinError(c.get_last_error())
    try:
        for n in range(128):
            item=Interface();item.size=c.sizeof(item)
            if not setup.SetupDiEnumDeviceInterfaces(devices,None,c.byref(guid),n,c.byref(item)):
                if c.get_last_error()==259:break
                raise c.WinError(c.get_last_error())
            needed=w.DWORD();setup.SetupDiGetDeviceInterfaceDetailW(devices,c.byref(item),None,0,c.byref(needed),None)
            data=c.create_string_buffer(needed.value);struct.pack_into('<I',data,0,8 if c.sizeof(c.c_void_p)==8 else 6)
            if not setup.SetupDiGetDeviceInterfaceDetailW(devices,c.byref(item),data,len(data),None,None):raise c.WinError(c.get_last_error())
            yield c.wstring_at(c.addressof(data)+4)
    finally:setup.SetupDiDestroyDeviceInfoList(devices)

def ioctl(handle,function,initial,size):
    data=c.create_string_buffer(size);c.memmove(data,initial,len(initial));returned=w.DWORD()
    if not kernel.DeviceIoControl(handle,(0x22<<16)|(function<<2),data,size,data,size,c.byref(returned),None):raise c.WinError(c.get_last_error())
    return data.raw[:returned.value]

def descriptor(handle,port,kind,length):
    initial=struct.pack('<IBBHHH',port,0x80,6,kind<<8,0,length)
    result=ioctl(handle,260,initial,length+12)
    if len(result)<14:raise ValueError('Descriptor response too short')
    return result[12:]

def configurations(raw):
    """Describe actual UVC formats without inventing a low-bandwidth mode."""
    result=[];i=0;subclass=None;fourcc=None
    while i+2<=len(raw):
        size,kind=raw[i:i+2]
        if size<2 or i+size>len(raw):break
        d=raw[i:i+size]
        if kind==4 and size>=9:subclass=d[6] if d[5]==14 else None
        if kind==0x24 and size>=3 and subclass==2:
            sub=d[2]
            if sub==4 and size>=21:fourcc=d[5:9].decode('ascii',errors='replace')
            elif sub==6:fourcc='MJPEG'
            elif sub in (5,7) and size>=26:
                width,height=struct.unpack_from('<HH',d,5)
                count=d[25];intervals=[]
                if count and size>=26+count*4:intervals=list(struct.unpack_from('<'+'I'*count,d,26))
                elif count==0 and size>=38:intervals=list(struct.unpack_from('<III',d,26))
                result.append(dict(format=fourcc,width=width,height=height,interval_type='discrete' if count else 'continuous_min_max_step',intervals_100ns=intervals))
        i+=size
    return result

def probe():
    targets=[];errors=[];hub_links=[];count=0;other=0;reference=False
    for path in hubs():
        count+=1
        handle=kernel.CreateFileW(path,0x40000000,3,None,3,0,None)
        if handle==INVALID:errors.append(dict(hub=count,open_error=c.get_last_error()));continue
        try:
            info=ioctl(handle,258,b'\x00'*4,256)
            if len(info)<7:continue
            for port in range(1,min(info[6],64)+1):
                try:connection=ioctl(handle,274,struct.pack('<I',port),4096)
                except OSError as e:errors.append(dict(hub=count,port=port,read_error=e.winerror));continue
                if len(connection)<35:continue
                status=struct.unpack_from('<I',connection,31)[0]
                if not status:continue
                if status!=1:errors.append(dict(hub=count,port=port,connection_status=status));continue
                d=connection[4:22]
                if d[:2]!=b'\x12\x01':errors.append(dict(hub=count,port=port,invalid_device_descriptor=True));continue
                vid,pid=struct.unpack_from('<HH',d,8)
                if connection[24]:hub_links.append(dict(parent_hub=count,port=port,vid_pid=f'{vid:04X}:{pid:04X}',bcd_usb=f'{struct.unpack_from("<H",d,2)[0]:04X}',connection_speed_code=connection[23]))
                reference|=(vid,pid)==(0x1a86,0x8010)
                if (vid,pid) not in TARGETS:other+=1;continue
                item=dict(hub=count,port=port,vid_pid=f'{vid:04X}:{pid:04X}',connection_status=status,device_descriptor_hex=d.hex(),bcd_usb=f'{struct.unpack_from("<H",d,2)[0]:04X}',connection_speed_code=connection[23])
                try:
                    v2=ioctl(handle,279,struct.pack('<IIII',port,16,7,0),16)
                    flags=struct.unpack_from('<I',v2,12)[0]
                    item['superspeed_operating']=bool(flags&1);item['superspeed_capable']=bool(flags&2)
                    item['superspeedplus_operating']=bool(flags&4)
                except OSError as e:item['v2_error']=e.winerror
                for kind,label,initial_len in [(2,'configuration',9),(15,'bos',5)]:
                    try:
                        raw=descriptor(handle,port,kind,initial_len)
                        total=struct.unpack_from('<H',raw,2)[0]
                        if total<initial_len or total>16384:raise ValueError('Invalid descriptor total length')
                        raw=descriptor(handle,port,kind,total);item[label+'_hex']=raw.hex()
                        if kind==2:
                            item['configured_max_power_raw']=raw[8]
                            item['uvc_modes']=configurations(raw)
                    except (OSError,ValueError) as e:item[label+'_error']=str(e)
                targets.append(item)
        except OSError as e:errors.append(dict(hub=count,hub_read_error=e.winerror))
        finally:kernel.CloseHandle(handle)
    return dict(scope='WINDOWS_STANDARD_HUB_GET_QUERIES_ONLY',hub_count=count,hub_links=hub_links,p9_reference_connected=reference,other_connected_count=other,cameras=targets,port_errors=errors,
                limitations='Current link only. bcdUSB/capability is not proof of USB2 firmware fallback; a real USB2 link must be tested. No reset, disable, driver replacement, firmware or video operations.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'output/onboard_dashboard/camera-compat-20261026/windows-usb-current.json');args=parser.parse_args()
    report=probe();args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['limitations']},ensure_ascii=False))
