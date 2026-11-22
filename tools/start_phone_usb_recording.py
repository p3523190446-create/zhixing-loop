"""Start a bounded passive on-phone USB capture that survives cable removal."""
import datetime
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ADB = ROOT / "tmp/android-tools/platform-tools/adb.exe"
SERIAL = "0123456789ABCDEF"

def adb(*args):
    return subprocess.run([str(ADB), "-s", SERIAL, *args], capture_output=True, timeout=20, check=True)

def shell(command):
    return adb("shell", command).stdout.decode("utf-8", "replace").strip()

if shell("getprop ro.board.platform") != "mt6739" or shell("getprop ro.build.version.sdk") != "28":
    raise SystemExit("Not the configured phone")
if not shell("pm path cn.zhixing.dashboard").startswith("package:"):
    raise SystemExit("Expected dashboard app missing")
stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y%m%d_%H%M%S")
out = ROOT / "output/onboard_dashboard/camera-compat-20261026/phone-usb-logs" / stamp
out.mkdir(parents=True, exist_ok=False)
remote = "/data/local/tmp/zhixing_usb_diag_" + stamp
script = """#!/system/bin/sh
cd REMOTE || exit 1
echo $$ > recorder.pid
date > started.txt
logcat -b main -b system -v threadtime -T 1 -f usb-events.log -r 256 -n 1 UsbHostManager:V UsbDescriptorParser:V UsbDeviceManager:V UsbPortManager:V UsbAlsaManager:V UsbSettingsManager:V UVCCamera:V libusb:V '*:S' > logcat-launch.txt 2>&1 &
logger=$!
echo "$logger" > logcat.pid
trap 'kill "$logger" 2>/dev/null' EXIT HUP INT TERM
index=0
while [ "$index" -lt 30 ]; do
  { date; dumpsys usb; } > "usb-state-$index.txt" 2>&1
  index=$((index+1))
  sleep 10
done
date > completed.txt
""".replace("REMOTE", shlex.quote(remote))
local = out / "record-usb.sh"
local.write_text(script, encoding="utf-8", newline="\n")
shell("mkdir " + shlex.quote(remote))
adb("push", str(local), remote + "/record-usb.sh")
pid = shell("nohup sh " + shlex.quote(remote + "/record-usb.sh") + " > " + shlex.quote(remote + "/launch.txt") + " 2>&1 < /dev/null & echo $!")
if not pid.isdigit():
    raise SystemExit("Recorder launch did not return a PID: " + pid)
verified = shell("cat /proc/" + pid + "/cmdline").replace("\x00", " ")
if remote + "/record-usb.sh" not in verified:
    raise SystemExit("Recorder process did not persist")
manifest = {"remote_directory": remote, "pid": int(pid), "process_verified": True,
            "duration_limit_seconds": 300, "sample_interval_seconds": 10,
            "controller_commands_sent": False, "app_launched": False,
            "wireless_debugging_enabled": False,
            "note": "Passive USB event recording. Pull after reconnecting; redact ADB public keys in dumpsys before presenting."}
(out / "recording.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"manifest": str(out / "recording.json"), **manifest}, ensure_ascii=False))
