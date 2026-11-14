"""Client report that never invents a number (Scenario C, SIMULATED agency data).

The idea: the model never types a number. It writes sentences with slots like {{revenue}}
and the code fills each slot from a facts table computed in SQL. Then two checks run:
  1. every slot key must exist in the facts (no made-up metric);
  2. the final text goes through the same number check as CX Pulse (no stray typed number).
If either check fails, the report is marked NEEDS REVIEW and is not sendable.

Steps
1. Monthly facts per client with DuckDB (revenue, orders, conversion, ROAS, by source, vs last month).
2. Anomaly detection by code on daily data: tracking outage, traffic spike, conversion jump.
3. Report text: LLM (slots) or demo template (same slots, fixed sentences).
4. Fill slots, check, save Markdown per client for human review.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from pydantic import BaseModel

from workflows.common import llm, numbers

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "data" / "simulated"
OUT = ROOT / "outputs" / "client_report"
SOURCE_NAMES = {"instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube",
                "newsletter": "Newsletter", "affiliate": "Affiliate links"}
SLOT_RE = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")

MONTHLY_SQL = """
WITH m AS (
  SELECT client_id, strftime(date, '%Y-%m') AS month, source,
         sum(clicks) AS clicks, sum(orders) AS orders,
         sum(revenue_eur) AS revenue, sum(spend_eur) AS spend
  FROM daily GROUP BY ALL)
SELECT *, lag(revenue) OVER (PARTITION BY client_id, source ORDER BY month) AS revenue_prev,
          lag(clicks)  OVER (PARTITION BY client_id, source ORDER BY month) AS clicks_prev
