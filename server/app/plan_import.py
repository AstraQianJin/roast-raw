import copy
import hashlib
import json
import math

from server.app.stats.engine import library
from server.app.validation import Reject, issue, validate_plan
from server.tools.gen_data import adapt


def parse_plan(plan_json: str, filename: str) -> dict:
    if not isinstance(plan_json, str):
        raise Reject([issue(filename, "$", "UTF-8 JSON text", type(plan_json).__name__)])
    try:
        original_bytes = plan_json.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise Reject([issue(filename, "$", "UTF-8 encodable JSON text", str(exc))]) from exc

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Reject([issue(filename, key, "unique JSON object key", key, result)])
            result[key] = value
        return result

    def reject_constant(value):
        raise Reject([issue(filename, "$", "finite JSON number", value)])

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            reject_constant(value)
        return number

    text = plan_json[1:] if plan_json.startswith("\ufeff") else plan_json
    try:
        doc = json.loads(text, object_pairs_hook=unique_object,
                         parse_constant=reject_constant, parse_float=finite_float)
    except Reject:
        raise
    except json.JSONDecodeError as exc:
        raise Reject([issue(filename, "$", "valid, complete JSON", str(exc),
                            line=exc.lineno, column=exc.colno)]) from exc
    except (ValueError, RecursionError) as exc:
        raise Reject([issue(filename, "$", "readable finite JSON within parser limits", str(exc))]) from exc

    if not isinstance(doc, dict):
        raise Reject([issue(filename, "$", "plan JSON object", doc)])
    version = doc.get("schemaVersion")
    if version == "RPL-Raw-v1":
        return validate_plan(doc, file=filename, lib=library())
    if version != "RPL-Plan-v4":
        raise Reject([issue(filename, "schemaVersion", "RPL-Raw-v1 or RPL-Plan-v4", version)])
    if doc.get("format") != "RPL-Plan":
        raise Reject([issue(filename, "format", "RPL-Plan", doc.get("format"))])

    # Hash the untouched input, including a BOM, not the parsed or reserialized plan.
    return adapt(doc, library(), None, source_sha256=hashlib.sha256(original_bytes).hexdigest(),
                 file=filename)


def summary(plan: dict) -> dict:
    meta = plan["meta"]
    return {
        "cycleId": meta["planId"],
        "name": meta["name"],
        "startDate": meta["startDate"],
        "endDate": meta["endDate"],
        "weeks": meta["weeks"],
        "sessions": meta["sessions"],
        "workouts": len(plan["workouts"]),
        "sets": sum(row["sets"] for row in plan["workouts"]),
        "tonnageKg": meta["cycleTonnageKg"],
        "profile": copy.deepcopy(meta["profile"]),
        "prescriptionPolicy": plan.get("prescription", {}).get("version", "legacy"),
        "testPlan": copy.deepcopy(plan.get("testPlan", {})),
    }
