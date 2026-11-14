"""Competitor Watch: track competitors' public pricing pages and only report what actually changed.

Steps
1. Read dated snapshots of each pricing page (Wayback Machine, see src/collect_pricing.py).
2. Reduce each page to a price-focused excerpt (plain code).
3. Extract plans and prices as JSON: LLM mode (schema-enforced) or demo mode (rules).
4. Compare each snapshot with the previous readable one, with guardrails:
   - a page with no prices is "unreadable", never "all plans removed";
   - a currency switch is "not comparable, check" rather than a price change;
   - a missing plan is "not found, verify" (pages often hide cards behind scripts).
5. Write a short digest of the changes; every number in it is checked against the extracted data.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field

from workflows.common import llm, numbers
from workflows.competitor_watch.textprep import merge_split_prices, price_excerpt

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "wayback"
OUT = ROOT / "outputs" / "competitor_watch"
EXTRACT_CACHE = ROOT / "data" / "public" / "pricing_extracted_{mode}.json"


# ---------- 1. Extraction ----------
class Plan(BaseModel):
    name: str
    list_price: float | None = Field(description="Regular price shown by default, per user (or per account) per month")
    promo_price: float | None = Field(default=None, description="Discounted/introductory price if one is shown")
    currency: str = Field(description="ISO code, e.g. USD, EUR")


class Extraction(BaseModel):
    page_has_prices: bool
    plans: list[Plan]


SYSTEM_EXTRACT = (
    "You extract the public pricing plans of a SaaS product from the visible text of its pricing page.\n"
    "Rules:\n- Only the core plans of the main product. Skip add-ons, credits, separate products and plans with "
    "no public price ('Contact sales').\n- list_price = the regular price shown by default. If a price is struck "
    "through or labelled 'Regular price', that is list_price and the lower one is promo_price. A time-limited "
    "discount ('50% off for 3 months') is promo_price.\n- Use the currency symbol shown on the page.\n"
    "- Never guess: if the text shows no prices, return page_has_prices=false and an empty list."
)


def extract_llm(excerpt: str) -> tuple[Extraction, dict]:
    return llm.structured_call("competitor_watch.extract", SYSTEM_EXTRACT, excerpt or "(empty page)", Extraction, 2000)


SKIP_TITLES = re.compile(r"^(popular|most popular|recommended|best value|best for .*|starting from|starts at|\+|"
                         r"per .*|billed .*|usd.*|save .*|get started|learn more|show more|try it free|new|beta|"
                         r"\d.*|.*regular price.*|monthly|yearly|free forever|recommended for you)$", re.I)
ADDON = re.compile(r"add-on|add-ons|add to|credits|premium starts|agents|chatbots|interfaces|tables|brain", re.I)
CUR_SYMBOL = {"$": "USD", "€": "EUR", "£": "GBP"}


def extract_demo(text: str) -> Extraction:
    """Rules baseline: a price on its own line belongs to the nearest short title line above it."""
    lines = merge_split_prices([ln.strip() for ln in text.splitlines() if ln.strip()])
    plans: dict[str, Plan] = {}
    for i, ln in enumerate(lines):
        m = re.fullmatch(r"([$€£])(\d[\d,]*(?:\.\d+)?)", ln)
        if not m:
            continue
        context = " ".join(lines[max(0, i - 4):i])
        price = float(m.group(2).replace(",", ""))
        if "regular price" in lines[i - 1].lower() and plans:  # "$9 / Regular price / $12"
            last = list(plans)[-1]
            plans[last] = plans[last].model_copy(update={"promo_price": plans[last].list_price, "list_price": price})
            continue
        if ADDON.search(context):
            continue
        title = next((lines[j] for j in range(i - 1, max(-1, i - 5), -1)
                      if len(lines[j]) <= 24 and not SKIP_TITLES.match(lines[j]) and not re.search(r"[$€£]", lines[j])), None)
        if title and title not in plans:
            plans[title] = Plan(name=title.title() if title.islower() else title, list_price=price,
                                currency=CUR_SYMBOL[m.group(1)])
    return Extraction(page_has_prices=bool(plans), plans=list(plans.values()))


def extract_all(snapshots: pd.DataFrame, use_cache: bool = True) -> tuple[dict, list[dict]]:
    """Extraction for every snapshot. Results are cached in data/public so a clean clone
    (without the unpublished raw pages) can still run the change detection and the digest."""
    mode = llm.mode()
    cache_path = Path(str(EXTRACT_CACHE).format(mode=mode))
    published = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    cache = dict(published) if use_cache else {}
    usages = []
    for s in snapshots.itertuples():
        key = f"{s.vendor}_{s.timestamp}"
        if key in cache:
            continue
        txt_path = RAW / f"{key}.txt"
        if not txt_path.exists():
            if key in published:  # clean clone without the raw pages: reuse the published extraction
                cache[key] = published[key]
                continue
            raise FileNotFoundError(f"{txt_path} missing: run `python src/collect_pricing.py` first")
        text = txt_path.read_text(encoding="utf-8")
        if mode == "llm":
            ex, usage = extract_llm(price_excerpt(text))
            usages.append(usage)
        else:
            ex = extract_demo(text)
        cache[key] = ex.model_dump()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    return cache, usages


# ---------- 2. Change detection ----------
def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9+]", "", name.lower())


def diff(prev: dict, cur: dict) -> list[dict]:
    """Compare two extractions of the same page. Returns a list of change records."""
    if not cur["plans"]:
        return [{"type": "unreadable", "detail": "no prices found on the page (script-rendered?) - skipped"}]
    p = {norm(x["name"]): x for x in prev["plans"]}
    c = {norm(x["name"]): x for x in cur["plans"]}
    cur_p = {x["currency"] for x in prev["plans"]}
    cur_c = {x["currency"] for x in cur["plans"]}
    if cur_p != cur_c:
        return [{"type": "currency_changed", "detail": f"currency {'/'.join(sorted(cur_p))} -> {'/'.join(sorted(cur_c))}: "
                 "prices not comparable, check manually"}]
    changes = []
    for k, x in c.items():
        if k not in p:
            changes.append({"type": "plan_added", "plan": x["name"], "new": x["list_price"]})
        elif x["list_price"] != p[k]["list_price"]:
            changes.append({"type": "price_changed", "plan": x["name"], "old": p[k]["list_price"], "new": x["list_price"]})
        if k in p and (x.get("promo_price") or None) != (p[k].get("promo_price") or None):
            changes.append({"type": "promo_changed", "plan": x["name"], "old": p[k].get("promo_price"),
                            "new": x.get("promo_price")})
    for k, x in p.items():
        if k not in c:
            changes.append({"type": "plan_not_found", "plan": x["name"], "old": x["list_price"],
                            "detail": "verify: removed, renamed or hidden"})
    return changes


def detect_changes(snapshots: pd.DataFrame, extracted: dict) -> list[dict]:
    """Walk each vendor's snapshots in time order; compare with the last readable one."""
    periods = []
    for vendor, g in snapshots.sort_values("timestamp").groupby("vendor"):
        last = None
        for s in g.itertuples():
            ex = extracted[f"{vendor}_{s.timestamp}"]
            if not ex["plans"]:
                continue  # unreadable page: never compared, never reported as "all plans removed"
            if last is not None:
                ch = diff(extracted[f"{vendor}_{last}"], ex)
                periods.append({"vendor": vendor, "from_ts": str(last), "to_ts": str(s.timestamp),
                                "changed": bool(ch), "changes": ch})
            last = s.timestamp
    return periods


