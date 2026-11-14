"""Rebuild everything in order: workflows, evaluations, dashboards, PDF report and memo.

    python src/run_all.py

With an API key in .env (see .env.example), the workflows and evaluations use the AI model and the report
replaces every "pending" with measured results. Without it, everything runs in demo mode.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    [sys.executable, "-m", "workflows", "run", "--scenario", "all"],
    [sys.executable, "src/evaluate.py"],
    [sys.executable, "src/build_dashboards.py"],
    [sys.executable, "src/build_report.py"],
]

if __name__ == "__main__":
    for cmd in STEPS:
        print(">", " ".join(cmd[1:]))
        subprocess.run(cmd, cwd=ROOT, check=True)
