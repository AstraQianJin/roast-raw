#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML renderer for the ExDark static site.

Owns every string that reaches the browser: the stylesheet, the day page and
the plan calendar. Data comes from day_model.py.

Display-only by design: no upload bar, no injury watch, no bodyweight or
readiness read-outs. Every prescribed set shows its absolute load.
"""
import datetime
import html
import json
import os
import re

import day_model as dm
import site_lang as sl
import site_theme as st

HERE = os.path.dirname(os.path.abspath(__file__))

# The finalised muscle-map component and its geometry live outside this file;
# both must exist or the page silently loses the body map.
MUSCLE_GEO_PATH = os.path.join(HERE, "..", "..", "tools", "muscle_geo.json")
MUSCLE_JS_PATH = os.path.join(HERE, "mockups", "muscle-map.js")
if not os.path.exists(MUSCLE_GEO_PATH):
    raise SystemExit("缺少 %s：肌群几何不可编造" % MUSCLE_GEO_PATH)
if not os.path.exists(MUSCLE_JS_PATH):
    raise SystemExit("缺少 %s：肌群组件不可编造" % MUSCLE_JS_PATH)
with open(MUSCLE_GEO_PATH, encoding="utf-8") as _f:
    MUSCLE_GEO = json.load(_f)
with open(MUSCLE_JS_PATH, encoding="utf-8") as _f:
    MUSCLE_JS = _f.read()

# Resident gear and supplement facts are research data, not page copy: the site
# reads them at build time so dose and evidence never fork from the workbook.
RESEARCH_DIR = os.path.join(HERE, "..", "research")
RESIDENT_PATH = os.path.join(RESEARCH_DIR, "gear", "gear_resident.json")
SUPPLEMENTS_PATH = os.path.join(RESEARCH_DIR, "supplements", "supplements.json")
for _p in (RESIDENT_PATH, SUPPLEMENTS_PATH):
    if not os.path.exists(_p):
        raise SystemExit("缺少 %s：常驻装备与补剂事实不可编造" % _p)
with open(RESIDENT_PATH, encoding="utf-8") as _f:
    RESIDENT_ITEMS = json.load(_f)["items"]
with open(SUPPLEMENTS_PATH, encoding="utf-8") as _f:
    _SUPP_DOC = json.load(_f)
SUPPLEMENTS_BY_ID = {it["id"]: it for it in _SUPP_DOC["items"]}
SUPP_META = _SUPP_DOC["meta"]
SUPP_ITEMS = _SUPP_DOC["items"]

# Plate math is one file for both sides: the App injects it at build time, the
# site inlines the same text.  The stock/bar defaults come from the gear schema,
# never from a second list kept here.
TOOLS_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "tools"))
PLATE_MATH_PATH = os.path.join(TOOLS_DIR, "plate_math.js")
GEAR_SCHEMA_PATH = os.path.join(TOOLS_DIR, "schema", "RPL-Gear-v2.json")
for _p in (PLATE_MATH_PATH, GEAR_SCHEMA_PATH):
    if not os.path.exists(_p):
        raise SystemExit("缺少 %s：配片算法与器械契约不可编造" % _p)
with open(PLATE_MATH_PATH, encoding="utf-8") as _f:
    PLATE_MATH_JS = _f.read()
with open(GEAR_SCHEMA_PATH, encoding="utf-8") as _f:
    _GEAR_DOC = json.load(_f)
PLATE_STOCK = [float(v) for v in _GEAR_DOC["plates"]["kg_list"]]
PLATE_BAR_DEFAULT = float(_GEAR_DOC["bar"]["default"])
PLATE_BAR_OPTIONS = [float(v) for v in _GEAR_DOC["bar"]["options"]]


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=False)


def fmt_int(n):
    return "{:,}".format(int(round(n)))


def wd(d):
    """Weekday: MON by default, 周一 in the Chinese layer."""
    return sl.D(dm.WEEKDAY[d.weekday()], sl.WEEKDAY_ZH[d.weekday()])


def zone_html(zone):
    """Z2 -> ``ZONE 2`` / ``2 区``; anything else stays verbatim."""
    z = str(zone or "").strip()
    m = re.fullmatch(r"[Zz](\d)", z)
    return sl.T("run.zone_label", m.group(1)) if m else esc(z)


def unitize(text):
    """Translate a trailing dose unit inside contract text (20 min, 10000 steps)."""
    s = str(text or "")
    m = re.match(r"^(.*?)([\d.,]+)\s*(kg|min|mins|bpm|steps|s/side|s/\u9879|secs|sec|s)$",
                 s, re.I)
    if not m:
        return s
    unit = m.group(3)
    key = {"s/\u9879": "unit.s_item", "s": "unit.sec", "sec": "unit.sec",
           "secs": "unit.sec"}.get(unit.lower()) or UNIT_KEYS.get(unit.lower())
    zh = sl.Z(key) if key else ""
    if not zh:
        return s
    return "%s%s %s" % (m.group(1), m.group(2), zh)


def wd_text(name):
    """Weekday from contract data (MON/tue/…) in the current language layer."""
    s = str(name or "").strip().upper()[:3]
    if s in dm.WEEKDAY:
        i = dm.WEEKDAY.index(s)
        return sl.D(dm.WEEKDAY[i], sl.WEEKDAY_ZH[i])
    return esc(name)


def md(d):
    """Month + day: NOV 09 by default, 11月09日 in Chinese."""
    return sl.D("%s %d" % (dm.MONTH[d.month - 1], d.day),
                "%d月%d日" % (d.month, d.day))


def dmy(d):
    """Weekday + date for run rows: TUE 10 NOV by default, 11月10日 周二 in Chinese."""
    return sl.D("%s %d %s" % (dm.WEEKDAY[d.weekday()], d.day, dm.MONTH[d.month - 1]),
                "%d月%d日 %s" % (d.month, d.day, sl.WEEKDAY_ZH[d.weekday()]))


def full_date(d):
    """Masthead date: MON · NOV 09 by default, 11月09日 · 周一 in Chinese."""
    return sl.D(dm.eng_date(d),
                "%d月%d日 · %s" % (d.month, d.day, sl.WEEKDAY_ZH[d.weekday()]))


def note_html(mv, note):
    """Coaching cue: Chinese is keyed by the movement, never by the sentence."""
    note = str(note or "")
    zh = sl.DZ("cue", mv)
    if zh and note.endswith(" Last set AMRAP.") and "\u6700\u540e\u4e00\u7ec4" not in zh:
        zh += " \u6700\u540e\u4e00\u7ec4 AMRAP\u3002"
    return sl.D(note, zh)


CSS = st.day_theme_css() + st.theme_button_css() + """
/* Day pages only: --tx3 measured below AA on all three themes (3.03-3.73:1).
   These values keep every fine-print pair at 4.5:1 or better, including the
   tinted injury strip. --onAcc is the ink on accent-filled chips; the dark
   theme's accent is a light salmon, so that ink must be dark, not white. */
html[data-theme="dark"]{--tx3:#7A869C;--onAcc:#160608}
html[data-theme="light"]{--tx3:#5B6672;--onAcc:#F4F7FA}
html[data-theme="ex"]{--tx3:#635D51;--onAcc:#EFE9DD}
/* Effort label swap: numeric in Max, three tiers in Mini. */
.rpe-t{display:none}
html[data-view="mini"] .rpe-n{display:none}
html[data-view="mini"] .rpe-t{display:inline}
/* Masthead control group: view + theme + language + share are one 44px row.
   Every control shows the CURRENT state (Mini/Max, DARK/LIGHT/EX, ZH/EN), not
   the next one; aria-pressed and aria-label carry the toggle affordance. The
   row wraps to a second header line instead of shrinking the touch targets, so
   a 320px viewport never needs a horizontal scroll. */
.mast-r .themebtn{margin:0}
/* Share sits in the same 44px row; it keeps the old .mbtn box. */
.mbtn{flex:0 0 auto;min-width:44px;height:44px;display:inline-flex;align-items:center;
  justify-content:center;gap:4px;padding:0 10px;border:1px solid var(--line2);
  border-radius:2px;background:transparent;color:var(--tx2);font-size:10px;font-weight:800;
  letter-spacing:.08em;line-height:1;text-transform:uppercase;cursor:pointer;font-variant-numeric:tabular-nums}
.mbtn:hover{color:var(--ink);border-color:var(--line)}
.mbtn:active{background:var(--ov1)}
.mbtn svg{display:block;width:18px;height:18px}
.mbtn[aria-pressed="true"]{border-color:var(--accLine);background:var(--accSoft);color:var(--acc)}
/* The view control names the current mode (MINI / MAX), so it must not read as a
   third ghost button: accent border, accent ink and the soft accent wash mark it
   as the live state under all three themes. */
.mast-r #viewBtn{border-color:var(--accLine);background:var(--accSoft);color:var(--acc)}
/* Mode switch: opacity only, 150ms, and nothing at all under reduced motion. */
.wrap{transition:opacity .15s var(--ease)}
body.view-swap .wrap{opacity:.7}
@media(prefers-reduced-motion:reduce){.wrap{transition:none}body.view-swap .wrap{opacity:1}}
/* Mini keeps the footer arrows reachable at 48px. The day footer itself is a
   data module (1RM anchors) and leaves Mini; the masthead arrow still returns
   to the plan. */
html[data-view="mini"] .foot a{min-height:48px}
/* The day footer prints the 1RM anchor table; that is a data module, so Mini
   drops it. The way back to the plan stays in the masthead arrow. */
html[data-view="mini"] .day-foot{display:none}
/* Mini is a separate read-only sheet, not the Max document with pieces hidden:
   only one of the two trees is in flow at any time. Max keeps its full markup
   untouched; Mini renders main lifts (+variations), accessories and a folded
   gear list, and nothing else. */
.mini-only{display:none}
html[data-view="mini"] .mini-only{display:block}
html[data-view="mini"] .max-only{display:none}
.ms{padding:0}
.ms-k{margin:22px 0 0;padding:0 0 8px;font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--tx3)}
.ms-k:first-child{margin-top:8px}
.ms-lift{padding:12px 0;border-top:1px solid var(--line)}
.ms-h{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
.ms-h b{font-size:17px;font-weight:800;letter-spacing:-.01em;line-height:1.25}
.ms-h span{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--tx3);font-weight:800;white-space:nowrap}
.ms-r{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 12px;margin-top:7px;font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:13px;color:var(--tx2)}
.ms-r b{font-size:18px;font-weight:800;color:var(--ink);letter-spacing:-.01em}
.ms-r b i{font-style:normal;font-size:11px;font-weight:600;color:var(--tx3);margin-left:2px}
.ms-tag{font-size:10px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--tx3)}
.ms-ctx{margin:0 0 8px;font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;
  color:var(--tx3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ms-acc-line{font-family:var(--mono);font-size:13px;color:var(--tx2)}
.ms-gear{border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-top:8px}
.ms-gear summary{display:flex;align-items:center;gap:10px;min-height:48px;cursor:pointer;list-style:none;font-size:12px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}
.ms-gear summary::-webkit-details-marker{display:none}
.ms-gear summary em{font-style:normal;margin-left:auto;font-size:10px;letter-spacing:.06em;color:var(--tx3);text-transform:none}
.ms-gear summary b{font-weight:800;color:var(--tx3);font-size:16px;line-height:1}
.ms-gear ul{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px;padding:0;list-style:none}
.ms-gear li{padding:5px 10px;border:1px solid var(--line);border-radius:2px;font-size:11px;color:var(--tx2)}
.ms-gear-empty{display:flex;align-items:center;gap:10px;min-height:48px;font-size:12px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}
.ms-gear-empty em{font-style:normal;margin-left:auto;font-size:10px;letter-spacing:.06em;color:var(--tx3);text-transform:none}
.ms-day{border-top:1px solid var(--line);padding:2px 0 14px}
.ms-day:first-of-type{border-top:0}
.ms-day-h{display:flex;align-items:center;gap:8px;min-height:48px;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--acc)}
.ms-day-h b{font-size:14px;letter-spacing:.04em}
.ms-day-h em{font-style:normal;margin-left:auto;font-size:10px;color:var(--tx3);letter-spacing:.06em}
.ms-day .ms-lift:first-of-type{border-top:1px solid var(--line2);padding-top:10px}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html{-webkit-text-size-adjust:100%}
html,body{margin:0;padding:0}
body{--tx2s:color-mix(in srgb,var(--tx2) 70%,var(--ink));background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;font-size:14px;line-height:1.5;padding:calc(14px + env(safe-area-inset-top)) 16px calc(34px + env(safe-area-inset-bottom));overflow-x:clip}
.wrap{max-width:600px;margin:0 auto}
a{color:inherit;text-decoration:none}
.mast{display:flex;flex-wrap:wrap;row-gap:4px;align-items:center;justify-content:flex-start;gap:8px;padding:0 0 12px;border-bottom:1px solid var(--line);font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--tx3)}
.up{display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:0 10px 0 0;margin-right:2px;font-family:var(--mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--tx2);white-space:nowrap}
.up:hover{color:var(--ink)}
.mast-r{display:inline-flex;flex-wrap:wrap;align-items:center;justify-content:flex-end;gap:6px;margin-left:auto;white-space:normal}
@media (max-width:420px){.mast-r>span{font-size:9px;letter-spacing:.02em}}
/* 320px: the date label and the wordmark text are the only things that force a
   second header row. The back arrow, the square mark and the four controls
   still fit on one 44px line, so the bar never becomes two lines again. */
@media (max-width:420px){
  .mast.has-up .brand{display:none}
  .mast:not(.has-up) .brand{font-size:0;letter-spacing:0}
  .mast-r>span:first-child{display:none}
}
.brand{color:var(--acc);font-weight:800;letter-spacing:.2em;white-space:nowrap;display:inline-flex;align-items:center}
.brand .bsq{width:9px;height:9px;background:var(--acc);display:inline-block;flex:none;margin-right:8px}
/* Tier badge: an independent capsule, never part of the wordmark (red line 8).
   The slot is only present on /plan/; empty slot renders no box at all. */
.tier-slot{display:inline-flex;align-items:center;margin-left:10px}
.tier-slot:empty{display:none}
.tierb{font-style:normal;display:inline-flex;align-items:center;height:20px;padding:0 8px;border:1px solid var(--accLine);border-radius:999px;font-size:10px;font-weight:800;line-height:1;letter-spacing:.12em;color:var(--acc);white-space:nowrap}
.hero{padding:24px 0 16px}
.eyebrow{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--tx3);font-weight:600}
.eyebrow span{color:var(--tx3);margin:0 4px}
.eyebrow .edate{display:none;font-style:normal}
.hero h1{margin:8px 0 0;font-size:clamp(20px,6.6vw,26px);line-height:1.14;font-weight:800;letter-spacing:-.02em;overflow-wrap:anywhere}
.hero h1 .act{display:inline-block;white-space:nowrap}
@media(max-width:479px){.hero h1 .cyc{display:block;margin-top:8px;font-size:12px;font-weight:600;letter-spacing:.02em;color:var(--tx2)}.hero h1 .cycsep{display:none}}
.hero-sub{margin:8px 0 0;font-size:11px;color:var(--tx3);letter-spacing:.02em}
.tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:12px}
.pill{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line2);border-radius:2px;padding:4px 8px;color:var(--tx2);white-space:nowrap}
.pill.on{color:var(--acc);border-color:var(--accLine);background:var(--accSoft)}
.pill.dl{color:var(--tx2);border-color:var(--line2);background:var(--ov1)}
.pill.ts{color:var(--acc);border-color:var(--accLine);background:var(--accSoft)}
.hero[data-kind]{border-top:2px solid transparent;padding-top:16px}
.hero[data-kind="deload"]{border-top-color:var(--line2)}
.hero[data-kind="test"]{border-top-color:var(--acc)}
.brief{border:1px solid var(--line);border-radius:2px;background:linear-gradient(180deg,var(--panel2),var(--panel));overflow:hidden;margin:2px 0 16px}
.brief-h{padding:12px 16px 8px;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--tx3);font-weight:700}
.mainloads{display:grid;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.ml{display:block;width:100%;min-height:44px;padding:12px;border:0;border-right:1px solid var(--line);background:transparent;color:inherit;font:inherit;text-align:left;cursor:pointer}
.ml:last-child{border-right:0}
.ml:hover{background:var(--ov1)}
.ml:focus-visible{outline:2px solid var(--acc);outline-offset:-2px}
.ml-k{display:block;font-size:10px;letter-spacing:.06em;color:var(--tx3);font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ml-p{display:block;margin-top:4px;font-size:16px;font-weight:800;color:var(--acc);letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.ml-p i{font-style:normal;font-size:10px;font-weight:700;color:var(--tx2);margin-left:2px;letter-spacing:.02em}
.ml-calc{display:inline-flex;align-items:center;justify-content:center;width:14px;height:14px;margin-left:4px;vertical-align:-2px;color:var(--tx2)}
.ml-calc svg{display:block;width:12px;height:12px}
.ml:hover .ml-calc{color:var(--acc)}
.ml-v{display:block;margin-top:2px;font-size:10px;color:var(--tx2);font-variant-numeric:tabular-nums;white-space:nowrap}
.ml-bar{display:block;margin-top:8px;height:3px;border-radius:2px;background:var(--ov2);overflow:hidden}
.ml-bar i{display:block;height:100%;border-radius:2px;background:var(--acc);transition:width var(--mo) var(--ease)}
.pcalc{position:fixed;inset:0;z-index:60;display:flex;align-items:flex-end;justify-content:center;padding:12px;background:rgba(0,0,0,.55)}
.pcalc[hidden]{display:none}
.pcalc-b{width:100%;max-width:520px;max-height:calc(100vh - 24px);overflow:auto;padding:14px 14px calc(14px + env(safe-area-inset-bottom));border:1px solid var(--line);border-radius:2px;background:var(--panel);color:var(--ink)}
.pcalc-h{display:flex;align-items:center;justify-content:space-between;gap:8px;padding-bottom:8px;border-bottom:1px solid var(--line2)}
.pcalc-h h2{margin:0;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--ink)}
.pcalc-x{width:44px;height:44px;margin:-8px -10px -8px 0;border:0;background:transparent;color:var(--tx2);font:inherit;font-size:18px;line-height:1;cursor:pointer}
.pcalc-x:hover{color:var(--ink)}
.pcalc-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:end;margin-top:10px}
.pcalc-f{min-width:0}
.pcalc-k{display:block;font-size:9px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--tx2)}
.pcalc-in,.pcalc-sel{width:100%;min-height:44px;margin-top:4px;padding:0 10px;border:1px solid var(--line2);border-radius:2px;background:var(--panel2);color:var(--ink);font:inherit;font-size:16px;font-weight:700;font-variant-numeric:tabular-nums}
.pcalc-sel{width:auto;min-width:92px;font-size:13px}
.pcalc-o{margin-top:14px;padding-top:10px;border-top:1px solid var(--line2)}
.pcalc-g + .pcalc-g{margin-top:10px}
.pcalc-plates{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;min-height:44px}
.pcalc-p{display:inline-flex;align-items:center;justify-content:center;min-width:44px;height:44px;padding:0 8px;border:1px solid var(--line2);border-radius:2px;font-size:13px;font-weight:800;font-variant-numeric:tabular-nums}
.pcalc-p i{font-style:normal;font-size:9px;font-weight:700;color:var(--tx2);margin-left:2px}
.pcalc-p.bar{border-color:var(--accLine);background:var(--accSoft);color:var(--acc)}
.pcalc-note{margin:10px 0 0;min-height:1.4em;font-size:11px;color:var(--tx2)}
.pcalc-done{width:100%;min-height:44px;margin-top:12px;border:1px solid var(--accLine);border-radius:2px;background:var(--accSoft);color:var(--acc);font:inherit;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;cursor:pointer}
.brief-empty{padding:12px 16px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-size:11px;color:var(--tx3)}
.brief-foot{display:flex;align-items:flex-end;gap:8px;padding:12px 16px 12px}
.brief-foot + .brief-foot{border-top:1px solid var(--line);padding-top:8px}
.bf-l{flex:1 1 auto;min-width:0}
.bf-l span{display:block;font-size:10px;letter-spacing:.08em;color:var(--tx3);font-weight:700}
.bf-l em{display:block;font-style:normal;font-size:10px;color:var(--tx3);margin-top:2px}
.vol{flex:0 0 auto;font-size:26px;font-weight:800;letter-spacing:-.03em;line-height:1;font-variant-numeric:tabular-nums}
.vol b{font:inherit;letter-spacing:inherit}
.vol.zero{color:var(--tx3)}
.vol span{font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.08em;margin-left:2px}
.sec{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin:24px 2px 8px}
.sec h2{margin:0;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--tx2);font-weight:700}
.sec span{font-size:10px;color:var(--tx3);font-variant-numeric:tabular-nums;letter-spacing:.08em}
.sec span a{display:inline-block;min-width:44px;text-align:right;padding:15px 0;margin:-15px 0}
.gear{margin:0 0 2px}
.gsum{display:grid;grid-template-columns:minmax(0,1fr) auto;align-content:center;row-gap:2px;width:100%;min-height:44px;margin:20px 0 0;padding:0 13px;border:0;background:transparent;color:var(--ink);font:inherit;text-align:left;cursor:pointer}
.gsum-k{grid-column:1;grid-row:1;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--tx2);font-weight:700}
.gsum-v{grid-column:1;grid-row:2;font-size:10px;color:var(--tx2);font-variant-numeric:tabular-nums;letter-spacing:.08em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gsum-x{grid-column:2;grid-row:1/span 2;align-self:center;font-size:14px;font-weight:700;color:var(--tx2)}
.gwrap{display:grid;grid-template-rows:1fr;overflow:hidden;transition:grid-template-rows .28s var(--ease)}
.gear.js .gwrap{grid-template-rows:0fr}
.gear.js.open .gwrap{grid-template-rows:1fr}
.gear.open .glayers{padding:10px 0 2px}
.gwrap>.glayers{overflow:hidden;min-height:0}
.gear-c .gsum{margin-top:24px}
.gear-groups{display:grid;gap:8px}
.gg{border:1px solid var(--accLine);border-radius:2px;background:var(--accSoft);padding:8px 12px;min-width:0}
.gg-head{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.gg-head span{font-size:10px;letter-spacing:.08em;font-weight:800;color:var(--acc)}
.gg-head b{font-size:14px;font-weight:800;color:var(--acc);font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.gg-items{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
.gchip{display:inline-flex;align-items:center;border:1px solid var(--accLine);border-radius:2px;padding:4px 8px;font-size:11px;font-weight:700;background:var(--k20);white-space:nowrap}
.glayers{display:grid;gap:8px}
.glayer{border:1px solid var(--line);border-radius:2px;background:var(--panel);padding:8px 12px;min-width:0}
.glayer.req{border-color:var(--accLine);background:linear-gradient(180deg,var(--accSoft),var(--panel))}
.glayer.always{background:var(--panel2)}
.glayer.high{border-color:var(--hotLine);background:linear-gradient(180deg,var(--hotSoft),var(--panel))}
.glayer.opt{border-style:dashed;border-color:var(--line2);background:transparent;padding:8px 12px}
.gl-h{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:8px}
.gl-h span{font-size:10px;letter-spacing:.08em;font-weight:800;color:var(--acc);text-transform:uppercase}
.glayer.always .gl-h span{color:var(--tx2)}
.glayer.high .gl-h span{color:var(--hot)}
.glayer.opt .gl-h span{color:var(--tx3);font-size:10px}
.gl-h em{font-style:normal;font-size:10px;color:var(--tx2);letter-spacing:.03em;text-align:right}
.grow{display:flex;flex-wrap:wrap;gap:4px}
.gitem{display:inline-flex;align-items:baseline;gap:4px;border:1px solid var(--line2);border-radius:2px;padding:4px 8px;font-size:11px;font-weight:700;color:var(--tx2);white-space:nowrap}
.gitem em{font-style:normal;font-size:10px;color:var(--tx2);font-weight:600}
.gitem.res{display:inline-block;max-width:100%;white-space:normal;padding:4px 8px}
.gitem.res b{display:block;font:inherit;font-weight:800}
.gitem.res em{display:block;margin-top:2px;line-height:1.35;color:var(--tx2)}
.sup-head{padding:2px 2px 10px}
.sup-head h2{margin:0;font-size:12px;font-weight:800;line-height:1.35;letter-spacing:.01em;overflow-wrap:anywhere}
.sup-head p{margin:4px 0 0;font-size:11px;line-height:1.5;color:var(--tx3);overflow-wrap:anywhere}
.sup-g .gl-h{margin:0}
.sup-list{display:grid;gap:8px}
.supcard{border:1px solid var(--line2);border-radius:2px;background:var(--panel);padding:8px 10px;min-width:0}
.sup-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px}
.sup-h h4{margin:0 0 0 0;font-size:12px;font-weight:800;color:var(--ink);min-width:0;overflow-wrap:anywhere}
.sup-chip{font-size:9px;letter-spacing:.06em;font-weight:800;color:var(--tx3);border:1px solid var(--line2);border-radius:2px;padding:1px 4px;text-transform:uppercase;white-space:nowrap}
.sup-chip.ev{color:var(--acc);border-color:var(--accLine)}
.sup-p{margin:6px 0 0;font-size:11px;line-height:1.45;color:var(--tx2);overflow-wrap:anywhere}
.sup-p b{display:block;margin-bottom:1px;font-size:9px;letter-spacing:.08em;color:var(--tx3);font-weight:800;text-transform:uppercase}
.sup-p em{font-style:normal;color:var(--tx3)}
.sup-rel{display:block;margin-top:3px;color:var(--tx3)}
.sup-foot{margin:2px 0 0;font-size:10px;line-height:1.45;color:var(--tx3);overflow-wrap:anywhere}
.day-share-row{display:flex;justify-content:flex-end;margin:20px 0 4px}
.day-share{display:inline-flex;align-items:center;justify-content:center;gap:8px;flex:none;min-height:44px;min-width:44px;padding:0 14px;border:1px solid var(--line);border-radius:2px;background:transparent;color:var(--ink);font:inherit;font-size:13px;font-weight:700;letter-spacing:.02em;cursor:pointer}
.day-share:hover{border-color:var(--acc);color:var(--acc)}
.day-share:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.day-share[disabled]{opacity:.55;cursor:default}
.glayer.opt .gitem{border-style:dashed;color:var(--tx3);font-size:10px;font-weight:600;padding:2px 8px}
.gempty{margin:0;font-size:10px;color:var(--tx2)}
.gear-c{margin:24px 0 4px}
.gear-c .sec{margin:0 0 8px}
.gearc{border:1px solid var(--line);border-radius:2px;background:var(--panel);overflow:hidden}
.gearc>summary{list-style:none;cursor:pointer;display:grid}
.gearc>summary::-webkit-details-marker{display:none}
.gcx{display:block;padding:0 12px 8px;font-size:10px;letter-spacing:.08em;color:var(--acc);font-weight:700}
.gearc[open] .gcx{display:none}
.gearc .glayers{padding:2px 8px 12px}
.pmini{margin-top:8px;border-top:1px solid var(--accLine);padding-top:8px}
.pmini-h{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:8px}
.pmini-h span{font-size:10px;letter-spacing:.06em;font-weight:800;color:var(--acc)}
.pmini-h em{font-style:normal;font-size:10px;color:var(--tx3)}
.pcab + .pcab{margin-top:8px;padding-top:8px;border-top:1px solid var(--line)}
.pcab-h{display:flex;align-items:flex-start;gap:8px;min-width:0}
.pcab-h > span{flex:0 0 auto;font-size:10px;letter-spacing:.06em;font-weight:800;color:var(--acc);padding-top:2px}
.pcab-loads{display:flex;flex-direction:column;gap:2px;min-width:0}
.pcab-loads span{font-size:10px;color:var(--tx3);font-variant-numeric:tabular-nums}
.pcab-loads b{font-size:12px;font-weight:800;color:var(--ink)}
.pcab-loads i{font-style:normal;font-weight:800;color:var(--acc)}
.pcab-loads em{display:block;font-style:normal;font-size:10px;color:var(--tx3);margin-top:2px}
.pcab-rack{display:flex;gap:8px;margin-top:8px}
.plate{width:40px;height:40px;border-radius:50%;border:2px solid var(--line2);background:radial-gradient(circle at 36% 28%,var(--panel2),var(--panel) 70%);display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1;color:var(--tx2);box-shadow:inset 0 0 0 3px var(--k22)}
.plate b{font-size:11px;font-weight:800;letter-spacing:-.03em}
.plate.on{border-color:var(--accLineStrong);color:var(--acc);background:radial-gradient(circle at 36% 28%,rgba(var(--accRgb),.26),rgba(var(--accRgb),.04) 70%),var(--panel);box-shadow:inset 0 0 0 3px rgba(var(--accRgb),.10),0 0 0 3px rgba(var(--accRgb),.05)}
.plate.on i{color:rgba(var(--accRgb),.9)}
.card{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:2px;padding:12px 16px;margin-bottom:8px;min-width:0}
.card.main{border-color:var(--line);padding-left:16px}
.card.main::before{content:"";position:absolute;left:0;top:13px;bottom:13px;width:3px;border-radius:2px;background:var(--mainCol)}
.card.main.equip::before{width:5px;background:var(--mainStrong)}
.card.main .c-name{font-size:14px;font-weight:800}
.card.main .c-cat{color:var(--mainCol);font-weight:800}
.card.main.equip .c-cat{color:var(--mainStrong)}
.card.var{border-color:var(--line);padding-left:16px}
.card.var::before{content:"";position:absolute;left:0;top:13px;bottom:13px;width:3px;border-radius:2px;background:var(--varCol)}
.card.var .c-name{font-size:14px;font-weight:700}
.card.var .c-cat{color:var(--varCol);font-weight:800}
.card.var .rx-tag{color:var(--varCol)}
.card.acc{padding-left:16px}
.card.acc::before{content:"";position:absolute;left:0;top:13px;bottom:13px;width:3px;border-radius:2px;background:var(--accCol)}
.card.acc .c-name{font-size:12px;font-weight:700;color:var(--ink)}
.card.acc .c-cat{color:var(--accCol);font-weight:800}
.card.acc .rx-sr{font-size:12px;color:var(--tx2)}
.c-gear{display:inline-block;margin-left:6px;padding:1px 4px;border:1px solid var(--mainStrong);border-radius:2px;font-size:10px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--mainStrong);vertical-align:1px}
.c-head{display:flex;align-items:flex-start;gap:8px;min-width:0}
.c-idx{flex:0 0 auto;margin-top:2px;font-size:10px;font-weight:800;color:var(--tx3);letter-spacing:.06em;font-variant-numeric:tabular-nums}
.c-id{flex:1 1 auto;min-width:0}
.c-name{font-size:14px;font-weight:800;letter-spacing:-.01em;line-height:1.25;overflow-wrap:anywhere}
.c-cat{margin-top:2px;font-size:10px;letter-spacing:.06em;color:var(--tx3);text-transform:uppercase;font-weight:600}
.c-rpe{flex:0 0 auto;margin-top:2px;font-size:10px;font-weight:800;letter-spacing:.08em;color:var(--acc);border:1px solid var(--accLine);border-radius:2px;padding:2px 8px;white-space:nowrap}
.rx{margin-top:12px;padding-top:8px;border-top:1px solid var(--line);display:grid;gap:8px}
.rx-row{display:flex;align-items:baseline;gap:8px;min-width:0}
.rx-tag{flex:0 0 58px;font-size:10px;letter-spacing:.06em;font-weight:800;text-transform:uppercase;color:var(--tx3);white-space:nowrap}
.card.main .rx-tag{color:var(--hot)}
.rx-sr{flex:0 0 auto;font-size:14px;font-weight:800;letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.rx-sr em{font-style:normal;font-size:10px;font-weight:600;color:var(--tx2);letter-spacing:0}
.rx-sr em.rpe{font-size:10px;color:var(--tx3);white-space:nowrap;letter-spacing:.01em}
.rx-kg{margin-left:auto;font-size:16px;font-weight:800;font-variant-numeric:tabular-nums;white-space:nowrap}
.rx-kg i{font-style:normal;font-size:10px;font-weight:600;color:var(--tx3);margin-left:2px}
.rx-kg.bw{font-size:11px;color:var(--tx2);letter-spacing:.06em}
.rx-pct{flex:0 0 46px;text-align:right;font-size:10px;color:var(--tx3);font-variant-numeric:tabular-nums;white-space:nowrap}
/* Full-log mode is opt-in: the page stays read-only until the reader asks for
   it. The four fields use minmax(0,1fr) so a long entry shrinks instead of
   pushing the card past the viewport (the Sheiko table failure). */
.logbar{display:flex;justify-content:flex-end;margin:0 2px 10px}
.logbtn{display:inline-flex;align-items:center;min-height:44px;padding:0 12px;border:1px solid var(--line);border-radius:2px;background:var(--panel);color:var(--tx2);font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;cursor:pointer}
.logbtn:hover{color:var(--ink)}
.logbtn[aria-pressed="true"]{border-color:var(--accLine);background:var(--accSoft);color:var(--acc)}
html[data-view="max"] .rx-log{display:grid;grid-template-columns:40px repeat(4,minmax(0,1fr));gap:6px;align-items:end}
.lg-tag{align-self:end;height:44px;display:flex;align-items:center;font-size:9px;font-weight:800;letter-spacing:.08em;color:var(--tx2)}
.rx-log.has .lg-tag{color:var(--acc)}
.lg{display:flex;flex-direction:column;gap:5px;min-width:0}
.lg>span{font-size:9px;font-weight:700;letter-spacing:.06em;color:var(--tx2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lg>span em{font-style:normal;font-weight:500;margin-left:3px}
.lg input{width:100%;min-width:0;height:44px;padding:0 2px;border:1px solid var(--line);border-radius:2px;background:var(--ov2);color:var(--ink);text-align:center;font:inherit;font-size:16px;font-weight:800;font-variant-numeric:tabular-nums;-moz-appearance:textfield}
.lg input::-webkit-outer-spin-button,.lg input::-webkit-inner-spin-button{-webkit-appearance:none;margin:0}
.lg input:focus{outline:2px solid var(--acc);outline-offset:-2px;border-color:var(--accLine)}
.rx-log.has .lg input{border-color:var(--accLine);background:var(--panel2)}
.lognote{display:none;margin:10px 0 0;font-size:10px;color:var(--tx2);letter-spacing:.02em}
html[data-view="max"] .lognote{display:block}
@media(max-width:360px){
  html[data-view="max"] .rx-log{grid-template-columns:30px repeat(4,minmax(0,1fr));gap:4px}
}
.cue{margin:8px 0 0;font-size:11px;line-height:1.5;color:var(--tx3);overflow-wrap:anywhere}
/* Accessory header: the prescription in one glance. Sets x reps and the target
   RPE on the first line, the reverse-engineered intensity on the second. */
.c-est{flex:0 0 auto;max-width:52%;text-align:right;font-variant-numeric:tabular-nums;line-height:1.25}
.c-est b{display:block;font-size:10px;font-weight:800;letter-spacing:.02em;color:var(--tx2);white-space:nowrap}
.c-est em{display:block;margin-top:1px;font-style:normal;font-size:10px;font-weight:800;letter-spacing:.02em;color:var(--accCol);white-space:nowrap}
/* Notes are reference text, not a step: collapsed by default so the card ends
   at the prescription. */
.cnote{margin:10px 0 0;border-top:1px solid var(--line);padding-top:2px}
.cnote>summary{display:flex;align-items:center;gap:8px;min-height:44px;list-style:none;cursor:pointer;font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--tx3)}
.cnote>summary::-webkit-details-marker{display:none}
.cnote>summary:focus-visible{outline:2px solid var(--acc);outline-offset:-2px}
.cnote>summary .x{margin-left:auto;font-size:12px;font-weight:600;line-height:1;color:var(--tx2);transition:transform var(--mo) var(--ease)}
.cnote[open]>summary .x{transform:rotate(45deg)}
.cnote .cue{margin:0 0 8px}
.nav{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:16px 0 0}
.nav>a,.nav>div{display:block;border:1px solid var(--line);border-radius:2px;padding:8px 12px;background:var(--panel);min-width:0}
.nav .l{font-size:10px;letter-spacing:.06em;color:var(--tx3);text-transform:uppercase;font-weight:700}
.nav .v{margin-top:4px;font-size:11px;font-weight:700;overflow-wrap:anywhere}
.nav .n2{text-align:right}
.skel{display:grid;gap:10px;margin:18px 0 0}
.skel i{display:block;height:14px;border-radius:2px;background:var(--ov3)}
.skel i:nth-child(1){width:62%}
.skel i:nth-child(2){width:84%}
.skel i:nth-child(3){width:46%}
.foot{margin-top:24px;padding-top:12px;border-top:1px solid var(--line);font-size:10px;color:var(--tx3);line-height:1.7;overflow-wrap:anywhere}
.fanc{display:block;margin-bottom:4px;color:var(--tx2);font-variant-numeric:tabular-nums;letter-spacing:.02em}
.fanc b{color:var(--ink);font-weight:800}
.fanc i{font-style:normal;color:var(--tx3)}
.fanc.none{color:var(--tx3)}
.foot a{display:inline-block;min-width:44px;padding:15px 0;margin:-15px 0;color:var(--tx2)}
html[data-lang="zh"] .foot a{display:block;width:max-content;margin:2px 0 0;padding:14px 0}
.friends{display:flex;flex-wrap:wrap;align-items:center;gap:0 14px;margin-top:10px;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--tx3)}
.friends span{font-weight:800;letter-spacing:.1em}
.friends a{display:inline-flex;align-items:center;min-height:44px;min-width:44px;color:var(--tx2)}
.friends a:hover{color:var(--ink)}
.fold-body{padding:2px 2px 12px;font-size:11px;color:var(--tx3);line-height:1.55}
.ramp + .ramp{margin-top:8px}
.ramp-h{display:flex;align-items:baseline;gap:8px;font-size:10px;letter-spacing:.06em;font-weight:800;color:var(--tx3);text-transform:uppercase}
.ramp-h b{font-size:10px;color:var(--tx2);letter-spacing:0;font-variant-numeric:tabular-nums}
.ramp-steps{display:flex;flex-wrap:wrap;gap:4px 4px;margin-top:4px}
.ramp-step{border:1px solid var(--line);border-radius:2px;padding:2px 8px;font-size:10px;color:var(--tx3);font-variant-numeric:tabular-nums;white-space:nowrap}
.ramp-step b{color:var(--tx2);font-weight:700}
.warm-fold{margin:12px 2px 12px}
.warm-fold>summary em{font-weight:600;color:var(--tx2)}
.wsub{font-size:10px;letter-spacing:.06em;font-weight:800;text-transform:uppercase;color:var(--tx3)}
.wlist + .wsub,.ramp + .wsub{margin-top:14px}
.wlift{display:block;margin:8px 0 1px;font-size:9px;letter-spacing:.1em;font-weight:800;text-transform:uppercase;color:var(--acc)}
.wlist{margin:2px 0 0;padding:0;list-style:none}
.wlist li{padding:4px 0;border-top:1px solid var(--line)}
.wlist li:first-child{border-top:0}
.wname{display:block;font-size:11px;font-weight:600;color:var(--tx2)}
.wev{margin-left:6px;font-style:normal;font-size:9px;font-weight:600;letter-spacing:.04em;color:var(--tx3);border:1px solid var(--line);border-radius:2px;padding:0 4px;white-space:nowrap}
.wdose{display:block;font-size:10px;color:var(--tx2);font-variant-numeric:tabular-nums}
.wwhy{display:block;margin-top:1px;font-style:normal;font-size:10px;line-height:1.35;color:var(--tx2)}
.wtip{margin:6px 0 2px;padding:5px 8px;border-left:2px solid var(--accLine);background:var(--accSoft);font-size:10px;line-height:1.4;color:var(--tx3)}
.wcaution{margin:7px 0 0;padding-top:6px;border-top:1px dashed var(--line);font-size:10px;line-height:1.45;color:var(--tx3)}
.wcaution b{font-weight:600;color:var(--tx3)}
.wcaution span{opacity:.92}
.inj{margin:0;padding:0;list-style:none}
.inj li{padding:4px 0;border-top:1px dashed var(--line)}
.inj li:first-child{border-top:0;padding-top:0}
.inj b{font-size:10px;letter-spacing:.06em;font-weight:800;color:var(--tx3);text-transform:uppercase;margin-right:4px}
.inj em{font-style:normal;color:var(--tx3)}
@media (max-width:390px){
  .mast-r>span{display:none}
  .eyebrow .edate{display:inline}
}
@media (max-width:360px){
  body{padding-left:12px;padding-right:12px}
  .hero{padding:16px 0 16px}
  .card{padding:12px 12px}
  .card.main{padding-left:16px}
  .rx-tag{flex-basis:48px}
  .rx-pct{flex-basis:42px}
  .vol{font-size:20px}
  .ml{padding:8px 8px}
}
/* One skeleton for the four rows that close a training day: ENGINE TOMORROW,
   ENGINE, FRAME/RESET and INJURY WATCH. Same 12px inset, same 44px height,
   same 2px radius. The value (.v) is the only flexible cell and it is pushed
   right; the trailing glyph (.x) owns a fixed 16px column, so every right edge
   lines up no matter whether the row is a link or a fold. */
.mskel{display:flex;align-items:center;gap:8px;width:100%;min-width:0;min-height:44px;padding:0 12px;border:1px solid var(--line);border-radius:2px;background:var(--k14);font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--tx3)}
.mskel .k{flex:0 0 auto;min-width:0;font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--tx2);white-space:nowrap}
.mskel .v{margin-left:auto;min-width:0;font-style:normal;font-size:10px;font-weight:700;letter-spacing:.03em;text-transform:none;color:var(--tx2);font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right}
.mskel .x{flex:0 0 16px;width:16px;text-align:center;font-size:12px;font-weight:600;line-height:1;color:var(--tx2);transition:transform var(--mo) var(--ease)}
details.mod{margin:8px 0 0;min-width:0}
details.mod>summary.mskel{list-style:none;cursor:pointer}
details.mod>summary.mskel::-webkit-details-marker{display:none}
details.mod>summary.mskel:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
details.mod[open]>summary.mskel{border-radius:2px 2px 0 0}
details.mod[open]>summary.mskel .x{transform:rotate(45deg)}
details.mod>.modb{padding:10px 12px 12px;border:1px solid var(--line);border-top:0;border-radius:0 0 2px 2px;background:var(--k14)}
details.mod.engine>summary.mskel .k{color:var(--acc)}
details.mod.inj>summary.mskel{color:var(--hot);background:var(--hotSoft);box-shadow:inset 3px 0 0 var(--hot)}
details.mod.inj>summary.mskel .k,details.mod.inj>summary.mskel .v,details.mod.inj>summary.mskel .x{color:var(--hot)}
details.mod.inj>.modb{background:var(--hotSoft);box-shadow:inset 3px 0 0 var(--hot)}
a.modline{margin:8px 0 0;cursor:pointer}
a.modline:hover{border-color:var(--tx3)}
a.modline:hover .v,a.modline:hover .x{color:var(--ink)}
.run-hero{padding:16px 0 12px;border-bottom:1px solid var(--line)}
.run-hero h1{margin:8px 0 0;font-size:20px;line-height:1.15;font-weight:700;letter-spacing:-.01em;color:var(--tx2)}
.run-rest{display:block;margin:16px 0 12px;padding:12px 12px;border:1px dashed var(--line2);border-radius:2px;font-size:10px;color:var(--tx2);overflow-wrap:anywhere}
.run-rest>span:first-child{display:block;margin-bottom:4px;font-size:10px;letter-spacing:.08em;font-weight:800;color:var(--tx2);text-transform:uppercase}
.run-card{border:1px solid var(--line);border-radius:2px;background:var(--panel);padding:12px 16px;margin-bottom:8px}
.run-top{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.run-top b{font-size:12px;font-weight:700;color:var(--tx2);letter-spacing:.01em;text-transform:uppercase}
.run-top span{font-size:10px;letter-spacing:.06em;color:var(--tx2);font-weight:700;text-transform:uppercase}
.run-big{display:flex;align-items:baseline;gap:4px;margin-top:8px}
.run-big b{font-size:20px;font-weight:700;letter-spacing:-.02em;line-height:1;color:var(--tx2);font-variant-numeric:tabular-nums}
.run-big i{font-style:normal;font-size:10px;letter-spacing:.06em;color:var(--tx2);font-weight:700;text-transform:uppercase}
.run-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px;border-top:1px solid var(--line);padding-top:8px}
.run-metrics>div>span{display:block;font-size:10px;letter-spacing:.06em;color:var(--tx2);font-weight:700;text-transform:uppercase}
.run-metrics b{display:block;margin-top:4px;font-size:12px;font-weight:800;color:var(--tx2);font-variant-numeric:tabular-nums;white-space:nowrap}
.run-cue{margin-top:12px;padding:8px 12px;border-left:2px solid var(--line2);border-radius:0 2px 2px 0;background:var(--ovL);font-size:11px;line-height:1.5;color:var(--tx2)}
.run-note{margin:12px 2px 0;font-size:10px;line-height:1.5;color:var(--tx2)}
.segwrap{display:flex;flex-wrap:wrap;gap:4px;margin:0 0 8px}
.segwrap>input{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}
.segwrap>label{flex:0 0 auto;display:inline-flex;align-items:center;min-height:44px;padding:4px 12px;border:1px solid var(--line2);border-radius:2px;font-size:10px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--tx3);cursor:pointer}
.segwrap>label:hover{color:var(--tx2);border-color:var(--tx3)}
.segwrap>input:checked+label{background:var(--acc);border-color:var(--acc);color:var(--bg)}
.segwrap>input:focus-visible+label{outline:2px solid var(--acc);outline-offset:2px}
.seg-panels{flex:0 0 100%;display:block}
.seg-panel{display:none;padding-top:2px}
.seg-panel li a{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:44px}
.segwrap>input:nth-of-type(1):checked~.seg-panels>.seg-panel:nth-child(1),
.segwrap>input:nth-of-type(2):checked~.seg-panels>.seg-panel:nth-child(2),
.segwrap>input:nth-of-type(3):checked~.seg-panels>.seg-panel:nth-child(3),
.segwrap>input:nth-of-type(4):checked~.seg-panels>.seg-panel:nth-child(4){display:block}
.gppl-rx{margin:0;padding:8px 12px;border:1px solid var(--line);border-radius:2px;background:var(--panel);font-size:11px;line-height:1.5;color:var(--tx2)}
.gppl-rx b{display:block;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--tx3);margin-bottom:2px}
.gppl-note{margin:8px 2px 0;font-size:11px;line-height:1.5;color:var(--tx3)}
.gppl-base{margin:10px 2px 0;padding-top:8px;border-top:1px dashed var(--line);font-size:11px;line-height:1.5;color:var(--tx3)}
.gppl-base b{font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--tx2);margin-right:8px}
.wk-more{margin:-4px 2px 8px;padding-top:8px;border-top:1px dashed var(--line);font-size:10px;color:var(--tx3)}
.wk-more>summary{display:flex;align-items:center;gap:8px;cursor:pointer;list-style:none;min-height:44px;font-size:11px;line-height:1.45;letter-spacing:.02em}
.wk-more>summary::-webkit-details-marker{display:none}
.wk-more>summary span{flex:0 0 auto;font-size:10px;font-weight:800;letter-spacing:.08em;color:var(--tx3);text-transform:uppercase}
.wk-more>summary em{font-style:normal;font-size:10px;color:var(--tx3);min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wk-more>summary b{margin-left:auto;font-size:12px;font-weight:600;line-height:1;color:var(--tx2);transition:transform var(--mo) var(--ease)}
.wk-more[open]>summary b{transform:rotate(45deg)}
.wm-body{padding:8px 0 2px}
.wm-sec + .wm-sec{margin-top:12px;padding-top:8px;border-top:1px solid var(--line)}
.wm-sec h4{margin:0 0 4px;display:flex;align-items:baseline;gap:4px;font-size:10px;letter-spacing:.08em;text-transform:uppercase;font-weight:800;color:var(--tx2)}
.wm-sec h4 em{font-style:normal;font-size:10px;letter-spacing:.06em;color:var(--tx3);font-weight:600;text-transform:none}
.wm-sec ul{list-style:none;margin:0;padding:0;display:grid;gap:2px}
.wm-sec li{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:44px;font-size:11px;line-height:1.4;color:var(--tx3)}
.wm-sec li a{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;min-width:0;min-height:44px;color:inherit}
.wm-sec li a b{text-decoration:underline;text-decoration-color:var(--ov3);text-underline-offset:2px}
.wm-sec li b{font-weight:600;color:var(--tx2);min-width:0}
.accfold{margin:24px 2px 0;padding-top:0;border-top:0}
.accfold>summary em,.accfold>summary em span{font-size:10px;font-weight:600;text-transform:none;letter-spacing:.1px;color:var(--tx2);white-space:normal;text-overflow:clip}
.accfold>summary>span>span{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3)}
.accfold .wm-body{display:grid;gap:8px;padding-top:10px}
.gpp-cap{margin:8px 0 0;min-width:0}
.gpp-cap>summary{display:flex;align-items:center;gap:8px;width:100%;min-width:0;min-height:44px;padding:0 12px;border:1px solid var(--accLine);border-radius:2px;background:var(--accSoft);cursor:pointer;list-style:none}
.gpp-cap>summary::-webkit-details-marker{display:none}
.gpp-cap>summary:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.gpp-cap-k{font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--acc)}
.gpp-cap-v{margin-left:auto;font-style:normal;font-size:11px;font-weight:700;letter-spacing:.02em;color:var(--tx2);font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gpp-cap>summary b{margin-left:6px;font-size:12px;font-weight:600;line-height:1;color:var(--acc);transition:transform var(--mo) var(--ease)}
.gpp-cap[open]>summary{border-radius:2px 2px 0 0}
.gpp-cap[open]>summary b{transform:rotate(45deg)}
.gpp-cap .wm-body{padding:10px 12px 12px;border:1px solid var(--accLine);border-top:0;border-radius:0 0 2px 2px;background:var(--k14)}
.gpp-fine{margin:8px 0 0}
.gpp-fine>summary{display:flex;align-items:center;gap:8px;min-height:44px;padding:0 12px;border:1px solid var(--line);border-radius:2px;background:var(--k14);cursor:pointer;list-style:none;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--tx3)}
.gpp-fine>summary::-webkit-details-marker{display:none}
.gpp-fine>summary:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.gpp-fine[open]>summary{border-radius:2px 2px 0 0}
.gpp-fine>summary b{margin-left:auto;font-size:12px;font-weight:600;line-height:1;color:var(--tx2);transition:transform var(--mo) var(--ease)}
.gpp-fine[open]>summary b{transform:rotate(45deg)}
.gpp-groups{display:grid;gap:10px;padding:8px 12px 4px;border:1px solid var(--line);border-top:0;border-radius:0 0 2px 2px;background:var(--k14)}
.gpp-g h4{margin:0 0 2px;font-size:10px;letter-spacing:.08em;text-transform:uppercase;font-weight:800;color:var(--tx2)}
.inj-alert{margin:8px 0 0;border:1px solid var(--hotLine);border-left:3px solid var(--hot);border-radius:2px;background:var(--hotSoft)}
.inj-alert>summary{display:flex;align-items:center;gap:8px;min-height:44px;padding:0 12px;cursor:pointer;list-style:none;font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--hot)}
.inj-alert>summary::-webkit-details-marker{display:none}
.inj-alert>summary:focus-visible{outline:2px solid var(--hot);outline-offset:-2px}
.inj-alert>summary em{margin-left:auto;font-style:normal;font-size:10px;font-weight:600;letter-spacing:.04em;text-transform:none;color:var(--hot)}
.inj-alert>summary b{margin-left:6px;font-size:12px;font-weight:600;line-height:1;color:var(--hot);transition:transform var(--mo) var(--ease)}
.inj-alert[open]>summary b{transform:rotate(45deg)}
.inj-alert .fold-body{padding:2px 12px 12px}
.wm-sec li span{flex:0 0 auto;font-variant-numeric:tabular-nums;color:var(--tx3)}
.wm-empty{margin:0;font-size:11px;line-height:1.45;color:var(--tx2)}
.rise{animation:rise var(--mo) var(--ease) both;animation-delay:var(--d,0ms)}
@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.001ms!important;animation-delay:0ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important;scroll-behavior:auto!important}
}
/* Scroll reveal: the hidden state only exists once JS has both attached the
   class and created the observer, so no-JS and script errors leave content
   readable. Reduced motion opts out entirely. */
