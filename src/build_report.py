"""Build the PDF report (docs/Hubs_AppliedAI_CaseStudy.pdf) and the product feedback memo.

    python src/build_report.py

1. Read every number from outputs/ (workflow runs + evaluations) and src/assumptions.py.
2. Render 11 landscape 16:9 pages as HTML (charts as static SVG from src/charts.py).
3. Print to PDF with headless Edge (or Chrome), then blank the PDF metadata.
4. Write docs/PRODUCT_FEEDBACK_MEMO.md from the same numbers.
"""
from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
import assumptions as AS  # noqa: E402
import charts  # noqa: E402

DOCS, BUILD = ROOT / "docs", ROOT / "outputs" / "report"
FOOT = "Independent case study based on public information · not affiliated with or endorsed by Hubs"
# The AI-use note is written once, in the README "Methods" section, and copied into the PDF from there.
README_TEXT = (ROOT / "README.md").read_text(encoding="utf-8")
AI_NOTE = README_TEXT.split("## Methods", 1)[1].strip().splitlines()[0].strip()


# ------------------------------------------------------------------ numbers
def load_numbers() -> dict:
    j = lambda p: json.loads((ROOT / p).read_text(encoding="utf-8"))  # noqa: E731
    A, B, C = j("outputs/eval/A.json"), j("outputs/eval/B.json"), j("outputs/eval/C.json")
    ra, rb, rc = (j(f"outputs/{w}/run_summary.json") for w in ("cx_pulse", "competitor_watch", "client_report"))
    llm_a = A["llm"] if isinstance(A["llm"], dict) else None
    ai = A["mode"] == "llm"
    n = {"A": A, "B": B, "C": C, "ra": ra, "rb": rb, "rc": rc, "ai": ai, "llm_a": llm_a,
         "time": AS.weekly_minutes()}
    a_acc = llm_a["theme"]["accuracy"] if llm_a else A["rules"]["theme"]["accuracy"]
    bx = B["llm_extraction"] or B  # AI results when available, else the rules baseline
    n["bx"] = bx
    n["avg_acc"] = round((a_acc + bx["extraction"]["f1"] + C["anomaly_detection"]["recall"]) / 3, 3)
    n["invented"] = ra["unsupported_numbers"] + rb["unsupported_numbers"] + C["unsupported_numbers"]
    n["numbers_checked"] = ra["numbers_checked"] + rb["numbers_checked"] + C["numbers_checked"]
    n["cost"] = weekly_cost(n)
    return n


def weekly_cost(n: dict) -> dict:
    """Measured cost per weekly cycle when runs used the model; otherwise a clearly labelled estimate."""
    from workflows.common import llm
    if n["ai"]:
        weekly = n["ra"]["cost_usd"] / max(1, n["ra"]["weeks"]) + n["rb"]["cost_usd"] / 1 + n["rc"]["cost_usd"] / (52 / 12)
        return {"usd": round(weekly, 3), "kind": "measured"}
    import pandas as pd
    from workflows.cx_pulse.pipeline import SYSTEM_CLASSIFY, SYSTEM_NOTE
    from workflows.competitor_watch.pipeline import SYSTEM_EXTRACT, SYSTEM_DIGEST
    from workflows.competitor_watch.textprep import price_excerpt
    from workflows.client_report.pipeline import SYSTEM as SYSTEM_C
    sample = pd.read_csv(ROOT / "data/public/reviews_sample.csv")
    week = sample[sample.week_start == sample.week_start.max()]
    a_in = (len(SYSTEM_CLASSIFY) * 6 + week.text.str.len().sum() + 80 * len(week) + len(SYSTEM_NOTE) + 3000) / AS.CHARS_PER_TOKEN
    a_out = 45 * len(week) + 400
    snaps = pd.read_csv(ROOT / "data/public/pricing_snapshots.csv", dtype={"timestamp": str})
    latest = snaps.sort_values("timestamp").groupby("vendor").tail(1)
    ex_chars = sum(len(price_excerpt((ROOT / f"data/raw/wayback/{r.vendor}_{r.timestamp}.txt").read_text(encoding="utf-8")))
                   for r in latest.itertuples() if (ROOT / f"data/raw/wayback/{r.vendor}_{r.timestamp}.txt").exists())
    b_in = (ex_chars + 6 * len(SYSTEM_EXTRACT) + len(SYSTEM_DIGEST) + 2000) / AS.CHARS_PER_TOKEN
    b_out = 6 * 250 + 300
    facts = json.loads((ROOT / "outputs/client_report/facts_2026-10.json").read_text(encoding="utf-8"))
    c_in = (sum(len(json.dumps(f)) * 2 for f in facts) + 6 * len(SYSTEM_C)) / AS.CHARS_PER_TOKEN / (52 / 12)
    c_out = 6 * 600 / (52 / 12)
    tin, tout = a_in + b_in + c_in, (a_out + b_out + c_out) * 1.5  # +50% margin for the model's short thinking
    return {"usd": round(llm.cost_usd(tin, tout), 3), "kind": "estimate", "tokens_in": int(tin), "tokens_out": int(tout)}


def pct(x: float, nd: int = 0) -> str:
    return f"{x*100:.{nd}f}%"


# ------------------------------------------------------------------ HTML helpers
CSS = """
@page { size: 13.333in 7.5in; margin: 0 }
* { box-sizing: border-box }
html, body { margin: 0; padding: 0 }
body { font-family: "Segoe UI", Arial, sans-serif; color: #0B0B0B; background: #F4F4F2; -webkit-print-color-adjust: exact; print-color-adjust: exact }
.page { width: 13.333in; height: 7.5in; padding: 30px 42px 26px; position: relative; overflow: hidden; page-break-after: always; background: #F4F4F2 }
.page:last-child { page-break-after: auto }
h1 { font-size: 25px; margin: 0 0 6px; font-weight: 700; max-width: 1040px; line-height: 1.2 }
.sub { color: #52514E; font-size: 13.5px; margin: 0 0 16px; max-width: 1040px; line-height: 1.4 }
.tag { position: absolute; top: 32px; right: 42px; font-size: 11px; font-weight: 600; letter-spacing: .07em; color: #52514E }
.foot { position: absolute; bottom: 14px; left: 42px; right: 42px; font-size: 9.5px; color: #898781; display: flex; justify-content: space-between; gap: 20px }
.grid { display: grid; gap: 12px }
.card { background: #FCFCFB; border: 1px solid #E1E0D9; border-radius: 8px; padding: 13px 16px; overflow: hidden }
.card h3 { font-size: 13.5px; margin: 0 0 7px; font-weight: 700 }
.card p, .card li { font-size: 12px; line-height: 1.42; color: #2b2a28; margin: 0 0 5px }
.card ul, .card ol { margin: 0; padding-left: 17px }
.small { font-size: 10.5px !important; color: #52514E !important }
.kpi .s { font-size: 10px; font-weight: 600; letter-spacing: .06em; color: #898781; margin-bottom: 4px }
.kpi .v { font-size: 34px; font-weight: 700; line-height: 1.05 }
.kpi .l { font-size: 12px; color: #52514E; margin-top: 4px; line-height: 1.35 }
.muted { color: #898781 } .blue { color: #2A78D6 } .red { color: #D03B3B }
.quote { font-size: 14px; line-height: 1.35; font-weight: 600; margin: 0 0 4px }
table { border-collapse: collapse; width: 100%; font-size: 11.2px }
th { text-align: left; color: #52514E; font-weight: 600; border-bottom: 1px solid #E1E0D9; padding: 4px 6px }
td { border-bottom: 1px solid #EEEDE8; padding: 4px 6px; vertical-align: top; color: #2b2a28 }
.chart svg { width: 100%; height: auto; display: block }
.pill { display: inline-block; font-size: 10px; font-weight: 600; letter-spacing: .05em; color: #52514E; border: 1px solid #E1E0D9; border-radius: 5px; padding: 1px 6px; margin-right: 4px }
.flow { display: flex; gap: 10px; align-items: stretch }
.flow .card { flex: 1 }
.arrow { align-self: center; color: #898781; font-size: 20px }
.out { font-family: "Segoe UI", Arial, sans-serif; font-size: 11px; line-height: 1.4; background: #F7F6F3; border-radius: 6px; padding: 8px 10px; color: #2b2a28 }
"""