# ---------- 3. Digest ----------
class Digest(BaseModel):
    headline: str
    bullets: list[str]


SYSTEM_DIGEST = (
    "You write a short competitor-pricing digest for a small SaaS company's founder. Input: detected changes "
    "between two dated snapshots of each competitor's pricing page. Use only numbers present in the input. "
    "Say clearly when something must be verified (currency change, plan not found). headline: one sentence. "
    "bullets: one per vendor with a change, most important first. No vendor without changes."
)


VENDOR_NAMES = {"notion": "Notion", "slack": "Slack", "asana": "Asana", "trello": "Trello",
                "clickup": "ClickUp", "zapier": "Zapier"}


def iso(ts: str) -> str:
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"


def money(v) -> str:
    return "none" if v is None else (f"{v:g}")


def digest_demo(latest: list[dict]) -> Digest:
    bullets = []
    for p in latest:
        parts = []
        for c in p["changes"]:
            if c["type"] == "price_changed":
                parts.append(f"{c['plan']} list price {money(c['old'])} -> {money(c['new'])}")
            elif c["type"] == "plan_added":
                parts.append(f"new plan {c['plan']} at {money(c['new'])}")
            elif c["type"] == "plan_not_found":
                parts.append(f"{c['plan']} not found (verify)")
            elif c["type"] == "promo_changed":
                parts.append(f"{c['plan']} promo price {money(c['old'])} -> {money(c['new'])}")
            else:
                parts.append(c["detail"])
        bullets.append(f"{VENDOR_NAMES.get(p['vendor'], p['vendor'])} ({iso(p['from_ts'])} -> {iso(p['to_ts'])}): " + "; ".join(parts))
    head = (f"{len(bullets)} of the tracked competitors changed their pricing page in the latest period."
            if bullets else "No pricing change in the latest period.")
    return Digest(headline=head, bullets=bullets)


