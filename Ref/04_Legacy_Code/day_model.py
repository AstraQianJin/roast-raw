#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Day model for the ExDark static site.

Pure data: dates, sessions, resolved loads/percentages and gear flags.
No HTML, no file writes. The renderer (render_day.py) owns all markup.

Two inputs are supported:

* ``load_seed``  – legacy mobile/tools/seed.json (kept byte-compatible with the
  pages that were already live before the 12.5-week plan landed).
* ``load_program`` – an RPL-Plan envelope (plan.Profile/Blocks/Days/Workouts),
  e.g. mobile/docs/program/program_12w5_draft.json.

Gear thresholds come from the plan's ``Guardrails.equipment_thresholds`` when
present (strict ``>``); gear_rules.json supplies labels, ordering and the
fallback numbers. The page is display-only: no injury watch, no readiness and
no in-browser state.
"""
import csv
import datetime
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "gear_rules.json"), encoding="utf-8") as _f:
    RULES = json.load(_f)

# GPP 三层的唯一来源：GPP 目录契约。站点侧不另写域名名单、活动处方或退役名单。
# 契约缺 layers 段、层 id 不是 gpp1/gpp2/gpp3、或出现无法归层的行，一律直接失败。
GPP_CATALOG = os.path.join(HERE, "..", "..", "tools", "schema", "RPL-GPP-v1.json")

# 季节性停用：由站点生成器 --off 设置，键名对应契约 season.switches[].key。
SEASON_OFF = set()

LAYER_IDS = ("gpp1", "gpp2", "gpp3")


def _norm(x):
    return str(x or "").strip().lower()


def gpp_catalog():
    with open(GPP_CATALOG, encoding="utf-8") as f:
        return json.load(f)


def gpp_layers():
    layers = gpp_catalog().get("layers") or []
    if len(layers) != 3 or {x.get("id") for x in layers} != set(LAYER_IDS):
        raise SystemExit("GPP 契约 layers 必须恰好是 gpp1+gpp2+gpp3 三层：%r"
                         % [x.get("id") for x in layers])
    return layers


def gpp_unlayered():
    return gpp_catalog().get("unlayered") or {}


def gpp_layer(layer_id):
    for lay in gpp_layers():
        if lay.get("id") == layer_id:
            return lay
    raise SystemExit("GPP 契约没有层 %r" % layer_id)


def _catalog_item(item):
    cat = gpp_catalog()
    name = str(item or "").strip()
    if not name:
        return None
    for it in (cat.get("items") or []) + (cat.get("custom_examples") or []):
        if name in (it.get("name_en"), it.get("name_zh")):
            return it
    return None


def gpp_layer_of(domain, item=None):
    """GPP 行 → 所属层（或 baseline/retired 两个非训练层）；未命中就报错。

    判定顺序固定：条目 id → unlayered 名单 → 域名。条目 id 先看各层
    item_ids/item_overrides，再看 baseline/retired；域名最后兜底。
    这样「拉伸/冥想留在 GPP-2」这类旧分类不会因为域名相同而悄悄复活。
    """
    un = gpp_unlayered()
    it = _catalog_item(item)
    iid = it.get("id") if it else None
    name = str(item or "").strip()

    if iid:
        for lay in gpp_layers():
            if iid in (lay.get("item_ids") or []):
                return lay
            override = (lay.get("item_overrides") or {}).get(iid)
            if override:
                return gpp_layer(override)
    if iid and iid in (un.get("baseline", {}).get("item_ids") or []):
        return un["baseline"]
    if iid and iid in (un.get("retired", {}).get("item_ids") or []):
        return un["retired"]
    if name and name in (un.get("retired", {}).get("names") or []):
        return un["retired"]

    key = _norm(domain)
    if key and key in [_norm(x) for x in (un.get("baseline", {}).get("domains") or [])]:
        return un["baseline"]
    if key and key in [_norm(x) for x in (un.get("retired", {}).get("domains") or [])]:
        return un["retired"]
    for lay in gpp_layers():
        if key in [_norm(x) for x in (lay.get("source_domains") or [])]:
            return lay
    raise SystemExit("GPP 行 domain=%r item=%r 不在契约 layers/unlayered 任何一层里"
                     "（新增域必须先登记到 RPL-GPP-v1.json#layers）" % (domain, item))


def gpp_split(rows):
    """[GPP rows] → 五个桶，顺序保持原表序。"""
    out = {"gpp1": [], "gpp2": [], "gpp3": [], "baseline": [], "retired": []}
    for r in rows or []:
        r = r or {}
        out[gpp_layer_of(r.get("domain"), r.get("item"))["id"]].append(r)
    return out


def _menu_item(it):
    """契约条目 → 页面显示用的一行（英文基准，中文随行由语言层决定）。"""
    return {
        "id": it.get("id") or "",
        "name": str(it.get("name_en") or it.get("name_zh") or ""),
        "name_zh": str(it.get("name_zh") or ""),
        "target": str(it.get("target_en") or it.get("target_text") or ""),
        "target_zh": str(it.get("target_text") or ""),
    }


def gpp_item_zh(item):
    """Chinese name for one GPP catalogue item; empty when the contract has none.

    The workbook GPP rows carry an English name only, so the Chinese side must
    come from the same catalogue the menu uses — not from a page-level map.
    """
    it = _catalog_item(item)
    return str((it or {}).get("name_zh") or "")


def gpp_menu_rows(week):
    """当周 GPP 行 = 契约 weekly_menu，逐条解析成站点渲染用的行。

    周 GPP 只有这一个来源：RPL-GPP-v1.json#weekly_menu。program 工作簿里的
    GPP 表不再参与站点渲染，避免两套菜单各说各话。
    """
    cat = gpp_catalog()
    items = {it["id"]: it for it in (cat.get("items") or [])}
    custom = {c["id"]: c for c in (cat.get("custom_examples") or [])}
    rows = []
    for r in cat.get("weekly_menu") or []:
        shown = []
        for iid in (r.get("item_ids") or []):
            it = items.get(iid) or custom.get(iid)
            if not it:
                raise SystemExit("weekly_menu 行 %r 引用未知条目 %r"
                                 % (r.get("row"), iid))
            shown.append(_menu_item(it))
        rows.append({
            "week": int(week),
            "item_idx": int(r.get("row") or 0),
            "row": int(r.get("row") or 0),
            "layer": r.get("layer"),
            "slot": bool(r.get("slot")),
            "domain": r.get("domain") or "",
            "item": shown[0]["name"] if shown else "",
            "items": shown,
        })
    rows.sort(key=lambda x: x["item_idx"])
    return rows


def set_season_off(keys):
    """设置季节性停用开关（pool / bike）；未知键直接失败。"""
    global SEASON_OFF
    known = {s.get("key") for s in (gpp_catalog().get("season") or {}).get("switches") or []}
    bad = {str(k).strip() for k in keys or []} - known
    if bad:
        raise SystemExit("未知季节开关：%s（可选：%s）" % (sorted(bad), sorted(known)))
    SEASON_OFF = {str(k).strip() for k in keys or []}


def _all_gpp1_activities():
    cat = gpp_catalog()
    items = {it["id"]: it for it in cat.get("items") or []}
    custom = {c["id"]: c for c in cat.get("custom_examples") or []}
    out = []
    for a in gpp_layer("gpp1").get("activities") or []:
        it = items.get(a.get("item_id")) or custom.get(a.get("item_id")) or {}
        out.append({
            "key": a["key"],
            "label": a.get("label") or {},
            "name_zh": it.get("name_zh", ""),
            "name_en": it.get("name_en", ""),
            "rx": it.get("target_text") or "",
            "note": it.get("note") or "",
            "note_en": it.get("note_en") or "",
            "source": a.get("source") or "",
            "season_key": a.get("season_key"),
        })
    if [a["key"] for a in out] != ["run", "swim", "cycle", "basketball"]:
        raise SystemExit("GPP-1 活动顺序必须是 run/swim/cycle/basketball：%r"
                         % [a.get("key") for a in out])
    return out


def gpp1_activities():
    """当前可用的 GPP-1 四类活动（已剔除季节停用项）。"""
    return [a for a in _all_gpp1_activities()
            if not a.get("season_key") or a["season_key"] not in SEASON_OFF]


def gpp1_off_activities():
    """被季节开关停用的活动，用于页面说明「哪些选项暂时不在」。"""
    return [a for a in _all_gpp1_activities()
            if a.get("season_key") and a["season_key"] in SEASON_OFF]


def gpp1_slots(week, count, run_count=0):
    """按周给出 GPP-1 的名额建议；停用后自动在剩余活动里轮换。

    先兑现 RunPlan 里已经排定的跑步次数，剩余名额再从可用活动里轮换；
    这样页面不会出现「RunPlan 两次跑步、名额却写着 RUN + CYCLE」的矛盾。
    """
    acts = gpp1_activities()
    keys = [a["key"] for a in acts]
    if count <= 0 or not keys:
        return []
    out = []
    if "run" in keys:
        runs = min(int(run_count or 0), count)
        out.extend(["run"] * runs)
        if not runs:
            out.append("run")
    pool = [k for k in keys if k not in out] or keys[:]
    i = (int(week or 1) - 1) % len(pool)
    while len(out) < count:
        out.append(pool[i % len(pool)])
        i += 1
    return out[:count]


def gpp_week(plan, week):
    """一层的当周次数与约束判定（站点与 App 共用同一套计数口径）。"""
    rows = (getattr(plan, "gpp", {}) or {}).get(week) or []
    split = gpp_split(rows)
    runs = (getattr(plan, "run_by_week", {}) or {}).get(week) or []
    engine = max(len(runs), 1 if split["gpp1"] else 0)
    group_by = ((gpp_layer("gpp2").get("weekly") or {}).get("session_group_by")
                or "domain")
    if group_by == "week":
        frame = 1 if split["gpp2"] else 0
    else:
        frame_domains = []
        for r in split["gpp2"]:
            key = _norm(r.get("domain"))
            if key not in frame_domains:
                frame_domains.append(key)
        frame = len(frame_domains)
    return {
        "week": int(week),
        "split": split,
        "runs": runs,
        "engine": engine,
        "frame": frame,
        "frame_items": len(split["gpp2"]),
        "reset": len(split["gpp3"]),
        "baseline": len(split["baseline"]),
        "frame_allowed": frame <= engine and (engine > 0 or frame == 0),
        "slots": gpp1_slots(week, engine, len(runs)),
    }


def rest_hint(d):
    """休息日的具体恢复提示，按日期确定性轮换（同一日期永远同一条）。"""
    hints = gpp_catalog().get("rest_hints") or []
    if not hints:
        return {"zh": "", "en": ""}
    return hints[d.toordinal() % len(hints)]


WEEKDAY = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
MONTH = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

CAT_EN = {
    "S.Main": "MAIN LIFT", "B.Main": "MAIN LIFT", "D.Main": "MAIN LIFT",
    "SBD.UpperBack": "UPPER BACK", "B.Delts": "DELTS", "S.Core": "CORE",
    "D.Lats": "LATS", "B.Triceps": "TRICEPS", "B.Rotator": "ROTATOR CUFF",
    "D.GluteHam": "GLUTES / HAMSTRINGS", "D.LowerBack": "LOWER BACK",
    "S.Quads": "QUADS", "Hyper.LatDelts": "LATERAL DELTS",
    "S.Vari.Start": "VARIATION", "S.Vari.Mid": "VARIATION", "S.Vari.End": "VARIATION",
    "B.Vari.Control": "VARIATION", "B.Vari.Mid": "VARIATION", "B.Vari.End": "VARIATION",
    "D.Vari.Mid": "VARIATION", "D.Vari.Power": "VARIATION", "D.Vari.End": "VARIATION",
}

RX_EN = {
    "1×3 顶组 + 2×3 减 5% 补组": "1×3 top + 2×3 @ −5%",
    "1×3 顶组 + 1×3 减 5% 补组": "1×3 top + 1×3 @ −5%",
    "1×1 · 第 1 把": "1×1 · attempt 1",
    "1×1 · 第 2 把": "1×1 · attempt 2",
    "1×1 · 第 3 把": "1×1 · attempt 3",
}

CUE = {
    "Seated Row": "Elbows tight to the body, 1-s pause with shoulder blades retracted.",
    "Cable Y-Raise": "Light load, full range; targets the mid and lower traps.",
    "Machine / Hanging Leg Raise": "Bodyweight only; controlled tempo, no swinging.",
    "OHP": "Upwardly rotate the shoulder blades; keep the ribs down.",
    "Weighted Pull-Up": "Bodyweight; full range, no kipping.",
    "Weighted Dip": "Bodyweight; controlled depth, no bouncing.",
    "Dip": "Bodyweight; controlled depth, no bouncing.",
    "Cable Lateral Raise": "Targets the lateral delt; lead with the elbow.",
    "Face Pull": "Targets the rear delts and scapular stability.",
    "Bent-Over Barbell Row": "1-s pause at the top of every rep.",
    "Power Clean": "Technique work only; no e1RM.",
    "Romanian Deadlift": "Hips back, bar close; stop when the hamstrings say stop.",
    "Front Squat": "Elbows high, upright torso; no bounce out of the hole.",
    "Spoto Bench": "Pause 2 s on the chest; no leg drive.",
    "Pin Squat": "Dead-stop on the pins; no bounce.",
    "Paused Squat": "2-s pause in the hole; stay tight.",
    "Tempo Bench": "3-s lowering phase; no bounce.",
    "Cable Pushdown": "Elbows pinned; full lockout.",
    "Pull-Up": "Full range; no kipping.",
    "Chest-Supported Row (Elbows Out)": "Chest on the pad; drive the elbows out.",
    "One-Arm Dumbbell Row": "Flat back; pull to the hip.",
    "45-Degree Back Extension": "Round-to-extend slowly; squeeze the glutes.",
    "Seated Leg Curl": "Slow eccentric; no hip lift.",
    "Side Plank": "Straight line from ear to ankle.",
    "Dumbbell Bulgarian Split Squat": "Front foot flat; control the descent.",
    "Bent-Over Reverse Fly": "Light load; lead with the elbows.",
}

LEGACY_BASE = dict(RULES["legacy_base"])
BIG3 = {"High-bar Squat", "Mid-grip Bench", "Conventional Deadlift"}
SITE_LIFT = {"High-bar Squat": "squat", "Mid-grip Bench": "bench",
             "Conventional Deadlift": "deadlift"}
LIFT_CODE = {"sq": "squat", "bp": "bench", "dl": "deadlift"}

# Single source of truth for the weekly main / variation / accessory split.
# Everything not listed here is an accessory.
MAIN_MOVES = {"High-bar Squat", "Mid-grip Bench", "Conventional Deadlift"}
# SBD variations: the same three competition lifts, different style.
SBD_VARIATION_MOVES = {"Low-bar Squat", "Wide-grip Bench", "Sumo Deadlift"}
# §4.5 高翻归属：只认「类别精确相等」或「精确名命中」，不做子串匹配。
# 依据 gen_muscle_map.py#sbd_of 的同一份规则（App 侧已正确，站点侧不得另写一套）。
POWER_CLEAN_NAMES = {"Power Clean", "Hang Power Clean", "Clean Pull", "Clean High Pull"}
SNATCH_NAMES = {"Snatch", "Power Snatch", "Hang Snatch", "Snatch Pull",
                "Snatch High Pull", "Muscle Snatch"}
# Variations that are not SBD (yet); kept as their own bucket until decided.
NON_SBD_VARIATION_MOVES = {"Romanian Deadlift"}
VARIATION_MOVES = SBD_VARIATION_MOVES | NON_SBD_VARIATION_MOVES


def _row_category(row):
    return str((row or {}).get("category") or (row or {}).get("cat") or "").strip()


def _is_power_clean(mv, row=None):
    """精确名或 D.Vari.Power 类别 → 硬拉变式；抓举先排除。"""
    name = str(mv or "").strip()
    if name in SNATCH_NAMES:
        return False
    return name in POWER_CLEAN_NAMES or _row_category(row) == "D.Vari.Power"


def movement_role(mv, row=None):
    """'main' / 'variation' / 'accessory'; None when the name is missing."""
    name = str(mv or "").strip()
    if not name:
        return None
    if name in MAIN_MOVES:
        return "main"
    if name in VARIATION_MOVES or _is_power_clean(name, row):
        return "variation"
    return "accessory"


def movement_bucket(mv, row=None):
    """'main' / 'sbdVar' / 'nonSbdVar' / 'accessory'; None when unnamed."""
    name = str(mv or "").strip()
    if not name:
        return None
    if name in MAIN_MOVES:
        return "main"
    if name in SBD_VARIATION_MOVES or _is_power_clean(name, row):
        return "sbdVar"
    if name in NON_SBD_VARIATION_MOVES:
        return "nonSbdVar"
    return "accessory"


# --- capacity panel: lift / muscle inference ------------------------------------
# The plan is adding ``lift`` and ``muscle_group`` to every workout row. Until
# those fields land, these tables are the single fallback. Row fields always win
# (see movement_lift / movement_group), so this never becomes a second source.

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

# --- fractional-set coefficients ------------------------------------------------
# One source of truth: mobile/tools/muscle_map.json, generated at build time by
# tools/gen_muscle_map.py from docs/research/fractional_sets/coefficient_matrix.csv
# (260 movements x 16 muscles, each row carrying an A/B/C evidence tier). The same
# file is copied verbatim into seed.lib.coef for the App, so site and App cannot
# drift apart.
#
# The capacity panel works in six muscle groups, so each 16-muscle row folds to
# six with ``max`` across its sub-muscles. Summing quads+hamstrings+glutes+adductors
# would score one squat set as ~2.1 leg sets; ``max`` caps a set at one set of its
# strongest sub-region, which is what "fractional" means here. The 16-leaf view
# keeps the row's own coefficients: one set can be 1.0 chest + 0.3 triceps, and
# those are different muscles, not one summed leg.
MUSCLE_MAP_PATH = os.path.normpath(os.path.join(
    HERE, "..", "..", "tools", "muscle_map.json"))


def load_muscle_map(path):
    """Read the build-time artifact shared with ``seed.lib.coef``.

    A missing or malformed artifact is a hard stop. Falling back to 1.0 would
    score an unknown movement as one full set of every muscle group -- the same
    silent error as counting an unmapped row as zero sets.
    """
    if not os.path.exists(path):
        raise SystemExit("缺少 %s：先跑 python tools/gen_muscle_map.py" % path)
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("schema") != "RPL-MuscleMap-v1":
        raise SystemExit("muscle_map.json schema=%r，只认 RPL-MuscleMap-v1"
                         % doc.get("schema"))
    if not doc.get("moves") or len(doc.get("groups") or []) != 6:
        raise SystemExit("muscle_map.json 结构不完整：groups=%d moves=%d"
                         % (len(doc.get("groups") or []), len(doc.get("moves") or {})))
    return doc


MUSCLE_MAP = load_muscle_map(MUSCLE_MAP_PATH)
GROUP_COEF = MUSCLE_MAP.get("moves") or {}
GROUP_COEF_BY_NAME = MUSCLE_MAP.get("by_name") or {}
GROUP_COEF_FINAL = bool(GROUP_COEF)

# 16-leaf view. Thresholds are the only place these numbers live: the renderer,
# the body map and the probe all read them from here.
LEAF_ORDER = list(MUSCLE_MAP.get("leaf_order") or [])
GROUP_LEAVES = MUSCLE_MAP.get("group_leaves") or {}
EXTRA_LEAVES = list(MUSCLE_MAP.get("extra_leaves") or [])
TIER_PRIMARY = 0.8      # >= max coefficient x 0.8 -> primary (lit)
TIER_SECONDARY = 0.3    # >= max coefficient x 0.3 -> secondary (lit)
LEAF_MAP_SCHEMA = MUSCLE_MAP.get("schema")

# --- cited volume references ----------------------------------------------------
# Two rulers, never subtracted from each other:
#   * six groups -> weekly_range in total sets (indirect work included);
#   * 16 leaves  -> RP direct sets, bound to 2 sessions/week.
# Group MEV/MRV stay null (RP stops at single muscles). S/B/D carry the
# INTEGRATION_SPEC construction. Leaf values come from the research ledger, so
# the page never hand-copies a number.
RANGES = MUSCLE_MAP.get("ranges") or {}
GROUP_RANGES = RANGES.get("groups") or {}
SBD_RANGES = RANGES.get("sbd") or {}
LEAF_RANGE_PATH = os.path.normpath(os.path.join(
    HERE, "..", "research", "mev_mrv", "mev_mrv_sources.csv"))


def _int_or_none(x):
    s = str(x or "").strip()
    if not s:
        return None
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def load_leaf_ranges(path=LEAF_RANGE_PATH):
    """Leaf-level RP reference keyed by leaf id.

    A missing ledger is a hard stop: falling back to empty would make the page
    look like the sources do not exist.
    """
    if not os.path.exists(path):
        raise SystemExit("缺少 %s：叶级区间不可编造" % path)
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = str(row.get("key") or "").strip()
            if not key.startswith("leaf."):
                continue
            out[key[5:]] = {
                "mev": _int_or_none(row.get("mev")),
                "mrv": _int_or_none(row.get("mrv")),
                "status": str(row.get("status") or "").strip(),
                "grade": str(row.get("grade") or "").strip(),
                "caliber": str(row.get("caliber") or "").strip(),
                "spw": _int_or_none(row.get("sessions_per_week")),
                "scope": str(row.get("interval_scope") or "").strip(),
                "has_zero": bool(str(row.get("zero_reason") or "").strip()),
                "has_a": bool(str(row.get("a_direction") or "").strip()),
            }
    return out


LEAF_RANGES = load_leaf_ranges()

# Cardio equivalent = sum(duration x intensity coefficient). The table lives on
# the site for now (not in RPL-GPP-v1.json, which another line owns); moving it
# into the schema is a follow-up, not a second source today.
CARDIO_COEF_PATH = os.path.join(HERE, "cardio_coef.json")


def load_cardio_coef(path=CARDIO_COEF_PATH):
    if not os.path.exists(path):
        raise SystemExit("缺少 %s：心肺等效没有系数表就不能算" % path)
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("schema") != "RPL-CardioCoef-v1" or not doc.get("rules"):
        raise SystemExit("cardio_coef.json schema 不符：只认 RPL-CardioCoef-v1")
    return doc


CARDIO_COEF = load_cardio_coef()


def cardio_coef(row):
    """Moderate-equivalent coefficient for one GPP row, or None if unmeasured."""
    zone = str((row or {}).get("zone") or "").strip().upper()
    typ = str((row or {}).get("type") or "").strip().lower()
    for rule in CARDIO_COEF.get("rules") or []:
        if rule.get("coef") is None:
            continue
        if typ and typ in [str(x).strip().lower() for x in rule.get("types") or []]:
            return float(rule["coef"])
        if zone and zone in [str(x).strip().upper() for x in rule.get("zones") or []]:
            return float(rule["coef"])
    return None


def cardio_weeks(plan):
    """Per-week prescribed minutes and moderate-equivalent minutes."""
    n = plan.total_weeks
    weeks = {w: {"min": 0.0, "eq": 0.0, "runs": 0, "unmeasured": 0}
             for w in range(1, n + 1)}
    for row in getattr(plan, "run_plan", []) or []:
        try:
            w = int(_num(row.get("week")) or 0)
        except (TypeError, ValueError):
            w = 0
        if not 1 <= w <= n:
            continue
        slot = weeks[w]
        slot["runs"] += 1
        coef = cardio_coef(row)
        if coef is None:
            slot["unmeasured"] += 1
            continue
        mins = float(_num(row.get("duration_min")) or 0)
        slot["min"] += mins
        slot["eq"] += mins * coef
    active = [v for v in weeks.values() if v["runs"]]
    eq = [v["eq"] for v in active]
    return {
        "weeks": weeks,
        "runs": sum(v["runs"] for v in active),
        "minutes": sum(v["min"] for v in active),
        "unmeasured": sum(v["unmeasured"] for v in active),
        "low": min(eq) if eq else 0.0,
        "high": max(eq) if eq else 0.0,
        "guideline": CARDIO_COEF.get("guideline") or {},
    }


def _resolve_entry(mv, cat=None):
    """(entry, how) for one workout row; (None, why) when it cannot be resolved.

    Lookup order follows INTEGRATION_SPEC_v1 §4.10: the row's ``category`` is the
    disambiguator. Exact ``category|name`` wins; a name whose vectors are all
    identical falls back to ``name``; only a multi-vector name that the category
    cannot distinguish becomes ``ambiguous``; everything else is ``unmapped``.
    """
    name = str(mv or "").strip().casefold()
    if not name:
        return None, "unmapped"
    hit = GROUP_COEF.get("%s|%s" % (str(cat or "").strip(), name))
    if hit is not None:
        return (None, "unmapped") if hit.get("placeholder") else (hit, "exact")
    slot = GROUP_COEF_BY_NAME.get(name) or {}
    keys = slot.get("keys") or []
    if slot.get("unique") and keys:
        hit = GROUP_COEF.get(keys[0])
        if hit is not None:
            return ((None, "unmapped") if hit.get("placeholder") else (hit, "name"))
    if keys:
        return None, "ambiguous"
    return None, "unmapped"


def resolve_coef(mv, cat=None):
    """(coefficient dict, how) for one workout row, in six groups."""
    hit, how = _resolve_entry(mv, cat)
    if hit is None:
        return None, how
    return hit.get("coef") or {}, how


def resolve_leaf(mv, cat=None):
    """(16-leaf coefficient dict, how) for one workout row."""
    hit, how = _resolve_entry(mv, cat)
    if hit is None:
        return None, how
    leaf = hit.get("leaf")
    return (leaf or {}, how) if leaf is not None else (None, "no-leaf")


def leaf_tiers(leaf):
    """({leaf: 0|1|2}, max) for one movement's leaf vector.

    1 = primary (>= max x TIER_PRIMARY), 2 = secondary (>= max x TIER_SECONDARY),
    0 = below the secondary cut: not lit and not counted as direct sets.
    """
    vals = [float(v or 0.0) for v in (leaf or {}).values()]
    mx = max(vals) if vals else 0.0
    out = {}
    for k in LEAF_ORDER:
        c = float((leaf or {}).get(k) or 0.0)
        if not mx or c <= 0:
            out[k] = 0
        elif c >= mx * TIER_PRIMARY - 1e-9:
            out[k] = 1
        elif c >= mx * TIER_SECONDARY - 1e-9:
            out[k] = 2
        else:
            out[k] = 0
    return out, mx


def group_coefficient(mv, group, cat=None):
    """Coefficient for one movement -> one muscle group, or None if unresolved.

    A resolved movement with no load on that group returns 0.0 (a bench set
    trains no legs). Unresolved movements return None; callers must report them
    instead of substituting a default coefficient.
    """
    coef, _how = resolve_coef(mv, cat)
    if coef is None:
        return None
    return float(coef.get(group, 0.0))


GROUP_ALIASES = {
    "chest": "chest", "pec": "chest", "pecs": "chest",
    "shoulder": "shoulders", "shoulders": "shoulders", "delts": "shoulders",
    "back": "back", "lats": "back", "upper back": "back",
    "legs": "legs", "quads": "legs", "hamstrings": "legs", "glutes": "legs",
    "arms": "arms", "biceps": "arms", "triceps": "arms",
    "abs": "abs", "core": "abs",
}


def movement_lift(mv, row=None):
    """Competition lift code from the row field, else the fallback table.

    Rows tagged ``other`` still resolve through the exact category/name rule
    (D.Vari.Power → D); only genuinely unrelated movements return None.
    """
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
    if _is_power_clean(name, row):
        return "D"
    if raw == "OTHER":
        return None
    return LIFT_OF_MOVEMENT.get(name)


def movement_group(mv, row=None):
    """Muscle group from the row field, else the fallback table."""
    raw = str((row or {}).get("muscle_group") or (row or {}).get("muscleGroup") or "").strip().lower()
    group = GROUP_ALIASES.get(raw, raw if raw in MUSCLE_GROUPS else None)
    if group:
        return group
    return GROUP_OF_MOVEMENT.get(str(mv or "").strip())


ANCHOR_CATEGORY = RULES["anchor_category"]
GEAR_BY_ID = {g["id"]: g for g in RULES["gear"]}
GEAR_ORDER = [g["id"] for g in RULES["gear"]]
GEAR_RULES = RULES["rules"]
LIFT_ORDER = RULES["lift_order"]
LIFT_LABEL = RULES["lift_label"]
# Cycle words the App publishes; anything else falls back to the block name.
CYCLE_KEYS = ("hyper", "strength", "transmute", "peak")
FALLBACK_THRESHOLD = RULES["fallback_thresholds"]


# --- formatting helpers (shared with the renderer) ------------------------------

def ymd6(d):
    return d.strftime("%y%m%d")


def eng_date(d):
    return "%s · %s %02d" % (WEEKDAY[d.weekday()], MONTH[d.month - 1], d.day)


def iso_date(d):
    return d.isoformat()


def pct_of(mv, load):
    b = LEGACY_BASE.get(mv)
    if not b or not load:
        return None
    return round(load / b * 100.0, 1)


def pct_str(p):
    if p is None:
        return None
    return ("%d%%" if abs(p - round(p)) < 0.05 else "%.1f%%") % p


def fmt_kg(x):
    if x is None or x == "":
        return ""
    return ("%.1f" % float(x)) + " kg"


def mround(x, step=0.5):
    """Round to the nearest multiple of step, halves up (contract mround)."""
    if x is None:
        return None
    return round(x / step + 1e-9) * step


def fmt_num(x):
    """110.5 stays 110.5, 110.0 becomes 110."""
    return ("%.1f" % float(x)).rstrip("0").rstrip(".")


_APPROX = re.compile(r"\s*[（(]\s*约?\s*[\d.]+\s*kg\s*[)）]")
_CAL_PREFIX = re.compile(r"^(?:CAL|CALIBRATION)\b[\s.:·-]*", re.I)
_KG_AT = re.compile(r"@\s*([\d.]+)\s*kg", re.I)
_TOP_RX = re.compile(
    r"^(\d+)\s*[×x]\s*(\d+)\s*顶组\s*\+\s*(\d+)\s*[×x]\s*(\d+)\s*减\s*([\d.]+)\s*%\s*补组\s*(\+)?$")
_TOP_RX_EN = re.compile(
    r"^(\d+)\s*[×x]\s*(\d+)\s*top\s*\+\s*(\d+)\s*[×x]\s*(\d+)\s*(?:at|@)\s*[-−–]?\s*([\d.]+)\s*%"
    r"(?:\s*\(back-off\))?\s*(\+)?$", re.I)
_BASE_RX = re.compile(r"^(\d+)\s*[×x]\s*(\d+)")
_SIDE_RX = re.compile(r"(\d+)\s*(?:s|秒)\s*/\s*侧")
_PCT_RX = re.compile(r"@\s*([\d.]+)\s*%")
_KG_RX = re.compile(r"约\s*([\d.]+)\s*kg")


def rx_english(text):
    """Translate the plan's rx_text into English without dropping numbers."""
    t = str(text or "").strip()
    if not t:
        return ""
    if t in RX_EN:
        return RX_EN[t]
    t = _APPROX.sub("", t)
    t = re.sub(r"减\s*([\d.]+)\s*%", r"−\1%", t)
    t = t.replace("顶组", "top").replace("补组", "back-off")
    t = t.replace("自重", "bodyweight").replace("技术组", "technique")
    t = t.replace("秒", "s").replace("/侧", "/side").replace("/臂", "/arm").replace("/腿", "/leg")
    t = t.replace("第 1 把", "attempt 1").replace("第 2 把", "attempt 2").replace("第 3 把", "attempt 3")
    return t.strip()