def page(title: str, sub: str, tag: str, body: str, foot: str, num: int) -> str:
    return (f'<section class="page"><div class="tag">{html.escape(tag)}</div><h1>{html.escape(title)}</h1>'
            f'<p class="sub">{html.escape(sub)}</p>{body}<div class="foot"><span>{html.escape(foot)}</span>'
            f'<span>{html.escape(FOOT)} · {num}</span></div></section>')


def card(title: str, inner: str, style: str = "") -> str:
    return f'<div class="card" style="{style}"><h3>{html.escape(title)}</h3>{inner}</div>'


def kpi(s: str, v: str, l: str) -> str:
    return f'<div class="card kpi"><div class="s">{html.escape(s)}</div><div class="v">{v}</div><div class="l">{l}</div></div>'


def ul(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def chart(fig, width=520) -> str:
    return f'<div class="chart">{charts.svg(fig, width)}</div>'


def esc(s: str) -> str:
    return html.escape(s)


# ------------------------------------------------------------------ pages
def build_pages(n: dict) -> list[str]:
    A, B, C, T = n["A"], n["B"], n["C"], n["time"]
    ai, la = n["ai"], n["llm_a"]
    mode_word = "AI model" if ai else "rules baseline (AI evaluation pending: no API key during this run)"
    pages = []

    # 0 Overview
    acc_label = ("mean of three test-set scores: A theme accuracy, B price extraction F1, C incident recall"
                 + ("" if ai else ". Demo mode: rules baseline, AI evaluation pending"))
    cost = n["cost"]
    cost_v = f"${cost['usd']:.3f}" if cost["usd"] >= 0.001 else "<$0.001"
    body = (f'<div class="grid" style="grid-template-columns:repeat(4,1fr)">'
            + kpi("ACCURACY · TEST SETS", pct(n["avg_acc"]), esc(acc_label))
            + kpi("INVENTED NUMBERS", f'{n["invented"]}', f'in every generated note, digest and report ({n["numbers_checked"]} numbers checked automatically)')
            + kpi("TIME SAVED", f'~{T["total_saved_hours_per_week"]} h', "per week across the three workflows (manual times are assumptions, see Methods)")
            + kpi("COST PER WEEK", cost_v, ("measured API cost of one weekly cycle" if cost["kind"] == "measured"
                                            else f"estimated API cost of one weekly cycle ({cost['tokens_in']:,} input tokens), to be measured"))
            + "</div>")
    body += ('<div class="grid" style="grid-template-columns:1.25fr 1fr;margin-top:12px">'
             + card("Three customer problems, three AI solutions", ul([
                 "<b class='blue'>A · CX Pulse</b> &nbsp;An e-commerce team drowns in reviews. <i>Solution:</i> classify real reviews by theme and severity, weekly note on what got worse. <span class='pill'>PUBLIC DATA</span>",
                 "<b class='blue'>B · Competitor Watch</b> &nbsp;A SaaS founder misses competitors' pricing moves. <i>Solution:</i> extract plans and prices from real pricing pages, report only real changes. <span class='pill'>PUBLIC DATA</span>",
                 "<b class='blue'>C · Client reporting</b> &nbsp;An agency spends a day a month on reports. <i>Solution:</i> reports where the model never types a number and data incidents are flagged. <span class='pill'>SIMULATED</span>",
             ]) + "<p class='small' style='margin-top:6px'>The three agents mirror those shown on Hubs' public site (CX Pulse, Competitor Watch, Proposal Gen / Reports). Customers are fictional; data is real public data or labelled simulated.</p>")
             + card("The method, applied to each scenario", ul([
                 "<b>Discovery</b>: the right questions, the real problem behind the request, a success metric.",
                 "<b>Solution</b>: Python + SQL (DuckDB) + one small model with schema-enforced JSON.",
                 "<b>Evaluation</b>: hand-labelled test sets, invented-number check, cost and time.",
                 "<b>Reuse</b>: what to parameterise so another team can run it (Hubs' 'Spread').",
                 "<b>Product feedback</b>: what building it taught me about what a platform like Hubs needs.",
             ]))
             + "</div>")
    body += ('<div class="card" style="margin-top:12px"><h3>How to read this report</h3><p><b>Titles</b> state the conclusion. '
             '<b>Tags</b> (PUBLIC DATA / SIMULATED / + AI) say where the data comes from. <b>Blue</b> = data in focus, grey = comparison, '
             '<b>red</b> = errors and alerts, dashed lines = targets. Every number comes from a script or an evaluation in the repository. '
             f'Mode of this build: <b>{esc(mode_word)}</b>.</p></div>')
    pages.append(page("Hubs: three customer problems, three AI solutions, measured",
                      "How I would run discovery, build reusable AI workflows on real data, prove they work, and turn what I learn into product feedback.",
                      "OVERVIEW", body, "Sources: data/SOURCES.md · Assumptions: data/ASSUMPTIONS.md", 1))

    # 1 What Hubs is building
    body = ('<div class="grid" style="grid-template-columns:1fr 1fr 1fr">'
            + card("The problem, in Hubs' words", "".join(f'<p class="quote">"{q}"</p>' for q in [
                "My team uses AI every day. But our business doesn't get smarter from it.",
                "Our best people have figured out incredible AI workflows. Nobody else knows they exist.",
                "I don't need another chatbot. I need AI that knows our business."]) + "<p class='small'>hubs.is, home page, read 2026-11-14</p>")
            + card("The model: Build → Spread → Scale", ul([
                "<b>Build</b>: someone sees an opportunity and acts on it (one prompt, one data source, one workflow).",
                "<b>Spread</b>: when something works, it is reused, adapted, connected.",
                "<b>Scale</b>: when something is proven, it becomes a reusable agent.",
                "Product pieces described publicly: an Agentic Workspace, a Network (what's hot, happening, changed, next), "
                "Spark (the creation agent), building blocks (information, intelligence, automation, action)."]))
            + card("Agents shown on the public site", ul([
                "Home: <b>Proposal Gen</b>, <b>Risk Monitor</b>, <b>CX Pulse</b>, Reports.",
                "Workspace demo: Risk Analysis, <b>Client Reporting</b>, Proposal Generator, <b>Competitor Watch</b>, Client Health, Deal Sourcing.",
                "Solutions page: 8 core patterns, incl. Competitor Watch ('you only hear about it when something actually shifts').",
                "SMB page: design partners get hands-on onboarding: 'We build your first hub with you.'"]))
            + "</div>")
    body += ('<div class="grid" style="grid-template-columns:1fr 1fr;margin-top:12px">'
             + card("What this implies for the Applied AI Product Associate role", ul([
                 "The first hub at each customer decides whether the rest spreads: it must solve a real problem and be <b>trusted</b>.",
                 "Trust needs proof: a small test set and visible checks, not a demo that looks right.",
                 "Each implementation is also research: what customers struggle with is product feedback for the San Francisco team.",
                 "European and Latin American customers: the careers page lists Forward Deployed roles asking for French or Spanish/Portuguese."]))
             + card("Why these three scenarios", ul([
                 "<b>CX Pulse</b> and <b>Competitor Watch</b> are named agents on the site; <b>Client Reporting</b> and Proposal Gen match the professional-services focus of the SMB page.",
                 "Each one stresses a different risk: classification quality (A), messy external sources (B), invented numbers (C).",
                 "All three are 'monitor and report' patterns that run on a schedule, the kind Hubs says agents should do 'even while you sleep'."]))
             + "</div>")
    pages.append(page("Hubs sells AI that compounds inside a company; the first hub has to be trusted",
                      "What Hubs says publicly about the problem, its model and its agents, and what that means for someone who implements solutions with its customers.",
                      "PUBLIC DATA", body, "Source: hubs.is (home, product, solutions, SMB, partners, careers, vision), read 2026-11-14. No product access was used.", 2))

    # 2 Discovery
    body = ('<div class="grid" style="grid-template-columns:1.15fr 1fr 1fr">'
            + card("The questions I ask", ul([
                "<b>The job</b>: 'Walk me through the last time you did this. What did you open first?'",
                "<b>The decision</b>: 'If this existed tomorrow, what would you decide differently?'",
                "<b>Today's cost</b>: 'How long does it take? When did it last go wrong, and what did it cost?'",
                "<b>Success</b>: 'What would make you say in four weeks: this works?'",
                "<b>Errors</b>: 'Which mistake is acceptable, and which is not acceptable at all?'",
                "<b>Data and trust</b>: 'What must never leave the company? Who checks before it is sent?'",
                "<b>Spread</b>: 'Who else does something similar? What would they change?'"]))
            + card("Finding the real problem", "<table><tr><th>They say</th><th>I ask</th></tr>"
                   "<tr><td>'We need AI for X'</td><td>What happens today when X goes wrong?</td></tr>"
                   "<tr><td>'Summarise our reviews'</td><td>What decision does the summary feed?</td></tr>"
                   "<tr><td>'The numbers are off'</td><td>Off compared to what? Who computes the other number?</td></tr>"
                   "<tr><td>'Our best person does it'</td><td>What would it take for someone else to do it next week?</td></tr>"
                   "<tr><td>'Watch everything'</td><td>Which change would make you act?</td></tr></table>")
            + card("What I leave the call with", ul([
                "The problem in their words, and the real problem in mine.",
                "One success metric they agree on, and the error they fear most.",
                "Where the data lives, how fresh it must be, what must be masked.",
                "A plan for 30-100 examples to label together: <b>no test set, no launch</b>.",
                "A separate note of product feedback for the product team."]))
            + "</div>")
    body += ('<div class="card" style="margin-top:12px"><h3>Applied to the three scenarios</h3><table>'
             "<tr><th></th><th>What they asked</th><th>The real problem</th><th>Success metric agreed</th></tr>"
             "<tr><td><b>A</b></td><td>'An AI that summarises our reviews'</td><td>Every Monday: which problem grew, how big, which orders need action today</td><td>≥ 90% recall on high-severity reviews; 0 invented numbers</td></tr>"
             "<tr><td><b>B</b></td><td>'An agent that watches everything competitors do'</td><td>Know within a week when list prices or plans change, never be told a fake change</td><td>Extraction F1 ≥ 0.95; every real change found; 0 invented prices</td></tr>"
             "<tr><td><b>C</b></td><td>'Can AI write our client reports?'</td><td>A correct first draft in minutes; data incidents flagged before a client sees them</td><td>0 invented numbers; every outage and spike flagged</td></tr>"
             "</table><p class='small' style='margin-top:6px'>Customers are fictional. Full notes: discovery/DISCOVERY_GUIDE.md and scenario_A/B/C_notes.md.</p></div>")
    pages.append(page("Discovery turns 'we want an AI agent' into a decision, a metric and a test set",
                      "My interview guide, built from onboarding agencies onto an analytics product: the questions, how to find the real problem, and what 'working' means before anything is built.",
                      "METHOD", body, "discovery/DISCOVERY_GUIDE.md", 3))

    # 3 Scenario A
    ra = n["ra"]
    stress = A["number_check_stress"]
    a_rules = A["rules"]
    a_metric = (f"AI model: theme accuracy {pct(la['theme']['accuracy'])}, high-severity recall {pct(la['high_severity']['recall'])}, "
                f"cost ${la['usage']['cost_usd']} for 100 reviews." if la else
                f"Rules baseline: theme accuracy {pct(a_rules['theme']['accuracy'])}, high-severity recall "
                f"{pct(a_rules['high_severity']['recall'])}. AI model: evaluation pending (same test set, one command).")
    note = (ROOT / "outputs/cx_pulse/weekly_notes.md").read_text(encoding="utf-8").split("\n---\n")[0]
    note_lines = [l for l in note.splitlines() if l.strip() and not l.startswith("##")][:9]
    last = json.loads((ROOT / "outputs/cx_pulse/facts.json").read_text(encoding="utf-8"))[-1]
    grew = last["most_worsened"][0] if last["most_worsened"] else last["top_issue"]
    grew_label = charts.LABEL[grew]
    body = ('<div class="grid" style="grid-template-columns:1fr 1fr 0.9fr">'
            + card(f"'{grew_label}' grew most in the latest week (+{last['themes'][grew]['change_pts']} pts)",
                   chart(charts.a_week_vs_before(), 500))
            + card("Theme share per week (sampled reviews with text)", chart(charts.a_theme_trend(), 500))
            + card("Discovery → solution", ul([
                "<b>Real problem</b>: what got worse vs usual, and which orders need action today.",
                f"<b>Data</b>: {ra['reviews_classified']:,} real Olist reviews over 8 weeks (150 per week, Portuguese), personal data masked first.",
                "<b>Solution</b>: theme + severity per review (batches of 25, JSON schema), SQL weekly shares, note written from a facts table.",
                "<b>Guardrail</b>: the low-volume week is flagged 'not comparable' instead of 'complaints fell'."]))
            + "</div>")
    body += ('<div class="grid" style="grid-template-columns:0.9fr 1.1fr 1fr;margin-top:12px">'
             + card("Evaluation (100 hand-labelled reviews)", chart(charts.a_eval_bars(), 440))
             + card("Weekly note produced (draft for human review)", "<div class='out'>" + "<br>".join(esc(l.replace("**", "")) for l in note_lines) + "</div>")
             + card("What the numbers say", ul([
                 esc(a_metric),
                 f"Invented numbers in the {ra['notes']} weekly notes: <b>{ra['unsupported_numbers']}</b> ({ra['numbers_checked']} checked).",
                 f"Stress test of the number check: {stress['planted_errors_caught']}/{stress['planted_errors']} planted errors caught. "
                 f"The {stress['missed_collisions']} missed ones were real numbers put in the wrong place, which a value check cannot see: "
                 "one reason scenario C uses slots.",
                 "Rules miss 'seller service' and 'wrong item' wording most: the model should beat them where wording varies."]))
             + "</div>")
    pages.append(page(f"A · CX Pulse: '{grew_label.lower()}' complaints rose in the latest week, and the note proves it",
                      "Fictional customer, real public reviews. Each review gets a theme and a severity; the weekly note only uses numbers computed by code.",
                      "PUBLIC DATA + AI", body, "Data: Olist Brazilian E-Commerce Public Dataset (CC BY-NC-SA 4.0). Test set labelled by reading each review, before running the workflow.", 4))

    # 4 Scenario B
    cd, ex = n["bx"]["change_detection"], n["bx"]["extraction"]
    rb = n["rb"]
    digest = (ROOT / "outputs/competitor_watch/digest.md").read_text(encoding="utf-8").splitlines()
    dl = [l for l in digest if l.startswith("- ") or l.startswith("**")][:2]
    body = ('<div class="grid" style="grid-template-columns:1.1fr 0.9fr 0.9fr">'
            + card("Three real pricing moves in two years of snapshots", chart(charts.b_price_steps(), 540))
            + card("Discovery → solution", ul([
                "<b>Real problem</b>: list prices and plan structure, dated, with evidence, never a fake change.",
                f"<b>Data</b>: {B['snapshots']} dated snapshots of 6 public pricing pages (Wayback Machine, robots.txt checked).",
                "<b>Solution</b>: price-focused excerpt (code) → plans, list price, promo price, currency as JSON → period-by-period diff → digest.",
                "<b>List vs promo</b>: '50% off for 3 months' and 'Regular price' are separated, as asked in discovery."]))
            + card("Traps found while building (now guardrails)", ul([
                f"<b>{B['unreadable_in_truth']} of {B['snapshots']} pages show no prices</b> in their static HTML (script-rendered). A naive diff says 'all plans removed'. Here: 'unreadable, skipped'.",
                "<b>Currency</b>: one Notion snapshot was archived in euros. A naive diff says 'Plus went from 9.50 to 10'. Here: 'not comparable, check'.",
                "<b>Renames</b>: Zapier went Professional → Pro → Professional; flagged as 'plan not found, verify'."]))
            + "</div>")
    body += ('<div class="grid" style="grid-template-columns:0.9fr 1.1fr 1fr;margin-top:12px">'
             + card("Evaluation against reference labels", chart(charts.b_extraction_bars(), 440))
             + card("Latest digest (draft)", "<div class='out'>" + "<br>".join(esc(l.replace("**", "").lstrip("- ")) for l in dl) + "</div>")
             + card("What the numbers say", ul([
                 f"Plan + price extraction ({mode_word.split(' (')[0]}): precision {pct(ex['precision'])}, recall {pct(ex['recall'])}; "
                 f"{ex['snapshots_exact']}/{B['snapshots']} snapshots exactly right; promo prices found {ex['promo_prices_found']}.",
                 f"Prices invented on pages that show none: <b>{ex['prices_invented_on_empty_pages']}</b>.",
                 f"Real changes detected: <b>{cd['detected']}/{cd['real_changes']}</b>; false alarms: {cd['false_alarms']} "
                 "(a ClickUp savings calculator read as plans, and a late rename), each marked 'verify'.",
                 f"Digest numbers checked: {rb['numbers_checked']}, unsupported: {rb['unsupported_numbers']}."]))
             + "</div>")
    pages.append(page(f"B · Competitor Watch: {cd['detected']} of {cd['real_changes']} real pricing moves found; currency and broken-page traps filtered out",
                      "Fictional customer, real public pricing pages. Zapier repriced and renamed plans, Notion raised Business, ClickUp repackaged everything in 2026.",
                      "PUBLIC DATA + AI", body, "Data: public pricing pages via the Internet Archive Wayback Machine (data/public/pricing_snapshots.csv). Vendors are examples only.", 5))

    # 5 Scenario C
    ad = C["anomaly_detection"]
    rep = (ROOT / "outputs/client_report/C04_2026-10.md").read_text(encoding="utf-8").splitlines()
    rep_lines = [l for l in rep if l.strip() and not l.startswith("#") and not l.startswith("_")][:8]
    sf = C["number_check_stress_final_text"]
    body = ('<div class="grid" style="grid-template-columns:1.1fr 0.9fr 0.9fr">'
            + card("A tracking outage is flagged as a data problem, not a sales drop", chart(charts.c_anomaly_example(), 540))
            + card("Discovery → solution", ul([
                "<b>Real problem</b>: a correct first draft in minutes; never a wrong number in front of a client.",
                "<b>Data</b>: SIMULATED daily clicks, orders, revenue and spend for 6 fictional creator brands, 5 sources, May-Oct 2026.",
                "<b>Solution</b>: SQL facts per client-month → incident detection in code → the writer uses <b>slots</b> like {{revenue_change_pct}} → code fills them → checks.",
                "<b>Proposal</b>: each report ends with a plan for next month, grounded in the same facts."]))
            + card("Example report (draft)", "<div class='out'>" + "<br>".join(esc(l.lstrip("- ")) for l in rep_lines) + "</div>")
            + "</div>")
    body += ('<div class="grid" style="grid-template-columns:repeat(4,1fr);margin-top:12px">'
             + kpi("INVENTED NUMBERS", f"{C['unsupported_numbers']}", f"in {C['client_months']} client-month reports, {C['numbers_checked']} numbers filled from the data")
             + kpi("TYPED NUMBERS CAUGHT", f"{C['typed_number_stress']['caught']}/{C['typed_number_stress']['planted']}", "stress test: a writer that types a digit instead of a slot is always flagged")
             + kpi("INCIDENTS FOUND", f"{ad['found']}/{ad['planted_events']}",
                   f"outages {pct(ad['recall_by_type'].get('tracking_outage', 0))}, spikes {pct(ad['recall_by_type'].get('viral_spike', 0))}, "
                   f"promotions {pct(ad['recall_by_type'].get('price_promo', 0))}; {ad['false_alarms']} false alarms")
             + kpi("WRONG NUMBERS CAUGHT", f"{sf['planted_errors_caught']}/{sf['planted_errors']}", "planted in final reports; misses are true numbers in the wrong place")
             + "</div>")
    fa = ad.get("false_alarms_by_kind", {})
    fa_txt = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in fa.items()) or "none"
    body += ('<div class="grid" style="grid-template-columns:1fr 1fr;margin-top:12px">'
             + card("Why slots, and not only a check", ul([
                 "A check after writing proves a number exists in the data, not that it describes the right thing.",
                 "With slots, a number can only enter the text through a named fact (<code>{{orders}}</code>), which a reviewer can read.",
                 "Result: the writer's freedom is in the words; the numbers are the code's job."]))
             + card("What is still hard", ul([
                 f"Promotions (+40% conversion for a week) are subtle: {pct(ad['recall_by_type'].get('price_promo', 0))} found; most sit on low-volume sources.",
                 f"False alarms: {fa_txt}. They appear as 'data notes' for the account manager to confirm, never as conclusions.",
                 "Thresholds were tuned on a separate simulation (seed 7) to avoid fitting the test data."]))
             + "</div>")
    pages.append(page("C · Client reporting: the model never types a number, so it cannot invent one",
                      "Fictional agency, SIMULATED data. Numbers come from SQL through slots; outages and spikes are detected in code and explained in the report.",
                      "SIMULATED + AI", body, "Data: simulated (seed 42). Planted events (data/simulated/events.csv) are the ground truth and are never read by the workflow. Detector thresholds tuned on a separate seed.", 6))

    # 6 Measured, not assumed
    la_row = (f"{pct(la['theme']['accuracy'])} theme · {pct(la['high_severity']['recall'])} high-sev. recall" if la else "pending (no API key)")
    body = ('<div class="card"><h3>Evaluation grid: same questions for every workflow</h3><table>'
            "<tr><th>Workflow</th><th>Test set</th><th>Rules baseline</th><th>AI model</th><th>Invented numbers</th><th>Cost / run</th><th>Time / week: manual → with workflow</th><th>Main limit</th></tr>"
            f"<tr><td><b>A · CX Pulse</b></td><td>100 real reviews, hand-labelled</td><td>{pct(a_rules['theme']['accuracy'])} theme · {pct(a_rules['high_severity']['recall'])} high-sev. recall</td><td>{la_row}</td>"
            f"<td>{ra['unsupported_numbers']} / {ra['numbers_checked']}</td><td>{'$'+str(ra['cost_usd']) if ai else 'estimate in Overview'}</td><td>{T['A']['manual']} → {T['A']['with_workflow']} min</td><td>One labeller; 8 themes; value check misses misplaced true numbers</td></tr>"
            f"<tr><td><b>B · Competitor Watch</b></td><td>{B['snapshots']} snapshots, 105 plan-price pairs; 28 periods</td><td>F1 {pct(B['extraction']['f1'])} · {B['change_detection']['detected']}/{B['change_detection']['real_changes']} changes</td>"
            f"<td>{(pct(B['llm_extraction']['extraction']['f1']) + ' F1 · ' + str(B['llm_extraction']['change_detection']['detected']) + '/' + str(B['llm_extraction']['change_detection']['real_changes']) + ' changes') if B['llm_extraction'] else 'pending (no API key)'}</td><td>{rb['unsupported_numbers']} / {rb['numbers_checked']}</td><td>{'$'+str(rb['cost_usd']) if ai else 'estimate in Overview'}</td><td>{T['B']['manual']} → {T['B']['with_workflow']} min</td><td>Script-rendered pages need a browser fetch; only 5 real changes</td></tr>"
            f"<tr><td><b>C · Client report</b></td><td>30 client-months, 27 planted incidents</td><td>Template writer: {C['reports_passing_checks']}/{C['client_months']} pass</td>"
            f"<td>{str(C['reports_passing_checks'])+'/'+str(C['client_months'])+' pass' if C['mode']=='llm' else 'pending (no API key)'}</td><td>{C['unsupported_numbers']} / {C['numbers_checked']}</td><td>{'$'+str(C['usage']['cost_usd']) if C['mode']=='llm' else 'estimate in Overview'}</td><td>{T['C']['manual']} → {T['C']['with_workflow']} min</td><td>Simulated data; promotions are hard to detect ({pct(ad['recall_by_type'].get('price_promo', 0))})</td></tr>"
            "</table></div>")
    body += ('<div class="grid" style="grid-template-columns:1fr 1fr 1fr;margin-top:12px">'
             + card("How accuracy is measured", ul([
                 "Reference labels are written by reading each source, before and independently of the workflow.",
                 "The critical class gets its own metric (high-severity recall, real changes found), not just overall accuracy.",
                 "Rules are kept as a baseline: the model must earn its cost against them."]))
             + card("How 'zero invented numbers' is proved", ul([
                 "Every number in every generated text is compared with the facts the code computed.",
                 f"The check itself is tested: wrong numbers are planted ({stress['planted_errors']} in A, {sf['planted_errors']} in C) to measure what it catches.",
                 "What it cannot see (a true number in the wrong place) is why C fills numbers through named slots and a person reviews every draft."]))
             + card("Cost and time", chart(charts.time_saved(), 440) + ul([
                 f"One small model ({'measured' if ai else 'estimated'}: {cost_v} per weekly cycle for all three workflows).",
                 "Workflow time is measured by the scripts; manual times are assumptions written in data/ASSUMPTIONS.md (e.g. 20 s to tag a review, 45 min per client report).",
                 f"Net: about {T['total_saved_hours_per_week']} hours per week, before counting what manual work misses (3-5 star reviews, old snapshots)."]))
             + "</div>")
    pages.append(page("Measured, not assumed: every claim has a test set, a check or a stated assumption",
                      "The same evaluation grid for the three workflows: accuracy against labels, invented numbers, cost, time saved, and the limits that remain.",
                      "EVALUATION", body, "outputs/eval/A.json, B.json, C.json · src/evaluate.py · src/assumptions.py", 7))

    # 7 Reuse
    body = ('<div class="card"><h3>From one solution to a reusable agent: what another team changes, and what stays</h3><table>'
            "<tr><th></th><th>Parameters another team sets</th><th>Inputs → outputs (fixed contract)</th><th>Reuse examples</th><th>Known limits to document</th></tr>"
            "<tr><td><b>A · CX Pulse</b></td><td>Theme list + definitions, severity rules, language, sample size, alert threshold</td><td>Text + rating + date → theme, severity, paraphrase (JSON) → weekly facts → note</td><td>Support tickets, NPS verbatims, app-store reviews, sales call notes</td><td>Needs ~100 labelled examples per new taxonomy; low-volume weeks</td></tr>"
            "<tr><td><b>B · Competitor Watch</b></td><td>URLs, change types that matter, list vs promo rule, currency, frequency</td><td>Page text → plans/prices (JSON) → period diff with guardrails → digest</td><td>Changelogs, job posts, marketplace listings, a client's own price list</td><td>Script-rendered pages; locale; renamed plans need a human</td></tr>"
            "<tr><td><b>C · Client report</b></td><td>Metrics and slots, sections, tone, incident thresholds, client list</td><td>Daily data → SQL facts → incidents → slotted text → filled, checked report</td><td>QBR decks, weekly creator check-ins, investor updates, proposals</td><td>Slots limit phrasing; thresholds tuned per data volume</td></tr>"
            "</table></div>")
    body += ('<div class="grid" style="grid-template-columns:1fr 1fr 1fr;margin-top:12px">'
             + card("What makes a workflow spreadable", ul([
                 "A one-paragraph purpose and a fixed input/output contract.",
                 "Parameters separated from logic (taxonomy, URLs, slots are data, not code).",
                 "Its test set travels with it: a new team re-runs the evaluation on 30 of its own examples before trusting it.",
                 "Guardrails on by default: masking, number check, human review."]))
             + card("How I would measure reuse", ul([
                 "Hubs created per week, and the share run by someone other than their creator.",
                 "Forks / adaptations per hub, and whether forks keep passing their tests.",
                 "Active agents: scheduled runs that succeed; runs that end in 'needs review'.",
                 "Time saved per run (measured once, then tracked) and drafts sent with few edits."]))
             + card("In this repository", ul([
                 "One command per workflow: <code>python -m workflows run --scenario A|B|C</code>.",
                 "Demo mode without an API key (rules + templates), same outputs and checks.",
                 "Each workflow folder: pipeline, prompts, schema, rules baseline, evaluation.",
                 "Test sets in data/eval; evaluations in src/evaluate.py."]))
             + "</div>")
    pages.append(page("From one solution to a reusable agent: parameters, contract, test set",
                      "Hubs' 'Spread' step needs more than a shared link. Each workflow here is split into what another team configures and what stays fixed.",
                      "REUSE", body, "workflows/ · data/eval/", 8))

    # 8 Product feedback
    body = ('<div class="grid" style="grid-template-columns:1fr 1fr">'
            + card("Recurring customer needs seen in the three builds", ul([
                "<b>Numbers people can trust</b>: the first wrong number ends adoption (all three).",
                "<b>Proof before sharing</b>: 'does it work on <i>my</i> data?' needs a test set, not a demo.",
                "<b>'What changed'</b> over time, not a one-off answer (A weekly trend, B diffs, C vs last month): it matches Hubs' 'What's changed' in the Network.",
                "<b>Data guardrails</b>: personal data masked, unreadable sources and incidents flagged, a human approves."]))
            + card("Likely friction points (hypotheses)", ul([
                "Labelling the first 30-100 examples is the step people skip; without it nobody knows if a hub works.",
                "External sources break silently (script-rendered pages, currency, renamed plans).",
                "Forked hubs drift: the copy no longer matches the original's tests.",
                "Cost and latency are invisible to the builder until they matter."]))
            + "</div>")
    body += ('<div class="card" style="margin-top:12px"><h3>Three ideas, prioritised (hypotheses to validate with customers)</h3><table>'
             "<tr><th>#</th><th>Idea</th><th>Why (from the builds)</th><th>How to validate</th><th>Metric</th></tr>"
             f"<tr><td><b>1</b></td><td><b>Verified numbers</b>: generated text cites numbers through slots linked to a data cell; a badge shows 'all numbers verified'</td><td>Slots gave {C['unsupported_numbers']} invented numbers in {C['client_months']} reports; a value-only check caught {pct(stress['catch_rate'])} of planted errors in A</td><td>5 design-partner interviews: 'what stops you from sending an AI draft to a client?'</td><td>Share of drafts sent with no number edits</td></tr>"
             "<tr><td><b>2</b></td><td><b>Test kit per hub</b>: label 30 examples in the UI, see accuracy on the hub card, re-run when the hub is forked</td><td>Every build needed one; it is what makes 'Spread' safe</td><td>Prototype the card; watch if teammates run a tested hub more than an untested one</td><td>Reuse rate of tested vs untested hubs</td></tr>"
             "<tr><td><b>3</b></td><td><b>Source health for monitor hubs</b>: unreadable ≠ removed, locale/currency normalised, 'verify' flags</td><td>" + str(B['unreadable_in_truth']) + f"/{B['snapshots']} pages unreadable; one currency trap; renames</td><td>Review false alarms with users of Competitor Watch / Risk Monitor</td><td>False alarms per week; alerts acted on</td></tr>"
             "</table><p class='small' style='margin-top:6px'>Full memo: docs/PRODUCT_FEEDBACK_MEMO.md. Based on Hubs' public positioning and on building these three workflows; I have not used the Hubs product.</p></div>")
    body += ('<div class="card" style="margin-top:12px"><h3>Adoption metrics I would track</h3><table><tr>'
             "<th>Build</th><th>Spread</th><th>Scale</th><th>Trust</th><th>Value</th></tr><tr>"
             "<td>Hubs created per active user per week</td><td>Share of runs by someone other than the creator; forks per hub</td>"
             "<td>Active agents: scheduled runs succeeding; hubs still running after 4 weeks</td>"
             "<td>Drafts sent with no number edits; runs ending in 'needs review'</td><td>Time saved per run, timed once then tracked</td>"
             "</tr></table></div>")
    pages.append(page("Product feedback for Hubs: make trust visible, numbers, tests and sources first",
                      "What building three of the agents shown on Hubs' site taught me: recurring needs, likely friction, adoption metrics and three prioritised ideas.",
                      "PRODUCT FEEDBACK", body, "docs/PRODUCT_FEEDBACK_MEMO.md · hypotheses, not findings from Hubs customers", 9))

    # 9 First 30 days
    body = ('<div class="flow">'
            + card("Days 1-7 · Learn", ul([
                "Use Hubs daily; rebuild these three workflows inside it.",
                "Shadow customer calls with the San Francisco team.",
                "Read the last month of customer feedback; tag it with one shared taxonomy.",
                "Write down what I would have needed as a new builder."]))
            + '<div class="arrow">→</div>'
            + card("Days 8-15 · First customer", ul([
                "Run discovery with one design partner (French-speaking if possible).",
                "Agree on one success metric and label 30-100 examples with them.",
                "Build the first hub with them, with checks visible."]))
            + '<div class="arrow">→</div>'
            + card("Days 16-23 · Prove it", ul([
                "Evaluate on their examples; fix the top errors.",
                "Measure time saved with the customer, not assumed.",
                "Show a teammate of theirs: does it spread without me?"]))
            + '<div class="arrow">→</div>'
            + card("Days 24-30 · Feed back", ul([
                "One structured feedback note per customer: need, friction, evidence, severity.",
                "Weekly digest of feedback themes for product (CX Pulse, applied to ourselves).",
                "A reusable discovery + evaluation template for the next implementation."]))
            + "</div>")
    body += ('<div class="grid" style="grid-template-columns:1fr 1fr 1fr;margin-top:12px">'
             + card("What I bring", ul([
                 "Discovery and implementation with 23 agency clients of an analytics product; their feedback drove the roadmap.",
                 "An agency for creators: listening to a client describe a problem, then building the fix.",
                 "BI work (Power BI, PL-300, SQL); AI used daily to solve business problems."]))
             + card("For European customers", ul([
                 "Native French, fluent English: discovery and onboarding in the customer's language.",
                 "Feedback translated into a structured note for the San Francisco team, same day.",
                 "Time zones: European mornings for customers, US mornings overlap with SF."]))
             + card("Questions I would ask the team", ul([
                 "Who are the first customers, and how do they find Hubs?",
                 "What do you measure today for adoption and reuse?",
                 "How does customer feedback reach the roadmap, and how fast?",
                 "What does a successful first hub look like for you?"]))
             + "</div>")
    pages.append(page("My first 30 days: one customer live, measured, and a feedback loop running",
                      "How I would help the San Francisco team from the start, including French-speaking customers in Europe.",
                      "PLAN", body, "Plan to adapt to the team's priorities", 10))

    # 10 Methods
    body = ('<div class="grid" style="grid-template-columns:1fr 1fr 1fr">'
            + card("Sources and licences", ul([
                "Hubs public website (hubs.is), read 2026-11-14; the job posting on Himalayas. Facts with dates in data/SOURCES.md.",
                "Olist Brazilian E-Commerce Public Dataset (Olist, CC BY-NC-SA 4.0), downloaded from Olist's public GitHub repository. Derived files carry the same licence.",
                "Public pricing pages of six SaaS vendors through the Internet Archive Wayback Machine; robots.txt checked, about one request every two seconds. Raw pages are not redistributed.",
                "Scenario C: simulated data (seed 42), fictional clients."]))
            + card("Limits", ul([
                "Customers in the scenarios are fictional; no Hubs customer, number or product access is used or implied.",
                "Small test sets (100 reviews, 40 snapshots, 30 reports), labelled by one person.",
                "Manual times are assumptions; workflow times, accuracy and checks are measured.",
                ("All three workflows were evaluated with the model." if ai else
                 "This build ran without an API key: the AI columns are pending and the rules baseline is shown. One command re-runs everything with a key."),
                "Rules for B were written after reading the pages, so the B baseline is optimistic."]))
            + card("Reproduce", "<div class='out'>python -m venv .venv<br>.venv\\Scripts\\pip install -r requirements.txt<br>"
                   "python src/prepare_reviews.py<br>python src/collect_pricing.py<br>python src/generate_sim.py<br>"
                   "python -m workflows run --scenario all<br>python src/evaluate.py<br>python src/build_dashboards.py<br>python src/build_report.py</div>"
                   "<p class='small' style='margin-top:6px'>One small, low-cost LLM (set in workflows/common/llm.py), JSON schema output, low effort, "
                   "call log without personal data. Without an API key in .env every workflow runs in demo mode.</p>")
            + "</div>")
    body += ('<div class="grid" style="grid-template-columns:1fr 1fr;margin-top:12px">'
             + card("Guardrails used everywhere", ul([
                 "Personal data masked before storage or any model call; no review text in logs or outputs.",
                 "Every number in generated text checked against computed facts; failures marked NEEDS REVIEW.",
                 "Every output is a draft for a person to review; nothing is sent automatically."]))
             + card("Note on AI use", f"<p>{esc(AI_NOTE)}</p>")
             + "</div>")
    pages.append(page("Methods, limits and how to reproduce every number",
                      "Where the data comes from, what is simulated, what is assumed, and the commands that rebuild the report.",
                      "METHODS", body, "README.md · data/SOURCES.md · data/ASSUMPTIONS.md", 11))
    return pages


