# Product feedback memo for Hubs

*Hypotheses to validate with customers. Written from Hubs' public positioning (hubs.is, read 2026-11-14) and from building three of the
agents shown on the site (CX Pulse, Competitor Watch, Client Reporting / Proposal Gen) on real public or labelled simulated data.
I have not used the Hubs product. These results come from the demo mode (rules and templates). The AI-model evaluation is pending and re-runs with one command.*

## 1. Recurring customer needs
1. **Numbers people can trust.** In all three builds, the hard requirement from (fictional) customers was "never a wrong number in front of
   my boss or my client". One wrong number ends adoption of a hub, and with it the "Spread" step.
2. **Proof before sharing.** "Does it work on *my* data?" is answered by 30-100 labelled examples, not by a demo. Each workflow here has a
   test set; without it, nobody (me included) could say whether the rules or the model were good enough.
3. **"What changed", not a one-off answer.** A: which complaint grew vs the four previous weeks. B: what moved since the last snapshot.
   C: this month vs last month. This matches the "What's changed" block Hubs shows in the Network.
4. **Data guardrails by default.** Personal data masked before any model call, unreadable sources and data incidents flagged, a person approves.

## 2. Likely friction points
- **Labelling is the step people skip.** It is also the step that tells you if a hub works.
- **External sources break silently.** 6 of 40 archived pricing pages show no prices in their static HTML;
  one Notion snapshot is in euros, the next in dollars; Zapier renamed a plan twice. Without guardrails, a monitor hub reports fake changes.
- **A value-only number check is not enough.** In A, planted wrong numbers were caught 84/100 times;
  every miss was a true number placed next to the wrong label. In C, where numbers go through named slots, a typed number was caught
  30/30 times and the reports contained 0 invented numbers.
- **Forked hubs drift.** A copy adapted by another team no longer matches the original's tests unless the tests travel with it.
- **Cost and latency are invisible** to the builder until a schedule multiplies them.

## 3. Adoption metrics to track
| Metric | Why |
|---|---|
| Hubs created per active user per week | Is "Build" happening? |
| Share of hub runs by someone other than the creator | Is "Spread" happening? |
| Forks / adaptations per hub, and forks still passing their tests | Healthy reuse vs drift |
| Active agents: scheduled runs succeeding; runs ending in "needs review" | "Scale" and reliability |
| Drafts sent with no number edits | Trust in generated outputs |
| Time saved per run (timed once, then tracked) | The value story for the buyer |
| Hubs still running after 4 weeks | Retention of solutions, not just users |

## 4. Three ideas, prioritised
| # | Idea | Evidence from the builds | How to validate | Success metric |
|---|---|---|---|---|
| 1 | **Verified numbers**: generated text references numbers through slots linked to data cells; a badge shows "all numbers verified" and each number links to its source | C: 0 invented numbers in 30 reports; A's value check caught 84% of planted errors | 5 design-partner interviews: "what stops you from sending an AI draft to a client?" | Share of drafts sent without number edits |
| 2 | **Test kit per hub**: label 30 examples in the UI, show accuracy on the hub card, re-run automatically when a hub is forked | Every build needed a test set; it is what makes reuse by a stranger safe | Prototype the hub card; compare reuse of tested vs untested hubs | Reuse rate of tested hubs |
| 3 | **Source health for monitor hubs**: "unreadable" is never "removed", locale and currency normalised, "verify" flags with evidence links | B: 6/40 unreadable pages, a currency trap, renamed plans | Review a month of alerts with Competitor Watch / Risk Monitor users | False alarms per week; alerts acted on |

**Why this order:** 1 protects the moment a hub's output leaves the company (highest cost of failure), 2 makes "Spread" safe at low build
cost, 3 matters most for the monitor-type agents that run unattended.

---
Independent case study based on public information · not affiliated with or endorsed by Hubs