def prescription(e):
    """One row -> renderable set segments, each with its own absolute load.

    The plan stores one ``load_kg`` per row (top set), so a row such as
    ``1×6 顶组 + 3×6 减 3% 补组`` is split here and the back-off load is
    derived from the top load. Every segment therefore carries a kg value.
    """
    raw = _CAL_PREFIX.sub("", str(e.get("rxRaw") or e.get("rx") or "").strip())
    load = e.get("load") or None
    pct = e.get("pct")
    pct_disp = (None if movement_bucket(e.get("mv"), e) == "nonSbdVar" else
                (round(pct * 100.0, 1) if pct is not None else None))

    m = _TOP_RX.match(raw) or _TOP_RX_EN.match(raw)
    if m:
        ts, tr, bs, br, d, plus = m.groups()
        delta = float(d) / 100.0
        return [
            {"kind": "top", "label": "TOP", "sets": int(ts), "reps": int(tr), "unit": "",
             "load": load, "pct": pct_disp, "delta": None, "amrap": bool(plus)},
            {"kind": "backoff", "label": "BACK-OFF", "sets": int(bs), "reps": int(br), "unit": "",
             "load": mround(load * (1.0 - delta), 0.5) if load else None,
             "pct": round(pct_disp * (1.0 - delta), 1) if pct_disp is not None else None,
             "delta": round(delta * 100.0, 1), "amrap": False},
        ]

    m = _BASE_RX.match(raw)
    if not m:
        return [{"kind": "work", "label": "WORK", "sets": e.get("sets") or 0,
                 "reps": e.get("reps") or 0, "unit": "", "load": load, "pct": pct_disp,
                 "delta": None, "amrap": raw.endswith("+"), "text": rx_english(raw)}]

    low = raw.lower()
    # The plan can state bodyweight in the row note instead of the set text
    # (e.g. "Pull-Up 2x6" + "Bodyweight only"). Both routes mean the same
    # thing, so read them together or the site prints a load-less WORK row
    # while the App classifies the same movement as BW.
    note = str(e.get("notes") or "").lower()
    bodyweight = (("自重" in raw) or ("bodyweight" in low) or ("bodyweight" in note)
                  or bool(e.get("bwAnchor")))
    technique = ("技术组" in raw) or ("technique" in low)
    side = _SIDE_RX.search(raw)
    if side:
        reps_disp, unit = int(side.group(1)), "s/side"
    else:
        reps_disp, unit = int(m.group(2)), ""
    pm = _PCT_RX.search(raw)
    if pm and pct_disp is None:
        pct_disp = float(pm.group(1))
    if load is None and not bodyweight:
        km = _KG_RX.search(raw) or _KG_AT.search(raw)
        if km:
            load = float(km.group(1))
    label = "BW" if bodyweight else ("TECH" if technique else "WORK")
    return [{"kind": "bw" if bodyweight else "work", "label": label,
             "sets": int(m.group(1)), "reps": reps_disp, "unit": unit,
             "load": None if bodyweight else load,
             "pct": None if bodyweight else pct_disp,
             "delta": None, "amrap": raw.endswith("+"), "text": rx_english(raw)}]


