from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Tuple

from .phase1_ingestion import CleanedReview


@dataclass(frozen=True)
class ThemeDefinition:
    name: str
    keywords: Tuple[str, ...]


DEFAULT_THEMES: Tuple[ThemeDefinition, ...] = (
    ThemeDefinition(
        name="onboarding",
        keywords=(
            "onboard",
            "signup",
            "sign up",
            "account opening",
            "account creation",
            "register",
        ),
    ),
    ThemeDefinition(
        name="kyc",
        keywords=(
            "kyc",
            "pan",
            "aadhaar",
            "aadhar",
            "verification",
            "document",
            "id proof",
        ),
    ),
    ThemeDefinition(
        name="payments",
        keywords=(
            "payment",
            "upi",
            "card",
            "debit",
            "credit",
            "gateway",
            "transaction failed",
        ),
    ),
    ThemeDefinition(
        name="withdrawals",
        keywords=(
            "withdraw",
            "payout",
            "redeem",
            "redemption",
            "cash out",
        ),
    ),
    ThemeDefinition(
        name="app_performance",
        keywords=(
            "crash",
            "bug",
            "slow",
            "lag",
            "performance",
            "hang",
            "freeze",
        ),
    ),
)

OTHER_THEME_NAME = "other"


def _text_for_matching(review: CleanedReview) -> str:
    return f"{review.title_clean} {review.text_clean}".lower()


def classify_review_to_theme(
    review: CleanedReview,
    themes: Iterable[ThemeDefinition] = DEFAULT_THEMES,
) -> str:
    """
    Simple rule-based classifier that assigns a single theme name.
    Falls back to 'other' if no keywords match.
    """
    text = _text_for_matching(review)

    best_theme = None
    best_hits = 0
    for theme in themes:
        hits = sum(1 for kw in theme.keywords if kw in text)
        if hits > best_hits:
            best_hits = hits
            best_theme = theme.name

    return best_theme or OTHER_THEME_NAME


@dataclass
class ThemedReview:
    review: CleanedReview
    theme: str


def classify_reviews(
    reviews: Iterable[CleanedReview],
    themes: Iterable[ThemeDefinition] = DEFAULT_THEMES,
) -> List[ThemedReview]:
    """Classify many reviews into themes."""
    themed: List[ThemedReview] = []
    for r in reviews:
        theme = classify_review_to_theme(r, themes=themes)
        themed.append(ThemedReview(review=r, theme=theme))
    return themed


@dataclass
class ThemeSummary:
    theme: str
    count: int
    average_rating: float


def summarize_themes(themed_reviews: Iterable[ThemedReview]) -> List[ThemeSummary]:
    """
    Aggregate per-theme counts and average rating.
    """
    rating_sum: Dict[str, float] = defaultdict(float)
    counts: Counter[str] = Counter()

    for tr in themed_reviews:
        counts[tr.theme] += 1
        rating_sum[tr.theme] += tr.review.rating

    summaries: List[ThemeSummary] = []
    for theme, count in counts.items():
        avg = rating_sum[theme] / count if count else 0.0
        summaries.append(ThemeSummary(theme=theme, count=count, average_rating=avg))

    # Sort by count descending then theme name for determinism
    summaries.sort(key=lambda s: (-s.count, s.theme))
    return summaries

