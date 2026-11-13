"""Independent pure expectations for the approved eight-variation policy.

No database, API, generation, or legacy fixture replacement. The main layer
must add parse_segments' systemLoad guard before running bodyweight cases.
"""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.stats import engine, variations as V
from server.app.stats.prescription import parse_segments


# Expectations are explicit, not calculated by the implementation under test.
APPROVED = (
    ('Low-bar Squat', 'S.Vari.End', 'S', .90, 120, False, 'primary_var'),
    ('Wide-grip Bench', 'B.Vari.Start', 'B', .90, 90, False, 'primary_var'),
    ('Sumo Deadlift', 'D.Vari.Power', 'D', .85, 120, False, 'primary_var'),
    ('Power Clean', 'D.Vari.Power', 'D', .15, 70, False, 'secondary_var'),
    ('OHP', 'B.Delts', 'B', .35, 60, False, 'secondary_var'),
    ('Pull-Up', 'D.Lats', 'D', .10, 100, True, 'secondary_var'),
    ('Weighted Dip', 'B.Pecs', 'B', .60, 105, True, 'secondary_var'),
    ('Bent-Over Barbell Row', 'SBD.UpperBack', 'D', .25, 90, False, 'secondary_var'),
)


def legacy_row(name, category, seq, *, pct=None, load=None, rpe=9, technique=False,
               notes='Keep the original coaching cue.'):
    primary = name in ('Low-bar Squat', 'Wide-grip Bench', 'Sumo Deadlift', 'Power Clean')
    lift = {'Low-bar Squat': 'S', 'Wide-grip Bench': 'B',
            'Sumo Deadlift': 'D', 'Power Clean': 'D'}.get(name)
    level = ('primary_var' if primary else 'accessory' if name in ('Pull-Up', 'Dip')
             else 'secondary_var')
    label = 'TECH' if technique else 'BW' if name == 'Pull-Up' else 'WORK'
    rx = f'3×3' + (f' @ {pct * 100:g}%' if pct is not None else '')
    rx += (f' @ {load:g} kg' if load is not None else '')
    rx += ' technique' if technique else ''
    return {
        'week': 1, 'day': 'A', 'date': '2026-02-02', 'seq': seq, 'rowIndex': seq,
        'mode': 'Legacy', 'category': category, 'movement': name, 'nameEn': name,
        'movementId': f'{category}|{name.casefold()}', 'lift': lift,
        'group': 'back', 'role': 'variation' if primary else 'accessory',
        'bucket': 'sbdVar' if primary else 'accessory', 'level': level,
        'pct': pct, 'loadKg': load, 'loadRaw': load, 'sets': 3, 'reps': 3,
        'targetRpe': rpe, 'notes': notes, 'rxRaw': rx, 'rxEn': rx,
        'segments': [{'kind': 'bw' if label == 'BW' else 'work', 'label': label,
                      'sets': 3, 'reps': 3, 'unit': '', 'load': load,
                      'pct': pct * 100 if pct is not None else None,
                      'delta': None, 'amrap': False, 'text': rx}],
        'tonnageKg': load * 9 if load is not None else 0, 'coefStatus': 'exact',
    }


