"""Prepare the review data for Scenario A (CX Pulse) with DuckDB.

Input  (not published, downloaded from Olist's public GitHub repo, see data/SOURCES.md):
  data/raw/reviews/olist_order_reviews_dataset.csv, orders, order_items, products, category translation
Output (published, CC BY-NC-SA 4.0 like the source):
  data/public/reviews_weekly_totals.csv  all reviews per week: volume, average score, share 1-2 stars
  data/public/reviews_sample.csv         weekly random sample of reviews WITH text, personal data masked
  data/eval/cx_eval_reviews.csv          100 other reviews for the labelled test set (labels added by hand)

Window: 8 complete weeks, Monday 2018-06-25 to Sunday 2018-08-19 (the most recent full weeks in the data).
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflows.common.pii import count_masks, scrub  # noqa: E402

RAW = ROOT / "data" / "raw" / "reviews"
START, END = "2018-06-25", "2018-08-20"  # END is exclusive
PER_WEEK = 150   # reviews with text sampled per week (all of them if fewer)
SEED = 42

SQL_BASE = f"""
CREATE OR REPLACE VIEW reviews AS
SELECT * FROM read_csv_auto('{(RAW / 'olist_order_reviews_dataset.csv').as_posix()}');
CREATE OR REPLACE VIEW items AS
SELECT * FROM read_csv_auto('{(RAW / 'olist_order_items_dataset.csv').as_posix()}');
CREATE OR REPLACE VIEW products AS
SELECT * FROM read_csv_auto('{(RAW / 'olist_products_dataset.csv').as_posix()}');
CREATE OR REPLACE VIEW cat AS
SELECT * FROM read_csv_auto('{(RAW / 'product_category_name_translation.csv').as_posix()}');

-- one category per order: the category of its first item
CREATE OR REPLACE VIEW order_category AS
SELECT i.order_id, coalesce(c.product_category_name_english, p.product_category_name, 'unknown') AS category
FROM items i
LEFT JOIN products p USING (product_id)
LEFT JOIN cat c USING (product_category_name)
WHERE i.order_item_id = 1;

-- a few review_ids appear twice in the source (same review attached to several orders);
-- keep one row per review_id, with a full tie-breaker so every run picks the same row
CREATE OR REPLACE VIEW reviews_clean AS
SELECT * EXCLUDE (rn) FROM (
  SELECT r.*, row_number() OVER (PARTITION BY review_id ORDER BY review_answer_timestamp, order_id) AS rn
  FROM reviews r) WHERE rn = 1;
"""


OLIST_URL = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/{name}.csv"
FILES = ["olist_order_reviews_dataset", "olist_orders_dataset", "olist_order_items_dataset",
         "olist_products_dataset", "product_category_name_translation"]


def download_if_missing() -> None:
    """Fetch the Olist CSVs from Olist's public GitHub repository (one file at a time)."""
    import time
    import requests
    RAW.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        path = RAW / f"{name}.csv"
        if not path.exists():
            print(f"downloading {name}.csv")
            r = requests.get(OLIST_URL.format(name=name), timeout=120,
                             headers={"User-Agent": "case-study-research/1.0 (low-rate, non-commercial)"})
            r.raise_for_status()
            path.write_bytes(r.content)
            time.sleep(1)


def main() -> None:
    download_if_missing()
    con = duckdb.connect()
    con.execute(SQL_BASE)

    weekly = con.sql(f"""
        SELECT CAST(date_trunc('week', review_creation_date) AS DATE) AS week_start,
               count(*) AS reviews,
               count(review_comment_message) AS reviews_with_text,
               round(avg(review_score), 2) AS avg_score,
               round(avg(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END), 4) AS share_1_2_stars
        FROM reviews_clean
        WHERE review_creation_date >= '{START}' AND review_creation_date < '{END}'
        GROUP BY 1 ORDER BY 1""").df()

    texts = con.sql(f"""
        SELECT r.review_id, CAST(date_trunc('week', r.review_creation_date) AS DATE) AS week_start,
               CAST(r.review_creation_date AS DATE) AS review_date, r.review_score,
               r.review_comment_title AS title, r.review_comment_message AS message,
               coalesce(oc.category, 'unknown') AS category
        FROM reviews_clean r LEFT JOIN order_category oc USING (order_id)
        WHERE r.review_comment_message IS NOT NULL AND length(trim(r.review_comment_message)) >= 3
        ORDER BY r.review_id  -- SQL results have no guaranteed order; sampling needs a fixed one
        """).df()

    texts["text"] = (texts["title"].fillna("") + ". " + texts["message"].fillna("")).str.strip(". ").map(scrub)
    texts["pii_masks"] = texts["text"].map(count_masks)
    texts = texts.drop(columns=["title", "message"])

    in_window = texts[(texts.review_date >= pd.Timestamp(START)) & (texts.review_date < pd.Timestamp(END))]
    sample = pd.concat([g.sample(n=min(PER_WEEK, len(g)), random_state=SEED)
                        for _, g in in_window.groupby("week_start")]).sort_values(["week_start", "review_id"])

    # Test set: 100 reviews with text from BEFORE the window (so it never overlaps the sample),
    # stratified by star rating so serious complaints are well represented.
    before = texts[texts.review_date < pd.Timestamp(START)]
    quota = {1: 25, 2: 10, 3: 15, 4: 20, 5: 30}
    eval_set = pd.concat([before[before.review_score == s].sample(n=n, random_state=SEED + s)
                          for s, n in quota.items()]).sample(frac=1, random_state=SEED)

    out_pub, out_eval = ROOT / "data" / "public", ROOT / "data" / "eval"
    out_pub.mkdir(parents=True, exist_ok=True)
    out_eval.mkdir(parents=True, exist_ok=True)
    weekly.to_csv(out_pub / "reviews_weekly_totals.csv", index=False)
    sample.to_csv(out_pub / "reviews_sample.csv", index=False)
    eval_path = out_eval / "cx_eval_reviews.csv"
    if not eval_path.exists():  # never overwrite: the labels are added to this file by hand
        eval_set[["review_id", "review_score", "category", "text"]].to_csv(eval_path, index=False)

    print(weekly.to_string(index=False))
    print(f"sample: {len(sample)} reviews over {sample.week_start.nunique()} weeks; "
          f"personal-data masks applied: {int(texts.pii_masks.sum())} across {len(texts):,} texts")
    print(f"test set: {len(eval_set)} reviews -> {eval_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
