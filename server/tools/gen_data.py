#!/usr/bin/env python3
"""RPL-Plan-v4 -> RPL-Raw-v1 adapter, plus movements.json / ranges.json generation.

Fail-closed: any field error rejects the whole import with a per-field report.
Week count is derived from blocks (work + deload), never from a constant.
Generated files are the only plan/library source the engine and web read.
"""
import copy
import csv
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from server.app.stats import classify as C
from server.app.stats.prescription import mround, parse_segments, row_load, rx_english
from server.app.validation import (Reject, is_number, issue, legacy_movement,
                                   test_dates, validate_legacy, validate_plan)

STATS = Path(ROOT) / "Ref/02_Stats"
SAMPLE = Path(ROOT) / "Ref/01_Current/plan_12w5_sample.json"
OUT = Path(ROOT) / "data"

ANCHOR_CATEGORY = {
    "S.Main": ("squat", "sq_1rm"),
    "B.Main": ("bench", "bp_1rm"),
    "D.Main": ("deadlift", "dl_1rm"),
}

def num(value):
    """Optional legacy number, used only after boundary validation."""
    if value is None or value == "":
        return None
    if not is_number(value):
        raise Reject([issue("plan.json", "number", "finite numeric value (not bool)", value)])
    return float(value)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    """Read actual input bytes, returning (document, sha256)."""
    try:
        data = Path(path).read_bytes()
        doc = json.loads(data.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Reject([issue(path, "$", "readable UTF-8 JSON", str(exc))]) from exc
    return doc, hashlib.sha256(data).hexdigest()


def _metadata(name):
    """Conservative name evidence; category letters do not encode equipment."""
    low = name.casefold()
    equipment = "unknown"
    if " / " not in name:
        for needle, value in (("dumbbell", "dumbbell"), ("cable", "cable"),
                              ("machine", "machine"), ("leg press", "machine"),
                              ("hack squat", "machine"), ("leverage squat", "machine"),
                              ("barbell", "barbell"), ("resistance band", "band")):
            if needle in low:
                equipment = value
                break
        if equipment == "unknown" and name in {
            "High-bar Squat", "Low-bar Squat", "Mid-grip Bench", "Wide-grip Bench",
            "Conventional Deadlift", "Sumo Deadlift", "Power Clean", "Romanian Deadlift", "OHP"
        }:
            equipment = "barbell"
        if equipment == "unknown" and name in {"Pull-Up", "Dip", "Push-Up", "Side Plank", "Plank", "Hanging Leg Raise"}:
            equipment = "bodyweight"
    pattern = "unknown"
    for needles, value in ((["squat", "leg press"], "squat"), (["lunge", "step-up"], "lunge"),
                           (["deadlift", "good morning", "back extension"], "hinge"),
                           (["power clean", "snatch"], "olympic_pull"),
                           (["bench", "push-up"], "horizontal_push"),
                           (["overhead press", "ohp"], "vertical_push"),
                           (["row"], "horizontal_pull"), (["pull-up", "pulldown"], "vertical_pull"),
                           (["plank"], "isometric_core"), (["leg raise"], "trunk_flexion")):
        if any(needle in low for needle in needles):
            pattern = value
            break
    return equipment, pattern


def build_movements(stats_dir=None):
    """Return (library, source_map); reconcile every category-distinct CSV ID."""
    directory = Path(stats_dir) if stats_dir is not None else STATS
    map_file, csv_file = directory / "muscle_map.json", directory / "coefficient_matrix.csv"
    mm, map_sha = read_json(map_file)
    errors = []
    if not isinstance(mm, dict) or mm.get("schema") != "RPL-MuscleMap-v1":
        raise Reject([issue(map_file, "schema", "RPL-MuscleMap-v1", mm)])
    leaf_order = mm.get("leaf_order")
    if (not isinstance(leaf_order, list) or len(leaf_order) != 16
            or not all(isinstance(k, str) for k in leaf_order) or len(set(leaf_order)) != 16):
        raise Reject([issue(map_file, "leaf_order", "16 distinct leaf names", leaf_order)])
    moves, groups = mm.get("moves"), mm.get("group_leaves")
    if not isinstance(moves, dict) or not isinstance(groups, dict) or set(groups) != set(C.MUSCLE_GROUPS):
        raise Reject([issue(map_file, "moves/group_leaves", "movement mapping and six source groups", None)])
    for group, leaves in groups.items():
        if not isinstance(leaves, list) or not leaves or any(k not in leaf_order for k in leaves):
            errors.append(issue(map_file, "group_leaves." + group, "non-empty known leaf list", leaves))
    if errors:
        raise Reject(errors)
    csv_rows = {}
    try:
        with csv_file.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"category", "exercise_en", *leaf_order}
            if not required <= set(reader.fieldnames or []):
                raise Reject([issue(csv_file, "header", sorted(required), reader.fieldnames)])
            for i, row in enumerate(reader, 2):
                if not row.get("category") or not row.get("exercise_en"):
                    errors.append(issue(csv_file, "row.%d.id" % i, "category and exercise_en", row))
                    continue
                key = row["category"] + "|" + row["exercise_en"].casefold()
                if key in csv_rows:
                    errors.append(issue(csv_file, "row.%d.id" % i, "unique category/name", key, movement=key))
                values = {}
                for leaf in leaf_order:
                    try:
                        value = float(row[leaf])
                        if not is_number(value) or not 0 <= value <= 1:
                            raise ValueError()
                        values[leaf] = value
                    except (ValueError, TypeError):
                        errors.append(issue(csv_file, "row.%d.%s" % (i, leaf), "explicit finite coefficient 0..1", row.get(leaf), movement=key))
                csv_rows[key] = (row, values)
    except OSError as exc:
        raise Reject([issue(csv_file, "$", "readable coefficient CSV", str(exc))]) from exc
    for key in sorted(set(moves) ^ set(csv_rows)):
        errors.append(issue(csv_file, "id", "same exact ID in muscle map and CSV", key, movement=key))
    entries = []
    csv_sha = sha(csv_file)
    for key, entry in moves.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("en"), str) or not isinstance(entry.get("cat"), str):
            errors.append(issue(map_file, "moves." + key, "entry with en and cat", entry, movement=key))
            continue
        cat, en = entry["cat"], entry["en"]
        if key != cat + "|" + en.casefold():
            errors.append(issue(map_file, "moves." + key + ".id", cat + "|" + en.casefold(), key, movement=key))
        pair = csv_rows.get(key)
        if pair is None:
            continue
        csv_row, csv_vector = pair
        for field, expected in (("category", cat), ("exercise_en", en)):
            if csv_row[field] != expected:
                errors.append(issue(csv_file, key + "." + field, expected, csv_row[field], movement=key))
        leaf = entry.get("leaf")
        vector, reason = None, None
        if leaf is None or leaf == {}:
            reason = "Source leaf vector is absent or empty; coefficients cannot be inferred."
        elif not isinstance(leaf, dict):
            errors.append(issue(map_file, "moves." + key + ".leaf", "sparse leaf object or null", leaf, movement=key))
            reason = "Invalid source leaf vector."
        else:
            # Only a populated source vector makes omitted CSV zeros meaningful.
            vector = dict(csv_vector)
            for name in set(leaf) - set(leaf_order):
                errors.append(issue(map_file, "moves." + key + ".leaf." + name, "known leaf name", name, movement=key))
            for name in leaf_order:
                if name not in csv_vector:
                    continue
                if name not in leaf and csv_vector[name] != 0:
                    errors.append(issue(map_file, "moves." + key + ".leaf." + name,
                                        "explicit source coefficient matching CSV %s" % csv_vector[name], None, movement=key))
                elif name in leaf:
                    value = leaf[name]
                    if not is_number(value) or not 0 <= value <= 1:
                        errors.append(issue(map_file, "moves." + key + ".leaf." + name, "finite coefficient 0..1", value, movement=key))
                    elif value != csv_vector[name]:
                        errors.append(issue(map_file, "moves." + key + ".leaf." + name, csv_vector[name], value, movement=key))
                    vector[name] = value
        coef = entry.get("coef")
        if not isinstance(coef, dict) or set(coef) != set(C.MUSCLE_GROUPS):
            errors.append(issue(map_file, "moves." + key + ".coef", C.MUSCLE_GROUPS, coef, movement=key))
        else:
            for group in C.MUSCLE_GROUPS:
                value = coef[group]
                if not is_number(value) or not 0 <= value <= 1:
                    errors.append(issue(map_file, "moves." + key + ".coef." + group, "finite coefficient 0..1", value, movement=key))
                elif vector is not None and all(k in vector and is_number(vector[k]) for k in groups[group]):
                    expected = max(vector[k] for k in groups[group])
                    if value != expected:
                        errors.append(issue(map_file, "moves." + key + ".coef." + group, expected, value, movement=key))
        if entry.get("placeholder"):
            reason = "Source placeholder is not a selectable movement."
        equipment, pattern = _metadata(en)
        group = C.movement_group(en, {"category": cat})
        group_basis = "classification-name-rule"
        if group is None and isinstance(coef, dict) and all(is_number(v) for v in coef.values()):
            top = max(coef.values()) if coef else 0
            candidates = [g for g, value in coef.items() if value == top and value > 0]
            group = candidates[0] if len(candidates) == 1 else None
            group_basis = "unique-largest-source-coef6" if group else "unknown"
        bucket = C.movement_bucket(en, {"category": cat})
        entries.append({
            "id": key, "name_en": en, "category": cat,
            "lift": C.movement_lift(en, {"category": cat}), "role": bucket,
            "level": C.movement_level(en), "pattern": pattern, "equipment": equipment, "group": group,
            "coef16": vector, "coef6": copy.deepcopy(coef), "tier": entry.get("tier"),
            "tags": [bucket] + ([pattern] if pattern != "unknown" else []),
            "plan_allowed": reason is None, "reason": reason, "contraindications": [],
            "source": {"muscleMap": "Ref/02_Stats/muscle_map.json", "muscleMapSha256": map_sha,
                       "coefficientCsv": "Ref/02_Stats/coefficient_matrix.csv", "coefficientCsvSha256": csv_sha,
                       "key": key},
            "metadataProvenance": {"equipment": "name-rule" if equipment != "unknown" else "unknown",
                                   "pattern": "name-rule" if pattern != "unknown" else "unknown",
                                   "group": group_basis, "liftRoleLevel": "classification-name/category-rules",
                                   "contraindications": "not supplied by source"},
            "primary_muscle": entry.get("primary_muscle")})
    if errors:
        raise Reject(errors)
    return {"schema": "RPL-Movements-v1", "leaf_order": leaf_order, "groups": mm["groups"],
            "group_leaves": groups, "extra_leaves": mm["extra_leaves"],
            "by_name": mm["by_name"], "ambiguous": mm["ambiguous"], "movements": entries}, mm


