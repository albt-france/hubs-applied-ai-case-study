"""Every assumption used to turn measurements into "time saved" and "cost" lives here.

They are written out in data/ASSUMPTIONS.md. Change a value here and the report follows.
Manual times are ASSUMPTIONS (not measured on a real team); workflow times and accuracy are measured.
"""
from __future__ import annotations

# Manual baselines (minutes)
A_MANUAL_SECONDS_PER_REVIEW = 20      # read one short review and tag theme + severity
A_REVIEWS_PER_WEEK = 150              # the weekly sample size the workflow processes
A_MANUAL_NOTE_MIN = 30                # write the Monday note from the tags
A_HUMAN_REVIEW_MIN = 10               # a person reads the draft note and the high-severity list

B_PAGES = 6
B_MANUAL_MIN_PER_PAGE = 5             # open a pricing page, compare with last notes
B_MANUAL_DIGEST_MIN = 10
B_HUMAN_REVIEW_MIN = 5

C_CLIENTS = 6
C_MANUAL_MIN_PER_REPORT = 45          # export from tools, paste, write (from the scenario discovery)
C_HUMAN_REVIEW_MIN_PER_REPORT = 10

# Token estimate when no API key is available (about 3.5 characters per token for this mix of
# Portuguese / English / JSON). Replaced by measured usage as soon as the workflows run with a key.
CHARS_PER_TOKEN = 3.5


def weekly_minutes() -> dict:
    a_manual = A_REVIEWS_PER_WEEK * A_MANUAL_SECONDS_PER_REVIEW / 60 + A_MANUAL_NOTE_MIN
    b_manual = B_PAGES * B_MANUAL_MIN_PER_PAGE + B_MANUAL_DIGEST_MIN
    c_manual_month = C_CLIENTS * C_MANUAL_MIN_PER_REPORT
    c_review_month = C_CLIENTS * C_HUMAN_REVIEW_MIN_PER_REPORT
    weeks_per_month = 52 / 12
    out = {
        "A": {"manual": a_manual, "with_workflow": A_HUMAN_REVIEW_MIN},
        "B": {"manual": b_manual, "with_workflow": B_HUMAN_REVIEW_MIN},
        "C": {"manual": c_manual_month / weeks_per_month, "with_workflow": c_review_month / weeks_per_month},
    }
    for v in out.values():
        v["saved"] = v["manual"] - v["with_workflow"]
        v["manual"], v["with_workflow"], v["saved"] = (round(v["manual"]), round(v["with_workflow"]), round(v["saved"]))
    out["total_saved_hours_per_week"] = round(sum(out[k]["saved"] for k in "ABC") / 60, 1)
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(weekly_minutes(), indent=2))
