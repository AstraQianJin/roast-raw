#!/usr/bin/env python3
"""Build arbitrary-length synthetic plans in memory; the CLI writes JSON to stdout."""
import argparse
import copy
import datetime
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.app.validation import Reject, is_integer, issue, validate_legacy, validate_plan
from server.tools.gen_data import SAMPLE, adapt, build_movements, read_json


def build(count):
    """Return a consistent RPL-Raw-v1 cycle of count positive integral weeks.

    Repeat a real non-test block's prescriptions, clipping only the final block.
    No legacy telemetry, test paths, warmups, running or GPP schedules are reused.
    """
    if not is_integer(count) or count < 1:
        raise Reject([issue("synthetic", "count", "positive integral week count, not bool", count)])
    count = int(count)
    lib, mm = build_movements()
    original, template_sha = read_json(SAMPLE)
    validate_legacy(original, file=str(SAMPLE), lib=lib)
    source = original["plan"]
    start = datetime.date.fromisoformat(next(r["value"] for r in source["Profile"] if r["field"] == "start_date"))
    if count > ((datetime.date.max - start).days + 1) // 7:
        raise Reject([issue("synthetic", "count", "cycle fitting ISO calendar", count)])
    begin, template = 1, None
    for block in source["Blocks"]:
        span = int(block["work_weeks"] + block["deload_weeks"])
        if block["cycle_type"].lower() != "peak" and not block["work_mode"].lower().endswith(".test") and block["work_weeks"] > 0:
            template = block
            break
        begin += span
    if template is None:
        raise Reject([issue(str(SAMPLE), "Blocks", "non-test training block", None)])
    span = int(template["work_weeks"] + template["deload_weeks"])
    templates = {offset: [r for r in source["Workouts"] if r["week"] == begin + offset]
                 for offset in range(span)}
    if any(not rows for rows in templates.values()):
        raise Reject([issue(str(SAMPLE), "Workouts", "training rows for every template week", None)])
    profile = []
    for row in source["Profile"]:
        if row["field"] == "motto" or row["field"].startswith("target_"):
            continue
        row = copy.deepcopy(row)
        row["description"] = "Synthetic baseline: " + row["field"]
        if row["field"] == "plan_weeks":
            row["value"] = count
        profile.append(row)
    days = copy.deepcopy(source["Days"])
    for day in days:
        day["title_en"] = "SYNTHETIC DAY " + day["day_id"]
        day["title_zh"] = ""
    plan = {"Profile": profile, "Blocks": [], "Days": days, "Workouts": []}
    if "Anchors" in source:
        plan["Anchors"] = copy.deepcopy(source["Anchors"])
    for first in range(1, count + 1, span):
        length = min(span, count - first + 1)
        block = copy.deepcopy(template)
        block["block_id"] = "SYN-%d" % (len(plan["Blocks"]) + 1)
        block["name_en"] = "SYNTHETIC / " + template["name_en"]
        block["name_zh"] = ""
        block["work_weeks"] = min(length, int(template["work_weeks"]))
        block["deload_weeks"] = length - block["work_weeks"]
        plan["Blocks"].append(block)
        for offset in range(length):
            for template_row in templates[offset]:
                row = copy.deepcopy(template_row)
                row["week"] = first + offset
                row.pop("date", None)  # Derived again by adapt from start/week/day.
                row["notes"] = "Synthetic prescription copied from source week %d.%s" % (
                    begin + offset, " Bodyweight." if "bodyweight" in row.get("notes", "").lower() else "")
                for field in ("actual_reps", "actual_rpe", "done_sets"):
                    row[field] = ""
                row["done"] = False
                plan["Workouts"].append(row)
    envelope = {"format": "RPL-Plan", "schemaVersion": "RPL-Plan-v4",
                "app": {"name": "Roast Raw synthetic fixture"}, "plan": plan}
    # Hash the actual serialized synthetic input, not the unrelated source sample.
    payload = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    doc = adapt(json.loads(payload), lib, mm, source_sha256=hashlib.sha256(payload).hexdigest(), file="synthetic.json")
    doc["source"]["synthetic"] = True
    doc["source"]["templateSha256"] = template_sha
    doc["meta"]["planId"] = "rpl-raw-synthetic-%dw-%s" % (count, doc["meta"]["startDate"])
    doc["meta"]["name"] = "Synthetic %d-week training cycle" % count
    return validate_plan(doc, file="synthetic.json", lib=lib)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("count", type=int, help="positive number of synthetic weeks")
    args = parser.parse_args()
    try:
        doc = build(args.count)
    except Reject as exc:
        print(json.dumps({"error": "IMPORT_REJECTED", "errors": exc.errors}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(doc, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
