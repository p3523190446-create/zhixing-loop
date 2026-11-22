"""Reuse guarded P9 deployment; read calibration caps only, never synthetic calibration."""
from pathlib import Path
import bringup_line_task as old
script=Path(old.__file__).read_text(encoding='utf-8')
script=script.replace("OUT=ROOT/'output/onboard_dashboard/phone-line-control-20261026'","OUT=ROOT/'output/onboard_dashboard/phone-line-calibration-20261027'")
script=script.replace("TOOLS/'flash_r1_line_task.py'","TOOLS/'flash_r1_line_calibration.py'")
script=script.replace("record['samples']=[];until=", "record['calibration_caps']=query('LINE_TASK_CAL_CAPS');assert record['calibration_caps']=='LINE_TASK_CAL_CAPS,1,8'\n   record['calibration_initial']=query('LINE_TASK_CAL_GET','LINE_TASK_CAL,');assert record['calibration_initial'].startswith('LINE_TASK_CAL,0,')\n   record['samples']=[];until=")
script=script.replace("record['service_pid_after']=service.pid", "record['service_pid_after']=service.pid\n   runtime['pid']=service.pid;(ROOT/'output/onboard_dashboard/pc-speed-20261021/runtime.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding='utf-8')")
exec(compile(script,old.__file__,'exec'),{'__file__':old.__file__,'__name__':'__main__'})