@media(prefers-reduced-motion:no-preference){
  .rv{opacity:0;transform:translateY(10px);transition:opacity .46s var(--ease),transform .46s var(--ease)}
  .rv.in{opacity:1;transform:none}
}"""

REVEAL_JS = (
    '<script>(function(){'
    'if(!window.IntersectionObserver)return;'
    'if(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches)return;'
    'var els=[].slice.call(document.querySelectorAll(".wrap>*"));'
    'els=els.filter(function(el){'
    'if(el.tagName==="SCRIPT"||el.tagName==="STYLE")return false;'
    'if(el.hasAttribute("hidden"))return false;'
    'if(el.classList.contains("mast")||el.classList.contains("rise"))return false;'
    'return el.getBoundingClientRect().top>innerHeight*0.9;});'
    'if(!els.length)return;'
    'els.forEach(function(el){el.classList.add("rv");});'
    'var io=new IntersectionObserver(function(es){es.forEach(function(e){'
    'if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target);}});'
    '},{rootMargin:"0px 0px -8% 0px",threshold:0.08});'
    'els.forEach(function(el){io.observe(el);});'
    '})();</script>'
)

PLAN_CSS = """.hero{padding:12px 0 12px}
/* The tier capsule rides the h1 row, not the masthead: the mast has no free
   space at 320-412 (adding it forces .mast-r onto a second line and shifts
   the page by 52px). The h1 line is 23-30px tall, so a 20px capsule fits
   inside it and the title row keeps its height whether or not the capsule
   is present. */
