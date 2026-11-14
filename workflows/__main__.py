"""Single entry point.

    python -m workflows run --scenario A     # CX Pulse on real reviews
    python -m workflows run --scenario B     # Competitor Watch on real pricing pages
    python -m workflows run --scenario C     # Client report on simulated agency data
    python -m workflows run --scenario all

Without ANTHROPIC_API_KEY in .env every workflow runs in demo mode (rules + templates).
"""
from __future__ import annotations

import argparse
import json

from workflows.common import llm


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m workflows")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run one scenario end to end")
    run.add_argument("--scenario", choices=["A", "B", "C", "all"], required=True)
    args = parser.parse_args()

    print(f"Mode: {llm.mode()} (model {llm.MODEL if llm.available() else 'none - demo rules/templates'})")
    todo = ["A", "B", "C"] if args.scenario == "all" else [args.scenario]
    for s in todo:
        if s == "A":
            from workflows.cx_pulse.pipeline import run as go
        elif s == "B":
            from workflows.competitor_watch.pipeline import run as go
        else:
            from workflows.client_report.pipeline import run as go
        print(json.dumps(go(), indent=2))


if __name__ == "__main__":
    main()
