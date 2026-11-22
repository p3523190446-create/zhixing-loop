"""Read-only USB diagnostics for the already configured SOYES K99. No control calls."""
import argparse
import datetime
import json
import re
import shlex
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ADB = ROOT / "tmp/android-tools/platform-tools/adb.exe"


def adb(*args):
    try:
        p = subprocess.run([str(ADB), *args], capture_output=True, timeout=25)
        return {"returncode": p.returncode, "stdout": p.stdout.decode("utf-8", "replace"),
                "stderr": p.stderr.decode("utf-8", "replace")}
    except subprocess.TimeoutExpired:
        return {"returncode": None, "stdout": "", "stderr": "TIMEOUT_25_SECONDS"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial")
    parser.add_argument("--label", default="snapshot")
    args = parser.parse_args()
    rows = adb("devices")["stdout"].splitlines()[1:]
    devices = [r.split()[0] for r in rows if len(r.split()) == 2 and r.split()[1] == "device"]
    if args.serial:
        if args.serial not in devices:
            raise SystemExit("Requested ADB transport is not connected")
        serial = args.serial
    elif len(devices) == 1:
        serial = devices[0]
    else:
        raise SystemExit("Need exactly one ADB device or --serial; no device selected")
    def shell(*command):
        # adb shell joins argv itself; quote the remote argv as one command.
        return adb("-s", serial, "shell", shlex.join(command))
    identity = {key: shell("getprop", key)["stdout"].strip() for key in
                ("ro.product.model", "ro.board.platform", "ro.build.version.sdk")}
    if identity.get("ro.board.platform") != "mt6739" or identity.get("ro.build.version.sdk") != "28":
        raise SystemExit("Phone differs from verified K99; no further collection")
    package = shell("pm", "path", "cn.zhixing.dashboard")
    if not package["stdout"].startswith("package:"):
        raise SystemExit("Expected existing dashboard app absent")
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    report = {"time": now.isoformat(), "label": args.label, "identity": identity,
              "read_only": True, "controller_commands_sent": False, "results": {}}
    commands = {
        "usb_service": ("dumpsys", "usb"),
        "wifi_ipv4": ("ip", "-4", "addr", "show", "wlan0"),
        "network_routes": ("ip", "route"),
        "kernel_usb": ("dmesg",),
        "system_usb": ("logcat", "-b", "main", "-b", "system", "-d", "-v", "threadtime", "-t", "4000", "UsbHostManager:V", "UsbDescriptorParser:V", "UsbDeviceManager:V", "UsbPortManager:V", "UsbAlsaManager:V", "UsbSettingsManager:V", "UVCCamera:V", "libusb:V", "*:S"),
        "sysfs_usb": ("sh", "-c", "for d in /sys/bus/usb/devices/*; do echo \"DEVICE $d\"; for f in idVendor idProduct speed bcdUSB product authorized; do echo \"$f\"; cat \"$d/$f\" 2>&1; done; done"),
    }
    for name, command in commands.items():
        report["results"][name] = shell(*command)
        if name == "kernel_usb":
            report["results"][name]["stdout"] = "\n".join(line for line in report["results"][name]["stdout"].splitlines() if re.search(r"usb|xhci|ehci|otg|descriptor|over.current|enumerat|permission|klogctl", line, re.I))
        if name == "usb_service":
            report["results"][name]["stdout"] = re.sub(
                r"(?m)^(\s*(?:user_keys|system_keys)=).*$", r"\1[REDACTED]",
                report["results"][name]["stdout"])
    report["limitations"] = "Kernel/sysfs may be denied on stock Android; a denial is not proof of no USB error. Logcat is a bounded recent snapshot. No root, reset, permission requests, app launch or camera start."
    out = ROOT / "output/onboard_dashboard/camera-compat-20261026/phone-usb-logs"
    out.mkdir(parents=True, exist_ok=True)
    target = out / (now.strftime("%Y%m%d-%H%M%S-%f") + ".json")
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved": str(target), "identity": identity,
                      "results": {k: {"returncode": v["returncode"], "bytes": len(v["stdout"]),
                                        "permission_denied": "Permission denied" in v["stdout"]}
                                  for k, v in report["results"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
