"""Import boundary regressions. Fixtures are read-only; no generation or network."""
import copy
import datetime as dt
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator, FormatChecker
from server.app.stats import classify as C
from server.app.stats.prescription import mround, parse_segments, row_load
from server.app.validation import Reject, validate_legacy, validate_plan
from server.tools import gen_data
from server.tools.synth_plan import build


class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib, cls.mm = gen_data.build_movements()
        cls.envelope, cls.digest = gen_data.read_json(gen_data.SAMPLE)
        cls.raw = gen_data.adapt(cls.envelope, cls.lib, cls.mm, source_sha256=cls.digest)

    def rejected(self, function, *args, **kwargs):
        with self.assertRaises(Reject) as caught:
            function(*args, **kwargs)
        errors = caught.exception.errors
        self.assertTrue(errors)
        for error in errors:
            self.assertTrue({"file", "week", "day", "movement", "field", "expected"} <= error.keys())
        return errors

    def legacy(self, doc):
        return gen_data.adapt(doc, self.lib, self.mm, file="malformed-v4.json")

    def raw_check(self, doc):
        return validate_plan(doc, file="malformed-raw.json", lib=self.lib)

    def test_schemas_are_draft202012(self):
        for name in ("RPL-Raw-v1.json", "RPL-Review-v1.json"):
            schema = json.loads((ROOT / "data/schema" / name).read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            Draft202012Validator.check_schema(schema)

    def test_sample_shape_and_source_preserved(self):
        self.assertEqual((13, 49, 265), (self.raw["meta"]["weeks"], self.raw["meta"]["sessions"], len(self.raw["workouts"])))
        self.assertEqual(self.raw["source"]["legacyEnvelope"], self.envelope)
        self.assertEqual(self.raw["source"]["sha256"], hashlib.sha256(gen_data.SAMPLE.read_bytes()).hexdigest())
        self.assertNotIn("legacyTonnageT", self.raw["meta"])
        self.assertIs(self.raw_check(self.raw), self.raw)

    def test_tonnage_matches_original_prescription_arithmetic(self):
        plan = self.envelope["plan"]
        profile = {r["field"]: r["value"] for r in plan["Profile"]}
        bw = {a["movement"] for a in plan["Anchors"]["entries"] if a["kind"] == "bodyweight_max"}
        amounts = []
        for row in plan["Workouts"]:
            value = row["load_kg"] if row["load_kg"] != "" else None
            pct = row["pct_1rm"] if row["pct_1rm"] != "" else None
            anchor_key = {"S.Main": "sq_1rm", "B.Main": "bp_1rm", "D.Main": "dl_1rm"}.get(row["category"])
            if value is None and pct is not None and anchor_key:
                value = mround(profile[anchor_key] * pct, 0.5)
            segments = parse_segments({"rxRaw": row["rx_text"], "load": value, "pct": pct,
                                       "sets": row["sets"], "reps": row["reps"], "notes": row["notes"],
                                       "bwAnchor": row["movement"] in bw,
                                       "bucket": C.movement_bucket(row["movement"], row)})
            role = C.movement_role(row["movement"], row)
            amounts.append(round(sum((row_load(s, role) or 0) * s["sets"] * s["reps"] for s in segments), 1))
        self.assertEqual(round(sum(amounts), 1), self.raw["meta"]["cycleTonnageKg"])
        self.assertGreater(self.raw["meta"]["cycleTonnageKg"], 0)

    def test_library_is_complete_and_exact_fold(self):
        entries = self.lib["movements"]
        self.assertEqual(len(entries), 261)
        self.assertEqual(len({r["id"] for r in entries}), 261)
        required = {"id", "name_en", "category", "lift", "role", "level", "pattern", "equipment",
                    "group", "coef16", "tier", "tags", "plan_allowed", "contraindications", "source"}
        for entry in entries:
            self.assertTrue(required <= entry.keys())
            self.assertEqual(entry["coef6"], self.mm["moves"][entry["id"]]["coef"])
            if entry["coef16"] is not None:
                self.assertEqual(set(entry["coef16"]), set(self.lib["leaf_order"]))
                for group, leaves in self.lib["group_leaves"].items():
                    self.assertEqual(entry["coef6"][group], max(entry["coef16"][leaf] for leaf in leaves))
        ids = {r["id"] for r in entries if r["name_en"] == "Low-bar Squat"}
        self.assertEqual(ids, {"S.Main|low-bar squat", "S.Vari.End|low-bar squat"})
        machine = next(r for r in entries if r["name_en"] == "Machine / Hanging Leg Raise")
        self.assertEqual(machine["equipment"], "unknown")
        self.assertNotEqual(machine["pattern"], "s")

    def test_absent_leaf_is_not_invented(self):
        source = copy.deepcopy(self.mm)
        key = "S.Main|high-bar squat"
        del source["moves"][key]["leaf"]
        with patch.object(gen_data, "read_json", return_value=(source, "0" * 64)):
            lib, _ = gen_data.build_movements()
        entry = next(r for r in lib["movements"] if r["id"] == key)
        self.assertIsNone(entry["coef16"])
        self.assertFalse(entry["plan_allowed"])
        self.assertTrue(entry["reason"])
        self.rejected(gen_data.adapt, self.envelope, lib, source)

    def test_missing_or_wrong_nonzero_leaf_reports_exact_field(self):
        for replacement in (None, 0.9, False):
            with self.subTest(value=replacement):
                source = copy.deepcopy(self.mm)
                leaf = source["moves"]["S.Main|high-bar squat"]["leaf"]
                if replacement is None:
                    del leaf["quads"]
                else:
                    leaf["quads"] = replacement
                with patch.object(gen_data, "read_json", return_value=(source, "0" * 64)):
                    errors = self.rejected(gen_data.build_movements)
                self.assertTrue(any(e["field"].endswith(".leaf.quads") for e in errors))

    def test_reference_ranges_keep_scope_and_unknowns(self):
        ranges = gen_data.build_ranges(self.mm)
        self.assertEqual(ranges["leaf"]["upper_back"]["scope"], "group_back")
        self.assertEqual(ranges["leaf"]["lats"]["scope"], "group_back")
        self.assertIsNone(ranges["leaf"]["adductors"]["mev"])
        self.assertIsNone(ranges["leaf"]["adductors"]["mrv"])
        self.assertEqual(ranges["leaf"]["chest"]["sessions"], 2)

    def test_only_explicit_v4_category_migrations(self):
        mappings = self.raw["source"]["adapterMappings"]
        self.assertEqual({(r["fromCategory"], r["toCategory"]) for r in mappings},
                         {("S.Vari.Mid", "S.Vari.End"), ("B.Vari.Mid", "B.Vari.Start")})
        doc = copy.deepcopy(self.envelope)
        doc["plan"]["Workouts"][0]["category"] = "S.Unknown"
        self.rejected(self.legacy, doc)
        doc = copy.deepcopy(self.raw)
        row = next(r for r in doc["workouts"] if r["movement"] == "Low-bar Squat")
        row["category"] = "S.Vari.Mid"
        row["movementId"] = "S.Vari.Mid|low-bar squat"
        self.rejected(self.raw_check, doc)

    def test_v4_only_enters_through_adapter(self):
        self.rejected(self.raw_check, self.envelope)
        for value in (None, [], {}, {"format": "RPL-Plan", "schemaVersion": "RPL-Plan-v3"}):
            self.rejected(self.legacy, value)

    def test_required_tables_and_fields_fail_closed(self):
        for field in ("Profile", "Blocks", "Days", "Workouts"):
            doc = copy.deepcopy(self.envelope)
            del doc["plan"][field]
            self.rejected(self.legacy, doc)
        for field in ("week", "day", "seq", "row_idx", "movement", "category", "sets", "reps", "rx_text"):
            doc = copy.deepcopy(self.envelope)
            del doc["plan"]["Workouts"][0][field]
            self.rejected(self.legacy, doc)

    def test_fractional_bool_and_nonfinite_legacy_numbers(self):
        for field in ("week", "seq", "row_idx", "sets", "reps"):
            for value in (1.5, True, float("nan"), float("inf"), "3"):
                with self.subTest(field=field, value=value):
                    doc = copy.deepcopy(self.envelope)
                    doc["plan"]["Workouts"][0][field] = value
                    self.rejected(self.legacy, doc)
        for table, field in (("Blocks", "work_weeks"), ("Blocks", "deload_weeks"), ("Days", "weekday_offset")):
            doc = copy.deepcopy(self.envelope)
            doc["plan"][table][0][field] = 1.5
            self.rejected(self.legacy, doc)
        doc = copy.deepcopy(self.envelope)
        next(r for r in doc["plan"]["Profile"] if r["field"] == "plan_weeks")["value"] = 13.5
        self.rejected(self.legacy, doc)

    def test_negative_loads_and_counts_rejected_before_accessory_strip(self):
        for field in ("load_kg", "pct_1rm", "sets", "reps"):
            doc = copy.deepcopy(self.envelope)
            row = next(r for r in doc["plan"]["Workouts"] if r["movement"] == "Side Plank")
            row[field] = -1
            self.rejected(self.legacy, doc)

    def test_accessories_never_carry_loads_or_tonnage(self):
        doc = copy.deepcopy(self.envelope)
        row = next(r for r in doc["plan"]["Workouts"] if r["movement"] == "Side Plank")
        row["load_kg"], row["pct_1rm"] = 20, 0.5
        result = self.legacy(doc)
        for row in result["workouts"]:
            if row["role"] == "accessory":
                self.assertIsNone(row["loadKg"])
                self.assertIsNone(row["loadRaw"])
                self.assertIsNone(row["pct"])
                self.assertEqual(row["tonnageKg"], 0)
                self.assertTrue(all(s["load"] is None and s["pct"] is None for s in row["segments"]))

    def test_duplicate_identities_rejected(self):
        for table in ("Profile", "Blocks", "Days", "Workouts"):
            doc = copy.deepcopy(self.envelope)
            doc["plan"][table].append(copy.deepcopy(doc["plan"][table][0]))
            self.rejected(self.legacy, doc)
        for table in ("weeks", "days", "blocks", "workouts"):
            doc = copy.deepcopy(self.raw)
            doc[table].append(copy.deepcopy(doc[table][0]))
            self.rejected(self.raw_check, doc)

    def test_wrong_dates_and_unknown_day(self):
        for value in ("2026-02-30", "not-a-date", True):
            doc = copy.deepcopy(self.envelope)
            next(r for r in doc["plan"]["Profile"] if r["field"] == "start_date")["value"] = value
            self.rejected(self.legacy, doc)
        doc = copy.deepcopy(self.envelope)
        doc["plan"]["Workouts"][0]["date"] = "2026-11-17"
        self.rejected(self.legacy, doc)
        doc["plan"]["Workouts"][0]["day"] = "NOT-A-DAY"
        self.rejected(self.legacy, doc)
        doc = copy.deepcopy(self.raw)
        doc["workouts"][0]["date"] = "2026-11-17"
        self.rejected(self.raw_check, doc)
        doc = copy.deepcopy(self.raw)
        doc["weeks"][0]["dateEnd"] = "2026-11-30"
        self.rejected(self.raw_check, doc)

    def test_unknown_movement_and_exact_name(self):
        for name in ("Unknown Squat", "high-bar squat", " High-bar Squat"):
            doc = copy.deepcopy(self.envelope)
            doc["plan"]["Workouts"][0]["movement"] = name
            self.rejected(self.legacy, doc)
        doc = copy.deepcopy(self.raw)
        doc["workouts"][0]["movementId"] = "S.Main|low-bar squat"
        self.rejected(self.raw_check, doc)

    def test_raw_schema_and_semantic_mutations(self):
        mutations = [lambda d: d.update(schemaVersion="RPL-Plan-v4"),
                     lambda d: d.update(unexpected=True),
                     lambda d: d["workouts"][0].update(sets=1.5),
                     lambda d: d["workouts"][0].update(loadKg=-1),
                     lambda d: d["workouts"][0].update(week=True),
                     lambda d: d["workouts"][0].update(loadKg=float("nan")),
                     lambda d: d["workouts"][0]["segments"][0].update(sets=5),
                     lambda d: d["workouts"][0]["segments"][0].update(reps=2.5),
                     lambda d: d["workouts"][0].update(tonnageKg=0),
                     lambda d: d["meta"].update(sessions=0),
                     lambda d: d["weeks"][0].update(blockId="missing"),
                     lambda d: d["weeks"][0].update(sets=0),
                     lambda d: d["weeks"][0].pop("days"),
                     lambda d: d["runPlan"][0].update(date="2000-01-01")]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                doc = copy.deepcopy(self.raw)
                mutation(doc)
                self.rejected(self.raw_check, doc)

    def test_rejections_accumulate_context(self):
        doc = copy.deepcopy(self.envelope)
        doc["plan"]["Workouts"][0]["sets"] = 1.5
        doc["plan"]["Workouts"][1]["load_kg"] = -1
        errors = self.rejected(self.legacy, doc)
        self.assertTrue(any(e["field"].endswith(".sets") for e in errors))
        self.assertTrue(any(e["field"].endswith(".load_kg") for e in errors))
        self.assertTrue(all(e["file"] == "malformed-v4.json" for e in errors))
        self.assertTrue(any(e["week"] == 1 and e["day"] == "A" and e["movement"] for e in errors))

    def test_bad_prescription_does_not_fall_back_to_counts(self):
        for rx in ("unparsed", "1.5x3", "1x3.5", "1x3 @-10kg", "99x3"):
            doc = copy.deepcopy(self.envelope)
            doc["plan"]["Workouts"][0]["rx_text"] = rx
            self.rejected(self.legacy, doc)

    def test_test_date_is_evidenced_not_fabricated(self):
        self.assertEqual(self.raw["testPlan"], {"tests": ["sbd"], "dates": {"sbd": "2027-02-13"}})
        doc = copy.deepcopy(self.envelope)
        for row in doc["plan"]["Workouts"]:
            if row["mode"] == "Top.Test":
                row["mode"] = "Top.Single"
        self.assertEqual(self.legacy(doc)["testPlan"], {"tests": [], "dates": {}})

    def test_hash_of_dict_input_is_unknown_and_no_mutation(self):
        before = copy.deepcopy(self.envelope)
        doc = self.legacy(self.envelope)
        self.assertIsNone(doc["source"]["sha256"])
        self.assertEqual(doc["source"]["hashBasis"], "unavailable")
        doc["source"]["legacyEnvelope"]["plan"]["Workouts"][0]["notes"] = "changed copy"
        self.assertEqual(self.envelope, before)

    def test_synthesis_is_generic_and_calendar_consistent(self):
        for count in (1, 8, 17, 21):
            with self.subTest(count=count):
                doc = build(count)
                self.assertIs(validate_plan(doc, lib=self.lib), doc)
                self.assertEqual(doc["meta"]["weeks"], count)
                self.assertEqual([w["n"] for w in doc["weeks"]], list(range(1, count + 1)))
                self.assertEqual(sum(b["workWeeks"] + b["deloadWeeks"] for b in doc["blocks"]), count)
                self.assertEqual(doc["meta"]["sessions"], sum(w["sessions"] for w in doc["weeks"]))
                start = dt.date.fromisoformat(doc["meta"]["startDate"])
                self.assertEqual(doc["meta"]["endDate"], (start + dt.timedelta(days=count * 7 - 1)).isoformat())
                self.assertTrue(doc["source"]["synthetic"])
                self.assertEqual(doc["source"]["templateSha256"], self.digest)
                self.assertNotEqual(doc["source"]["sha256"], self.digest)
                self.assertEqual(doc["testPlan"], {"tests": [], "dates": {}})
                for key in ("gpp", "runPlan", "warmups"):
                    self.assertFalse(doc[key])
                source = doc["source"]["legacyEnvelope"]["plan"]
                self.assertTrue({"Telemetry", "TestPaths", "Warmups", "RunPlan", "GPP"}.isdisjoint(source))

    def test_synthesis_rejects_nonintegral_nonpositive_counts(self):
        for value in (0, -1, 8.5, True, "17", None, float("nan"), float("inf")):
            self.rejected(build, value)

    def test_review_has_independent_fields_and_null_actuals(self):
        schema = json.loads((ROOT / "data/schema/RPL-Review-v1.json").read_text(encoding="utf-8"))
        review = {field: None for field in schema["required"]}
        review.update(schema="RPL-Review-v1", exported_at="2026-11-16T00:00:00Z",
                      plan_id=self.raw["meta"]["planId"], plan=self.raw, logs=[])
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.assertEqual(list(validator.iter_errors(review)), [])
        self.assertIsNone(review["completion"])
        self.assertIsNone(review["e1rm"])
        review["completion"] = 120
        self.assertEqual(list(validator.iter_errors(review)), [])
        review["exported_at"] = "not-a-date"
        self.assertTrue(list(validator.iter_errors(review)))


if __name__ == "__main__":
    unittest.main()
