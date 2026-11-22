"""Flash the prepared, electrically checked ID experiment and collect real MCU samples."""
from pathlib import Path
import hashlib, json, subprocess, socket, time, threading, queue, re, sys

project=Path(__file__).resolve().parents[2]
ranging='--ranging' in sys.argv
calibration_firmware='--calibration-firmware' in sys.argv
assert not calibration_firmware or ranging
corrected_firmware='--corrected-firmware' in sys.argv
assert not corrected_firmware or (ranging and not calibration_firmware)
guard_firmware='--guard-firmware' in sys.argv
assert not guard_firmware or (ranging and not calibration_firmware and not corrected_firmware)
buzzer_output_test='--buzzer-output-test' in sys.argv
assert not buzzer_output_test or (guard_firmware and '--verify-only' in sys.argv)
date_args=[a.split('=',1)[1] for a in sys.argv if a.startswith('--record-date=')]
assert len(date_args)<=1 and (not date_args or re.fullmatch(r'\d{4}-\d{2}-\d{2}',date_args[0]))
cal_args=[a for a in sys.argv if a.startswith('--calibrate-mm=')]
assert len(cal_args)<=1
cal_target=int(cal_args[0].split('=',1)[1]) if cal_args else None
assert cal_target is None or (calibration_firmware and 50<=cal_target<=500)
apply_args=[a for a in sys.argv if a.startswith('--apply-offset-um=')]
assert len(apply_args)<=1
apply_offset=int(apply_args[0].split('=',1)[1]) if apply_args else None
assert apply_offset is None or (calibration_firmware and cal_target is None and -512000<=apply_offset<=511000)
stem='r1_distance_guard' if guard_firmware else 'r1_ranging_corrected' if corrected_firmware else 'r1_ranging_calibration' if calibration_firmware else 'r1_ranging' if ranging else 'r1_i2c_probe'
out=project/'知行回路软件/build'/stem
toolroot=Path.home()/'Documents/ch32-tools'
ocdbin=toolroot/'MRS2/resources/app/resources/win32/components/WCH/OpenOCD/OpenOCD/bin'
elf=toolroot/stem.replace('_','-')/(stem+'.elf')
build=json.loads((out/'build_result.json').read_text(encoding='utf-8'))
source=project/'知行回路软件/board'/stem/'main.c'
assert hashlib.sha256(source.read_bytes()).hexdigest()==build['source_sha256']
assert hashlib.sha256((elf.with_suffix('.bin')).read_bytes()).hexdigest()==build['binary_sha256']
assert elf.read_bytes()==(out/(stem+'.elf')).read_bytes()
logfile=(out/'openocd_hardware.log').open('w',encoding='utf-8')
ocd=None;gdb=None;lines=[];q=queue.Queue();token=0
result={'date':date_args[0] if date_args else '2026-10-06','record_type':'Real MCU raw ranging experiment' if ranging else 'Real MCU identity experiment','firmware_sha256':build['binary_sha256'],'flash':'NOT_RUN','readback':'NOT_RUN','samples':[]}
def cmd(s,timeout=15):
 global token
 token+=1;prefix=str(token)
 gdb.stdin.write(prefix+s+'\n');gdb.stdin.flush()
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  try:
   row=q.get(timeout=.2);lines.append(row)
   if row.startswith(prefix+'^'):
    if '^error' in row:raise RuntimeError(row.strip())
    return row
  except queue.Empty:pass
 raise TimeoutError(s)
def evaluate(name):
 row=cmd('-data-evaluate-expression '+json.dumps(name))
 m=re.search(r'value="([^\"]+)"',row)
 if not m:raise RuntimeError(row)
 return int(m.group(1),0)
def read_output():
 for row in gdb.stdout:q.put(row)