# ------------------------------------------------------------------ PDF
def find_browser() -> str:
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              shutil.which("msedge") or "", shutil.which("google-chrome") or "", shutil.which("chromium") or ""]:
        if p and Path(p).exists():
            return p
    raise FileNotFoundError("Edge or Chrome is needed to print the PDF")


def print_pdf(html_path: Path, pdf_path: Path) -> None:
    import time
    profile = BUILD / "browser-profile"
    pdf_path.unlink(missing_ok=True)
    subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=5000", f"--user-data-dir={profile}", f"--print-to-pdf={pdf_path}",
                    html_path.as_uri()], capture_output=True, timeout=180)
    for _ in range(120):  # the browser may return before the file is fully written
        if pdf_path.exists() and pdf_path.stat().st_size > 10_000:
            time.sleep(1)
            break
        time.sleep(0.5)
    shutil.rmtree(profile, ignore_errors=True)
    if not pdf_path.exists():
        raise RuntimeError("PDF was not produced by the browser")
    # Blank the metadata (no local paths, no tool names in the PDF properties)
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    for pg in reader.pages:
        writer.add_page(pg)
    writer.add_metadata({"/Title": "Hubs: three customer problems, three AI solutions, measured",
                         "/Author": "", "/Creator": "", "/Producer": "", "/Subject": "", "/Keywords": ""})
    with open(pdf_path, "wb") as f:
        writer.write(f)


