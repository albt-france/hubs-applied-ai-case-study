# Scenario A - CX Pulse: discovery notes

> **Fictional customer.** "A mid-size e-commerce marketplace" is invented to frame the problem.
> The reviews used to build and test the solution are **real public data** (Olist, Brazil, 2016-2018,
> CC BY-NC-SA 4.0). Nothing here describes a Hubs customer.

## What the customer asked for
"We get thousands of reviews a week. We'd like an AI that summarises them."

## Questions I asked, and what came out
| Question | Answer (fictional) | What it told me |
|---|---|---|
| Who reads the summary, and what do they do with it? | The ops lead, Monday meeting; decides where to send the team. | The output is a **weekly decision**, not a summary. |
| What happens today? | Someone skims 1-2 star reviews for half a day; the rest is ignored. | Only the star rating is used; text in 3-5 star reviews is lost. |
| When did it last go wrong? | A carrier problem ran for three weeks before anyone noticed. | The real need is **change detection**: what got worse vs usual. |
| Which error is unacceptable? | Missing an order that never arrived. A mislabelled compliment is fine. | Optimise **recall on high-severity issues**, not overall accuracy. |
| What must not leave the company? | Customer names, e-mails, phone numbers. | Mask personal data **before** any model call. |
| Language? | Reviews are in Portuguese; the leadership team reads English. | Classify in the source language, report in English. |

## The real problem
Not "summarise reviews", but: **every Monday, tell the ops lead which problem grew last week, how
big it is, and which orders need action today**, with numbers the team can trust.

## Success criteria agreed
- Recall >= 90% on high-severity reviews (order not received, wrong item, broken, refund issue).
- Theme accuracy >= 85% on a 100-review test set labelled with the customer.
- 0 numbers in the weekly note that do not come from the data.
- Under $0.10 and under 5 minutes per weekly run.

## Data
- Reviews with star rating and date; product category through the order. 99,224 reviews, 40,977 with text.
- 8 most recent full weeks (2018-06-25 to 2018-08-19); a weekly random sample of 150 reviews with text.
- One week (2018-07-16) has a quarter of the usual volume: the note must say "not comparable",
  not "complaints fell". (A real data issue found while building.)

## Spread: who else would reuse it
Customer service (daily queue of high-severity reviews), category managers (themes per category),
marketing (praise quotes). Same pipeline, different filters: see the Reuse section of the report.
