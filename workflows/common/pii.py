"""Remove personal data from free text before it is stored or sent to a model.

The Olist reviews are already anonymised by Olist, but real customer text can still contain
e-mails, phone numbers, Brazilian tax IDs (CPF), URLs or a person's name after a greeting.
We mask them with tags so the meaning of the sentence survives.
"""
from __future__ import annotations

import re

TAGS = ("[EMAIL]", "[URL]", "[CPF]", "[PHONE]", "[NAME]")

PATTERNS = [
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("[URL]", re.compile(r"https?://\S+|www\.\S+", re.I)),
    ("[CPF]", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("[PHONE]", re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b")),
    # "meu nome é Maria" / "att, Carlos" -> keep the phrase, mask the capitalised name after it
    (r"\g<1> [NAME]", re.compile(r"\b((?i:nome é|me chamo|att,?|atenciosamente,?))\s+[A-ZÀ-Ú][a-zà-ú]+")),
]


def scrub(text: str | None) -> str:
    """Return the text with personal data replaced by tags. None -> empty string."""
    if not text:
        return ""
    out = str(text)
    for repl, pat in PATTERNS:
        out = pat.sub(repl, out)
    return " ".join(out.split())


def count_masks(text: str) -> int:
    return sum(text.count(tag) for tag in TAGS)
