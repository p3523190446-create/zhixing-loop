"""Decode independently aged line readings. No device I/O or movement outputs."""
def decode_line(analog, digital, status):
    if len(analog)!=10 or len(digital)!=3 or len(status)!=12:
        raise ValueError('八路数据长度不符')
    if any(type(n) is not int or not 0<=n<=65535 for n in analog[2:]) or not 0<=digital[2]<=255:
        raise ValueError('八路数据范围不符')
    return dict(valid=analog[1]==1 and digital[1]==1 and status[10]==1 and status[11]==1,
                age_ms=max(analog[0],digital[0]),raw=analog[2:],digital_mask=digital[2],
                analog_frames=status[2],digital_frames=status[3],rejected_frames=status[4],
                uart_errors=status[5],overflows=status[6])
