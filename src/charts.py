"""Figures shared by the HTML dashboards (interactive) and the PDF report (static SVG).

Visual rules (same as the previous case study): blue for the data in focus, grey for comparison,
red only for errors/alerts, dashed lines for thresholds, thin marks, direct labels, no dual axis.
Every number shown comes from outputs/ (workflow runs and evaluations).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
BLUE, ORANGE, AQUA = "#2A78D6", "#EB6834", "#1BAF7A"
GREY, GREY_LIGHT, RED = "#898781", "#D9D7D0", "#D03B3B"
INK, INK2, GRID, SURFACE = "#0B0B0B", "#52514E", "#E1E0D9", "#FCFCFB"
FONT = "Segoe UI, -apple-system, Helvetica, Arial, sans-serif"
LABEL = {"not_received": "Not received", "delivery_late": "Late delivery", "wrong_or_incomplete": "Wrong / incomplete",
         "damaged_defective": "Damaged / defective", "quality_mismatch": "Quality / not as described",
         "seller_service": "Seller service / refund", "other": "Other complaint", "praise": "No complaint"}


def base(fig: go.Figure, height: int = 300, legend: bool = False) -> go.Figure:
    fig.update_layout(template="none", height=height, margin=dict(l=8, r=16, t=40 if legend else 12, b=8),
                      font=dict(family=FONT, size=12, color=INK2), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=legend,
                      legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=12, color=INK2)),
                      uniformtext=dict(minsize=11, mode="show"),
                      hoverlabel=dict(font=dict(family=FONT)))
    fig.update_xaxes(showgrid=False, linecolor=GRID, ticks="", tickfont=dict(color=GREY), automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color=GREY), automargin=True)
    return fig


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- Scenario A
def a_theme_trend() -> go.Figure:
    t = pd.read_csv(ROOT / "outputs/cx_pulse/weekly_themes.csv", parse_dates=["week_start"])
    totals = pd.read_csv(ROOT / "data/public/reviews_weekly_totals.csv", parse_dates=["week_start"])
    low = totals[totals.reviews < 0.5 * totals.reviews.median()].week_start
    fig = go.Figure()
    for theme, color in [("not_received", BLUE), ("delivery_late", ORANGE), ("wrong_or_incomplete", AQUA)]:
        s = t[t.theme == theme].set_index("week_start").share_pct.reindex(sorted(t.week_start.unique()), fill_value=0)
        fig.add_scatter(x=s.index, y=s.values, mode="lines+markers", name=LABEL[theme],
                        line=dict(color=color, width=2), marker=dict(size=8),
                        hovertemplate="%{x|%d %b}: %{y:.1f}% of sampled reviews<extra>" + LABEL[theme] + "</extra>")
        fig.add_annotation(x=s.index[-1], y=s.values[-1], text=LABEL[theme], showarrow=False, xanchor="left",
                           xshift=8, font=dict(size=11, color=INK2))
    for w in low:
        fig.add_vrect(x0=w - pd.Timedelta(days=3), x1=w + pd.Timedelta(days=3), fillcolor=RED, opacity=0.08, line_width=0)
        fig.add_annotation(x=w, y=0.97, yref="paper", text="low-volume week", showarrow=False, font=dict(size=10, color=RED))
    fig.update_yaxes(ticksuffix="%", rangemode="tozero")
    fig.update_xaxes(range=[t.week_start.min() - pd.Timedelta(days=3), t.week_start.max() + pd.Timedelta(days=24)])
    return base(fig, 290, legend=True)


def a_week_vs_before() -> go.Figure:
    f = load("outputs/cx_pulse/facts.json")[-1]
    rows = sorted(f["themes"].items(), key=lambda kv: kv[1]["share_pct"])
    names = [LABEL[k] for k, _ in rows]
    fig = go.Figure()
    fig.add_bar(y=names, x=[v["prev4_pct"] for _, v in rows], orientation="h", name="Previous 4 weeks (avg)",
                marker=dict(color=GREY_LIGHT), hovertemplate="%{y}: %{x:.1f}% (4-week avg)<extra></extra>")
    fig.add_bar(y=names, x=[v["share_pct"] for _, v in rows], orientation="h", name=f"Week of {f['week_start']}",
                marker=dict(color=BLUE), text=[f"{v['share_pct']}%" for _, v in rows], textposition="outside",
                textfont=dict(color=INK2, size=11), hovertemplate="%{y}: %{x:.1f}% this week<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08)
    top = max(max(v["share_pct"], v["prev4_pct"]) for _, v in rows)
    fig.update_xaxes(ticksuffix="%", showgrid=True, gridcolor=GRID, range=[0, top * 1.22])
    fig.update_yaxes(showgrid=False)
    return base(fig, 290, legend=True)


def a_eval_bars() -> go.Figure:
    e = load("outputs/eval/A.json")
    metrics = [("Theme accuracy", e["rules"]["theme"]["accuracy"],
                e["llm"]["theme"]["accuracy"] if isinstance(e["llm"], dict) else None),
               ("Severity accuracy", e["rules"]["severity"]["accuracy"],
                e["llm"]["severity"]["accuracy"] if isinstance(e["llm"], dict) else None),
               ("High-severity recall", e["rules"]["high_severity"]["recall"],
                e["llm"]["high_severity"]["recall"] if isinstance(e["llm"], dict) else None)]
    fig = go.Figure()
    fig.add_bar(x=[m[0] for m in metrics], y=[m[1] * 100 for m in metrics], name="Rules (demo mode)",
                marker=dict(color=GREY_LIGHT), text=[f"{m[1]*100:.0f}%" for m in metrics], textposition="outside")
    if metrics[0][2] is not None:
        fig.add_bar(x=[m[0] for m in metrics], y=[m[2] * 100 for m in metrics], name="AI model",
                    marker=dict(color=BLUE), text=[f"{m[2]*100:.0f}%" for m in metrics], textposition="outside")
    fig.add_hline(y=90, line=dict(color=INK2, dash="dash", width=1))
    fig.add_annotation(x=1, xref="paper", y=90, text="target 90%", showarrow=False, yshift=8, xanchor="right",
                       font=dict(size=10, color=INK2))
    fig.update_yaxes(range=[0, 108], ticksuffix="%")
    fig.update_layout(barmode="group", bargap=0.4)
    return base(fig, 260, legend=True)


# ---------------------------------------------------------------- Scenario B
def b_price_steps() -> go.Figure:
    """List price over time for the plans whose price or structure changed."""
    snaps = pd.read_csv(ROOT / "data/public/pricing_snapshots.csv", dtype={"timestamp": str})
    labels = pd.read_csv(ROOT / "data/eval/pricing_labels.csv", dtype={"timestamp": str}).dropna(subset=["plan"])
    labels = labels.merge(snaps[["vendor", "timestamp"]], on=["vendor", "timestamp"])
    labels["date"] = pd.to_datetime(labels.timestamp.str[:8])
    series = [("zapier", ["Professional", "Pro"], "Zapier Professional / Pro", BLUE, -9),
              ("clickup", ["Business"], "ClickUp Business", ORANGE, 0),
              ("notion", ["Business"], "Notion Business", AQUA, 9)]
    fig = go.Figure()
    for vendor, plans, name, color, yshift in series:
        d = labels[(labels.vendor == vendor) & labels.plan.isin(plans)].sort_values("date")
        hover = [f"{r.plan}: {r.currency} {r.list_price:g}" for r in d.itertuples()]
        fig.add_scatter(x=d.date, y=d.list_price, mode="lines+markers", line=dict(shape="hv", color=color, width=2),
                        marker=dict(size=8, symbol=["diamond" if c == "EUR" else "circle" for c in d.currency]),
                        name=name, text=hover, hovertemplate="%{x|%b %Y} · %{text}<extra>" + name + "</extra>")
    eur = labels[(labels.vendor == "notion") & (labels.currency == "EUR") & (labels.plan == "Business")]
    if len(eur):
        fig.add_annotation(x=eur.date.iloc[0], y=float(eur.list_price.iloc[0]), text="shown in EUR", ax=0, ay=28,
                           font=dict(size=10, color=RED), arrowcolor=RED)
    fig.update_yaxes(tickprefix="$", rangemode="tozero", title=None)
    fig.update_xaxes(range=[pd.Timestamp("2023-12-01"), pd.Timestamp("2027-01-15")])
    return base(fig, 290, legend=True)


def b_extraction_bars() -> go.Figure:
    e = load("outputs/eval/B.json")
    llm_e = e.get("llm_extraction")  # None until the AI model has been evaluated
    metrics = [("Plan + price precision", e["extraction"]["precision"]), ("Plan + price recall", e["extraction"]["recall"]),
               ("Real changes detected", e["change_detection"]["recall"])]
    fig = go.Figure()
    fig.add_bar(x=[m[0] for m in metrics], y=[m[1] * 100 for m in metrics], name="Rules (demo mode)",
                marker=dict(color=GREY_LIGHT), text=[f"{m[1]*100:.0f}%" for m in metrics], textposition="outside")
    if llm_e:
        vals = [llm_e["extraction"]["precision"], llm_e["extraction"]["recall"], llm_e["change_detection"]["recall"]]
        fig.add_bar(x=[m[0] for m in metrics], y=[v * 100 for v in vals], name="AI model", marker=dict(color=BLUE),
                    text=[f"{v*100:.0f}%" for v in vals], textposition="outside")
    fig.update_yaxes(range=[0, 110], ticksuffix="%")
    fig.update_layout(barmode="group", bargap=0.4)
    return base(fig, 260, legend=True)


# ---------------------------------------------------------------- Scenario C
def c_anomaly_example(client_id: str = "C01", source: str = "instagram") -> go.Figure:
    d = pd.read_csv(ROOT / "data/simulated/daily_performance.csv", parse_dates=["date"])
    d = d[(d.client_id == client_id) & (d.source == source) & (d.date >= "2026-06-20") & (d.date <= "2026-09-10")]
    ev = pd.read_csv(ROOT / "data/simulated/events.csv")
    ev = ev[(ev.client_id == client_id) & (ev.source == source)]
    fig = go.Figure()
    for i, e in enumerate(ev.itertuples()):
        color = RED if e.event == "tracking_outage" else BLUE
        fig.add_vrect(x0=pd.Timestamp(e.start) - pd.Timedelta(hours=12), x1=pd.Timestamp(e.end) + pd.Timedelta(hours=12),
                      fillcolor=color, opacity=0.10, line_width=0)
        label = {"tracking_outage": "tracking outage: flagged, not a sales drop", "viral_spike": "traffic spike: one-off",
                 "price_promo": "promotion"}[e.event]
        fig.add_annotation(x=pd.Timestamp(e.end) + pd.Timedelta(days=1), y=1 - 0.12 * i, yref="paper", text=label,
                           showarrow=False, xanchor="left", font=dict(size=10, color=color))
    fig.add_scatter(x=d.date, y=d.clicks, mode="lines", line=dict(color=BLUE, width=2), name="Daily clicks",
                    hovertemplate="%{x|%d %b}: %{y:,} clicks<extra></extra>")
    fig.update_yaxes(rangemode="tozero")
    return base(fig, 260)


def c_revenue_by_client(month: str = "2026-10") -> go.Figure:
    facts = load(f"outputs/client_report/facts_{month}.json")
    facts = sorted(facts, key=lambda f: f["revenue"])
    fig = go.Figure(go.Bar(y=[f["client"] for f in facts], x=[f["revenue"] for f in facts], orientation="h",
                           marker=dict(color=BLUE), text=[f"€{f['revenue']:,} ({f['revenue_change_pct']:+.1f}%)" for f in facts],
                           textposition="outside", textfont=dict(color=INK2, size=11),
                           hovertemplate="%{y}: €%{x:,}<extra></extra>"))
    fig.update_xaxes(tickprefix="€", showgrid=True, gridcolor=GRID, range=[0, max(f["revenue"] for f in facts) * 1.35])
    fig.update_yaxes(showgrid=False)
    return base(fig, 260)


def time_saved() -> go.Figure:
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    import assumptions
    t = assumptions.weekly_minutes()
    names = ["C · Client report", "B · Competitor Watch", "A · CX Pulse"]
    keys = ["C", "B", "A"]
    fig = go.Figure()
    fig.add_bar(y=names, x=[t[k]["manual"] for k in keys], orientation="h", name="Manual (assumed)",
                marker=dict(color=GREY_LIGHT), text=[f"{t[k]['manual']} min" for k in keys], textposition="outside")
    fig.add_bar(y=names, x=[t[k]["with_workflow"] for k in keys], orientation="h", name="With the workflow (human review)",
                marker=dict(color=BLUE), text=[f"{t[k]['with_workflow']} min" for k in keys], textposition="outside")
    fig.update_layout(barmode="group", bargap=0.3)
    fig.update_xaxes(ticksuffix=" min", showgrid=True, gridcolor=GRID, range=[0, 100])
    fig.update_yaxes(showgrid=False)
    return base(fig, 220, legend=True)


def svg(fig: go.Figure, width: int = 640) -> str:
    """Static SVG for the PDF (kaleido)."""
    out = fig.to_image(format="svg", width=width, height=fig.layout.height or 300).decode("utf-8")
    return out[out.find("<svg"):]
