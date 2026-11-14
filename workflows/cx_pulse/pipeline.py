"""CX Pulse: every week, what customers complain about, what got worse, what improved.

Steps
1. Load the weekly review sample (personal data already masked) and the weekly totals.
2. Classify each review: theme + severity (+ a short English paraphrase in LLM mode).
   LLM mode: batches of 25 reviews per call, JSON schema enforced. Demo mode: keyword rules.
3. Aggregate with SQL (DuckDB): theme share per week, change vs the 4 previous weeks.
4. Write the weekly note from a facts table. The model only writes words around numbers
   computed by code; an automatic check rejects any number that is not in the facts.
5. Save everything for a human to review before it is shared.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

import duckdb
import pandas as pd
from pydantic import BaseModel, Field

from workflows.common import llm, numbers
from workflows.cx_pulse import rules
from workflows.cx_pulse.taxonomy import NEGATIVE_THEMES, SEVERITY, THEMES

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "cx_pulse"
BATCH = 25
Theme = Literal[tuple(THEMES)]  # type: ignore[valid-type]
Severity = Literal[tuple(SEVERITY)]  # type: ignore[valid-type]


# ---------- 1. Classification ----------
class ReviewLabel(BaseModel):
    review_id: str
    theme: Theme
    severity: Severity
    paraphrase_en: str = Field(description="Max 15 words, English, no names")


class LabelBatch(BaseModel):
    labels: list[ReviewLabel]


SYSTEM_CLASSIFY = (
    "You label e-commerce customer reviews written in Brazilian Portuguese.\n"
    "For each review return exactly one primary theme and one severity.\n"
    "If a review mixes praise and a complaint, the complaint is the theme.\n\nThemes:\n"
    + "\n".join(f"- {k}: {v}" for k, v in THEMES.items())
    + "\n\nSeverity:\n" + "\n".join(f"- {k}: {v}" for k, v in SEVERITY.items())
    + "\n\nThe star rating is context, not the answer: judge the text."
    "\nparaphrase_en: a neutral English paraphrase of the complaint (or praise), max 15 words, no names."
    "\nReturn one label per review_id, in the same order. Never invent review_ids."
)


def classify_llm(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    rows, usages = [], []
    for start in range(0, len(df), BATCH):
        chunk = df.iloc[start:start + BATCH]
        payload = "\n".join(json.dumps({"review_id": r.review_id, "stars": int(r.review_score), "text": r.text},
                                       ensure_ascii=False) for r in chunk.itertuples())
        parsed, usage = llm.structured_call("cx_pulse.classify", SYSTEM_CLASSIFY, payload, LabelBatch,
                                            max_tokens=4000)
        usages.append(usage)
        got = {lab.review_id: lab for lab in parsed.labels}
        for r in chunk.itertuples():  # guardrail: every review must get exactly one label
            lab = got.get(r.review_id)
            rows.append({"review_id": r.review_id,
                         "theme": lab.theme if lab else "other",
                         "severity": lab.severity if lab else "medium",
                         "paraphrase_en": lab.paraphrase_en if lab else "",
                         "label_missing": lab is None})
    return pd.DataFrame(rows), usages


def classify_demo(df: pd.DataFrame) -> pd.DataFrame:
    out = [dict(zip(("theme", "severity"), rules.classify(r.text, int(r.review_score))),
                review_id=r.review_id, paraphrase_en="", label_missing=False) for r in df.itertuples()]
    return pd.DataFrame(out)


def classify(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    if llm.available():
        return classify_llm(df)
    return classify_demo(df), []


# ---------- 2. Aggregation (SQL) ----------
def weekly_theme_table(labeled: pd.DataFrame) -> pd.DataFrame:
    """Share of sampled reviews per theme per week, in percent."""
    con = duckdb.connect()
    con.register("labeled", labeled)
    return con.sql("""
        WITH counts AS (
            SELECT CAST(week_start AS DATE) AS wk, theme, count(*) AS n,
                   sum(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) AS n_high
            FROM labeled GROUP BY 1, 2)
        SELECT wk AS week_start, theme, n,
               round(100.0 * n / sum(n) OVER (PARTITION BY wk), 1) AS share_pct, n_high
        FROM counts ORDER BY 1, 2""").df()


def week_facts(themes: pd.DataFrame, totals: pd.DataFrame, labeled: pd.DataFrame, week) -> dict:
    """All numbers the weekly note may use, computed by code."""
    weeks = sorted(themes.week_start.unique())
    i = weeks.index(week)
    prev = weeks[max(0, i - 4):i]
    pivot = themes.pivot(index="week_start", columns="theme", values="share_pct").fillna(0.0)
    for t in THEMES:
        if t not in pivot:
            pivot[t] = 0.0
    tot = totals.set_index("week_start")
    this = labeled[labeled.week_start == week]
    median_volume = float(tot.reviews.median())
    facts = {
        "week_start": str(week),
        "reviews_total": int(tot.loc[week, "reviews"]),
        "avg_score": float(tot.loc[week, "avg_score"]),
        "avg_score_prev4": round(float(tot.loc[prev, "avg_score"].mean()), 2),
        "share_1_2_stars_pct": round(100 * float(tot.loc[week, "share_1_2_stars"]), 1),
        "share_1_2_stars_prev4_pct": round(100 * float(tot.loc[prev, "share_1_2_stars"].mean()), 1),
        "sample_size": int(len(this)),
        "high_severity_n": int((this.severity == "high").sum()),
        "low_volume_week": bool(tot.loc[week, "reviews"] < 0.5 * median_volume),
        "themes": {},
    }
    for t in NEGATIVE_THEMES:
        now, before = float(pivot.loc[week, t]), round(float(pivot.loc[prev, t].mean()), 1)
        facts["themes"][t] = {"share_pct": now, "prev4_pct": before, "change_pts": round(now - before, 1)}
    ranked = sorted(facts["themes"].items(), key=lambda kv: kv[1]["change_pts"])
    facts["most_improved"] = [k for k, v in ranked if v["change_pts"] < 0][:2]
    facts["most_worsened"] = [k for k, v in reversed(ranked) if v["change_pts"] > 0][:2]
    facts["top_issue"] = max(facts["themes"], key=lambda k: facts["themes"][k]["share_pct"])
    examples = this[(this.theme == facts["top_issue"]) & (this.severity == "high")].head(2)
    facts["examples"] = [(e.paraphrase_en or e.text[:120]) for e in examples.itertuples()]
    return facts


# ---------- 3. Weekly note ----------
class Note(BaseModel):
    headline: str
    worse: list[str]
    better: list[str]
    action: str


SYSTEM_NOTE = (
    "You write a weekly customer-experience note for an e-commerce brand's operations lead.\n"
    "Use ONLY numbers that appear in the facts JSON (you may round to 1 decimal). Do not compute new numbers "
    "(no sums, no ratios, no differences that are not given). Shares are % of sampled reviews with text. "
    "Plain English, short sentences. headline: one sentence. worse/better: 1-2 bullets each. "
    "action: one concrete next step for the team. If low_volume_week is true, say the week is not comparable."
)

READABLE = {t: t.replace("_", " ") for t in THEMES}


def note_demo(f: dict) -> Note:
    """Template note used without an API key: same facts, fixed sentences."""
    top = f["themes"][f["top_issue"]]
    worse = [f"{READABLE[t]}: {f['themes'][t]['share_pct']}% of sampled reviews "
             f"({f['themes'][t]['change_pts']:+} pts vs the 4 previous weeks)" for t in f["most_worsened"]] or ["No theme got worse."]
    better = [f"{READABLE[t]}: {f['themes'][t]['share_pct']}% "
              f"({f['themes'][t]['change_pts']:+} pts)" for t in f["most_improved"]] or ["No theme improved."]
    headline = (f"Week of {f['week_start']}: {READABLE[f['top_issue']]} is the top complaint "
                f"({top['share_pct']}% of {f['sample_size']} sampled reviews); "
                f"1-2 star reviews at {f['share_1_2_stars_pct']}% vs {f['share_1_2_stars_prev4_pct']}% before.")
    if f["low_volume_week"]:
        headline += " Low-volume week: not comparable."
    action = f"Review the {f['high_severity_n']} high-severity reviews today, starting with {READABLE[f['top_issue']]}."
    return Note(headline=headline, worse=worse, better=better, action=action)


def render(note: Note, facts: dict, check: numbers.CheckResult, mode: str) -> str:
    status = "PASSED" if check.ok else f"NEEDS REVIEW - unsupported numbers: {', '.join(check.unsupported)}"
    lines = [f"## CX Pulse - week of {facts['week_start']}", "", f"**{note.headline}**", "", "**Got worse**"]
    lines += [f"- {b}" for b in note.worse] + ["", "**Improved**"] + [f"- {b}" for b in note.better]
    lines += ["", f"**Next step:** {note.action}", ""]
    if facts["examples"]:
        lines += ["**Examples (high severity)**"] + [f"- \"{e}\"" for e in facts["examples"]] + [""]
    lines += [f"_Number check: {status} ({check.numbers_found} numbers). Mode: {mode}. "
              f"Draft for human review before sharing._"]
    return "\n".join(lines)


def write_note(facts: dict) -> tuple[str, numbers.CheckResult, list[dict]]:
    usages = []
    if llm.available():
        note, usage = llm.structured_call("cx_pulse.note", SYSTEM_NOTE, json.dumps(facts, ensure_ascii=False), Note, 1500)
        usages.append(usage)
    else:
        note = note_demo(facts)
    body = " ".join([note.headline, *note.worse, *note.better, note.action])
    check = numbers.check(body, facts, always_allowed=(1, 2, 4))  # "1-2 stars", "4 previous weeks"
    if not check.ok and llm.available():  # one retry with the problem spelled out
        fix = (json.dumps(facts, ensure_ascii=False) + "\n\nYour previous draft used numbers that are not in the facts: "
               + ", ".join(check.unsupported) + ". Rewrite using only numbers from the facts.")
        note, usage = llm.structured_call("cx_pulse.note_retry", SYSTEM_NOTE, fix, Note, 1500)
        usages.append(usage)
        body = " ".join([note.headline, *note.worse, *note.better, note.action])
        check = numbers.check(body, facts, always_allowed=(1, 2, 4))
    return render(note, facts, check, llm.mode()), check, usages


# ---------- 4. Run ----------
def run(weeks_to_report: int = 4) -> dict:
    t0 = time.perf_counter()
    sample = pd.read_csv(ROOT / "data" / "public" / "reviews_sample.csv", parse_dates=["week_start"])
    totals = pd.read_csv(ROOT / "data" / "public" / "reviews_weekly_totals.csv", parse_dates=["week_start"])
    sample["week_start"] = sample.week_start.dt.date
    totals["week_start"] = totals.week_start.dt.date

    labels, usages = classify(sample[["review_id", "review_score", "text"]])
    labeled = sample.merge(labels, on="review_id")
    themes = weekly_theme_table(labeled[["week_start", "theme", "severity"]])
    themes["week_start"] = pd.to_datetime(themes.week_start).dt.date

    OUT.mkdir(parents=True, exist_ok=True)
    weeks = sorted(labeled.week_start.unique())
    notes, checks, all_facts = [], [], []
    for week in weeks[-weeks_to_report:]:
        facts = week_facts(themes, totals, labeled, week)
        text, check, u = write_note(facts)
        usages += u
        notes.append(text)
        checks.append(check.as_dict())
        all_facts.append(facts)

    (OUT / "weekly_notes.md").write_text("\n\n---\n\n".join(reversed(notes)), encoding="utf-8")
    (OUT / "facts.json").write_text(json.dumps(all_facts, indent=2, ensure_ascii=False), encoding="utf-8")
    labeled.drop(columns=["text"]).to_csv(OUT / "labels.csv", index=False)  # no review text in outputs
    themes.to_csv(OUT / "weekly_themes.csv", index=False)

    summary = {"workflow": "cx_pulse", "mode": llm.mode(), "reviews_classified": int(len(labeled)),
               "weeks": len(weeks), "notes": len(notes),
               "unsupported_numbers": sum(len(c["unsupported"]) for c in checks),
               "numbers_checked": sum(c["numbers_found"] for c in checks),
               "runtime_s": round(time.perf_counter() - t0, 1), **llm.summarize_usage(usages)}
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
