"""Build and verify host logic; never changes system execution policies."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", help="Path to GCC, Clang or TinyCC")
    parser.add_argument("--compile-only", action="store_true",
                        help="Build only; no generated program is executed")
    args = parser.parse_args()
    compiler = args.compiler or next((shutil.which(x) for x in
                                     ("gcc", "clang", "tcc") if shutil.which(x)), None)
    local = ROOT.parent / "tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe"
    if not compiler and local.is_file():
        compiler = str(local)
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "host C logic only; no MCU, wiring or hardware validation",
        "compile_only": args.compile_only, "compiler": compiler,
        "status": "INCOMPLETE", "steps": [], "source_sha256": {},
    }
    for folder in ("include", "src", "tests", "sim", "board", "tools"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and path.suffix in (".c", ".h", ".csv", ".py"):
                report["source_sha256"][path.relative_to(ROOT).as_posix()] = (
                    hashlib.sha256(path.read_bytes()).hexdigest())

    def run(label, command, expected=0):
        step = {"name": label, "command": [str(x) for x in command]}
        report["steps"].append(step)
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            step.update(status="BLOCKED", error=str(error))
            raise RuntimeError(f"{label}: execution blocked or timed out: {error}") from error
        step.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                    status="PASS" if result.returncode == expected else "FAIL")
        if result.returncode != expected:
            raise RuntimeError(f"{label}: expected exit {expected}, got {result.returncode}")
        return result.stdout

    def require(label, condition):
        report["steps"].append({"name": label, "status": "PASS" if condition else "FAIL"})
        if not condition:
            raise RuntimeError(label)

    try:
        if not compiler:
            raise RuntimeError("No compiler found. Supply --compiler; no tools are downloaded automatically.")
        run("compiler version", [compiler, "-v"])
        flags = [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-Iinclude"]
        sources = sorted((ROOT / "src").glob("*.c"))
        # Compile board integration contracts, without pretending the BSP is implemented.
        for path in sources + sorted((ROOT / "board").glob("*.c")):
            run("compile " + path.name, flags + ["-c", str(path), "-o", str(build / (path.stem + ".o"))])
        suffix = ".exe" if os.name == "nt" else ""
        programs = {
            "guard_tests": [str(p) for p in sources] + ["tests/test_guard.c"],
            "guard_demo": ["src/guard.c", "src/app.c", "sim/demo.c"],
            "guard_replay": ["src/guard.c", "src/trace.c", "sim/replay.c"],
        }
        for name, files in programs.items():
            run("link " + name, flags + files + ["-o", str(build / (name + suffix))])
        if args.compile_only:
            report["status"] = "COMPILE_ONLY_PASS"
            report["runtime_tests"] = "NOT_RUN"
        else:
            run("13 C assertion groups", [str(build / ("guard_tests" + suffix))])
            run("application demo", [str(build / ("guard_demo" + suffix))])
            replay = str(build / ("guard_replay" + suffix))
            output = run("example trace", [replay, "sim/example_trace.csv"])
            rows = list(csv.DictReader(io.StringIO(output)))
            require("example state sequence", [r["state"] for r in rows] == [
                "FAULT", "FAULT", "NORMAL", "CAUTION", "DANGER", "FAULT",
                "FAULT", "FAULT", "NORMAL", "FAULT"])
            require("example motion permissions", [r["motion_allowed"] for r in rows] ==
                    ["0", "0", "1", "1", "0", "0", "0", "0", "1", "0"])
            cases = {
                "duplicate_time": "0,1,1,800\n0,1,1,800\n",
                "backwards_time": "10,1,1,800\n9,1,1,800\n",
                "negative": "-1,1,1,800\n",
                "overflow_time": "4294967296,1,1,800\n",
                "overflow_distance": "0,1,1,65536\n",
                "bad_boolean": "0,2,1,800\n",
                "extra_column": "0,1,1,800,1\n",
                "embedded_nul": "0,1,1,800\0junk\n",
                "cr_then_garbage": "\rgarbage\n0,1,1,800\n",
                "text_eof_suffix": "0,1,1,800\n\x1ajunk\n",
                "empty": "# no data\n",
                "long_line": "0,1,1," + "9" * 200 + "\n",
            }
            for name, content in cases.items():
                path = build / (name + ".csv")
                path.write_text(content, encoding="utf-8")
                run("reject " + name, [replay, str(path)], expected=2)
            path = build / "bom.csv"
            path.write_text("# BOM accepted\n0,1,1,800\n", encoding="utf-8-sig")
            run("accept UTF-8 BOM", [replay, str(path)])
            report["status"] = "HOST_TESTS_PASS"
            report["runtime_tests"] = "PASS"
    except RuntimeError as error:
        report["status"] = "BLOCKED" if any(s.get("status") == "BLOCKED" for s in report["steps"]) else "FAIL"
        report["error"] = str(error)
    finally:
        target = build / "verification.json"
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(report["status"])
        print(target)
        if "error" in report:
            print(report["error"], file=sys.stderr)
    return 0 if report["status"] in ("COMPILE_ONLY_PASS", "HOST_TESTS_PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