def resolve(lib, mm, mv, cat):
    """Exact category/name only; name fallback would erase category identity."""
    if not isinstance(mv, str) or not isinstance(cat, str):
        return None, "unmapped"
    key = cat + "|" + mv.casefold()
    entry = next((m for m in lib["movements"] if m["id"] == key), None)
    if entry is None or entry["name_en"] != mv or entry["category"] != cat:
        return None, "unmapped"
    if entry.get("plan_allowed") is not True or entry.get("coef16") is None:
        return None, "not_allowed"
    return entry, "exact"


def build_ranges(mm, stats_dir=None):
    """Read the ledger when present, otherwise the supplied mmData fixture."""
    directory = Path(stats_dir) if stats_dir is not None else STATS
    ledger = directory / "mev_mrv_sources.csv"
    leaf, errors = {}, []
    if ledger.exists():
        with ledger.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                key = row.get("key", "")
                if not key.startswith("leaf."):
                    continue
                key = key[5:]
                if key in leaf:
                    errors.append(issue(ledger, "leaf." + key, "unique range", key))
                def number(field):
                    raw = row.get(field)
                    if raw is None or raw == "":
                        return None
                    try:
                        value = float(raw)
                        if not is_number(value) or value < 0:
                            raise ValueError()
                        return value
                    except ValueError:
                        errors.append(issue(ledger, "leaf." + key + "." + field, "nonnegative finite number or empty", raw))
                        return None
                scope, group = row.get("interval_scope", ""), row.get("group", "")
                if scope == "group" and group:
                    scope += "_" + group
                leaf[key] = {"mev": number("mev"), "mrv": number("mrv"), "status": row.get("status", ""),
                             "scope": scope, "group": group, "sessions": number("sessions_per_week"),
                             "zero": bool(row.get("zero_reason", "").strip())}
        source = "Ref/02_Stats/mev_mrv_sources.csv"
    else:
        fixture = directory / "mmData.json"
        data, _ = read_json(fixture)
        ranges = data.get("ranges") if isinstance(data, dict) else None
        if not isinstance(ranges, dict):
            raise Reject([issue(fixture, "ranges", "object", ranges)])
        for key in mm["leaf_order"]:
            row = ranges.get(key)
            if not isinstance(row, dict):
                errors.append(issue(fixture, "ranges." + key, "range object or explicit na", row))
                continue
            if row.get("na") is True:
                leaf[key] = {"mev": None, "mrv": None, "scope": None, "group": None,
                             "sessions": None, "zero": False, "status": "unavailable"}
                continue
            for field in ("lo", "hi", "sessions"):
                value = row.get(field)
                if not is_number(value) or value < 0:
                    errors.append(issue(fixture, "ranges." + key + "." + field, "nonnegative finite number", value))
            scope, group = row.get("scope"), row.get("group")
            if scope not in ("leaf", "group") or (scope == "group" and group not in mm["groups"]):
                errors.append(issue(fixture, "ranges." + key + ".scope", "leaf or named group scope", scope))
            leaf[key] = {"mev": row.get("lo"), "mrv": row.get("hi"),
                         "scope": "group_" + group if scope == "group" and isinstance(group, str) else scope,
                         "group": group, "sessions": row.get("sessions"), "zero": row.get("zero") is True,
                         "status": "reference"}
        source = "Ref/02_Stats/mmData.json"
    for key in mm["leaf_order"]:
        if key not in leaf:
            errors.append(issue(source, "leaf." + key, "range or explicit unavailable entry", None))
        elif leaf[key]["mev"] is not None and leaf[key]["mrv"] is not None and leaf[key]["mev"] > leaf[key]["mrv"]:
            errors.append(issue(source, "leaf." + key, "mev <= mrv", leaf[key]))
    if errors:
        raise Reject(errors)
    return {"schema": "RPL-Ranges-v1", "leaf": leaf, "groups": mm["ranges"]["groups"],
            "sbd": mm["ranges"]["sbd"], "source": source}


