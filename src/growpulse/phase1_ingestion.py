from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
from dateutil import parser as date_parser


@dataclass
class CleanedReview:
    review_id: str
    date: datetime
    rating: float
    title_clean: str
    text_clean: str
    source_meta: Optional[dict] = None


class ReviewIngestionError(Exception):
    """Raised when reviews cannot be ingested or validated."""


PII_PATTERNS = [
    # Emails
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]"),
    # Phone numbers (10+ digits, with optional separators)
    (r"\b(?:\+?\d[\d\s\-]{8,}\d)\b", "[PHONE]"),
    # URLs
    (r"https?://[^\s]+", "[URL]"),
# Simple account / reference IDs (alphanumeric strings 8+ chars that contain at least one digit)
(r"\b(?=.*\d)[A-Za-z0-9]{8,}\b", "[ID]"),
]


def _parse_date(value: str) -> datetime:
    dt = date_parser.parse(str(value))
    return dt.replace(tzinfo=None)


def _within_window(date_value: datetime, weeks: int, now: Optional[datetime] = None) -> bool:
    if now is None:
        now = datetime.utcnow()
    lower_bound = now - timedelta(weeks=weeks)
    return lower_bound <= date_value <= now


def _redact_pii(text: str) -> str:
    import re

    cleaned = str(text)
    for pattern, replacement in PII_PATTERNS:
        cleaned = re.sub(pattern, replacement, cleaned)
    return cleaned


def _ensure_no_pii(text: str) -> bool:
    """Best-effort post-check using the same patterns; returns True if nothing matches."""
    import re

    for pattern, _ in PII_PATTERNS:
        if re.search(pattern, text):
            return False
    return True


def ingest_and_clean_reviews(
    csv_path: Path | str,
    time_window_weeks: int = 12,
    now: Optional[datetime] = None,
) -> List[CleanedReview]:
    """
    Load reviews from a CSV, filter by date window, and apply PII cleaning.

    Expected minimal columns: rating, title, text, date.
    """
    path = Path(csv_path)
    if not path.exists():
        raise ReviewIngestionError(f"CSV file not found: {path}")

    try:
        df = pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - pandas-specific edge
        raise ReviewIngestionError(f"Failed to read CSV: {exc}") from exc

    required_cols = {"rating", "title", "text", "date"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ReviewIngestionError(f"Missing required columns: {', '.join(sorted(missing))}")

    cleaned_reviews: List[CleanedReview] = []
    now_value = now or datetime.utcnow()

    for idx, row in df.iterrows():
        try:
            raw_date = _parse_date(row["date"])
        except Exception:
            # Skip rows with invalid dates
            continue

        if not _within_window(raw_date, time_window_weeks, now=now_value):
            continue

        try:
            rating = float(row["rating"])
        except Exception:
            # Skip rows with invalid rating
            continue

        title_raw = str(row.get("title", "") or "")
        text_raw = str(row.get("text", "") or "")

        # If raw text contains obvious PII, drop the review entirely instead of
        # relying only on redaction. This keeps the downstream set strictly
        # PII-free at the sample level.
        if not (_ensure_no_pii(title_raw) and _ensure_no_pii(text_raw)):
            continue

        title_clean = _redact_pii(title_raw)
        text_clean = _redact_pii(text_raw)

        # PII compliance guard: if still detects patterns, drop the review
        if not (_ensure_no_pii(title_clean) and _ensure_no_pii(text_clean)):
            continue

        review_id = f"{path.stem}-{idx}"

        # Optional metadata: include any extra columns
        meta_keys = [c for c in df.columns if c not in ("rating", "title", "text", "date")]
        source_meta = {k: row[k] for k in meta_keys} if meta_keys else None

        cleaned_reviews.append(
            CleanedReview(
                review_id=review_id,
                date=raw_date,
                rating=rating,
                title_clean=title_clean,
                text_clean=text_clean,
                source_meta=source_meta,
            )
        )

    return cleaned_reviews

