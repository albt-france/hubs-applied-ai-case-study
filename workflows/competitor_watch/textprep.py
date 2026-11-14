"""Turn a pricing page's visible text into a compact, price-focused excerpt.

Pricing pages are long (FAQ, footer, feature grids). Sending everything to a model costs more
and adds noise, so we keep the blocks around prices. This is plain code, used in both modes.
"""
from __future__ import annotations

import re

CUR = r"[$€£]"
PRICE_RE = re.compile(rf"{CUR}\s?\d[\d,]*(?:\.\d+)?")


def merge_split_prices(lines: list[str]) -> list[str]:
    """Many pages render '$' and '19' and '.99' in separate elements. Glue them back together."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if re.fullmatch(CUR, ln) and i + 1 < len(lines) and re.fullmatch(r"\d[\d,]*(\.\d+)?", lines[i + 1]):
            ln = ln + lines[i + 1]
            i += 1
            if i + 1 < len(lines) and re.fullmatch(r"\.\d{2}", lines[i + 1]):  # '.99'
                ln += lines[i + 1]
                i += 1
            elif (i + 2 < len(lines) and lines[i + 1] == "."
                  and re.fullmatch(r"\d{2}", lines[i + 2])):  # '.' then '99'
                ln += "." + lines[i + 2]
                i += 2
        out.append(ln)
        i += 1
    return out


def price_excerpt(text: str, before: int = 6, after: int = 4, max_lines: int = 400) -> str:
    """Lines around every price mention, in page order, with '...' between separate blocks."""
    lines = merge_split_prices([ln.strip() for ln in text.splitlines() if ln.strip()])
    hits = [i for i, ln in enumerate(lines) if PRICE_RE.search(ln)]
    keep = sorted({j for i in hits for j in range(max(0, i - before), min(len(lines), i + after + 1))})
    out, prev = [], None
    for j in keep[:max_lines]:
        if prev is not None and j != prev + 1:
            out.append("...")
        out.append(lines[j])
        prev = j
    return "\n".join(out)