def pct_fmt(p):
    """0.725 -> '72.5%', 0.8 -> '80%'."""
    if p is None:
        return "—"
    v = round(float(p) * 100.0, 1)
    return (("%d" % v) if abs(v - round(v)) < 0.05 else ("%.1f" % v)) + "%"


def row_load(seg, role):
    """Prescribed load as displayed: main on 0.5 kg, variation on 2.5 kg.

    Accessories carry no load in the new volume model, so they get ``None``.
    """
    load = seg.get("load")
    if not load:
        return None
    if role == "main":
        return mround(load, 0.5)
    if role == "variation":
        return mround(load, 2.5)
    return None


def session_volume(plan, session):
    """Mixed volume: (main + variation) tonnage plus accessory set count.

    Accessories no longer carry external load, so they contribute sets only.
    The bucket counts add up to ``sets``: main + sbdVar + nonSbdVar + accessory.
    ``variation`` stays the sum of both variation buckets for older callers.
    """
    kg = 0.0
    sets = 0
    roles = {"main": 0, "sbdVar": 0, "nonSbdVar": 0, "accessory": 0}
    lifts = {c: {"main": 0, "var": 0} for c in ("S", "B", "D")}
    groups = {g: 0.0 for g in MUSCLE_GROUPS}
    groups_weighted = {g: 0.0 for g in MUSCLE_GROUPS}
    leaves = {k: 0.0 for k in LEAF_ORDER}
    leaves_weighted = {k: 0.0 for k in LEAF_ORDER}
    moves = {}
    unresolved = []
    for e in session.get("exercises") or []:
        mv = e.get("mv")
        bucket = movement_bucket(mv, e)
        if bucket is None:
            unresolved.append(str(mv or ""))
        row_sets = 0
        for seg in prescription(e):
            n = int(seg.get("sets") or 0)
            row_sets += n
            sets += n
            reps = seg.get("reps")
            load = row_load(seg, movement_role(mv, e))
            if isinstance(reps, int) and reps > 0 and load:
                kg += load * n * reps
        if bucket:
            roles[bucket] += row_sets
            if bucket == "nonSbdVar":
                name = str(mv or "")
                moves[name] = moves.get(name, 0) + row_sets
            if bucket in ("main", "sbdVar"):
                code = movement_lift(mv, e)
                if code in lifts:
                    lifts[code]["main" if bucket == "main" else "var"] += row_sets
            if bucket in ("main", "sbdVar", "nonSbdVar", "accessory"):
                group = movement_group(mv, e)
                if group:
                    groups[group] += row_sets
                entry, how = _resolve_entry(mv, e.get("cat"))
                if entry is None:
                    unresolved.append("%s (%s, %d sets)" % (mv, how, row_sets))
                else:
                    # Fractional sets: one movement feeds every group it loads.
                    coef = entry.get("coef") or {}
                    for g in MUSCLE_GROUPS:
                        groups_weighted[g] += row_sets * float(coef.get(g, 0.0))
                    leaf = entry.get("leaf")
                    if leaf is None:
                        unresolved.append("%s (no leaf, %d sets)" % (mv, row_sets))
                    else:
                        tiers, _mx = leaf_tiers(leaf)
                        for k in LEAF_ORDER:
                            c = float(leaf.get(k) or 0.0)
                            leaves_weighted[k] += row_sets * c
                            if tiers[k] == 1:
                                leaves[k] += row_sets
    return {"kg": int(round(kg)), "sets": sets,
            "main": roles["main"], "sbdVar": roles["sbdVar"],
            "nonSbdVar": roles["nonSbdVar"], "accessory": roles["accessory"],
            "variation": roles["sbdVar"] + roles["nonSbdVar"],
            "lifts": lifts, "groups": groups, "groupsWeighted": groups_weighted,
            "leaves": leaves, "leavesWeighted": leaves_weighted,
            "moves": moves, "unresolved": unresolved}