def adapt(envelope, lib, mm, errors=None, source_sha256=None, file="plan.json"):
    """Adapt validated v4. Byte SHA must come from the actual caller input.

    A dict alone cannot prove the source byte digest; leave it null instead.
    All legacy metadata and tables are retained as an opaque source envelope.
    """
    errors = errors if errors is not None else []
    if errors:
        raise Reject(errors)
    try:
        validate_legacy(envelope, file=file, lib=lib)
    except Reject as exc:
        errors.extend(exc.errors)
        raise Reject(errors) from exc

    def err(**kw):
        errors.append(issue(file, kw.pop("field"), kw.pop("expected"), kw.pop("got", None), **kw))

    plan = envelope["plan"]
    prof = {r["field"]: copy.deepcopy(r["value"]) for r in plan["Profile"]}
    start = datetime.date.fromisoformat(prof["start_date"])
    blocks = [{"id": b["block_id"], "nameEn": b["name_en"], "nameZh": b.get("name_zh", ""),
               "cycleType": b["cycle_type"], "workWeeks": int(b["work_weeks"]),
               "deloadWeeks": int(b["deload_weeks"]), "workMode": b["work_mode"],
               "deloadMode": b["deload_mode"], "baseRpe": num(b.get("base_rpe")),
               "rpeStep": num(b.get("rpe_step")), "deloadRpe": num(b.get("deload_rpe"))}
              for b in plan["Blocks"]]
    total_weeks = sum(b["workWeeks"] + b["deloadWeeks"] for b in blocks)
    days = {d["day_id"]: {"id": d["day_id"], "label": d["label"], "titleEn": d["title_en"],
                          "weekdayOffset": int(d["weekday_offset"]),
                          "focusTags": [t.strip() for t in d.get("focus_tags", "").split(",") if t.strip()]}
            for d in plan["Days"]}
    anchors = {a["id"]: {"value": num(a["value"]), "source": a.get("source", ""),
                         "unit": a.get("unit", ""), "kind": a.get("kind", ""), "movement": a.get("movement", "")}
               for a in plan.get("Anchors", {}).get("entries", [])}
    bw_moves = {a["movement"] for a in anchors.values() if a["kind"] == "bodyweight_max"}

    workouts = []
    for i, r in enumerate(plan["Workouts"]):
        where = {"row": i, "week": r["week"], "day": r["day"], "seq": r["seq"], "movement": r["movement"]}
        week, did, mv = int(r["week"]), r["day"], r["movement"]
        cat = legacy_movement(r)["category"]
        entry, how = resolve(lib, mm, mv, cat)
        if entry is None:
            err(**where, field="Workouts[%d].movement" % i, expected="exact allowed movement", got=how)
            continue
        pct, load_raw = num(r.get("pct_1rm")), num(r.get("load_kg"))
        defn = ANCHOR_CATEGORY.get(cat)
        anchor = num(prof[defn[1]]) if defn else None
        disp_load = load_raw
        if disp_load is None and pct is not None and anchor is not None:
            try:
                disp_load = mround(anchor * pct, 0.5)
            except (ValueError, OverflowError) as exc:
                err(**where, field="Workouts[%d].load_kg" % i, expected="finite computable load", got=str(exc))
                continue
        bucket = C.movement_bucket(mv, {"category": cat})
        role = C.movement_role(mv, {"category": cat})
        if role == "accessory":
            pct = load_raw = disp_load = None
        e = {"rxRaw": r["rx_text"], "load": disp_load, "pct": pct,
             "sets": int(r["sets"]), "reps": int(r["reps"]),
             "notes": r.get("notes", ""), "bwAnchor": mv in bw_moves, "bucket": bucket}
        try:
            segments = parse_segments(e)
        except (ValueError, TypeError, OverflowError) as exc:
            err(**where, field="Workouts[%d].rx_text" % i, expected="parseable prescription", got=str(exc))
            continue
        if role == "accessory":
            for segment in segments:
                segment["load"] = segment["pct"] = None
        seg_sets = sum(s["sets"] for s in segments)
        if seg_sets != e["sets"]:
            err(**where, field="Workouts[%d].sets" % i, expected=e["sets"], got=seg_sets)
        if segments[0]["reps"] != e["reps"]:
            err(**where, field="Workouts[%d].reps" % i, expected=e["reps"], got=segments[0]["reps"])
        tonnage = 0.0
        try:
            for s in segments:
                ld = row_load(s, role)
                if isinstance(s["reps"], int) and s["reps"] > 0 and ld:
                    tonnage += ld * s["sets"] * s["reps"]
            if not is_number(tonnage):
                raise ValueError("non-finite tonnage")
        except (ValueError, OverflowError) as exc:
            err(**where, field="Workouts[%d].tonnageKg" % i, expected="finite computable tonnage", got=str(exc))
            continue
        date = start + datetime.timedelta(days=(week - 1) * 7 + days[did]["weekdayOffset"])
        workouts.append({
            "week": week, "day": did, "date": date.isoformat(),
            "seq": int(r["seq"]), "rowIndex": int(r["row_idx"]),
            "mode": r["mode"], "category": cat, "movement": mv,
            "nameEn": entry["name_en"], "movementId": entry["id"],
            "lift": entry["lift"], "group": entry["group"],
            "role": role, "bucket": bucket, "level": entry["level"],
            "pct": pct, "loadKg": disp_load, "loadRaw": load_raw,
            "sets": seg_sets, "reps": e["reps"], "targetRpe": num(r.get("target_rpe")),
            "notes": e["notes"], "rxRaw": e["rxRaw"], "rxEn": rx_english(e["rxRaw"]),
            "segments": segments, "tonnageKg": round(tonnage, 1), "coefStatus": how})
    if errors:
        raise Reject(errors)

    weeks = []
    n = 0
    for b in blocks:
        span = b["workWeeks"] + b["deloadWeeks"]
        is_test = b["cycleType"].lower() == "peak" or b["workMode"].lower().endswith(".test")
        for w in range(n + 1, n + span + 1):
            kind = "test" if is_test else ("deload" if w > n + b["workWeeks"] else "training")
            ws = start + datetime.timedelta(days=(w - 1) * 7)
            rows = [x for x in workouts if x["week"] == w]
            mains = [x for x in rows if x["bucket"] == "main" and x["pct"] is not None]
            by_lift = {}
            for code in ("S", "B", "D"):
                p = [x["pct"] for x in mains if x["lift"] == code]
                by_lift[code] = round(max(p) * 100, 1) if p else None
            weeks.append({
                "n": w, "blockId": b["id"], "blockName": b["nameEn"], "kind": kind,
                "dateStart": ws.isoformat(),
                "dateEnd": (ws + datetime.timedelta(days=6)).isoformat(),
                "days": sorted({x["day"] for x in rows}),
                "sessions": len({(x["day"]) for x in rows}),
                "sets": sum(x["sets"] for x in rows),
                "tonnageKg": round(sum(x["tonnageKg"] for x in rows), 1),
                "mainTonnageKg": round(sum(x["tonnageKg"] for x in rows if x["bucket"] == "main"), 1),
                "topPct": round(max([x["pct"] for x in mains]) * 100, 1) if mains else None,
                "topPctByLift": by_lift,
            })
        n += span

    gpp = copy.deepcopy(plan.get("GPP", []))
    warm = {}
    for r in plan.get("Warmups", {}).get("sets", []):
        warm.setdefault(r["date"], {}).setdefault(r["movement"], []).append(r)
    warmups = {}
    for date, groups in warm.items():
        lifts = []
        for mv, rows in groups.items():
            rows = sorted(rows, key=lambda x: x["step_index"])
            lifts.append({"lift": rows[0]["lift"], "movement": mv,
                          "steps": [{"pct": round(num(x["pct"]) * 100, 1),
                                     "label": x["pct_label"], "kg": num(x["kg"]), "reps": int(x["reps"])}
                                    for x in rows]})
        warmups[date] = lifts
    actual_test_dates = test_dates(workouts)
    doc = {
        "schemaVersion": "RPL-Raw-v1",
        "meta": {
            "planId": "rpl-raw-%s" % start.isoformat(),
            "name": "Roast Raw cycle %s" % start.isoformat(),
            "startDate": start.isoformat(),
            "endDate": (start + datetime.timedelta(days=total_weeks * 7 - 1)).isoformat(),
            "weeks": total_weeks,
            "sessions": len({(x["week"], x["day"]) for x in workouts}),
            "auxSets": sum(x["sets"] for x in workouts if x["bucket"] == "accessory"),
            "cycleTonnageKg": round(sum(x["tonnageKg"] for x in workouts), 1),
            "tonnageBasis": "prescribed loads rounded to 0.5 kg (main) / 2.5 kg (variation)",
            "profile": prof, "anchors": anchors,
            "goals": copy.deepcopy(plan.get("Goals", {}).get("entries", [])),
            "guardrails": copy.deepcopy(plan.get("Guardrails", {})),
        },
        "blocks": blocks,
        "weeks": weeks,
        "days": [days[k] for k in sorted(days)],
        "workouts": workouts,
        "gpp": gpp,
        "warmups": warmups,
        "runPlan": [dict(copy.deepcopy(r), date=(start + datetime.timedelta(
            days=(int(r["week"]) - 1) * 7 + int(r.get("weekday_offset", days[r["day"]]["weekdayOffset"])))).isoformat())
                    for r in plan.get("RunPlan", [])],
        "testPlan": {"tests": sorted(actual_test_dates), "dates": actual_test_dates},
        "source": {"format": envelope["format"], "schemaVersion": envelope["schemaVersion"],
                   "exportedAt": envelope.get("exportedAt"), "app": copy.deepcopy(envelope.get("app")),
                   "sha256": source_sha256, "hashBasis": "input-bytes" if source_sha256 is not None else "unavailable",
                   "legacyEnvelope": copy.deepcopy(envelope),
                   "adapterMappings": [{"week": r["week"], "day": r["day"], "seq": r["seq"],
                                        "movement": r["movement"], "fromCategory": r["category"],
                                        "toCategory": legacy_movement(r)["category"],
                                        "reason": "Explicit v4 slot-category migration to reference taxonomy"}
                                       for r in plan["Workouts"] if r["category"] != legacy_movement(r)["category"]]},
    }
    try:
        return validate_plan(doc, file=file, lib=lib)
    except Reject as exc:
        errors.extend(exc.errors)
        raise Reject(errors) from exc


def main():
    try:
        lib, mm = build_movements()
        envelope, digest = read_json(SAMPLE)
        doc = adapt(envelope, lib, mm, source_sha256=digest, file=str(SAMPLE))
        ranges = build_ranges(mm)
        ids = [m["id"] for m in lib["movements"]]
        if len(ids) != len(set(ids)) or len(ids) != 261:
            raise Reject([issue(STATS / "muscle_map.json", "movements", "261 distinct source IDs", len(ids))])
        # Validate the entire batch before opening any generated output file.
        for name, payload in (("plan.json", doc), ("movements.json", lib), ("ranges.json", ranges)):
            with (OUT / name).open("w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except Reject as exc:
        print(json.dumps({"error": "IMPORT_REJECTED", "errors": exc.errors}, ensure_ascii=False), file=sys.stderr)
        return 1
    print("plan.json weeks=%d sessions=%d workouts=%d tonnage=%.1f kg" %
          (doc["meta"]["weeks"], doc["meta"]["sessions"], len(doc["workouts"]), doc["meta"]["cycleTonnageKg"]))
    print("movements.json entries=%d denied=%d" % (len(ids), sum(not m["plan_allowed"] for m in lib["movements"])))
    print("ranges.json leaf=%d" % len(ranges["leaf"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())