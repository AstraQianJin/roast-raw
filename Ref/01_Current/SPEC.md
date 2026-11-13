# Roast Raw rebuild — legacy spec (authoritative)

Source: the deployed legacy plan board `http://49.233.196.202/plan/` plus its generator
`C:\Users\Astra\Desktop\Roast PowerLifting\mobile\docs\site\day_model.py`.
All rules below are extracted, not invented. The JSON fixtures in this folder are the
reference output for the same 13-week plan.

## 0. User decision (2026-11-13, final)

- Rebuild from scratch. The previous attempt (Roast Raw) was rejected: it looked close but
  dropped the statistics that made the old board good.
- Keep the strengths: plan → prescription → last-set log → capacity analysis → export.
- Remove the branches: accounts, cloud, AI, coach, equipment/supplement/venue libraries,
  tiers, plate math, mini/max density, `ex` theme, i18n, run module (cardio survives only
  as a GPP block).
- Two themes only: dark and light. English only. Root stays 4 folders + 4 files.
- Do not deploy, do not git init, do not touch the old project or the server.

## 1. Movement classification (exact, from day_model.py)

```
MAIN_MOVES        = {High-bar Squat, Mid-grip Bench, Conventional Deadlift}
SBD_VARIATION     = {Low-bar Squat, Wide-grip Bench, Sumo Deadlift}
POWER_CLEAN_NAMES = {Power Clean, Hang Power Clean, Clean Pull, Clean High Pull}
SNATCH_NAMES      = {Snatch, Power Snatch, Hang Snatch, Snatch Pull, Snatch High Pull, Muscle Snatch}
NON_SBD_VARIATION = {Romanian Deadlift}
```

Bucket order:
1. name in MAIN_MOVES → `main`
2. name in SBD_VARIATION → `sbdVar`
3. `_is_power_clean(name, cat)`: name in POWER_CLEAN_NAMES or cat === "D.Vari.Power",
   and name not in SNATCH_NAMES → `sbdVar`
4. name in NON_SBD_VARIATION → `nonSbdVar`
5. else → `accessory`

Lift code:
- High-bar Squat / Low-bar Squat → S
- Mid-grip Bench / Wide-grip Bench → B
- Conventional Deadlift / Sumo Deadlift → D
- power-clean family → D
- else none.

Legacy output for W1: total sets 71; S main/var 10/3; B 9/4; D 8/6;
roles main/sbdVar/accessory = 27/13/31.

## 2. 16-leaf fractional sets

Movement → 16 coefficients come from `coefficient_matrix.csv` (already in
`mobile/docs/research/fractional_sets/coefficient_matrix.csv`, 261 rows, columns:
chest, delts_ant, delts_lat, delts_post, triceps, upper_back, lats, erectors,
quads, hamstrings, glutes, adductors, biceps, forearms, core, calves).

For each movement and week:
- `weighted[k] += sets × coef[k]`
- `direct[k] += sets` only when the leaf is *primary* for that movement.

Primary rule (`leaf_tiers`):
```
mx = max(coef over 16 leaves)
primary if coef[k] >= mx * 0.8
secondary if coef[k] >= mx * 0.3
direct counts primary only (tier 1); secondary is lit but not counted
```

## 3. Six muscle groups (capacity board)

Groups: `chest, shoulders, back, legs, arms, abs`.

- Each movement folds to one group via the row field `muscle_group` / fallback table:
  - legs: High-bar Squat, Low-bar Squat, Sumo Deadlift, Power Clean, Leg Press, RDL, etc.
  - chest: Mid-grip Bench, Wide-grip Bench, Weighted Dip, Dip
  - back: Conventional Deadlift, 45-Degree Back Extension, Bent-Over Barbell Row, Pull-Up, Seated Row
  - shoulders: Cable Lateral Raise, Face Pull, OHP
  - abs: Machine / Hanging Leg Raise, Side Plank
- `group direct += sets` for that one group (each set counts once).
- `group weighted += sets × groupCoef`, where groupCoef is the 16-leaf vector folded to
  6 groups by `max` across its sub-muscles (legacy `GROUP_COEF`), not by summing.

## 4. Landmarks (RP practice framework, direct sets, 2 sessions/week)

| leaf | MEV | MRV |
|---|---|---|
| chest | 6 | 20 |
| delts_ant | 0 | 12 |
| delts_lat | 8 | 25 |
| delts_post | 6 | 18 |
| triceps | 6 | 16 |
| upper_back | 10 | 20 (group/back scope) |
| lats | 10 | 20 (group/back scope) |
| erectors | 10 | 20 (group/back scope) |
| quads | 8 | 18 |
| hamstrings | 4 | 12 |
| glutes | 0 | 12 |
| adductors | — | — (no standalone source) |
| biceps | 8 | 20 |
| forearms | 8 | 15 |
| core | 0 | 25 |
| calves | 8 | 16 |

SBD ranges (capacity board):
- S: MEV 8 / MRV 18, weekly range 10–16
- B: MEV 8 / MRV 20, weekly range 10–18
- D: MEV 6 / MRV 17, weekly range 10–15