# ------------------------------------------------------------------ memo
def write_memo(n: dict) -> None:
    A, B, C = n["A"], n["B"], n["C"]
    st, sf = A["number_check_stress"], C["number_check_stress_final_text"]
    mode = ("All results below come from runs with the AI model." if n["ai"] else
            "These results come from the demo mode (rules and templates). The AI-model evaluation is pending and re-runs with one command.")
    md = f"""# Product feedback memo for Hubs

*Hypotheses to validate with customers. Written from Hubs' public positioning (hubs.is, read 2026-11-14) and from building three of the
agents shown on the site (CX Pulse, Competitor Watch, Client Reporting / Proposal Gen) on real public or labelled simulated data.
I have not used the Hubs product. {mode}*

## 1. Recurring customer needs
1. **Numbers people can trust.** In all three builds, the hard requirement from (fictional) customers was "never a wrong number in front of
   my boss or my client". One wrong number ends adoption of a hub, and with it the "Spread" step.
2. **Proof before sharing.** "Does it work on *my* data?" is answered by 30-100 labelled examples, not by a demo. Each workflow here has a
   test set; without it, nobody (me included) could say whether the rules or the model were good enough.
3. **"What changed", not a one-off answer.** A: which complaint grew vs the four previous weeks. B: what moved since the last snapshot.
   C: this month vs last month. This matches the "What's changed" block Hubs shows in the Network.
4. **Data guardrails by default.** Personal data masked before any model call, unreadable sources and data incidents flagged, a person approves.

## 2. Likely friction points
- **Labelling is the step people skip.** It is also the step that tells you if a hub works.
- **External sources break silently.** {B['unreadable_in_truth']} of {B['snapshots']} archived pricing pages show no prices in their static HTML;
  one Notion snapshot is in euros, the next in dollars; Zapier renamed a plan twice. Without guardrails, a monitor hub reports fake changes.
- **A value-only number check is not enough.** In A, planted wrong numbers were caught {st['planted_errors_caught']}/{st['planted_errors']} times;
  every miss was a true number placed next to the wrong label. In C, where numbers go through named slots, a typed number was caught
  {C['typed_number_stress']['caught']}/{C['typed_number_stress']['planted']} times and the reports contained {C['unsupported_numbers']} invented numbers.
- **Forked hubs drift.** A copy adapted by another team no longer matches the original's tests unless the tests travel with it.
- **Cost and latency are invisible** to the builder until a schedule multiplies them.

## 3. Adoption metrics to track
| Metric | Why |
|---|---|
| Hubs created per active user per week | Is "Build" happening? |
| Share of hub runs by someone other than the creator | Is "Spread" happening? |
| Forks / adaptations per hub, and forks still passing their tests | Healthy reuse vs drift |
| Active agents: scheduled runs succeeding; runs ending in "needs review" | "Scale" and reliability |
| Drafts sent with no number edits | Trust in generated outputs |
| Time saved per run (timed once, then tracked) | The value story for the buyer |
| Hubs still running after 4 weeks | Retention of solutions, not just users |

## 4. Three ideas, prioritised
| # | Idea | Evidence from the builds | How to validate | Success metric |
|---|---|---|---|---|
| 1 | **Verified numbers**: generated text references numbers through slots linked to data cells; a badge shows "all numbers verified" and each number links to its source | C: {C['unsupported_numbers']} invented numbers in {C['client_months']} reports; A's value check caught {pct(st['catch_rate'])} of planted errors | 5 design-partner interviews: "what stops you from sending an AI draft to a client?" | Share of drafts sent without number edits |
| 2 | **Test kit per hub**: label 30 examples in the UI, show accuracy on the hub card, re-run automatically when a hub is forked | Every build needed a test set; it is what makes reuse by a stranger safe | Prototype the hub card; compare reuse of tested vs untested hubs | Reuse rate of tested hubs |
| 3 | **Source health for monitor hubs**: "unreadable" is never "removed", locale and currency normalised, "verify" flags with evidence links | B: {B['unreadable_in_truth']}/{B['snapshots']} unreadable pages, a currency trap, renamed plans | Review a month of alerts with Competitor Watch / Risk Monitor users | False alarms per week; alerts acted on |

**Why this order:** 1 protects the moment a hub's output leaves the company (highest cost of failure), 2 makes "Spread" safe at low build
cost, 3 matters most for the monitor-type agents that run unattended.

---
Independent case study based on public information · not affiliated with or endorsed by Hubs
"""
    (DOCS / "PRODUCT_FEEDBACK_MEMO.md").write_text(md, encoding="utf-8")