def volumes(plan):
    """Per-session, per-week and whole-cycle tonnage plus the role split."""
    days = {}
    weeks = {w: {"kg": 0, "sets": 0, "main": 0, "variation": 0,
                 "sbdVar": 0, "nonSbdVar": 0, "accessory": 0,
                 "lifts": {c: {"main": 0, "var": 0} for c in ("S", "B", "D")},
                 "groups": {g: 0.0 for g in MUSCLE_GROUPS},
                 "groupsWeighted": {g: 0.0 for g in MUSCLE_GROUPS},
                 "leaves": {k: 0.0 for k in LEAF_ORDER},
                 "leavesWeighted": {k: 0.0 for k in LEAF_ORDER}}
             for w in range(1, plan.total_weeks + 1)}
    non_sbd = {}
    unresolved = set()
    for (week, did), s in plan.sessions.items():
        v = session_volume(plan, s)
        days[(week, did)] = v
        for k in ("kg", "sets", "main", "variation", "sbdVar", "nonSbdVar", "accessory"):
            weeks[week][k] += v[k]
        for code in ("S", "B", "D"):
            for kind in ("main", "var"):
                weeks[week]["lifts"][code][kind] += v["lifts"][code][kind]
        for group in MUSCLE_GROUPS:
            weeks[week]["groups"][group] += v["groups"][group]
            weeks[week]["groupsWeighted"][group] += v["groupsWeighted"][group]
        for leaf in LEAF_ORDER:
            weeks[week]["leaves"][leaf] += v["leaves"][leaf]
            weeks[week]["leavesWeighted"][leaf] += v["leavesWeighted"][leaf]
        for name, n in v["moves"].items():
            slot = non_sbd.setdefault(name, {"sets": 0, "weeks": {}})
            slot["sets"] += n
            slot["weeks"][week] = slot["weeks"].get(week, 0) + n
        unresolved.update(v["unresolved"])
    return {"days": days, "weeks": weeks, "nonSbd": non_sbd,
            "total": int(sum(v["kg"] for v in weeks.values())),
            "accSets": int(sum(v["accessory"] for v in weeks.values())),
            "coef": None, "coefFinal": GROUP_COEF_FINAL,
            "coefN": len(GROUP_COEF),
            "unresolved": sorted(unresolved)}


