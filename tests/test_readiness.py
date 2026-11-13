from copy import deepcopy
from datetime import date, timedelta
import unittest

from server.app.stats.readiness import score_readiness


def make_record(**values):
    record = {
        "recovery": None,
        "arousal": None,
        "nutrition": None,
        "hrv": None,
        "rhr": None,
        "sleep_score": None,
        "date": "2026-04-01",
        "session_time": None,
        "joint_pain": False,
        "note": "",
    }
    record.update(values)
    return record


def make_history(count=28):
    start = date(2026, 1, 1)
    return [
        make_record(
            date=(start + timedelta(days=index)).isoformat(),
            hrv=40 if index % 2 == 0 else 60,
            rhr=50 if index % 2 == 0 else 70,
        )
        for index in range(count)
    ]


class ReadinessTests(unittest.TestCase):
    def test_manual_subjective_and_sleep_arithmetic(self):
        result = score_readiness(make_record(recovery=1, arousal=4, nutrition=7, sleep_score=80), [])
        self.assertEqual(result["scores"], {
            "recovery": 0.0, "arousal": 50.0, "nutrition": 100.0,
            "sleep_score": 80.0, "hrv": None, "rhr": None,
        })
        self.assertEqual(result["validInputs"], 4)
        self.assertEqual(result["score"], 57.5)
        self.assertAlmostEqual(result["rec"], 1.0375)

    def test_every_subjective_level(self):
        expected = (0.0, 100 / 6, 100 / 3, 50.0, 200 / 3, 250 / 3, 100.0)
        for level, score in enumerate(expected, start=1):
            with self.subTest(level=level):
                result = score_readiness(make_record(recovery=level, arousal=level, nutrition=level), [])
                self.assertAlmostEqual(result["score"], score)

    def test_exactly_three_inputs_and_rec_endpoints(self):
        for level, score, rec in ((1, 0.0, 0.75), (4, 50.0, 1.0), (7, 100.0, 1.25)):
            with self.subTest(level=level):
                result = score_readiness(make_record(recovery=level, arousal=level, nutrition=level), [])
                self.assertEqual(result["validInputs"], 3)
                self.assertEqual(result["score"], score)
                self.assertEqual(result["rec"], rec)

    def test_nulls_and_fewer_than_three(self):
        for values, count in (({}, 0), ({"recovery": 1}, 1), ({"recovery": 1, "sleep_score": 0}, 2)):
            with self.subTest(values=values):
                result = score_readiness(make_record(**values), [])
                self.assertEqual(result["validInputs"], count)
                self.assertIsNone(result["score"])
                self.assertIsNone(result["rec"])
                self.assertTrue(any("three valid scored inputs" in text for text in result["advice"]))
        result = score_readiness(make_record(), [])
        self.assertTrue(all(value is None for value in result["scores"].values()))

    def test_known_population_baselines_and_normalization(self):
        result = score_readiness(make_record(hrv=60, rhr=50), make_history())
        for field, mean in (("hrv", 50.0), ("rhr", 60.0)):
            with self.subTest(field=field):
                baseline = result["baseline"][field]
                self.assertEqual(baseline["count"], 28)
                self.assertEqual(baseline["requiredDays"], 28)
                self.assertEqual(baseline["mean"], mean)
                self.assertEqual(baseline["sigma"], 10.0)
                self.assertEqual(baseline["status"], "ready")
                self.assertEqual(baseline["dates"][0], "2026-01-01")
                self.assertEqual(baseline["dates"][-1], "2026-01-28")
        self.assertEqual(result["scores"]["hrv"], 75.0)
        self.assertEqual(result["scores"]["rhr"], 75.0)
        self.assertEqual(result["validInputs"], 2)
        self.assertIsNone(result["score"])
        self.assertIsNone(result["rec"])

    def test_all_six_inputs_have_equal_weight(self):
        result = score_readiness(
            make_record(recovery=4, arousal=4, nutrition=4, sleep_score=50, hrv=60, rhr=50),
            make_history(),
        )
        self.assertEqual(result["validInputs"], 6)
        self.assertAlmostEqual(result["score"], 58.333333333333336)
        self.assertAlmostEqual(result["rec"], 1.0416666666666667)

    def test_zero_sleep_is_valid_alongside_physiological_inputs(self):
        result = score_readiness(make_record(sleep_score=0, hrv=50, rhr=60), make_history())
        self.assertEqual(result["validInputs"], 3)
        self.assertAlmostEqual(result["score"], 33.333333333333336)
        self.assertAlmostEqual(result["rec"], 0.9166666666666666)

    def test_rhr_is_inverted(self):
        for rhr, expected in ((50, 75.0), (60, 50.0), (70, 25.0)):
            with self.subTest(rhr=rhr):
                result = score_readiness(make_record(rhr=rhr), make_history())
                self.assertEqual(result["scores"]["rhr"], expected)

    def test_physiological_scores_are_clamped(self):
        for hrv, rhr, expected_hrv, expected_rhr in ((80, 90, 100.0, 0.0), (20, 30, 0.0, 100.0)):
            with self.subTest(hrv=hrv, rhr=rhr):
                result = score_readiness(make_record(hrv=hrv, rhr=rhr), make_history())
                self.assertEqual(result["scores"]["hrv"], expected_hrv)
                self.assertEqual(result["scores"]["rhr"], expected_rhr)

    def test_twenty_seven_days_cannot_score_or_use_population_defaults(self):
        result = score_readiness(make_record(hrv=60, rhr=50), make_history(27))
        for field in ("hrv", "rhr"):
            with self.subTest(field=field):
                self.assertEqual(result["baseline"][field]["count"], 27)
                self.assertIsNone(result["baseline"][field]["mean"])
                self.assertIsNone(result["baseline"][field]["sigma"])
                self.assertEqual(result["baseline"][field]["status"], "insufficient_history")
                self.assertIsNone(result["scores"][field])
        self.assertEqual(result["validInputs"], 0)

    def test_same_day_future_and_invalid_history_dates_are_excluded(self):
        history = make_history(27) + [
            make_record(date=day, hrv=60, rhr=50)
            for day in ("2026-04-01", "2026-04-02", "2099-01-01", "2026-02-30", "20260128", None)
        ]
        result = score_readiness(make_record(hrv=60, rhr=50), history)
        for field in ("hrv", "rhr"):
            self.assertEqual(result["baseline"][field]["count"], 27)
            self.assertIsNone(result["scores"][field])
        clean = score_readiness(make_record(hrv=60, rhr=50), make_history())
        contaminated = score_readiness(make_record(hrv=60, rhr=50), make_history() + history[27:])
        self.assertEqual(clean, contaminated)

    def test_invalid_reference_date_is_rejected(self):
        for value in (None, "2026-02-30", "20260401", "2026-4-1", "2026-04-01T12:00:00"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "date: expected a valid YYYY-MM-DD date"):
                    score_readiness(make_record(date=value), make_history())

    def test_duplicate_dates_do_not_inflate_baseline(self):
        repeated = [make_record(date="2026-01-01", hrv=40 if index % 2 else 60, rhr=50) for index in range(28)]
        result = score_readiness(make_record(hrv=60, rhr=50), repeated)
        for field in ("hrv", "rhr"):
            self.assertEqual(result["baseline"][field]["count"], 1)
            self.assertIsNone(result["scores"][field])

    def test_last_valid_duplicate_reading_wins_per_field(self):
        history = [make_record(date="2026-01-01", hrv=999, rhr=999)] + make_history()
        history.append(make_record(date="2026-01-01", hrv=None, rhr=0))
        self.assertEqual(
            score_readiness(make_record(hrv=60, rhr=50), history),
            score_readiness(make_record(hrv=60, rhr=50), make_history()),
        )

    def test_latest_twenty_eight_valid_days_not_calendar_window(self):
        history = make_history()
        history.append(make_record(date="2025-12-31", hrv=999, rhr=999))
        history.append(make_record(date="2026-03-31", hrv=None, rhr=0))
        self.assertEqual(
            score_readiness(make_record(hrv=60, rhr=50), list(reversed(history))),
            score_readiness(make_record(hrv=60, rhr=50), make_history()),
        )

    def test_baseline_days_are_selected_independently_per_field(self):
        history = []
        start = date(2026, 1, 1)
        for index in range(28):
            history.append(make_record(
                date=(start + timedelta(days=index * 2)).isoformat(),
                hrv=40 if index % 2 == 0 else 60,
            ))
            history.append(make_record(
                date=(start + timedelta(days=index * 2 + 1)).isoformat(),
                rhr=50 if index % 2 == 0 else 70,
            ))
        result = score_readiness(make_record(hrv=60, rhr=50), history)
        self.assertEqual(result["scores"]["hrv"], 75.0)
        self.assertEqual(result["scores"]["rhr"], 75.0)
        self.assertEqual(result["baseline"]["hrv"]["dates"][-1], "2026-02-24")
        self.assertEqual(result["baseline"]["rhr"]["dates"][-1], "2026-02-25")

    def test_zero_variance_is_unscored(self):
        history = [dict(entry, hrv=50, rhr=60) for entry in make_history()]
        result = score_readiness(make_record(recovery=4, sleep_score=50, hrv=50, rhr=60), history)
        for field in ("hrv", "rhr"):
            self.assertEqual(result["baseline"][field]["sigma"], 0.0)
            self.assertEqual(result["baseline"][field]["status"], "zero_variance")
            self.assertIsNone(result["scores"][field])
        self.assertEqual(result["validInputs"], 2)
        self.assertIsNone(result["score"])
        self.assertIsNone(result["rec"])

    def test_missing_current_readings_remain_null_with_ready_baselines(self):
        result = score_readiness(make_record(), make_history())
        for field in ("hrv", "rhr"):
            self.assertEqual(result["baseline"][field]["status"], "ready")
            self.assertIsNone(result["scores"][field])
        self.assertEqual(result["validInputs"], 0)

    def test_invalid_values_are_not_coerced_into_scores(self):
        cases = {
            "recovery": (True, False, 0, 8, 4.0, "4", -1),
            "arousal": (True, 0, 8, 4.0, "4"),
            "nutrition": (False, 0, 8, 4.0, "4"),
            "sleep_score": (True, False, -1, 101, "50", float("nan"), float("inf")),
            "hrv": (True, False, 0, -1, "50", float("nan"), float("inf")),
            "rhr": (True, False, 0, -1, "60", float("nan"), float("inf")),
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    result = score_readiness(make_record(**{field: value}), make_history())
                    self.assertIsNone(result["scores"][field])
                    self.assertEqual(result["validInputs"], 0)

    def test_invalid_history_readings_do_not_complete_a_baseline(self):
        for value in (None, True, 0, -1, "60", float("nan"), float("inf")):
            with self.subTest(value=value):
                history = make_history(27) + [make_record(date="2026-01-28", hrv=value, rhr=value)]
                result = score_readiness(make_record(hrv=60, rhr=50), history)
                self.assertEqual(result["baseline"]["hrv"]["count"], 27)
                self.assertEqual(result["baseline"]["rhr"]["count"], 27)

    def test_experience_time_boundaries_and_afternoon_baseline(self):
        cases = (
            ("00:00", 0.0), ("04:59", 0.0), ("05:00", -3.0), ("08:59", -3.0),
            ("09:00", -1.5), ("11:59", -1.5), ("12:00", 0.0), ("13:59", 0.0),
            ("14:00", 0.0), ("16:59", 0.0), ("17:00", -1.0), ("20:59", -1.0),
            ("21:00", 0.0), ("23:59", 0.0), (None, 0.0),
        )
        for session_time, expected in cases:
            with self.subTest(session_time=session_time):
                result = score_readiness(make_record(recovery=4, arousal=4, nutrition=4, session_time=session_time), [])
                self.assertEqual(result["timeAdjustmentPct"], expected)
                self.assertEqual(result["timeBasis"], "experience")
                self.assertEqual(result["score"], 50.0)
                self.assertEqual(result["rec"], 1.0)

    def test_malformed_times_have_no_adjustment(self):
        for value in ("5:00", "24:00", "08:60", "08:59:00", " 05:00", True):
            with self.subTest(value=value):
                result = score_readiness(make_record(session_time=value), [])
                self.assertEqual(result["timeAdjustmentPct"], 0.0)

    def test_eight_weeks_of_readiness_are_not_performance_observations(self):
        history = [dict(entry, session_time="06:00", recovery=7, note="Personal best") for entry in make_history(56)]
        result = score_readiness(make_record(session_time="06:00"), history)
        self.assertEqual(result["timeBasis"], "experience")
        self.assertEqual(result["timeAdjustmentPct"], -3.0)
        advice = " ".join(result["advice"])
        self.assertIn("Insufficient matched observations", advice)
        self.assertIn("performance_index", advice)
        self.assertIn("eight weeks", advice)
        self.assertIn("personal time curve is not implemented", advice)

    def test_joint_pain_is_caution_only_and_inputs_are_unchanged(self):
        record = make_record(recovery=4, arousal=4, nutrition=4, joint_pain=True, note="Pain during squat")
        history = make_history()
        original = deepcopy((record, history))
        result = score_readiness(record, history)
        no_pain = score_readiness(dict(record, joint_pain=False), history)
        self.assertEqual((record, history), original)
        for field in ("scores", "validInputs", "score", "rec", "baseline", "timeAdjustmentPct", "timeBasis"):
            self.assertEqual(result[field], no_pain[field])
        self.assertTrue(any("Caution: joint pain" in text for text in result["advice"]))
        self.assertFalse(any("Caution: joint pain" in text for text in no_pain["advice"]))
        self.assertTrue(any("never change prescribed loads automatically" in text for text in result["advice"]))
        self.assertEqual(result, score_readiness(record, history))


if __name__ == "__main__":
    unittest.main()
