"""Prescription parsing and load rounding, ported from legacy day_model.py.

One row -> set segments (TOP / BACK-OFF / WORK / BW / TECH). Sets counted by the
statistics engine are the sum of segment sets, exactly as the legacy board did.
"""
import re

_CAL_PREFIX = re.compile(r"^(?:CAL|CALIBRATION)\b[\s.:·-]*", re.I)
_KG_AT = re.compile(r"@\s*([\d.]+)\s*kg", re.I)
_TOP_RX = re.compile(
    r"^(\d+)\s*[×x]\s*(\d+)\s*顶组\s*\+\s*(\d+)\s*[×x]\s*(\d+)\s*减\s*([\d.]+)\s*%\s*补组\s*(\+)?$")
_TOP_RX_EN = re.compile(
    r"^(\d+)\s*[×x]\s*(\d+)\s*top\s*\+\s*(\d+)\s*[×x]\s*(\d+)\s*(?:at|@)?\s*[-−–]?\s*([\d.]+)\s*%"
    r"(?:\s*(?:\(back-off\)|back-off))?\s*(\+)?$", re.I)
_BASE_RX = re.compile(r"^(\d+)\s*[×x]\s*(\d+)")
_SIDE_RX = re.compile(r"(\d+)\s*(?:s|秒)\s*/\s*(?:side|侧)", re.I)
_PCT_RX = re.compile(r"@\s*([\d.]+)\s*%")
_KG_RX = re.compile(r"约\s*([\d.]+)\s*kg")
_APPROX = re.compile(r"约\s*")

RX_EN = {}


def mround(x, step=0.5):
    """Round to the nearest multiple of step, halves up (legacy contract)."""
    if x is None:
        return None
    return round(x / step + 1e-9) * step


def rx_english(text):
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


def parse_segments(e):
    """e: {rxRaw, load, pct, sets, reps, notes, bwAnchor, bucket} -> list of segments."""
    raw = _CAL_PREFIX.sub("", str(e.get("rxRaw") or e.get("rx") or "").strip())
    load = e.get("load") or None
    pct = e.get("pct")
    pct_disp = (None if e.get("bucket") == "nonSbdVar" else
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
    if pm and pct_disp is None and e.get("bucket") != "nonSbdVar":
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


def row_load(seg, role):
    """Prescribed load as displayed: main on 0.5 kg, variation on 2.5 kg, accessory none."""
    load = seg.get("load")
    if not load:
        return None
    if role == "main":
        return mround(load, 0.5)
    if role == "variation":
        return mround(load, 2.5)
    return None