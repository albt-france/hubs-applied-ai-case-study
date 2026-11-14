"""Thin wrapper around the Anthropic API used by the three workflows.

Design choices (each one is something I can defend in an interview):
- One small, cheap model (`claude-haiku-5-5`) for classification, extraction and short writing.
- Structured output: every call returns JSON validated against a Pydantic schema, so
  downstream code never parses free text.
- `effort: low` keeps the model's thinking short (these are narrow tasks). Current API
  versions do not accept `temperature`, so determinism comes from the schema + fixed prompts.
- No key in `.env`  ->  `available()` is False and each workflow uses its rule-based demo mode.
- Every call is logged to outputs/logs/llm_calls.jsonl with tokens, cost and latency only:
  no prompt text and no review text, so the log never holds customer data.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Type, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

MODEL = os.getenv("HUBS_CASE_MODEL", "claude-haiku-5-5")
# USD per million tokens (Anthropic price list, checked 2026-11-14, prompts < 100K tokens).
PRICE_IN, PRICE_OUT = 0.10, 0.50
LOG = ROOT / "outputs" / "logs" / "llm_calls.jsonl"

T = TypeVar("T", bound=BaseModel)
_client = None


def available() -> bool:
    """True when an API key is configured (otherwise workflows run in demo mode)."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def mode() -> str:
    return "llm" if available() else "demo"


def _get_client():
    global _client
    if _client is None:
        import anthropic  # imported lazily so demo mode works without network setup
        _client = anthropic.Anthropic()
    return _client


def cost_usd(tokens_in: int, tokens_out: int) -> float:
    return tokens_in / 1e6 * PRICE_IN + tokens_out / 1e6 * PRICE_OUT


def structured_call(workflow: str, system: str, user: str, schema: Type[T],
                    max_tokens: int = 4000) -> tuple[T, dict]:
    """Ask the model for JSON matching `schema`. Returns (parsed object, usage dict)."""
    import anthropic

    client = _get_client()
    t0 = time.perf_counter()
    kwargs = dict(model=MODEL, max_tokens=max_tokens, system=system,
                  messages=[{"role": "user", "content": user}], output_format=schema)
    try:
        resp = client.messages.parse(output_config={"effort": "low"}, **kwargs)
    except anthropic.BadRequestError:
        resp = client.messages.parse(**kwargs)  # fall back to the model's default effort
    latency = time.perf_counter() - t0
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        raise RuntimeError(f"{workflow}: no parsed output (stop_reason={resp.stop_reason})")
    usage = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "workflow": workflow,
        "model": MODEL,
        "tokens_in": resp.usage.input_tokens,
        "tokens_out": resp.usage.output_tokens,
        "cost_usd": round(cost_usd(resp.usage.input_tokens, resp.usage.output_tokens), 6),
        "latency_s": round(latency, 2),
    }
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(usage) + "\n")
    return resp.parsed_output, usage


def summarize_usage(usages: list[dict]) -> dict:
    """Totals for a run: calls, tokens, cost, wall time spent waiting on the model."""
    return {
        "calls": len(usages),
        "tokens_in": sum(u["tokens_in"] for u in usages),
        "tokens_out": sum(u["tokens_out"] for u in usages),
        "cost_usd": round(sum(u["cost_usd"] for u in usages), 4),
        "model_time_s": round(sum(u["latency_s"] for u in usages), 1),
    }
