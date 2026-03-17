"""
Quick script to convert the raw Groww CSV into the schema expected by the pipeline.

Raw columns:   reviewId, content, star score, date & time
Target columns: rating, title, text, date
"""
import pandas as pd
from pathlib import Path

RAW_CSV = Path(__file__).resolve().parent.parent.parent / "groww_cleaned_with_id_final (1).csv"
OUT_CSV = Path(__file__).resolve().parent / "reviews.csv"


def main():
    df = pd.read_csv(RAW_CSV)
    df.columns = df.columns.str.strip()  # normalise column names
    print(f"Loaded {len(df)} rows from {RAW_CSV}")
    print(f"Columns: {list(df.columns)}")

    # Map columns
    mapped = pd.DataFrame({
        "rating": df["star score"],
        "title": "",                     # no title column in raw data
        "text": df["content"],
        "date": df["date & time"],
    })

    mapped.to_csv(OUT_CSV, index=False)
    print(f"Wrote {len(mapped)} rows to {OUT_CSV}")


if __name__ == "__main__":
    main()
