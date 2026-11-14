# Scenario C - Client report that never invents a number: discovery notes

> **Fictional customer and SIMULATED data.** "A creator-marketing agency with six creator brands as clients"
> is invented; the client names (Lumen Skincare, Trailhead Gear, ...) are fictional. The daily performance
> data is simulated (seed 42) on the pattern of how a small agency tracks creator-driven sales.

## What the customer asked for
"We spend a day each month writing client reports. Can AI write them?"

## Questions I asked, and what came out
| Question | Answer (fictional) | What it told me |
|---|---|---|
| What is in a report today? | Revenue, orders, best source, what we'll do next month. | Fixed structure: facts + interpretation + **proposal**. |
| How long per client? | About 45 minutes: export from 3 tools, paste, write. | Most of the time is data handling, not writing. |
| What would kill trust? | One wrong number in front of a client. | The hard requirement is **zero invented numbers**. |
| What else goes wrong? | Last summer a tracking link broke and we told a client sales had dropped. | Detect **data problems** (outages) and say so. |
| Who checks before sending? | The account manager. | Output is a draft with checks shown, never auto-sent. |
| Would others use it? | Every account manager, and sales for pitch decks. | Template per client type; same facts engine. |

## The real problem
**Produce a correct first draft of each monthly client report in minutes, where every number is
computed, data incidents are flagged, and the account manager only edits the words.**

## Success criteria agreed
- 0 numbers in a report that do not come from the facts table (checked automatically).
- Every planted tracking outage and traffic spike flagged in the "Data notes" section.
- Draft time per client: minutes instead of ~45 (manual time is an assumption, see data/ASSUMPTIONS.md).

## Design decision that came from discovery
The model never types a number. It writes sentences with slots such as `{{revenue_change_pct}}`;
code fills the slots from SQL results; a checker rejects any unknown slot or typed digit.

## Spread
Same engine for weekly creator check-ins, QBR decks, or a pitch "proposal" using a prospect's public numbers.