def update_readme(n: dict) -> None:
    """Write the key results between the markers in README.md, from the same numbers as the report."""
    A, B, C, bx, la = n["A"], n["B"], n["C"], n["bx"], n["llm_a"]
    who = "AI model" if n["ai"] else "demo mode: rules baseline, AI evaluation pending"
    a_acc = la["theme"]["accuracy"] if la else A["rules"]["theme"]["accuracy"]
    a_rec = la["high_severity"]["recall"] if la else A["rules"]["high_severity"]["recall"]
    cost = n["cost"]
    block = f"""<!-- RESULTS:START -->
**Key results** ({who}):

| | Result |
|---|---|
| Accuracy on the test sets | **{pct(n['avg_acc'])}** on average (A theme accuracy {pct(a_acc)}, B plan/price F1 {pct(bx['extraction']['f1'])}, C incident recall {pct(C['anomaly_detection']['recall'])}); A high-severity recall {pct(a_rec)} |
| Invented numbers | **{n['invented']}** in every generated note, digest and report ({n['numbers_checked']} numbers checked) |
| Time saved | **~{n['time']['total_saved_hours_per_week']} h per week** across the three workflows (manual times are assumptions) |
| Cost | **${cost['usd']:.3f} per weekly cycle** ({cost['kind']}) |
<!-- RESULTS:END -->"""
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    start, end = text.index("<!-- RESULTS:START -->"), text.index("<!-- RESULTS:END -->") + len("<!-- RESULTS:END -->")
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    n = load_numbers()
    pages = build_pages(n)
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Hubs: three customer problems, three AI solutions, measured</title>'
           f"<style>{CSS}</style></head><body>{''.join(pages)}</body></html>")
    html_path = BUILD / "report.html"
    html_path.write_text(doc, encoding="utf-8")
    pdf = DOCS / "Hubs_AppliedAI_CaseStudy.pdf"
    print_pdf(html_path, pdf)
    write_memo(n)
    update_readme(n)
    try:  # page previews for the README (optional dependency)
        import pypdfium2 as pdfium
        doc_pdf = pdfium.PdfDocument(str(pdf))
        names = {0: "00_overview", 3: "03_cx_pulse", 4: "04_competitor_watch", 5: "05_client_report",
                 6: "06_measured", 8: "08_product_feedback"}
        (DOCS / "img").mkdir(exist_ok=True)
        for i, name in names.items():
            doc_pdf[i].render(scale=1.5).to_pil().convert("RGB").save(DOCS / "img" / f"{name}.png", optimize=True)
        doc_pdf.close()
    except ImportError:
        print("pypdfium2 not installed: page previews not refreshed")
    print(f"{len(pages)} pages -> {pdf.relative_to(ROOT)}; memo -> docs/PRODUCT_FEEDBACK_MEMO.md")


if __name__ == "__main__":
    main()
