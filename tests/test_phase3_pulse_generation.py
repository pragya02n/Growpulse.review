from datetime import date, datetime

from growpulse.phase1_ingestion import CleanedReview
from growpulse.phase2_classification import ThemeSummary, ThemedReview
from growpulse.phase3.pulse_generation import (
    GroqClient,
    PulseConfig,
    WeeklyPulse,
    generate_weekly_pulse,
)


class FakeGroqClient(GroqClient):
    """Test double that bypasses real Groq calls."""

    def __init__(self) -> None:  # type: ignore[override]
        # Do not call the real Groq constructor
        self.api_key = "test"
        self.model = "test"

    def generate_pulse(self, prompt: str) -> str:  # type: ignore[override]
        assert "Weekly Pulse" in prompt or "Weekly Pulse note" in prompt
        return "# Weekly Pulse\n\nThis is a fake note for testing.\n"


def _make_review(rating: float, theme: str, title: str, text: str) -> ThemedReview:
    r = CleanedReview(
        review_id=f"r-{theme}",
        date=datetime(2026, 3, 10),
        rating=rating,
        title_clean=title,
        text_clean=text,
        source_meta=None,
    )
    return ThemedReview(review=r, theme=theme)


def test_generate_weekly_pulse_with_fake_groq_client() -> None:
    week_start = date(2026, 3, 9)
    week_end = date(2026, 3, 15)

    themed_reviews = [
        _make_review(1, "payments", "UPI failed", "Payment not going through"),
        _make_review(2, "payments", "Card payment issue", "Card declined"),
        _make_review(5, "onboarding", "Great onboarding", "Signup was smooth"),
    ]

    summaries = [
        ThemeSummary(theme="payments", count=2, average_rating=1.5),
        ThemeSummary(theme="onboarding", count=1, average_rating=5.0),
    ]

    cfg = PulseConfig(
        top_n_themes=2,
        max_quotes=3,
        max_actions=3,
        max_reviews_per_theme=5,
    )

    client = FakeGroqClient()
    pulse: WeeklyPulse = generate_weekly_pulse(
        week_start=week_start,
        week_end=week_end,
        themed_reviews=themed_reviews,
        theme_summaries=summaries,
        cfg=cfg,
        client=client,
    )

    assert week_start.isoformat() in pulse.title
    assert week_end.isoformat() in pulse.title
    assert "Weekly Pulse" in pulse.body_markdown
    assert len(pulse.top_themes) == 2

