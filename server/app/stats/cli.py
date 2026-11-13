#!/usr/bin/env python3
"""CLI for the statistics engine: prints the analysis JSON for a plan document."""
import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

from server.app.stats import engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=os.path.join(ROOT, "data", "plan.json"))
    ap.add_argument("--logs", default=None)
    ap.add_argument("--mode", default="plan", choices=["plan", "log"])
    args = ap.parse_args()
    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    logs = None
    if args.logs:
        with open(args.logs, encoding="utf-8") as f:
            logs = json.load(f)
    json.dump(engine.analyze(plan, logs, args.mode), sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())