try:
 ocd=subprocess.Popen([str(ocdbin/'openocd.exe'),'-f','wch-riscv.cfg'],cwd=ocdbin,stdout=logfile,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
 for _ in range(60):
  if ocd.poll() is not None:raise RuntimeError('OpenOCD exited; see log')
  try:
   with socket.create_connection(('127.0.0.1',3333),timeout=.2):pass
   break
  except OSError:time.sleep(.2)
 else:raise TimeoutError('OpenOCD GDB port')
 gdb=subprocess.Popen([str(toolroot/'gcc/bin/riscv-none-embed-gdb.exe'),'--interpreter=mi2',str(elf)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
 threading.Thread(target=read_output,daemon=True).start()
 cmd('-gdb-set mi-async on')
 cmd('-target-select extended-remote localhost:3333')
 if '--verify-only' in sys.argv:
  previous=json.loads((out/'hardware_check.json').read_text(encoding='utf-8'))
  assert previous['firmware_sha256']==result['firmware_sha256'] and previous['flash']=='PASS'
  (out/'initial_download_evidence.json').write_text(json.dumps(previous,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  result['flash']='PASS';result['download_this_run']=False
  print('Board attached; verifying previously downloaded '+stem+' experiment.',flush=True)
 else:
  print('Board attached; downloading '+stem+'.',flush=True)
  cmd('-target-download',45);result['flash']='PASS';result['download_this_run']=True
 start=len(lines)
 cmd('-interpreter-exec console "compare-sections"',20)
 compare=''.join(lines[start:]);result['compare_sections_output']=compare
 assert compare.count('matched')>=4 and 'MIS-MATCH' not in compare,compare
 result['readback']='PASS'
 print('Flash and section readback passed.',flush=True)
 if (apply_offset is not None or corrected_firmware or guard_firmware) and '--verify-only' in sys.argv and '--keep-running-state' not in sys.argv:
  # Reconnecting this debugger can leave the vendor SysTick delay waiting.
  # Start from a known reset before explicitly restoring the experimental offset.
  cmd('-interpreter-exec console "monitor reset halt"')
  result['debugger_reset_before_offset_reload']=True
 if cal_target is not None:
  # Caller must have physically fixed the known white target before invocation.
  cmd('-exec-continue');time.sleep(5)
  cmd('-exec-interrupt');time.sleep(.3)
  assert evaluate('range_stage')==8 and evaluate('range_init_error')==0
  result['pre_calibration_sample']={name:evaluate(name) for name in ['range_mm','range_status','range_error']}
  completed_before=evaluate('calibration_completed')
  cmd('-interpreter-exec console "set variable calibration_request_mm = '+str(cal_target)+'"')
  cmd('-exec-continue');time.sleep(10)
  cmd('-exec-interrupt');time.sleep(.3)
  fields=['calibration_target_mm','calibration_completed','calibration_stage','calibration_error','calibration_restore_error','calibration_old_offset_um','calibration_new_offset_um']
  result['offset_calibration']={name:evaluate(name) for name in fields}
  print('Offset calibration: '+json.dumps(result['offset_calibration']),flush=True)
  c=result['offset_calibration']
  assert c['calibration_completed']==completed_before+1 and c['calibration_stage']==2 and c['calibration_error']==0 and c['calibration_restore_error']==0,c
  result['calibration_scope']='Volatile offset only; multi-distance verification and reboot persistence pending'
 if apply_offset is not None:
  cmd('-exec-continue');time.sleep(5)
  cmd('-exec-interrupt');time.sleep(.3)
  assert evaluate('range_stage')==8 and evaluate('range_init_error')==0
  completed_before=evaluate('calibration_apply_completed')
  cmd('-interpreter-exec console "set variable calibration_apply_offset_um = '+str(apply_offset)+'"')
  cmd('-interpreter-exec console "set variable calibration_apply_request = 1"')
  cmd('-exec-continue');time.sleep(3)
  cmd('-exec-interrupt');time.sleep(.3)
  names=['calibration_apply_completed','calibration_apply_error','calibration_active_offset_um']
  result['offset_reload']={name:evaluate(name) for name in names}
  result['requested_offset_um']=apply_offset
  c=result['offset_reload']
  assert c['calibration_apply_completed']==completed_before+1 and c['calibration_apply_error']==0 and c['calibration_active_offset_um']==int(apply_offset/250)*250,c
  result['calibration_scope']='Explicit temporary reload of prior calibrated offset; no boot persistence or new target calibration'
  print('Offset reload: '+json.dumps(c),flush=True)
 for n in range(3):
  cmd('-exec-continue');time.sleep(5 if ranging and n==0 else 2.2)
  cmd('-exec-interrupt');time.sleep(.3)
  names=['range_stage','range_init_error','range_rounds','range_model_id','range_error','range_status','range_mm','range_valid_count','SystemCoreClock'] if ranging else ['probe_rounds','probe_kind','probe_l0_id','probe_l1_id','probe_l0_error','probe_l1_error','SystemCoreClock']
  if corrected_firmware or guard_firmware:
   names+=['range_corrected_mm','range_correction_valid','range_in_calibrated_interval','range_loaded_offset_um']
  if guard_firmware:
   names+=['tick_ms','guard_state','guard_fault','led_mode','led_last_good_ms','led_is_on','led_edges','red_is_on','red_edges','green_is_on','green_edges','buzzer_is_on','buzzer_edges','app_ticks','timer_clock_hz','timer_prescaler','led_period_ms','led_phase_step','led_phase_q24','led_filtered_distance_q8']
  sample={name:evaluate(name) for name in names}
  if guard_firmware:
   sample['pd0_output_level']=evaluate('(*(volatile unsigned int*)0x4001140c)&1')
   sample['pd1_output_level']=evaluate('((*(volatile unsigned int*)0x4001140c)>>1)&1')
   sample['pd2_output_level']=evaluate('((*(volatile unsigned int*)0x4001140c)>>2)&1')
   sample['pd3_output_level']=evaluate('((*(volatile unsigned int*)0x4001140c)>>3)&1')
   sample['pd3_input_level']=evaluate('((*(volatile unsigned int*)0x40011408)>>3)&1')
   sample['pd3_gpio_config']=evaluate('((*(volatile unsigned int*)0x40011400)>>12)&15')
  result['samples'].append(sample)
  print(json.dumps(sample),flush=True)
 if ranging and '--diagnostics' in sys.argv:
  # Debugger reads only: no firmware or calibration changes.
  fields={
   'linearity_gain_x1000':'(int)device.Data.LinearityCorrectiveGain',
   'offset_um':'range_loaded_offset_um' if corrected_firmware or guard_firmware else 'calibration_active_offset_um' if apply_offset is not None else 'device.Data.CurrentParameters.RangeOffsetMicroMeters',
   'xtalk_enabled':'(int)device.Data.CurrentParameters.XTalkCompensationEnable',
   'xtalk_rate_q16':'device.Data.CurrentParameters.XTalkCompensationRateMegaCps',
   'fractional_enabled':'(int)device.Data.RangeFractionalEnable',
   'osc_frequency_mhz_q16':'device.Data.DeviceSpecificParameters.OscFrequencyMHz',
   'signal_rate_mcps_q16':'device.Data.LastRangeMeasure.SignalRateRtnMegaCps',
   'ambient_rate_mcps_q16':'device.Data.LastRangeMeasure.AmbientRateRtnMegaCps',
   'effective_spads_q8':'(int)device.Data.LastRangeMeasure.EffectiveSpadRtnCount',
  }
  result['diagnostics']={key:evaluate(expr) for key,expr in fields.items()}
  print('Diagnostics: '+json.dumps(result['diagnostics']),flush=True)
 count='range_rounds' if ranging else 'probe_rounds'
 result['loop_running']=result['samples'][-1][count]>result['samples'][0][count]
 if ranging:
  result['identity']='VL53L0X' if all(s['range_model_id']==238 for s in result['samples']) else 'UNCONFIRMED'
  result['ranging']='RAW_READ_PASS' if result['loop_running'] and all(s['range_init_error']==0 and s['range_error']==0 and s['range_status']==0 for s in result['samples']) else 'NOT_VALIDATED'
  result['ruler_accuracy']='NOT_RUN'
 else:
  kinds=[s['probe_kind'] for s in result['samples']]
  result['identity']='VL53L0X' if all(k==1 for k in kinds) else 'VL53L1X' if all(k==2 for k in kinds) else 'UNCONFIRMED'
  result['ranging']='NOT_RUN'
 if guard_firmware:
  result['guard_integration']='PASS' if result['ranging']=='RAW_READ_PASS' and all(s['guard_fault']==0 and s['guard_state'] in [0,1,2] for s in result['samples']) and result['samples'][-1]['tick_ms']>result['samples'][0]['tick_ms'] else 'NOT_VALIDATED'
  result['physical_led_patterns']='NOT_RUN_THIS_FIRMWARE'
  result['cadence']='RUNTIME_PARAMETERS_PASS' if all(160<=s['led_period_ms']<=1200 and s['led_phase_step']==(1<<24)//s['led_period_ms'] and s['led_is_on']==(1-s['pd0_output_level']) for s in result['samples']) else 'NOT_VALIDATED'
  def three_led_sample_matches(s):
   gpio_matches=(s['led_is_on']==1-s['pd0_output_level'] and s['red_is_on']==1-s['pd1_output_level'] and s['green_is_on']==1-s['pd2_output_level'])
   stale=((s['tick_ms']-s['led_last_good_ms'])&0xffffffff)>=300
   mode=3 if stale else s['led_mode']
   if mode==0:policy_matches=s['green_is_on']==1 and s['led_is_on']==0 and s['red_is_on']==0
   elif mode in (1,2):policy_matches=s['green_is_on']==0 and s['red_is_on']==0
   else:policy_matches=s['red_is_on']==1 and s['green_is_on']==0 and s['led_is_on']==0
   return gpio_matches and policy_matches
  result['triple_led_gpio']='PASS' if all(three_led_sample_matches(s) for s in result['samples']) else 'NOT_VALIDATED'
  result['observed_guard_states']=sorted(set(s['guard_state'] for s in result['samples']))
  result['buzzer_gpio']='PASS' if all(s['buzzer_is_on']==1-s['pd3_output_level'] and s['buzzer_is_on']==s['led_is_on'] for s in result['samples']) else 'NOT_VALIDATED'
  result['pd3_pad_logic']='PASS' if all(s['pd3_input_level']==s['pd3_output_level'] and s['pd3_gpio_config']==2 for s in result['samples']) else 'NOT_VALIDATED'
  result['buzzer_module_sound']='NOT_RUN_PHYSICAL_MODULE'
  result['external_leds']='PHYSICAL_WIRING_AND_BRIGHTNESS_NOT_RUN'
  result['independent_power_cycle']='NOT_RUN_THIS_FIRMWARE'
 if buzzer_output_test:
  assert evaluate('((*(volatile unsigned int*)0x40011400)>>12)&15')==2
  result['forced_pd3_test']={'scope':'CPU temporarily halted; direct GPIO low/high pulses bypass distance logic; no firmware or supply change','requested_low_hold_s':0.6,'requested_high_gap_s':0.4,'pulses':[],'actual_sound':'USER_OBSERVATION_PENDING'}
  def set_pd3(high):
   address='0x40011410' if high else '0x40011414'
   cmd('-interpreter-exec console '+json.dumps('set {unsigned int}'+address+' = 8'))
  try:
   set_pd3(True)
   for n in range(3):
    set_pd3(False)
    pulse={'n':n+1,'low_output':evaluate('((*(volatile unsigned int*)0x4001140c)>>3)&1'),'low_input':evaluate('((*(volatile unsigned int*)0x40011408)>>3)&1')}
    result['forced_pd3_test']['pulses'].append(pulse)
    assert pulse['low_output']==0 and pulse['low_input']==0,pulse
    time.sleep(.6)
    set_pd3(True)
    pulse.update(high_output=evaluate('((*(volatile unsigned int*)0x4001140c)>>3)&1'),high_input=evaluate('((*(volatile unsigned int*)0x40011408)>>3)&1'))
    assert pulse['high_output']==1 and pulse['high_input']==1,pulse
    time.sleep(.4)
    print('PD3 direct test pulse '+str(n+1)+' low/high logic passed.',flush=True)
   result['forced_pd3_test']['gpio_logic']='PASS'
  finally:
   set_pd3(True)
   result['forced_pd3_test']['restore']='PD3_HIGH_BEFORE_APPLICATION_RESUME'
 # This WCH GDB build asserts internally after MI detach. Leave the MCU
 # running, close the host debugger, then shut down OpenOCD in finally.
 cmd('-exec-continue')
 time.sleep(.3)
 gdb.terminate();gdb.wait(timeout=3)
 result['debugger_cleanup']='HOST_DEBUGGER_CLOSED_AFTER_CONTINUE'
 print('Identity: '+result['identity'],flush=True)
except Exception as exc:
 result['failure']=repr(exc);print('ERROR '+repr(exc),flush=True)
 if gdb and gdb.poll() is None:
  try:
   cmd('-exec-continue',3)
   result['failure_cleanup']='MCU_CONTINUE_REQUESTED'
  except Exception:
   pass
 raise
finally:
 if gdb and gdb.poll() is None:gdb.terminate()
 if ocd and ocd.poll() is None:
  try:
   with socket.create_connection(('127.0.0.1',4444),timeout=1) as s:s.sendall(b'shutdown\n')
   ocd.wait(timeout=3)
  except (OSError,subprocess.TimeoutExpired):ocd.terminate()
 logfile.close()
 (out/'gdb_hardware.log').write_text(''.join(lines),encoding='utf-8')
 (out/'hardware_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
