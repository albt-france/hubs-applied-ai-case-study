"""Build one interactive HTML dashboard per scenario (docs/dashboard_A.html, _B, _C).

Plotly charts + the latest workflow output (note / digest / report) + evaluation tiles.
Open the files in a browser; they also work on GitHub Pages.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import charts  # noqa: E402

DOCS = ROOT / "docs"
FOOT = "Independent case study based on public information · not affiliated with or endorsed by Hubs"

CSS = """
:root{color-scheme:light;--bg:#F4F4F2;--card:#FCFCFB;--line:#E1E0D9;--ink:#0B0B0B;--ink2:#52514E;--muted:#898781;--blue:#2A78D6;--red:#D03B3B}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI",-apple-system,Helvetica,Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 16px 40px}
header{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}
h1{font-size:26px;margin:0 0 6px}p.sub{color:var(--ink2);margin:0 0 18px;max-width:860px}
.tag{font-size:12px;font-weight:600;letter-spacing:.06em;color:var(--ink2);border:1px solid var(--line);border-radius:6px;padding:4px 8px;white-space:nowrap;background:var(--card)}
.grid{display:grid;gap:14px}.g4{grid-template-columns:repeat(4,1fr)}.g2{grid-template-columns:1fr 1fr}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px 18px}
.card h3{margin:0 0 8px;font-size:15px}.kpi .v{font-size:30px;font-weight:700}.kpi .l{color:var(--ink2);font-size:13px}
.kpi .s{font-size:11px;font-weight:600;letter-spacing:.05em;color:var(--muted);margin-bottom:6px}
.out{font-size:13.5px;line-height:1.5}.out h2{font-size:16px;margin:4px 0 8px}.out h1{font-size:18px}
.out code{background:#efeee9;padding:1px 4px;border-radius:4px}
.g2>.card:last-child:nth-child(odd){grid-column:1/-1}
footer{color:var(--muted);font-size:12px;margin-top:22px}
@media (max-width:820px){.g4{grid-template-columns:1fr 1fr}.g2{grid-template-columns:1fr}}
"""


def md_to_html(md: str) -> str:
    """Tiny Markdown renderer (headings, bullets, bold, italics, paragraphs) - enough for our outputs."""
    import re
    out, in_list = [], False
    for line in md.splitlines():
        esc = html.escape(line)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
        esc = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", esc)
        esc = re.sub(r"`(.+?)`", r"<code>\1</code>", esc)
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{esc[2:]}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.startswith("### "):
            out.append(f"<h3>{esc[4:]}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{esc[3:]}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{esc[2:]}</h1>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip():
            out.append(f"<p>{esc}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def page(title: str, sub: str, tag: str, kpis: list[tuple[str, str, str]], charts_html: list[tuple[str, str]],
         output_title: str, output_md: str, sources: str, steps: list[str] | None = None) -> str:
    if steps:
        charts_html = charts_html + [("How it works", "<ol class='out'>" + "".join(f"<li>{html.escape(x)}</li>" for x in steps) + "</ol>")]
    k = "".join(f'<div class="card kpi"><div class="s">{html.escape(s)}</div><div class="v">{html.escape(v)}</div>'
                f'<div class="l">{html.escape(l)}</div></div>' for s, v, l in kpis)
    c = "".join(f'<div class="card"><h3>{html.escape(t)}</h3>{h}</div>' for t, h in charts_html)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>
<style>{CSS}</style></head><body><div class="wrap">
<header><div><h1>{html.escape(title)}</h1><p class="sub">{html.escape(sub)}</p></div><span class="tag">{html.escape(tag)}</span></header>
<div class="grid g4">{k}</div><div class="grid g2" style="margin-top:14px">{c}</div>
<div class="card out" style="margin-top:14px"><h3>{html.escape(output_title)}</h3>{md_to_html(output_md)}</div>
<footer>{html.escape(sources)}<br>{FOOT}</footer></div></body></html>"""


def div(fig) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False, "responsive": True})


