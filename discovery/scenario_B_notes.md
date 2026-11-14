# Scenario B - Competitor Watch: discovery notes

> **Fictional customer.** "A small B2B SaaS company selling a team-productivity tool" is invented.
> The pricing pages are **real public pages** (Notion, Slack, Asana, Trello, ClickUp, Zapier), read through
> dated Wayback Machine snapshots from 2024-01 to 2026-11. These companies are examples of public pricing,
> not customers or partners of anyone in this study.

## What the customer asked for
"An agent that watches our competitors and tells us everything they do."

## Questions I asked, and what came out
| Question | Answer (fictional) | What it told me |
|---|---|---|
| What decision would change? | Our own pricing review, twice a year, and sales talk tracks. | They need **prices and packaging**, not "everything". |
| How do you do it today? | The founder opens 6 pricing pages once a quarter and compares from memory. | No history, no dates: changes are noticed late or never. |
| What counts as a change? | A price, a new or removed plan, a renamed plan. A new FAQ line does not. | Define change types up front; ignore cosmetic edits. |
| A 50%-off-for-3-months banner: is that a price change? | No, but sales wants to know about it. | Separate **list price** from **promo price**. |
| Which mistake is worse? | Missing a real change. A false alarm costs 2 minutes. | Favour recall; label uncertain cases "verify". |
| How fast? | Weekly is enough. | A weekly digest; no real-time scraping. |

## The real problem
**Know within a week when a competitor changes its list prices or its plan structure, with the date and
a link to the evidence**, and never be told a fake change.

## Success criteria agreed
- Plan/price extraction F1 >= 0.95 on labelled snapshots; 0 prices invented on pages that show none.
- All real changes in the history detected; false alarms acceptable if marked "verify".
- Every number in the digest traceable to a snapshot.

## Data and constraints found while building
- Public pages only, robots.txt checked, one request every ~2 s, archived snapshots (no load on the vendors).
- Some snapshots are **script-rendered**: the static page has no prices (Slack before 2026, Asana and
  ClickUp early 2024). A naive diff would report "all plans removed".
- One Notion snapshot was archived from Europe and shows **euros**; the next one shows dollars. A naive diff
  reports "Plus went from 9.50 to 10" - a currency effect, not a price change.
- ClickUp shows "Regular price" next to a lower price: list vs promo must be read correctly.

## Spread
Same pipeline for: a competitor's job posts (hiring signals), changelog pages (feature launches), or a
client's own price list across marketplaces. Parameters: list of URLs, change types, digest frequency.
