#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare Roast Raw's generated plan against the legacy /plan/ capacity JSON."""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "Build", "app", "js", "data.js")
CAP = os.path.join(ROOT, "Data", "capData.json")
MM = os.path.join(ROOT, "Data", "mmData.json")


def load_data():
    js = open(DATA, encoding="utf-8").read()
    return json.loads(js[js.index("=") + 1:].rsplit(";", 1)[0])


def week1(d):
    raw = d["plan"]["1"]["A"] + d["plan"]["1"]["B"] + d["plan"]["1"]["C"] + d["plan"]["1"]["D"]
    agg = {}
    for it in raw:
        k = it["exId"]
        if k not in agg:
            agg[k] = dict(it)
            agg[k]["sets"] = int(it.get("sets") or 0)
        else:
            agg[k]["sets"] += int(it.get("sets") or 0)
    return list(agg.values())


def main():
    d = load_data()
    items = week1(d)
    ex = {e["id"]: e for e in d["exercises"]}
    muscles = [m["id"] for m in d["muscles"]]
    mi = {m: i for i, m in enumerate(muscles)}

    total = sum(i["sets"] for i in items)
    lifts = {"sq": [0, 0], "bp": [0, 0], "dl": [0, 0]}
    roles = {"main": 0, "variant": 0, "accessory": 0}
    w = [0.0] * 16
    direct = [0.0] * 16
    for it in items:
        e = ex[it["exId"]]
        sets = it["sets"]
        cat = e["cat"]
        role = "main" if cat.endswith(".Main") else ("variant" if ".Vari" in cat else "accessory")
        roles[role] += sets
        fam = e.get("fam")
        if fam in lifts:
            lifts[fam][0 if role == "main" else 1 if role == "variant" else 0] += sets
        for n, c in enumerate(e["c"]):
            w[n] += sets * c
        if e.get("pm") in mi:
            direct[mi[e["pm"]]] += sets

    cap = json.load(open(CAP, encoding="utf-8-sig"))
    mm = json.load(open(MM, encoding="utf-8-sig"))
    print("total sets: ours=%d legacy=%d" % (total, cap["total"][0]))
    for k, key in (("S", "sq"), ("B", "bp"), ("D", "dl")):
        leg = next(x for x in cap["items"] if x["k"] == k)
        print("%s main/var: ours=%d/%d legacy=%d/%d range %d-%d mev/mrv %d/%d" % (
            k, lifts[key][0], lifts[key][1], leg["m"][0], leg["v"][0], leg["lo"], leg["hi"], leg["mev"], leg["mrv"]))
    print("roles: ours=%s legacy=%s" % (roles, {r["k"]: r["m"][0] for r in cap["roles"]}))
    lw = mm["weeks"]["1"]["w"]
    ld = mm["weeks"]["1"]["d"]
    print("%-12s %7s %7s" % ("muscle", "weighted", "direct"))
    for i, m in enumerate(muscles):
        print("%-12s %6.1f/%6.1f %6.1f/%6.1f" % (m, w[i], lw[i], direct[i], ld[i]))


if __name__ == "__main__":
    main()
