"""Movement classification, ported verbatim in rule order from legacy day_model.py.

Single source for bucket / lift / group. The statistics engine and the v4 adapter
both import this module; nothing else may restate these rules.
"""

MAIN_MOVES = {"High-bar Squat", "Mid-grip Bench", "Conventional Deadlift"}
SBD_VARIATION_MOVES = {"Low-bar Squat", "Wide-grip Bench", "Sumo Deadlift"}
POWER_CLEAN_NAMES = {"Power Clean", "Hang Power Clean", "Clean Pull", "Clean High Pull"}
SNATCH_NAMES = {"Snatch", "Power Snatch", "Hang Snatch", "Snatch Pull",
                "Snatch High Pull", "Muscle Snatch"}
NON_SBD_VARIATION_MOVES = {"Romanian Deadlift"}
VARIATION_MOVES = SBD_VARIATION_MOVES | NON_SBD_VARIATION_MOVES

MUSCLE_GROUPS = ["chest", "shoulders", "back", "legs", "arms", "abs"]

LIFT_OF_MOVEMENT = {
    "High-bar Squat": "S", "Low-bar Squat": "S",
    "Mid-grip Bench": "B", "Wide-grip Bench": "B",
    "Conventional Deadlift": "D", "Sumo Deadlift": "D",
}

GROUP_OF_MOVEMENT = {
    "High-bar Squat": "legs", "Low-bar Squat": "legs", "Wide-grip Bench": "chest",
    "Mid-grip Bench": "chest", "Conventional Deadlift": "back",
    "Sumo Deadlift": "legs", "Power Clean": "legs",
    "45-Degree Back Extension": "back", "Bent-Over Barbell Row": "back",
    "Cable Lateral Raise": "shoulders", "Face Pull": "shoulders",
    "Machine / Hanging Leg Raise": "abs", "OHP": "shoulders",
    "Pull-Up": "back", "Seated Row": "back", "Side Plank": "abs",
    "Weighted Dip": "chest", "Dip": "chest",
}

GROUP_ALIASES = {
    "chest": "chest", "pec": "chest", "pecs": "chest",
    "shoulder": "shoulders", "shoulders": "shoulders", "delts": "shoulders",
    "back": "back", "lats": "back", "upper back": "back", "upper_back": "back", "erectors": "back",
    "legs": "legs", "quads": "legs", "hamstrings": "legs", "glutes": "legs", "adductors": "legs", "calves": "legs",
    "arms": "arms", "biceps": "arms", "triceps": "arms", "forearms": "arms",
    "delts_ant": "shoulders", "delts_lat": "shoulders", "delts_post": "shoulders",
    "abs": "abs", "core": "abs",
}

PRIMARY_VARIATIONS = ["Power Clean", "Low-bar Squat", "Wide-grip Bench", "Sumo Deadlift"]
SECONDARY_VARIATIONS = ["OHP", "Weighted Pull-Up", "Weighted Dip", "Barbell Row", "Bent-Over Barbell Row"]


def row_category(row):
    return str((row or {}).get("category") or (row or {}).get("cat") or "").strip()


def is_power_clean(mv, row=None):
    name = str(mv or "").strip()
    if name in SNATCH_NAMES:
        return False
    return name in POWER_CLEAN_NAMES or row_category(row) == "D.Vari.Power"


def movement_role(mv, row=None):
    name = str(mv or "").strip()
    if not name:
        return None
    if name in MAIN_MOVES:
        return "main"
    if name in VARIATION_MOVES or is_power_clean(name, row):
        return "variation"
    return "accessory"


def movement_bucket(mv, row=None):
    name = str(mv or "").strip()
    if not name:
        return None
    if name in MAIN_MOVES:
        return "main"
    if name in SBD_VARIATION_MOVES or is_power_clean(name, row):
        return "sbdVar"
    if name in NON_SBD_VARIATION_MOVES:
        return "nonSbdVar"
    return "accessory"


def movement_lift(mv, row=None):
    name = str(mv or "").strip()
    raw = str((row or {}).get("lift") or "").strip().upper()
    if raw in ("S", "B", "D"):
        return raw
    if raw in ("SQ", "BP", "DL"):
        return {"SQ": "S", "BP": "B", "DL": "D"}[raw]
    if raw in ("SQUAT", "BENCH", "DEADLIFT"):
        return {"SQUAT": "S", "BENCH": "B", "DEADLIFT": "D"}[raw]
    if name in SNATCH_NAMES:
        return None
    if is_power_clean(name, row):
        return "D"
    if raw == "OTHER":
        return None
    return LIFT_OF_MOVEMENT.get(name)


def movement_group(mv, row=None):
    raw = str((row or {}).get("muscle_group") or (row or {}).get("muscleGroup") or "").strip().lower()
    group = GROUP_ALIASES.get(raw, raw if raw in MUSCLE_GROUPS else None)
    if group:
        return group
    return GROUP_OF_MOVEMENT.get(str(mv or "").strip())


def movement_level(mv):
    name = str(mv or "").strip()
    if name in MAIN_MOVES:
        return "main"
    if name in PRIMARY_VARIATIONS:
        return "primary_var"
    if name in SECONDARY_VARIATIONS:
        return "secondary_var"
    return "accessory"