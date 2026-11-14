# Assumptions

What is assumed rather than measured, and why. The values live in `src/assumptions.py`; change them there and rebuild the report.

## Measured (not assumptions)
- Accuracy, recall, F1 and change detection: measured against the test sets in `data/eval/`.
- Invented numbers: counted by the automatic number check on every generated text.
- Workflow run time and, when an API key is set, tokens and cost per call (`outputs/logs/llm_calls.jsonl`).

## Assumed
| Item | Value | Why this value |
|---|---|---|
| Manual tagging of one short review | 20 s | Most Olist reviews are one or two sentences; read + pick a theme + pick a severity. |
| Reviews processed per week | 150 | The weekly sample size the workflow uses. |
| Writing the weekly CX note by hand | 30 min | Count tags, compare with past weeks, write five lines. |
| Checking one pricing page by hand | 5 min | Open, find the plans, compare with last notes. |
| Pages tracked | 6 | The vendors in scenario B. |
| Writing the competitor digest by hand | 10 min | |
| One monthly client report by hand | 45 min | From the scenario C discovery: export from three tools, paste, write. |
| Human review of each workflow output | A 10 min/week, B 5 min/week, C 10 min/report | Every output is a draft a person reads before it is used. |
| Characters per token (cost estimate without an API key) | 3.5 | Mix of Portuguese, English and JSON; replaced by measured usage when a key is set. |
| Extra output for the model's short reasoning (cost estimate only) | +50% | Effort is set to low; a margin rather than zero. |

These give about 2.5 hours saved per week across the three workflows. They should be replaced by timing a real person once.

## Scenario framing
- The three customers (an e-commerce marketplace, a SaaS company, a creator-marketing agency) are **fictional**. Their answers in
  `discovery/` are written to illustrate the method, not reported from real interviews.
- Scenario C data is **simulated**. Its shape (sources, conversion rates, order values) is plausible for a small creator-driven
  brand, not taken from any real client.
- Reference labels for the test sets were written by one person reading each source text, before running the workflows.
  A second labeller would make the scores more robust.
- Detector thresholds in scenario C were tuned on a separate simulation (seed 7), never on the test data (seed 42).
- Scenario B's rule baseline was written after reading the pages, so it is an optimistic baseline.
