"""Evaluation of Competitor Watch against reference labels written by reading each snapshot.

1. Extraction: plan + list price pairs per snapshot (precision / recall), currency, promo prices,
   and "hallucinations" (prices returned for pages that show none).
2. Change detection, per period between two readable snapshots: did we flag the periods with a real
   change, and how many false alarms?
Always scores the rules baseline; also scores the AI model when an API key is set.
"""
from __future__ import annotations

import json
import time

import pandas as pd

from workflows.common import llm
from workflows.competitor_watch import pipeline as p

ROOT = p.ROOT


def _pairs(plans) -> set:
    return {(p.norm(x["name"]), round(float(x["list_price"]), 2)) for x in plans if x["list_price"] is not None}


def score(snaps: pd.DataFrame, extracted: dict, tag: str) -> dict:
    labels = pd.read_csv(ROOT / "data" / "eval" / "pricing_labels.csv", dtype={"timestamp": str})
    truth_changes = pd.read_csv(ROOT / "data" / "eval" / "pricing_changes.csv", dtype={"from_ts": str, "to_ts": str})
    tp = fp = fn = exact = cur_ok = cur_n = promo_hit = promo_n = halluc = 0
    rows = []
    for s in snaps.itertuples():
        key = f"{s.vendor}_{s.timestamp}"
        lab = labels[(labels.vendor == s.vendor) & (labels.timestamp == s.timestamp) & labels.plan.notna()]
        truth = {(p.norm(r.plan), round(float(r.list_price), 2)) for r in lab.itertuples()}
        pred_plans = extracted[key]["plans"]
        pred = _pairs(pred_plans)
        if not truth:
            halluc += len(pred)
        tp += len(truth & pred)
        fp += len(pred - truth)
        fn += len(truth - pred)
        exact += truth == pred
        by_name = {p.norm(x["name"]): x for x in pred_plans}
        for r in lab.itertuples():
            x = by_name.get(p.norm(r.plan))
            if x:
                cur_n += 1
                cur_ok += x["currency"] == r.currency
            if pd.notna(r.promo_price):
                promo_n += 1
                promo_hit += bool(x and x.get("promo_price") and abs(x["promo_price"] - r.promo_price) < 0.01)
        rows.append({"snapshot": key, "truth": sorted(truth), "pred": sorted(pred), "exact": truth == pred})
    pd.DataFrame(rows).to_csv(ROOT / "outputs" / "eval" / f"B_{tag}_extraction.csv", index=False)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0

    periods = p.detect_changes(snaps, extracted)
    flagged = {(x["vendor"], x["to_ts"]) for x in periods if x["changed"]}
    real = {(r.vendor, r.to_ts) for r in truth_changes.itertuples() if r.real_change == "yes"}
    return {
        "extraction": {"plan_price_pairs_truth": tp + fn, "precision": round(prec, 3), "recall": round(rec, 3),
                       "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0,
                       "snapshots_exact": exact, "currency_accuracy": round(cur_ok / cur_n, 3) if cur_n else None,
                       "promo_prices_found": f"{promo_hit}/{promo_n}", "prices_invented_on_empty_pages": halluc},
        "change_detection": {"periods_labelled": len(truth_changes), "real_changes": len(real),
                             "detected": len(real & flagged), "missed": len(real - flagged),
                             "false_alarms": len(flagged - real),
                             "recall": round(len(real & flagged) / len(real), 3) if real else None,
                             "false_alarm_periods": sorted(f"{v} {t[:8]}" for v, t in flagged - real)},
    }


def evaluate() -> dict:
    snaps = pd.read_csv(ROOT / "data" / "public" / "pricing_snapshots.csv", dtype={"timestamp": str})
    labels = pd.read_csv(ROOT / "data" / "eval" / "pricing_labels.csv", dtype={"timestamp": str})
    empty = sum(labels[(labels.vendor == s.vendor) & (labels.timestamp == s.timestamp)].plan.isna().all()
                for s in snaps.itertuples())

    # Rules baseline (fresh from raw pages when available, else the published demo extraction)
    rules_path = ROOT / "data" / "public" / "pricing_extracted_demo.json"
    published = json.loads(rules_path.read_text(encoding="utf-8")) if rules_path.exists() else {}
    t0 = time.perf_counter()
    rules = {}
    for s in snaps.itertuples():
        key = f"{s.vendor}_{s.timestamp}"
        raw = p.RAW / f"{key}.txt"
        rules[key] = p.extract_demo(raw.read_text(encoding="utf-8")).model_dump() if raw.exists() else published[key]
    rules_time = time.perf_counter() - t0
    res = {"scenario": "B", "mode": llm.mode(), "snapshots": len(snaps), "unreadable_in_truth": int(empty),
           **score(snaps, rules, "rules"), "rules_runtime_s": round(rules_time, 2)}

    if llm.available():
        t0 = time.perf_counter()
        extracted, usages = p.extract_all(snaps, use_cache=False)
        res["llm_extraction"] = {**score(snaps, extracted, "llm"), "runtime_s": round(time.perf_counter() - t0, 1),
                                 "usage": llm.summarize_usage(usages)}
    else:
        res["llm_extraction"] = None
    return res