def run(as_of: str | None = None) -> dict:
    """Digest for the most recent period of each vendor (as_of = last snapshot), plus the full history."""
    t0 = time.perf_counter()
    snaps = pd.read_csv(ROOT / "data" / "public" / "pricing_snapshots.csv", dtype={"timestamp": str})
    extracted, usages = extract_all(snaps)
    periods = detect_changes(snaps, extracted)
    latest = {}
    for p in periods:
        latest[p["vendor"]] = p  # time-ordered, so the last one per vendor wins
    changed_latest = [p for p in latest.values() if p["changed"]]
    history_changed = [p for p in periods if p["changed"]]

    if llm.available():
        for_model = [{**p, "from_date": iso(p["from_ts"]), "to_date": iso(p["to_ts"])} for p in changed_latest]
        dg, u = llm.structured_call("competitor_watch.digest", SYSTEM_DIGEST, json.dumps(for_model), Digest, 1500)
        usages.append(u)
    else:
        dg = digest_demo(changed_latest)
    facts = {"changes": changed_latest, "n": len(changed_latest)}
    check = numbers.check(" ".join([dg.headline, *dg.bullets]), facts)

    OUT.mkdir(parents=True, exist_ok=True)
    md = [f"## Competitor Watch - pricing digest", "", f"**{dg.headline}**", ""] + [f"- {b}" for b in dg.bullets]
    md += ["", "### Full history (all periods with a detected change)"]
    md += [f"- {VENDOR_NAMES.get(p['vendor'], p['vendor'])} {iso(p['from_ts'])} -> {iso(p['to_ts'])}: "
           + "; ".join(c.get("type") + (f" {c['plan']}" if c.get("plan") else "") for c in p["changes"])
           for p in history_changed]
    md += ["", f"_Number check: {'PASSED' if check.ok else 'NEEDS REVIEW ' + str(check.unsupported)} "
               f"({check.numbers_found} numbers). Mode: {llm.mode()}. Sources: Wayback Machine snapshots listed in "
               f"data/public/pricing_snapshots.csv. Draft for human review._"]
    (OUT / "digest.md").write_text("\n".join(md), encoding="utf-8")
    (OUT / "periods.json").write_text(json.dumps(periods, indent=1), encoding="utf-8")
    summary = {"workflow": "competitor_watch", "mode": llm.mode(), "snapshots": len(snaps),
               "readable_snapshots": sum(bool(v["plans"]) for v in extracted.values()),
               "periods_compared": len(periods), "periods_with_change": len(history_changed),
               "unsupported_numbers": len(check.unsupported), "numbers_checked": check.numbers_found,
               "runtime_s": round(time.perf_counter() - t0, 1), **llm.summarize_usage(usages)}
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