def action_vectors(plan):
    """Distinct movements used by the plan, each with its 16-leaf vector.

    Sorted main lifts first, then SBD variations, then accessories. Rows without
    a leaf vector are skipped here (session_volume() already reports them as
    unresolved), so the body map never shows a guessed vector.
    """
    rows = {}
    for s in plan.sessions.values():
        for e in s.get("exercises") or []:
            mv = str(e.get("mv") or "").strip()
            cat = str(e.get("cat") or "").strip()
            if not mv:
                continue
            key = (cat, mv)
            if key in rows:
                continue
            entry, _how = _resolve_entry(mv, cat)
            leaf = (entry or {}).get("leaf")
            if not leaf:
                continue
            tiers, mx = leaf_tiers(leaf)
            rows[key] = {
                "name": str(entry.get("en") or mv),
                "cat": cat,
                "leaf": {k: float(leaf.get(k) or 0.0) for k in LEAF_ORDER},
                "tier": tiers,
                "max": mx,
            }

    def rank(a):
        cat = a["cat"]
        if cat.endswith(".Main"):
            top = 0
        elif ".Vari." in cat:
            top = 1
        else:
            top = 2
        return (top, cat, a["name"].casefold())

    return sorted(rows.values(), key=rank)


def is_calibration(e):
    """True for the fixed calibration set (``CAL 1×3`` / ``T1.3x3``).

    It is a reference single, not the day's top work, so it is excluded from
    the top-intensity summary even when its percentage is the highest in the
    session.
    """
    mode = str(e.get("mode") or "").lower()
    looks = mode in ("t1.3x3", "cal") or mode.startswith("t1.cal") or "calibration" in mode
    # The mode alone is not enough: the plan reuses T1.3x3 for multi-set work
    # blocks. Only the fixed single triple is the calibration set.
    return bool(looks and int(e.get("sets") or 0) == 1 and int(e.get("reps") or 0) == 3)


LIFT_CODE_BY_KEY = {"squat": "S", "bench": "B", "deadlift": "D"}


def week_intensity(plan):
    """Highest prescribed %1RM per competition lift, per week.

    Only rows whose percentage comes straight from the plan's ``pct_1rm``
    count. A percentage back-calculated from a legacy base is not a
    prescription, so it stays ``None`` here and the page says it is missing
    instead of showing a plausible-looking number.
    """
    out = {w: {c: None for c in ("S", "B", "D")}
           for w in range(1, plan.total_weeks + 1)}
    for (w, _did), s in plan.sessions.items():
        for e in s.get("exercises") or []:
            if e.get("pctSrc") != "plan" or e.get("pct") is None:
                continue
            if is_calibration(e) or not _is_main_row(plan, e):
                continue
            defn = ANCHOR_CATEGORY.get(e.get("cat"))
            code = LIFT_CODE_BY_KEY.get(defn["lift"] if defn else SITE_LIFT.get(e.get("mv")))
            if code is None:
                continue
            cur = out[w][code]
            if cur is None or e["pct"] > cur:
                out[w][code] = e["pct"]
    return out


def main_loads(plan, session):
    """Top intensity per competition lift for this session."""
    best = {}
    for e in session.get("exercises") or []:
        if not _is_main_row(plan, e) or is_calibration(e):
            continue
        defn = ANCHOR_CATEGORY.get(e.get("cat"))
        lift = defn["lift"] if defn else SITE_LIFT.get(e.get("mv"))
        if not lift:
            continue
        pct = e.get("pct")
        if pct is None:
            base = LEGACY_BASE.get(e.get("mv"))
            if base and e.get("load"):
                pct = e["load"] / float(base)
        if pct is None:
            continue
        cur = best.get(lift)
        if cur is None or pct > cur["pct"]:
            best[lift] = {"lift": lift, "label": LIFT_LABEL[lift], "pct": pct,
                          "pctDisp": round(pct * 100.0, 1), "load": e.get("load") or 0}
    return [best[l] for l in LIFT_ORDER if l in best]


# --- legacy seed text ----------------------------------------------------------

def note_en(e, week):
    mv, cat, mode = e["mv"], e["cat"], e["mode"]
    load, rx = e["load"], e["rx"]
    p = pct_of(mv, load)
    ps = pct_str(p)

    if week == 9:
        if mv in BIG3:
            return "Test-week activation — %s of the competition max, light and fast. No e1RM." % ps
        return "Test-week activation — quality reps only, stay fresh. No e1RM."

    if mode.endswith(".DL"):
        if mv == "High-bar Squat" and cat == "S.Main":
            return "Deload squat — %s of the 150 kg squat max. No AMRAP, nothing near a max. Monday is the squat e1RM sample point." % ps
        if mv == "Mid-grip Bench" and cat == "B.Vari.Control":
            return "Deload bench — %s of the 100 kg bench max. No AMRAP; bench e1RM is sampled on Wednesday." % ps
        if mv == "Mid-grip Bench" and cat == "B.Main":
            return "Deload bench — %s of the 100 kg bench max. No AMRAP, nothing near a max. Wednesday is the bench e1RM sample point." % ps
        if mv == "Conventional Deadlift":
            return "Deload deadlift — %s of the 175 kg deadlift max. No AMRAP, no near-max singles; deadlift e1RM is sampled on Friday." % ps
        if mv in LEGACY_BASE:
            return "Stay in the prescribed rep range. Deload — stop well short of failure."
        base = CUE.get(mv, "Stay in the prescribed rep range.")
        return base + " Deload — stop well short of failure."

    if mv == "High-bar Squat" and cat == "S.Main":
        return "Week %d high-bar squat — %s of the 150 kg squat max. Monday is the squat e1RM sample point." % (week, ps)
    if mv == "Mid-grip Bench" and cat == "B.Main":
        return "Week %d mid-grip bench — %s of the 100 kg bench max. Wednesday is the bench e1RM sample point." % (week, ps)
    if mv == "Mid-grip Bench" and cat == "B.Vari.Control":
        return "Straight 5×5 at %s of the 100 kg bench max, no AMRAP. Bench e1RM is sampled on Wednesday, not today." % ps
    if mv == "Conventional Deadlift" and cat == "D.Main":
        return "Week %d conventional deadlift — %s of the 175 kg deadlift max. Friday is the deadlift e1RM sample point." % (week, ps)
    if mv == "Conventional Deadlift" and cat == "D.Vari.Mid":
        back = round(load * 0.95 / 0.5) * 0.5
        return "Top triple at %s, then two back-off triples at −5%% (about %s after 0.5 kg rounding). No deadlift e1RM today — sampled Friday." % (fmt_kg(load), fmt_kg(back))
    if mv == "Tempo Squat":
        return "3-s lowering with a 1-s pause at the bottom; %s of the 150 kg squat max. Accessory volume — no squat e1RM." % ps
    if mv == "Tempo Bench":
        return "3-s lowering phase; %s of the 100 kg bench max. Accessory volume — no bench e1RM." % ps
    if mv == "Power Clean":
        return "Technique work at %s — about 64%% of an estimated 70 kg power-clean 1RM. No e1RM." % fmt_kg(load)
    if mv in CUE:
        extra = " Last set AMRAP." if "+" in rx else ""
        return CUE[mv] + extra
    return "Stay in the prescribed rep range and leave 1–2 reps in reserve."


