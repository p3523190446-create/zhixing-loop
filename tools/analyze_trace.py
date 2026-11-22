"""Summarize four-column input logs; never infer physical reliability from them."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

LINE = re.compile(r"[ \t]*([0-9]+)[ \t]*,[ \t]*([0-9]+)[ \t]*,[ \t]*([0-9]+)[ \t]*,[ \t]*([0-9]+)[ \t]*")
LIMITS = (4294967295, 1, 1, 65535)
ORIGINS = ("unknown", "synthetic", "hardware_declared")


def parse_trace(content):
    rows = []
    lines = content.removeprefix("\ufeff").split("\n")
    for number, raw in enumerate(lines, 1):
        physical_length = len(raw.encode("utf-8")) + (1 if number < len(lines) else 0)
        if physical_length > 159 or "\0" in raw:
            raise ValueError(f"line {number}: invalid bytes or too long for replay format")
        if raw.endswith("\r"):
            raw = raw[:-1]
        stripped = raw.lstrip(" \t")
        if not stripped or stripped.startswith("#"):
            continue
        match = LINE.fullmatch(raw)
        if match is None:
            raise ValueError(f"line {number}: expected time_ms,has_new_sample,valid,distance_mm")
        values = tuple(int(value) for value in match.groups())
        if any(value > limit for value, limit in zip(values, LIMITS)):
            raise ValueError(f"line {number}: integer out of range")
        if rows and values[0] <= rows[-1][0]:
            raise ValueError(f"line {number}: timestamps must strictly increase; split reboot/wrap segments")
        rows.append(values)
    if not rows:
        raise ValueError("trace contains no data rows")
    return rows


def summarize(rows, origin="unknown", firmware="unknown", conditions="not provided"):
    if origin not in ORIGINS:
        raise ValueError("invalid origin")
    new_rows = [row for row in rows if row[1]]
    valid_rows = [row for row in new_rows if row[2]]
    invalid_count = len(new_rows) - len(valid_rows)
    distances = [row[3] for row in valid_rows]
    gaps = [right[0] - left[0] for left, right in zip(valid_rows, valid_rows[1:])]
    all_gaps = [right[0] - left[0] for left, right in zip(rows, rows[1:])]
    notes = [
        "Only input records are summarized; no guard state/output is simulated here.",
        "Origin is a caller declaration, not independently verified hardware provenance.",
        "No reference distance or output timestamp is present: accuracy, response time and missed alarms cannot be calculated.",
        "Intervals describe supplied records; missing records and old values mislabeled as new cannot be ruled out.",
        "No automatic pass/fail, award estimate or reliability claim is produced.",
    ]
    if origin == "synthetic":
        notes.insert(0, "SYNTHETIC DATA: this report must not count as hardware test evidence.")
    if not valid_rows:
        notes.append("No valid measurement in this trace; distance statistics and valid-sample intervals are unavailable.")
    if len(rows) == 1:
        notes.append("Single row: observation span is zero and no sampling interval can be inferred.")
    return {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "declared_origin": origin, "firmware_id": firmware,
        "declared_conditions": conditions,
        "rows": len(rows), "first_time_ms": rows[0][0], "last_time_ms": rows[-1][0],
        "observation_span_ms": rows[-1][0] - rows[0][0],
        "new_sample_count": len(new_rows), "valid_new_sample_count": len(valid_rows),
        "invalid_new_sample_count": invalid_count,
        "no_new_sample_rows": len(rows) - len(new_rows),
        "invalid_fraction_of_new_samples": invalid_count / len(new_rows) if new_rows else None,
        "largest_record_interval_ms": max(all_gaps) if all_gaps else None,
        "largest_valid_sample_interval_ms": max(gaps) if gaps else None,
        "median_valid_sample_interval_ms": statistics.median(gaps) if gaps else None,
        "initial_gap_before_first_valid_ms": valid_rows[0][0] - rows[0][0] if valid_rows else None,
        "tail_after_last_valid_ms": rows[-1][0] - valid_rows[-1][0] if valid_rows else None,
        "distance_mm": {
            "minimum": min(distances) if distances else None,
            "maximum": max(distances) if distances else None,
            "median": statistics.median(distances) if distances else None,
        },
        "limitations": notes,
    }


def markdown(report):
    def value(item):
        return "不可计算" if item is None else str(item)
    origin = {"synthetic": "模拟数据（不得作为实物证据）",
              "hardware_declared": "操作者声明来自硬件（本工具未核实）",
              "unknown": "来源未确认"}[report["declared_origin"]]
    rows = [
        ("记录行数", report["rows"]),
        ("观察跨度 ms", report["observation_span_ms"]),
        ("新样本数量", report["new_sample_count"]),
        ("有效新样本数量", report["valid_new_sample_count"]),
        ("明确无效新样本数量", report["invalid_new_sample_count"]),
        ("没有新样本的记录行", report["no_new_sample_rows"]),
        ("无效比例（分母仅新样本）", None if report["invalid_fraction_of_new_samples"] is None else
         f"{report['invalid_fraction_of_new_samples']:.2%} ({report['invalid_new_sample_count']}/{report['new_sample_count']})"),
        ("最大相邻记录间隔 ms", report["largest_record_interval_ms"]),
        ("最大相邻有效样本间隔 ms", report["largest_valid_sample_interval_ms"]),
        ("有效样本间隔中位数 ms", report["median_valid_sample_interval_ms"]),
        ("首行至首个有效样本 ms", report["initial_gap_before_first_valid_ms"]),
        ("最后有效样本至末行 ms", report["tail_after_last_valid_ms"]),
    ]
    # User-supplied metadata is shown as JSON inside a code block.
    metadata = json.dumps({key: report[key] for key in
                           ("firmware_id", "declared_conditions", "source_sha256")}, ensure_ascii=False, indent=2)
    metadata = metadata.replace("`", "\\u0060")
    return ("# 输入记录分析\n\n**来源：" + origin + "**\n\n"
            + "```json\n" + metadata + "\n```\n\n"
            + "| 指标 | 结果 |\n| --- | --- |\n"
            + "\n".join(f"| {label} | {value(item)} |" for label, item in rows)
            + "\n\n距离的最小/中位/最大值只描述这些有效读数，不代表测量准确度："
            + "/".join(value(report["distance_mm"][key]) for key in ("minimum", "median", "maximum"))
            + " mm。\n\n本报告不模拟状态机，不计算误报/漏报率或物理响应时间，也不判断测试是否合格。记录缺口、旧数据被误标成新数据、日志丢行均需另行核实。\n\n"
            + "**下一步**：将异常时间段与同版本原始状态码、物理操作记录对照；需要检查状态时使用 C 回放工具。**停止条件**：来源、单位或版本不明时先补记录，不将统计表写成实物通过证明。\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--origin", choices=ORIGINS, default="unknown")
    parser.add_argument("--firmware", default="unknown")
    parser.add_argument("--conditions", default="not provided")
    parser.add_argument("--output", type=Path, help="New output directory; must not already exist")
    args = parser.parse_args()
    try:
        raw = args.trace.read_bytes()
        rows = parse_trace(raw.decode("utf-8-sig"))
        report = summarize(rows, args.origin, args.firmware, args.conditions)
        report["source_sha256"] = hashlib.sha256(raw).hexdigest()
        report["source_file"] = args.trace.name
        if args.output:
            args.output.mkdir(parents=True, exist_ok=False)
            (args.output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (args.output / "summary.md").write_text(markdown(report), encoding="utf-8")
            print(args.output.resolve())
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
