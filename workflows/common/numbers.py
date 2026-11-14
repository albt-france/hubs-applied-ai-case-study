"""Automatic number check: every number written in a generated text must come from the data.

How it works
1. The workflow computes a "facts" dictionary with code (SQL / pandas). Only these numbers
   are allowed in the text.
2. `extract_numbers` finds every number in the generated text (12, 1,234, 3.5%, $8, -0.4 pts...).
3. Each number must match an allowed value at the precision it is written with
   (12.46 -> "12.5" is fine, 12.7 -> "13" is not), percentages may be written as 12.5 for 0.125,
   thousands separators are ignored. Dates and week labels are handled explicitly.
4. Anything that does not match is an "unsupported number" - the report is flagged and a human
   must fix it before sending. The target is zero.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

NUM_RE = re.compile(r"(?<![\w.])[-+−]?\$?€?\d{1,3}(?:[,\s]\d{3})+(?:\.\d+)?|(?<![\w.])[-+−]?\$?€?\d+(?:\.\d+)?")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
WEEK_RE = re.compile(r"\b(?:W|week\s?)(\d{1,2})\b", re.I)


@dataclass
class CheckResult:
    numbers_found: int = 0
    supported: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.unsupported

    def as_dict(self) -> dict:
        return {"numbers_found": self.numbers_found, "supported": len(self.supported),
                "unsupported": self.unsupported, "ok": self.ok}


def _to_float(token: str) -> float:
    t = token.replace("−", "-").replace("$", "").replace("€", "").replace(",", "").replace(" ", "")
    return float(t)


def flatten(obj, out: list[float] | None = None) -> list[float]:
    """All numeric values inside nested dicts / lists (the allowed facts)."""
    out = [] if out is None else out
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            flatten(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            flatten(v, out)
    elif isinstance(obj, str):
        for m in DATE_RE.finditer(obj):  # dates in facts are allowed as written
            for part in re.split(r"[-/]", m.group()):
                out.append(float(part))
    return out


def extract_numbers(text: str) -> list[str]:
    """Numbers as written in the text, ignoring ISO dates and week labels (checked separately)."""
    cleaned = DATE_RE.sub(" ", text)
    cleaned = WEEK_RE.sub(" ", cleaned)
    return [m.group().strip() for m in NUM_RE.finditer(cleaned)]


def _decimals(token: str) -> int:
    t = token.replace(",", "")
    return len(t.split(".")[1]) if "." in t else 0


def _matches(value: float, allowed: list[float], decimals: int) -> bool:
    """Strict on purpose: the written number must equal a fact rounded to the precision written,
    and a whole number may only stand for a fact that is itself a whole number.
    (Loose rounding lets an invented "13" hide behind a true 12.7.)"""
    v = abs(value)
    for a in allowed:
        targets = [abs(a)] + ([abs(a) * 100] if abs(a) <= 1 else [])  # 0.125 written as 12.5 (%)
        for target in targets:
            if decimals == 0:
                if abs(target - round(target)) < 1e-9 and abs(v - target) < 1e-9:
                    return True
            elif round(target, decimals) == round(v, decimals) and _decimals(f"{target}") >= decimals:
                return True
    return False


def check(text: str, facts, always_allowed: tuple[float, ...] = ()) -> CheckResult:
    """Compare every number in `text` with the numbers in `facts`."""
    allowed = flatten(facts) + list(always_allowed)
    res = CheckResult()
    for tok in extract_numbers(text):
        res.numbers_found += 1
        try:
            val = _to_float(tok)
        except ValueError:
            res.unsupported.append(tok)
            continue
        (res.supported if _matches(val, allowed, _decimals(tok)) else res.unsupported).append(tok)
    return res