def seed_day_title(ctx, week, day):
    if week == 9:
        return {"A": "TEST-WEEK ACTIVATION · SQUAT + BENCH",
                "B": "TEST-WEEK ACTIVATION · BENCH + PULL-UP",
                "C": "TEST-WEEK ACTIVATION · DEADLIFT + CORE",
                "D": "TEST DAY · SQUAT / BENCH / DEADLIFT / POWER CLEAN"}[day]
    if week == 3 or week == 6:
        if day == "A": return "DELOAD · SQUAT · BENCH 5×5 · DL · ROW"
        if day == "B": return "DELOAD · BENCH · OHP · PULL-UP · DIP"
        if day == "C": return "DELOAD · DEADLIFT · TEMPO SQUAT · ROW"
        return "DELOAD · NO SESSION"
    return ctx.days[day]["titleEn"]


def short_title(week, day):
    if week == 9:
        return {"A": "Squat + Bench activation", "B": "Bench + Pull-Up activation",
                "C": "Deadlift + Core activation", "D": "Test day"}[day]
    return {"A": "Squat · Bench 5×5 · DL · Row",
            "B": "Bench · OHP · Pull-Up · Dip",
            "C": "Deadlift · Tempo Squat · Row",
            "D": "Power Clean · Upper back"}[day]


# --- plan container ------------------------------------------------------------

class SitePlan(object):
    """Calendar + session container shared by both inputs."""

    def __init__(self, start, days, sessions, blocks, total_weeks, mode,
                 name="", version="", profile=None, rows=None, gpp=None,
                 anchors=None):
        self.start = start
        self.days = days                 # day_id -> {weekdayOffset, titleEn}
        self.sessions = sessions         # (week, day_id) -> {exercises, title}
        self.blocks = blocks             # [{workWeeks, deloadWeeks, nameEn, nameZh}]
        self.total_weeks = total_weeks
        self.mode = mode                 # "seed" | "program"
        self.name = name
        self.version = version
        self.profile = profile or {}
        self.anchors = anchors or {}     # anchor id -> {value, source, unit, kind}
        self.rows = rows or []
        self.gpp = gpp or {}             # week -> [GPP rows]
        self.ramp = None                 # plan's own per-lift warm-up template
        self.injury = []                 # read-only injury_watch rules
        self.warmups = {}                # ISO date -> [lift warm-up groups]
        self.run_plan = []               # optional RunPlan rows
        self.run_by_week = {}            # week -> [RunPlan rows]
        self.run_by_date = {}            # ISO date -> RunPlan row
        self.goals = []                  # career goals (not weekly tasks)

        self.block_en = {}
        self.block_cycle = {}
        self.deload_weeks = set()
        n = 0
        for b in blocks:
            span = b["workWeeks"] + b["deloadWeeks"]
            key = str(b.get("cycleType") or "").strip().lower()
            for w in range(n + 1, min(n + span, total_weeks) + 1):
                self.block_cycle[w] = key
            n += span
        for w in range(1, total_weeks + 1):
            en, zh, dl = self.block_of_week(w)
            self.block_en[w] = en
            if dl:
                self.deload_weeks.add(w)

        self.training_dates = []
        for (w, did), s in self.sessions.items():
            d = start + datetime.timedelta(days=(w - 1) * 7 + days[did]["weekdayOffset"])
            self.training_dates.append((d, w, did))
        self.training_dates.sort()
        self.date_set = {d for d, _, _ in self.training_dates}
        self.order = {d: i for i, (d, _, _) in enumerate(self.training_dates)}
        self.info_by_date = {d: (w, did) for d, w, did in self.training_dates}
        self.n_training = len(self.training_dates)
        self.first_train = self.training_dates[0]
        self.last_train = self.training_dates[-1]
        self.plan_end = start + datetime.timedelta(days=(total_weeks - 1) * 7 + 6)
        nrows = len(rows) if rows else sum(len(s.get("exercises") or []) for s in sessions.values())
        self.fingerprint = "%s|%d|%d" % (start.isoformat(), total_weeks, nrows)

    def block_of_week(self, w):
        n = 0
        for b in self.blocks:
            span = b["workWeeks"] + b["deloadWeeks"]
            if w <= n + span:
                return b["nameEn"], b.get("nameZh", ""), w > n + b["workWeeks"]
            n += span
        return "NO PLAN", "", False

    def is_deload(self, w):
        return w in self.deload_weeks

    def next_session_after(self, d):
        for tup in self.training_dates:
            if tup[0] > d:
                return tup
        return None

    def session(self, week, day):
        return self.sessions.get((week, day))

    def program_note(self, e, week):
        """English note for program rows (the plan's own notes are Chinese)."""
        mv, cat = e["mv"], e["cat"]
        ps = pct_str(e.get("pctDisp"))
        if e.get("mode", "").endswith(".DL") or e.get("deload"):
            return "Deload — stop well short of failure; nothing near a max."
        if cat in ("S.Main", "B.Main", "D.Main"):
            anchor = self.anchor_for(cat)
            base = "%s — %s of the %s plan 1RM." % (mv, ps or "—", fmt_kg(anchor) or "—")
            if week >= self.total_weeks:
                return base + " Checkpoint test: openers, second and third attempts as written."
            return base + " Main lift; the percentage comes from the plan's pct_1rm."
        cue = CUE.get(mv)
        if cue:
            extra = " Last set AMRAP." if "+" in (e.get("rx") or "") else ""
            return cue + extra
        return "Stay in the prescribed rep range and leave 1–2 reps in reserve."

    def anchor_for(self, cat):
        defn = ANCHOR_CATEGORY.get(cat)
        if not defn:
            return None
        v = self.profile.get(defn["anchor"])
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


# --- loaders -------------------------------------------------------------------

def load_seed(seed):
    start = datetime.date.fromisoformat(seed["structure"]["startDate"])
    days = {d["id"]: {"weekdayOffset": d["weekdayOffset"], "titleEn": d["titleEn"]}
            for d in seed["structure"]["dayDefs"]}
    weeks = seed["weeks"]
    sessions = {}
    for w in range(1, seed["structure"]["totalWeeks"] + 1):
        for did in ("A", "B", "C", "D"):
            s = weeks.get(str(w), {}).get(did)
            if s and s.get("exercises"):
                sessions[(w, did)] = s
    blocks = [{"workWeeks": b["workWeeks"], "deloadWeeks": b["deloadWeeks"],
               "nameEn": b["nameEn"], "nameZh": b.get("nameZh", ""),
               "cycleType": b.get("cycleType") or b.get("cycle_type") or ""}
              for b in seed["structure"]["blocks"]]
    return SitePlan(start, days, sessions, blocks, seed["structure"]["totalWeeks"], "seed")


