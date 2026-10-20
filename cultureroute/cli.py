"""Command line: plan a route or feed a preference back into the taste profile."""
from __future__ import annotations

import argparse
import json
import os
import sys

from .agent import CultureAgent
from .qloo import QlooClient, QlooConfigError
from .taste import TasteProfile

STATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "state", "taste.json")


def _load_taste() -> TasteProfile:
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as fh:
            return TasteProfile.from_json(fh.read())
    return TasteProfile()


def _save_taste(taste: TasteProfile) -> None:
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as fh:
        fh.write(taste.to_json())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cultureroute")
    sub = ap.add_subparsers(dest="cmd", required=True)

    plan = sub.add_parser("plan", help="build a cultural route")
    plan.add_argument("--city", required=True)
    plan.add_argument("--mood", default="curious", choices=["reflective", "energetic", "curious"])
    plan.add_argument("--minutes", type=int, default=180)
    plan.add_argument("--offline", action="store_true", help="use deterministic fixtures")
    plan.add_argument("--json", action="store_true")

    fb = sub.add_parser("feedback", help="record a like/dislike")
    fb.add_argument("item")
    fb.add_argument("signal", choices=["like", "dislike"])
    fb.add_argument("--tags", default="")

    args = ap.parse_args(argv)
    taste = _load_taste()

    if args.cmd == "feedback":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        if not tags:
            print("feedback needs --tags a,b,c", file=sys.stderr)
            return 2
        taste.observe(tags, args.signal == "like")
        _save_taste(taste)
        print("updated:", taste.top(5))
        return 0

    try:
        client = QlooClient(offline=args.offline)
    except QlooConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    route = CultureAgent(client, taste).plan(args.city, args.mood, args.minutes)
    if args.json:
        print(json.dumps(route.as_dict(), ensure_ascii=False, indent=1))
        return 0
    mode = "OFFLINE FIXTURES" if args.offline else "LIVE QLOO"
    print(f"CultureRoute — {route.city}, mood={route.mood}, mode={mode}")
    for item in route.items:
        print(f"  [{item.kind:5s}] {item.name} ({item.minutes} min, score {item.score}) — {item.why}")
    print(f"  steps used: {len(route.trace)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
