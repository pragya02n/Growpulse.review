from datetime import datetime
from pathlib import Path

import pandas as pd

from growpulse.phase1_ingestion import (
    CleanedReview,
    ReviewIngestionError,
    ingest_and_clean_reviews,
)


def _make_sample_csv(tmp_path: Path) -> Path:
    now = datetime(2026, 3, 16)
    recent_date = now.strftime("%Y-%m-%d")
    old_date = "2020-01-01"

    data = [
        {
            "rating": 5,
            "title": "Great onboarding experience",
            "text": "Loved the flow, very smooth.",
            "date": recent_date,
        },
        {
            "rating": 1,
            "title": "KYC issue - contact me at user@example.com",
            "text": "My phone 9876543210 was rejected.",
            "date": recent_date,
        },
        {
            "rating": 4,
            "title": "Old review out of window",
            "text": "This should be filtered by date.",
            "date": old_date,
        },
    ]
    df = pd.DataFrame(data)
    csv_path = tmp_path / "reviews.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


def test_ingest_and_clean_reviews_filters_window_and_removes_pii(tmp_path: Path) -> None:
    csv_path = _make_sample_csv(tmp_path)
    now = datetime(2026, 3, 16)

    cleaned = ingest_and_clean_reviews(csv_path, time_window_weeks=12, now=now)

    # The old review should be filtered out by date, so we expect 2 recent rows,
    # but the one with PII should be dropped by the PII guard, leaving 1.
    assert len(cleaned) == 1

    review = cleaned[0]
    assert isinstance(review, CleanedReview)
    assert "onboarding" in review.title_clean.lower()
    assert "example.com" not in review.title_clean
    assert "9876543210" not in review.text_clean


def test_missing_required_columns_raises(tmp_path: Path) -> None:
    df = pd.DataFrame([{"rating": 5, "title": "Missing text/date"}])
    csv_path = tmp_path / "bad.csv"
    df.to_csv(csv_path, index=False)

    try:
        ingest_and_clean_reviews(csv_path)
    except ReviewIngestionError as exc:
        assert "Missing required columns" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ReviewIngestionError")