.hero-title{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:8px 0 0}
.hero-title h1{margin:0}
.hero-title .tier-slot{margin-left:0}
.tier-note{display:grid;grid-template-columns:minmax(0,1fr) 44px;grid-template-areas:"msg x" "act x";align-items:center;gap:4px 8px;margin:0 0 16px;padding:8px 12px;border:1px solid var(--accLine);border-left:3px solid var(--acc);border-radius:2px;background:var(--accSoft);color:var(--tierNote);font-size:11px;line-height:1.45;letter-spacing:.01em}
.tier-note[hidden]{display:none}
.tier-note .tn-msg{grid-area:msg;min-width:0;margin:0;overflow-wrap:anywhere}
.tier-note .tn-link{grid-area:act;justify-self:start;display:inline-flex;align-items:center;min-width:44px;min-height:44px;color:var(--acc);font-weight:800;font-size:10px;letter-spacing:.06em;text-transform:uppercase;white-space:nowrap}
.tier-note .tn-x{grid-area:x;align-self:center;display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;margin:0;border:0;background:transparent;color:var(--tx3);font-size:18px;line-height:1;cursor:pointer}
.tier-note .tn-x:hover,.tier-note .tn-x:focus-visible{color:var(--ink)}
.hero h1{font-size:clamp(20px,6.4vw,26px)}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:0 0 12px}
.stat{border:1px solid var(--line);border-radius:2px;background:var(--panel);padding:8px 12px;min-width:0}
.stat span{display:block;font-size:10px;letter-spacing:.02em;color:var(--tx3);text-transform:uppercase;font-weight:700}
.stat b{display:block;margin-top:4px;font-size:12px;font-weight:800;letter-spacing:.01em;font-variant-numeric:tabular-nums;overflow-wrap:anywhere;white-space:nowrap}
.stat i{display:block;margin-top:2px;font-style:normal;font-size:10px;color:var(--tx3);font-variant-numeric:tabular-nums}
.cap{margin:0 0 16px;border:1px solid var(--accLine);border-radius:2px;padding:16px 12px 12px;background:radial-gradient(130% 110% at 0% 0%,rgba(var(--accRgb),.07),rgba(var(--accRgb),0) 58%),linear-gradient(180deg,var(--panel2),var(--panel));box-shadow:inset 0 1px 0 var(--ov1)}
.cap-h{display:flex;align-items:flex-end;justify-content:space-between;gap:8px}
.cap-k{font-size:10px;letter-spacing:.08em;font-weight:800;color:var(--acc)}
.cap-t{margin:4px 0 0;font-size:16px;line-height:1.05;font-weight:800;letter-spacing:-.02em;text-transform:uppercase;white-space:nowrap}
.cap-t em{font-style:normal;color:var(--tx2);font-weight:600;letter-spacing:.06em;font-size:10px;margin-left:8px;text-transform:uppercase;vertical-align:middle}
.cap-mode{flex:0 0 auto;text-align:right;font-size:10px;letter-spacing:.06em;font-weight:800;color:var(--tx2);text-transform:uppercase;font-variant-numeric:tabular-nums}
.cap-list{display:grid;gap:2px;align-content:start;margin-top:12px}
.cap-gh{grid-column:1/-1;margin:8px 0 2px;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--tx2);font-weight:800}
.cap-gh:first-child{margin-top:0}
.cap-gh em{font-style:normal;color:var(--tx3);letter-spacing:.06em;font-weight:700;text-transform:none;margin-left:4px}
.cap-row{display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:8px;width:100%;min-height:44px;padding:4px 8px;border:0;border-radius:2px;background:transparent;color:inherit;font:inherit;text-align:left;cursor:pointer;transition:opacity var(--mo) var(--ease),background var(--mo) var(--ease),box-shadow var(--mo) var(--ease)}
.cap-row.single{grid-template-columns:1fr auto}
.cap-row.dual{grid-template-columns:1fr auto auto}
.cap-row .cr-bar{grid-column:1/-1}
.cap-row:active{background:var(--ov1)}
.cap-row.on{background:rgba(var(--accRgb),.11);box-shadow:inset 2px 0 0 var(--acc)}
.cap.dim .cap-row:not(.on) .cr-k b,.cap.dim .cap-row:not(.on) .cr-v b{color:var(--tx2)}
.cap.dim .cap-row:not(.on) .cr-k em,.cap.dim .cap-row:not(.on) .cr-v i{color:var(--tx3)}
.cap.dim .cap-row:not(.on) .cr-bar{opacity:.35}
.cr-k{min-width:0;display:flex;align-items:baseline;gap:4px}
.cr-k b{font-size:11px;font-weight:800;letter-spacing:.04em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cr-k em{font-style:normal;font-size:10px;letter-spacing:.06em;color:var(--tx2);font-weight:700;text-transform:uppercase;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cr-v{min-width:34px;text-align:right}
.cr-v b{display:block;font-size:12px;font-weight:800;line-height:1;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.cr-v i{display:block;margin-top:2px;font-style:normal;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--tx2);font-weight:700}
.cr-v.main b{font-size:14px}
.cr-v.sub b{font-size:11px;color:var(--tx2)}
.cr-v.sub i{color:var(--tx3)}
.cr-rng{grid-column:1/-1;display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-top:-1px;font-size:9px;letter-spacing:.05em;text-transform:uppercase;font-weight:800;color:var(--tx3);font-variant-numeric:tabular-nums}
.cr-rng b{font-weight:800;color:var(--tx2);white-space:nowrap}
.cr-rng em{font-style:normal;text-align:right;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cr-rng em.over{color:var(--hot)}
.cr-rng em.within{color:var(--acc)}
.cr-rng em.skip{color:var(--tx3);font-weight:700}
/* Tinted rows (.on) lift the background luminance, so secondary greys lose ~0.3-0.5
   of contrast there. These annotations carry the numbers people read, so they use
   ink2 on tinted surfaces and stay above 4.5 in all three themes. */
.cr-rng b,.cr-rng>em{color:var(--tx2s)}
.cr-rng em.over{color:var(--hot)}
.cr-rng em.within{color:var(--acc)}
.cap-row.on .cr-k>em,.cap-row.on .cr-v i>span{color:var(--tx2s)}
.cap-detail #capSub,.cap-detail #capRef, .cap-detail #capRefA,
.cap-detail #capCap,.cap-detail #capPrev,.cap-detail #capNext{color:var(--tx2s)}
.cb .cbv{color:var(--tx2s)}
.cb.on .cbv,.cb.on em{color:var(--tx2s)}
.cd-ref{margin:6px 0 0;font-size:10px;line-height:1.5;color:var(--tx3);letter-spacing:.01em}
.cd-ref span{display:block}
.cd-ref span:first-child{color:var(--tx2);font-weight:700;letter-spacing:.03em}
.cr-bar{display:block;height:3px;border-radius:2px;background:var(--ov2);overflow:hidden;margin-top:2px}
.cr-bar i{display:block;height:100%;border-radius:2px;background:linear-gradient(90deg,var(--acc),rgba(var(--accRgb),.36));transition:width var(--mo) var(--ease)}
.cap-detail{border:1px solid var(--line);border-radius:2px;background:var(--k20);padding:12px 12px 8px;min-width:0;margin-top:12px}
.cd-top{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.cd-top span{font-size:10px;letter-spacing:.08em;color:var(--tx2s);font-weight:800}
.cd-top b{font-size:10px;letter-spacing:.06em;color:var(--acc);font-weight:800;text-transform:uppercase}
.cd-num{display:flex;align-items:baseline;gap:8px;margin-top:4px;flex-wrap:wrap}
.cd-num b{font-size:32px;line-height:.95;font-weight:800;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.cd-num i{font-style:normal;font-size:10px;color:var(--tx2s);letter-spacing:.06em}
.cd-num em{font-style:normal;color:var(--acc);font-weight:800}
.cd-delta{margin-left:auto;font-size:10px;letter-spacing:.04em;font-weight:800;color:var(--tx2);white-space:nowrap;font-variant-numeric:tabular-nums}
.cd-delta.up{color:var(--acc)}
.cd-delta.down{color:var(--tx2)}
.cd-delta.flat{color:var(--tx3)}
.cd-delta.anim{animation:capDelta var(--mo) var(--ease)}
@keyframes capDelta{from{opacity:.35;transform:translateY(2px)}to{opacity:1;transform:none}}
.cd-rail{height:3px;border-radius:2px;background:var(--ov2);margin-top:8px;overflow:hidden}
.cd-rail i{display:block;height:100%;width:0;border-radius:2px;background:linear-gradient(90deg,var(--acc),rgba(var(--accRgb),.35));transition:width var(--mo) var(--ease)}
.cd-sub{margin-top:4px;font-size:10px;color:var(--tx2);letter-spacing:.04em;text-transform:uppercase;font-weight:700}
.cap-view{position:sticky;top:0;z-index:4;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0 4px;padding:8px 0 8px;background:linear-gradient(180deg,rgba(var(--panelRgb),.98) 70%,rgba(var(--panelRgb),.86))}.cap-list [hidden],.cap-row [hidden]{display:none!important}.cr-z{grid-column:2/4;text-align:right;font-size:10px;letter-spacing:.04em;color:var(--tx3)}
.cap-view button{height:44px;min-width:0;padding:0 2px;border:1px solid var(--line);border-radius:2px;background:var(--k14);color:var(--tx2);font-size:10px;letter-spacing:.04em;font-weight:800;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:background var(--mo) var(--ease),color var(--mo) var(--ease),border-color var(--mo) var(--ease),transform var(--mo) var(--ease)}
.cap-view button.on{background:var(--acc);border-color:var(--acc);color:var(--onAcc)}
.cap-view button:active{transform:scale(.97)}
@media(max-width:479px){.cap-view{position:static;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px}}
.cap-ctx{display:flex;align-items:center;gap:4px;margin-top:4px}
.cap-ctx button{height:44px;min-width:44px;padding:0 4px;border:1px solid var(--line);border-radius:2px;background:var(--k14);color:var(--tx2);font-size:10px;font-weight:800;cursor:pointer;font-variant-numeric:tabular-nums}
.cap-ctx #capAll{flex:0 0 52px;font-size:10px;letter-spacing:.1em}
.cap-ctx #capAll.on{background:var(--acc);border-color:var(--acc);color:var(--onAcc)}
.cap-ctx #capWk{flex:1;min-width:0;text-align:center;font-size:10px;letter-spacing:.06em;font-weight:800;color:var(--tx2);font-variant-numeric:tabular-nums}
.cap-ctx #capWk.muted{color:var(--tx3)}
.cd-cap{margin-top:8px;font-size:10px;letter-spacing:.06em;color:var(--tx2);text-transform:uppercase;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cap-chart{display:grid;grid-template-columns:repeat(var(--n,3),minmax(0,1fr));gap:2px;height:134px;margin-top:4px;align-items:end;transition:opacity var(--mo) var(--ease)}
.cap-chart.compact{gap:2px}
.cb{height:100%;display:flex;flex-direction:column;justify-content:flex-end;gap:2px;padding:0;border:0;background:transparent;cursor:pointer;min-width:0}
.cb.off{display:none}
.cbv{display:block;height:13px;line-height:13px;font-size:10px;text-align:center;color:var(--tx2);font-variant-numeric:tabular-nums;font-weight:800;white-space:nowrap;overflow:hidden}
.cap-chart.compact .cbv{display:none}
.cbi{display:flex;flex-direction:column-reverse;width:100%;border-radius:2px 2px 0 0;overflow:hidden;transform-origin:bottom center;transition:transform var(--mo) var(--ease)}
.cbi i{display:block;width:100%;height:0;transition:height var(--mo) var(--ease)}
.cbi .m{background:var(--acc)}
.cbi .v{background:rgba(var(--accRgb),.32)}
.cb.dl .cbi .m{background:rgba(167,176,187,.34)}
.cb.dl .cbi .v{background:rgba(167,176,187,.15)}
.cb.dl em{color:var(--tx3)}
.cb:active .cbi{opacity:.72}
.cb.on .cbi{box-shadow:0 0 0 1px var(--acc)}
.cb.cur .cbi{box-shadow:0 0 0 1px var(--acc)}
.cb.cur em{color:var(--acc);font-weight:800}
.cb.ts .cbi{outline:1px solid rgba(var(--accRgb),.55);outline-offset:2px;border-radius:2px}
.cb.ts .cbv{color:var(--acc)}
.cb em.d{color:var(--tx3)}
.cb em.t{color:var(--acc);font-weight:800}
.cb em{display:block;height:16px;line-height:16px;font-style:normal;font-size:12px;color:var(--tx2s);text-align:center;font-variant-numeric:tabular-nums;font-weight:700;white-space:nowrap;overflow:hidden}
.cb.ts em{color:var(--acc)}
.cap-empty{grid-column:1/-1;display:flex;align-items:center;gap:12px;margin:2px 0 4px;padding:8px 12px;border:1px dashed var(--line2);border-radius:2px;font-size:11px;line-height:1.45;color:var(--tx2);letter-spacing:.02em}
.ce-art{flex:0 0 40px;display:flex;align-items:flex-end;gap:2px;height:24px}
.ce-art i{flex:1;border-radius:0px;background:rgba(var(--accRgb),.16);box-shadow:inset 0 0 0 1px rgba(var(--accRgb),.18)}
.ce-art i:nth-child(1){height:8px}
.ce-art i:nth-child(2){height:18px}
.ce-art i:nth-child(3){height:12px}
.cap-row[data-zero="1"] .cr-bar{background:transparent;box-shadow:inset 0 0 0 1px var(--ov2)}
.cap-row[data-zero="1"] .cr-v b{color:var(--tx3)}
.cd-foot{min-height:42px;margin-top:8px}.cd-legend{display:flex;justify-content:space-between;gap:8px;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--tx2s);font-weight:700}
.cd-legend[hidden]{display:none}
.cap-note{margin-top:8px;font-size:10px;line-height:1.5;letter-spacing:.02em;text-transform:none;color:var(--tx2);font-weight:700}
.cap-note[hidden]{display:none}
.mmap{margin:0 0 16px;border:1px solid var(--line);border-radius:2px;background:var(--panel);padding:12px}
.mmh{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.mmk{font-size:10px;letter-spacing:.08em;font-weight:800;color:var(--acc)}
.mmt{margin:0;font-size:15px;font-weight:800;letter-spacing:-.02em;text-transform:uppercase}
.mmp{display:flex;align-items:center;gap:8px;margin-top:10px}
.mmp label{flex:0 0 auto;font-size:10px;letter-spacing:.08em;font-weight:800;color:var(--tx3)}
.mmp select{flex:1 1 auto;min-width:0;height:44px;padding:0 8px;border:1px solid var(--line2);border-radius:2px;background:var(--k14);color:var(--ink);font:inherit;font-size:11px;font-weight:700}
.mmg{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
.mmf{margin:0;border:1px solid var(--line);border-radius:2px;background:var(--k20);padding:4px;min-width:0}
.mmf figcaption{font-size:9px;letter-spacing:.1em;font-weight:800;color:var(--tx3);text-align:center;text-transform:uppercase}
.mmf svg{display:block;width:100%;height:auto;margin:0 auto}
.mb{fill:var(--ov1);stroke:var(--line)}
.mz{fill:var(--ov2);stroke:var(--line);stroke-width:.5}
.mz.t1{fill:var(--acc)}
.mz.t2{fill:rgba(var(--accRgb),.42)}
.mml{display:flex;flex-wrap:wrap;gap:4px 10px;margin-top:6px;font-size:9px;letter-spacing:.04em;text-transform:uppercase;color:var(--tx3);font-weight:700}
.mml i{display:inline-block;width:7px;height:7px;border-radius:1px;background:var(--ov2);margin-right:3px}
.mml i.p{background:var(--acc)}
.mml i.s{background:rgba(var(--accRgb),.42)}
.mmrs{border:1px solid var(--line);border-radius:2px;overflow:hidden;margin-top:12px}
.mmr{display:grid;grid-template-columns:minmax(0,1fr) 40px 50px 38px;gap:6px;align-items:center;padding:6px 9px;border-bottom:1px solid var(--line);min-height:34px;font-variant-numeric:tabular-nums}
.mmr:last-child{border-bottom:0}
.mmr.h{background:var(--k14);min-height:28px;padding:4px 9px}
.mmr.h span{font-size:9px;letter-spacing:.05em;color:var(--tx3);font-weight:800;text-transform:uppercase;text-align:right}
.mmr.h span:first-child{text-align:left}
.mmr .a{min-width:0;font-size:11px;font-weight:700;color:var(--tx2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mmr .b{display:inline-flex;align-items:center;justify-content:flex-end;gap:4px;font-size:10px;color:var(--tx3);font-weight:700}
.mmr .b:before{content:"";flex:0 0 auto;width:6px;height:6px;border-radius:1px;background:var(--ov2)}
.mmr .b.t1:before{background:var(--acc)}
.mmr .b.t2:before{background:rgba(var(--accRgb),.42)}
.mmr .c{text-align:right;font-size:12px;font-weight:800;color:var(--ink)}
.mmr .d{text-align:right;font-size:10px;font-weight:700;color:var(--tx3)}
.mmn{margin:6px 0 0;font-size:10px;line-height:1.45;color:var(--tx3)}
.mmsub{margin:2px 0 10px;font-size:10px;line-height:1.45;color:var(--tx3);letter-spacing:.02em}
.mmsub b{color:var(--tx2);font-variant-numeric:tabular-nums}
.mmns{margin:0;padding:0 0 0 16px;font-size:11px;line-height:1.75;color:var(--tx2)}
.mmns b{color:var(--ink);font-weight:700}
@media(max-width:340px){.mmr{grid-template-columns:minmax(0,1fr) 34px 44px 34px;gap:4px;padding:6px 7px}.mmt em{display:none}}
.mmref{margin-top:10px;border-top:1px solid var(--line);padding-top:2px}
.mmref>summary{display:flex;align-items:center;gap:6px;min-height:44px;list-style:none;cursor:pointer;font-size:9px;letter-spacing:.04em;text-transform:uppercase;font-weight:800;color:var(--tx2)}
.mmref>summary::-webkit-details-marker{display:none}
.mmref>summary::after{content:"+";margin-left:auto;color:var(--tx3);font-size:14px;line-height:1}
.mmref[open]>summary::after{content:"\u2013"}
.mmref>summary em{min-width:0;overflow:hidden;text-overflow:ellipsis;font-style:normal;color:var(--tx3);font-weight:700;letter-spacing:.03em;white-space:nowrap}
.mmrt{width:100%;table-layout:fixed;border-collapse:collapse;margin-top:2px;font-variant-numeric:tabular-nums}
.mmrsrc{margin:0 0 6px;font-size:9px;line-height:1.45;color:var(--tx3);letter-spacing:.01em}
.mmrt th,.mmrt td{padding:5px 3px;border-top:1px solid var(--line);text-align:right;vertical-align:top}
.mmrt th:first-child,.mmrt td:first-child{text-align:left;width:31%}
.mmrt th:nth-child(2),.mmrt td:nth-child(2){width:32%}
.mmrt th:nth-child(3),.mmrt td:nth-child(3){width:15%}
.mmrt thead th{font-size:8px;letter-spacing:.03em;text-transform:uppercase;color:var(--tx3);font-weight:800;border-top:0}
.mmrt td.lf{font-size:10px;font-weight:700;color:var(--tx2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mmrt td{font-size:10px;color:var(--tx2)}
.mmrt td.n{font-size:11px;font-weight:800;color:var(--ink)}
.mmrt td small{display:block;font-size:8px;font-weight:600;color:var(--tx3);letter-spacing:.01em;white-space:normal}
.mmrt td.n small.zf{text-align:left;margin-top:2px;line-height:1.3}
.mmrt td.note,.mmrt th.note{text-align:left;font-size:9px;line-height:1.35;color:var(--tx3)}
.mmrt tr.off td{color:var(--tx3)}
.mmrn{margin:6px 0 0;font-size:9px;line-height:1.5;color:var(--tx3)}
@media(max-width:360px){.mmrt td.note,.mmrt th.note{display:none}.mmrt th:nth-child(2),.mmrt td:nth-child(2){width:42%}}
.car{margin:0 0 16px;border:1px solid var(--line);border-radius:2px;background:var(--panel);padding:12px}
.car-h{display:block}
.car-k{display:block;font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--acc);font-weight:800}
.car-t{margin:2px 0 0;font-size:15px;font-weight:800;letter-spacing:-.01em}
.car-t em{font-style:normal;margin-left:6px;font-size:9px;letter-spacing:.08em;color:var(--hot);font-weight:800;vertical-align:middle}
.car-num{display:flex;align-items:baseline;flex-wrap:wrap;gap:6px;margin-top:8px}
.car-num b{font-size:22px;font-weight:800;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.car-num i{font-style:normal;font-size:9px;letter-spacing:.03em;color:var(--tx3);font-weight:700}
.carband{position:relative;height:96px;margin-top:10px;border-bottom:1px solid var(--line)}
.carzone{position:absolute;left:0;right:0;background:rgba(var(--accRgb),.10);border-top:1px dashed var(--accLine);border-bottom:1px dashed var(--accLine)}
.carbars{position:absolute;left:0;right:0;bottom:0;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:2px;align-items:end;height:100%}
.carbars i{display:block;min-height:2px;border-radius:1px 1px 0 0;background:var(--acc);opacity:.85}
.carbars i.zero{min-height:1px;background:var(--ov2)}
.carlbl{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:2px;margin-top:3px;font-size:8px;color:var(--tx3);text-align:center;font-weight:700;letter-spacing:.02em}
.car-leg{display:flex;align-items:center;gap:5px;margin-top:6px;font-size:8px;letter-spacing:.04em;text-transform:uppercase;color:var(--tx3);font-weight:700}
.car-leg i{display:inline-block;width:14px;height:8px;background:rgba(var(--accRgb),.10);border-top:1px dashed var(--accLine);border-bottom:1px dashed var(--accLine)}
.car-note{margin:8px 0 0;font-size:9px;line-height:1.5;color:var(--tx3)}
.lg{display:inline-block;width:6px;height:6px;border-radius:2px;margin-right:4px;vertical-align:middle}
.lg.m{background:var(--acc)}
.lg.v{background:rgba(var(--accRgb),.32)}
@media(max-width:340px){.cap-t em{display:none}}
.wkbar{display:flex;align-items:center;gap:8px;margin:0 0 8px}
.wkbtn{flex:0 0 44px;height:46px;border:1px solid var(--line2);border-radius:2px;background:var(--panel);color:var(--ink);font-size:20px;line-height:1;font-weight:700;cursor:pointer;padding:0;transition:border-color var(--mo) var(--ease),opacity var(--mo) var(--ease)}
.wkbtn:disabled{opacity:.3;cursor:default}
.wkinfo{flex:1 1 auto;min-width:0;text-align:center}
.wkinfo b{display:block;font-size:12px;font-weight:800;letter-spacing:.08em}
.wkinfo span{display:block;margin-top:2px;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--tx3);overflow-wrap:anywhere}
.wkprog{margin:0 0 12px}
.wp-track{display:grid;grid-template-columns:repeat(var(--wn,13),minmax(0,1fr));gap:2px;height:8px;align-items:center}
.wp-track i{display:block;height:100%;border-radius:0px;background:var(--track);transition:background var(--mo) var(--ease),box-shadow var(--mo) var(--ease)}
.wp-track i.done{background:color-mix(in srgb,var(--tx3) 42%,var(--track))}
.wp-track i.now{background:var(--acc);box-shadow:0 0 0 2px rgba(var(--accRgb),.16)}
.wp-track i.dl:not(.now){background:repeating-linear-gradient(45deg,rgba(var(--accRgb),.55) 0 1px,transparent 1px 4px),var(--track);box-shadow:inset 0 0 0 1px var(--accLine)}
.wp-track i.ts:not(.now){background:radial-gradient(circle at 50% 50%,var(--acc) 0 2px,transparent 2.5px);box-shadow:inset 0 0 0 1px var(--accLine)}
.wp-cap{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-top:4px;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--tx3);font-weight:700;font-variant-numeric:tabular-nums}
.wp-cap b{color:var(--tx2);font-weight:800}
.wp-legend{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 14px;margin-top:6px;font-size:10px;letter-spacing:.04em;text-transform:uppercase;color:var(--tx3);font-weight:700}
.wp-legend span{display:inline-flex;align-items:center;gap:5px;min-width:0}
.wp-legend i{display:inline-block;width:14px;height:6px;border-radius:1px;background:var(--track)}
.wp-legend i.lg-done{background:color-mix(in srgb,var(--tx3) 42%,var(--track))}
.wp-legend i.lg-dl{background:repeating-linear-gradient(45deg,rgba(var(--accRgb),.55) 0 1px,transparent 1px 4px),var(--track);box-shadow:inset 0 0 0 1px var(--accLine)}
.wp-legend i.lg-ts{background:radial-gradient(circle at 50% 50%,var(--acc) 0 1.5px,transparent 2px);box-shadow:inset 0 0 0 1px var(--accLine)}
.wp-legend i.lg-now{background:var(--acc)}
.wkrail{display:flex;gap:4px;overflow-x:auto;padding:2px 12px 4px 0;margin:0 0 16px;scrollbar-width:none;scroll-snap-type:x proximity;scroll-behavior:smooth;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch;-webkit-mask-image:linear-gradient(90deg,#000 calc(100% - 26px),transparent);mask-image:linear-gradient(90deg,#000 calc(100% - 26px),transparent)}
.wkrail::-webkit-scrollbar{display:none}
.wkdot{flex:0 0 44px;height:44px;border:1px solid var(--line);border-radius:2px;background:var(--panel);color:var(--tx3);font-size:10px;font-weight:800;cursor:pointer;padding:0;font-variant-numeric:tabular-nums;scroll-snap-align:center;transition:background var(--mo) var(--ease),color var(--mo) var(--ease),border-color var(--mo) var(--ease)}
.wkdot.on{background:var(--acc);border-color:var(--acc);color:var(--onAcc)}
.wkdot.dl:not(.on){background:var(--ovL);border-style:dashed}
.wkdot.ts:not(.on){border-color:var(--accLine);color:var(--acc)}
.wk[hidden]{display:none}
.wk{position:relative}
.wk[data-kind="deload"]::before,.wk[data-kind="test"]::before{content:"";position:absolute;left:-10px;top:0;bottom:14px;width:2px;border-radius:0 2px 2px 0;background:var(--line2)}
.wk[data-kind="test"]::before{background:linear-gradient(180deg,var(--acc),var(--hot))}
@keyframes wkIn{from{opacity:0;transform:translateX(var(--sx,0))}to{opacity:1;transform:none}}
.wk.slide{animation:wkIn var(--mo) var(--ease)}
.wk-head{display:flex;align-items:flex-start;gap:12px;padding:2px 2px 12px}
.wk-n{flex:0 0 auto;font-size:32px;line-height:.92;font-weight:800;letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.wk-n small{display:block;margin-top:4px;font-size:10px;font-weight:700;letter-spacing:.08em;color:var(--tx3)}
.wk-mid{flex:1 1 auto;min-width:0;padding-top:2px}
.wk-phase{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--tx3);font-weight:700;overflow-wrap:anywhere}
.wk-status{display:flex;flex-wrap:wrap;gap:0 6px;margin-top:3px;font-size:9px;letter-spacing:.06em;text-transform:uppercase;color:var(--tx3);font-weight:600;line-height:1.35}
.wk-st{white-space:nowrap}
.wk-st + .wk-st::before{content:"· ";opacity:.6}
.wk-st.ts{color:var(--acc);font-weight:700}
.wk-vol{flex:0 0 auto;text-align:right;padding-top:2px}
.wk-vol b{font-size:16px;font-weight:800;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.wk-vol span{font-size:10px;color:var(--tx3);margin-left:2px;font-weight:700}
.wk-vol i{display:block;font-style:normal;margin-top:2px;font-size:10px;color:var(--tx3);letter-spacing:.06em;font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}
.wk-int{display:flex;align-items:baseline;gap:6px;margin:-6px 2px 10px;font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--tx3);font-weight:700;min-width:0;white-space:nowrap}
.wk-int>span,.wk-int>b{flex:0 0 auto}
.wk-int b{font-size:14px;line-height:1;font-weight:800;letter-spacing:-.01em;color:var(--ink);font-variant-numeric:tabular-nums}
.wk-int b.na{color:var(--tx3);font-weight:600}
.wk-int em{font-style:normal;margin-left:auto;min-width:0;overflow:hidden;text-overflow:ellipsis;font-size:10px;letter-spacing:.04em;color:var(--tx3);font-variant-numeric:tabular-nums}
.wk-int em.inl{margin-left:0}
.wk-split{display:grid;gap:6px;margin:0 0 8px;padding:8px 12px;border:1px solid var(--line);border-radius:2px;background:var(--k14);font-size:11px;letter-spacing:.02em;font-weight:700;color:var(--tx3);text-transform:uppercase}
.wk-split .ws{display:grid;grid-template-columns:72px minmax(0,1fr) 34px;align-items:baseline;gap:1px 8px;min-width:0}
.wk-split .ws>i{font-style:normal;color:var(--tx3);white-space:nowrap;letter-spacing:.06em;overflow:hidden;text-overflow:ellipsis}
.wk-split .ws>em{justify-self:end;font-style:normal;min-width:0;font-size:10px;letter-spacing:.04em;color:var(--tx2);font-variant-numeric:tabular-nums;white-space:nowrap}
.wk-split .ws>u{justify-self:end;text-decoration:none;font-weight:800;color:var(--ink);font-variant-numeric:tabular-nums}
.wk-split .ws.z>u{color:var(--tx3)}
.wk-split .ws-b{grid-column:1/-1;position:relative;display:flex;height:7px;margin:1px 0 2px;border-radius:2px;background:var(--ov1)}
.wk-split .ws-b>i{display:block;height:100%;transition:width var(--mo) var(--ease)}
.wk-split .ws-b>i.m{background:var(--acc)}
.wk-split .ws-b>i.v{background:repeating-linear-gradient(135deg,rgba(var(--accRgb),.72) 0 1.5px,rgba(var(--accRgb),.16) 1.5px 5px);box-shadow:inset 0 0 0 1px rgba(var(--accRgb),.22)}
.wk-split .ws-b>i.a{background:repeating-linear-gradient(135deg,var(--tx3) 0 1.5px,transparent 1.5px 5px);opacity:.85}
.wk-split .ws.acc .ws-b{background:transparent;box-shadow:inset 0 0 0 1px var(--line2)}
.wk-split .ws-b>s{position:absolute;top:-3px;bottom:-3px;width:2px;border-radius:1px;background:var(--tx2)}
.wk-split .ws-b>s.mrv{background:var(--ink)}
.wk-split .tot{border-top:1px solid var(--line);margin-top:2px;padding-top:5px}
.wk-split .tot>i,.wk-split .tot>em{color:var(--tx3)}
.wk-split .tot>u{color:var(--acc)}
.rows{border:1px solid var(--line);border-radius:2px;overflow:hidden;background:var(--panel);margin:0 0 8px}
.row{display:flex;align-items:center;gap:8px;padding:4px 12px;border-bottom:1px solid var(--line);min-width:0;min-height:44px}
.row:last-child{border-bottom:0}
.row .dt{flex:0 0 44px;min-width:0}
.row .dt b{display:block;font-size:10px;font-weight:800;color:var(--tx2);font-variant-numeric:tabular-nums;letter-spacing:.01em;white-space:nowrap}
.row .dt i{display:block;font-style:normal;font-size:10px;letter-spacing:.06em;color:var(--tx3);font-weight:700}
.row .day{flex:0 0 20px;height:20px;line-height:20px;border-radius:2px;background:rgba(var(--accRgb),.12);font-size:11px;font-weight:800;color:var(--acc);text-align:center;font-variant-numeric:tabular-nums}
.row .ttl{flex:1 1 auto;min-width:0;overflow:hidden}
.row .ldl{display:flex;align-items:baseline;gap:8px;min-width:0;white-space:nowrap;overflow:hidden}
.row .ldk{flex:0 0 auto;font-style:normal;font-size:9px;font-weight:800;letter-spacing:.12em;color:var(--tx3)}
.row .ld{display:inline-flex;align-items:baseline;gap:2px;min-width:0}
.row .ld i{font-style:normal;font-size:9px;font-weight:800;letter-spacing:.04em;color:var(--tx3)}
.row .ld b{font-variant-numeric:tabular-nums;letter-spacing:-.02em;line-height:1.1}
.row .ld.main i{color:var(--acc)}
.row .ld.main b{font-size:16px;font-weight:800;color:var(--ink)}
.row .ld.lead i{color:var(--acc);opacity:1}
.row .ld.lead b{font-size:12px;font-weight:800;color:var(--tx2)}
.row .ld.sub i{font-weight:700}
.row .ld.sub b{font-size:11px;font-weight:700;color:var(--tx2)}
.row .dname{display:block;margin-top:2px;font-size:10px;line-height:1.2;color:var(--tx3);font-weight:600;letter-spacing:.035em;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .dname b{color:var(--tx2);font-weight:800}
.row .dname.solo{font-size:12px;font-weight:700;color:var(--tx2);letter-spacing:.02em}
.row .mgs{display:block;margin-top:2px;font-size:9px;letter-spacing:.04em;color:var(--tx3);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .chev{flex:0 0 auto;color:var(--tx3);font-size:12px}
.row.rest{min-height:18px;padding:2px 12px;gap:8px;background:var(--ovL);flex-wrap:wrap}
.row.rest .dt{flex:0 0 auto;display:flex;align-items:baseline;gap:4px}
.row.rest .dt b{display:inline;font-size:10px;font-weight:700;color:var(--tx3)}
.row.rest .dt i{display:inline;margin:0}
.row.rest .day{display:none}
.row.rest .ttl{font-size:10px;letter-spacing:.08em;color:var(--tx3);text-transform:uppercase;font-weight:700;text-align:right}
.row.rest .rhint{flex:1 1 100%;font-size:10px;line-height:1.35;color:var(--tx3);text-align:right;letter-spacing:.01em;font-weight:400;text-transform:none;white-space:normal}
.row.rest.today .dt b,.row.rest.today .dt i{color:var(--acc)}
.row.rest.has-run{min-height:44px;padding:4px 12px;align-items:center;cursor:pointer}
.row.rest.has-run .ttl{text-align:left}
.row.rest.has-run .rhint{flex:1 1 100%;text-align:left;color:var(--tx2);font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.row.rest.has-run .chev{display:inline-block;margin-left:auto;color:var(--tx3)}
.row.today:not(.rest){background:linear-gradient(90deg,rgba(var(--accRgb),.16),rgba(var(--accRgb),.01));box-shadow:inset 3px 0 0 var(--acc);animation:todayPulse var(--pulse) var(--ease) infinite}
@keyframes todayPulse{0%,100%{box-shadow:inset 3px 0 0 var(--acc)}50%{box-shadow:inset 3px 0 0 var(--acc),inset 20px 0 24px -18px rgba(var(--accRgb),.6)}}
.row.today .dt b{color:var(--ink)}
.row.pk{outline:2px solid rgba(var(--accRgb),.55);outline-offset:-2px;background:rgba(var(--accRgb),.10)}
.tbadge{flex:0 0 auto;display:inline-block;font-size:10px;font-weight:800;letter-spacing:.06em;background:var(--acc);color:var(--onAcc);border-radius:2px;padding:2px 4px;white-space:nowrap}
.row[data-peek]{-webkit-touch-callout:none}
.peek{position:fixed;left:16px;right:16px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:9;padding:12px 12px;border:1px solid var(--accLine);border-radius:2px;background:rgba(var(--panelRgb),.97);color:var(--ink);font-size:11px;line-height:1.5;letter-spacing:.02em;white-space:pre-line;box-shadow:0 10px 30px var(--k55);opacity:0;transform:translateY(8px);transition:opacity var(--mo) var(--ease),transform var(--mo) var(--ease);pointer-events:none}
.peek.on{opacity:1;transform:none}
.peek[hidden]{display:none}
.peek b{color:var(--acc);font-weight:800}
@media (max-width:390px){
  .row .dname{white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.3}
  .mast-r>span{display:none}
}
@media (max-width:360px){
  .wk-head{gap:8px}
  .wk-n{font-size:26px}
  .row{padding:4px 8px;gap:8px}
  .row.rest{padding:2px 8px;gap:4px}
  .row .dt{flex-basis:42px}
  .row .chev{display:none}
  .stat{padding:8px}
  .stat b{font-size:11px}
}
"""

TIER_JS = """<script>
/* /plan/ entitlement badge and expiry notice. The hub session is the only
   source: 200 + a known tier renders the capsule; 401, network error, an
   unknown tier or a signed-out visitor leaves the slot empty, so no
   placeholder flashes and no tier is ever inferred. A downgraded tier also
   shows a dismissible notice, which stays in the flow and never covers the
   page. tier_expires_at is printed as its date part and omitted when absent. */
(function () {
  var slot = document.querySelector('[data-tier-slot]');
  var note = document.getElementById('tierNote');
  if (!window.fetch) return;
  var fill = function (s, vals) {
    for (var i = 0; i < vals.length; i++) s = s.split('{' + i + '}').join(vals[i]);
    return s;
  };
  var pair = function (key, en, vals) {
    var zh = String((window.RPL_ZH || {})[key] || en);
    return [fill(en, vals), fill(zh, vals)];
  };
  var showNote = function (exp) {
    if (!note) return;
    var d = '';
    if (typeof exp === 'string') {
      var m = exp.match(/^([0-9]{4}-[0-9]{2}-[0-9]{2})/);
      if (m) d = m[1];
    }
    var p = d
      ? pair('tier.expired_on', 'Your subscription expired on {0} — you are on STANDARD.', [d])
      : pair('tier.expired', 'Your subscription has expired — you are on STANDARD.', []);
    var msg = document.getElementById('tierNoteText');
    if (msg) {
      msg.setAttribute('data-en', p[0]);
      msg.setAttribute('data-zh', p[1]);
      msg.textContent = document.documentElement.getAttribute('lang') === 'zh-CN' ? p[1] : p[0];
    }
    var x = document.getElementById('tierNoteX');
    if (x) x.onclick = function () { note.hidden = true; };
    note.hidden = false;
  };
  fetch('/hub/v1/status', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
    .then(function (r) { return r.status === 200 ? r.json() : null; })
    .then(function (j) {
      if (!j) return;
      /* Hub contract (hub.py /v1/status): tier_downgraded is a JSON boolean
         (`eff != raw`) and true always means the effective tier is standard.
         One rule: a downgraded verdict wins over `tier`, so no capsule is
         rendered at all in that state. Rendering PRO next to a notice that
         says "you are on STANDARD" is the contradiction this prevents. */
      var down = j.tier_downgraded === true;
      var t = String(j.tier || '').toLowerCase();
      if (!down && slot && ['lite', 'plus', 'pro', 'ultra'].indexOf(t) >= 0) {
        var b = document.createElement('i');
        b.className = 'tierb';
        b.textContent = t.toUpperCase();
        b.setAttribute('aria-label', t.toUpperCase() + ' — permission active');
        b.setAttribute('data-zh-aria-label', t.toUpperCase() + ' — ' + ((window.RPL_ZH || {})['tier.active'] || 'permission active'));
        slot.appendChild(b);
      }
      if (down) showNote(j.tier_expires_at);
    })
    .then(null, function () {});
})();
</script>"""

TIER_NOTE_HTML = (
    '<div class="tier-note" id="tierNote" role="status" aria-live="polite" hidden>'
    '<p class="tn-msg"><span id="tierNoteText"></span></p>'
    '<a class="tn-link" href="/#license">%s</a>'
    '<button type="button" class="tn-x" id="tierNoteX" %s>&times;</button>'
    '</div>' % (sl.T("tier.renew"), sl.A("aria-label", "tier.dismiss"))
)


PLAN_JS = """<script>
(function(){
  var p=function(n){return (n<10?'0':'')+n};
  var now=new Date();
  var iso=now.getFullYear()+'-'+p(now.getMonth()+1)+'-'+p(now.getDate());
  var view=document.getElementById('wkview');
  if(!view||!view.querySelector) return;
  var secs=[].slice.call(view.querySelectorAll('.wk'));
  var total=parseInt(view.getAttribute('data-weeks'),10)||secs.length;
  var start=view.getAttribute('data-start'), cur=1;
  if(start){
    var s=new Date(start+'T00:00:00'), t=new Date(iso+'T00:00:00');
    var days=Math.floor((t-s)/86400000);
    cur=days<0?1:Math.min(total,Math.floor(days/7)+1);
  }
  var w=cur;
  function T(k,en,vals){
    var z=(window.RPL_ZH||{})[k];
    var zh=document.documentElement.getAttribute('lang')==='zh-CN';
    var s=(zh&&z)?z:en;
    if(vals)for(var i=0;i<vals.length;i++)s=s.replace('{'+i+'}',vals[i]);
    return s;
  }
  function L(en,zh){return document.documentElement.getAttribute('lang')==='zh-CN'?(zh||en):en}
  var dots=[].slice.call(document.querySelectorAll('.wkdot'));
  var segs=[].slice.call(document.querySelectorAll('.wp-track i'));
  var MO=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--mo'))*1000||340;
  var first=true;
  function show(n){
    var prev=w;
    w=Math.max(1,Math.min(total,n));
    for(var i=0;i<secs.length;i++){
      var k=parseInt(secs[i].getAttribute('data-week'),10);
      if(k===w){secs[i].removeAttribute('hidden');}else{secs[i].setAttribute('hidden','');}
    }
    var sec=secs[w-1]||secs[0];
    var lab=document.getElementById('wklabel'), blk=document.getElementById('wkblock');
    if(lab) lab.textContent=T('plan.week','WEEK {0}',[p(w)]);
    if(blk) blk.textContent=L(sec.getAttribute('data-block')||'',sec.getAttribute('data-block-zh')||'');
    var pv=document.getElementById('wkPrev'), nx=document.getElementById('wkNext');
    if(pv) pv.disabled=(w<=1);
    if(nx) nx.disabled=(w>=total);
    for(var j=0;j<dots.length;j++){
      var on=parseInt(dots[j].getAttribute('data-jump'),10)===w;
      if(on){dots[j].classList.add('on');}else{dots[j].classList.remove('on');}
    }
    for(var s=0;s<segs.length;s++){
      var sk=parseInt(segs[s].getAttribute('data-wk'),10);
      var cls=sk<w?'done':(sk===w?'now':'');
      if(segs[s].getAttribute('data-dl')==='1') cls+=' dl';
      if(segs[s].getAttribute('data-ts')==='1') cls+=' ts';
      segs[s].className=cls;
    }
    var pg=document.getElementById('wkprog');
    if(pg) pg.setAttribute('aria-valuenow',String(w));
    var dn=document.getElementById('wkDone');
    if(dn) dn.innerHTML=T('plan.week_bar','W{0}',[p(w)])+' <b>/ '+total+'</b>';
    var lf=document.getElementById('wkLeft');
    if(lf){var left=total-w;
      lf.textContent=left===0?T('plan.final','final week')
        :(left===1?T('plan.weeks_left_one','{0} week left',[left])
                  :T('plan.weeks_left','{0} weeks left',[left]));}
    var rail=document.getElementById('wkrail'), dot=dots[w-1];
    if(rail&&dot){rail.scrollLeft=Math.max(0,dot.offsetLeft+dot.offsetWidth/2-rail.clientWidth/2);}
    view.setAttribute('data-cur',String(w));
    if(!first&&sec){
      sec.style.setProperty('--sx',(w>prev?'14px':'-14px'));
      sec.classList.remove('slide');
      void sec.offsetWidth;
      sec.classList.add('slide');
      setTimeout(function(){sec.classList.remove('slide');},MO+40);
    }
    first=false;
  }
  var pv=document.getElementById('wkPrev'), nx=document.getElementById('wkNext');
  if(pv) pv.addEventListener('click',function(){show(w-1);});
  if(nx) nx.addEventListener('click',function(){show(w+1);});
  for(var d=0;d<dots.length;d++){
    dots[d].addEventListener('click',function(){
      show(parseInt(this.getAttribute('data-jump'),10));
    });
  }
  var peek=document.getElementById('peek'), ps=null, ph=null, pkEl=null;
  function hidePeek(){
    if(!peek) return;
    peek.classList.remove('on');
    if(pkEl){pkEl.classList.remove('pk');pkEl=null;}
    clearTimeout(ph);
    ph=setTimeout(function(){peek.hidden=true;},MO);
  }
  function showPeek(el){
    if(!peek) return;
    var t=L(el.getAttribute('data-peek')||'',el.getAttribute('data-peek-zh')||'');
    if(!t) return;
    clearTimeout(ph);
    peek.textContent=t;
    peek.hidden=false;
    peek.classList.remove('on');
    var r=el.getBoundingClientRect(), h=peek.offsetHeight;
    var top=r.bottom+8;
    if(top+h>window.innerHeight-10) top=Math.max(8,r.top-h-8);
    top=Math.max(8,Math.min(top,window.innerHeight-h-8));
    peek.style.top=top+'px';
    peek.style.bottom='auto';
    void peek.offsetWidth;
    peek.classList.add('on');
    if(pkEl) pkEl.classList.remove('pk');
    pkEl=el; el.classList.add('pk');
    ph=setTimeout(hidePeek,3200);
  }
  var prs=[].slice.call(document.querySelectorAll('.row[data-peek]'));
  for(var q=0;q<prs.length;q++){
    (function(el){
      el.addEventListener('touchstart',function(){
        clearTimeout(ps);
        ps=setTimeout(function(){showPeek(el);},450);
      },{passive:true});
      el.addEventListener('touchmove',function(){clearTimeout(ps);},{passive:true});
      el.addEventListener('touchend',function(){clearTimeout(ps);},{passive:true});
      el.addEventListener('touchcancel',function(){clearTimeout(ps);},{passive:true});
      el.addEventListener('contextmenu',function(e){e.preventDefault();showPeek(el);});
    })(prs[q]);
  }
  document.addEventListener('click',function(e){
    if(peek&&peek.classList.contains('on')){
      e.preventDefault();e.stopPropagation();hidePeek();
    }
  },true);
  var x0=null,y0=0;
  view.addEventListener('touchstart',function(e){
    if(e.touches.length===1){x0=e.touches[0].clientX;y0=e.touches[0].clientY;}
  },{passive:true});
  view.addEventListener('touchend',function(e){
    if(x0===null||!e.changedTouches.length) return;
    var dx=e.changedTouches[0].clientX-x0, dy=e.changedTouches[0].clientY-y0;
    x0=null;
    if(Math.abs(dx)>40&&Math.abs(dx)>Math.abs(dy)*1.4){show(w+(dx<0?1:-1));}
  },{passive:true});
  var rows=document.querySelectorAll('.row[data-date]');
  for(var j2=0;j2<rows.length;j2++){
    if(rows[j2].getAttribute('data-date')===iso){
      rows[j2].className+=' today';
      if(!rows[j2].getAttribute('data-peek')) continue;
      var b=document.createElement('span');
      b.className='tbadge'; b.textContent=T('plan.today_badge','TODAY');
      var chev=rows[j2].querySelector('.chev');
      if(chev&&chev.parentNode){chev.parentNode.insertBefore(b,chev);}
      else{rows[j2].appendChild(b);}
    }
  }
  document.addEventListener('rpl:lang',function(){show(w);});
  show(cur);
})();
</script>"""

CAP_JS = """<script>
(function(){
  var root=document.getElementById('cap'), raw=document.getElementById('capData');
  if(!root||!raw||!window.JSON) return;
  var D=JSON.parse(raw.textContent);
  function zh(){return document.documentElement.getAttribute('lang')==='zh-CN';}
  function T(k,en,vals){
    var z=(window.RPL_ZH||{})[k];
    var zh=document.documentElement.getAttribute('lang')==='zh-CN';
    var s=(zh&&z)?z:en;
    if(vals)for(var i=0;i<vals.length;i++)s=s.replace('{'+i+'}',vals[i]);
    return s;
  }
  var N=D.weeks, DL=D.deload||[], TS=D.test, cur=D.cur||1;
  var rows=[].slice.call(root.querySelectorAll('.cap-row'));
  var viewBtns=[].slice.call(root.querySelectorAll('[data-view]'));
  var byK={}, i;
  for(i=0;i<D.items.length;i++){byK[D.items[i].k]=D.items[i];}
  for(i=0;i<(D.roles||[]).length;i++){byK[D.roles[i].k]=D.roles[i];}
  var sel='S', view='lift', mode='all', wk=cur, lastDelta='';
  var GROUPS=['chest','shoulders','back','legs','arms','abs'];
  var GLAB={chest:'CH',shoulders:'SH',back:'BK',legs:'LG',arms:'AR',abs:'AB'};
  var ROLES=['R_MAIN','R_VAR','R_ACC'];
  var RLAB={R_MAIN:'MAIN',R_VAR:'SBD VAR',R_ACC:'ACCS'};
  var BAR_H=88, slots=[];
  var chart=document.getElementById('capChart');
  if(chart) slots=[].slice.call(chart.querySelectorAll('.cb'));
  var RM=!!(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches);
  var MO=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--mo'))*1000||340;
  var EASE=(getComputedStyle(document.documentElement).getPropertyValue('--ease')||'ease').trim();
  var rollSeq=0, rollFrom=0, rollSel='';
  function rollSets(el,to){
    if(!el) return;
    if(sel!==rollSel){rollFrom=0;rollSel=sel;}
    if(RM){rollFrom=to;el.textContent=fmt(to);return;}
    var from=rollFrom, seq=++rollSeq, t0=performance.now();
    function step(now){
      if(seq!==rollSeq) return;
      var k=Math.min(1,(now-t0)/MO), e=1-Math.pow(1-k,3);
      el.textContent=fmt(Math.round(from+(to-from)*e));
      if(k<1){requestAnimationFrame(step);}
      else{rollFrom=to;el.textContent=fmt(to);}
    }
    requestAnimationFrame(step);
  }
  function sum(a){var s=0;for(var j=0;j<a.length;j++)s+=a[j]||0;return s;}
  function item(k){return byK[k];}
  function at(a,j){return ((a||[])[j-1]||0);}
  function r1(x){return Math.round((+x||0)*10)/10;}
  function fmt(x){x=r1(x);return Math.abs(x-Math.round(x))<1e-9?String(Math.round(x)):x.toFixed(1);}
  function pad(n){return (n<10?'0':'')+n;}
  function val(k,j){
    var it=item(k); if(!it) return 0;
    if(it.kind==='muscle') return at(it.w,j);
    return at(it.m,j)+at(it.v,j);
  }
  function rv(k){
    var it=item(k); if(!it) return {m:0,v:0,d:0,w:0,t:0};
    if(it.kind==='muscle'){
      var d=mode==='all'?sum(it.d):at(it.d,wk);
      var w=mode==='all'?sum(it.w):at(it.w,wk);
      return {m:0,v:0,d:d,w:w,t:w};
    }
    var m=mode==='all'?sum(it.m):at(it.m,wk);
    var v=mode==='all'?sum(it.v):at(it.v,wk);
    return {m:m,v:v,d:0,w:0,t:m+v};
  }
  function totalNow(kind){
    if(kind==='muscle') return mode==='all'?D.mtAll:(D.mt[wk-1]||0);
    return mode==='all'?D.totalAll:(D.total[wk-1]||0);
  }
  function isLoadWeek(){return !(wk===TS||DL.indexOf(wk)>=0);}
  function verdict(it,total){
    if(it.lo==null||it.hi==null) return null;
    var lo=+it.lo,hi=+it.hi;
    if(mode!=='week') return {t:(it.kind==='lift'?T('cap.weekly_range','RANGE {0}\u2013{1}',[lo,hi]):T('cap.verdict.all','PER-WEEK RANGE')),c:''};
    if(!isLoadWeek()){
      var tag=(wk===TS)?T('cap.mark.test','TEST'):T('cap.mark.deload','DELOAD');
      return {t:T('cap.verdict.skip','NOT JUDGED \u00b7 {0}',[tag]),c:'skip'};
    }
    var over=r1(total-hi),under=r1(lo-total);
    if(over>1) return {t:T('cap.verdict.over','+{0} ABOVE RANGE {1}\u2013{2}',[fmt(over),lo,hi]),c:'over'};
    if(under>1) return {t:T('cap.verdict.under','{0} UNDER {1}\u2013{2}',[fmt(under),lo,hi]),c:'under'};
    return {t:T('cap.verdict.within','WITHIN {0}\u2013{1}',[lo,hi]),c:'within'};
  }
  function rangeLine(it,o){
    if(it.lo==null||it.hi==null) return '';
    var lo=+it.lo,hi=+it.hi;
    if(mode!=='week') return T('cap.verdict.all_line','Weekly range {0}\u2013{1}; switch to a week to compare.',[lo,hi]);
    if(!isLoadWeek()) return T('cap.verdict.skip_line','W{0} \u00b7 {1} weighted \u00b7 {2} week, not judged',
      [pad(wk),fmt(o.t),wk===TS?T('cap.mark.test','TEST'):T('cap.mark.deload','DELOAD')]);
    var over=r1(o.t-hi),under=r1(lo-o.t);
    if(over>1) return T('cap.verdict.over_line','W{0} \u00b7 {1} weighted \u00b7 +{2} above range {3}\u2013{4}',
      [pad(wk),fmt(o.t),fmt(over),lo,hi]);
    if(under>1) return T('cap.verdict.under_line','W{0} \u00b7 {1} weighted \u00b7 {2} under {3}\u2013{4}',
      [pad(wk),fmt(o.t),fmt(under),lo,hi]);
    return T('cap.verdict.within_line','W{0} \u00b7 {1} weighted \u00b7 within {2}\u2013{3}',
      [pad(wk),fmt(o.t),lo,hi]);
  }
  function pct(a,b){return b>0?Math.round(a*100/b):0;}
  function grpOf(r){return r.getAttribute('data-grp')||'lift';}
  function weekVal(k){var j=parseInt(k.slice(1),10);return (D.total&&D.total[j-1])||0;}
  function syncList(){
    var els=root.querySelectorAll('#capList > *');
    for(var j=0;j<els.length;j++){
      var g=els[j].getAttribute('data-grp');
      if(g) els[j].hidden=(g!==view);
    }
  }
  function paintRows(){
    var mx=0,j;
    for(j=0;j<rows.length;j++){
      if(grpOf(rows[j])!==view) continue;
      var k0=rows[j].getAttribute('data-cap');
      var t0=(view==='week')?weekVal(k0):rv(k0).t;
      if(t0>mx)mx=t0;
    }
    for(j=0;j<rows.length;j++){
      var r=rows[j], k=r.getAttribute('data-cap');
      if(grpOf(r)==='week'){
        var wj=parseInt(r.getAttribute('data-wk'),10), tw=weekVal(k);
        var bt=r.querySelector('[data-t]'); if(bt) bt.textContent=fmt(tw);
        var bb=r.querySelector('[data-bar]'); if(bb) bb.style.width=(mx>0?tw*100/mx:0)+'%';
        r.setAttribute('data-zero',tw===0?'1':'0');
        var won=(mode==='week'&&wk===wj);
        r.className='cap-row single'+(won?' on':'');
        r.setAttribute('aria-pressed',won?'true':'false');
        continue;
      }
      var o=rv(k);
      var em=r.querySelector('[data-m]'), ev=r.querySelector('[data-v]'),
          ed=r.querySelector('[data-d]'), ew=r.querySelector('[data-w]'),
          et=r.querySelector('[data-t]');
      if(em) em.textContent=fmt(o.m);
      if(ev) ev.textContent=fmt(o.v);
      if(ed) ed.textContent=fmt(o.d);
      if(ew) ew.textContent=fmt(o.w);
      if(et) et.textContent=fmt(o.t);
      var bar=r.querySelector('[data-bar]');
      if(bar) bar.style.width=(mx>0?o.t*100/mx:0)+'%';
      r.setAttribute('data-zero',o.t===0?'1':'0');
      var it=item(k), z=r.querySelector('.cr-z');
      var muscleRow=!!(it&&it.kind==='muscle');
      var blank=muscleRow&&o.d===0&&o.w===0;
      if(z) z.hidden=!blank;
      var cells=r.querySelectorAll('.cr-v');
      for(var c=0;c<cells.length;c++){cells[c].hidden=blank;}
      var vd=r.querySelector('[data-verdict]');
      if(vd){
        var vr=verdict(it,o.t);
        if(vr){vd.textContent=vr.t;vd.className=vr.c;}
        else{vd.textContent='';vd.className='';}
      }
    }
    var empty=document.getElementById('capEmpty');
    if(empty) empty.hidden=mx>0;
  }
  function markRows(){
    var any=false;
    for(var j=0;j<rows.length;j++){
      var rk=rows[j].getAttribute('data-cap'), it=item(rk);
      if(!it) continue;
      var on=(rk===sel);
      if(on) any=true;
      var base=it.kind==='lift'?'cap-row':(it.kind==='muscle'?'cap-row dual':'cap-row single');
      rows[j].className=base+(on?' on':'');
      rows[j].setAttribute('aria-pressed',on?'true':'false');
    }
    root.className='cap'+(any?' dim':'');
  }
  function categories(){
    if(view==='muscle') return GROUPS.map(function(g){return {k:g,lab:GLAB[g]};});
    if(view==='role') return ROLES.map(function(k){return {k:k,lab:RLAB[k]};});
    if(view==='week'){
      var a=[];
      for(var j=1;j<=N;j++){
        var lab=(j===1||j%4===0||j===N)?pad(j):'', cls='';
        if(j===TS){lab='T';cls='t';}
        else if(DL.indexOf(j)>=0){lab='D';cls='d';}
        a.push({k:'w'+j,lab:lab,cls:cls});
      }
      return a;
    }
    return [{k:'S',lab:'S'},{k:'B',lab:'B'},{k:'D',lab:'D'}];
  }
  function catVal(k){
    if(view==='week') return val(sel,parseInt(k.slice(1),10));
    return rv(k).t;
  }
  function chartMax(){
    var mx=0, cs=categories();
    for(var j=0;j<cs.length;j++){var q=catVal(cs[j].k);if(q>mx)mx=q;}
    return mx>0?mx:1;
  }
  function chartCls(k){
    var cls='cb', wn=parseInt(k.slice(1),10);
    if(view==='week'){
      if(wn===TS) cls+=' ts';
      if(DL.indexOf(wn)>=0) cls+=' dl';
      if(mode==='week'&&wn===wk) cls+=' cur';
    }else{
      if((view==='lift'&&k===sel)||(view==='muscle'&&k===sel)||
         (view==='role'&&k===sel)) cls+=' on';
    }
    return cls;
  }
  function renderChart(){
    var cs=categories(), mx=chartMax(), hs=[], vs=[];
    chart.style.setProperty('--n',String(cs.length));
    chart.setAttribute('data-n',String(cs.length));
    chart.className='cap-chart'+(view==='week'?' compact':'');
    for(var j=0;j<slots.length;j++){
      var el=slots[j];
      if(j>=cs.length){el.className='cb off';el.removeAttribute('data-ck');hs.push(0);vs.push(0);continue;}
      var k=cs[j].k, t=catVal(k), o=(view==='week'?null:rv(k));
      var mh=t*BAR_H/mx, vh=0;
      if(o&&o.v){mh=o.m*BAR_H/mx;vh=o.v*BAR_H/mx;}
      hs.push(mh);vs.push(vh);
      el.className=chartCls(k);
      el.setAttribute('data-ck',k);
      el.setAttribute('aria-label',T('cap.aria_sets','{0}, {1} sets',
        [(view==='week'?T('plan.week_aria','Week {0}',[pad(parseInt(k.slice(1),10))]):k),fmt(t)]));
      var lab=el.querySelector('.cbv');
      if(lab) lab.textContent=(view==='week'?'':fmt(t));
      var em=el.querySelector('em');
      if(em){em.textContent=cs[j].lab||'';em.className=cs[j].cls||'';}
    }
    for(var q=0;q<cs.length;q++){
      var e2=slots[q], m=e2.querySelector('.m'), v=e2.querySelector('.v');
      if(m) m.style.height=hs[q].toFixed(1)+'px';
      if(v) v.style.height=vs[q].toFixed(1)+'px';
    }
  }
  var fadeSeq=0;
  function updateChart(cross){
    if(cross&&!RM){
      var half=Math.round(MO/2), seq=++fadeSeq;
      chart.style.transition='opacity '+half+'ms '+EASE;
      chart.style.opacity='0';
      setTimeout(function(){
        if(seq!==fadeSeq) return;
        renderChart();
        chart.style.opacity='1';
        setTimeout(function(){
          if(seq===fadeSeq){chart.style.transition='';chart.style.opacity='';}
        },half+40);
      },half);
    }else{
      fadeSeq++;
      chart.style.transition='';chart.style.opacity='';
      renderChart();
    }
  }
  function deltaText(){
    if(mode==='week'){
      if(wk<=1) return {t:T('cap.baseline','W01 BASELINE'),c:'flat'};
      var d=r1(val(sel,wk)-val(sel,wk-1));
      if(Math.abs(d)<1e-9) return {t:T('cap.flat','FLAT VS W{0}',[pad(wk-1)]),c:'flat'};
      return {t:T('cap.delta','{0} VS W{1}',
        [(d>0?'+':'-')+fmt(Math.abs(d)),pad(wk-1)]),c:d>0?'up':'down'};
    }
    var pk=1,pv=-1;
    for(var j=1;j<=N;j++){var q=val(sel,j);if(q>pv){pv=q;pk=j;}}
    return {t:T('cap.peak','PEAK W{0} / {1}',[pad(pk),fmt(pv)]),c:'flat'};
  }
  function markViews(){
    for(var j=0;j<viewBtns.length;j++){
      var on=viewBtns[j].getAttribute('data-view')===view;
      viewBtns[j].className=on?'on':'';
      viewBtns[j].setAttribute('aria-pressed',on?'true':'false');
    }
  }
  function paintDetail(){
    var it=item(sel), o=rv(sel);
    document.getElementById('capName').textContent=(zh()&&it.z)?it.z:it.n;
    rollSets(document.getElementById('capSets'),o.t);
    document.getElementById('capShare').textContent=pct(o.t,totalNow(it.kind))+'%';
    var sub=document.getElementById('capSub');
    if(it.kind==='lift') sub.textContent=T('cap.sub_lift','MAIN {0} / VAR {1}',[fmt(o.m),fmt(o.v)]);
    else if(it.kind==='muscle') sub.textContent=T('cap.sub_muscle','WEIGHTED {0} / DIRECT {1}',[fmt(o.w),fmt(o.d)]);
    else sub.textContent=(zh()&&it.sub_z)?it.sub_z:(it.sub||T('cap.sub_role_fallback','ROLE TOTAL'));
    var rail=document.getElementById('capRail');
    if(rail) rail.style.width=pct(o.t,totalNow(it.kind))+'%';
    var ref=document.getElementById('capRef'),ra=document.getElementById('capRefA'),
        rb=document.getElementById('capRefB');
    if(ref&&ra&&rb){
      if(it.kind==='lift'){
        ref.hidden=false;
        ra.textContent=T('cap.sbd_ref','MEV {0} / MRV {1}',[fmt(it.mev),fmt(it.mrv)]);
        rb.textContent=T('cap.mrv_note','MRV is a recovery ceiling, not a target.');
      }else if(it.kind==='muscle'){
        ref.hidden=false;
        ra.textContent=T('cap.group_ref','No group-level range \u2014 see the muscle map for per-muscle ranges.');
        rb.textContent=rangeLine(it,o);
      }else ref.hidden=true;
    }
    var lg=document.getElementById('capLg');
    if(it.kind==='lift') lg.innerHTML='<span><i class="lg m"></i>'+T('cap.legend.main','Main')+'</span><span><i class="lg v"></i>'+T('cap.legend.var','Var')+'</span>';
    else if(it.kind==='muscle') lg.innerHTML='<span><i class="lg m"></i>'+T('cap.legend.weighted_sets','Weighted sets')+'</span><span>'+T('cap.legend.direct_sub','direct sets')+'</span>';
    else lg.innerHTML='<span>'+T('cap.legend.working_sets','Working sets')+'</span>';
    var note=document.getElementById('capNote');
    if(note){
      var show=(it.kind==='muscle');
      note.hidden=!show;
      if(show&&D.coefFinal) note.textContent=T('cap.note','Weighted sets count how much each muscle is involved.');
      else note.hidden=true;
    }
    var dd=deltaText(), el=document.getElementById('capDelta');
    el.textContent=dd.t;
    el.className='cd-delta '+dd.c;
    if(lastDelta!==dd.t){el.classList.remove('anim');void el.offsetWidth;el.classList.add('anim');lastDelta=dd.t;}
    var cap=document.getElementById('capCap');
    if(view==='week'){
      var wt=(wk===TS?T('cap.test_week_suffix',' \u00b7 TEST WEEK'):(DL.indexOf(wk)>=0?T('cap.deload_suffix',' \u00b7 DELOAD'):''));
      cap.textContent=T('cap.cap_week','{0} SETS \u00b7 {1}{2}',
        [(zh()&&it.z)?it.z:it.n,(mode==='all'?T('cap.all_cycle','ALL CYCLE'):T('plan.week_bar','W{0}',[pad(wk)])),wt]);
    }
    else cap.textContent=T('cap.cap','{0} / {1}',
      [({lift:T('cap.by_lift','BY LIFT'),muscle:T('cap.by_muscle','BY MUSCLE'),
         role:T('cap.by_role','BY ROLE')}[view]||T('cap.by_lift','BY LIFT')).toUpperCase(),
       mode==='all'?T('cap.all_cycle','ALL CYCLE'):T('cap.week_label','WEEK {0}',[pad(wk)])]);
    document.getElementById('capMode').textContent=mode==='all'?T('cap.all_cycle','ALL CYCLE'):T('cap.week_label','WEEK {0}',[pad(wk)]);
    var all=document.getElementById('capAll');
    all.className=mode==='all'?'on':'';
    all.setAttribute('aria-pressed',mode==='all'?'true':'false');
    var wkl=document.getElementById('capWk');
    wkl.textContent=T('plan.week_bar','W{0}',[pad(wk)]);
    wkl.className=mode==='all'?'muted':'';
    markViews();
  }
  function paintAll(){syncList();markRows();paintRows();paintDetail();updateChart(false);}
  function viewFor(k){
    var it=item(k); if(!it) return 'lift';
    if(it.kind==='lift') return 'lift';
    if(it.kind==='muscle') return 'muscle';
    return 'role';
  }
  function pick(k){
    if(!item(k)){
      if(k.charAt(0)==='w'){mode='week';wk=parseInt(k.slice(1),10)||cur;paintAll();}
      return;
    }
    var want=viewFor(k), changed=(want!==view);
    sel=k;
    if(changed){view=want;syncList();updateChart(true);markRows();paintRows();paintDetail();}
    else{paintAll();}
  }
  function setView(v){
    if(v===view) return;
    var sp=document.getElementById('capSpacer');
    var prevY=window.pageYOffset;
    if(sp) sp.style.height='600px';
    view=v;
    if(v==='week') mode='week';
    if(v==='lift'&&item(sel).kind!=='lift') sel='S';
    if(v==='muscle'&&item(sel).kind!=='muscle') sel=GROUPS[0];
    if(v==='role'&&item(sel).kind!=='role') sel='R_MAIN';
    if(v==='week'&&item(sel).kind==='role') sel='S';
    syncList();updateChart(true);markRows();paintRows();paintDetail();
    if(sp){
      var baseH=document.documentElement.scrollHeight-600;
      sp.style.height=Math.max(0,prevY+window.innerHeight-baseH)+'px';
    }
  }
  for(i=0;i<rows.length;i++){
    rows[i].addEventListener('click',function(){pick(this.getAttribute('data-cap'));});
  }
  for(i=0;i<viewBtns.length;i++){
    viewBtns[i].addEventListener('click',function(){setView(this.getAttribute('data-view'));});
  }
  document.getElementById('capAll').addEventListener('click',function(){mode='all';paintAll();});
  document.getElementById('capPrev').addEventListener('click',function(){
    if(mode==='all'){mode='week';}
    else if(wk>1){wk--;}
    paintAll();
  });
  document.getElementById('capNext').addEventListener('click',function(){
    if(mode==='all'){mode='week';}
    else if(wk<N){wk++;}
    paintAll();
  });
  chart.addEventListener('click',function(e){
    var t=e.target;
    while(t&&t!==chart&&!t.getAttribute('data-ck')){t=t.parentNode;}
    if(!t||t===chart) return;
    var k=t.getAttribute('data-ck');
    if(view==='week'){mode='week';wk=parseInt(k.slice(1),10);paintAll();}
    else{pick(k);}
  });
  document.addEventListener('rpl:lang',function(){paintAll();});
  pick('S');
})();
</script>"""

TODAY_JS = """<script>
(function(){
  var m=%s;
  var d=new Date(),p=function(n){return (n<10?'0':'')+n};
  var k=String(d.getFullYear()).slice(2)+p(d.getMonth()+1)+p(d.getDate());
  var target=m[k];
  if(!target){var best=null;for(var key in m){if(key<=k&&(!best||key>best))best=key;}
    target=best?m[best]:null;}
  if(!target){location.replace('../plan/');return;}
  function go(){location.replace('../'+target+'/');}
  if(!window.fetch||!window.DOMParser){go();return;}
  fetch('../'+target+'/').then(function(r){
    if(!r.ok)throw 0;return r.text();
  }).then(function(html){
    var doc=new DOMParser().parseFromString(html,'text/html');
    var wrap=doc.querySelector('.wrap');
    var here=document.querySelector('.wrap');
    if(!wrap||!here)throw 0;
    here.outerHTML=wrap.outerHTML;
    document.title=doc.title;
    var ss=doc.querySelectorAll('script');
    for(var i=0;i<ss.length;i++){
      var n=document.createElement('script');
      n.textContent=ss[i].textContent;
      document.body.appendChild(n);
      document.body.removeChild(n);
    }
  }).catch(go);
})();
</script>"""


COUNT_JS = """<script>
(function(){
  var els=[].slice.call(document.querySelectorAll('[data-count]'));
  if(!els.length) return;
  if(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var cs=getComputedStyle(document.documentElement);
  var MO=parseFloat(cs.getPropertyValue('--mo'))*1000||340;
  function f(v,d){
    var s=v.toFixed(d),p=s.split('.');
    p[0]=p[0].replace(/\\B(?=(\\d{3})+(?!\\d))/g,',');
    return p.join('.');
  }
  for(var i=0;i<els.length;i++){
    (function(el){
      if(!el.offsetParent&&getComputedStyle(el).position!=='fixed') return;
      var to=parseFloat(el.getAttribute('data-count'))||0;
      var dec=parseInt(el.getAttribute('data-dec')||'0',10);
      var t0=performance.now();
      function step(now){
        var k=Math.min(1,(now-t0)/MO), e=1-Math.pow(1-k,3);
        el.textContent=f(to*e,dec);
        if(k<1){requestAnimationFrame(step);}else{el.textContent=f(to,dec);}
      }
      requestAnimationFrame(step);
    })(els[i]);
  }
})();
</script>"""


GEAR_JS = """<script>
(function(){
  var bs=document.querySelectorAll('.gsum');
  for(var i=0;i<bs.length;i++){
    bs[i].parentNode.classList.add('js');
    bs[i].addEventListener('click',function(){
      var s=this.parentNode, on=s.classList.toggle('open');
      this.setAttribute('aria-expanded',on?'true':'false');
      var x=this.querySelector('.gsum-x');
      if(x)x.textContent=on?'\u2013':'+';
    });
  }
})();
</script>"""


LOG_JS = """<script>
(function(){
  var btn=document.getElementById('viewBtn');
  var day=btn?btn.getAttribute('data-day')||'':'';
  if(!day)return;
  var KEY='rpl.site.log.v1';
  var rows=[].slice.call(document.querySelectorAll('.rx-log[data-k]'));
  function read(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')||{};}catch(e){return {};}}
  var store=read();
  function key(row){return day+'|'+row.getAttribute('data-k');}
  function paint(row){
    var rec=store[key(row)]||{},has=false;
    [].forEach.call(row.querySelectorAll('input'),function(inp){
      var v=rec[inp.getAttribute('data-f')];
      if(v!==undefined&&v!==''){inp.value=v;has=true;}else{inp.value='';}
    });
    row.classList.toggle('has',has);
  }
  rows.forEach(paint);
  function save(row){
    var rec={},has=false;
    [].forEach.call(row.querySelectorAll('input'),function(inp){
      var v=inp.value.trim();
      if(v){rec[inp.getAttribute('data-f')]=v;has=true;}
    });
    if(has){store[key(row)]=rec;}else{delete store[key(row)];}
    try{localStorage.setItem(KEY,JSON.stringify(store));}catch(e){}
    row.classList.toggle('has',has);
  }
  rows.forEach(function(row){
    row.addEventListener('input',function(ev){
      var t=ev.target;
      if(!t||t.tagName!=='INPUT')return;
      var v=t.value.replace(/[^0-9.]/g,'');
      if(v!==t.value){
        var p=t.selectionStart;
        t.value=v;
        try{t.setSelectionRange(p>v.length?v.length:p,p);}catch(e){}
      }
      save(row);
    });
  });
})();
</script>"""


VIEW_JS = """<script>
(function(){
  var R=document.documentElement,K='rpl.view';
  var btn=document.getElementById('viewBtn');
  function lang(){return R.getAttribute('data-lang')==='zh'?'zh':'en'}
  function label(){
    var v=R.getAttribute('data-view')==='mini'?'mini':'max',mini=v==='mini',zh=lang()==='zh';
    if(btn){
      btn.textContent=mini?'Mini':'Max';
      btn.setAttribute('aria-pressed',mini?'true':'false');
      btn.setAttribute('aria-label',zh
        ?(mini?'\\u663e\\u793a\\u6a21\\u5f0f\\uff1aMini\\u3002\\u6309\\u4e0b\\u5207\\u6362\\u5230 Max\\u3002'
              :'\\u663e\\u793a\\u6a21\\u5f0f\\uff1aMax\\u3002\\u6309\\u4e0b\\u5207\\u6362\\u5230 Mini\\u3002')
        :(mini?'Display mode: Mini. Activate to switch to Max.'
              :'Display mode: Max. Activate to switch to Mini.'));
    }
  }
  function setView(v,save){
    var y=window.pageYOffset||document.documentElement.scrollTop||0;
    R.setAttribute('data-view',v);
    if(save){try{localStorage.setItem(K,v)}catch(e){}}
    label();
    try{window.scrollTo(0,y)}catch(e){}
    requestAnimationFrame(function(){try{window.scrollTo(0,y)}catch(e){}});
    if(document.body){
      document.body.classList.add('view-swap');
      setTimeout(function(){document.body.classList.remove('view-swap')},170);
    }
  }
  if(btn)btn.addEventListener('click',function(){
    setView(R.getAttribute('data-view')==='mini'?'max':'mini',true);
  });
  document.addEventListener('rpl:lang',label);
  label();
})();
</script>"""


MMAP_ADAPTER = """<script>
(function(){
  var M=document.getElementById('mmMount'),D=document.getElementById('mmData');
  if(!M||!D||!window.MuscleMap)return;
  var p=JSON.parse(D.textContent||'{}'),cur=+p.cur||1,order=p.order||[];
  var view=document.getElementById('wkview');
  var init=view?parseInt(view.getAttribute('data-cur'),10):0;
  if(init)cur=init;
  function arr(a){var o={},i;for(i=0;i<order.length;i++)o[order[i]]=+((a||[])[i]||0);return o;}
  function wv(w){var x=p.weeks[String(w)]||{w:[],d:[]};return {values:arr(x.w),values2:arr(x.d)};}
  function lang(){return document.documentElement.getAttribute('data-lang')==='zh'?'zh':'en';}
  function wlab(n){var z=(window.RPL_ZH||{})['plan.week_bar'];return (lang()==='zh'&&z)?z.replace('{0}',n):'W'+n;}
  function label(){var b=document.getElementById('mmWeek');if(b)b.textContent=wlab((cur<10?'0':'')+cur);}
  var ZH={view_both:'\u6b63 / \u80cc',view_front:'\u6b63\u9762',view_back:'\u80cc\u9762',
    cap_both:'\u6b63\u9762 / \u80cc\u9762',cap_front:'\u6b63\u9762',cap_back:'\u80cc\u9762',
    lg_primary:'\u4e3b\u8981',lg_secondary:'\u6b21\u8981',lg_off:'\u672a\u8ba1',
    coef:'\u7cfb\u6570',this_week:'\u672c\u5468',sets:'\u7ec4',direct:'\u76f4\u63a5',
    no_source:'\u65e0\u5355\u72ec\u6765\u6e90',range_na:'\u533a\u95f4\u7f3a\u5931',
    delta_na:'\u5dee\u503c\uff1a\u533a\u95f4\u672a\u5b9a\u4e49',
    range:'\u533a\u95f4',group_based:'\u6309\u7ec4\u8ba1',
    sessions:'\u6bcf\u5468 {n} \u7ec3',
    covered:'\u590d\u5408\u52a8\u4f5c\u5df2\u8986\u76d6',
    achieved:'\u5df2\u8fbe {p}%',
    group_total:'\u7ec4\u603b\u548c {g} / \u4e0a\u9650 {h}',
    nodata:'\u65e0\u6570\u636e',p:'\u4e3b',s:'\u6b21',
    muscles:'\u8bad\u7ec3\u808c\u7fa4',all16:'\u5168\u90e8 {n} \u53f6',top5:'\u524d 5'};
  var v=wv(cur);
  var ctl=MuscleMap.mount(M,{geo:window.RPL_MUSCLE_GEO,values:v.values,values2:v.values2,
    ranges:p.ranges,thresholds:{primary:.8,secondary:.3},mode:'rate',unit:'sets',lang:lang(),zh:ZH});
  label();
  if(view&&window.MutationObserver){
    new MutationObserver(function(){
      var n=parseInt(view.getAttribute('data-cur'),10);if(!n||n===cur)return;
      var x=wv(n);cur=n;ctl.update({values:x.values,values2:x.values2});label();
    }).observe(view,{attributes:true,attributeFilter:['data-cur']});
  }
  document.addEventListener('rpl:lang',function(){ctl.setLang(lang());});
})();
</script>"""


def shell(title, body, extra_css="", title_zh="", view_switch=True):
    style = CSS + (("\n" + extra_css) if extra_css else "")
    if view_switch:
        view_init = ('try{t=localStorage.getItem("rpl.theme");v=localStorage.getItem("rpl.view");'
                     'if(v!=="mini"&&v!=="max"){var o=localStorage.getItem("rpl.site.logmode");v=o==="0"?"mini":"max"}}catch(e){}')
    else:
        # No Mini/Max switch on this page: pin the max tree even if an older
        # visit left rpl.view=mini in localStorage.
        view_init = 'try{t=localStorage.getItem("rpl.theme")}catch(e){}'
    head_js = (
        '<script>(function(){var r=document.documentElement,t=null,v="max";'
        + view_init +
        'r.setAttribute("data-view",v);'
        'if(t!=="dark"&&t!=="light"&&t!=="ex")t=r.getAttribute("data-theme");'
        'if(!t)return;'
        'r.setAttribute("data-theme",t);r.setAttribute("data-mode",t==="dark"?"dark":"light");'
        'var m=document.querySelector(\'meta[name="theme-color"]\');'
        'if(m)m.setAttribute("content",t==="dark"?"#07090D":t==="light"?"#F4F7FA":"#EFE9DD");})();</script>'
    )
    title_attr = ' data-title-en="%s"' % esc(title)
    if title_zh:
        title_attr += ' data-title-zh="%s"' % esc(title_zh)
    # 每页只带 JS 会查的中文：静态文案已经有 data-zh 属性，运行时由 HEAD_JS 换文本，
    # 不需要再进 window.RPL_ZH。只有 PLAN_JS / CAP_JS 里的 T('key') 字面量要在表里。
    # 整表内联会让每页多背 5–10 KB；App 快照有两页，这份重复直接吃体积预算。
    keys = set(k for k in sl.STRINGS
               if ("'%s'" % k) in body or ('"%s"' % k) in body)
    lang_js = '<script>window.RPL_ZH=%s;</script>\n' % sl.js_literal(keys) + sl.HEAD_JS

    return (
        '<!DOCTYPE html>\n<html lang="en" data-lang="en" data-theme="dark" data-mode="dark" data-view="max"%s>\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="theme-color" content="#07090D">\n'
        % title_attr
        + head_js + "\n" + lang_js + "\n"
        "<title>%s</title>\n<style>\n%s\n</style>\n</head>\n<body>\n"
        '<div class="wrap">\n%s\n</div>\n%s\n%s\n%s\n</body>\n</html>\n'
    ) % (esc(title), style, body, REVEAL_JS, VIEW_JS if view_switch else "", st.THEME_JS)


def _friends_html():
    with open(os.path.join(HERE, "friends.json"), encoding="utf-8") as f:
        items = json.load(f)
    links = []
    for it in items:
        # 英文基准：title 一律取 desc_en，中文只在 data-zh-title 里，
        # 与站内其它属性同一个机制（site_lang.A 的 name="en" data-zh-name="zh"）。
        en = str(it.get("desc_en") or it.get("desc") or "")
        zh = str(it.get("desc") or "")
        attr = 'title="%s"' % html.escape(en, quote=True)
        if zh and zh != en:
            attr += ' data-zh-title="%s"' % html.escape(zh, quote=True)
        links.append('<a href="%s" %s>%s</a>' % (
            html.escape(str(it.get("href") or "#"), quote=True),
            attr,
            html.escape(str(it.get("name") or ""))))
    return '<div class="friends"><span>%s</span>%s</div>' % (sl.T("friends"), "".join(links))


FRIENDS = _friends_html()


def _mini_sr(seg):
    """Sets x reps for one prescribed block, never a second label."""
    sets = int(seg.get("sets") or 0)
    reps = seg.get("reps")
    if isinstance(reps, int):
        out = "%d&times;%d" % (sets, reps)
    else:
        out = esc(reps or "")
    if seg.get("amrap"):
        out += "+"
    return out


def _mini_row(bits):
    return '<div class="ms-r">%s</div>' % "".join(bits)


_UNIT_TAIL = re.compile(r"(s/side|secs|sec|s)\s*$", re.I)


def _rx_unit(e):
    """Unit the raw prescription carries when the parser left ``seg['unit']`` empty."""
    m = _UNIT_TAIL.search(str(e.get("rx") or ""))
    return m.group(1) if m else ""


def _rx_tag(seg):
    """Row role word (CAL / WORK / TOP / BACK-OFF): two identical lift names must differ."""
    key = RX_TAG_KEYS.get(str(seg.get("kind") or "").upper())
    return sl.T(key) if key else ""


def mini_exercise(e, role):
    """One read-only line block: lift name, then load / sets x reps / target RPE.

    Every prescribed row prints the intensity it implies: main lifts use the
    contractual percentage, accessories the RPE/reps estimate (marked with ≈).
    """
    is_acc = role == "accessory"
    out = ['<div class="ms-lift"><div class="ms-h"><b>%s</b>%s</div>'
           % (sl.MV(e.get("mv")), "")]
    rpe = e.get("targetRpe")
    raw_unit = _rx_unit(e)
    if is_acc:
        seg = next((sg for sg in (e.get("rxParts") or [])
                    if isinstance(sg.get("reps"), int)
                    and int(sg.get("sets") or 0) > 0), None)
        bits = []
        if seg:
            bits.append("<b>%s</b>" % _mini_sr(seg))
            if raw_unit:
                bits.append("<span>%s</span>" % sl.T(UNIT_KEYS.get(raw_unit.lower(), "unit.sec")))
            if rpe is not None:
                bits.append("<span>RPE %s</span>" % dm.fmt_num(rpe))
                pct = est_pct_1rm(seg.get("reps"), rpe)
                # A timed hold (s/side) has no 1RM to estimate; the number is in seconds.
                if pct is not None and seg.get("kind") != "bw" and not raw_unit:
                    bits.append("<span>&asymp;%d%% 1RM</span>" % pct)
        out.append(_mini_row(bits))
    else:
        for seg in (e.get("rxParts") or []):
            tag = _rx_tag(seg)
            bits = []
            if tag:
                bits.append('<span class="ms-tag">%s</span>' % tag)
            bits.append("<b>%s</b>" % _mini_sr(seg))
            if seg.get("kind") == "bw":
                bits.append("<span>%s</span>" % sl.T("unit.bw"))
            else:
                load = dm.row_load(seg, role)
                if load:
                    bits.append("<span>%s<i>%s</i></span>" % (dm.fmt_num(load), sl.T("unit.kg")))
            if rpe is not None:
                bits.append("<span>RPE %s</span>" % dm.fmt_num(rpe))
            if seg.get("pct") is not None:
                bits.append("<span>%d%% 1RM</span>" % int(round(float(seg["pct"]))))
            out.append(_mini_row(bits))
    out.append("</div>")
    return "".join(out)


def mini_test(mv, rows):
    """Test-day read-only attempts: one line each, no edit fields."""
    out = ['<div class="ms-lift"><div class="ms-h"><b>%s</b><span>%s</span></div>'
           % (sl.MV(mv), sl.T("test.attempts"))]
    for e in rows:
        bits = ["<b>1&times;1</b>"]
        if e.get("load") is not None:
            bits.append("<span>%s<i>%s</i></span>" % (dm.fmt_num(e["load"]), sl.T("unit.kg")))
        if e.get("targetRpe") is not None:
            bits.append("<span>RPE %s</span>" % dm.fmt_num(e["targetRpe"]))
        out.append(_mini_row(bits))
    out.append("</div>")
    return "".join(out)


def gear_summary(m):
    """One summary line for Mini and Max: wearable gear, then micro plates.

    Both views must read the same derived state. Mini used to count only
    ``m["gear"]["items"]`` and said "no gear" on a day whose fractional loads
    still need micro plates, while Max said "micro plates" for the same day.
    """
    n = len((m.get("gear") or {}).get("items") or [])
    if n:
        return sl.T("gear.required", n)
    if ((m.get("micro") or {}).get("groups") or []):
        return sl.T("gear.micro")
    return sl.T("gear.clear")


def micro_gear_lines(m):
    """Micro-plate chips per lift, same ``m["micro"]`` data Max's cabinet reads."""
    out = []
    for grp in (m.get("micro") or {}).get("groups") or []:
        sizes = [("%g" % float(x)) for x in (grp.get("used") or [])]
        if not sizes:
            continue
        out.append("<li>%s %s %s</li>"
                   % (lift_html(grp.get("label")), " / ".join(sizes), sl.T("unit.kg")))
    return out


def mini_gear(m):
    """Gear stays folded: a title, the same one-line summary Max shows, and a list."""
    items = [gear_label(it) for it in (m["gear"].get("items") or [])]
    if not items:
        items = micro_gear_lines(m)
    suffix = gear_summary(m)
    if not items:
        return ('<div class="ms-gear ms-gear-empty"><span>%s</span><em>%s</em></div>'
                % (sl.T("gear.title"), suffix))
    return ('<details class="ms-gear"><summary><span>%s</span><em>%s</em>'
            '<b aria-hidden="true">+</b></summary><ul>%s</ul></details>'
            % (sl.T("gear.title"), suffix, "".join(items)))


def mini_blocks(m):
    """The Mini whitelist: main lifts (+variations), accessories, folded gear."""
    mains = list(m["mains"])
    accs = list(m["accs"])
    out = []
    if m.get("is_test"):
        for mv, rows in mains:
            out.append(mini_test(mv, rows))
        for mv, rows in accs:
            out.append(mini_test(mv, rows))
    else:
        vars_ = [e for e in accs if dm.movement_role(e["mv"], e) == "variation"]
        rest = [e for e in accs if dm.movement_role(e["mv"], e) != "variation"]
        if mains or vars_:
            out.append('<p class="ms-k">%s</p>' % sl.T("sec.main"))
            for e in mains:
                out.append(mini_exercise(e, dm.movement_role(e["mv"], e)))
            for e in vars_:
                out.append(mini_exercise(e, "variation"))
        if rest:
            out.append('<p class="ms-k">%s</p>' % sl.T("sec.acc"))
            for e in rest:
                out.append(mini_exercise(e, "accessory"))
    out.append(mini_gear(m))
    return "".join(out)


def mini_sheet(plan, m):
    """Mini keeps one context line: week, date and day letter, then the whitelist."""
    d = m["date"]
    ctx = sl.D("W%d · %s %d · DAY %s" % (m["week"], dm.MONTH[d.month - 1], d.day, esc(m["day"])),
               "第 %d 周 · %d月%d日 · %s 日" % (m["week"], d.month, d.day, esc(m["day"])))
    return '<section class="ms"><p class="ms-ctx">%s</p>%s</section>' % (ctx, mini_blocks(m))


def mini_plan_sheet(plan, iweek):
    """Plan page in Mini: this week's sessions, read-only.

    Every day is one link to its own page and repeats the same three blocks a
    day page shows in Mini (main + variations, accessories, folded gear). The
    week rail, progress, volume, legends, capacity board, muscle map and cardio
    panels are not rendered here at all.
    """
    out = ['<section class="ms"><p class="ms-k">%s &middot; %s</p>'
           % (sl.T("plan.week", "%d" % iweek),
              sl.D(plan.block_en[iweek], sl.block_zh(plan.block_en[iweek])))]
    for (w, did) in plan.sessions:
        if w != iweek:
            continue
        off = plan.days[did]["weekdayOffset"]
        d = plan.start + datetime.timedelta(days=(w - 1) * 7 + off)
        m = dm.build_day_model(plan, d, w, did)
        head = ('<a class="ms-day-h" href="../%s/"><span>%s %d</span>'
                '<b>%s</b><em aria-hidden="true">&rarr;</em></a>'
                % (dm.ymd6(d), wd(d), d.day, esc(did)))
        out.append('<div class="ms-day">%s%s</div>' % (head, mini_blocks(m)))
    out.append('</section>')
    return "".join(out)


def view_button(day_iso=""):
    """Mini / Max switch in the masthead next to theme and language.

    The label names the mode the page is IN, not the one it would switch to;
    aria-pressed marks Mini, and VIEW_JS refreshes both the text and the
    aria-label (including the Chinese one) on every toggle.
    """
    return ('<button type="button" class="themebtn" id="viewBtn" data-day="%s" '
            'aria-pressed="false" aria-label="Display mode: Max. Activate to switch to Mini.">Max</button>'
            % esc(day_iso))


def masthead(right, up_href=None, up_key="nav.plan", day_iso=None, share="", view=True):
    """Top bar. The tier capsule is not rendered here: the mast has no free
    horizontal space at 320-412, so the badge lives on the /plan/ title row
    instead (see PLAN_CSS .hero-title)."""
    up = ""
    if up_href:
        up = '<a class="up" href="%s">&#8592; %s</a>' % (up_href, sl.T(up_key))
    return ('<header class="mast%s">' % (" has-up" if up else "") + up +
            '<span class="brand"><span class="bsq" aria-hidden="true"></span>EXDARK</span>' +
            '<span class="mast-r"><span>%s</span>%s'
            '<button type="button" class="themebtn" id="themeBtn" aria-pressed="false" '
            'aria-label="Theme: DARK. Activate to switch.">DARK</button>'
            '<button type="button" class="themebtn" id="langBtn" aria-pressed="false" '
            'aria-label="Language: English. Activate to switch.">EN</button>'
            '%s</span></header>'
            % (right, view_button(day_iso or "") if view else "", share))


def sec_head(title_key, count=None):
    right = ('<span>%s</span>' % count) if count is not None else ""
    return '<div class="sec"><h2>%s</h2>%s</div>' % (sl.T(title_key), right)


def pill(key, kind=""):
    return '<span class="pill%s">%s</span>' % ((" " + kind) if kind else "", sl.T(key))


def pill_raw(text, kind=""):
    return '<span class="pill%s">%s</span>' % ((" " + kind) if kind else "", esc(text))


UNIT_KEYS = {
    "kg": "unit.kg", "min": "unit.min", "mins": "unit.min", "bpm": "unit.bpm",
    "t": "unit.t", "steps": "unit.steps", "s/side": "unit.s_side",
    "bw": "unit.bw", "sets": "unit.sets",
}


def unit_html(unit):
    """Display unit with its Chinese from the one UI table, never a literal."""
    u = str(unit or "").strip()
    key = UNIT_KEYS.get(u.lower())
    return sl.T(key) if key else esc(u)


def gpp_item_text(it):
    """One GPP row -> (name, target) HTML; Chinese rides in the language layer."""
    parts = it.get("items") or []
    if parts:
        names = [sl.D(p.get("name"), p.get("name_zh")) for p in parts]
        targets = [sl.D(unitize(p.get("target")), unitize(p.get("target_zh") or p.get("target")))
                   for p in parts]
        if len(parts) == 1:
            return names[0], targets[0]
        return " + ".join(names), " · ".join(t for t in targets if t)
    name = str(it.get("item") or "").strip()
    val = it.get("target_value")
    unit = str(it.get("target_unit") or "").strip()
    if val is None or str(val).strip() == "":
        return sl.D(name, dm.gpp_item_zh(name)), ""
    try:
        v = float(val)
        vs = fmt_int(v) if abs(v - round(v)) < 1e-9 else dm.fmt_num(v)
    except (TypeError, ValueError):
        vs = str(val)
    tail = "" if (unit and unit.lower() in name.lower()) else ((" " + unit) if unit else "")
    return sl.D(name, dm.gpp_item_zh(name)), sl.D(vs + tail, unitize(vs + tail))


def run_href(date):
    """Relative link from /plan/ or a day page to the run page for that date."""
    try:
        d = datetime.date.fromisoformat(str(date or ""))
    except ValueError:
        return ""
    return "../%s/" % dm.ymd6(d)


_RPE_RX = re.compile(r"RPE\s*([\d.]+(?:\s*[-–]\s*[\d.]+)?)", re.I)


def run_rpe(note):
    m = _RPE_RX.search(str(note or ""))
    if not m:
        return ""
    return m.group(1).replace("–", "-").replace(" ", "").rstrip(".")


_DUP_CN_PUNCT = re.compile(r"[，,]\s*([。！？；])|([。！？；])\s*[，,]")


def _tidy_cn_punct(s):
    """Collapse punctuation left dangling after a clause is removed.

    Stripping "RPE 3–4" out of "鼻呼吸，RPE 3–4。若…" used to leave "鼻呼吸，。若…";
    the comma now folds into the following stop.
    """
    prev = None
    while prev != s:
        prev = s
        s = _DUP_CN_PUNCT.sub(lambda m: m.group(1) or m.group(2), s)
    return s


def _cue_pick(s):
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", str(s or "")) if p.strip()]
    if not parts:
        return ""
    pick = next((p for p in parts if re.search(r"\bmin\b|\bminutes\b|\u5206\u949f", p, re.I)),
                parts[-1])
    pick = _RPE_RX.sub("", pick).strip(" ,;")
    return _tidy_cn_punct(pick).rstrip(".")


def run_cue(note):
    """One prescription sentence, RPE stripped out; Chinese from the cue layer."""
    raw = str(note or "").strip()
    if not raw:
        return ""
    return sl.D(_cue_pick(raw), _cue_pick(sl.DZ("run_note", raw)))


_GPP_NUM_RX = re.compile(r"^GPP-\d+\s*[·:.\-]?\s*", re.I)


GPP_LAYER_KEYS = {"gpp1": "gpp.layer.engine", "gpp2": "gpp.layer.frame",
                  "gpp3": "gpp.layer.reset", "gpp4": "gpp.layer.base"}


def gpp_layer_name(lid):
    """Contract layer label minus the GPP-n prefix; site copy may sharpen the Chinese."""
    lab = dm.gpp_layer(lid).get("label") or {}
    en = _GPP_NUM_RX.sub("", str(lab.get("en") or lid).upper()).strip() or lid.upper()
    zh = _GPP_NUM_RX.sub("", str(lab.get("zh") or "")).strip()
    key = GPP_LAYER_KEYS.get(lid)
    if key and sl.Z(key):
        zh = sl.Z(key)
    return sl.D(en, zh)


def gpp_group_head(lid):
    return '<h4>%s</h4>' % gpp_layer_name(lid)


GPP1_SWAP_NOTE = "gpp.swap"


def gpp_rows_html(items):
    lis = []
    for it in items:
        parts = it.get("items") or []
        if parts:
            for p in parts:
                lis.append('<li><b>%s</b><span>%s</span></li>'
                           % (sl.D(p.get("name"), p.get("name_zh")),
                              sl.D(unitize(p.get("target")),
                                   unitize(p.get("target_zh") or p.get("target")))))
        else:
            n, t = gpp_item_text(it)
            lis.append('<li><b>%s</b><span>%s</span></li>' % (n, t))
    return '<ul>%s</ul>' % "".join(lis)


def gpp_engine_tag(gw):
    """Capsule value: session count x activity, plus the run zone when uniform."""
    n = int(gw["engine"])
    if n == 0:
        return "0"
    labels = {a["key"]: (a.get("label") or {})
              for a in dm.gpp1_activities()}
    slots = gw.get("slots") or []
    key = slots[0] if slots else "run"
    lab = labels.get(key) or {}
    act = sl.T("gpp.act." + key) if sl.Z("gpp.act." + key) else esc(
        str(lab.get("en") or key).title())
    zone = ""
    if key == "run":
        zones = []
        for r in gw.get("runs") or []:
            z = str(r.get("zone") or "").strip().upper()
            z = z[4:].strip() if z.startswith("ZONE") else z
            if z and z not in zones:
                zones.append(z)
        if len(zones) == 1:
            zone = " " + zones[0]
    return "%s%s &times;%d" % (act, esc(zone), n)


def gpp1_tabs(uid, run_panel):
    """GPP-1 的四类切换（CSS-only，无脚本）：Run / Swim / Cycle / Basketball。

    面板内容：Run 用调用方给的处方；其余取契约 item_id 指向的目录条目，
    basketball 无计量处方，只显示 note。季节停用项不生成 tab。
    """
    acts = dm.gpp1_activities()
    out = ['<div class="segwrap">']
    for a in acts:
        rid = "%s-%s" % (uid, a["key"])
        out.append('<input type="radio" name="%s" id="%s"%s>'
                   % (esc(uid), esc(rid), " checked" if a["key"] == "run" else ""))
        lab = a.get("label") or {}
        out.append('<label for="%s">%s</label>'
                   % (esc(rid), sl.D(str(lab.get("en") or a["key"]), str(lab.get("zh") or ""))))
    out.append('<div class="seg-panels">')
    for a in acts:
        out.append('<div class="seg-panel">')
        if a["key"] == "run":
            out.append(run_panel)
            out.append('</div>')
            continue
        name = a.get("name_en") or (a.get("label") or {}).get("en") or a["key"]
        lab = (a.get("label") or {}).get("en") or a["key"]
        body_name = "" if name.lower() == lab.lower() else sl.D(name, a.get("name_zh"))
        if a.get("rx"):
            out.append('<p class="gppl-rx"><b>%s</b>%s%s &middot; %s</p>'
                       % (sl.D(lab, str((a.get("label") or {}).get("zh") or "")),
                       body_name, " " if body_name else "", sl.D(a["rx"], unitize(a["rx"]))))
        else:
            out.append('<p class="gppl-rx"><b>%s</b>%s</p>'
                       % (sl.D(lab, str((a.get("label") or {}).get("zh") or "")),
                          body_name))
        note = a.get("note_en") or ""
        if note:
            out.append('<p class="gppl-note">%s</p>' % sl.D(note, a.get("note")))
        out.append('<p class="gppl-note">%s</p>' % sl.T(GPP1_SWAP_NOTE))
        out.append('</div>')
    out.append('</div></div>')
    return "".join(out)


def run_week_panel(runs):
    if not runs:
        return '<p class="wm-empty">%s</p>' % sl.T("gpp.no_run")
    rows = []
    for r in runs:
        try:
            dt = datetime.date.fromisoformat(str(r.get("date") or ""))
            when = dmy(dt)
        except ValueError:
            when = wd_text(r.get("weekday"))
        zone = str(r.get("zone") or "").strip()
        dur = dm.fmt_num(r.get("duration_min"))
        href = run_href(r.get("date"))
        line = ('<b>%s</b><span>%s &middot; %s %s</span>'
                % (when, zone_html(zone), esc(dur), sl.T("unit.min")))
        if href:
            line = '<a href="%s">%s</a>' % (href, line)
        rows.append('<li>%s</li>' % line)
    return '<ul>%s</ul>' % "".join(rows)


def gpp_engine_body(plan, w, uid):
    """Inside the ENGINE capsule: four activity tabs and this week's schedule."""
    gw = dm.gpp_week(plan, w)
    split = gw["split"]
    out = []
    gpp1_rows = [r for r in split["gpp1"] if not r.get("slot")]
    if gpp1_rows:
        out.append(gpp_rows_html(gpp1_rows))
    out.append(gpp1_tabs(uid, run_week_panel(gw["runs"])))
    off = dm.gpp1_off_activities()
    if off:
        names = ", ".join((a.get("label") or {}).get("en") or a["key"] for a in off)
        out.append('<p class="gppl-note">%s</p>' % sl.T("gpp.season_off", names))
    return "".join(out)


def gpp_frame_reset_body(plan, w):
    """FRAME and RESET, grouped inside the single fine line."""
    gw = dm.gpp_week(plan, w)
    split = gw["split"]
    out = ['<div class="gpp-g">', gpp_group_head("gpp2"),
           gpp_rows_html(split["gpp2"]) if split["gpp2"]
           else '<p class="wm-empty">%s</p>' % sl.T("gpp.no_topup"),
           '</div>', '<div class="gpp-g">', gpp_group_head("gpp3"),
           gpp_rows_html(split["gpp3"]) if split["gpp3"]
           else '<p class="wm-empty">%s</p>' % sl.T("gpp.no_recovery"),
           '</div>']
    if split["baseline"]:
        base = " &middot; ".join(
            " ".join(x for x in gpp_item_text(it) if x) for it in split["baseline"])
        out.append('<p class="gppl-base"><b>%s</b>%s</p>'
                   % (sl.T("gpp.base"), base))
    return "".join(out)


def gpp_engine_capsule(plan, w, uid):
    """Second level: one capsule carrying ENGINE + this week's actual content."""
    gw = dm.gpp_week(plan, w)
    return ('<details class="gpp-cap"><summary>'
            '<span class="gpp-cap-k">%s</span>'
            '<em class="gpp-cap-v">%s</em><b>+</b></summary>'
            '<div class="wm-body">%s</div></details>'
            % (gpp_layer_name("gpp1"), gpp_engine_tag(gw),
               gpp_engine_body(plan, w, uid)))


def gpp_layer_plain(lid):
    """Layer label as plain text pairs, for lines that carry a unit after the count."""
    lab = dm.gpp_layer(lid).get("label") or {}
    en = _GPP_NUM_RX.sub("", str(lab.get("en") or lid).upper()).strip() or lid.upper()
    zh = sl.Z(GPP_LAYER_KEYS.get(lid, "")) or _GPP_NUM_RX.sub("", str(lab.get("zh") or "")).strip()
    return en, zh


def gpp_frame_reset_fine(plan, w):
    """Third level: FRAME and RESET collapsed into one thin count line."""
    gw = dm.gpp_week(plan, w)
    f_en, f_zh = gpp_layer_plain("gpp2")
    r_en, r_zh = gpp_layer_plain("gpp3")
    bits = sl.DH("%s %d · %s %d" % (f_en, int(gw["frame"]), r_en, int(gw["reset"])),
                 "%s %d 次 · %s %d 次" % (f_zh, int(gw["frame"]), r_zh, int(gw["reset"])))
    return ('<details class="gpp-fine"><summary><span>%s</span><b>+</b></summary>'
            '<div class="wm-body gpp-groups">%s</div></details>'
            % (bits, gpp_frame_reset_body(plan, w)))


def goals_fold(plan):
    """Career goals are not weekly tasks: their own quiet fold."""
    goals = getattr(plan, "goals", []) or []
    label = "%s %d" % (sl.T("fold.goals"), len(goals))
    if goals:
        rows = []
        for g in goals:
            title = str(g.get("title") or g.get("id") or "").strip()
            deadline = str(g.get("deadline_date") or "").strip()
            age = g.get("deadline_age")
            meta = sl.T("fold.by_date", deadline) if deadline else (
                sl.T("fold.by_age", age) if age is not None else sl.T("fold.no_date"))
            rows.append('<li><b>%s</b><span>%s &middot; %s</span></li>'
                        % (sl.D(title, sl.DZ("goal", g.get("id"))), meta,
                           sl.T("fold.career_goal")))
        body = '<ul>%s</ul>' % "".join(rows)
    else:
        body = '<p class="wm-empty">%s</p>' % sl.T("fold.no_goals")
    return ('<details class="wk-more goals-fold"><summary><span>%s</span>'
            '<em>%s</em><b>+</b></summary>'
            '<div class="wm-body">%s</div></details>'
            % (label, sl.T("fold.goals_sub"), body))


def week_extras(plan, w):
    """Plan calendar, week strip: ENGINE capsule, FRAME/RESET line, goals fold."""
    return (gpp_engine_capsule(plan, w, "g1-w%d" % w)
            + gpp_frame_reset_fine(plan, w)
            + goals_fold(plan))


def gpp_day_fold(plan, w):
    """Training-day page: ENGINE and FRAME/RESET share the closing-row skeleton.

    The plan calendar keeps the accent capsule (gpp_engine_capsule); only the
    day page swaps to the neutral module row so the four closing blocks read as
    one stack.
    """
    gw = dm.gpp_week(plan, w)
    engine = ('<details class="mod engine"><summary class="mskel">'
              '<span class="k">%s</span><em class="v">%s</em><span class="x">+</span>'
              '</summary><div class="modb">%s</div></details>'
              % (gpp_layer_name("gpp1"), gpp_engine_tag(gw),
                 gpp_engine_body(plan, w, "g1-dw%d" % w)))
    bits = "%s %d &middot; %s %d" % (
        gpp_layer_name("gpp2"), int(gw["frame"]),
        gpp_layer_name("gpp3"), int(gw["reset"]))
    frame = ('<details class="mod"><summary class="mskel">'
             '<span class="k">%s</span><em class="v"></em><span class="x">+</span>'
             '</summary><div class="modb">%s</div></details>'
             % (bits, gpp_frame_reset_body(plan, w)))
    return engine + frame


def gpp_frame_reset_fold(plan, w):
    """ENGINE day page: only the FRAME/RESET line; ENGINE is the page itself."""
    return gpp_frame_reset_fine(plan, w)


def run_next_line(run):
    if not run:
        return ""
    zone = str(run.get("zone") or "").strip()
    dur = dm.fmt_num(run.get("duration_min"))
    inner = ('<span class="k">%s</span><em class="v">%s &middot; %s &middot; %s %s</em>'
             '<span class="x" aria-hidden="true">&rsaquo;</span>'
             % (sl.T("run.next"), sl.T("run.tag"), zone_html(zone), esc(dur),
                sl.T("unit.min")))
    href = run_href(run.get("date"))
    if href:
        return '<a class="mskel modline run-next" href="%s">%s</a>' % (href, inner)
    return '<div class="mskel modline run-next">%s</div>' % inner


WARMUP_PATH = os.path.join(HERE, "..", "research", "warmup", "warmup.json")
_WARMUP = None


def warmup_content(path=WARMUP_PATH):
    """Body-prep copy is read from the research file; nothing is copied here."""
    global _WARMUP
    if _WARMUP is None:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        _WARMUP = {"items": doc.get("items") or [],
                   "cautions": doc.get("cautions") or []}
    return _WARMUP


def _lift_key(mv):
    s = str(mv or "").lower()
    if "squat" in s:
        return "squat"
    if "bench" in s:
        return "bench"
    if "deadlift" in s or "dead lift" in s:
        return "deadlift"
    return ""


def _warm_item(it):
    """One prep row: name, dose, one-line reason; C-level work is badged."""
    badge = ""
    if (str(it.get("evidence") or "").upper() == "C"
            or "经验" in str(it.get("source") or "")):
        badge = '<i class="wev">%s</i>' % sl.T("warm.evidence_c")
    return ('<li><span class="wname">%s%s</span>'
            '<span class="wdose">%s</span><em class="wwhy">%s</em></li>'
            % (sl.D(it.get("name_en"), it.get("name_zh")), badge,
               sl.D(it.get("dose"), sl.DZF("warm", it.get("id"), "dose")),
               sl.D(it.get("why"), sl.DZF("warm", it.get("id"), "why"))))


def _caution_line(rows):
    """Claim/verdict notes stay inside the warm-up block, never a new block."""
    return '<p class="wcaution">%s</p>' % " &middot; ".join(
        '<span><b>%s</b> %s</span>'
        % (sl.D(c.get("claim_en"), c.get("claim_zh")),
           sl.D(c.get("verdict"), c.get("verdict_zh")))
        for c in rows)


def warmup_fold(m):
    """Default-collapsed warm-up, rendered above the exercise list.

    Summary follows the same hierarchy as OPTIONAL / ACCESSORIES (label span,
    secondary em, trailing +). Expanded order is fixed: RAMP SETS first (the
    block you use with plates in hand), then BODY PREP (general, then one group
    per main lift in the day's order).
    """
    warm = m.get("warmup") or []
    src = warmup_content()
    mains = []
    for item in m.get("mains") or []:
        mv = item[0] if isinstance(item, tuple) else (item.get("mv") or "")
        key = _lift_key(mv)
        if key and key not in mains:
            mains.append(key)
    gen = sorted([x for x in src["items"] if x.get("lift") == "general"],
                 key=lambda x: x.get("priority") or 0)
    # Four core drills per lift; on a three-lift test day keep two each so the
    # expanded block stays inside the 1.5-screen budget.
    per_lift = 4 if len(mains) <= 2 else 2
    grouped = [(key, sorted([x for x in src["items"]
                             if x.get("lift") == key
                             and (x.get("priority") or 0) <= per_lift],
                            key=lambda x: x.get("priority") or 0))
               for key in mains]
    prep_n = len(gen) + sum(len(rows) for _k, rows in grouped)
    if not warm and not prep_n:
        return ""
    if prep_n and warm:
        sub = sl.T("fold.warmup_sub_both", prep_n)
    elif prep_n:
        sub = sl.T("fold.warmup_sub_prep", prep_n)
    else:
        sub = sl.T("fold.warmup_sub")
    body = []
    if warm:
        # Load progression comes first: it is the block you read with plates in hand.
        rows = []
        for g in warm:
            steps = "".join(
                '<span class="ramp-step"><b>%s</b>&times;%d &middot; %s</span>'
                % (sl.T("fold.bar") if st["pct"] is None else "%g%%" % st["pct"],
                   st["reps"], dm.fmt_num(st["kg"]))
                for st in g["steps"])
            rows.append('<div class="ramp"><div class="ramp-h">%s</div>'
                        '<div class="ramp-steps">%s</div></div>'
                        % (lift_html(g["label"]), steps))
        body.append('<div class="wsub">%s</div>%s'
                    % (sl.T("fold.ramp"), "".join(rows)))
    if prep_n:
        body.append('<div class="wsub">%s</div><p class="wtip">%s</p>'
                    % (sl.T("fold.prep"), sl.T("warm.tip")))
        # Claims with no lift binding belong to GENERAL, so they show on every
        # day instead of vanishing when that day has no matching main lift.
        general_warns = [c for c in src["cautions"] if not (c.get("lifts") or [])]
        body.append('<span class="wlift">%s</span><ul class="wlist">%s</ul>'
                    % (sl.T("warm.general"),
                       "".join(_warm_item(it) for it in gen)))
        if general_warns:
            body.append(_caution_line(general_warns))
        for key, rows in grouped:
            body.append('<span class="wlift">%s</span><ul class="wlist">%s</ul>'
                        % (sl.T("lift." + key),
                           "".join(_warm_item(it) for it in rows)))
        warns = [c for c in src["cautions"] if set(c.get("lifts") or []) & set(mains)]
        if warns:
            body.append(_caution_line(warns))
    return ('<details class="wk-more warm-fold"><summary>'
            '<span>%s</span><em>%s</em><b>+</b></summary>'
            '<div class="fold-body">%s</div></details>'
            % (sl.T("fold.warmup"), sub, "".join(body)))


def folds_block(m):
    """Injury watch: one warning line, and only when a rule is in force.

    No rules means no markup at all, so the block takes zero vertical space.
    """
    rules = m.get("injury") or []
    if not rules:
        return ""
    lis = []
    for r in rules:
        rid = str(r.get("id") or "")
        title = str(rid).replace("_", " ")
        rule = str(r.get("rule") or "").replace(">=", "≥").replace("<=", "≤").replace("_", " ")
        action = str(r.get("action") or "").replace(">=", "≥").replace("<=", "≤")
        lis.append('<li><b>%s</b>%s<em> &rarr; %s</em></li>'
                   % (sl.D(title, sl.DZF("injury", rid, "name")),
                      sl.D(rule, sl.DZF("injury", rid, "rule")),
                      sl.D(action, sl.DZF("injury", rid, "action"))))
    return ('<details class="mod inj"><summary class="mskel">'
            '<span class="k">%s</span><em class="v">%s</em><span class="x">+</span>'
            '</summary>'
            '<div class="modb"><ul class="inj">%s</ul></div></details>'
            % (sl.T("fold.injury"), sl.T("fold.injury_sub", len(rules)),
               "".join(lis)))


def rpe_label(rpe):
    """Numeric RPE for full logging; a three-step effort label for the lite view.

    Tiers follow the owner's split: >=9.5 failure, 7.5-9 near failure, <7.5
    reps in reserve. CSS swaps the two spans on html[data-view="mini"].
    """
    value = float(rpe)
    if value >= 9.5:
        key = "rpe.fail"
    elif value >= 7.5:
        key = "rpe.near"
    else:
        key = "rpe.reserve"
    return ('<span class="rpe-n">RPE %s</span><span class="rpe-t">%s</span>'
            % (dm.fmt_num(rpe), sl.T(key)))


def rx_row(seg, label=None, show_tag=True, rpe=None, role=None, label_key=None):
    """One prescribed set block with its own absolute load.

    Main lifts show kg to 0.5, variations to the 2.5 kg grid, accessories
    show sets × reps + RPE only (no load column).
    """
    tag = label or seg.get("label") or "WORK"
    sets = int(seg.get("sets") or 0)
    reps = seg.get("reps")
    if isinstance(reps, int):
        sr = "%d×%d" % (sets, reps)
        if seg.get("unit") == "s/side":
            sr += ' <em>%s</em>' % sl.T("unit.s_side")
    else:
        sr = esc(reps or "")
    if seg.get("amrap"):
        sr += "+"
    if rpe is not None:
        sr += ' <em class="rpe">· %s</em>' % rpe_label(rpe)
    load = dm.row_load(seg, role)
    pct = ""
    if role == "accessory":
        kg = ('<span class="rx-kg bw">%s</span>' % sl.T("unit.bw")
              if seg.get("kind") == "bw" else "")
    elif seg.get("kind") == "bw":
        kg = '<span class="rx-kg bw">%s</span>' % sl.T("unit.bw")
    elif load:
        kg = '<span class="rx-kg">%s<i>%s</i></span>' % (dm.fmt_num(load), sl.T("unit.kg"))
    else:
        kg = '<span class="rx-kg bw">—</span>'
    if role != "accessory" and seg.get("pct") is not None:
        # Integer everywhere: a card mixing "75%" and "72.8%" reads as two scales.
        pct = "%d%%" % int(round(float(seg["pct"])))
    if label_key:
        tag_html = '<span class="rx-tag">%s</span>' % sl.T(label_key)
    elif show_tag:
        tag_html = '<span class="rx-tag">%s</span>' % sl.D(tag, sl.Z(RX_TAG_KEYS[tag])
                                                          if tag in RX_TAG_KEYS else "")
    else:
        tag_html = ""
    return ('<div class="rx-row">%s'
            '<span class="rx-sr">%s</span>%s<span class="rx-pct">%s</span></div>'
            % (tag_html, sr, kg, esc(pct)))


MODE_EN = {
    "T1.Mod": "MAIN WORK", "T1.3x3": "CALIBRATION", "T1.Cal": "CALIBRATION",
    "CAL": "CALIBRATION", "T1.DL": "DELOAD",
    "T2.5x5": "MAIN WORK", "T2.Vol": "VOLUME", "T2.Mod": "MAIN WORK", "T2.DL": "DELOAD",
    "Top.Set": "TOP SET", "Top.Single": "TOP SINGLE",
}

RX_TAG_KEYS = {"WORK": "rx.work", "TOP": "rx.top",
               "BACK-OFF": "rx.backoff", "CAL": "rx.cal"}

CAT_KEY = {
    "MAIN LIFT": "cat.main_lift", "CALIBRATION": "cat.calibration",
    "DELOAD": "cat.deload", "MAIN WORK": "cat.main_work",
    "VOLUME": "cat.volume", "TOP SET": "cat.top_set",
    "TOP SINGLE": "cat.top_single", "ACCESSORY": "cat.accessory",
    "VARIATION": "cat.variation",
    "UPPER BACK": "cat.upper_back", "DELTS": "cat.delts",
    "CORE": "cat.core", "LATS": "cat.lats", "TRICEPS": "cat.triceps",
    "ROTATOR CUFF": "cat.rotator_cuff",
    "GLUTES / HAMSTRINGS": "cat.glutes_hamstrings",
    "LOWER BACK": "cat.lower_back", "QUADS": "cat.quads",
    "LATERAL DELTS": "cat.lateral_delts",
}

GEAR_KEY = {"belt": "gear.belt", "shoes": "gear.shoes", "sleeves": "gear.sleeves",
            "wrist": "gear.wrist", "chalk": "gear.chalk", "shirt": "gear.shirt"}


def gear_label(it):
    key = GEAR_KEY.get(str(it.get("id") or ""))
    return sl.T(key) if key else esc(it.get("label"))


def _clause(text):
    """Leading clause: enough for a subtitle, never a second copy of the fact."""
    return re.split(r"[,，;；]", str(text or ""), maxsplit=1)[0].strip()


def resident_always():
    """The always-on trio collapses into one summary cell, never three."""
    names = [sl.D(it.get("short_en") or it.get("name_en"),
                  it.get("short_zh") or it.get("name_zh"))
             for it in RESIDENT_ITEMS
             if (it.get("trigger") or {}).get("type") == "always"]
    return " &middot; ".join(names)


def resident_high(top):
    """Intensity-gated reminders; below their own threshold they leave no gap."""
    if top is None:
        return ""
    top_pct = int(round(float(top) * 100))
    cells = []
    for it in RESIDENT_ITEMS:
        trig = it.get("trigger") or {}
        if trig.get("type") != "intensity":
            continue
        if top_pct < int(trig.get("pct1rm_min") or 0):
            continue
        supp = SUPPLEMENTS_BY_ID.get(it.get("supplement_id") or "")
        if it.get("supplement_id") and not supp:
            # A dangling reference must disappear, never fall back to a second copy.
            continue
        if supp:
            dose_en = _clause(supp.get("dose_en")).split(" split")[0].strip()
            sub = sl.D(dose_en, _clause(supp.get("dose_zh")))
            grade = str(supp.get("evidence") or "").strip().lower()
            if grade:
                sub += " &middot; " + sl.T("gear.ev_" + grade)
        else:
            sub = sl.D(_clause(it.get("dose_en")), _clause(it.get("dose_zh")))
        cells.append('<span class="gitem res"><b>%s</b><em>%s</em></span>'
                     % (sl.D(it.get("name_en"), it.get("name_zh")), sub))
    return "".join(cells)


SUPP_ORDER = ("ergogenic", "deficiency", "weak")


def supp_card(it):
    """One supplement record; every fact comes from supplements.json."""
    timing = it.get("timing") or {}
    grade = str(it.get("evidence") or "").strip().lower()
    onset = sl.D(it.get("onset_en"), it.get("onset_zh"))
    relation = sl.D(timing.get("relation_en"), timing.get("relation_zh"))
    return ('<article class="supcard">'
            '<div class="sup-h"><h4>%s</h4>'
            '<span class="sup-chip">%s</span><span class="sup-chip ev">%s</span></div>'
            '<p class="sup-p"><b>%s</b>%s</p>'
            '<p class="sup-p"><b>%s</b>%s%s%s</p>'
            '<p class="sup-p"><b>%s</b>%s</p>'
            '<p class="sup-p"><b>%s</b>%s</p>'
            '</article>'
            % (sl.D(it.get("name_en"), it.get("name_zh")),
               sl.T("sup.class_" + str(it.get("class") or "")),
               sl.T("sup.ev_" + grade) if grade else "",
               sl.T("sup.dose"), sl.D(it.get("dose_en"), it.get("dose_zh")),
               sl.T("sup.timing"),
               sl.D(timing.get("window_en"), timing.get("window_zh")),
               (' <em>%s</em>' % onset) if onset else "",
               ('<span class="sup-rel">%s</span>' % relation) if relation else "",
               sl.T("sup.why"), sl.D(it.get("why_en"), it.get("why_zh")),
               sl.T("sup.cautions"), sl.D(it.get("cautions_en"), it.get("cautions_zh"))))


def supplements_block():
    """Reference table, folded by default and sharing the gear's visual language.

    Every fact (class, timing, dose, evidence) is read from supplements.json at
    build time; this renderer carries no copy of any dose string.
    """
    groups = []
    for cls in SUPP_ORDER:
        rows = [it for it in SUPP_ITEMS if it.get("class") == cls]
        if not rows:
            continue
        gid = "sup-%s" % cls
        groups.append('<section class="glayer sup-g" aria-labelledby="%s">'
                      '<h3 class="gl-h" id="%s"><span>%s</span><em>%d</em></h3>'
                      '<div class="sup-list">%s</div></section>'
                      % (gid, gid, sl.T("sup.class_" + cls), len(rows),
                         "".join(supp_card(it) for it in rows)))
    return ('<section class="gear sup" role="region" %s>'
            '<button class="gsum" type="button" aria-expanded="false">'
            '<span class="gsum-k">%s</span><span class="gsum-v">%s</span>'
            '<b class="gsum-x">+</b></button>'
            '<div class="gwrap"><div class="glayers">'
            '<div class="sup-head"><h2>%s</h2><p>%s</p></div>'
            '%s<p class="sup-foot">%s</p></div></div></section>'
            % (sl.A("aria-label", "sup.title"),
               sl.T("sup.title"), sl.T("sup.sub", len(SUPP_ITEMS)),
               sl.D(SUPP_META.get("title_en"), SUPP_META.get("title_zh")),
               sl.D(SUPP_META.get("scope_en"), SUPP_META.get("scope_zh")),
               "".join(groups),
               sl.D(SUPP_META.get("disclaimer_en"), SUPP_META.get("disclaimer_zh"))))


def day_share_json(plan, m, d, week, did):
    """Fields for ShareCard kind=day; all numbers measured from the session."""
    s = m["session"]
    vol = dm.session_volume(plan, s)
    sets = 0
    reps = 0
    dist = {}
    for e in s.get("exercises") or []:
        kg = 0.0
        role = dm.movement_role(e.get("mv"), e)
        for seg in dm.prescription(e):
            n = int(seg.get("sets") or 0)
            sets += n
            r = seg.get("reps")
            if isinstance(r, int) and r > 0:
                reps += n * r
            load = dm.row_load(seg, role)
            if isinstance(r, int) and r > 0 and load:
                kg += load * n * r
        if kg > 0:
            name = str(e.get("mv") or "")
            dist[name] = dist.get(name, 0.0) + kg
    bests = {"squat": 0, "bench": 0, "deadlift": 0}
    for it in dm.main_loads(plan, s):
        if it["lift"] in bests:
            bests[it["lift"]] = int(round(it.get("load") or 0))
    top = (m.get("signals") or {}).get("top")
    rows = [{"name": n, "kg": int(round(kg))} for n, kg in dist.items()]
    rows.sort(key=lambda x: -x["kg"])
    return {"kind": "day", "date": dm.iso_date(d), "week": week, "dayType": did,
            "tonnageKg": int(vol["kg"]), "exercises": len(s.get("exercises") or []),
            "sets": sets, "reps": reps,
            "topIntensity": int(round(float(top) * 100)) if top is not None else 0,
            "bests": bests, "distribution": rows}


SHARE_JS = """<script>
(function(){
  var btn=document.getElementById('dayShareBtn');
  if(!btn||!window.ShareCard||!window.__DAY_SHARE)return;
  function theme(){
    var cs=getComputedStyle(document.documentElement);
    var v=function(n){return cs.getPropertyValue(n).trim()};
    return {bg:v('--bg'),ink:v('--ink'),ink2:v('--tx2'),mut:v('--tx3'),
            line:v('--line'),accent:v('--acc'),accentText:v('--acc')};
  }
  async function shareDay(){
    var day=window.__DAY_SHARE;
    var lang=document.documentElement.getAttribute('data-lang')==='zh'?'zh':'en';
    btn.disabled=true;
    try{
      var blob=await ShareCard.toBlob(day,{theme:theme(),kind:'day',lang:lang,unit:'t'});
      var file=new File([blob],'ExDark_session_'+day.date+'.png',{type:'image/png'});
      if(navigator.canShare&&navigator.canShare({files:[file]})){
        try{await navigator.share({files:[file],title:'ExDark · '+day.date});return;}
        catch(e){if(e&&e.name==='AbortError')return;}
      }
      var url=URL.createObjectURL(blob);
      var a=document.createElement('a');
      a.href=url;a.download=file.name;
      document.body.appendChild(a);a.click();a.remove();
      setTimeout(function(){URL.revokeObjectURL(url)},1000);
    }catch(e){if(window.console)console.error('share failed',e);}
    finally{btn.disabled=false;}
  }
  btn.addEventListener('click',shareDay);
})();
</script>"""


def share_button(compact=False):
    if compact:
        return ('<button type="button" class="mbtn" id="dayShareBtn" %s>'
                '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none"'
                ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
                ' stroke-linejoin="round"><path d="M12 16V4"></path>'
                '<path d="M7 9l5-5 5 5"></path>'
                '<path d="M5 14v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"></path></svg>'
                '</button>'
                % sl.A("aria-label", "share.aria"))
    return ('<button type="button" class="day-share" id="dayShareBtn" %s>'
            '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none"'
            ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
            ' stroke-linejoin="round"><path d="M12 16V4"></path>'
            '<path d="M7 9l5-5 5 5"></path>'
            '<path d="M5 14v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"></path></svg>'
            '<span>%s</span></button>'
            % (sl.A("aria-label", "share.aria"), sl.T("share.label")))


def plan_share_json(plan, vols):
    """Fields for ShareCard kind=cycle; every number is measured from the plan.

    Same pass that feeds the plan page (day_model.volumes), weekly kg list,
    total tonnage and session count included. bests are the highest planned
    main-lift loads across the cycle, not claimed 1RMs: seed mode has no
    anchors, so this is the only definition that reads the same in both modes.
    """
    bests = {"squat": 0, "bench": 0, "deadlift": 0}
    for s in plan.sessions.values():
        for it in dm.main_loads(plan, s):
            if it["lift"] in bests:
                bests[it["lift"]] = max(bests[it["lift"]],
                                        int(round(it.get("load") or 0)))
    weekly = [int(vols["weeks"].get(w, {}).get("kg") or 0)
              for w in range(1, plan.total_weeks + 1)]
    return {"kind": "cycle",
            "cycle": {"start": dm.iso_date(plan.start),
                      "end": dm.iso_date(plan.last_train[0]),
                      "weeks": plan.total_weeks},
            "tonnageKg": int(vols["total"]),
            "sessions": plan.n_training,
            "bests": bests,
            "weeklyKg": weekly,
            "brand": "ExDark"}


PLAN_SHARE_JS = """<script>
(function(){
  var btn=document.getElementById('planShareBtn');
  if(!btn||!window.ShareCard||!window.__PLAN_SHARE)return;
  function theme(){
    var cs=getComputedStyle(document.documentElement);
    var v=function(n){return cs.getPropertyValue(n).trim()};
    return {bg:v('--bg'),ink:v('--ink'),ink2:v('--tx2'),mut:v('--tx3'),
            line:v('--line'),accent:v('--acc'),accentText:v('--acc')};
  }
  async function shareCycle(){
    var cyc=window.__PLAN_SHARE;
    var lang=document.documentElement.getAttribute('data-lang')==='zh'?'zh':'en';
    btn.disabled=true;
    try{
      var blob=await ShareCard.toBlob(cyc,{theme:theme(),kind:'cycle',lang:lang,unit:'t'});
      var name='ExDark_cycle_'+cyc.cycle.start+'_'+cyc.cycle.end+'.png';
      if(navigator.canShare&&navigator.canShare({files:[blob]})){
        var file=new File([blob],name,{type:'image/png'});
        try{await navigator.share({files:[file],title:'ExDark · CYCLE '+cyc.cycle.weeks});return;}
        catch(e){if(e&&e.name==='AbortError')return;}
      }
      var url=URL.createObjectURL(blob);
      var a=document.createElement('a');
      a.href=url;a.download=name;
      document.body.appendChild(a);a.click();a.remove();
      setTimeout(function(){URL.revokeObjectURL(url)},1000);
    }catch(e){if(window.console)console.error('share failed',e);}
    finally{btn.disabled=false;}
  }
  btn.addEventListener('click',shareCycle);
})();
</script>"""


def plan_share_button(compact=False):
    if compact:
        return ('<button type="button" class="mbtn" id="planShareBtn" %s>'
                '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none"'
                ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
                ' stroke-linejoin="round"><path d="M12 16V4"></path>'
                '<path d="M7 9l5-5 5 5"></path>'
                '<path d="M5 14v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"></path></svg>'
                '</button>'
                % sl.A("aria-label", "share.plan.aria"))
    return ('<button type="button" class="day-share" id="planShareBtn" %s>'
            '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none"'
            ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
            ' stroke-linejoin="round"><path d="M12 16V4"></path>'
            '<path d="M7 9l5-5 5 5"></path>'
            '<path d="M5 14v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"></path></svg>'
            '<span>%s</span></button>'
            % (sl.A("aria-label", "share.plan.aria"), sl.T("share.label")))


def plate_sheet():
    """Persistent plate calculator entry, prefilled from a main-lift card.

    The entry is the LOAD card itself (same place as the App's LOAD affordance);
    the algorithm is tools/plate_math.js, inlined once per page below.
    """
    bars = "".join('<option value="%s"%s>%s kg</option>'
                   % (dm.fmt_num(v), " selected" if v == PLATE_BAR_DEFAULT else "",
                      dm.fmt_num(v))
                   for v in PLATE_BAR_OPTIONS)
    return ('<div class="pcalc" id="plateCalc" hidden>'
            '<div class="pcalc-b" role="dialog" aria-modal="true" aria-labelledby="pcalcTitle">'
            '<div class="pcalc-h"><h2 id="pcalcTitle">%s</h2>'
            '<button class="pcalc-x" id="pcalcX" type="button" %s>&times;</button></div>'
            '<div class="pcalc-row">'
            '<div class="pcalc-f"><label class="pcalc-k" for="pcalcIn">%s</label>'
            '<input class="pcalc-in" id="pcalcIn" type="number" inputmode="decimal"'
            ' step="0.25" min="0"></div>'
            '<div class="pcalc-f"><label class="pcalc-k" for="pcalcBar">%s</label>'
            '<select class="pcalc-sel" id="pcalcBar">%s</select></div></div>'
            '<div class="pcalc-o">'
            '<div class="pcalc-g"><span class="pcalc-k">%s</span>'
            '<div class="pcalc-plates" id="pcalcBarOut"></div></div>'
            '<div class="pcalc-g"><span class="pcalc-k">%s</span>'
            '<div class="pcalc-plates" id="pcalcPlates"></div></div>'
            '<p class="pcalc-note" id="pcalcNote"></p></div>'
            '<button class="pcalc-done" id="pcalcDone" type="button">%s</button>'
            '</div></div>'
            % (sl.T("plate.title"), sl.A("aria-label", "plate.close"),
               sl.T("plate.total"), sl.T("plate.bar"), bars,
               sl.T("plate.bar"), sl.T("plate.per_side"), sl.T("plate.done")))


PLATE_UI_JS = """<script>
(function(){
  var root=document.getElementById('plateCalc');
  if(!root||!window.RPLPlateMath)return;
  var input=document.getElementById('pcalcIn'), barSel=document.getElementById('pcalcBar');
  var barOut=document.getElementById('pcalcBarOut'), platesOut=document.getElementById('pcalcPlates');
  var note=document.getElementById('pcalcNote');
  var STOCK=window.__PLATE_STOCK__||[], BAR=window.__PLATE_BAR__;
  function zh(){return document.documentElement.getAttribute('data-lang')==='zh'}
  function T(k,en,vals){
    var s=en;
    if(zh()){var z=window.RPL_ZH&&window.RPL_ZH[k];if(z)s=z}
    if(vals)for(var i=0;i<vals.length;i++)s=s.replace('{'+i+'}',vals[i]);
    return s;
  }
  function fmt(n){return String(Math.round((+n||0)*100)/100)}
  function chip(kg,bar){
    return '<span class="pcalc-p'+(bar?' bar':'')+'">'+fmt(kg)+'<i>'+T('unit.kg','kg')+'</i></span>';
  }
  function render(){
    var total=parseFloat(input.value);
    if(!isFinite(total)){barOut.innerHTML='';platesOut.innerHTML='';note.textContent='';return}
    var bar=parseFloat(barSel.value);if(!isFinite(bar))bar=BAR;
    var r=RPLPlateMath.solve(total,bar,0,STOCK);
    barOut.innerHTML=chip(bar,true);
    platesOut.innerHTML=r.plateKgs.map(function(kg){return chip(kg,false)}).join('');
    var msg='';
    if(r.status==='below_bar')msg=T('plate.below_bar','Below bar weight ({0} kg)',[fmt(bar)]);
    else if(r.status==='remainder')msg=T('plate.remainder','Remainder {0} kg cannot be plated',[fmt(r.remainder)]);
    else if(!r.plateKgs.length)msg=T('plate.none','No plates needed');
    note.textContent=msg;
  }
  function open(v){
    input.value=v;barSel.value=String(BAR);root.hidden=false;render();
    try{input.focus();input.select()}catch(e){}
  }
  function close(){root.hidden=true}
  document.querySelectorAll('.ml[data-load]').forEach(function(b){
    b.addEventListener('click',function(){open(b.getAttribute('data-load'))});
  });
  document.getElementById('pcalcX').addEventListener('click',close);
  document.getElementById('pcalcDone').addEventListener('click',close);
  root.addEventListener('click',function(e){if(e.target===root)close()});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!root.hidden)close()});
  input.addEventListener('input',render);
  barSel.addEventListener('change',render);
  document.addEventListener('rpl:lang',function(){if(!root.hidden)render()});
})();
</script>"""


def plate_js():
    """The shared algorithm plus the page-local sheet wiring, both inline."""
    data = ('<script>window.__PLATE_STOCK__=%s;window.__PLATE_BAR__=%s;</script>'
            % (json.dumps(PLATE_STOCK), json.dumps(PLATE_BAR_DEFAULT)))
    return ('<script>\n%s\n</script>\n%s\n%s'
            % (PLATE_MATH_JS, data, PLATE_UI_JS))


_EQUIP_CACHE = None
_GEAR_WORDS = re.compile(r"腰带|护膝|护腕|绑腕|护具|弹力带|belt|sleeve|wrap|band", re.I)


def _equip_of(mv):
    global _EQUIP_CACHE
    if _EQUIP_CACHE is None:
        _EQUIP_CACHE = dm.equipment_map()
    return str((_EQUIP_CACHE.get(str(mv or "").lower()) or ("", ""))[0] or "")


def main_equipped(m, e):
    """True when this main lift needs protective or attached gear today.

    Same library the App reads: the day's gear evaluation (belt/sleeves/wraps
    triggered by intensity) plus the exercise's own ``equip`` string when it
    names wearable or attached gear.
    """
    lift = (dm.ANCHOR_CATEGORY.get(e.get("cat")) or {}).get("lift")
    if lift:
        for it in (m.get("gear") or {}).get("items") or []:
            if any(s.get("lift") == lift for s in it.get("sources") or []):
                return True
    return bool(_GEAR_WORDS.search(_equip_of(e.get("mv"))))


def log_row(seg, i, idx, role, rpe=None, prefix="c"):
    """Actual weight / sets / reps / RPE for one prescribed line.

    Hidden until the page is in full-log mode. Labels stay bare: the
    prescription line directly above already prints sets, reps, load and RPE,
    so repeating the targets here would be a second copy of the same numbers.
    """
    fields = []
    for f, key in (("kg", "log.kg"), ("sets", "log.sets"),
                   ("reps", "log.reps"), ("rpe", "log.rpe")):
        mode = ' inputmode="decimal"' if f in ("kg", "rpe") else ' inputmode="numeric"'
        fields.append('<label class="lg"><span>%s</span>'
                      '<input type="text"%s data-f="%s" '
                      'autocomplete="off" %s></label>'
                      % (sl.T(key), mode, f, sl.A("aria-label", key)))
    return ('<div class="rx-log" data-k="%s%02d|%d" role="group" %s>'
            '<span class="lg-tag">%s</span>%s</div>'
            % (prefix, idx, i, sl.A("aria-label", "log.aria"),
               sl.T("log.act"), "".join(fields)))


# RPE -> %1RM: reps in reserve (RIR = 10 - RPE) is added to the rep count, and
# the sum is read off the RPE-10 column of the Reactive Training Systems chart.
# That single column reproduces every RPE row, e.g. 3 reps @ RPE 9 == 4 reps @
# RPE 10 == 92.2%. Source: RTS "RPE Chart" (Mike Tuchscherer), 1-20 reps.
# Half-point RPEs round to the nearest whole rep; anything past 20 reps clamps
# to the 20-rep value, which keeps the estimate inside the chart.
_RTS_PCT_BY_TOTAL_REPS = (
    None, 100.0, 95.5, 92.2, 89.2, 86.3, 83.7, 81.1, 78.6, 76.2, 74.0,
    72.0, 70.0, 68.3, 66.7, 65.2, 63.8, 62.5, 61.2, 60.0, 58.8,
)


def est_pct_1rm(reps, rpe):
    """Estimated %1RM for a prescribed set, from reps and target RPE."""
    if not isinstance(reps, int) or reps <= 0 or rpe is None:
        return None
    total = int(round(reps + (10.0 - float(rpe))))
    if total < 1:
        return None
    total = min(total, len(_RTS_PCT_BY_TOTAL_REPS) - 1)
    return int(round(_RTS_PCT_BY_TOTAL_REPS[total]))


def card(e, idx, equipped=False):
    cat = dm.CAT_EN.get(e.get("cat"), "ACCESSORY")
    is_main = cat == "MAIN LIFT"
    role = dm.movement_role(e.get("mv"), e)
    tier = "main" if role == "main" else ("var" if role == "variation" else "acc")
    cal = dm.is_calibration(e)
    equipped = equipped and not cal
    if cal:
        cat = "CALIBRATION"
    elif is_main:
        cat = MODE_EN.get(e.get("mode"), cat)
        if e.get("mode") == "T1.3x3":
            cat = "MAIN WORK"
    elif role == "accessory" and cat == "VARIATION":
        cat = "ACCESSORY"           # e.g. Front Squat: a variation category, but an accessory row
    rpe_pill = ""
    if role != "accessory" and e.get("targetRpe") is not None:
        rpe_pill = '<span class="c-rpe">%s</span>' % rpe_label(e["targetRpe"])
    # Accessories repeat their estimate in the header only: the rx row below
    # already prints sets x reps and the target RPE, so the header carries the
    # one number the row cannot show — the intensity the pair implies.
    est = ""
    if role == "accessory" and e.get("targetRpe") is not None:
        first = next((sg for sg in (e.get("rxParts") or [])
                      if isinstance(sg.get("reps"), int)
                      and int(sg.get("sets") or 0) > 0), None)
        # A timed hold is prescribed in seconds, so a %1RM estimate is meaningless.
        pct = (None if _rx_unit(e) or not first
               else est_pct_1rm(first.get("reps"), e["targetRpe"]))
        if pct is not None:
            # Bodyweight rows have no external load, so no %1RM to estimate.
            # Sets x reps and RPE already sit in the rx row below; repeating
            # them here made the header and the row print the same numbers.
            bw = first.get("kind") == "bw"
            est = ('' if bw else
                   '<span class="c-est" %s><b>&asymp;%d%% 1RM</b></span>'
                   % (sl.A("title", "card.est_title"), pct))
    gear_tag = ('<span class="c-gear">%s</span>' % sl.T("card.gear")) if equipped else ""
    cls = tier + (" equip" if equipped else "")
    out = ['<article class="card %s rise" style="--d:%dms">' % (cls, 120 + idx * 40),
           '  <div class="c-head"><span class="c-idx">%d</span><div class="c-id">'
           '<div class="c-name">%s</div><div class="c-cat">%s%s</div></div>%s</div>'
           % (idx, sl.MV(e["mv"]), sl.T(CAT_KEY[cat]) if cat in CAT_KEY else esc(cat), gear_tag,
              est or rpe_pill)]
    segs = e.get("rxParts") or []
    lines = []
    for i, seg in enumerate(segs):
        lines.append(rx_row(seg, label=("CAL" if cal and len(segs) == 1 else None),
                            show_tag=(cal or len(segs) > 1 or seg.get("label") not in ("WORK", "BW")),
                            rpe=(e.get("targetRpe") if role == "accessory" else None), role=role))
        lines.append(log_row(seg, i, idx, role, rpe=e.get("targetRpe")))
    out.append('  <div class="rx">%s</div>' % "".join(lines))
    note = e.get("note")
    if cal:
        out.append('  <p class="cue">%s</p>' % sl.T("cal.note"))
    elif note and role == "accessory":
        out.append('  <details class="cnote"><summary><span>%s</span>'
                   '<span class="x">+</span></summary>'
                   '<p class="cue">%s</p></details>'
                   % (sl.T("card.note"), note_html(e["mv"], note)))
    elif note:
        out.append('  <p class="cue">%s</p>' % note_html(e["mv"], note))
    out.append('</article>')
    return "\n".join(out)


def test_card(mv, rows, idx):
    role = dm.movement_role(mv, rows[0] if rows else None)
    out = ['<article class="card main rise" style="--d:%dms">' % (120 + idx * 40),
           '  <div class="c-head"><span class="c-idx">%d</span><div class="c-id">'
           '<div class="c-name">%s</div><div class="c-cat">%s</div></div></div>'
           % (idx, sl.MV(mv), sl.T("test.attempts"))]
    lines = []
    for i, e in enumerate(rows):
        label = ("1ST", "2ND", "3RD")[i] if i < 3 else ("ATT %d" % (i + 1))
        seg = {"sets": e.get("sets") or 1, "reps": e.get("reps") or 1,
               "unit": "", "load": e.get("load"), "pct": e.get("pctDisp"),
               "amrap": False, "label": label}
        lines.append(rx_row(seg, label, rpe=e.get("targetRpe"), role=role,
                            label_key=("test.1st", "test.2nd", "test.3rd")[i] if i < 3 else None))
        lines.append(log_row(seg, i, idx, role, rpe=e.get("targetRpe"), prefix="t"))
    out.append('  <div class="rx">%s</div>' % "".join(lines))
    out.append('</article>')
    return "\n".join(out)


LIFT_KEYS = {"SQUAT": "cap.lift.squat", "BENCH": "cap.lift.bench",
             "DEADLIFT": "cap.lift.deadlift"}


def lift_zh(label):
    key = LIFT_KEYS.get(str(label or "").strip().upper())
    return sl.Z(key) if key else ""


def mv_zh(name):
    """Plain-text Chinese for one movement name; empty when the library has none."""
    return sl.MOVE_ZH.get(str(name or "").strip(), "")


def lift_html(label):
    """Squat/Bench/Deadlift display label, Chinese from the UI table."""
    key = LIFT_KEYS.get(str(label or "").strip().upper())
    return sl.T(key) if key else esc(str(label or "").upper())


def brief(m, plan):
    vol = dm.session_volume(plan, m["session"])
    loads = dm.main_loads(plan, m["session"])
    out = ['<section class="brief rise" style="--d:60ms">',
           '  <div class="brief-h">%s</div>' % sl.T("brief.title")]
    if loads:
        out.append('  <div class="mainloads" style="grid-template-columns:repeat(%d,1fr)">' % len(loads))
        for l in loads:
            w = max(0.0, min(100.0, float(l["pct"] or 0) * 100.0))
            load_num = dm.fmt_num(l["load"])
            out.append('    <button class="ml" type="button" data-load="%s" %s>'
                       '<span class="ml-k">%s</span>'
                       '<span class="ml-p">%s<i>%s</i>'
                       '<span class="ml-calc" aria-hidden="true">'
                       '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
                       '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2.4" fill="currentColor" stroke="none"/>'
                       '</svg></span></span>'
                       '<span class="ml-v">%s</span>'
                       '<span class="ml-bar"><i style="width:%.0f%%"></i></span></button>'
                       % (load_num,
                          sl.A2("aria-label", "plate.open",
                                "%s %s" % (l["label"].upper(), load_num)),
                          lift_html(l["label"]), load_num, sl.T("unit.kg"),
                          dm.pct_fmt(l["pct"]), w))
        out.append('  </div>')
    else:
        out.append('  <p class="brief-empty">%s</p>' % sl.T("brief.no_main"))
    out.append('  <div class="brief-foot"><div class="bf-l"><span>%s</span>'
               '<em>%s</em></div>'
               '<div class="vol"><b data-count="%d">%s</b><span>%s</span></div></div>'
               % (sl.T("brief.full"), sl.T("brief.full_sub"),
                  vol["kg"], fmt_int(vol["kg"]), sl.T("unit.kg")))
    out.append('</section>')
    return "\n".join(out)


def plates_block(micro):
    """Micro-plate cabinet as its own layer, never inside HARD GEAR."""
    if not (micro.get("groups") or []):
        return ""
    return ('<div class="glayer"><div class="gl-h"><span>%s</span>'
            '<em>%s</em></div>%s</div>'
            % (sl.T("gear.micro"), sl.T("gear.micro_sub"), micro_cabinet(micro)))


def gear_block(m, plan, compact=False):
    g = m["gear"]
    sig = m.get("signals") or {}
    micro = m.get("micro") or {}
    plates = plates_block(micro)
    suffix = gear_summary(m)

    req = []
    if g["status"] == "no-main":
        req.append('<p class="gempty">%s</p>' % sl.T("gear.no_main"))
    elif not g["items"]:
        if g["status"] == "unknown":
            req.append('<p class="gempty">%s</p>' % sl.T("gear.unknown"))
        else:
            req.append('<p class="gempty">%s</p>' % sl.T("gear.none"))
    else:
        groups = []
        for it in g["items"]:
            for src in it["sources"]:
                grp = next((x for x in groups if x["lift"] == src["label"]), None)
                if grp is None:
                    grp = {"lift": src["label"], "pct": src["pct"], "items": []}
                    groups.append(grp)
                grp["items"].append(it)
        groups.sort(key=lambda x: {"Squat": 0, "Bench": 1, "Deadlift": 2}.get(x["lift"], 9))
        chunks = []
        for grp in groups:
            chips = "".join('<span class="gchip">%s</span>'
                            % gear_label(it) for it in grp["items"])
            chunks.append('<div class="gg"><div class="gg-head"><span>%s</span><b>%s</b></div>'
                          '<div class="gg-items">%s</div></div>'
                          % (lift_html(grp["lift"]), dm.pct_fmt(grp["pct"]), chips))
        req.append('<div class="gear-groups">%s</div>' % "".join(chunks))

    req_cls = "glayer req" if g["items"] else "glayer"
    req_html = ('<div class="%s"><div class="gl-h"><span>%s</span>'
                '<em>%s</em></div>%s</div>'
                % (req_cls, sl.T("gear.hard"), sl.T("gear.hard_sub"), "".join(req)))

    always_html = ('<div class="glayer always"><div class="gl-h"><span>%s</span>'
                   '<em>%s</em></div>'
                   '<div class="grow"><span class="gitem">%s</span>'
                   '<span class="gitem">%s</span></div></div>'
                   % (sl.T("gear.always"), sl.T("gear.always_sub"),
                      sl.T("gear.water"), resident_always()))

    resident_html = resident_high(sig.get("top"))
    high_html = ""
    if sig.get("coffee") or resident_html:
        meta = []
        if sig.get("top") is not None and sig["top"] >= 0.85:
            meta.append("top %s" % dm.pct_fmt(sig["top"]))
        if (sig.get("rpe") or 0) >= 8.5:
            meta.append("RPE %s" % dm.fmt_num(sig["rpe"]))
        coffee = ('<span class="gitem">%s</span>' % sl.T("gear.coffee")
                  if sig.get("coffee") else "")
        high_html = ('<div class="glayer high"><div class="gl-h"><span>%s</span>'
                     '<em>%s</em></div>'
                     '<div class="grow">%s%s</div></div>'
                     % (sl.T("gear.high"), esc(" · ".join(meta)), coffee, resident_html))

    opts = []
    if sig.get("straps"):
        why = "RDL" if sig.get("rdl") else sl.T("gear.dl_sets", sig.get("dlSets") or 0)
        opts.append('<span class="gitem">%s<em>%s</em></span>'
                    % (sl.T("gear.straps"), why))
    if sig.get("bands"):
        opts.append('<span class="gitem">%s<em>%s</em></span>'
                    % (sl.T("gear.bands"), esc(sig.get("bandsWhy") or "")))
    opt_html = ""
    if opts:
        opt_html = ('<div class="glayer opt"><div class="gl-h"><span>%s</span>'
                    '<em>%s</em></div><div class="grow">%s</div></div>'
                    % (sl.T("gear.optional"), sl.T("gear.optional_sub"), "".join(opts)))

    inner = req_html + plates + always_html + high_html + opt_html

    summary = ('<span class="gsum-k">%s</span><span class="gsum-v">%s</span>'
               % (sl.T("gear.title"), suffix))

    return ('<section class="gear%s"><button class="gsum" type="button" aria-expanded="false">'
            '%s<b class="gsum-x" aria-hidden="true">+</b></button>'
            '<div class="gwrap"><div class="glayers">%s</div></div></section>'
            % (" gear-c" if compact else "", summary, inner))


def plate_num(x):
    return ("%.2f" % float(x)).rstrip("0").rstrip(".")


def micro_cabinet(micro):
    """Per-main-lift plate cabinet: four plates, only the needed ones lit."""
    groups = micro.get("groups") or []
    if not groups:
        return ""
    blocks = []
    for grp in groups:
        entries = []
        for en in grp["entries"]:
            base = (en["load"] - dm.BAR_KG) / 2.0 - sum(en["plates"])
            parts = (["%s %s" % (plate_num(base), sl.T("unit.kg"))] if base > 0 else []) + \
                    ["%s %s" % (plate_num(p), sl.T("unit.kg")) for p in en["plates"]]
            per_side = " + ".join(parts) + sl.T("gear.per_side")
            entries.append('<span><b>%s</b>'
                           '<em>%s</em></span>'
                           % (sl.T("gear.to_reach", dm.fmt_num(en["load"])), per_side))
        plates = "".join(
            '<span class="plate%s"><b>%s</b></span>'
            % (" on" if size in grp["used"] else "", plate_num(size))
            for size in dm.MICRO_PLATE_SIZES)
        blocks.append('<div class="pcab"><div class="pcab-h"><span>%s</span>'
                      '<div class="pcab-loads">%s</div></div>'
                      '<div class="pcab-rack">%s</div></div>'
                      % (lift_html(grp["label"]), "".join(entries), plates))
    return "".join(blocks)


def nav_html(plan, d):
    prev_t = None
    nxt_t = None
    for t in plan.training_dates:
        if t[0] < d:
            prev_t = t
        elif t[0] > d and nxt_t is None:
            nxt_t = t
    def short(d):
        return md(d)

    if prev_t:
        prev = ('<a href="../%s/"><div class="l">%s</div><div class="v">%s &middot; %s</div></a>'
                % (dm.ymd6(prev_t[0]), sl.T("nav.prev"),
                   sl.T("plan.day_id", prev_t[2]), short(prev_t[0])))
    else:
        prev = ('<a href="../plan/"><div class="l">%s</div><div class="v">%s</div></a>'
                % (sl.T("nav.prev"), sl.T("nav.all_days")))
    if nxt_t:
        nxt = ('<a class="n2" href="../%s/"><div class="l">%s</div><div class="v">%s &middot; %s</div></a>'
               % (dm.ymd6(nxt_t[0]), sl.T("nav.next"),
                  sl.T("plan.day_id", nxt_t[2]), short(nxt_t[0])))
    else:
        nxt = ('<a class="n2" href="../plan/"><div class="l">%s</div><div class="v">%s</div></a>'
               % (sl.T("nav.next"), sl.T("nav.all_days")))
    return '<div class="nav">%s%s</div>' % (prev, nxt)


def hero_title(parts):
    """Join (english_text, html) parts with "·", keeping each part unbroken.

    The cycle word gets its own line on narrow screens: the serif theme is
    wider, so leaving it inline makes the same title one line in sans and two
    in serif — the header would jump when the theme changes.
    """
    out = []
    last = len(parts) - 1
    for i, (text, html_part) in enumerate(parts):
        if i:
            out.append('<span class="act%s">\u00b7</span>'
                       % (" cycsep" if i == last else ""))
        cls = "act cyc" if i == last else "act"
        if len(text) <= 18:
            out.append('<span class="%s">%s</span>' % (cls, html_part))
        else:
            out.append(html_part)
    return " ".join(out)


def _cycle_part(plan, m):
    """Cycle word: the five the App publishes, else the block name."""
    if m["deload"]:
        return sl.S("cycle.deload")[0], sl.T("cycle.deload")
    key = str(plan.block_cycle.get(m["week"]) or "")
    if key in dm.CYCLE_KEYS:
        i18n = "cycle." + key
        return sl.S(i18n)[0], sl.T(i18n)
    return m["blockEn"], sl.D(m["blockEn"], sl.block_zh(m["blockEn"]))


def _hero_parts(plan, m):
    """Main lifts in S→B→D order, then the cycle word — same wording as the App.

    A day with no competition-lift main (e.g. a clean day) falls back to its
    first movement instead of printing a dash.
    """
    parts = []
    for l in dm.main_loads(plan, m["session"]):
        key = "lift." + l["lift"]
        parts.append((sl.S(key)[0], sl.T(key)))
    if not parts:
        mv = ""
        for e in (m["session"].get("exercises") or []):
            mv = str(e.get("mv") or "").strip()
            if mv:
                break
        if not mv:
            mv = str(m["session"].get("title") or "").split("\u00b7")[0].strip()
        parts.append((mv, sl.MV(mv)))
    parts.append(_cycle_part(plan, m))
    return parts


def footer_anchors(plan):
    """1RM anchors printed from the plan's own Anchors table, with their source.

    A tested max and a conservative estimate must not look alike, so the source
    sits next to the number. A plan without the table says so; it never prints
    a 1RM reverse-engineered from a top set.
    """
    rows = []
    for aid, code, lift in (("sq", "SQ", "SQUAT"), ("bp", "BN", "BENCH"),
                            ("dl", "DL", "DEADLIFT")):
        a = (plan.anchors or {}).get(aid)
        if not a:
            continue
        src = str(a.get("source") or "").strip()
        rows.append("%s <b>%s</b> %s%s"
                    % (sl.D(code, lift_zh(lift)), dm.fmt_num(a["value"]),
                       unit_html(a.get("unit") or "kg"),
                       (" <i>%s</i>" % sl.D(src, sl.DZ("anchor", src))) if src else ""))
    if not rows:
        return '<span class="fanc none">%s</span>' % sl.T("footer.anchor_none")
    return ('<span class="fanc">%s &mdash; %s</span>'
            % (sl.T("footer.anchor_label"), " &middot; ".join(rows)))


def build_day_page(plan, d, week, did, share=True):
    # share=False 给 App 内嵌快照用：快照必须自包含，不能带 ../sharecard.js 这类外链。
    m = dm.build_day_model(plan, d, week, did)
    s = m["session"]
    title, title_zh = sl.S("title.day", week, did, dm.iso_date(d))
    body = [masthead("%s · %s" % (full_date(d), sl.T("nav.plan")), "../plan/", "nav.plan",
                     day_iso=dm.iso_date(d), share=share_button(compact=True) if share else ""),
            ]
    body.append('<div class="mini-only">%s</div>' % mini_sheet(plan, m))
    body.append('<div class="max-only">')
    kind = "deload" if m["deload"] else ("test" if m["is_test"] else "")
    body.append('<div class="hero rise" style="--d:0ms" data-kind="%s">' % kind)
    body.append('<div class="eyebrow"><i class="edate">%s &middot; </i>%s</div>'
                % (full_date(d),
                   sl.T("day.eyebrow", "%d" % week, did, m["seq"], m["n"])))
    body.append('<h1>%s</h1>' % hero_title(_hero_parts(plan, m)))
    tags = ['<span class="pill on">%s</span>'
            % sl.D(m["blockEn"], sl.block_zh(m["blockEn"]))]
    if week == 1:
        tags.append(pill("pill.calibration"))
    if m["deload"]:
        tags.append(pill("pill.deload", "dl"))
    if m["is_test"]:
        tags.append(pill("pill.test", "ts"))
    body.append('<div class="tags">%s</div>' % "".join(tags))
    body.append('</div>')

    body.append(brief(m, plan))
    # The LOAD cards are the plate-calculator entry; the sheet only exists where
    # there is at least one card to prefill from.
    has_loads = bool(dm.main_loads(plan, m["session"]))
    if has_loads:
        body.append(plate_sheet())

    # Gear sits right under the brief: it is what the session asks you to pack,
    # so it belongs before the exercise list. Folded by default.
    body.append(gear_block(m, plan, compact=bool(m["is_test"])))

    # Warm-up sits between gear and the work: pack first, prepare second, lift third.
    # Collapsed by default; body prep comes from research/warmup/warmup.json.
    body.append(warmup_fold(m))

    # The density switch lives in the masthead; the exercise list starts clean.
    idx = 0
    if m["is_test"]:
        if m["mains"]:
            body.append(sec_head("sec.main", "%d" % len(m["mains"])))
            for mv, rows in m["mains"]:
                idx += 1
                body.append(test_card(mv, rows, idx))
        if m["accs"]:
            body.append(sec_head("sec.acc", "%d" % len(m["accs"])))
            for mv, rows in m["accs"]:
                idx += 1
                body.append(test_card(mv, rows, idx))
    else:
        if m["mains"]:
            body.append(sec_head("sec.main", "%d" % len(m["mains"])))
            for e in m["mains"]:
                idx += 1
                body.append(card(e, idx, main_equipped(m, e)))
        if m["accs"]:
            vars_ = [e for e in m["accs"] if dm.movement_role(e["mv"], e) == "variation"]
            rest = [e for e in m["accs"] if dm.movement_role(e["mv"], e) != "variation"]
            if vars_:
                body.append(sec_head("sec.var", "%d" % len(vars_)))
                for e in vars_:
                    idx += 1
                    body.append(card(e, idx))
            if rest:
                vol = dm.session_volume(plan, m["session"])
                inner = []
                for e in rest:
                    idx += 1
                    inner.append(card(e, idx))
                body.append('<details class="wk-more accfold" open><summary>'
                            '<span>%s</span><em>%s</em><b>+</b></summary>'
                            '<div class="wm-body">%s</div></details>'
                            % (sl.T("sec.acc"),
                               sl.T("acc.sum", len(rest), vol["accessory"]),
                               "".join(inner)))

    body.append('<p class="lognote">%s</p>' % sl.T("log.note"))
    body.append(run_next_line(m.get("run_next")))
    body.append(gpp_day_fold(plan, week))
    body.append(folds_block(m))
    # Supplement reference closes the page: a lookup table, not a session step.
    body.append(supplements_block())
    body.append(nav_html(plan, d))
    body.append(FRIENDS)
    body.append('</div>')
    body.append('<footer class="foot day-foot">%s '
                '<a href="../plan/">%s &rarr;</a></footer>'
                % (footer_anchors(plan), sl.T("nav.all_days")))
    body.append(COUNT_JS)
    body.append(GEAR_JS)
    body.append(LOG_JS)
    if has_loads:
        body.append(plate_js())
    if share:
        share_data = json.dumps(day_share_json(plan, m, d, week, did),
                                ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        body.append('<script src="../sharecard.js"></script>')
        body.append('<script>window.__DAY_SHARE=%s;</script>' % share_data)
        body.append(SHARE_JS)
    return shell(title, "\n".join(body), title_zh=title_zh)


CAP_LIFTS = (("S", "SQUAT"), ("B", "BENCH"), ("D", "DEADLIFT"))


def capacity_panel(plan, vols, cur_week):
    """Interactive capacity board: lift, muscle, role and week views.

    Server-renders the full-cycle totals so the board is readable without JS.
    CAP_JS switches the analysis between dimensions (lift / muscle / main-vs-var
    / week), dims unselected rows and morphs the bars in place. Numbers come from
    day_model.volumes(), the same pass that feeds the weekly reconciliation, so
    the board can never disagree with the calendar.
    """
    n = plan.total_weeks
    weeks = vols["weeks"]

    def fmt_sets(x):
        x = float(x or 0)
        return ("%d" % int(round(x))) if abs(x - round(x)) < 1e-9 else ("%.1f" % x)

    items = {}
    for code, label in CAP_LIFTS:
        rr = dm.SBD_RANGES.get(code) or {}
        wr = rr.get("weekly_range") or [None, None]
        en, zh = sl.S("cap.lift." + label.lower())
        items[code] = {"k": code, "n": en, "z": zh, "kind": "lift",
                       "m": [weeks[w]["lifts"][code]["main"] for w in range(1, n + 1)],
                       "v": [weeks[w]["lifts"][code]["var"] for w in range(1, n + 1)],
                       "lo": wr[0], "hi": wr[1],
                       "mev": rr.get("mev"), "mrv": rr.get("mrv")}
    for g in dm.MUSCLE_GROUPS:
        rr = dm.GROUP_RANGES.get(g) or {}
        wr = rr.get("weekly_range") or [None, None]
        items[g] = {"k": g, "n": g.upper(), "z": sl.Z("cap.g." + g), "kind": "muscle",
                    "d": [weeks[w]["groups"][g] for w in range(1, n + 1)],
                    "w": [weeks[w]["groupsWeighted"][g] for w in range(1, n + 1)],
                    "lo": wr[0], "hi": wr[1],
                    "mev": rr.get("mev"), "mrv": rr.get("mrv")}
    order = ["S", "B", "D"] + dm.MUSCLE_GROUPS
    roles = [
        {"k": "R_MAIN", "n": "MAIN", "z": sl.Z("cap.role.main"), "kind": "role",
         "sub": "MAIN LIFTS", "sub_z": sl.Z("cap.role.main_sub"),
         "m": [weeks[w]["main"] for w in range(1, n + 1)], "v": [0] * n},
        {"k": "R_VAR", "n": "SBD VAR", "z": sl.Z("cap.role.var"), "kind": "role",
         "sub": "S/B/D VARIATIONS", "sub_z": sl.Z("cap.role.var_sub"),
         "m": [weeks[w]["sbdVar"] for w in range(1, n + 1)], "v": [0] * n},
        {"k": "R_ACC", "n": "ACCESSORY", "z": sl.Z("cap.role.acc"), "kind": "role",
         "sub": "ACCESSORY WORK", "sub_z": sl.Z("cap.role.acc_sub"),
         "m": [weeks[w]["accessory"] for w in range(1, n + 1)], "v": [0] * n},
    ]
    totals = [weeks[w]["sets"] for w in range(1, n + 1)]
    test_week = (plan.last_train[0] - plan.start).days // 7 + 1

    def all_sets(it):
        if it["kind"] == "muscle":
            return sum(it["w"])
        return sum(it["m"]) + sum(it["v"])



    deloads = [w for w in range(1, n + 1) if plan.is_deload(w)]
    deload_set = set(deloads)

    def bar(it, ref):
        return '<span class="cr-bar"><i data-bar style="width:%.1f%%"></i></span>' % (
            100.0 * all_sets(it) / ref)

    rows = ['<div class="cap-gh" data-grp="lift">%s</div>' % sl.T("cap.by_lift")]
    lift_peak = max(all_sets(items[k]) for k in ("S", "B", "D")) or 1
    for k in ("S", "B", "D"):
        it = items[k]
        on = " on" if k == "S" else ""
        pressed = "true" if k == "S" else "false"
        rows.append(
            '<button class="cap-row%s" type="button" data-cap="%s" data-grp="lift" data-zero="%d" aria-pressed="%s">'
            '<span class="cr-k"><b>%s</b><em>%s</em></span>'
            '<span class="cr-v"><b data-m>%s</b><i>%s</i></span>'
            '<span class="cr-v"><b data-v>%s</b><i>%s</i></span>%s'
            '<span class="cr-rng"><b>%s</b><em data-verdict>%s</em></span></button>'
            % (on, k, 1 if all_sets(it) == 0 else 0, pressed, k, sl.D(it["n"], it["z"]),
               fmt_sets(sum(it["m"])), sl.T("cap.main"),
               fmt_sets(sum(it["v"])), sl.T("cap.var"), bar(it, lift_peak),
               sl.T("cap.mev_mrv", fmt_sets(it["mev"]), fmt_sets(it["mrv"])),
               sl.T("cap.weekly_range", fmt_sets(it["lo"]), fmt_sets(it["hi"]))))
    rows.append('<div class="cap-gh" data-grp="muscle" hidden>%s '
                '<em>%s</em></div>' % (sl.T("cap.by_muscle"), sl.T("cap.by_muscle_sub")))
    muscle_peak = max(all_sets(items[g]) for g in dm.MUSCLE_GROUPS) or 1
    for g in dm.MUSCLE_GROUPS:
        it = items[g]
        rows.append(
            '<button class="cap-row dual" type="button" data-cap="%s" data-grp="muscle" '
            'data-zero="%d" aria-pressed="false" hidden>'
            '<span class="cr-k"><b>%s</b></span>'
            '<span class="cr-v main"><b data-w>%s</b><i>%s</i></span>'
            '<span class="cr-v sub"><b data-d>%s</b><i>%s</i></span>'
            '<span class="cr-z" hidden>%s</span>%s'
            '<span class="cr-rng"><b>%s</b><em data-verdict>%s</em></span></button>'
            % (g, 1 if all_sets(it) == 0 else 0, sl.D(it["n"], it["z"]),
               fmt_sets(sum(it["w"])), sl.T("cap.weighted"),
               fmt_sets(sum(it["d"])), sl.T("cap.direct"),
               sl.T("cap.not_programmed"), bar(it, muscle_peak),
               sl.T("cap.weekly_range", fmt_sets(it["lo"]), fmt_sets(it["hi"])),
               sl.T("cap.verdict.all")))
    rows.append('<div class="cap-gh" data-grp="role" hidden>%s '
                '<em>%s</em></div>' % (sl.T("cap.by_role"), sl.T("cap.by_role_sub")))
    role_peak = max(all_sets(it) for it in roles) or 1
    for it in roles:
        rows.append(
            '<button class="cap-row single" type="button" data-cap="%s" data-grp="role" '
            'data-zero="%d" aria-pressed="false" hidden>'
            '<span class="cr-k"><b>%s</b><em>%s</em></span>'
            '<span class="cr-v"><b data-t>%s</b><i>%s</i></span>%s</button>'
            % (it["k"], 1 if all_sets(it) == 0 else 0, sl.D(it["n"], it["z"]),
               sl.D(it["sub"], it["sub_z"]),
               fmt_sets(all_sets(it)), sl.T("cap.sets"), bar(it, role_peak)))
    rows.append('<div class="cap-gh" data-grp="week" hidden>%s '
                '<em>%s</em></div>' % (sl.T("cap.total_sets"), sl.T("cap.per_week")))
    week_peak = max(totals) or 1
    for j in range(1, n + 1):
        mark = (sl.T("cap.mark.deload") if j in deload_set
                else (sl.T("cap.mark.test") if j == test_week else ""))
        rows.append(
            '<button class="cap-row single" type="button" data-cap="w%d" data-grp="week" '
            'data-wk="%d" data-zero="%d" aria-pressed="false" hidden>'
            '<span class="cr-k"><b>%s</b><em>%s</em></span>'
            '<span class="cr-v"><b data-t>%d</b><i>%s</i></span>'
            '<span class="cr-bar"><i data-bar style="width:%.1f%%"></i></span></button>'
            % (j, j, 1 if totals[j - 1] == 0 else 0,
               sl.T("plan.week_bar", "%d" % j), mark, totals[j - 1],
               sl.T("cap.sets"), 100.0 * totals[j - 1] / week_peak))
    muscle_total = sum(all_sets(items[g]) for g in dm.MUSCLE_GROUPS)
    muscle_tot = [round(sum(weeks[w]["groupsWeighted"][g] for g in dm.MUSCLE_GROUPS), 1)
                  for w in range(1, n + 1)]
    rows.append('<p class="cap-empty" id="capEmpty"%s><span class="ce-art" aria-hidden="true"><i></i><i></i><i></i></span>'
                '<span>%s</span></p>'
                % ("" if muscle_total == 0 else " hidden", sl.T("cap.empty")))

    data = {"weeks": n, "deload": deloads, "test": test_week, "cur": cur_week,
            "total": totals, "totalAll": sum(totals),
            "mt": muscle_tot, "mtAll": round(sum(muscle_tot), 1),
            "coef": vols.get("coef", 1.0), "coefFinal": vols.get("coefFinal", False),
            "items": [items[k] for k in order], "roles": roles}
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\/")

    # First paint matches what CAP_JS shows on load: SQUAT, all cycle, lift view.
    first = items["S"]
    first_sets = all_sets(first)
    first_share = int(round(100.0 * first_sets / data["totalAll"])) if data["totalAll"] else 0
    s_series = [first["m"][j] + first["v"][j] for j in range(n)]
    peak_week = max(range(1, n + 1), key=lambda w: s_series[w - 1]) if n else 1
    peak_val = s_series[peak_week - 1] if n else 0
    delta_txt = sl.T("cap.peak", "%d" % peak_week, fmt_sets(peak_val))

    init_keys = ("S", "B", "D")
    init_max = max(all_sets(items[k]) for k in init_keys) or 1
    pool = max(len(init_keys), len(order), n)  # widest view defines the slot pool
    init_bars = []
    for j in range(pool):
        if j < len(init_keys):
            k = init_keys[j]
            it = items[k]
            m = sum(it["m"])
            v = sum(it["v"])
            cls = "cb" + (" on" if k == "S" else "")
            init_bars.append(
                '<button class="%s" type="button" data-ck="%s" aria-label="%s, %s sets" '
                'data-zh-aria-label="%s，%s 组">'
                '<b class="cbv">%s</b><span class="cbi">'
                '<i class="m" style="height:%.1fpx"></i>'
                '<i class="v" style="height:%.1fpx"></i></span><em>%s</em></button>'
                % (cls, k, esc(it["n"]), fmt_sets(m + v), esc(it["z"] or it["n"]),
                   fmt_sets(m + v), fmt_sets(m + v),
                   m * 88.0 / init_max, v * 88.0 / init_max, k))
        else:
            init_bars.append(
                '<button class="cb off" type="button" aria-hidden="true">'
                '<b class="cbv"></b><span class="cbi">'
                '<i class="m" style="height:0px"></i>'
                '<i class="v" style="height:0px"></i></span><em></em></button>')

    return ('<section class="cap" id="cap">'
            '<div class="cap-h"><div><div class="cap-k">%s</div>'
            '<h2 class="cap-t">%s<em>%s</em></h2></div>'
            '<div class="cap-mode" id="capMode">%s</div></div>'
            '<div class="cap-view" id="capView">'
            '<button type="button" class="on" data-view="lift" aria-pressed="true">%s</button>'
            '<button type="button" data-view="muscle" aria-pressed="false">%s</button>'
            '<button type="button" data-view="role" aria-pressed="false">%s</button>'
            '<button type="button" data-view="week" aria-pressed="false">%s</button></div>'
            '<div class="cap-list" id="capList">%s</div>'
            '<aside class="cap-detail" aria-live="polite">'
            '<div class="cd-top"><span>%s</span><b id="capName">%s</b></div>'
            '<div class="cd-num"><b id="capSets">%s</b>'
            '<i>%s <em id="capShare">%s%%</em></i>'
            '<span class="cd-delta flat" id="capDelta">%s</span></div>'
            '<div class="cd-rail"><i id="capRail" style="width:%s%%"></i></div>'
            '<div class="cd-sub" id="capSub">%s</div>'
            '<p class="cd-ref" id="capRef" hidden><span id="capRefA"></span><span id="capRefB"></span></p>'
            '<div class="cap-ctx" id="capCtx">'
            '<button type="button" id="capAll" class="on" aria-pressed="true">%s</button>'
            '<button type="button" id="capPrev" %s>&lsaquo;</button>'
            '<span id="capWk" class="muted">%s</span>'
            '<button type="button" id="capNext" %s>&rsaquo;</button></div>'
            '<div class="cd-cap" id="capCap">%s</div>'
            '<div class="cap-chart" id="capChart" style="--n:3" data-n="3">%s</div>'
            '<div class="cd-foot"><div class="cd-legend" id="capLg">'
            '<span><i class="lg m"></i>%s</span>'
            '<span><i class="lg v"></i>%s</span></div>'
            '<div class="cd-legend cap-note" id="capNote" hidden></div></div>'
            '</aside>'
            '<script type="application/json" id="capData">%s</script></section>'
            % (sl.T("cap.title"), sl.T("cap.working"), sl.T("cap.map", n),
               sl.T("cap.all_cycle"),
               sl.T("cap.view.lift"), sl.T("cap.view.muscle"),
               sl.T("cap.view.role"), sl.T("cap.view.week"),
               "".join(rows), sl.T("cap.selected"),
               sl.D(first["n"], first["z"]), fmt_sets(first_sets),
               sl.T("cap.sets"), first_share, delta_txt, first_share,
               sl.T("cap.sub_lift", fmt_sets(sum(first["m"])), fmt_sets(sum(first["v"]))),
               sl.T("cap.all"),
               sl.A("aria-label", "plan.prev_week"),
               sl.T("plan.week_bar", "%d" % cur_week),
               sl.A("aria-label", "plan.next_week"),
               sl.T("cap.by_lift") + " &middot; " + sl.T("cap.all_cycle"),
               "".join(init_bars),
               sl.T("cap.legend.main"), sl.T("cap.legend.var"), payload))


MMAP_JS = """
(function(){
var R=document.getElementById('mmap'),S=document.getElementById('mmAction'),
J=document.getElementById('mmData'),B=document.getElementById('mmRows');
if(!R||!S||!J||!B)return;
var D=JSON.parse(J.textContent||'{}'),A=D.a||[],O=D.o||[],N=D.n||[],Z=D.z||[],W=D.w||[],X=D.d||[];
var P=(+D.p||80)/100,Q=(+D.s||30)/100,cur=0;
function tier(c,m){return(!m||!c)?0:(c>=m*P-1e-9?1:(c>=m*Q-1e-9?2:0));}
function zh(){return document.documentElement.getAttribute('data-lang')==='zh';}
function fs(x){return(Math.abs(x-Math.round(x))<1e-9)?String(Math.round(x)):x.toFixed(1);}
function rows(){
 var v=(A[cur]||[])[1]||[],m=0,i,h='';
 for(i=0;i<v.length;i++)if(v[i]>m)m=v[i];
 for(i=0;i<O.length;i++){var k=O[i],c=+v[i]||0,t=(k==='adductors')?0:tier(c,m);
  var n=zh()?(Z[i]||N[i]):N[i];
  h+='<div class="mmr" data-leaf="'+k+'"><span class="a">'+n+'</span>'+
   '<b class="b t'+t+'">'+(c?(c/100).toFixed(2):'\\u2014')+'</b>'+
   '<b class="c">'+W[i].toFixed(1)+'</b><span class="d">'+fs(+X[i]||0)+'</span></div>';}
 B.innerHTML=h;
}
function paint(i){
 cur=i;var v=(A[i]||[])[1]||[],m=0,j,k,z=R.querySelectorAll('.mz');
 for(j=0;j<v.length;j++)if(v[j]>m)m=v[j];
 for(j=0;j<z.length;j++){k=z[j].getAttribute('data-leaf');
  var tt=(k==='adductors')?0:tier(+v[O.indexOf(k)]||0,m);
  z[j].setAttribute('class','mz t'+tt);}
 rows();
}
for(var i=0;i<A.length;i++){var o=document.createElement('option');
 o.value=i;o.textContent=A[i][0];S.appendChild(o);}
S.addEventListener('change',function(){paint(+this.value||0);});
document.addEventListener('rpl:lang',rows);
paint(0);
})();
"""


def _mm_figure(tiers, back=False):
    """Schematic front/back body: 16 leaf zones, no decorative base limbs."""
    def z(tag, leaf, attrs):
        # Adductors have no cited range, so they never take a shading tier.
        t = 0 if leaf == "adductors" else tiers.get(leaf, 0)
        return '<%s class="mz t%d" data-leaf="%s" %s/>' % (
            tag, int(t), leaf, attrs)

    parts = ['<svg viewBox="0 0 120 236" role="img" %s>'
             % sl.A("aria-label", "mmap.back" if back else "mmap.front"),
             '<circle class="mb" cx="60" cy="18" r="11"/>',
             '<path class="mb" d="M38 40h44l7 26-4 48H35l-4-48z"/>']
    if back:
        parts += [
            z("rect", "delts_post", 'x="30" y="40" width="60" height="9" rx="4"'),
            z("path", "upper_back", 'd="M40 44h40l-4 26H44z"'),
            z("path", "lats", 'd="M38 72h20l-2 30H36z"'),
            z("path", "lats", 'd="M82 72H62l2 30h20z"'),
            z("rect", "erectors", 'x="55" y="78" width="10" height="36"'),
            z("rect", "triceps", 'x="24" y="70" width="9" height="24" rx="3"'),
            z("rect", "triceps", 'x="87" y="70" width="9" height="24" rx="3"'),
            z("rect", "glutes", 'x="40" y="102" width="40" height="20" rx="5"'),
            z("rect", "hamstrings", 'x="40" y="114" width="16" height="48" rx="4"'),
            z("rect", "hamstrings", 'x="64" y="114" width="16" height="48" rx="4"'),
            z("rect", "calves", 'x="42" y="172" width="12" height="48" rx="4"'),
            z("rect", "calves", 'x="66" y="172" width="12" height="48" rx="4"'),
        ]
    else:
        parts += [
            z("rect", "delts_ant", 'x="30" y="40" width="60" height="9" rx="4"'),
            z("rect", "chest", 'x="43" y="44" width="34" height="22"'),
            z("rect", "delts_lat", 'x="24" y="50" width="8" height="18" rx="3"'),
            z("rect", "delts_lat", 'x="88" y="50" width="8" height="18" rx="3"'),
            z("rect", "biceps", 'x="24" y="70" width="9" height="24" rx="3"'),
            z("rect", "biceps", 'x="87" y="70" width="9" height="24" rx="3"'),
            z("rect", "forearms", 'x="24" y="96" width="8" height="28" rx="3"'),
            z("rect", "forearms", 'x="88" y="96" width="8" height="28" rx="3"'),
            z("rect", "core", 'x="45" y="68" width="30" height="32"'),
            z("rect", "quads", 'x="40" y="114" width="16" height="48" rx="4"'),
            z("rect", "quads", 'x="64" y="114" width="16" height="48" rx="4"'),
            z("rect", "adductors", 'x="56" y="114" width="8" height="46"'),
        ]
    parts.append("</svg>")
    return "".join(parts)


def muscle_map_panel(plan, vols, cur_week):
    """16-leaf body map driven by the finalised MuscleMap component.

    One ruler per scope: leaf ranges (RP direct sets) are compared with direct
    sets; the six group ranges live in capacity_panel and are compared with
    weighted sets. Crossing the two would invent deltas, so they stay apart.
    The map follows the week picked in the week switcher.
    """
    n = plan.total_weeks
    weeks = vols["weeks"]
    cur_week = max(1, min(n, int(cur_week or 1)))

    ranges = {}
    for k in dm.LEAF_ORDER:
        r = dm.LEAF_RANGES.get(k) or {}
        mev, mrv = r.get("mev"), r.get("mrv")
        if mev is None or mrv is None:
            ranges[k] = {"na": True}
            continue
        sc = r.get("scope") or ""
        ranges[k] = {"lo": mev, "hi": mrv,
                     "scope": "group" if sc.startswith("group") else "leaf",
                     "group": "back" if sc == "group_back" else "",
                     "sessions": r.get("spw") or 0,
                     "zero": mev == 0}

    # Literature reference: RP direct sets at 2 sessions/week. These numbers are
    # a different ruler from the six-group total-set ranges, so they live in a
    # fold and are never subtracted from the group scale.
    ref_rows, cited = [], 0
    for k in dm.LEAF_ORDER:
        r = dm.LEAF_RANGES.get(k) or {}
        mev, mrv = r.get("mev"), r.get("mrv")
        if mev is None or mrv is None:
            grade, rng, note = "&mdash;", "&mdash;", sl.T("mmap.ref.none")
        else:
            cited += 1
            grade = sl.T("mmap.ref.grade_label", esc(r.get("grade") or ""))
            rng = '%d&ndash;%d<small>%s</small>' % (mev, mrv, sl.T("mmap.ref.spw"))
            if mev == 0:
                # A zero-MEV note belongs under the range digits, never beside
                # them: side by side it reads as "0 sets prescribed here".
                rng += '<small class="zf">%s</small>' % sl.T("mmap.ref.zero")
            if r.get("scope") == "group_back":
                note = sl.T("mmap.ref.group_back")
            elif mev == 0:
                note = ""
            elif r.get("has_a"):
                note = sl.T("mmap.ref.direction")
            else:
                note = ""
        ref_rows.append(
            '<tr%s><td class="lf">%s</td><td class="n">%s</td><td>%s</td>'
            '<td class="note">%s</td></tr>'
            % (' class="off"' if mev is None else "", sl.T("leaf.%s" % k),
               rng, grade, note))
    ref_fold = (
        '<details class="mmref"><summary>%s<em>%s</em></summary>'
        '<p class="mmrsrc">%s</p>'
        '<table class="mmrt"><thead><tr><th>%s</th><th>%s</th><th>%s</th>'
        '<th class="note">%s</th></tr></thead><tbody>%s</tbody></table></details>'
        % (sl.T("mmap.ref.summary"), sl.T("mmap.ref.count", cited, len(dm.LEAF_ORDER)),
           sl.T("mmap.ref.source"),
           sl.T("mmap.ref.leaf"), sl.T("mmap.ref.range"), sl.T("mmap.ref.grade"),
           sl.T("mmap.ref.note"), "".join(ref_rows)))

    payload = {
        "order": dm.LEAF_ORDER,
        "cur": cur_week,
        "ranges": ranges,
        "weeks": {str(w): {
            "w": [round(weeks[w]["leavesWeighted"][k], 1) for k in dm.LEAF_ORDER],
            "d": [round(weeks[w]["leaves"][k], 1) for k in dm.LEAF_ORDER],
        } for w in range(1, n + 1)},
    }
    zero_leaves = [k for k in dm.LEAF_ORDER if (ranges.get(k) or {}).get("zero")]
    zero_note = (sl.T("mmap.ref.zero") + ": " +
                 ", ".join(sl.T("leaf.%s" % k) for k in zero_leaves)) if zero_leaves else ""

    ns_rows = []
    for k in dm.LEAF_ORDER:
        r = ranges.get(k) or {}
        val = weeks[cur_week]["leaves"][k]
        if r.get("na"):
            rng = sl.S("mmap.ref.none")[0]
        elif r.get("zero"):
            rng = sl.S("mmap.ref.zero")[0]
        else:
            rng = "%d&ndash;%d &middot; %s" % (r["lo"], r["hi"], sl.S("mmap.ref.spw")[0])
        ns_rows.append("<li><b>%s</b> %s %s &middot; %s</li>"
                       % (sl.S("leaf.%s" % k)[0], dm.fmt_num(val),
                          sl.S("mmap.col.direct")[0], rng))
    noscript = '<noscript><ol class="mmns">%s</ol></noscript>' % "".join(ns_rows)

    geo_embed = dict(MUSCLE_GEO)
    if isinstance(geo_embed.get("source"), dict):
        # The snapshot is reviewed as self-contained: keep attribution, drop URLs.
        geo_embed["source"] = {k: v for k, v in geo_embed["source"].items() if k != "repo"}

    body = (
        '<section class="mmap" id="mmap">'
        '<div class="mmh"><span class="mmk">%s</span><h2 class="mmt">%s</h2></div>'
        '<p class="mmsub"><b id="mmWeek">W%d</b> &middot; %s &middot; %s</p>'
        '<div class="rplmm" id="mmMount">%s</div>'
        '<p class="mmn">%s</p>'
        '<p class="mmn">%s</p>'
        '%s'
        '<script type="application/json" id="mmData">%s</script>'
        '<script>window.RPL_MUSCLE_GEO=%s;</script>'
        '<script>%s</script>'
        '%s</section>'
        % (sl.T("mmap.kicker"), sl.T("mmap.title", len(dm.LEAF_ORDER)),
           cur_week, sl.T("mmap.volume"), sl.T("mmap.scope"), noscript,
           sl.T("mmap.note"), zero_note, ref_fold,
           json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
           json.dumps(geo_embed, ensure_ascii=False, separators=(",", ":")),
           MUSCLE_JS, MMAP_ADAPTER))
    return body


def cardio_panel(plan):
    """Moderate-equivalent cardio minutes per week, always marked as an estimate."""
    c = dm.cardio_weeks(plan)
    if not c["runs"]:
        return ""
    n = plan.total_weeks
    hi = float((c["guideline"] or {}).get("high") or 300)
    scale = max(hi, float(c["high"])) or 1.0
    bars, labels = [], []
    for w in range(1, n + 1):
        eq = c["weeks"][w]["eq"]
        bars.append('<i class="%s" style="height:%.1f%%" title="W%d &middot; %s min"></i>'
                    % ("zero" if eq <= 0 else "", max(0.0, 100.0 * eq / scale), w,
                       dm.fmt_num(eq)))
        labels.append("<span>%s</span>" % (("W%d" % w) if w in (1, 4, 7, 10, n) else ""))
    lo = float((c["guideline"] or {}).get("low") or 0)
    return ('<section class="car" id="cardio">'
            '<div class="car-h"><span class="car-k">%s</span>'
            '<h2 class="car-t">%s<em>%s</em></h2></div>'
            '<div class="car-num"><b>%s&ndash;%s</b><i>%s</i></div>'
            '<div class="carband"><div class="carzone" style="bottom:%.1f%%;height:%.1f%%"></div>'
            '<div class="carbars" style="--n:%d">%s</div></div>'
            '<div class="carlbl" style="--n:%d">%s</div>'
            '<div class="car-leg"><i></i>%s</div>'
            '<p class="car-note">%s</p><p class="car-note">%s</p></section>'
            % (sl.T("cardio.kicker"), sl.T("cardio.title"), sl.T("cardio.est"),
               dm.fmt_num(c["low"]), dm.fmt_num(c["high"]), sl.T("cardio.unit"),
               100.0 * lo / scale, 100.0 * (hi - lo) / scale, n, "".join(bars),
               n, "".join(labels), sl.T("cardio.band"),
               sl.T("cardio.note"), sl.T("cardio.ball")))


def build_run_page(plan, d, runs):
    """GPP-1 ENGINE page: conditioning, four types, run is the prescription."""
    week = int(runs[0].get("week") or 0)
    title, title_zh = sl.S("title.run", dm.iso_date(d))
    body = [masthead("%s · %s" % (full_date(d), sl.T("run.engine")), "../plan/", "nav.plan")]
    body.append('<div class="run-hero">')
    body.append('<div class="eyebrow">%s</div>' % sl.T("run.eyebrow", "%d" % week))
    body.append('<h1>%s</h1>' % sl.T("run.title"))
    body.append('<div class="tags">%s</div>' % pill("run.optional"))
    body.append('</div>')
    body.append('<div class="run-rest"><span>%s</span>%s</div>'
                % (sl.T("run.no_lift"), sl.T("run.no_lift_sub")))
    run_panel = []
    for row in runs:
        zone = str(row.get("zone") or "").strip() or "RUN"
        dur = dm.fmt_num(row.get("duration_min"))
        try:
            hr = "%d&ndash;%d %s" % (int(row.get("hr_low")), int(row.get("hr_high")),
                                   sl.T("unit.bpm"))
        except (TypeError, ValueError):
            hr = "&mdash;"
        rpe = run_rpe(row.get("note")).replace("-", "&ndash;")
        cue = run_cue(row.get("note"))
        run_panel.append('<article class="run-card">')
        run_panel.append('<div class="run-top"><b>%s</b><span>%s</span></div>'
                         % (esc(zone), wd_text(row.get("weekday"))))
        run_panel.append('<div class="run-big"><b>%s</b><i>%s</i></div>'
                         % (esc(dur), sl.T("unit.min")))
        run_panel.append('<div class="run-metrics">'
                         '<div><span>%s</span><b>%s</b></div>'
                         '<div><span>%s</span><b>%s</b></div>'
                         '<div><span>RPE</span><b>%s</b></div></div>'
                         % (sl.T("run.heart"), hr, sl.T("run.zone"),
                            esc(zone), rpe or "&mdash;"))
        if cue:
            run_panel.append('<p class="run-cue">%s</p>' % cue)
        run_panel.append('</article>')
    if len(runs) > 1:
        run_panel.append('<p class="run-note">%s</p>' % sl.T("run.many", len(runs)))
    body.append(gpp1_tabs("g1-d%s" % dm.iso_date(d).replace("-", ""), "".join(run_panel)))
    body.append('<p class="run-note">%s</p>' % sl.T("run.skip"))
    body.append(gpp_frame_reset_fold(plan, week))
    body.append('<footer class="sec"><h2>%s</h2><span><a href="../plan/">%s</a></span></footer>'
                % (sl.T("run.plan"), sl.T("run.all_days")))
    body.append(FRIENDS)
    return shell(title, "\n".join(body), title_zh=title_zh)


_DAY_CHIP = {"squat": ("SQ", "SQUAT"), "bench": ("BN", "BENCH"),
             "deadlift": ("DL", "DEADLIFT")}


def day_loads(plan, sess):
    """Every competition-lift top set for the calendar row.

    ``main_loads`` returns all main lifts in S/B/D order, and the row must show
    all of them: a three-lift day that stops at two silently loses the third
    lift (W13 Day B/C shipped without the deadlift). Days without a
    competition lift (Day D) fall back to the first two loaded variations so
    the row still shows absolute kg instead of an empty chip line.
    """
    out = []
    for l in dm.main_loads(plan, sess):
        ab, full = _DAY_CHIP.get(l["lift"], (l["label"][:2].upper(), l["label"].upper()))
        zh = lift_zh(l["label"])
        out.append({"key": l["lift"], "ab": ab, "full": full,
                    "ab_zh": zh, "full_zh": zh, "load": l["load"],
                    "role": "main", "pct": float(l["pct"] or 0)})
    if not out:
        for e in sess.get("exercises") or []:
            mv, load = e.get("mv"), e.get("load")
            if not load or dm.movement_role(mv, e) != "variation":
                continue
            ab, full = {
                "Power Clean": ("PC", "CLEAN"),
                "Wide-grip Bench": ("WB", "WIDE BENCH"),
                "Low-bar Squat": ("LB", "LOW-BAR SQ"),
            }.get(mv, (mv.split()[0][:2].upper(), mv.upper()))
            zh = mv_zh(mv)
            out.append({"key": mv.lower(), "ab": ab, "full": full,
                        "ab_zh": zh, "full_zh": zh, "load": float(load),
                        "role": "var", "pct": 0.0})
            if len(out) == 2:
                break
    return out


_MAIN_IN_TITLE = re.compile(r"\b(SQUAT|BENCH|DEADLIFT)\s+MAIN\b")


def day_lead(sess, loads):
    """The chip the bold weight belongs to: the lift the session title calls MAIN.

    Percentages alone are not enough: on W13 Day B all three lifts sit at 70%,
    and picking the numeric maximum would bold a volume lift while the row's
    own subtitle says BENCH MAIN. Falls back to the highest %1RM when the title
    names no main lift (Day D, variation wording).
    """
    m = _MAIN_IN_TITLE.search(str(sess.get("title") or "").upper())
    if m:
        key = m.group(1).lower()
        for l in loads:
            if l["role"] == "main" and l["key"] == key:
                return l
    mains = [l for l in loads if l["role"] == "main"]
    return max(mains, key=lambda l: l["pct"]) if mains else None


def day_muscles(dv, limit=3, floor=0.5):
    """Top muscle leaves for one session, from the fractional-set volume.

    ``leavesWeighted`` comes from ``tools/muscle_map.json`` (the same 260-movement
    matrix the capacity board and the body map read), so a row cannot disagree
    with the week view.
    """
    lw = (dv or {}).get("leavesWeighted") or {}
    rows = sorted(((k, float(v or 0.0)) for k, v in lw.items()), key=lambda x: -x[1])
    rows = [r for r in rows if r[1] >= floor][:limit]
    return " &middot; ".join(sl.T("leaf.%s" % k) for k, _v in rows)


def _day_desc(did, title, is_test=False):
    """Session descriptor with the competition-lift clause in the lead weight.

    The calendar row shows the number first; this line carries the words, so
    ``SQUAT MAIN`` has to stay legible against the rest of the tag list.
    ``(W13 TEST)`` is part of the Day C title for every week; it is only true
    on the test week, so elsewhere the marker is dropped. Chinese comes from
    the day-title table, never from a per-page translation of the English split.
    """
    def build(text, main_word):
        out = []
        for p in [x.strip() for x in str(text or "").split("·") if x.strip()]:
            if not is_test:
                p = re.sub(r"\s*\(W\d+\s+TEST\)", "", p).strip()
            up = p.upper()
            bold = up.endswith(" MAIN") or up.endswith(" TEST") or p.endswith(main_word)
            out.append("<b>%s</b>" % esc(p) if bold else esc(p))
        return "\u00a0&middot; ".join(out)

    en = build(title, "\x00")
    zh = sl.Z("day.%s.title" % did)
    if zh and is_test:
        zh += sl.Z("day.test_suffix")
    return sl.DH(en, build(zh, "主项") if zh else "")


def week_split(wv, vols, w):
    """Per-lift split of the week's working sets.

    Reads the same ``volumes()`` slot the capacity board renders, so the week
    card and the analysis board cannot drift: each row is a projection of
    ``lifts[code][main|var]`` plus the accessory bucket.
    """
    lf = wv.get("lifts") or {}

    def n(code, key):
        return int(round(((lf.get(code) or {}).get(key) or 0)))

    out = ['<div class="wk-split">']
    acc = int(round(wv["accessory"]))
    tot_sets = int(round(wv["sets"]))
    # One ruler for S/B/D and the accessory bucket, and never shorter than the
    # widest MRV, so a MEV/MRV tick always lands inside the track.
    base = max([n(c, "main") + n(c, "var") for c, _ in CAP_LIFTS]
               + [acc] + [int(r["mrv"]) for r in dm.SBD_RANGES.values()
                          if str(r.get("mrv", "")).isdigit()] + [1])
    for code, label in CAP_LIFTS:
        m, v = n(code, "main"), n(code, "var")
        n_all = m + v
        rng = dm.SBD_RANGES.get(code) or {}
        mev, mrv = rng.get("mev"), rng.get("mrv")
        ticks = ""
        if isinstance(mev, int) and isinstance(mrv, int):
            ticks = ('<s class="mev" style="left:%.1f%%"></s>'
                     '<s class="mrv" style="left:%.1f%%"></s>'
                     % (100.0 * mev / base, 100.0 * mrv / base))
        ref = ('<em>%s</em>' % sl.T("cap.sbd_ref", mev, mrv)
               if isinstance(mev, int) and isinstance(mrv, int) else '<em></em>')
        out.append('<span class="ws%s"><i>%s</i>%s<u>%d</u>'
                   '<b class="ws-b">'
                   '<i class="m" style="width:%.1f%%"></i>'
                   '<i class="v" style="width:%.1f%%"></i>%s'
                   '</b></span>'
                   % (" z" if n_all == 0 else "", label, ref, n_all,
                      100.0 * m / base, 100.0 * v / base, ticks))
    out.append('<span class="ws acc%s"><i>%s</i><em>%s</em><u>%d</u>'
               '<b class="ws-b"><i class="a" style="width:%.1f%%"></i></b></span>'
               % (" z" if acc == 0 else "", sl.T("split.acc"),
                  sl.T("split.acc_ref"), acc, 100.0 * acc / base))
    out.append('<span class="ws tot"><i>%s</i><em>%s</em>'
               '<u>%d</u></span>' % (sl.T("split.total"), sl.T("split.total_sub"),
                                     tot_sets))
    out.append('</div>')
    return "".join(out)


def build_index(plan, share=False, tier_probe=True, view_switch=True):
    """Plan calendar page.

    share=False (default) keeps the App snapshot byte-identical: no share
    entry, no ../sharecard.js external script (site_snapshot.py calls this
    without arguments; the snapshot must stay self-contained).

    tier_probe=False drops the whole hub entitlement probe (slot + TIER_JS).
    The App snapshot runs inside a same-origin srcdoc iframe, so its scripts
    do execute; a whoami fetch there would be a second network exit in the
    single-file product (gate D16 A1) and could never resolve a tier anyway.
    The App shows its own PRO badge from the native licence, not from the hub.

    view_switch=False drops the Mini/Max control and the Mini tree entirely,
    so the public plan page always renders the full Max document.
    """
    vols = dm.volumes(plan)
    ints = dm.week_intensity(plan)
    span = (datetime.date.today() - plan.start).days
    iweek = 1 if span < 0 else min(plan.total_weeks, span // 7 + 1)
    test_week = (plan.last_train[0] - plan.start).days // 7 + 1
    body = []
    body.append(masthead("", None, "nav.home",
                         share=plan_share_button(compact=True) if share else "",
                         view=view_switch))
    if view_switch:
        body.append('<div class="mini-only">%s</div>' % mini_plan_sheet(plan, iweek))
    body.append('<div class="max-only">')
    if tier_probe:
        body.append(TIER_NOTE_HTML)
    body.append('<div class="hero rise" style="--d:0ms">')
    body.append('<div class="eyebrow">%s</div>'
                % sl.T("plan.eyebrow", plan.total_weeks, plan.n_training))
    title = '<h1>%s</h1>' % sl.T("plan.title")
    if tier_probe:
        title += '<span class="tier-slot" data-tier-slot></span>'
    body.append('<div class="hero-title">%s</div>' % title)
    body.append('<p class="hero-sub">%s &rarr; %s</p>'
                % (md(plan.start), md(plan.last_train[0])))
    body.append('</div>')
    body.append('<div class="stats rise" style="--d:50ms">')
    body.append('  <div class="stat"><span>%s</span><b>%s</b></div>'
                % (sl.T("plan.start"), dm.iso_date(plan.start)))
    body.append('  <div class="stat"><span>%s</span><b>%s</b></div>'
                % (sl.T("plan.test_day"), dm.iso_date(plan.last_train[0])))
    body.append('  <div class="stat"><span>%s</span><b>%.1f %s</b><i>%s</i></div>'
                % (sl.T("plan.volume"), vols["total"] / 1000.0, sl.T("unit.t"),
                   sl.T("plan.aux", vols["accSets"])))
    body.append('</div>')
    body.append('<div class="wkbar rise" style="--d:100ms">'
                '<button class="wkbtn" id="wkPrev" type="button" %s>&lsaquo;</button>'
                '<div class="wkinfo"><b id="wklabel">%s</b><span id="wkblock">%s</span></div>'
                '<button class="wkbtn" id="wkNext" type="button" %s>&rsaquo;</button>'
                '</div>' % (sl.A("aria-label", "plan.prev_week"),
                            sl.T("plan.week_bar", "%d" % iweek),
                            sl.D(plan.block_en[iweek], sl.block_zh(plan.block_en[iweek])),
                            sl.A("aria-label", "plan.next_week")))
    segs = []
    for w in range(1, plan.total_weeks + 1):
        cls = "seg"
        if w < iweek:
            cls += " done"
        if w == iweek:
            cls += " now"
        if plan.is_deload(w):
            cls += " dl"
        if w == test_week:
            cls += " ts"
        segs.append('<i class="%s" data-wk="%d" data-dl="%d" data-ts="%d"></i>'
                    % (cls, w, 1 if plan.is_deload(w) else 0, 1 if w == test_week else 0))
    body.append('<div class="wkprog rise" style="--d:130ms" id="wkprog" role="progressbar" '
                'aria-valuemin="1" aria-valuemax="%d" aria-valuenow="%d">'
                '<div class="wp-track" style="--wn:%d">%s</div>'
                '<div class="wp-cap"><span id="wkDone">%s <b>/ %d</b></span>'
                '<span id="wkLeft">%s</span></div>'
                '<div class="wp-legend">'
                '<span><i class="lg-done"></i>%s</span>'
                '<span><i class="lg-dl"></i>%s</span>'
                '<span><i class="lg-ts"></i>%s</span>'
                '<span><i class="lg-now"></i>%s</span></div></div>'
                % (plan.total_weeks, iweek, plan.total_weeks, "".join(segs),
                   sl.T("plan.week_bar", "%d" % iweek), plan.total_weeks,
                   sl.T("plan.weeks_left_one" if plan.total_weeks - iweek == 1
                        else "plan.weeks_left", plan.total_weeks - iweek),
                   sl.T("plan.legend.training"), sl.T("plan.legend.deload"),
                   sl.T("plan.legend.test"), sl.T("plan.legend.current")))
    body.append('<div class="wkrail rise" style="--d:160ms" id="wkrail">')
    for w in range(1, plan.total_weeks + 1):
        extra = " dl" if plan.is_deload(w) else (" ts" if w == test_week else "")
        aria_key = ("plan.week_aria_deload" if plan.is_deload(w)
                    else ("plan.week_aria_test" if w == test_week else "plan.week_aria"))
        body.append('<button class="wkdot%s%s" type="button" data-jump="%d" %s>%d</button>'
                    % (" on" if w == iweek else "", extra, w,
                       sl.A2("aria-label", aria_key, w), w))
    body.append('</div>')
    body.append('<div class="peek" id="peek" role="status" aria-live="polite" hidden></div>')
    body.append('<div class="wkview" id="wkview" data-weeks="%d" data-start="%s">'
                % (plan.total_weeks, dm.iso_date(plan.start)))

    for w in range(1, plan.total_weeks + 1):
        btxt = plan.block_en[w]
        bzh = sl.block_zh(btxt)
        kind = "deload" if plan.is_deload(w) else ("test" if w == test_week else "")
        cls = "wk now" if w == iweek else "wk"
        body.append('<section class="%s" data-week="%d" data-block="%s" data-block-zh="%s" data-kind="%s">'
                    % (cls, w, esc(btxt), esc(bzh), kind))
        tags = []
        if w == 1:
            tags.append('<span class="wk-st">%s</span>' % sl.T("pill.calibration"))
        if plan.is_deload(w):
            tags.append('<span class="wk-st">%s</span>' % sl.T("pill.deload"))
        if w == test_week:
            tags.append('<span class="wk-st ts">%s</span>' % sl.T("pill.test"))
        n_sess = sum(1 for (w2, _d) in plan.sessions if w2 == w)
        wv = vols["weeks"].get(w, {"kg": 0, "sets": 0, "main": 0, "variation": 0,
                                   "sbdVar": 0, "nonSbdVar": 0, "accessory": 0})
        iv = ints.get(w) or {}
        have = [v for v in iv.values() if v is not None]
        top = max(have) if have else None
        if top is None:
            int_line = ('<span>%s</span><b class="na">&mdash;</b>'
                        '<em class="inl">%s</em>'
                        % (sl.T("plan.top_pct"), sl.T("plan.no_pct")))
        else:
            detail = " &middot; ".join("%s %s" % (c, dm.pct_fmt(iv.get(c)))
                                       for c in ("S", "B", "D"))
            int_line = ('<span>%s</span><b>%s</b><em>%s</em>'
                        % (sl.T("plan.top_pct"), dm.pct_fmt(top), detail))
        body.append('<div class="wk-head"><div class="wk-n">%d<small>%s</small></div>'
                    '<div class="wk-mid"><div class="wk-phase">%s</div>'
                    '<div class="wk-status">%s</div></div>'
                    '<div class="wk-vol"><b data-count="%.1f" data-dec="1">%.1f</b><span>%s</span><i>%s</i></div></div>'
                    % (w, sl.T("plan.week_small"), sl.D(btxt, bzh), "".join(tags),
                       wv["kg"] / 1000.0, wv["kg"] / 1000.0, sl.T("unit.t"),
                       sl.T("plan.sessions", n_sess)))
        body.append('<div class="wk-int">%s</div>' % int_line)
        body.append('<div class="rows">')
        for offset in range(7):
            d = plan.start + datetime.timedelta(days=(w - 1) * 7 + offset)
            did = None
            for k, v in plan.days.items():
                if v["weekdayOffset"] == offset:
                    did = k
            if did and (w, did) in plan.sessions:
                sess = plan.sessions[(w, did)]
                loads = day_loads(plan, sess)
                top = day_lead(sess, loads)
                chips = []
                for i, l in enumerate(loads):
                    if l is top:
                        cls = "main"
                    elif top is None and i == 0:
                        cls = "lead"
                    else:
                        cls = "sub"
                    chips.append('<span class="ld %s"><i>%s</i><b>%s</b></span>'
                                 % (cls, sl.D(l["ab"], l.get("ab_zh") or ""),
                                    dm.fmt_num(l["load"])))
                ldl = ""
                if chips:
                    ldl = ('<span class="ldl">%s%s</span>'
                           % ('<em class="ldk">%s</em>' % sl.T("plan.top") if top is not None else "",
                              "".join(chips)))
                dv = vols["days"].get((w, did)) or {"sets": 0, "kg": 0}
                mg = day_muscles(dv)
                mline = ('<span class="mgs"%s>%s</span>'
                         % (sl.A("aria-label", "plan.muscles"), mg)) if mg else ""
                peek = "DAY %s · %d SETS · %s kg" % (did, int(round(dv["sets"])), fmt_int(dv["kg"]))
                peek_zh = "%s 日 · %d 组 · %s 公斤" % (did, int(round(dv["sets"])), fmt_int(dv["kg"]))
                pl = " · ".join("%s %s kg" % (l["full"], dm.fmt_num(l["load"]))
                                for l in loads)
                pl_zh = " · ".join("%s %s 公斤" % (l.get("full_zh") or l["full"],
                                                dm.fmt_num(l["load"]))
                                   for l in loads)
                if pl:
                    peek += "\n" + pl
                if pl_zh:
                    peek_zh += "\n" + pl_zh
                body.append('<a class="row" data-date="%s" data-ex="%d" data-peek="%s" data-peek-zh="%s" href="../%s/">'
                            '<span class="dt"><b>%s</b><i>%s</i></span>'
                            '<span class="day">%s</span>'
                            '<span class="ttl">%s<span class="dname%s">%s</span>%s</span>'
                            '<span class="chev">&rsaquo;</span></a>'
                            % (dm.iso_date(d), len(sess.get("exercises") or []),
                               html.escape(peek, quote=True), html.escape(peek_zh, quote=True),
                               dm.ymd6(d),
                               md(d), wd(d),
                               esc(did), ldl, "" if chips else " solo",
                               _day_desc(did, plan.days[did]["titleEn"], w == test_week), mline))
            else:
                runs = [x for x in (plan.run_plan or [])
                        if str(x.get("date") or "") == dm.iso_date(d)]
                if runs:
                    zone = str(runs[0].get("zone") or "RUN").strip().upper()
                    mins = 0
                    for x in runs:
                        try:
                            mins += int(float(x.get("duration_min") or 0))
                        except (TypeError, ValueError):
                            pass
                    line = "%s · %s" % (sl.T("gpp.act.run"), zone_html(zone))
                    if mins:
                        line += " · %d %s" % (mins, sl.T("unit.min"))
                    body.append('<a class="row rest has-run" data-date="%s" href="../%s/">'
                                '<span class="dt"><b>%s</b><i>%s</i></span>'
                                '<span class="ttl">%s</span>'
                                '<span class="chev">&rsaquo;</span>'
                                '<span class="rhint">%s</span></a>'
                                % (dm.iso_date(d), dm.ymd6(d),
                                   md(d), wd(d), sl.T("plan.rest"),
                                   "%s &middot; %s" % (sl.T("plan.optional"), line)))
                    continue
                rh = dm.rest_hint(d)
                body.append('<div class="row rest" data-date="%s">'
                            '<span class="dt"><b>%s</b><i>%s</i></span>'
                            '<span class="ttl">%s</span>'
                            '<span class="rhint">%s</span></div>'
                            % (dm.iso_date(d),
                               md(d), wd(d), sl.T("plan.rest"),
                               sl.D(rh.get("en") or "", rh.get("zh") or "")))
        body.append('</div>')
        body.append(week_split(wv, vols, w))
        body.append(week_extras(plan, w))
        body.append('</section>')
    body.append('</div>')
    body.append('<div class="sec"><h2>%s</h2><span>%s</span></div>'
                % (sl.T("plan.capacity"), sl.T("plan.weeks", plan.total_weeks)))
    body.append(capacity_panel(plan, vols, iweek))
    body.append(cardio_panel(plan))
    body.append(muscle_map_panel(plan, vols, iweek))
    body.append(FRIENDS)
    body.append('</div>')
    body.append('<footer class="foot">'
                '<a href="../today/">%s</a>'
                '<a href="../">%s</a></footer>'
                % (sl.T("footer.today"), sl.T("nav.home")))
    body.append('<div id="capSpacer" style="height:0" aria-hidden="true"></div>')
    body.append(CAP_JS)
    body.append(PLAN_JS)
    if tier_probe:
        body.append(TIER_JS)
    body.append(COUNT_JS)
    if share:
        share_data = json.dumps(plan_share_json(plan, vols),
                                ensure_ascii=False,
                                separators=(",", ":")).replace("</", "<\\/")
        body.append('<script src="../sharecard.js"></script>')
        body.append('<script>window.__PLAN_SHARE=%s;</script>' % share_data)
        body.append(PLAN_SHARE_JS)
    title, title_zh = sl.S("title.plan")
    return shell(title, "\n".join(body), extra_css=PLAN_CSS, title_zh=title_zh,
                 view_switch=view_switch)


def build_today_shell(plan):
    mapping = {dm.ymd6(d): dm.ymd6(d) for d, _, _ in plan.training_dates}
    for row in (plan.run_plan or []):
        try:
            rd = datetime.date.fromisoformat(str(row.get("date") or ""))
        except ValueError:
            continue
        if rd not in plan.date_set:
            mapping[dm.ymd6(rd)] = dm.ymd6(rd)
    body = [masthead(sl.T("today.eyebrow"), "/plan/", "nav.plan")]
    body.append('<div class="hero">')
    body.append('<div class="eyebrow">%s</div>' % sl.T("today.eyebrow"))
    body.append('<h1>%s</h1>' % sl.T("today.h1"))
    body.append('<p class="hero-sub">%s</p>' % sl.T("today.loading"))
    body.append('</div>')
    body.append('<div class="skel" aria-hidden="true"><i></i><i></i><i></i></div>')
    body.append('<noscript><p class="hero-sub"><a href="../plan/">%s</a></p></noscript>'
                % sl.T("today.nojs"))
    body.append(TODAY_JS % _js_obj(mapping))
    title, title_zh = sl.S("title.today")
    return shell(title, "\n".join(body), title_zh=title_zh)


def _js_obj(mapping):
    import json
    return json.dumps(mapping, separators=(",", ":"))


GATE_CSS = """
.gate{max-width:560px;margin:24px auto 0;padding:0 0 32px}
.gate-k{margin:0 0 6px;font-size:10px;font-weight:800;letter-spacing:.12em;
  text-transform:uppercase;color:var(--tx3)}
.gate h1{margin:0 0 8px;font-size:26px;line-height:1.15;letter-spacing:-.01em}
.gate p{margin:0 0 18px;color:var(--tx2);font-size:14px;line-height:1.55;text-wrap:pretty}
.gate-list{display:flex;flex-direction:column;gap:12px;margin:0;padding:0;list-style:none}
.gate-cta{display:flex;align-items:center;gap:12px;min-height:56px;padding:12px 14px;
  border:1px solid var(--line2);border-radius:2px;background:transparent;color:var(--ink);
  text-decoration:none}
.gate-cta:hover{border-color:var(--line);background:var(--ov1)}
.gate-cta:active{background:var(--ov2)}
.gate-cta>span{display:block;min-width:0}
.gate-cta b{display:block;font-size:14px;font-weight:800;line-height:1.25;color:var(--ink)}
.gate-cta b+span{display:block;margin-top:2px;font-size:12px;color:var(--tx3);line-height:1.35}
.gate-cta i{margin-left:auto;font-style:normal;color:var(--tx3);font-size:16px}
.gate-cta[hidden]{display:none}
.gate-cta.gate-primary{border-color:var(--accLine);background:var(--accSoft)}
.gate-cta.gate-primary b{color:var(--acc)}
.gate-cta.gate-primary i{color:var(--acc)}
.gate-state{margin:18px 0 0;font-size:12px;color:var(--tx3)}
.gate-state[hidden]{display:none}
.gate-tier{margin:14px 0 0;font-size:11px;letter-spacing:.06em;text-transform:uppercase;
  color:var(--tx3)}
"""

GATE_JS = """
(function(){
  var G=document.getElementById('gate');
  if(!G)return;
  var LOAD=document.getElementById('gateLoad'),ERR=document.getElementById('gateErr'),
      Q=document.getElementById('gQ'),U=document.getElementById('gU'),
      TIER=document.getElementById('gateTier'),tier='';
  function zh(){return document.documentElement.getAttribute('lang')==='zh-CN';}
  function paintTier(){
    if(!TIER)return;
    var t=(zh()?TIER.getAttribute('data-zh-text'):TIER.getAttribute('data-en-text'))||'';
    TIER.textContent=t.replace('{0}',tier?tier.toUpperCase():'STANDARD');
  }
  function get(u){
    return fetch(u,{credentials:'same-origin',headers:{'Accept':'application/json'}})
      .then(function(r){return r.json().catch(function(){return {}})
        .then(function(b){return {ok:r.ok,status:r.status,b:b}})});
  }
  function fail(){
    LOAD.hidden=true;ERR.hidden=false;
    var b=document.getElementById('gateRetry');
    if(b)b.addEventListener('click',function(){b.disabled=true;boot()},{once:true});
  }
  function boot(){
    ERR.hidden=true;LOAD.hidden=false;
    get('/hub/v1/auth/whoami').then(function(w){
      var u=w.ok&&w.b&&w.b.user;
      if(!u){location.replace('/account/?next=/plan/');return null;}
      var name=String(u.username||u.name||u.email||'');
      return get('/hub/v1/plans').then(function(p){
        var list=(p.ok&&p.b&&(p.b.plans||p.b.items))||[];
        if(list.length){location.replace('/u/'+encodeURIComponent(name)+'/plan/');return;}
        tier=String(u.tier||'').toLowerCase();
        LOAD.hidden=true;
        if(tier==='pro'||tier==='ultra'){Q.hidden=false;}
        else{U.hidden=false;}
        TIER.hidden=false;paintTier();
      });
    }).catch(fail);
  }
  document.addEventListener('rpl:lang',paintTier);
  boot();
})();
"""


def build_plan_gate():
    """Signed-in /plan/ gate: empty state when the account owns no plan.

    The page carries no session rows at all. The static file that used to be
    /plan/ was the built-in sample calendar, so a brand-new account saw a
    finished nine-week plan as if it were its own. Entitlement and ownership
    are read at runtime from the hub; the sample calendar stays on the public
    home page only, where it is labelled SAMPLE.
    """
    body = [masthead("", None, "nav.home")]
    body.append('<main class="gate" id="gate">')
    body.append('<p class="gate-k">%s</p>' % sl.T("gate.kicker"))
    body.append('<h1>%s</h1>' % sl.T("gate.h1"))
    body.append('<p>%s</p>' % sl.T("gate.body"))
    body.append('<ul class="gate-list">')
    body.append('<li id="gQ" hidden><a class="gate-cta gate-primary" href="/pro/">'
                '<span><b>%s</b><span>%s</span></span><i aria-hidden="true">&rarr;</i></a></li>'
                % (sl.T("gate.q"), sl.T("gate.q_sub")))
    body.append('<li id="gU" hidden><a class="gate-cta gate-primary" href="/#license">'
                '<span><b>%s</b><span>%s</span></span><i aria-hidden="true">&rarr;</i></a></li>'
                % (sl.T("gate.upgrade"), sl.T("gate.upgrade_sub")))
    body.append('<li><a class="gate-cta" href="/#download">'
                '<span><b>%s</b><span>%s</span></span><i aria-hidden="true">&rarr;</i></a></li>'
                % (sl.T("gate.import"), sl.T("gate.import_sub")))
    body.append('<li><a class="gate-cta" href="/#download">'
                '<span><b>%s</b><span>%s</span></span><i aria-hidden="true">&rarr;</i></a></li>'
                % (sl.T("gate.download"), sl.T("gate.download_sub")))
    body.append('</ul>')
    body.append('<p class="gate-state" id="gateLoad">%s</p>' % sl.T("gate.loading"))
    body.append('<p class="gate-state" id="gateErr" hidden>%s '
                '<button type="button" class="mbtn" id="gateRetry">%s</button></p>'
                % (sl.T("gate.error"), sl.T("gate.retry")))
    tier_en, tier_zh = sl.S("gate.tier")
    body.append('<p class="gate-tier" id="gateTier" data-en-text="%s" data-zh-text="%s" hidden>'
                '</p>' % (esc(tier_en), esc(tier_zh)))
    body.append('<noscript><p class="gate-state">%s</p></noscript>' % sl.T("gate.nojs"))
    body.append('</main>')
    body.append('<footer class="foot"><a href="../">%s &rarr;</a></footer>'
                % sl.T("nav.home"))
    body.append('<script>%s</script>' % GATE_JS)
    title, title_zh = sl.S("gate.title")
    return shell(title, "\n".join(body), extra_css=GATE_CSS, title_zh=title_zh)