def base_plan():
    rows = [legacy_row(name, category, index + 1) for index, (name, category, *_) in enumerate(APPROVED)]
    rows[0] = legacy_row('Low-bar Squat', 'S.Vari.End', 1, pct=.75, load=100)
    rows[1] = legacy_row('Wide-grip Bench', 'B.Vari.Start', 2, pct=.8, load=70)
    rows[2] = legacy_row('Sumo Deadlift', 'D.Vari.Power', 3, pct=.8, load=100)
    rows[3] = legacy_row('Power Clean', 'D.Vari.Power', 4, pct=.76, load=40, rpe=5.5, technique=True)
    rows[5]['notes'] = 'Bodyweight only; retain this historical cue.'
    main = {
        'week': 1, 'day': 'A', 'date': '2026-02-02', 'seq': 9,
        'movement': 'High-bar Squat', 'movementId': 'S.Main|high-bar squat',
        'category': 'S.Main', 'role': 'main', 'bucket': 'main', 'lift': 'S', 'level': 'main',
        'sets': 2, 'reps': 5, 'targetRpe': 8, 'pct': .8, 'loadRaw': 100, 'loadKg': 100,
        'rxRaw': '2×5 @ 80% @ 100 kg', 'rxEn': '2×5 @ 80% @ 100 kg',
        'notes': 'Do not rewrite this main.', 'tonnageKg': 1000,
        'segments': [{'sets': 2, 'reps': 5, 'load': 100, 'pct': 80, 'label': 'WORK', 'unit': ''}],
    }
    accessory = {
        'week': 1, 'day': 'A', 'date': '2026-02-02', 'seq': 10,
        'movement': 'Face Pull', 'movementId': 'B.Delts|face pull', 'category': 'B.Delts',
        'role': 'accessory', 'bucket': 'accessory', 'lift': None, 'level': 'accessory',
        'sets': 4, 'reps': 12, 'targetRpe': 7, 'pct': None, 'loadRaw': None, 'loadKg': None,
        'rxRaw': '4×12', 'rxEn': '4×12', 'notes': 'Do not rewrite this accessory.', 'tonnageKg': 0,
        'segments': [{'sets': 4, 'reps': 12, 'load': None, 'pct': None, 'label': 'WORK', 'unit': ''}],
    }
    rows.extend((main, accessory))
    return {
        'schemaVersion': 'RPL-Raw-v1',
        'meta': {'startDate': '2026-02-02', 'endDate': '2026-02-08', 'weeks': 1,
                 'sessions': 1, 'auxSets': 16, 'cycleTonnageKg': 3790,
                 'tonnageBasis': 'Original legacy basis',
                 'anchors': {'pull': {'kind': 'bodyweight_max', 'movement': 'Pull-Up', 'value': 10}}},
        'weeks': [{'n': 1, 'sets': 30, 'tonnageKg': 3790, 'mainTonnageKg': 1000,
                   'dateStart': '2026-02-02', 'dateEnd': '2026-02-08',
                   'topPct': 80, 'topPctByLift': {'S': 80, 'B': None, 'D': None}}],
        'workouts': rows,
        'source': {'legacyEnvelope': {'originalRx': ['Keep every original prescription.']}},
    }


