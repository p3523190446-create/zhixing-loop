"""Adapt isolated PC adapter while keeping existing readback/control gates."""
from prepare_mecanum import SW,UI,replace

def main():
    p=UI/'speed_server.py';s=(SW/'debug_ui/speed_server.py').read_text(encoding='utf-8')
    s=replace(s,"    def snapshot(self):", "    def is_mecanum(self):\n        return self.identity=='R1_DRIVE_STARTUP_MANUAL_MECANUM_V1_20261026'\n\n    def snapshot(self):")
    s=replace(s,"'DRIVE_PROFILE')", "'DRIVE_PROFILE','DRIVE_CHASSIS','DRIVE_VECTOR_STATUS')")
    # Expand existing native-speed/full-speed predicates, without changing their old cases.
    s=s.replace("'MANUAL_V8' in self.identity", "('MANUAL_V8' in self.identity or self.is_mecanum())")
    s=replace(s,"'DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_V8_20261023,1')", "'DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_V8_20261023,1','DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_MECANUM_V1_20261026,1')")
    s=replace(s,"expected = 'DRIVE_CAPS,4,250,600'", "expected = 'DRIVE_CAPS,5,250,600' if 'MANUAL_MECANUM_' in identity else 'DRIVE_CAPS,4,250,600'")
    s=replace(s,"                        self.identity = identity.split(',')[1]", "                        self.identity = identity.split(',')[1]\n                        if self.is_mecanum() and self.exchange('DRIVE_CHASSIS','DRIVE_CHASSIS,')!='DRIVE_CHASSIS,MECANUM_X,FL_RL_FR_RR,250,600':\n                            raise ValueError('麦轮布局协议不符')")
    s=replace(s,"manual_stem='r1_official_tt_v8'", "manual_stem='r1_mecanum' if self.is_mecanum() else 'r1_official_tt_v8'")
    s=replace(s,"            self.seq = seq\n", "            self.seq = seq\n")  # Unique anchor protects preparation from drift.
    s=replace(s,"                left, right = throttle+turn, throttle-turn", "                strafe=integer(body,'strafe',-100,100) if 'strafe' in body else 0\n                if strafe and not self.is_mecanum():raise ValueError('当前固件不支持横移')\n                left, right = throttle+turn, throttle-turn")
    s=replace(s,"                self.exchange(f'DRIVE_SET,{self.generation},{seq},{left},{right}', 'DRIVE_SET_ACCEPTED')", """                if self.is_mecanum():
                    norm=max(100,abs(throttle)+abs(strafe)+abs(turn))
                    forward,lateral,yaw=[int(v/norm*250*limit/100) for v in (throttle,strafe,turn)]
                    self.exchange(f'DRIVE_VECTOR,{self.generation},{seq},{forward},{lateral},{yaw}','DRIVE_VECTOR_ACCEPTED')
                    left,right=forward+lateral+yaw,forward-lateral-yaw
                else:self.exchange(f'DRIVE_SET,{self.generation},{seq},{left},{right}', 'DRIVE_SET_ACCEPTED')""")
    s=replace(s,"        data['demo'] = False", "        data['capabilities']['mecanum_control']=data['capabilities']['drive_control'] and self.is_mecanum()\n        data.setdefault('drive',{})['chassis']='mecanum' if self.is_mecanum() else 'differential'\n        data['demo'] = False")
    p.write_text(s,encoding='utf-8')
    p=UI/'pc_integration.py';s=(SW/'debug_ui/pc_integration.py').read_text(encoding='utf-8')
    s=s.replace("'MANUAL_V8' in data.get('firmware','')", "('MANUAL_V8' in data.get('firmware','') or 'MANUAL_MECANUM_' in data.get('firmware',''))")
    p.write_text(s,encoding='utf-8');print('PC adapter prepared; readback gate retained')

if __name__=='__main__':main()
