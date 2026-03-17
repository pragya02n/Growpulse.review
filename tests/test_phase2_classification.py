from datetime import datetime

from growpulse.phase1_ingestion import CleanedReview
from growpulse.phase2_classification import (
    OTHER_THEME_NAME,
    ThemeSummary,
    classify_review_to_theme,
    classify_reviews,
    summarize_themes,
)


def _review(rating: float, title: str, text: str) -> CleanedReview:
    return CleanedReview(
        review_id="r",
        date=datetime(2026, 3, 16),
        rating=rating,
        title_clean=title,
        text_clean=text,
        source_meta=None,
    )


def test_classify_review_to_expected_themes() -> None:
    r_onboard = _review(5, "Smooth onboarding", "Loved the signup flow")
    r_kyc = _review(2, "KYC issues", "PAN verification failed")
    r_pay = _review(1, "UPI payment failed", "Transaction failed twice")
    r_withdraw = _review(3, "Withdraw funds", "Payout delayed")
    r_perf = _review(2, "App is slow", "Crashes frequently on login")
    r_other = _review(4, "Nice design", "Looks good overall")

    assert classify_review_to_theme(r_onboard) == "onboarding"
    assert classify_review_to_theme(r_kyc) == "kyc"
    assert classify_review_to_theme(r_pay) == "payments"
    assert classify_review_to_theme(r_withdraw) == "withdrawals"
    assert classify_review_to_theme(r_perf) == "app_performance"
    assert classify_review_to_theme(r_other) == OTHER_THEME_NAME


def test_summarize_themes_counts_and_average_rating() -> None:
    reviews = [
        _review(5, "Great onboarding", "Easy signup"),
        _review(4, "Onboarding ok", "Account opening smooth"),
        _review(1, "UPI payment failed", "Payment issue"),
        _review(3, "Nice design", "Looks good overall"),
    ]

    themed = classify_reviews(reviews)
    summaries = summarize_themes(themed)

    # Convert to dict for easier assertions
    summary_by_theme = {s.theme: s for s in summaries}

    assert "onboarding" in summary_by_theme
    assert summary_by_theme["onboarding"].count == 2
    assert summary_by_theme["onboarding"].average_rating == (5 + 4) / 2

    assert "payments" in summary_by_theme
    assert summary_by_theme["payments"].count == 1
    assert summary_by_theme["payments"].average_rating == 1

    assert OTHER_THEME_NAME in summary_by_theme
    assert summary_by_theme[OTHER_THEME_NAME].count == 1
    assert summary_by_theme[OTHER_THEME_NAME].average_rating == 3