def _num(v):
    try:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def load_program(envelope, name=""):
    plan = envelope["plan"]
    prof = {}
    for r in plan.get("Profile", []):
        if isinstance(r, dict) and r.get("field") is not None:
            prof[str(r["field"])] = r.get("value")

    start = datetime.date.fromisoformat(str(prof["start_date"]))
    days = {}
    for d in plan.get("Days", []):
        did = str(d.get("day_id"))
        off = _num(d.get("weekday_offset"))
        if did and off is not None:
            days[did] = {"weekdayOffset": int(off),
                         "titleEn": d.get("title_en") or d.get("title_zh") or ("DAY " + did)}

    blocks = [{"workWeeks": int(_num(b.get("work_weeks")) or 0),
               "deloadWeeks": int(_num(b.get("deload_weeks")) or 0),
               "nameEn": b.get("name_en") or b.get("name_zh") or b.get("block_id") or "BLOCK",
               "nameZh": b.get("name_zh", ""),
               "cycleType": b.get("cycle_type") or b.get("cycleType") or ""}
              for b in plan.get("Blocks", [])]
    total_weeks = sum(b["workWeeks"] + b["deloadWeeks"] for b in blocks)
    max_week = max([int(_num(r.get("week")) or 0) for r in plan.get("Workouts", [])] or [0])
    total_weeks = total_weeks or max_week

    # Guardrails thresholds (plan extension key; the App ignores it).
    guard = plan.get("Guardrails") or {}
    thresholds = dict(FALLBACK_THRESHOLD)
    threshold_lift = {}
    for t in guard.get("equipment_thresholds", []) or []:
        lift = str(t.get("lift") or "")
        val = _num(t.get("value"))
        if lift in thresholds and val is not None:
            thresholds[lift] = val
        if t.get("movement") and lift:
            threshold_lift[str(t["movement"])] = lift

    rows_by_session = {}
    flat = []
    for i, r in enumerate(plan.get("Workouts", [])):
        week = _num(r.get("week"))
        did = str(r.get("day")) if r.get("day") is not None else ""
        mv = str(r.get("movement") or "").strip()
        if week is None or week < 1 or week > total_weeks or did not in days or not mv:
            continue
        cat = str(r.get("category") or "")
        pct = _num(r.get("pct_1rm"))
        if pct is not None and not (0 <= pct <= 1.5):
            pct = None
        load_raw = _num(r.get("load_kg"))
        if load_raw is not None and load_raw <= 0:
            load_raw = None

        defn = ANCHOR_CATEGORY.get(cat)
        lift = defn["lift"] if defn else None
        anchor = None
        if defn:
            try:
                anchor = float(prof.get(defn["anchor"]))
            except (TypeError, ValueError):
                anchor = None
        if lift is None:
            lift = threshold_lift.get(mv) or movement_lift(mv, r)

        pct_src = "plan" if pct is not None else None
        if pct is None and load_raw and anchor:
            pct = load_raw / anchor
            pct_src = "derived"
        disp_load = load_raw
        if disp_load is None and pct is not None and anchor:
            disp_load = mround(anchor * pct, 0.5)

        e = {
            "row": int(_num(r.get("row_idx")) or i),
            "seq": int(_num(r.get("seq")) or i + 1),
            "week": int(week),
            "day": did,
            "mode": str(r.get("mode") or ""),
            "cat": cat,
            "mv": mv,
            "load": disp_load or 0,
            "loadRaw": load_raw,
            "pctDisp": (None if movement_bucket(mv, r) == "nonSbdVar" else
                        (round(pct * 100.0, 2) if pct is not None else None)),
            "pct": pct,
            "pctSrc": pct_src,
            "lift": lift,
            "rxRaw": str(r.get("rx_text") or ""),
            "rx": rx_english(r.get("rx_text")),
            "sets": int(_num(r.get("sets")) or 0),
            "reps": int(_num(r.get("reps")) or 0),
            "targetRpe": _num(r.get("target_rpe")),
            "actualRpe": _num(r.get("actual_rpe")),
            "notes": str(r.get("notes") or ""),
            "deload": False,
        }
        rows_by_session.setdefault((int(week), did), []).append(e)
        flat.append(e)

    for key, lst in rows_by_session.items():
        lst.sort(key=lambda x: x["seq"])

    sessions = {}
    for (w, did), lst in rows_by_session.items():
        sessions[(w, did)] = {
            "exercises": lst,
            "title": days[did]["titleEn"],
        }
    gpp = {w: gpp_menu_rows(w) for w in range(1, total_weeks + 1)}

    # 1RM anchors are the plan's own field (``Anchors.entries``). The day footer
    # prints these values and their source; it never reverse-engineers a 1RM
    # from a top set, which would turn a guess into a published number.
    anchors = {}
    for a in ((plan.get("Anchors") or {}).get("entries") or []):
        aid = str(a.get("id") or "").strip()
        val = _num(a.get("value"))
        if aid and val is not None:
            anchors[aid] = {"value": val, "source": str(a.get("source") or ""),
                            "unit": str(a.get("unit") or "kg"),
                            "kind": str(a.get("kind") or ""),
                            "movement": str(a.get("movement") or "")}

    # ``kind: bodyweight_max`` in the plan's own Anchors table is the machine
    # readable "this movement is bodyweight" fact. Tag the rows once here so
    # the renderer never has to guess from a name prefix.
    bw_moves = {a["movement"] for a in anchors.values()
                if a.get("kind") == "bodyweight_max" and a.get("movement")}
    for e in flat:
        e["bwAnchor"] = e.get("mv") in bw_moves

    plan_obj = SitePlan(start, days, sessions, blocks, total_weeks, "program",
                        name=name, version=str(envelope.get("schemaVersion") or ""),
                        profile=prof, rows=flat, gpp=gpp, anchors=anchors)
    for (w, did), s in plan_obj.sessions.items():
        s["deload"] = plan_obj.is_deload(w)
        for e in s["exercises"]:
            e["deload"] = plan_obj.is_deload(w)
    plan_obj.thresholds = thresholds
    plan_obj.ramp = (plan.get("TestPaths") or {}).get("ramp") or None
    plan_obj.injury = [r for r in (guard.get("injury_watch") or []) if r.get("id")]
    plan_obj.goals = [g for g in ((plan.get("Goals") or {}).get("entries") or [])
                      if g.get("id")]

    warm = {}
    for r in ((plan.get("Warmups") or {}).get("sets") or []):
        date = str(r.get("date") or "").strip()
        mv = str(r.get("movement") or "").strip()
        if date and mv:
            warm.setdefault(date, {}).setdefault(mv, []).append(r)
    for date, groups in warm.items():
        lifts = []
        for mv, rows in groups.items():
            rows.sort(key=lambda x: int(_num(x.get("step_index")) or 0))
            code = str(rows[0].get("lift") or "")
            lift = LIFT_CODE.get(code, code)
            steps = []
            for x in rows:
                pct = _num(x.get("pct"))
                steps.append({"pct": round(pct * 100.0, 1) if pct else None,
                              "label": str(x.get("pct_label") or "").strip(),
                              "kg": _num(x.get("kg")),
                              "reps": int(_num(x.get("reps")) or 0)})
            lifts.append({"lift": lift, "label": LIFT_LABEL.get(lift, mv), "steps": steps})
        lifts.sort(key=lambda g: LIFT_ORDER.index(g["lift"]) if g["lift"] in LIFT_ORDER else 9)
        plan_obj.warmups[date] = lifts

    runs = []
    for r in (plan.get("RunPlan") or plan.get("RunPlanTable") or []):
        date = str(r.get("date") or "").strip()
        if not date:
            continue
        item = dict(r)
        item["date"] = date
        runs.append(item)
        wk = int(_num(r.get("week")) or 0)
        if wk:
            plan_obj.run_by_week.setdefault(wk, []).append(item)
        plan_obj.run_by_date[date] = item
    plan_obj.run_plan = runs
    for lst in plan_obj.run_by_week.values():
        lst.sort(key=lambda x: x["date"])
    return plan_obj


# --- gear ----------------------------------------------------------------------

def thresholds_for(plan):
    return getattr(plan, "thresholds", dict(FALLBACK_THRESHOLD)) or dict(FALLBACK_THRESHOLD)


def resolve_row(plan, e):
    """Return {lift,label,pct,source,threshold} for a main-lift row, else None."""
    if plan.mode == "seed":
        lift = SITE_LIFT.get(e.get("mv"))
        if not lift:
            return None
        thr = thresholds_for(plan)[lift]
        base = LEGACY_BASE.get(e["mv"])
        load = e.get("load") or 0
        if load > 0 and base:
            return {"lift": lift, "label": LIFT_LABEL[lift], "pct": load / float(base),
                    "source": "base", "threshold": thr, "row": e}
        return {"lift": lift, "label": LIFT_LABEL[lift], "pct": None,
                "source": "none", "threshold": thr, "row": e, "reason": "load missing"}
    defn = ANCHOR_CATEGORY.get(e["cat"])
    if not defn:
        return None
    lift = defn["lift"]
    thr = thresholds_for(plan)[lift]
    if e.get("pct") is not None:
        return {"lift": lift, "label": LIFT_LABEL[lift], "pct": e["pct"],
                "source": e.get("pctSrc") or "plan", "threshold": thr, "row": e}
    if e.get("loadRaw") and plan.anchor_for(e["cat"]):
        return {"lift": lift, "label": LIFT_LABEL[lift],
                "pct": e["loadRaw"] / plan.anchor_for(e["cat"]),
                "source": "derived", "threshold": thr, "row": e}
    return {"lift": lift, "label": LIFT_LABEL[lift], "pct": None,
            "source": "none", "threshold": thr, "row": e,
            "reason": "pct_1rm missing" if e.get("loadRaw") is None else "load_kg missing"}


def lift_evaluations(plan, infos):
    by_lift = {x: [] for x in LIFT_ORDER}
    for x in infos:
        if x:
            by_lift[x["lift"]].append(x)
    out = []
    for lift in LIFT_ORDER:
        lst = by_lift[lift]
        if not lst:
            continue
        valid = [x for x in lst if x["pct"] is not None]
        bad = [x for x in lst if x["pct"] is None]
        thr = thresholds_for(plan)[lift]
        if not valid:
            out.append({"lift": lift, "label": LIFT_LABEL[lift], "status": "unknown",
                        "threshold": thr, "row": None, "unknownCount": len(bad),
                        "reasons": sorted({x.get("reason") for x in bad if x.get("reason")})})
            continue
        # Ties keep the session's own row order: the sort is stable, so no
        # per-row sequence field is needed (seed rows do not carry one).
        valid.sort(key=lambda x: (-x["pct"], -(x["row"].get("loadRaw") or 0)))
        top = valid[0]
        bp = int(round(top["pct"] * 10000))
        out.append({"lift": lift, "label": top["label"], "status": "ok", "pct": top["pct"],
                    "source": top["source"], "threshold": thr,
                    "triggered": bp > int(round(thr * 10000)),
                    "row": top["row"], "unknownCount": len(bad),
                    "reasons": sorted({x.get("reason") for x in bad if x.get("reason")})})
    return out


BAR_KG = 20.0
SIDE_STEP = 2.5            # smallest standard side plates -> 5 kg on the bar
MICRO_PLATE_SIZES = (1.0, 0.75, 0.5, 0.25)


