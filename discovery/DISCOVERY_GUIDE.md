# Discovery guide: from "we want an AI agent" to the real problem

How I run a first customer conversation before building anything. Built from my own practice of
onboarding agencies onto an analytics product, adapted to what Hubs describes publicly
(Build -> Spread -> Scale, design partners, "we build your first hub with you").

The goal of a discovery call is not to collect features. It is to leave with:
1. **the decision or task** the solution must support (who does what, how often);
2. **how it is done today** and what it costs (time, errors, missed signals);
3. **what "working" means**, as a number the customer agrees on;
4. **the data** that exists, who owns it, and what must never leave the company;
5. **who else** would reuse the solution (the "Spread" in Hubs' model).

---

## 1. Before the call (15 min)
- Read what they sell, to whom, and their public footprint (site, reviews, pricing page, job posts).
- Write 3 hypotheses about their pain. The call is there to kill or confirm them.
- Prepare one tiny demo on public data that looks like theirs (it changes the conversation from
  "imagine" to "react").

## 2. The call (45 min): question bank

### Context: the job, not the tool
- "Walk me through the last time you did this. What did you open first?"
- "Who asks for this result, and what do they do with it?"
- "How often? What happens when it is late or wrong?"

### Today's cost
- "How long does it take, end to end? Who else is involved?"
- "When did it last go wrong? What did it cost you?"
- "What do you already try that does not work? Why did you stop?"

### The real problem behind the request
- "If this agent existed tomorrow, what decision would you make differently?"
- "What would you stop doing?"
- "Is the problem finding the information, trusting it, or acting on it?"
- When they name a solution ("a dashboard", "a chatbot"): "What would you do with it on Monday morning?"

### Success, as a number
- "What would make you say in four weeks: this works?"
- "What error is acceptable? Which error is not acceptable at all?" (e.g. a missed serious complaint
  vs a mislabelled compliment)
- "How much time per week is worth saving to keep using it?"

### Data and trust
- "Where does the data live? Who can export it? How fresh does it need to be?"
- "What must never be sent to an outside model? (names, e-mails, client contracts...)"
- "Who must check the output before it reaches a client or a manager?"

### Spread
- "Who else in the company does something similar?"
- "If a colleague in another team used this, what would they need to change?"

## 3. Finding the real problem: signals I listen for
| They say | It often means | I ask |
|---|---|---|
| "We need AI for X" | A pain exists, the cause is unclear | "What happens today when X goes wrong?" |
| "We have too much data" | They cannot prioritise | "Which 3 items would you look at first, and why?" |
| "The numbers are off" | A definition problem, not a tool problem | "Off compared to what? Who computes the other number?" |
| "Our best person does it" | A workflow trapped in one head (Hubs' own pain #2) | "What would it take for someone else to do it next week?" |
| "Just give me a summary" | They want a decision, not a text | "What decision does the summary feed?" |

## 4. After the call (30 min)
- One-page note: problem in their words, the real problem in mine, success metric, data, risks.
- A test set plan: 30-100 real examples the customer helps label. **No test set, no launch.**
- Send it back to the customer: "Did I get this right?" Their corrections are the most valuable output.
- Log product feedback separately (what the platform made easy or hard) for the product team.

## 5. Success criteria template
| Criterion | Target | How it is measured |
|---|---|---|
| Accuracy on the critical class | e.g. >= 90% recall on serious complaints | hand-labelled test set |
| Invented numbers in outputs | 0 | automatic number check on every run |
| Time saved | e.g. >= 2 h/week | manual time (timed once) vs workflow time |
| Cost per run | e.g. < $0.10 | API usage log |
| Adoption | e.g. 3 people use it by week 3 | usage, reuse by another team |

The three scenario notes in this folder apply this guide. The customers are **fictional**; the
data behind the solutions is real public data (A, B) or clearly labelled simulated data (C).
