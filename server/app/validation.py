"""Fail-closed raw-plan and legacy-adapter boundaries; source payloads stay opaque."""
import datetime as dt
import json
import math
import re
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]

# Two fixture-era slot categories differ from the reference library taxonomy.
# This is an explicit v4 migration, never a Raw/name-only resolution fallback.
LEGACY_CATEGORY_MAPPINGS = {
    ("S.Vari.Mid", "Low-bar Squat"): "S.Vari.End",
    ("B.Vari.Mid", "Wide-grip Bench"): "B.Vari.Start",
}


def legacy_movement(row):
    """Normalize only documented v4 category migrations; preserve the source row."""
    result = dict(row)
    category, name = row.get("category"), row.get("movement")
    if isinstance(category, str) and isinstance(name, str):
        result["category"] = LEGACY_CATEGORY_MAPPINGS.get((category, name), category)
    return result


class Reject(ValueError):
    """An import rejection with machine-readable, contextual field errors."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("%d field error(s)" % len(errors))


def issue(file, field, expected, got=None, row=None, **context):
    row = row if isinstance(row, dict) else {}
    result = {"file": str(file), "week": row.get("week", row.get("n")),
              "day": row.get("day"), "movement": row.get("movement", row.get("movementId")),
              "field": field, "expected": expected, "got": got}
    result.update(context)

    def safe(value):
        if isinstance(value, float) and not math.isfinite(value):
            return repr(value)
        if isinstance(value, dict):
            return {str(k): safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [safe(v) for v in value]
        return value

    return safe(result)


def is_number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def is_integer(value):
    return is_number(value) and int(value) == value


def _finite(value, file, errors, path="", row=None):
    if isinstance(value, float) and not math.isfinite(value):
        errors.append(issue(file, path, "finite JSON number", repr(value), row))
    elif isinstance(value, dict):
        context = value if "week" in value or "movement" in value else row
        for k, v in value.items():
            _finite(v, file, errors, (path + "." + k).lstrip("."), context)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _finite(v, file, errors, "%s[%d]" % (path, i), row)


def _number(errors, file, row, field, value, minimum=0, maximum=None, integer=False, optional=False):
    if optional and (value is None or value == ""):
        return True
    valid = is_integer(value) if integer else is_number(value)
    valid = valid and value >= minimum and (maximum is None or value <= maximum)
    if not valid:
        expected = "%s >= %s" % ("integer" if integer else "finite number", minimum)
        if maximum is not None:
            expected += " and <= %s" % maximum
        errors.append(issue(file, field, expected, value, row))
    return valid


def _text(errors, file, row, field, value):
    valid = isinstance(value, str) and bool(value.strip()) and value == value.strip()
    if not valid:
        errors.append(issue(file, field, "non-empty, unpadded string", value, row))
    return valid


def _date(errors, file, row, field, value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError()
        return dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        errors.append(issue(file, field, "valid ISO calendar date YYYY-MM-DD", value, row))
        return None


def _library(lib, file, errors):
    if lib is None:
        with (ROOT / 'data/movements.json').open(encoding='utf-8') as stream:
            lib = json.load(stream)
    if not isinstance(lib, dict) or not isinstance(lib.get("movements"), list):
        errors.append(issue(file, "lib.movements", "movement array", lib))
        return {}, lib
    leaves = lib.get("leaf_order", [])
    if (not isinstance(leaves, list) or len(leaves) != 16
            or not all(isinstance(leaf, str) for leaf in leaves) or len(set(leaves)) != 16):
        errors.append(issue(file, "lib.leaf_order", "16 distinct leaf names", leaves))
        return {}, lib
    groups = lib.get("group_leaves")
    expected_groups = {"chest", "shoulders", "back", "legs", "arms", "abs"}
    if not isinstance(groups, dict) or set(groups) != expected_groups:
        errors.append(issue(file, "lib.group_leaves", "six source groups", groups))
        return {}, lib
    index = {}
    for i, entry in enumerate(lib["movements"]):
        path = "lib.movements[%d]" % i
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            errors.append(issue(file, path, "movement with string id", entry))
            continue
        key = entry["id"]
        if (not all(isinstance(entry.get(k), str) for k in ("category", "name_en", "level"))
                or any(k not in entry for k in ("lift", "group", "plan_allowed"))):
            errors.append(issue(file, path, "complete movement identity/classification", key))
            continue
        if key != entry["category"] + "|" + entry["name_en"].casefold():
            errors.append(issue(file, path + ".id", "category|casefold(name_en)", key))
        if key in index:
            errors.append(issue(file, path + ".id", "unique category-distinct ID", key))
        index[key] = entry
        if entry.get("plan_allowed") is not True:
            continue
        vector = entry.get("coef16")
        if not isinstance(vector, dict) or set(vector) != set(leaves):
            errors.append(issue(file, path + ".coef16", leaves, vector, movement=key))
            continue
        for leaf, value in vector.items():
            _number(errors, file, entry, path + ".coef16." + leaf, value, maximum=1)
        groups = lib.get("group_leaves", {})
        coef6 = entry.get("coef6")
        if not isinstance(coef6, dict) or set(coef6) != set(groups):
            errors.append(issue(file, path + ".coef6", "exact source group keys", coef6, movement=key))
        elif all(is_number(v) for v in vector.values()):
            for group, group_leaves in groups.items():
                if (not isinstance(group_leaves, list) or not group_leaves
                        or any(not isinstance(leaf, str) or leaf not in vector for leaf in group_leaves)):
                    errors.append(issue(file, "lib.group_leaves." + group, "known leaf names", group_leaves))
                    continue
                expected = max(vector[leaf] for leaf in group_leaves)
                if not is_number(coef6[group]) or coef6[group] != expected:
                    errors.append(issue(file, path + ".coef6." + group, expected, coef6[group], movement=key))
    return index, lib


def _movement(errors, file, row, path, index, raw=False):
    name, category = row.get("movement"), row.get("category")
    key = (category + "|" + name.casefold()) if isinstance(name, str) and isinstance(category, str) else None
    entry = index.get(key)
    if entry is None:
        errors.append(issue(file, path + ".movementId", "known exact category/name pair", key, row))
        return None
    for field, expected in (("category", entry["category"]), ("movement", entry["name_en"])):
        if row.get(field) != expected:
            errors.append(issue(file, path + "." + field, expected, row.get(field), row))
    if entry.get("plan_allowed") is not True or entry.get("coef16") is None:
        errors.append(issue(file, path + ".movementId", "plan_allowed movement with complete coef16", key, row))
    if raw:
        for field, expected in (("movementId", entry["id"]), ("nameEn", entry["name_en"])):
            if row.get(field) != expected:
                errors.append(issue(file, path + "." + field, expected, row.get(field), row))
    return entry


def block_weeks(blocks):
    """Yield derived (number, block, kind) without a fixed cycle length."""
    n = 0
    for block in blocks:
        test = block["cycleType"].lower() == "peak" or block["workMode"].lower().endswith(".test")
        for offset in range(int(block["workWeeks"] + block["deloadWeeks"])):
            n += 1
            kind = "test" if test else ("deload" if offset >= block["workWeeks"] else "training")
            yield n, block, kind


def test_dates(workouts):
    """Only full S/B/D test sessions qualify; unknown tests are not scheduled."""
    by_date = {}
    for row in workouts:
        if row["mode"].lower().endswith(".test") and row["bucket"] == "main":
            by_date.setdefault(row["date"], set()).add(row["lift"])
    dates = sorted(date for date, lifts in by_date.items() if {"S", "B", "D"} <= lifts)
    return {"sbd": dates[-1]} if dates else {}


def _rx_syntax(errors, file, row, path, text):
    if not isinstance(text, str):
        return
    stripped = re.sub(r"^(?:CAL|CALIBRATION)\b[\s.:·-]*", "", text.strip(), flags=re.I)
    if not re.match(r"^\d+\s*[×x]\s*\d+(?![\d.])", stripped):
        errors.append(issue(file, path, "prescription beginning with integral sets x reps", text, row))
    negative_kg = re.search(r"(?:@|~|约)\s*[-−]\s*\d+(?:\.\d+)?\s*kg", text, re.I)
    negative_pct = re.search(r"@\s*[-−]\s*\d+(?:\.\d+)?\s*%", text)
    backoff = ("top" in text.lower() or "顶组" in text) and "+" in text
    if negative_kg or (negative_pct and not backoff):
        errors.append(issue(file, path, "nonnegative absolute loads/percentages", text, row))


def validate_legacy(envelope, file="plan.json", lib=None):
    """Validate v4 before any coercion or arithmetic; return it or raise Reject."""
    errors = []
    _finite(envelope, file, errors)
    if not isinstance(envelope, dict):
        raise Reject([issue(file, "$", "RPL-Plan-v4 object", envelope)])
    for field, expected in (("format", "RPL-Plan"), ("schemaVersion", "RPL-Plan-v4")):
        if envelope.get(field) != expected:
            errors.append(issue(file, field, expected, envelope.get(field)))
    plan = envelope.get("plan")
    if not isinstance(plan, dict):
        raise Reject(errors + [issue(file, "plan", "object", plan)])
    tables = {}
    for name in ("Profile", "Blocks", "Days", "Workouts"):
        rows = plan.get(name)
        if not isinstance(rows, list) or not rows:
            errors.append(issue(file, "plan." + name, "non-empty array of objects", rows))
            tables[name] = []
        else:
            tables[name] = []
            for i, row in enumerate(rows):
                if not isinstance(row, dict):
                    errors.append(issue(file, "%s[%d]" % (name, i), "object", row))
                else:
                    tables[name].append(row)
    index, _ = _library(lib, file, errors)
    profile = {}
    for i, row in enumerate(tables["Profile"]):
        key = row.get("field")
        if not _text(errors, file, row, "Profile[%d].field" % i, key):
            continue
        if key in profile:
            errors.append(issue(file, "Profile." + key, "unique field", key))
        if "value" not in row:
            errors.append(issue(file, "Profile." + key, "value present", None))
        profile[key] = row.get("value")
    start = _date(errors, file, {}, "Profile.start_date", profile.get("start_date"))
    valid_count = _number(errors, file, {}, "Profile.plan_weeks", profile.get("plan_weeks"), minimum=1, integer=True)
    for field in ("sq_1rm", "bp_1rm", "dl_1rm"):
        _number(errors, file, {}, "Profile." + field, profile.get(field))
    for field, value in profile.items():
        if (field.endswith(("_kg", "_1rm", "_cm")) or field in
                ("age", "init_sq", "init_bp", "init_dl", "target_sq", "target_bp", "target_dl")):
            _number(errors, file, {}, "Profile." + field, value, integer=(field == "age"))
    total = 0
    block_ids = set()
    for i, row in enumerate(tables["Blocks"]):
        path = "Blocks[%d]" % i
        for field in ("block_id", "cycle_type", "name_en", "work_mode", "deload_mode"):
            _text(errors, file, row, path + "." + field, row.get(field))
        key = row.get("block_id")
        if isinstance(key, str):
            if key in block_ids:
                errors.append(issue(file, path + ".block_id", "unique block ID", key))
            block_ids.add(key)
        work = _number(errors, file, row, path + ".work_weeks", row.get("work_weeks"), integer=True)
        rest = _number(errors, file, row, path + ".deload_weeks", row.get("deload_weeks"), integer=True)
        if work and rest:
            span = int(row["work_weeks"] + row["deload_weeks"])
            total += span
            if span == 0:
                errors.append(issue(file, path, "positive block span", span))
        for field in ("base_rpe", "rpe_step", "deload_rpe"):
            _number(errors, file, row, path + "." + field, row.get(field), maximum=10, optional=True)
    if valid_count and profile["plan_weeks"] != total:
        errors.append(issue(file, "Profile.plan_weeks", total, profile["plan_weeks"]))
    if start and total > ((dt.date.max - start).days + 1) // 7:
        errors.append(issue(file, "Profile.plan_weeks", "cycle fitting ISO calendar", total))
        start = None
    days, offsets = {}, set()
    for i, row in enumerate(tables["Days"]):
        path = "Days[%d]" % i
        for field in ("day_id", "label", "title_en"):
            _text(errors, file, row, path + "." + field, row.get(field))
        key = row.get("day_id")
        off_ok = _number(errors, file, row, path + ".weekday_offset", row.get("weekday_offset"), maximum=6, integer=True)
        if isinstance(key, str):
            if key in days:
                errors.append(issue(file, path + ".day_id", "unique day ID", key))
            if off_ok:
                offset = int(row["weekday_offset"])
                if offset in offsets:
                    errors.append(issue(file, path + ".weekday_offset", "unique session weekday", offset))
                offsets.add(offset)
                days[key] = offset
        if "focus_tags" in row and not isinstance(row["focus_tags"], str):
            errors.append(issue(file, path + ".focus_tags", "comma-separated string", row["focus_tags"]))

    def calendar(row, path, require_date=False, own_offset=False):
        valid_week = _number(errors, file, row, path + ".week", row.get("week"), minimum=1, maximum=total, integer=True)
        day = row.get("day")
        known = isinstance(day, str) and day in days
        if not known:
            errors.append(issue(file, path + ".day", sorted(days), day, row))
        off = days.get(day) if isinstance(day, str) else None
        if own_offset and "weekday_offset" in row:
            if _number(errors, file, row, path + ".weekday_offset", row["weekday_offset"], maximum=6, integer=True):
                off = int(row["weekday_offset"])
        if "date" in row or require_date:
            actual = _date(errors, file, row, path + ".date", row.get("date"))
            if actual and start and valid_week and known and off is not None:
                expected = start + dt.timedelta(days=(int(row["week"]) - 1) * 7 + off)
                if actual != expected:
                    errors.append(issue(file, path + ".date", expected.isoformat(), row["date"], row))
        return valid_week and known

    identities = set()
    for i, row in enumerate(tables["Workouts"]):
        path = "Workouts[%d]" % i
        cal_ok = calendar(row, path)
        seq_ok = _number(errors, file, row, path + ".seq", row.get("seq"), minimum=1, integer=True)
        for field in ("row_idx", "sets", "reps"):
            _number(errors, file, row, path + "." + field, row.get(field), integer=True)
        for field in ("mode", "category", "movement", "rx_text"):
            _text(errors, file, row, path + "." + field, row.get(field))
        for field, maximum in (("load_kg", None), ("pct_1rm", 1.5), ("target_rpe", 10),
                               ("actual_rpe", 10), ("done_sets", None), ("actual_reps", None)):
            _number(errors, file, row, path + "." + field, row.get(field), maximum=maximum,
                    integer=field in ("done_sets", "actual_reps"), optional=True)
        if "notes" in row and not isinstance(row["notes"], str):
            errors.append(issue(file, path + ".notes", "string", row["notes"], row))
        _movement(errors, file, legacy_movement(row), path, index)
        _rx_syntax(errors, file, row, path + ".rx_text", row.get("rx_text"))
        if cal_ok and seq_ok:
            identity = (row["week"], row["day"], row["seq"])
            if identity in identities:
                errors.append(issue(file, path + ".seq", "unique (week, day, seq)", list(identity), row))
            identities.add(identity)

    # Optional tables remain intact in source. Validate the schedules/numbers we consume.
    for table in ("GPP", "RunPlan", "Telemetry", "Gear", "Level"):
        if table not in plan:
            continue
        if not isinstance(plan[table], list):
            errors.append(issue(file, table, "array of objects", plan[table]))
            continue
        seen = set()
        for i, row in enumerate(plan[table]):
            path = "%s[%d]" % (table, i)
            if not isinstance(row, dict):
                errors.append(issue(file, path, "object", row))
                continue
            if table in ("RunPlan", "Telemetry"):
                cal_ok = calendar(row, path, own_offset=table == "RunPlan")
                if cal_ok:
                    identity = (row["week"], row["day"])
                    if identity in seen:
                        errors.append(issue(file, path, "unique (week, day)", list(identity), row))
                    seen.add(identity)
            elif table == "GPP":
                _number(errors, file, row, path + ".week", row.get("week"), minimum=1, maximum=total, integer=True)
                _number(errors, file, row, path + ".item_idx", row.get("item_idx"), integer=True)
            for field in ("load_kg", "target_value", "duration_min", "target_sec", "reps", "target_rpe"):
                if field in row:
                    _number(errors, file, row, path + "." + field, row[field], integer=field == "reps",
                            maximum=10 if field == "target_rpe" else None, optional=True)
    for table, member in (("Anchors", "entries"), ("Goals", "entries"), ("Warmups", "sets")):
        if table not in plan:
            continue
        container = plan[table]
        if not isinstance(container, dict) or not isinstance(container.get(member), list):
            errors.append(issue(file, table + "." + member, "array in object", container))
            continue
        seen = set()
        for i, row in enumerate(container[member]):
            path = "%s.%s[%d]" % (table, member, i)
            if not isinstance(row, dict):
                errors.append(issue(file, path, "object", row))
                continue
            if table == "Warmups":
                calendar(row, path, require_date=True)
                for field in ("movement", "lift", "pct_label"):
                    _text(errors, file, row, path + "." + field, row.get(field))
                for field in ("step_index", "reps", "kg", "pct"):
                    _number(errors, file, row, path + "." + field, row.get(field),
                            integer=field in ("step_index", "reps"), maximum=1.5 if field == "pct" else None)
            else:
                key = row.get("id")
                if _text(errors, file, row, path + ".id", key):
                    if key in seen:
                        errors.append(issue(file, path + ".id", "unique ID", key))
                    seen.add(key)
                if table == "Anchors":
                    for field in ("movement", "kind", "unit"):
                        _text(errors, file, row, path + "." + field, row.get(field))
                    _number(errors, file, row, path + ".value", row.get("value"), integer=row.get("kind") == "bodyweight_max")
    if "Guardrails" in plan and not isinstance(plan["Guardrails"], dict):
        errors.append(issue(file, "Guardrails", "object", plan["Guardrails"]))
    if errors:
        raise Reject(errors)
    return envelope


def validate_plan(doc, file="plan.json", lib=None):
    """Validate only RPL-Raw-v1 with JSON Schema and exact semantic checks."""
    errors = []
    _finite(doc, file, errors)
    with (ROOT / "data/schema/RPL-Raw-v1.json").open(encoding="utf-8") as stream:
        schema = json.load(stream)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in validator.iter_errors(doc):
        path = list(error.absolute_path)
        row = doc
        for part in path:
            if isinstance(row, dict) and ("week" in row or "movement" in row or "n" in row):
                break
            try:
                row = row[part]
            except (KeyError, IndexError, TypeError):
                break
        field = ".".join(str(p) for p in path) or "$"
        errors.append(issue(file, field, error.message, error.instance, row))
    if errors:
        raise Reject(errors)
    if "prescription" in doc:
        from server.app.stats.variations import recalculate
        version = doc["prescription"]
        base = version["basePlan"]
        if "prescription" in base:
            raise Reject([issue(file, "prescription.basePlan", "original non-nested prescription", "nested version")])
        validate_plan(base, file=file + ":original", lib=lib)
        try:
            expected = recalculate(base, version["references"])
        except ValueError as exc:
            raise Reject([issue(file, "prescription.references", str(exc), version["references"])])
        def compare(expected_value, actual_value, path, context=None):
            if isinstance(expected_value, dict) and isinstance(actual_value, dict):
                context = actual_value if "movement" in actual_value or "n" in actual_value else context
                for key in sorted(expected_value.keys() | actual_value.keys()):
                    if key not in expected_value or key not in actual_value:
                        errors.append(issue(file, path + "." + key, "exact source field presence", "missing or added", context))
                    else:
                        compare(expected_value[key], actual_value[key], path + "." + key, context)
            elif isinstance(expected_value, list) and isinstance(actual_value, list):
                if len(expected_value) != len(actual_value):
                    errors.append(issue(file, path + ".length", len(expected_value), len(actual_value), context))
                for index, (before, after) in enumerate(zip(expected_value, actual_value)):
                    compare(before, after, path + "." + str(index), context)
            elif expected_value != actual_value:
                errors.append(issue(file, path, expected_value, actual_value, context))
        compare(expected, doc, "$")
        if errors:
            raise Reject(errors)
        return doc
    index, _ = _library(lib, file, errors)
    from server.app.stats import classify as C
    from server.app.stats.prescription import parse_segments, row_load

    def equal(path, expected, got, row=None):
        if expected != got:
            errors.append(issue(file, path, expected, got, row))

    meta = doc["meta"]
    start = dt.date.fromisoformat(meta["startDate"])
    total = sum(b["workWeeks"] + b["deloadWeeks"] for b in doc["blocks"])
    if total > ((dt.date.max - start).days + 1) // 7:
        raise Reject(errors + [issue(file, "meta.weeks", "cycle fitting ISO calendar", total)])
    equal("meta.weeks", total, meta["weeks"])
    equal("meta.endDate", (start + dt.timedelta(days=total * 7 - 1)).isoformat(), meta["endDate"])
    equal("weeks.length", total, len(doc["weeks"]))
    equal("weeks.n", list(range(1, int(total) + 1)), [w["n"] for w in doc["weeks"]])
    for field, expected in (("start_date", meta["startDate"]), ("plan_weeks", meta["weeks"])):
        if field in meta["profile"]:
            equal("meta.profile." + field, expected, meta["profile"][field])
    for field in ("sq_1rm", "bp_1rm", "dl_1rm"):
        _number(errors, file, {}, "meta.profile." + field, meta["profile"].get(field))
    for field, value in meta["profile"].items():
        if field == "plan_weeks":
            _number(errors, file, {}, "meta.profile." + field, value, minimum=1, integer=True)
        elif field.endswith(("_kg", "_1rm", "_cm")) or field in ("age", "init_sq", "init_bp", "init_dl", "target_sq", "target_bp", "target_dl"):
            _number(errors, file, {}, "meta.profile." + field, value, integer=field == "age")
    for key, anchor in meta["anchors"].items():
        if not isinstance(anchor, dict):
            errors.append(issue(file, "meta.anchors." + key, "anchor object", anchor))
        else:
            _number(errors, file, {}, "meta.anchors." + key + ".value", anchor.get("value"), integer=anchor.get("kind") == "bodyweight_max")
    for key in ("id",):
        ids = [b[key] for b in doc["blocks"]]
        if len(set(ids)) != len(ids):
            errors.append(issue(file, "blocks.id", "unique block IDs", ids))
    for b in doc["blocks"]:
        if b["workWeeks"] + b["deloadWeeks"] <= 0:
            errors.append(issue(file, "blocks." + b["id"], "positive block span", b))
    days = {d["id"]: d for d in doc["days"]}
    equal("days.id", len(doc["days"]), len(days))
    equal("days.weekdayOffset", len(days), len({d["weekdayOffset"] for d in doc["days"]}))
    seen, by_week = set(), {}
    for i, row in enumerate(doc["workouts"]):
        path = "workouts.%d" % i
        if "systemLoad" in row:
            errors.append(issue(file, path + ".systemLoad", "field only in a versioned prescription", row["systemLoad"], row))
        identity = (row["week"], row["day"], row["seq"])
        if identity in seen:
            errors.append(issue(file, path + ".seq", "unique (week, day, seq)", list(identity), row))
        seen.add(identity)
        by_week.setdefault(row["week"], []).append(row)
        if not 1 <= row["week"] <= total:
            errors.append(issue(file, path + ".week", "1..%d" % total, row["week"], row))
        elif row["day"] not in days:
            errors.append(issue(file, path + ".day", sorted(days), row["day"], row))
        else:
            date = start + dt.timedelta(days=(row["week"] - 1) * 7 + days[row["day"]]["weekdayOffset"])
            equal(path + ".date", date.isoformat(), row["date"], row)
        entry = _movement(errors, file, row, path, index, raw=True)
        # Classification is name/category based, never accepted from a forged row.lift.
        expected_role = C.movement_role(row["movement"], {"category": row["category"]})
        equal(path + ".role", expected_role, row["role"], row)
        equal(path + ".bucket", C.movement_bucket(row["movement"], {"category": row["category"]}), row["bucket"], row)
        if entry:
            equal(path + ".lift", entry["lift"], row["lift"], row)
            equal(path + ".level", entry["level"], row["level"], row)
            equal(path + ".group", entry["group"], row["group"], row)
        segments = row["segments"]
        equal(path + ".sets", sum(s["sets"] for s in segments), row["sets"], row)
        equal(path + ".reps", segments[0]["reps"], row["reps"], row)
        _rx_syntax(errors, file, row, path + ".rxRaw", row["rxRaw"])
        if expected_role == "accessory":
            for field in ("loadKg", "loadRaw", "pct"):
                equal(path + "." + field, None, row[field], row)
            for j, segment in enumerate(segments):
                for field in ("load", "pct"):
                    equal(path + ".segments.%d.%s" % (j, field), None, segment[field], row)
        bw = any(isinstance(a, dict) and a.get("kind") == "bodyweight_max" and a.get("movement") == row["movement"]
                 for a in meta["anchors"].values())
        try:
            parsed = parse_segments({"rxRaw": row["rxRaw"], "load": row["loadKg"], "pct": row["pct"],
                                     "sets": row["sets"], "reps": row["reps"], "notes": row["notes"],
                                     "bwAnchor": bw, "bucket": row["bucket"]})
            if expected_role == "accessory":
                for segment in parsed:
                    segment["load"] = segment["pct"] = None
            equal(path + ".segments", parsed, segments, row)
        except (ValueError, TypeError, OverflowError) as exc:
            errors.append(issue(file, path + ".rxRaw", "parseable prescription", str(exc), row))
        try:
            tons = round(sum((row_load(s, expected_role) or 0) * s["sets"] * s["reps"] for s in segments), 1)
            if not is_number(tons):
                raise ValueError("non-finite tonnage")
            equal(path + ".tonnageKg", tons, row["tonnageKg"], row)
        except (ValueError, OverflowError) as exc:
            errors.append(issue(file, path + ".tonnageKg", "finite computable tonnage", str(exc), row))
    for week, (n, block, kind) in zip(doc["weeks"], block_weeks(doc["blocks"])):
        path = "weeks.%d" % (n - 1)
        rows = by_week.get(n, [])
        mains = [r for r in rows if r["bucket"] == "main" and r["pct"] is not None]
        ws = start + dt.timedelta(days=(n - 1) * 7)
        expected = {
            "blockId": block["id"], "blockName": block["nameEn"], "kind": kind,
            "dateStart": ws.isoformat(), "dateEnd": (ws + dt.timedelta(days=6)).isoformat(),
            "days": sorted({r["day"] for r in rows}), "sessions": len({r["day"] for r in rows}),
            "sets": sum(r["sets"] for r in rows), "tonnageKg": round(sum(r["tonnageKg"] for r in rows), 1),
            "mainTonnageKg": round(sum(r["tonnageKg"] for r in rows if r["bucket"] == "main"), 1),
            "topPct": round(max(r["pct"] for r in mains) * 100, 1) if mains else None,
            "topPctByLift": {lift: round(max(r["pct"] for r in mains if r["lift"] == lift) * 100, 1)
                             if any(r["lift"] == lift for r in mains) else None for lift in ("S", "B", "D")}}
        for field, value in expected.items():
            equal(path + "." + field, value, week[field], week)
    equal("meta.sessions", len({(r["week"], r["day"]) for r in doc["workouts"]}), meta["sessions"])
    equal("meta.auxSets", sum(r["sets"] for r in doc["workouts"] if r["bucket"] == "accessory"), meta["auxSets"])
    equal("meta.cycleTonnageKg", round(sum(r["tonnageKg"] for r in doc["workouts"]), 1), meta["cycleTonnageKg"])
    if "testPlan" in doc:
        dates = test_dates(doc["workouts"])
        plan = doc["testPlan"]
        # SBD keeps the evidenced date and must never be invented. The extra groups
        # (tier-1, tier-2, 5 km) are checked against that same date instead of being
        # forced to equal it, and their items must stay inside the declared groups.
        equal("testPlan.dates.sbd", dates.get("sbd"), plan["dates"].get("sbd"))
        extra = sorted(set(plan["dates"]) - {"sbd"})
        for group in extra:
            equal("testPlan.dates." + group, dates.get("sbd"), plan["dates"][group])
        equal("testPlan.tests", sorted(set(dates) | set(extra)), plan["tests"])
        items = plan.get("items") or []
        ids = [item["id"] for item in items]
        if len(ids) != len(set(ids)):
            errors.append(issue(file, "testPlan.items", "unique ids", ids, items))
        for i, item in enumerate(items):
            if item["group"] == "fivekm" and item["kind"] != "run":
                errors.append(issue(file, "testPlan.items.%d.kind" % i, "run for the 5 km item", item["kind"], item))
            if item["group"] in ("tier1", "tier2") and item["kind"] == "run":
                errors.append(issue(file, "testPlan.items.%d.kind" % i, "a lifting item", item["kind"], item))
            if item["group"] not in extra:
                errors.append(issue(file, "testPlan.items.%d.group" % i, extra or ["no extra test group"], item["group"], item))
    for table, identity_field in (("gpp", "item_idx"), ("runPlan", "day")):
        identities = set()
        for i, row in enumerate(doc.get(table, [])):
            path = "%s.%d" % (table, i)
            identity = (row["week"], row[identity_field])
            if identity in identities:
                errors.append(issue(file, path, "unique schedule identity", list(identity), row))
            identities.add(identity)
            in_range = 1 <= row["week"] <= total
            if not in_range:
                errors.append(issue(file, path + ".week", "1..%d" % total, row["week"], row))
            if table == "runPlan":
                if row["day"] not in days:
                    errors.append(issue(file, path + ".day", sorted(days), row["day"], row))
                elif in_range:
                    offset = row.get("weekday_offset", days[row["day"]]["weekdayOffset"])
                    expected = start + dt.timedelta(days=(row["week"] - 1) * 7 + offset)
                    equal(path + ".date", expected.isoformat(), row.get("date"), row)
    end = dt.date.fromisoformat(meta["endDate"])
    allowed_names = {entry["name_en"] for entry in index.values() if entry.get("plan_allowed") is True}
    for date, groups in doc.get("warmups", {}).items():
        if not start <= dt.date.fromisoformat(date) <= end:
            errors.append(issue(file, "warmups." + date, "date inside cycle", date))
        seen_names = set()
        for group in groups:
            name = group["movement"]
            if name not in allowed_names or name in seen_names:
                errors.append(issue(file, "warmups." + date + ".movement", "known unique movement", name))
            seen_names.add(name)
    source = doc["source"]
    if source.get("hashBasis") == "input-bytes" and source["sha256"] is None:
        errors.append(issue(file, "source.sha256", "actual input-byte SHA-256", None))
    if errors:
        raise Reject(errors)
    return doc
