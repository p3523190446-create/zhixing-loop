#ifndef ZXR_USBFS_LIFECYCLE_H
#define ZXR_USBFS_LIFECYCLE_H
/* USB configuration/alternate-setting resets affect DATA0 endpoint state.
 * Never touch EP0: it belongs to the control transfer currently in progress. */
static void usbfs_reset_interface(unsigned interface)
{
 if(interface==0 || interface==255){USBFSD->UEP1_TX_CTRL=USBFS_UEP_T_RES_NAK;USBFSD->UEP1_TX_LEN=0;USBFS_Endp_Busy[DEF_UEP1]=0;}
 if(interface==1 || interface==255){
  USBFSD->UEP2_RX_CTRL=USBFS_UEP_R_RES_ACK;
  USBFSD->UEP3_TX_CTRL=USBFS_UEP_T_RES_NAK;USBFSD->UEP3_TX_LEN=0;USBFS_Endp_Busy[DEF_UEP3]=0;
  /* Invalidate queued native commands and stop a previous motion lease. */
  UART2_ParaInit(1);
 }
}
static int usbfs_apply_configuration(unsigned type,unsigned value,unsigned index,unsigned length)
{
 if(type!=0 || value>1 || index!=0 || length!=0)return 0;
 usbfs_reset_interface(255);USBFS_DevConfig=(uint8_t)value;USBFS_DevEnumStatus=value==1;
 return 1;
}
static int usbfs_apply_interface(unsigned type,unsigned value,unsigned index,unsigned length)
{
 if(type!=1 || value!=0 || index>1 || length!=0 || USBFS_DevConfig!=1)return 0;
 usbfs_reset_interface(index);return 1;
}
#endif
