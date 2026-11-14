"""Collect dated snapshots of public SaaS pricing pages (Scenario B - Competitor Watch).

Source: the Internet Archive Wayback Machine (public snapshots), fetched in raw mode (`id_`)
so we get the page as the vendor served it, without the archive toolbar.

Politeness rules:
- robots.txt of each vendor was checked on 2026-11-14: no rule blocks /pricing.
- one request every ~2 seconds, a clear User-Agent, no login, no form submission.

Output:
- data/raw/wayback/<vendor>_<timestamp>.html   (raw page, NOT published - vendor copyright)
- data/raw/wayback/<vendor>_<timestamp>.txt    (visible text, NOT published)
- data/public/pricing_snapshots.csv            (vendor, timestamp, snapshot URL) - published
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "wayback"
OUT = ROOT / "data" / "public" / "pricing_snapshots.csv"
HEADERS = {"User-Agent": "case-study-research/1.0 (low-rate, non-commercial)"}
PAUSE_S = 2.0

VENDORS = {
    "notion": "www.notion.com/pricing",
    "slack": "slack.com/pricing",
    "asana": "asana.com/pricing",
    "trello": "trello.com/pricing",
    "clickup": "clickup.com/pricing",
    "zapier": "zapier.com/pricing",
}
# One snapshot close to each of these dates (YYYYMM). Semi-annual + the latest month.
TARGET_MONTHS = ["202401", "202407", "202501", "202507", "202601", "202607", "202611"]


def polite_get(url: str, **kwargs) -> requests.Response:
    """GET with a few retries and growing pauses (the archive throttles bursts)."""
    for attempt in range(5):
        try:
            r = requests.get(url, headers=HEADERS, timeout=90, **kwargs)
            if r.status_code == 200:
                return r
            print(f"  HTTP {r.status_code}, retrying")
        except requests.RequestException as exc:
            print(f"  {type(exc).__name__}, retrying")
        time.sleep(30 * (attempt + 1))
    raise RuntimeError(f"giving up on {url}")


def list_snapshots(url: str) -> list[str]:
    """Return one 200-status snapshot timestamp per month (Wayback CDX API)."""
    r = polite_get(
        "https://web.archive.org/cdx/search/cdx",
        params={"url": url, "from": "2024", "to": "2026", "output": "json",
                "filter": "statuscode:200", "collapse": "timestamp:6", "fl": "timestamp"})
    rows = r.json()
    return [row[0] for row in rows[1:]]


def pick(timestamps: list[str], month: str) -> str | None:
    """Pick the snapshot in the target month, else the closest later one (max 2 months later)."""
    def idx(yyyymm: str) -> int:  # months since year 0, so "202412" -> "202501" is 1 month
        return int(yyyymm[:4]) * 12 + int(yyyymm[4:6])

    for ts in timestamps:
        if 0 <= idx(ts[:6]) - idx(month) <= 2:
            return ts
    return None


def visible_text(html: str) -> str:
    """Visible text of a page, one block per line (scripts/styles removed)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    lines = [ln.strip() for ln in soup.get_text("\n").splitlines()]
    return "\n".join(ln for ln in lines if ln)


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    rows = []
    for vendor, url in VENDORS.items():
        stamps = list_snapshots(url)
        time.sleep(PAUSE_S)
        for month in TARGET_MONTHS:
            ts = pick(stamps, month)
            if not ts:
                print(f"{vendor} {month}: no snapshot")
                continue
            html_path = RAW / f"{vendor}_{ts}.html"
            if not html_path.exists():
                snap = f"https://web.archive.org/web/{ts}id_/https://{url}"
                resp = polite_get(snap)
                html_path.write_text(resp.text, encoding="utf-8")
                time.sleep(PAUSE_S)
            text = visible_text(html_path.read_text(encoding="utf-8"))
            (RAW / f"{vendor}_{ts}.txt").write_text(text, encoding="utf-8")
            rows.append({"vendor": vendor, "target_month": month, "timestamp": ts,
                         "snapshot_url": f"https://web.archive.org/web/{ts}/https://{url}"})
            print(f"{vendor} {month} -> {ts} ({len(text):,} chars)")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} snapshots -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