FROM m ORDER BY client_id, month, source
"""


def pct(a: float, b: float) -> float | None:
    return None if not b else round(100 * (a - b) / b, 1)


# ---------- 1. Facts ----------
def client_month_facts(monthly: pd.DataFrame, client_id: str, month: str, name: str) -> dict:
    cur = monthly[(monthly.client_id == client_id) & (monthly.month == month)]
    months = sorted(monthly.month.unique())
    prev_month = months[months.index(month) - 1]
    prev = monthly[(monthly.client_id == client_id) & (monthly.month == prev_month)]
    tot = lambda d, c: float(d[c].sum())  # noqa: E731
    rev, rev_p = tot(cur, "revenue"), tot(prev, "revenue")
    orders, orders_p = tot(cur, "orders"), tot(prev, "orders")
    clicks, clicks_p = tot(cur, "clicks"), tot(prev, "clicks")
    spend = tot(cur, "spend")
    f = {
        "client": name, "month": month, "prev_month": prev_month,
        "revenue": round(rev), "revenue_prev": round(rev_p), "revenue_change_pct": pct(rev, rev_p),
        "orders": int(orders), "orders_change_pct": pct(orders, orders_p),
        "clicks": int(clicks), "clicks_change_pct": pct(clicks, clicks_p),
        "conversion_rate_pct": round(100 * orders / clicks, 2) if clicks else None,
        "conversion_rate_prev_pct": round(100 * orders_p / clicks_p, 2) if clicks_p else None,
        "aov": round(rev / orders, 1) if orders else None,
        "spend": round(spend),
    }
    by_src = cur.set_index("source")
    shares = (by_src.revenue / rev * 100).round(1) if rev else by_src.revenue * 0
    for src, r in by_src.iterrows():
        f[f"{src}_revenue"] = round(float(r.revenue))
        f[f"{src}_share_pct"] = float(shares[src])
        f[f"{src}_revenue_change_pct"] = pct(float(r.revenue), float(r.revenue_prev or 0))
    paid_rev = float(by_src.revenue[by_src.spend > 0].sum())  # ROAS only on sources we pay for
    f["paid_roas"] = round(paid_rev / spend, 1) if spend else None
    f["top_source"] = str(by_src.revenue.idxmax())
    changes = {s: f[f"{s}_revenue_change_pct"] for s in by_src.index if f[f"{s}_revenue_change_pct"] is not None}
    f["biggest_gain_source"] = max(changes, key=changes.get)
    f["biggest_drop_source"] = min(changes, key=changes.get)
    return f


# ---------- 2. Anomalies (code, not AI) ----------
def detect_anomalies(daily: pd.DataFrame, client_id: str, month: str) -> list[dict]:
    """Rolling 14-day median per source; flag outages (3+ days at zero), spikes (2+ days > 2.5x)
    and conversion jumps (5+ days > 1.3x the usual conversion rate)."""
    found = []
    d = daily[daily.client_id == client_id].sort_values("date")
    for src, g in d.groupby("source"):
        g = g.set_index("date")
        base = g.clicks.shift(1).rolling(14, min_periods=7).median()
        # Conversion: compare last-7-day orders with what the previous 28 days' conversion rate predicts.
        # A Poisson z-score (not a plain ratio) so small sources with noisy daily rates do not raise false alarms.
        # Thresholds tuned on a separate development simulation (seed 7), never on the test data.
        o7, c7 = g.orders.rolling(7).sum(), g.clicks.rolling(7).sum()
        base_cr = (g.orders.shift(7).rolling(28, min_periods=14).sum()
                   / g.clicks.shift(7).rolling(28, min_periods=14).sum())
        expected = c7 * base_cr
        z = (o7 - expected) / np.sqrt(expected)
        tests = {
            "tracking_outage": (g.clicks == 0) & (base > 20),
            "traffic_spike": g.clicks > 2.5 * base,
            "conversion_jump": (z > 3) & (o7 > 1.2 * expected),
        }
        min_len = {"tracking_outage": 3, "traffic_spike": 2, "conversion_jump": 3}
        for kind, flag in tests.items():
            run_start, run_len = None, 0
            for day, is_on in list(flag.fillna(False).items()) + [(None, False)]:
                if is_on:
                    run_start = run_start or day
                    run_len += 1
                    continue
                if run_len >= min_len[kind] and str(run_start)[:7] == month:
                    found.append({"source": src, "kind": kind, "start": str(run_start)[:10], "days": run_len})
                run_start, run_len = None, 0
    return found


# ---------- 3. Writing ----------
class Report(BaseModel):
    summary: str
    drivers: list[str]
    data_notes: list[str]
    next_month_plan: list[str]


def allowed_slots(facts: dict) -> list[str]:
    return [k for k, v in facts.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and v is not None]


SYSTEM = (
    "You write the monthly performance report an agency sends to a creator brand.\n"
    "RULE: never type a digit. Every number must be a slot written {{key}}, using only the keys listed. "
    "Words like 'last month' are fine. Use the anomalies list for data_notes: an outage means the source's numbers "
    "are understated, not that sales fell; a spike or conversion jump should be explained as a one-off.\n"
    "summary: 2 sentences. drivers: 2-3 bullets. data_notes: one bullet per anomaly, or ['No data issues detected.']. "
    "next_month_plan: 2-3 concrete proposals for next month grounded in the facts. Plain, friendly English."
)


def demo_report(f: dict, anomalies: list[dict]) -> Report:
    n = SOURCE_NAMES
    summary = (f"{f['client']} generated {{{{revenue}}}} in revenue this month ({{{{revenue_change_pct}}}} "
               f"vs last month) from {{{{orders}}}} orders. {n[f['top_source']]} was the top source with "
               f"{{{{{f['top_source']}_share_pct}}}} of revenue.")
    drivers = [
        f"Strongest source: {n[f['biggest_gain_source']]}, {{{{{f['biggest_gain_source']}_revenue_change_pct}}}} vs last month.",
        f"Weakest source: {n[f['biggest_drop_source']]}, {{{{{f['biggest_drop_source']}_revenue_change_pct}}}}.",
        "Conversion rate was {{conversion_rate_pct}} (last month {{conversion_rate_prev_pct}}).",
    ]
    notes = []
    for a in anomalies:
        if a["kind"] == "tracking_outage":
            notes.append(f"Tracking outage on {n[a['source']]} starting {a['start']}: its numbers are understated, not a real drop.")
        elif a["kind"] == "traffic_spike":
            notes.append(f"Traffic spike on {n[a['source']]} starting {a['start']}: treat as a one-off, not the new baseline.")
        else:
            notes.append(f"Conversion jump on {n[a['source']]} starting {a['start']} (likely a promotion): one-off.")
    plan = [f"Double down on {n[f['biggest_gain_source']]}: brief two more creators on what worked this month.",
            f"Review {n[f['biggest_drop_source']]} content and test one new format.",
            "Paid return on ad spend was {{paid_roas}} on {{spend}} of spend; shift budget toward the stronger paid source."
            if f.get("paid_roas") else
            "Keep the posting calendar and review again next month."]
    return Report(summary=summary, drivers=drivers, data_notes=notes or ["No data issues detected."],
                  next_month_plan=plan)


def fmt(key: str, v: float) -> str:
    if key.endswith("_change_pct"):
        return f"{v:+.1f}%"
    if key.endswith("_pct"):
        return f"{v}%"
    if key == "paid_roas":
        return f"{v}x"
    if key in ("revenue", "revenue_prev", "spend") or key.endswith("_revenue"):
        return f"€{v:,.0f}"
    if key == "aov":
        return f"€{v}"
    return f"{v:,}" if isinstance(v, int) else f"{v}"


def fill(text: str, facts: dict, errors: list[str]) -> str:
    def sub(m):
        k = m.group(1)
        if k not in facts or facts[k] is None or isinstance(facts[k], str):
            errors.append(k)
            return "[MISSING]"
        return fmt(k, facts[k])
    return SLOT_RE.sub(sub, text)


def render(f: dict, rep: Report, anomalies: list[dict], mode: str) -> tuple[str, dict]:
    slot_errors: list[str] = []
    raw = " ".join([rep.summary, *rep.drivers, *rep.data_notes, *rep.next_month_plan])
    typed = numbers.check(SLOT_RE.sub(" ", raw), {"dates": [a["start"] for a in anomalies]})  # digits typed by the writer
    parts = {k: fill(v, f, slot_errors) if isinstance(v, str) else [fill(x, f, slot_errors) for x in v]
             for k, v in rep.model_dump().items()}
    final_text = " ".join([parts["summary"], *parts["drivers"], *parts["data_notes"], *parts["next_month_plan"]])
    final = numbers.check(final_text, {**f, "dates": [a["start"] for a in anomalies]})
    ok = final.ok and typed.ok and not slot_errors
    md = [f"# {f['client']} - monthly report, {f['month']}", "", parts["summary"], "", "## What drove the month"]
    md += [f"- {d}" for d in parts["drivers"]] + ["", "## Data notes"] + [f"- {d}" for d in parts["data_notes"]]
    md += ["", "## Proposed plan for next month"] + [f"- {d}" for d in parts["next_month_plan"]]
    status = "PASSED" if ok else "NEEDS REVIEW"
    md += ["", f"_Checks: {status} - {final.numbers_found} numbers, all from the data: {final.ok}; "
               f"unknown slots: {slot_errors or 'none'}; digits typed by the writer: {typed.unsupported or 'none'}. "
               f"Mode: {mode}. SIMULATED data. Draft for human review before sending._"]
    check = {"ok": ok, "numbers_found": final.numbers_found, "unsupported": final.unsupported,
             "typed_digits": typed.unsupported, "slot_errors": slot_errors}
    return "\n".join(md), check


def write_report(f: dict, anomalies: list[dict]) -> tuple[str, dict, list[dict], Report]:
    usages = []
    if llm.available():
        prompt = json.dumps({"allowed_slot_keys": allowed_slots(f),
                             "facts": f, "anomalies": anomalies}, ensure_ascii=False)
        rep, usage = llm.structured_call("client_report.write", SYSTEM, prompt, Report, 2000)
        usages.append(usage)
    else:
        rep = demo_report(f, anomalies)
    md, check = render(f, rep, anomalies, llm.mode())
    return md, check, usages, rep


# ---------- 4. Run ----------
def load():
    daily = pd.read_csv(SIM / "daily_performance.csv", parse_dates=["date"])
    clients = pd.read_csv(SIM / "clients.csv")
    con = duckdb.connect()
    con.register("daily", daily)
    monthly = con.sql(MONTHLY_SQL).df()
    return daily, clients, monthly


def run(month: str = "2026-10") -> dict:
    t0 = time.perf_counter()
    daily, clients, monthly = load()
    OUT.mkdir(parents=True, exist_ok=True)
    usages, checks, all_facts = [], [], []
    for c in clients.itertuples():
        f = client_month_facts(monthly, c.client_id, month, c.client_name)
        anomalies = detect_anomalies(daily, c.client_id, month)
        md, check, u, _ = write_report(f, anomalies)
        usages += u
        checks.append(check)
        all_facts.append({**f, "anomalies": anomalies})
        (OUT / f"{c.client_id}_{month}.md").write_text(md, encoding="utf-8")
    (OUT / f"facts_{month}.json").write_text(json.dumps(all_facts, indent=2), encoding="utf-8")
    summary = {"workflow": "client_report", "mode": llm.mode(), "month": month, "reports": len(checks),
               "reports_passing_checks": sum(c["ok"] for c in checks),
               "numbers_checked": sum(c["numbers_found"] for c in checks),
               "unsupported_numbers": sum(len(c["unsupported"]) + len(c["typed_digits"]) for c in checks),
               "slot_errors": sum(len(c["slot_errors"]) for c in checks),
               "runtime_s": round(time.perf_counter() - t0, 1), **llm.summarize_usage(usages)}
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