def pct(x) -> str:
    return f"{x*100:.0f}%"


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    A, B, C = (charts.load(f"outputs/eval/{s}.json") for s in "ABC")
    sa = charts.load("outputs/cx_pulse/run_summary.json")
    llm_a = A["llm"] if isinstance(A["llm"], dict) else None

    # ---- A
    kpis = [("TEST SET", f"{A['test_set']}", "real reviews labelled by hand (Portuguese)"),
            ("THEME ACCURACY", pct(llm_a["theme"]["accuracy"]) if llm_a else pct(A["rules"]["theme"]["accuracy"]),
             "AI model" if llm_a else "rules baseline · AI evaluation pending"),
            ("HIGH-SEVERITY RECALL", pct(llm_a["high_severity"]["recall"]) if llm_a else pct(A["rules"]["high_severity"]["recall"]),
             "serious complaints caught" + ("" if llm_a else " (rules)")),
            ("INVENTED NUMBERS", f"{sa['unsupported_numbers']}", f"in {sa['notes']} weekly notes ({sa['numbers_checked']} numbers checked)")]
    (DOCS / "dashboard_A.html").write_text(page(
        "CX Pulse: what customers complain about, week by week",
        f"{sa['reviews_classified']:,} real Olist reviews (Brazil, 2018) classified by theme and severity; the weekly note is written "
        f"from numbers computed by code and checked automatically. Mode of the last run: {sa['mode']}.",
        "PUBLIC DATA + AI", kpis,
        [("Share of sampled reviews by theme, per week", div(charts.a_theme_trend())),
         ("Latest week vs the 4 weeks before", div(charts.a_week_vs_before())),
         ("Evaluation on 100 hand-labelled reviews", div(charts.a_eval_bars()))],
        "Latest weekly notes (draft for human review)",
        (ROOT / "outputs/cx_pulse/weekly_notes.md").read_text(encoding="utf-8").split("\n---\n")[0],
        "Data: Olist Brazilian E-Commerce Public Dataset (CC BY-NC-SA 4.0), personal data masked before processing.",
        ["Mask personal data (e-mails, phones, tax IDs, names) before anything is stored or sent.",
         "Classify each review: one theme + one severity. AI model in batches of 25 with a fixed JSON schema; keyword rules without a key.",
         "SQL (DuckDB) computes theme shares per week and the change vs the 4 previous weeks.",
         "The note is written from that facts table only; every number is checked against it (target: 0 unsupported).",
         "A person reviews the draft and the list of high-severity reviews before Monday's meeting."]),
        encoding="utf-8")

    # ---- B
    sb = charts.load("outputs/competitor_watch/run_summary.json")
    bx = B["llm_extraction"] or B
    kpis = [("SNAPSHOTS", f"{B['snapshots']}", "dated pricing pages, 6 vendors, 2024-2026"),
            ("EXTRACTION F1", pct(bx["extraction"]["f1"]), "plan + list price pairs (" + ("AI model" if B["llm_extraction"] else "rules baseline · AI pending") + ")"),
            ("REAL CHANGES FOUND", f"{bx['change_detection']['detected']}/{bx['change_detection']['real_changes']}",
             f"{bx['change_detection']['false_alarms']} false alarms, each marked 'verify'"),
            ("PRICES INVENTED", f"{bx['extraction']['prices_invented_on_empty_pages']}", f"on {B['unreadable_in_truth']} pages that show no prices")]
    (DOCS / "dashboard_B.html").write_text(page(
        "Competitor Watch: only hear about real pricing changes",
        "Public pricing pages of Notion, Slack, Asana, Trello, ClickUp and Zapier, read from Wayback Machine snapshots. "
        f"Plans and prices extracted, compared period by period with guardrails for currency switches and unreadable pages. Mode: {sb['mode']}.",
        "PUBLIC DATA + AI", kpis,
        [("List price of plans that changed (from the labelled snapshots)", div(charts.b_price_steps())),
         ("Evaluation against reference labels", div(charts.b_extraction_bars()))],
        "Latest digest (draft for human review)",
        (ROOT / "outputs/competitor_watch/digest.md").read_text(encoding="utf-8"),
        "Data: public pricing pages via the Internet Archive Wayback Machine (snapshot list in data/public/pricing_snapshots.csv). "
        "Vendors are examples of public pricing only.",
        ["Collect dated snapshots of each pricing page (Wayback Machine, robots.txt checked, ~1 request / 2 s).",
         "Keep only the text around prices (plain code), then extract plans, list prices, promo prices and currency as JSON.",
         "Compare each snapshot with the previous readable one: price changed, plan added, plan not found, promo changed.",
         "Guardrails: a page without prices is 'unreadable' (never 'all plans removed'); a currency switch is 'not comparable'.",
         "Weekly digest of the latest changes, numbers checked against the extraction, links to evidence."]), encoding="utf-8")

    # ---- C
    sc = charts.load("outputs/client_report/run_summary.json")
    ad = C["anomaly_detection"]
    kpis = [("REPORTS CHECKED", f"{C['client_months']}", "fictional client-months (6 clients x 5 months)"),
            ("INVENTED NUMBERS", f"{C['unsupported_numbers']}", f"{C['numbers_checked']} numbers, all filled from the data"),
            ("DATA INCIDENTS FOUND", f"{ad['found']}/{ad['planted_events']}", "planted outages, spikes and promotions"),
            ("TYPED NUMBERS CAUGHT", f"{C['typed_number_stress']['caught']}/{C['typed_number_stress']['planted']}",
             "stress test: a writer typing a number is always flagged")]
    (DOCS / "dashboard_C.html").write_text(page(
        "Client reporting that never invents a number",
        "SIMULATED data for a fictional creator-marketing agency. The writer uses slots like {{revenue}}; code fills them from SQL "
        f"and flags tracking outages before they become 'sales dropped' in front of a client. Mode: {sc['mode']}.",
        "SIMULATED + AI", kpis,
        [("Example: an outage and a spike in one client's daily clicks", div(charts.c_anomaly_example())),
         ("October 2026 revenue by client (vs September)", div(charts.c_revenue_by_client()))],
        "Example report: Atelier Nord, October 2026 (draft for human review)",
        (ROOT / "outputs/client_report/C04_2026-10.md").read_text(encoding="utf-8"),
        "Data: simulated (seed 42), clients are fictional. Planted events are logged in data/simulated/events.csv "
        "and only used by the evaluation.",
        ["SQL builds a facts table per client and month: revenue, orders, conversion, paid ROAS, by source, vs last month.",
         "Code detects data incidents in daily data: tracking outages, traffic spikes, conversion jumps (Poisson test).",
         "The writer (AI model or template) produces sentences with slots such as {{revenue_change_pct}}, never digits.",
         "Code fills the slots; any unknown slot or typed digit marks the report NEEDS REVIEW.",
         "The account manager edits the words and sends. Nothing is sent automatically."]), encoding="utf-8")
    print("dashboards -> docs/dashboard_A.html, dashboard_B.html, dashboard_C.html")


if __name__ == "__main__":
    main()