class VariationTests(unittest.TestCase):
    def test_policy_and_all_eight_families(self):
        self.assertEqual(V.POLICY, 'eight-variations-v1')
        for name, category, lift, transfer, reference, system, level in APPROVED:
            row = {'movement': name, 'category': category}
            with self.subTest(name=name):
                self.assertEqual(V.family(row), {'lift': lift, 'transfer': transfer,
                                                 'default': reference, 'system': system})
                self.assertEqual(V.classification(row, V.POLICY), ('variation', 'sbdVar', lift, level))
        self.assertEqual(V.family({'movement': 'Weighted Pull-Up'}), V.family({'movement': 'Pull-Up'}))
        self.assertEqual(V.family({'movement': 'Dip'}), V.family({'movement': 'Weighted Dip'}))
        for name in ('Hang Power Clean', 'Barbell Row', 'Romanian Deadlift', 'Front Squat', 'Face Pull'):
            self.assertIsNone(V.family({'movement': name}))
        descriptor = V.family({'movement': 'OHP'})
        descriptor['default'] = 1
        self.assertEqual(V.family({'movement': 'OHP'})['default'], 60)

    def test_legacy_classification_is_not_silently_promoted(self):
        cases = (
            ('OHP', 'B.Delts', ('accessory', 'accessory', None, 'secondary_var')),
            ('Pull-Up', 'D.Lats', ('accessory', 'accessory', None, 'accessory')),
            ('Weighted Dip', 'B.Pecs', ('accessory', 'accessory', None, 'secondary_var')),
            ('Power Clean', 'D.Vari.Power', ('variation', 'sbdVar', 'D', 'primary_var')),
            ('Front Squat', 'S.Vari.Mid', ('accessory', 'accessory', None, 'accessory')),
            ('Romanian Deadlift', 'D.Vari.Mid', ('variation', 'nonSbdVar', None, 'accessory')),
        )
        for name, category, expected in cases:
            row = {'movement': name, 'category': category, 'lift': 'B', 'level': 'main'}
            with self.subTest(name=name):
                self.assertEqual(V.classification(row), expected)
                self.assertEqual(V.classification(row, 'unrecognized-policy'), expected)
        self.assertEqual(V.classification({'movement': 'Front Squat', 'category': 'S.Vari.Mid'}, V.POLICY),
                         ('accessory', 'accessory', None, 'accessory'))

    def test_catalogue_uses_only_allowed_existing_ids_and_keeps_aliases(self):
        groups = V.catalogue()
        self.assertEqual(list(groups), ['S', 'B', 'D'])
        entries = {entry['id']: entry for group in groups.values() for entry in group}
        source_ids = {entry['id'] for entry in engine.library()['movements'] if entry['plan_allowed']}
        self.assertLessEqual(entries.keys(), source_ids)
        self.assertEqual(set(V.defaults()), set(entries))
        expected = {
            'S.Main|low-bar squat': 120, 'S.Vari.End|low-bar squat': 120,
            'D.Main|sumo deadlift': 120, 'D.Vari.Power|sumo deadlift': 120,
            'D.Lats|pull-up': 100, 'D.Lats|weighted pull-up': 100,
            'B.Pecs|weighted dip': 105, 'B.Triceps|weighted dip': 105, 'B.Triceps|dip': 105,
            'S.Vari.Mid|front squat': None, 'D.Vari.Mid|romanian deadlift': None,
        }
        for identity, reference in expected.items():
            self.assertEqual(V.defaults()[identity], reference, identity)
        self.assertEqual(entries['SBD.UpperBack|bent-over barbell row']['lift'], 'D')
        self.assertEqual(entries['S.Vari.Mid|front squat']['lift'], 'S')
        self.assertIsNone(entries['S.Vari.Mid|front squat']['transfer'])
        self.assertNotIn('S.Main|high-bar squat', entries)
        for name, category, lift, transfer, reference, system, _ in APPROVED:
            self.assertEqual(entries[f'{category}|{name.casefold()}'], {
                'id': f'{category}|{name.casefold()}', 'name': name, 'lift': lift,
                'system': system, 'default': reference, 'transfer': transfer})
        refs = V.defaults()
        refs['S.Main|low-bar squat'] = 125
        refs['D.Lats|weighted pull-up'] = 110
        self.assertEqual(refs['S.Vari.End|low-bar squat'], 120)
        self.assertEqual(refs['D.Lats|pull-up'], 100)
        self.assertEqual(V.defaults()['S.Main|low-bar squat'], 120)

    def test_catalogue_lift_priority_and_exclusion_are_explicit(self):
        lib = {'movements': [
            {'id': 'existing-family', 'name_en': 'OHP', 'category': 'X.Other',
             'lift': 'S', 'level': 'accessory', 'plan_allowed': True},
            {'id': 'existing-library', 'name_en': 'Other Press', 'category': 'S.Vari.Start',
             'lift': 'B', 'level': 'accessory', 'plan_allowed': True},
            {'id': 'existing-category', 'name_en': 'Other Pull', 'category': 'D.Vari.Start',
             'lift': None, 'level': 'accessory', 'plan_allowed': True},
            {'id': 'undecidable', 'name_en': 'Other', 'category': 'X.Vari.Start',
             'lift': None, 'level': 'primary_var', 'plan_allowed': True},
            {'id': 'disallowed', 'name_en': 'Pull-Up', 'category': 'D.Lats',
             'lift': None, 'level': 'accessory', 'plan_allowed': False},
            {'id': 'not-variation', 'name_en': 'Other Accessory', 'category': 'B.Delts',
             'lift': 'B', 'level': 'accessory', 'plan_allowed': True},
        ]}
        original = copy.deepcopy(lib)
        with patch.object(engine, 'library', return_value=lib):
            groups = V.catalogue()
            self.assertEqual(groups['S'], [])
            self.assertEqual([entry['id'] for entry in groups['B']], ['existing-family', 'existing-library'])
            self.assertEqual([entry['id'] for entry in groups['D']], ['existing-category'])
            self.assertEqual(V.defaults(), {'existing-family': 60, 'existing-library': None,
                                           'existing-category': None})
        self.assertEqual(lib, original)

    def test_reference_validation_reports_the_exact_key(self):
        refs = V.defaults()
        identity = 'D.Lats|pull-up'
        for value in (True, False, 0, -1, float('nan'), float('inf'), -float('inf'), '100'):
            invalid = dict(refs, **{identity: value})
            with self.subTest(value=value), self.assertRaises(ValueError) as caught:
                V.validate_references(invalid)
            self.assertEqual(str(caught.exception), identity)
        missing = dict(refs)
        del missing[identity]
        with self.assertRaises(ValueError) as caught:
            V.validate_references(missing)
        self.assertEqual(str(caught.exception), identity)
        unknown = dict(refs, **{'unknown|movement': 100})
        with self.assertRaises(ValueError) as caught:
            V.validate_references(unknown)
        self.assertEqual(str(caught.exception), 'unknown|movement')
        for value in (None, 100, 100.25):
            valid = dict(refs, **{identity: value})
            self.assertEqual(V.validate_references(valid), valid)
            self.assertIsNot(V.validate_references(valid), valid)

    def test_recalculation_preserves_raw_counts_inputs_and_history(self):
        plan, refs = base_plan(), V.defaults()
        saved_plan, saved_refs = copy.deepcopy(plan), copy.deepcopy(refs)
        library_before = copy.deepcopy(engine.library())
        after = V.recalculate(plan, refs)
        self.assertEqual(plan, saved_plan)
        self.assertEqual(refs, saved_refs)
        self.assertEqual(engine.library(), library_before)
        self.assertEqual(after['prescription']['basePlan'], saved_plan)
        self.assertIsNot(after['prescription']['basePlan'], plan)
        self.assertEqual(set(after) - set(plan), {'prescription'})
        self.assertEqual(set(after['prescription']), {'version', 'references', 'basePlan'})
        self.assertEqual(after['prescription']['version'], 'eight-variations-v1')
        self.assertEqual(after['prescription']['references'], refs)
        self.assertEqual(sum(row['sets'] for row in after['workouts']), 30)
        self.assertEqual(sum(row['sets'] for row in after['workouts'] if row['bucket'] == 'sbdVar'), 24)
        self.assertEqual(sum(row['sets'] for row in after['workouts'] if row['bucket'] == 'main'), 2)
        self.assertEqual(after['meta']['auxSets'], 4)
        self.assertEqual(after['meta']['cycleTonnageKg'], 6625)
        self.assertEqual(after['weeks'][0]['tonnageKg'], 6625)
        self.assertEqual(after['weeks'][0]['sets'], 30)
        self.assertEqual(after['weeks'][0]['mainTonnageKg'], 1000)
        self.assertEqual(after['weeks'][0]['topPct'], 80)
        self.assertEqual(after['weeks'][0]['topPctByLift'], {'S': 80, 'B': None, 'D': None})
        self.assertIn('bodyweight', after['meta']['tonnageBasis'])
        self.assertIn('total system', after['meta']['tonnageBasis'])
        self.assertEqual(after['workouts'][8:], plan['workouts'][8:])
        self.assertEqual(after['source'], plan['source'])
        for old, new in zip(plan['workouts'], after['workouts']):
            for field in ('week', 'day', 'date', 'seq', 'movementId', 'category', 'sets', 'reps', 'targetRpe', 'notes'):
                self.assertEqual(new[field], old[field], (new['movement'], field))
        self.assertEqual([row['loadKg'] for row in after['workouts'][:8]],
                         [90, 72.5, 95, 52.5, 52.5, 90, 92.5, 80])
        self.assertEqual([row['segments'][0]['pct'] for row in after['workouts'][:8]],
                         [75, 80, 80, 76, 89, 89, 89, 89])
        self.assertEqual([row['tonnageKg'] for row in after['workouts'][:8]],
                         [810, 652.5, 855, 472.5, 472.5, 810, 832.5, 720])
        after['prescription']['basePlan']['workouts'][0]['notes'] = 'Changed copy'
        self.assertEqual(plan, saved_plan)

    def test_arbitrary_week_totals_do_not_rewrite_calendar_or_top_percentage(self):
        plan = base_plan()
        second_week = copy.deepcopy(plan['weeks'][0])
        second_week.update(n=2, dateStart='2026-02-09', dateEnd='2026-02-15')
        plan['weeks'].append(second_week)
        extra_rows = copy.deepcopy(plan['workouts'])
        for row in extra_rows:
            row.update(week=2, date='2026-02-09')
        plan['workouts'].extend(extra_rows)
        plan['meta'].update(weeks=2, endDate='2026-02-15', sessions=2,
                            cycleTonnageKg=7580, auxSets=32)
        snapshot = copy.deepcopy(plan)
        after = V.recalculate(plan, V.defaults())
        self.assertEqual(plan, snapshot)
        self.assertEqual(sum(row['sets'] for row in after['workouts']), 60)
        self.assertEqual(after['meta']['cycleTonnageKg'], 13250)
        self.assertEqual(after['meta']['auxSets'], 8)
        self.assertEqual([week['tonnageKg'] for week in after['weeks']], [6625, 6625])
        self.assertEqual([week['topPct'] for week in after['weeks']], [80, 80])
        self.assertEqual(after['workouts'][-1]['date'], '2026-02-09')
        self.assertEqual(after['meta']['endDate'], '2026-02-15')

    def test_alias_rows_use_their_own_reference_and_never_rename_ids(self):
        plan, refs = base_plan(), V.defaults()
        aliases = [legacy_row('Low-bar Squat', 'S.Main', 11, pct=.75, load=100),
                   legacy_row('Weighted Pull-Up', 'D.Lats', 12),
                   legacy_row('Weighted Dip', 'B.Triceps', 13),
                   legacy_row('Dip', 'B.Triceps', 14)]
        plan['workouts'].extend(aliases)
        refs['S.Main|low-bar squat'] = 160
        refs['D.Lats|weighted pull-up'] = 110
        refs['B.Triceps|weighted dip'] = 120
        after = V.recalculate(plan, refs)
        self.assertEqual([row['loadKg'] for row in after['workouts'][10:]], [120, 97.5, 107.5, 92.5])
        self.assertEqual(after['workouts'][0]['loadKg'], 90)
        self.assertEqual(after['workouts'][5]['loadKg'], 90)
        self.assertEqual(after['workouts'][6]['loadKg'], 92.5)
        self.assertEqual([row['movementId'] for row in after['workouts'][10:]],
                         ['S.Main|low-bar squat', 'D.Lats|weighted pull-up',
                          'B.Triceps|weighted dip', 'B.Triceps|dip'])
        self.assertEqual([row['systemLoad'] for row in after['workouts'][10:]], [False, True, True, True])

    def test_power_clean_and_rts_ties_even_not_epley(self):
        after = V.recalculate(base_plan(), V.defaults())
        prescribed = after['workouts'][3]
        # An explicit 76% takes precedence at any RPE, including 3@5.5.
        self.assertEqual(prescribed['segments'][0]['pct'], 76)
        self.assertEqual(prescribed['loadRaw'], 53.2)
        self.assertEqual(prescribed['loadKg'], 52.5)
        self.assertEqual(prescribed['rxRaw'], '3×3 @ 76% @ 52.5 kg technique')
        self.assertEqual(prescribed['segments'][0]['label'], 'TECH')
        ohp = after['workouts'][4]
        self.assertEqual(ohp['pct'], .89)  # 3@9 -> index 4 -> 89.2 -> 89%, not 92.2.
        plan = base_plan()
        row = plan['workouts'][3]
        row['pct'] = row['segments'][0]['pct'] = None
        clean = V.recalculate(plan, V.defaults())['workouts'][3]
        # Without an explicit percent, 3@5.5 cannot be 76 under the given table:
        # 3 + (10 - 5.5) = 7.5 -> Python round = 8 -> 78.6 -> 79%.
        self.assertEqual(clean['segments'][0]['pct'], 79)
        self.assertEqual(clean['loadKg'], 55)
        self.assertEqual(clean['rxRaw'], '3×3 @ 79% @ 55 kg technique')
        row['targetRpe'] = 4.5
        clean = V.recalculate(plan, V.defaults())['workouts'][3]
        # 8.5 ties to 8 as well, rather than always rounding upward.
        self.assertEqual(clean['segments'][0]['pct'], 79)
        row['reps'] = row['segments'][0]['reps'] = 30
        row['targetRpe'] = 5.5
        self.assertEqual(V.recalculate(plan, V.defaults())['workouts'][3]['segments'][0]['pct'], 59)

    def test_explicit_segment_then_row_percentage_and_original_provenance(self):
        plan = base_plan()
        row = plan['workouts'][0]
        row['segments'][0]['pct'] = 76
        row['pct'] = .9
        row['targetRpe'] = None
        after = V.recalculate(plan, V.defaults())
        self.assertEqual(after['workouts'][0]['pct'], .76)
        self.assertEqual(after['workouts'][0]['loadRaw'], 91.2)
        self.assertEqual(after['workouts'][0]['loadKg'], 90)
        self.assertEqual(after['workouts'][0]['rxRaw'], '3×3 @ 76% @ 90 kg')
        preview = V.changes(plan, after)[0]
        self.assertEqual(preview, {
            'key': '1|A|1', 'movement': 'Low-bar Squat', 'date': '2026-02-02',
            'sets': 3, 'reps': 3, 'targetRpe': None, 'oldLoad': 100, 'newLoad': 90,
            'oldRx': row['rxRaw'], 'newRx': '3×3 @ 76% @ 90 kg',
            'basis': 'Prescribed percentage', 'reference': 120, 'percent': 76, 'system': False})
        row['segments'][0]['pct'] = None
        row['pct'] = .7625
        revised = V.recalculate(plan, V.defaults())['workouts'][0]
        self.assertEqual(revised['loadKg'], 92.5)
        self.assertEqual(revised['segments'][0]['pct'], 76.25)
        self.assertEqual(revised['pct'], .7625)

    def test_amrap_semantics_survive_recalculation_and_repeated_reference_changes(self):
        plan = base_plan()
        row = plan['workouts'][0]
        row['segments'][0]['amrap'] = True
        row['rxRaw'] += '+'
        row['rxEn'] += '+'
        revised = V.recalculate(plan, V.defaults())
        self.assertTrue(revised['workouts'][0]['segments'][0]['amrap'])
        self.assertEqual(revised['workouts'][0]['rxRaw'], '3×3 @ 75% @ 90 kg+')
        self.assertEqual(revised['workouts'][0]['reps'], 3)
        self.assertEqual(revised['prescription']['basePlan'], plan)
        refs = V.defaults()
        refs[row['movementId']] = 160
        second = V.recalculate(revised, refs)
        self.assertEqual(second['workouts'][0]['rxRaw'], '3×3 @ 75% @ 120 kg+')
        self.assertTrue(second['workouts'][0]['segments'][0]['amrap'])
        self.assertEqual(second['workouts'][0]['tonnageKg'], 1080)

    def test_repeated_policy_recalculation_always_uses_legacy_base(self):
        plan, refs = base_plan(), V.defaults()
        first = V.recalculate(plan, refs)
        saved_first = copy.deepcopy(first)
        self.assertEqual(V.recalculate(first, refs), first)
        updated = dict(refs, **{'B.Delts|ohp': 80})
        second = V.recalculate(first, updated)
        self.assertEqual(second['prescription']['basePlan'], plan)
        self.assertNotIn('prescription', second['prescription']['basePlan'])
        self.assertEqual(first, saved_first)
        self.assertEqual(second['workouts'][4]['loadKg'], 70)
        preview = V.changes(first, second)
        self.assertEqual(len(preview), 1)
        self.assertEqual(preview[0]['oldLoad'], 52.5)
        self.assertEqual(preview[0]['newLoad'], 70)
        self.assertEqual(preview[0]['percent'], 89)
        self.assertEqual(preview[0]['basis'], 'Legacy RTS reps/RPE estimate')
        self.assertEqual(V.changes(first, first), [])
        restored = V.changes(first, plan)
        self.assertTrue(restored)
        self.assertTrue(all(change['reference'] is None for change in restored))
        self.assertTrue(all(change['basis'] == 'Original legacy prescription' for change in restored))

    def test_missing_reference_rpe_and_unsupported_segments_reject_exact_row(self):
        refs = V.defaults()
        refs['B.Delts|ohp'] = None
        with self.assertRaises(ValueError) as caught:
            V.recalculate(base_plan(), refs)
        self.assertIn('1|A|5', str(caught.exception))
        self.assertIn('B.Delts|ohp', str(caught.exception))
        for fault in ('rpe', 'bool-rpe', 'infinite-rpe', 'multi', 'missing',
                      'bool-pct', 'zero-pct', 'invalid-row-pct', 'unknown-id'):
            plan = base_plan()
            row = plan['workouts'][4]
            if fault == 'rpe':
                row['targetRpe'] = None
            elif fault == 'bool-rpe':
                row['targetRpe'] = True
            elif fault == 'infinite-rpe':
                row['targetRpe'] = float('inf')
            elif fault == 'multi':
                row['segments'].append(copy.deepcopy(row['segments'][0]))
            elif fault == 'missing':
                row['segments'] = []
            elif fault == 'bool-pct':
                row['segments'][0]['pct'] = True
            elif fault == 'zero-pct':
                row['segments'][0]['pct'] = 0
            elif fault == 'invalid-row-pct':
                row['pct'] = -1
            else:
                row['movementId'] = 'unknown|ohp'
            snapshot = copy.deepcopy(plan)
            with self.subTest(fault=fault), self.assertRaises(ValueError) as caught:
                V.recalculate(plan, V.defaults())
            self.assertIn('1|A|5', str(caught.exception))
            self.assertEqual(plan, snapshot)
        for prior in ({'version': 'other', 'basePlan': base_plan()},
                      {'version': V.POLICY, 'basePlan': {'prescription': {}}}):
            plan = dict(base_plan(), prescription=prior)
            with self.assertRaises(ValueError):
                V.recalculate(plan, V.defaults())

    def test_system_flag_prevents_legacy_bodyweight_note_or_anchor_override(self):
        segment = parse_segments({
            'rxRaw': '3×3 @ 89% @ 90 kg', 'load': 90, 'pct': .89,
            'sets': 3, 'reps': 3, 'notes': 'Bodyweight only.', 'bwAnchor': True,
            'bucket': 'sbdVar', 'systemLoad': True,
        })[0]
        self.assertEqual((segment['label'], segment['load'], segment['pct']), ('WORK', 90, 89))
        pull = V.recalculate(base_plan(), V.defaults())['workouts'][5]
        self.assertTrue(pull['systemLoad'])
        self.assertEqual(pull['notes'], 'Bodyweight only; retain this historical cue.')
        self.assertEqual(pull['tonnageKg'], 810)
        self.assertEqual(pull['segments'][0]['label'], 'WORK')

    def test_bodyweight_same_day_closest_prior_assisted_and_weighted(self):
        metrics = [{'date': '2026-02-10', 'bodyweight': 95},
                   {'date': '2026-02-01', 'bodyweight': 80},
                   {'date': '2026-02-02', 'bodyweight': 85},
                   {'date': '2026-02-03', 'bodyweight': None}]
        snapshot = copy.deepcopy(metrics)
        self.assertEqual(V.system_load(82.5, '2026-02-02', metrics), {
            'total': 82.5, 'bodyweight': 85, 'bodyweightDate': '2026-02-02',
            'adjustment': -2.5, 'kind': 'assisted'})
        self.assertEqual(V.system_load(100, '2026-02-05', metrics), {
            'total': 100, 'bodyweight': 85, 'bodyweightDate': '2026-02-02',
            'adjustment': 15, 'kind': 'weighted'})
        self.assertEqual(V.system_load(85, '2026-02-02', metrics)['kind'], 'bodyweight')
        self.assertEqual(V.system_load(100, '2026-01-31', metrics), {
            'total': 100, 'bodyweight': None, 'bodyweightDate': None,
            'adjustment': None, 'kind': 'unknown'})
        self.assertEqual(V.system_load(100, '2026-02-02', [])['kind'], 'unknown')
        self.assertEqual(V.system_load(None, '2026-02-02', metrics)['kind'], 'unknown')
        self.assertEqual(metrics, snapshot)

    def test_equivalent_capacity_keeps_raw_sets_and_muscle_coefficients_independent(self):
        plan = base_plan()
        original = engine.row_volume(plan['workouts'][5])[0]
        revised = V.recalculate(plan, V.defaults())
        for index, (name, _, lift, transfer, _, _, _) in enumerate(APPROVED):
            row = revised['workouts'][index]
            volume, errors = engine.row_volume(row, policy=V.POLICY)
            with self.subTest(movement=name):
                self.assertEqual(errors, [])
                self.assertEqual(volume['sets'], 3)
                self.assertEqual(volume['roles']['sbdVar'], 3)
                self.assertEqual(volume['lifts'][lift]['var'], 3)
                self.assertAlmostEqual(volume['equivalent'][lift]['var'], 3 * transfer)
                baseline = engine.row_volume(plan['workouts'][index])[0]
                for field in ('groups', 'groupsWeighted', 'leaves', 'leavesWeighted',
                              'primaryWeighted', 'secondaryWeighted'):
                    self.assertEqual(volume[field], baseline[field])
        pull = engine.row_volume(revised['workouts'][5], {'sets': 2, 'reps': 3, 'load': 90}, V.POLICY)[0]
        self.assertEqual(pull['sets'], 2)
        self.assertEqual(pull['lifts']['D']['var'], 2)
        self.assertEqual(pull['equivalent']['D']['var'], .2)
        self.assertEqual(original['roles']['accessory'], 3)
        skipped = engine.row_volume(revised['workouts'][5], {'sets': 0, 'reps': 3, 'load': 90}, V.POLICY)[0]
        self.assertEqual(skipped['sets'], 0)
        self.assertEqual(skipped['equivalent']['D']['var'], 0)
        unknown = {'movement': 'Cluster Deadlift', 'category': 'D.Vari.Power', 'group': 'legs',
                   'sets': 4, 'tonnageKg': 1000}
        volume = engine.row_volume(unknown, policy=V.POLICY)[0]
        self.assertEqual(volume['lifts']['D']['var'], 4)
        self.assertEqual(volume['equivalent']['D'], {'main': 0, 'var': 0, 'unknown': 4})
        main = engine.row_volume(dict(plan['workouts'][8], group='legs'), policy=V.POLICY)[0]
        self.assertEqual(main['equivalent']['S'], {'main': 2, 'var': 0, 'unknown': 0})

    def test_digest_is_canonical_and_rejects_nonfinite_json(self):
        self.assertEqual(V.digest({}), '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a')
        self.assertEqual(V.digest({'b': 2, 'a': 1}), V.digest({'a': 1, 'b': 2}))
        self.assertEqual(V.digest({'name': '力量'}), hashlib.sha256(b'{"name":"\\u529b\\u91cf"}').hexdigest())
        self.assertNotEqual(V.digest({'a': 1}), V.digest({'a': 2}))
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.assertRaises(ValueError):
                V.digest({'a': value})


if __name__ == '__main__':
    unittest.main()
