"""Evaluation of the client report workflow on 30 client-months (6 fictional clients x Jun-Oct 2026).

Ground truth for anomalies = the simulator's event log (data/simulated/events.csv). The workflow never
reads it, so detection is measured, not assumed.
"""
from __future__ import annotations

import random
import time

import pandas as pd

from workflows.common import llm, numbers
from workflows.client_report import pipeline as p

MONTHS = ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
KIND = {"viral_spike": "traffic_spike", "tracking_outage": "tracking_outage", "price_promo": "conversion_jump"}


def evaluate(stress_number_check) -> dict:
    daily, clients, monthly = p.load()
    events = pd.read_csv(p.SIM / "events.csv")
    events["month"] = events.start.str[:7]
    events = events[events.month.isin(MONTHS)]

    t0 = time.perf_counter()
    reports, usages, detected_all, texts = [], [], [], []
    for c in clients.itertuples():
        for m in MONTHS:
            f = p.client_month_facts(monthly, c.client_id, m, c.client_name)
            an = p.detect_anomalies(daily, c.client_id, m)
            md, check, u, rep = p.write_report(f, an)
            usages += u
            reports.append({"client_id": c.client_id, "month": m, **check,
                            "anomalies_detected": len(an),
                            "anomalies_mentioned": sum(a["source"] in md.lower() or p.SOURCE_NAMES[a["source"]] in md
                                                       for a in an)})
            detected_all += [{"client_id": c.client_id, "month": m, **a} for a in an]
            body = md.split("_Checks:")[0].split("\n", 1)[1]  # drop the title line (month label)
            texts.append((body, {**f, "dates": [a["start"] for a in an]}))
    runtime = time.perf_counter() - t0
    det = pd.DataFrame(detected_all)

    # Anomaly detection: match planted events to detections (same client, source, kind, month)
    hits = []
    for e in events.itertuples():
        match = det[(det.client_id == e.client_id) & (det.source == e.source) &
                    (det.kind == KIND[e.event]) & (det.month == e.month)] if len(det) else det
        hits.append({"event": e.event, "found": len(match) > 0})
    hits = pd.DataFrame(hits)
    true_keys = {(e.client_id, e.source, KIND[e.event], e.month) for e in events.itertuples()}
    false_alarms = [r for r in det.itertuples() if (r.client_id, r.source, r.kind, r.month) not in true_keys] if len(det) else []

    # Stress test 1: wrong numbers planted in the final text (same test as CX Pulse)
    stress_final = stress_number_check(texts, always=(), trials=5)
    # Stress test 2: the writer types a number instead of using a slot -> must always be flagged
    rng = random.Random(3)
    typed_caught = sum(not numbers.check(f"Revenue grew {rng.randint(3, 60)}% this month.", {}).ok for _ in texts)

    r = pd.DataFrame(reports)
    return {
        "scenario": "C", "mode": llm.mode(), "client_months": len(r),
        "reports_passing_checks": int(r.ok.sum()),
        "numbers_checked": int(r.numbers_found.sum()),
        "unsupported_numbers": int(r.unsupported.map(len).sum() + r.typed_digits.map(len).sum()),
        "slot_errors": int(r.slot_errors.map(len).sum()),
        "anomaly_detection": {
            "planted_events": len(hits), "found": int(hits.found.sum()),
            "recall": round(float(hits.found.mean()), 3),
            "recall_by_type": hits.groupby("event").found.mean().round(3).to_dict(),
            "detections": len(det), "false_alarms": len(false_alarms),
            "false_alarms_by_kind": pd.Series([r.kind for r in false_alarms], dtype=object).value_counts().to_dict(),
            "precision": round(1 - len(false_alarms) / len(det), 3) if len(det) else None,
        },
        "anomalies_mentioned_in_reports": f"{int(r.anomalies_mentioned.sum())}/{int(r.anomalies_detected.sum())}",
        "number_check_stress_final_text": stress_final,
        "typed_number_stress": {"planted": len(texts), "caught": typed_caught},
        "runtime_s_30_reports": round(runtime, 1), "usage": llm.summarize_usage(usages),
    }
