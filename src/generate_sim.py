"""SIMULATED data for Scenario C: a creator-marketing agency and its (fictional) clients.

The shape mirrors how a small agency tracks creator-driven sales: daily clicks, orders and revenue
by traffic source, plus paid spend. Clients, names and numbers are invented (seed 42).
Some events are planted on purpose and logged in data/simulated/events.csv, so the evaluation
can check that the report notices them (the workflow never reads that file):
  - viral_spike:     one source has 3-6x traffic for 2-4 days
  - tracking_outage: one source records zero clicks/orders for 3-5 days (a data problem, not a sales drop)
  - price_promo:     conversion rate +40% for a week (a promotion)

Outputs: data/simulated/daily_performance.csv, clients.csv, events.csv
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "simulated"

CLIENTS = [  # fictional creator brands
    ("C01", "Lumen Skincare", "beauty", 1.0),
    ("C02", "Trailhead Gear", "outdoor", 0.8),
    ("C03", "Mirepoix Kitchen", "food", 0.6),
    ("C04", "Atelier Nord", "fashion", 1.2),
    ("C05", "Pixel & Pine", "gaming", 0.7),
    ("C06", "Studio Calme", "wellness", 0.5),
]
SOURCES = {  # base daily clicks, conversion rate, average order value (EUR), paid spend per click
    "instagram": (900, 0.021, 42.0, 0.25),
    "tiktok": (1300, 0.012, 35.0, 0.15),
    "youtube": (500, 0.030, 55.0, 0.00),
    "newsletter": (300, 0.055, 48.0, 0.00),
    "affiliate": (250, 0.040, 60.0, 0.00),
}
START, END = "2026-05-01", "2026-10-31"


def main(seed: int = 42, out: Path = OUT) -> None:
    """seed 42 = the published test data; another seed = a development copy used to tune detectors."""
    rng = np.random.default_rng(seed)
    out.mkdir(parents=True, exist_ok=True)
    days = pd.date_range(START, END, freq="D")
    rows, events = [], []
    for cid, name, vertical, scale in CLIENTS:
        trend = rng.uniform(-0.04, 0.06)  # monthly growth of this client
        for src, (clicks0, cr0, aov0, cpc) in SOURCES.items():
            mult = np.ones(len(days))
            cr_mult = np.ones(len(days))
            # weekly seasonality and slow trend
            dow = np.array([1.0, 0.95, 0.95, 1.0, 1.05, 1.15, 1.1])[days.day_of_week]
            months = (days - days[0]).days / 30.0
            base = clicks0 * scale * dow * (1 + trend) ** months
            # planted events (about one per client-source over 6 months, at random)
            if rng.random() < 0.45:
                d0 = int(rng.integers(10, len(days) - 10))
                length = int(rng.integers(2, 5))
                factor = float(rng.uniform(3, 6))
                mult[d0:d0 + length] *= factor
                events.append((cid, src, "viral_spike", days[d0].date(), days[d0 + length - 1].date()))
            if rng.random() < 0.25:
                d0 = int(rng.integers(10, len(days) - 10))
                length = int(rng.integers(3, 6))
                mult[d0:d0 + length] = 0.0
                events.append((cid, src, "tracking_outage", days[d0].date(), days[d0 + length - 1].date()))
            if rng.random() < 0.20:
                d0 = int(rng.integers(10, len(days) - 10))
                cr_mult[d0:d0 + 7] *= 1.4
                events.append((cid, src, "price_promo", days[d0].date(), days[d0 + 6].date()))
            clicks = rng.poisson(np.maximum(base * mult, 0))
            orders = rng.binomial(clicks, np.clip(cr0 * cr_mult * rng.uniform(0.85, 1.15, len(days)), 0, 1))
            revenue = np.round(orders * aov0 * rng.uniform(0.9, 1.1, len(days)), 2)
            spend = np.round(clicks * cpc * rng.uniform(0.9, 1.1, len(days)), 2)
            for d, c, o, r, s in zip(days, clicks, orders, revenue, spend):
                rows.append((cid, d.date(), src, int(c), int(o), float(r), float(s)))

    daily = pd.DataFrame(rows, columns=["client_id", "date", "source", "clicks", "orders", "revenue_eur", "spend_eur"])
    daily.to_csv(out / "daily_performance.csv", index=False)
    pd.DataFrame([c[:3] for c in CLIENTS], columns=["client_id", "client_name", "vertical"]).to_csv(out / "clients.csv", index=False)
    pd.DataFrame(events, columns=["client_id", "source", "event", "start", "end"]).to_csv(out / "events.csv", index=False)
    print(f"{len(daily):,} rows, {len(events)} planted events -> {out}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:  # e.g. `python src/generate_sim.py 7` -> outputs/dev_sim (not published)
        main(int(sys.argv[1]), ROOT / "outputs" / "dev_sim")
    else:
        main()