def micro_plates(load):
    """Per-side micro plates for a symmetric 20 kg bar.

    ``[]`` means the load already sits on the 5 kg grid (no reminder needed),
    a list means micro plates are required, ``None`` means the load cannot be
    made up and must be reported rather than guessed.
    """
    try:
        x = float(load or 0)
    except (TypeError, ValueError):
        return None
    if x <= BAR_KG:
        return None
    per = (x - BAR_KG) / 2.0
    if abs(per - round(per / 0.25) * 0.25) > 1e-6:
        return None
    rem = round(per - int(per // SIDE_STEP) * SIDE_STEP, 2)
    plates = []
    for p in MICRO_PLATE_SIZES:
        if rem + 1e-9 >= p:
            plates.append(p)
            rem = round(rem - p, 2)
    return None if rem > 1e-9 else plates


def session_micro_plates(plan, session):
    """Micro plates needed by the day's main-lift working sets, per lift."""
    groups = []
    unresolved = []
    for e in session.get("exercises") or []:
        if movement_role(e.get("mv"), e) != "main":
            continue
        lift = e.get("lift") or SITE_LIFT.get(e.get("mv"))
        grp = None
        for seg in prescription(e):
            load = seg.get("load")
            if not load:
                continue
            plates = micro_plates(load)
            if plates is None:
                unresolved.append({"movement": e.get("mv"), "load": load})
                continue
            if not plates:
                continue
            if grp is None:
                grp = next((x for x in groups if x["lift"] == lift), None)
            if grp is None:
                grp = {"lift": lift, "label": LIFT_LABEL.get(lift, ""),
                       "entries": [], "used": []}
                groups.append(grp)
            labels = [("%.2f" % p).rstrip("0").rstrip(".") for p in plates]
            if not any(abs(x["load"] - float(load)) < 1e-9 and x["labels"] == labels
                       for x in grp["entries"]):
                grp["entries"].append({"load": float(load), "plates": plates,
                                       "labels": labels})
            for p in plates:
                if p not in grp["used"]:
                    grp["used"].append(p)
    for grp in groups:
        grp["used"].sort(reverse=True)
    groups.sort(key=lambda g: LIFT_ORDER.index(g["lift"]) if g["lift"] in LIFT_ORDER else 9)
    return {"groups": groups, "unresolved": unresolved}


DL_MOVES = {"Conventional Deadlift", "Sumo Deadlift", "Romanian Deadlift"}
STRAP_SETS = 6            # deadlift-family sets that make straps worth suggesting

# Exercise -> equipment, read from the exercise library payload that ships with
# the seed (itself generated from the authoritative workbook). No hand-written
# per-day table: a movement asks for its gear, and the day only inherits that.
EQUIP_PATH = os.path.join(HERE, "..", "..", "tools", "seed.json")
_EQUIP_BY_MOVEMENT = None


def equipment_map(path=EQUIP_PATH):
    global _EQUIP_BY_MOVEMENT
    if _EQUIP_BY_MOVEMENT is None:
        with open(path, encoding="utf-8") as f:
            acts = (json.load(f).get("lib") or {}).get("acts") or []
        _EQUIP_BY_MOVEMENT = {str(a.get("en") or "").strip().lower():
                              (str(a.get("equip") or ""), str(a.get("cn") or ""))
                              for a in acts}
    return _EQUIP_BY_MOVEMENT


_BAND_RE = re.compile("\u5f39\u529b\u5e26|\u963b\u529b\u5e26|\\bband", re.I)


def requires_bands(mv):
    """True only when the exercise itself names a band — same test as the App.

    The library entry (equipment + Chinese name) is tried first; a movement that
    is not in the library falls back to its own name, so custom work still
    declares its band instead of inheriting a day label.
    """
    equip, cn = equipment_map().get(str(mv or "").strip().lower(), ("", ""))
    return bool(_BAND_RE.search(" ".join([equip, cn, str(mv or "")])))


_RAMP_STEP = re.compile(r"^(\d+(?:\.\d+)?)\s*%\s*[×x]\s*(\d+)$")
_RAMP_BAR = re.compile(r"^empty\s*bar\s*[×x]\s*(\d+)$", re.I)


def warmup_ladder(plan, session, d=None):
    """Per-lift ramp for one day.

    Warmups.sets is the source: already grouped by week/day/lift, already
    truncated by top_pct, and already carries kg. The W13 Friday test day is
    not in Warmups; there we read TestPaths.ramp and convert its percentages
    with that lift's 1RM, so the two sources never render twice.
    """
    date = d.isoformat() if d is not None else session.get("date")
    data = (getattr(plan, "warmups", {}) or {}).get(date)
    if data:
        return data
    ramp = getattr(plan, "ramp", None)
    if not ramp or not ramp.get("order"):
        return []
    if not any("per-lift ramp" in str(e.get("notes") or "").lower()
               for e in session.get("exercises") or []):
        return []
    out = []
    for e in session.get("exercises") or []:
        if movement_role(e.get("mv"), e) != "main":
            continue
        lift = e.get("lift") or SITE_LIFT.get(e.get("mv"))
        if any(g["lift"] == lift for g in out):
            continue
        anchor = plan.anchor_for(e.get("cat"))
        if not anchor:
            continue
        steps = []
        for item in ramp["order"]:
            m = _RAMP_STEP.match(str(item).strip())
            if m:
                pct, reps = float(m.group(1)), int(m.group(2))
                steps.append({"pct": pct, "label": "%g%%" % pct, "reps": reps,
                              "kg": mround(anchor * pct / 100.0, 0.5)})
                continue
            b = _RAMP_BAR.match(str(item).strip())
            if b:
                steps.append({"pct": None, "label": "empty bar", "reps": int(b.group(1)),
                              "kg": BAR_KG})
        if steps:
            out.append({"lift": lift, "label": LIFT_LABEL.get(lift, ""), "steps": steps})
    out.sort(key=lambda g: LIFT_ORDER.index(g["lift"]) if g["lift"] in LIFT_ORDER else 9)
    return out


def run_tomorrow(plan, d):
    """Optional RunPlan entry on the next calendar day, if any."""
    return (getattr(plan, "run_by_date", {}) or {}).get(
        (d + datetime.timedelta(days=1)).isoformat())


def session_signals(session, lifts):
    """Gear layer triggers that are not covered by the intensity rules."""
    top = max((l["pct"] for l in lifts if l["status"] == "ok" and l["pct"] is not None),
              default=None)
    rpe = max([e.get("targetRpe") or 0 for e in session["exercises"]
               if movement_role(e.get("mv"), e) == "main"] or [0])
    dl_sets = 0
    rdl = False
    bands_why = ""
    for e in session["exercises"]:
        mv = str(e.get("mv") or "").strip()
        if not bands_why and requires_bands(mv):
            bands_why = mv
        if mv not in DL_MOVES:
            continue
        if mv == "Romanian Deadlift":
            rdl = True
        for seg in prescription(e):
            dl_sets += int(seg.get("sets") or 0)
    return {"top": top, "rpe": rpe,
            "coffee": (top is not None and top >= 0.85) or rpe >= 8.5,
            "straps": rdl or dl_sets >= STRAP_SETS,
            "bands": bool(bands_why), "bandsWhy": bands_why,
            "rdl": rdl, "dlSets": dl_sets}


def gear_for(plan, session):
    infos = [resolve_row(plan, e) for e in session["exercises"]]
    lifts = lift_evaluations(plan, infos)
    if not lifts:
        return {"status": "no-main", "items": [], "lifts": [], "unknown": [], "ignoredRows": 0}
    store = {}
    for l in lifts:
        if l["status"] != "ok" or not l["triggered"]:
            continue
        for gid in GEAR_RULES[l["lift"]]:
            if gid not in store:
                store[gid] = {"id": gid, "label": GEAR_BY_ID[gid]["label"],
                              "mono": GEAR_BY_ID[gid]["mono"], "sources": []}
            store[gid]["sources"].append({"lift": l["lift"], "label": l["label"],
                                          "pct": l["pct"], "source": l["source"],
                                          "threshold": l["threshold"]})
    items = [store[g] for g in GEAR_ORDER if g in store]
    unknown = [l for l in lifts if l["status"] == "unknown"]
    partial = [l for l in lifts if l["status"] == "ok" and l["unknownCount"] > 0]
    if items and (unknown or partial):
        status = "partial"
    elif items:
        status = "triggered"
    elif len(unknown) == len(lifts):
        status = "unknown"
    elif unknown or partial:
        status = "partial"
    else:
        status = "below"
    return {"status": status, "items": items, "lifts": lifts, "unknown": unknown,
            "partialUnknown": partial, "ignoredRows": sum(l.get("unknownCount", 0) for l in lifts)}


def _is_main_row(plan, e):
    if plan.mode == "program":
        return e.get("cat") in ANCHOR_CATEGORY
    # Seed rows carry the load but no loadRaw/seq; judge on the load itself.
    return e.get("mv") in BIG3 and float(e.get("load") or 0) > 0


def build_day_model(plan, d, week, did):
    """Everything the renderer needs for one page."""
    s = plan.sessions[(week, did)]
    exercises = s["exercises"]
    for e in exercises:
        if plan.mode == "seed":
            e["note"] = note_en(e, week)
            p = pct_of(e["mv"], e.get("load"))
            e["pct"] = (p / 100.0) if p is not None else None
            e["pctDisp"] = p
            e["rxRaw"] = e.get("rx") or ""
        else:
            e["note"] = CUE.get(e["mv"], "")
        e["rxParts"] = prescription(e)
    is_test = (plan.mode == "seed" and week == 9 and did == "D") or \
              any("test" in str(e.get("mode") or "").lower() for e in exercises)
    mains, accs = [], []
    if is_test:
        seen = []
        for e in exercises:
            if e["mv"] not in seen:
                seen.append(e["mv"])
        for mv in seen:
            rows = [x for x in exercises if x["mv"] == mv]
            (mains if _is_main_row(plan, rows[0]) or mv in BIG3 else accs).append((mv, rows))
    else:
        for e in exercises:
            (mains if _is_main_row(plan, e) else accs).append(e)
    block_en, block_zh, deload = plan.block_of_week(week)
    ctx = {"week": week, "date": iso_date(d), "exercises": exercises}
    gear = gear_for(plan, ctx)
    return {
        "date": d, "week": week, "day": did, "session": s, "exercises": exercises,
        "is_test": is_test, "mains": mains, "accs": accs,
        "blockEn": block_en, "blockZh": block_zh, "deload": deload,
        "seq": plan.order[d] + 1, "n": plan.n_training,
        "gear": gear,
        "signals": session_signals(s, gear["lifts"]),
        "micro": session_micro_plates(plan, s),
        "warmup": warmup_ladder(plan, s, d),
        "run_next": run_tomorrow(plan, d),
        "injury": getattr(plan, "injury", []),
    }
