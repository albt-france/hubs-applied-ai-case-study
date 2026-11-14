"""Evaluate the three workflows against hand-labelled test sets.

    python src/evaluate.py            # all scenarios
    python src/evaluate.py A          # one scenario

What is measured (same grid for every workflow, see docs/ and the report page "Measured, not assumed"):
- accuracy of the AI step against reference labels (theme/severity, extracted prices, ...);
- unsupported ("invented") numbers in generated text: must be 0;
- how well the number check itself catches planted errors (so "0 invented" is meaningful);
- cost and time per run; time saved vs doing it by hand (manual times are assumptions,
  see data/ASSUMPTIONS.md).

Results go to outputs/eval/<scenario>.json. In demo mode the AI columns say "pending".
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflows.common import llm, numbers  # noqa: E402

OUT = ROOT / "outputs" / "eval"


def _prf(y_true: list, y_pred: list, positive) -> dict:
    tp = sum(t == positive and p == positive for t, p in zip(y_true, y_pred))
    fp = sum(t != positive and p == positive for t, p in zip(y_true, y_pred))
    fn = sum(t == positive and p != positive for t, p in zip(y_true, y_pred))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(prec, 3), "recall": round(rec, 3),
            "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0, "support": tp + fn}


def classification_scores(y_true: list, y_pred: list) -> dict:
    labels = sorted(set(y_true))
    per = {lab: _prf(y_true, y_pred, lab) for lab in labels}
    return {"accuracy": round(sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true), 3),
            "macro_f1": round(sum(v["f1"] for v in per.values()) / len(per), 3), "per_label": per}


# ---------------------------------------------------------------- number-check stress test
def plant_errors(text: str, rng: random.Random, n: int = 1) -> tuple[str, int]:
    """Change n numbers in a correct text into plausible wrong values (what a model might invent)."""
    dates = [d.span() for d in numbers.DATE_RE.finditer(text)]  # dates are not claims: leave them alone
    spans = [m for m in re.finditer(r"(?<![\w.])\d+(?:\.\d+)?", text)
             if not any(a <= m.start() < b for a, b in dates)]
    if not spans:
        return text, 0
    chosen = rng.sample(spans, min(n, len(spans)))
    out, last, planted = [], 0, 0
    for m in sorted(chosen, key=lambda m: m.start()):
        val = float(m.group())
        wrong = val * rng.choice([1.3, 0.7, 1.5, 2.0]) + rng.choice([1, 3, 7])
        token = f"{wrong:.1f}" if "." in m.group() else f"{int(round(wrong))}"
        out += [text[last:m.start()], token]
        last = m.end()
        planted += 1
    out.append(text[last:])
    return "".join(out), planted


def stress_number_check(texts_and_facts: list[tuple[str, dict]], always=(1, 2, 4), seed: int = 7,
                        trials: int = 25) -> dict:
    """Plant one wrong number in a correct text, `trials` times per text; count what the check catches.

    - clean texts must pass (no false alarms);
    - a planted number is missed only when it happens to equal another true number in the facts
      (a "collision"): the check proves every number exists in the data, not that it sits next to the
      right label. That residual risk is why a human reviews every output.
    """
    rng = random.Random(seed)
    clean_pass, caught, planted_total = 0, 0, 0
    for text, facts in texts_and_facts:
        clean_pass += numbers.check(text, facts, always).ok
        for _ in range(trials):
            bad, planted = plant_errors(text, rng)
            if planted:
                planted_total += 1
                caught += not numbers.check(bad, facts, always).ok
    return {"texts": len(texts_and_facts), "clean_texts_passing": clean_pass,
            "planted_errors": planted_total, "planted_errors_caught": caught,
            "missed_collisions": planted_total - caught,
            "catch_rate": round(caught / planted_total, 3) if planted_total else None}


# ---------------------------------------------------------------- Scenario A
def eval_a() -> dict:
    from workflows.cx_pulse import pipeline, rules

    df = pd.read_csv(ROOT / "data" / "eval" / "cx_eval_reviews.csv", dtype={"review_id": str})
    res: dict = {"scenario": "A", "test_set": len(df), "mode": llm.mode()}

    t0 = time.perf_counter()
    demo = [rules.classify(t, int(s)) for t, s in zip(df.text, df.review_score)]
    res["rules"] = {"theme": classification_scores(list(df.label_theme), [d[0] for d in demo]),
                    "severity": classification_scores(list(df.label_severity), [d[1] for d in demo]),
                    "seconds": round(time.perf_counter() - t0, 2)}
    res["rules"]["high_severity"] = _prf(list(df.label_severity), [d[1] for d in demo], "high")

    if llm.available():
        t0 = time.perf_counter()
        pred, usages = pipeline.classify_llm(df[["review_id", "review_score", "text"]])
        pred = df[["review_id"]].merge(pred, on="review_id")
        res["llm"] = {"theme": classification_scores(list(df.label_theme), list(pred.theme)),
                      "severity": classification_scores(list(df.label_severity), list(pred.severity)),
                      "high_severity": _prf(list(df.label_severity), list(pred.severity), "high"),
                      "seconds": round(time.perf_counter() - t0, 1), "usage": llm.summarize_usage(usages),
                      "labels_missing": int(pred.label_missing.sum())}
        errors = df.assign(pred_theme=pred.theme.values, pred_severity=pred.severity.values)
        errors = errors[(errors.pred_theme != errors.label_theme) | (errors.pred_severity != errors.label_severity)]
        errors.drop(columns=["text"]).to_csv(OUT / "A_llm_errors.csv", index=False)
    else:
        res["llm"] = "pending (no API key)"

    # Weekly notes produced by the last run: invented numbers + stress test of the checker
    facts = json.loads((ROOT / "outputs" / "cx_pulse" / "facts.json").read_text(encoding="utf-8"))
    summary = json.loads((ROOT / "outputs" / "cx_pulse" / "run_summary.json").read_text(encoding="utf-8"))
    res["notes"] = {"mode": summary["mode"], "notes": summary["notes"],
                    "numbers_checked": summary["numbers_checked"],
                    "unsupported_numbers": summary["unsupported_numbers"]}
    texts = []
    for f in facts:
        n = pipeline.note_demo(f)
        texts.append((" ".join([n.headline, *n.worse, *n.better, n.action]), f))
    res["number_check_stress"] = stress_number_check(texts)
    res["run"] = {k: summary[k] for k in ("reviews_classified", "runtime_s", "calls", "cost_usd", "model_time_s")}
    return res


# ---------------------------------------------------------------- Scenario B / C
def eval_b() -> dict:
    from workflows.competitor_watch import evaluate as ev_b
    return ev_b.evaluate()


def eval_c() -> dict:
    from workflows.client_report import evaluate as ev_c
    return ev_c.evaluate(stress_number_check)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    todo = sys.argv[1:] or ["A", "B", "C"]
    for s in todo:
        res = {"A": eval_a, "B": eval_b, "C": eval_c}[s]()
        (OUT / f"{s}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(json.dumps(res, indent=2)[:3000])


if __name__ == "__main__":
    main()