Six-group weekly ranges (total sets, from the legacy board):
- chest 10–20, shoulders 10–18, back 16–32, legs 14–30, arms 10–20, abs 10–20.

## 5. Board views (must all exist)

1. **Lift** — S / B / D rows. Each: main sets, variant sets, full-cycle bar, `MEV x / MRV y`,
   verdict `RANGE lo–hi` (or below/above). Clicking a row selects it and shows a 13-week bar
   chart of main vs variant plus a detail panel.
2. **Muscle** — six groups. Weighted vs direct numbers, range, verdict.
3. **Role** — MAIN / SBD VAR / ACCESSORY set totals.
4. **Week** — total sets per week; deload and test marked; click a week to inspect.
5. **16 leaves** — 16 rows with weighted and direct per week, range and verdict;
   heatmap or bar list. Adductors shows "no separate source". Back three labelled "group scope".
6. **Cardio equivalent minutes** — Z2/hard minutes × WHO 1:2, with the note that basketball
   is not scored. (Optional in 0.01 but part of the old board.)

Cycle header stats: 13 weeks, 49 sessions, cycle tonnage (e.g. 139.6 t), aux sets (317).

## 6. Weekly reference output (fixtures)

`capData.json`:
```
weeks 13, deload [4,8,12], test 13
total sets per week: [71,72,73,40,72,72,73,39,59,59,54,31,17]  totalAll 732
S m: [10,11,11,4,11,11,12,4,10,10,8,4,6]
S v: [3,3,3,2,3,3,3,2,2,2,2,0,0]
B m: [9,9,10,4,9,9,9,4,7,7,5,4,6]
B v: [4,4,4,2,4,4,4,2,3,3,3,0,0]
D m: [8,8,9,4,8,8,9,4,6,6,5,5,5]
D v: [6,6,6,4,6,6,6,4,5,5,5,2,0]
roles MAIN: [27,28,30,12,28,28,30,12,23,23,18,13,17]
roles SBD VAR: [13,13,13,8,13,13,13,8,10,10,10,2,0]
roles ACCESSORY: [31,31,30,20,31,31,30,19,26,26,26,16,0]
```

`mmData.json` weeks 1–13:
- `w` = weighted per leaf (16 values), `d` = direct per leaf.
- Week 1 w: [14.8,8.2,3.9,3.2,7.8,23.2,11.2,16.8,22.6,12.4,22.2,8.0,6.2,11.0,16.1,1.5]
- Week 1 d: [13,3,2,4,3,13,12,10,19,11,14,0,0,0,5,0]
- Reality check: our preview pipeline reproduced weighted within 0.1 and total/lift B exactly;
  it failed S/D main-vs-var because it used category instead of the movement maps, and it
  failed direct because it used `primary_muscle` instead of the 0.8×max tier rule.

## 7. Design tokens (from the old board)

Dark:
```
--bg:#07090D; --panel:#0E121A; --panel2:#121722;
--line:rgba(255,255,255,.11); --line2:rgba(255,255,255,.06);
--ink:#F2F5F9; --tx2:#8B97A8; --tx3:#7A869C;
--acc:#FF7A73; --accSoft:rgba(217,48,42,.12); --accLine:rgba(217,48,42,.35);
--main:#FF6B64; --mainStrong:#FF3B30; --var:#7FB0FF; --accCol:#4ADE80;
```
Light:
```
--bg:#F4F7FA; --panel:#FFFFFF; --panel2:#F8FAFC;
--line:rgba(15,23,42,.16); --line2:rgba(15,23,42,.13);
--ink:#0F1720; --tx2:#5F6B7A; --tx3:#5B6672;
--acc:#A01B14; --accSoft:rgba(179,38,30,.07); --accLine:rgba(179,38,30,.30);
--main:#B3261E; --mainStrong:#8C1A12; --var:#1D5BC4; --accCol:#1E7A45;
```
Type: Georgia serif for wordmark and section headings; sans for body; mono with
`tabular-nums` for every number. Radius 2–10px (the old board is squarer than the app).
Week circles, day rail, chips, 44px targets, section rules.

## 8. Product rules kept from the user

- Record only the last working set per exercise: load × reps @ RPE + actual set count.
- Load is the largest number; sets × reps and target RPE are secondary.
- Intensity bands: <75 neutral, 75–85 amber, 85–95 red, 95+ ink.
- Main red, variation blue, accessory green.
- Gear is a collapsed one-line strip driven by the day's top %1RM.
- GPP is three blocks: cardio, recovery, weak point.
- Readiness is the 6-dimension JTS check-in; recovery multiplier scales MRV.
- JSON schema `roast-raw/v1`, full + week slices, derived read-only.
- Share cards: day / week / cycle / test day, 1080 px.
- No account, no cloud, no AI, no coach.

## 9. Acceptance

- Engine reproduces `capData` and `mmData` for all 13 weeks: total/lift/role exact,
  weighted within 0.1, direct exact.
- All board views exist and are interactive.
- No horizontal overflow at 320/360/390/412, both themes.
- Single-file Release app + self-contained launch page, no network.
- Root exactly: Build/ Release/ Data/ Ref/ + .gitgone CHANGELOG.md README.md AGENT.md.
