"""Retrieve the known passive capture; stop only its verified process IDs."""
import argparse
import datetime
import json
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ADB = ROOT / "tmp/android-tools/platform-tools/adb.exe"
SERIAL = "0123456789ABCDEF"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("manifest", type=Path)
args = parser.parse_args()
manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
remote = manifest["remote_directory"]
if not re.fullmatch(r"/data/local/tmp/zhixing_usb_diag_\d{8}_\d{6}", remote):
    raise SystemExit("Unexpected capture directory")

def adb(*a, check=True):
    return subprocess.run([str(ADB), "-s", SERIAL, *a], capture_output=True, timeout=25, check=check)

def shell(command):
    return adb("shell", command, check=False).stdout.decode("utf-8", "replace").strip()

if shell("getprop ro.board.platform") != "mt6739" or shell("getprop ro.build.version.sdk") != "28":
    raise SystemExit("Not the configured phone")
stopped = []
for file, expected in [("recorder.pid", remote + "/record-usb.sh"), ("logcat.pid", "usb-events.log")]:
    pid = shell("cat " + shlex.quote(remote + "/" + file))
    if pid.isdigit():
        command = shell("cat /proc/" + pid + "/cmdline").replace("\x00", " ")
        if expected in command:
            shell("kill " + pid)
            stopped.append(int(pid))
raw = args.manifest.parent / "readback"
raw.mkdir(exist_ok=True)
adb("pull", remote + "/.", str(raw))
files = list(raw.glob("*.txt")) + list(raw.glob("*.log*"))
for path in files:
    data = path.read_text(encoding="utf-8", errors="replace")
    data = re.sub(r"(?m)^(\s*(?:user_keys|system_keys)=).*$", r"\1[REDACTED]", data)
    path.write_text(data, encoding="utf-8")
states = []
for path in sorted(raw.glob("usb-state-*.txt"), key=lambda p: int(p.stem.rsplit("-", 1)[1])):
    data = path.read_text(encoding="utf-8")
    active_host = data.split("host_manager={", 1)[-1].split("num_connects=", 1)[0]
    states.append({"file": path.name, "phone_date": data.splitlines()[0] if data else "",
                   "host_connected": "host_connected=true" in data,
                   "source_power": "source_power=true" in data,
                   "usb_device_role": "data_role=device" in data,
                   "usb_host_role": "data_role=host" in data,
                   "num_connects": re.findall(r"num_connects=(\d+)", data),
                   "current_vid_pid": sorted(set(f"{int(v):04X}:{int(p):04X}" for v, p in re.findall(r"vendor_id=(\d+)\s+product_id=(\d+)", active_host))),
                   "historical_vid_pid": sorted(set(f"{int(v):04X}:{int(p):04X}" for v, p in re.findall(r"manufacturer=(\d+)\s+product=(\d+)", data)))})
report = {"time": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
          "remote_directory": remote, "stopped_verified_pids": stopped,
          "files_read_back": len(list(raw.iterdir())), "states": states,
          "limitations": "VID/PID sets from dumpsys include retained history, not just currently attached devices. Correlate new events and host-role intervals. Kernel access was denied; no root or motion commands."}
target = args.manifest.parent / "readback-summary.json"
target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"summary": str(target), "states": states, "stopped_verified_pids": stopped}, ensure_ascii=False))
