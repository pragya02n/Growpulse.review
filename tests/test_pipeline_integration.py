from datetime import datetime
from pathlib import Path

import pandas as pd

from growpulse.phase3.pulse_generation import GroqClient
from growpulse.phase4.delivery import EmailConfig, EmailMessage, Mailer
from growpulse.pipeline import PipelineConfig, PipelineResult, run_pipeline


class FakeGroqClient(GroqClient):
    def __init__(self) -> None:  # type: ignore[override]
        self.api_key = "test"
        self.model = "test"

    def generate_pulse(self, prompt: str) -> str:  # type: ignore[override]
        import json
        return json.dumps({
            "themes": [{"name": "Payments", "mentions": 10, "priority": "HIGH", "percentage_change": "+5%", "action_text": "Fix UPI"}],
            "quotes": ["Integration test quote"],
            "actions": [],
            "severity_scores": [],
            "feature_impact": [],
            "theme_deep_dives": [],
            "weekly_comparison": [],
            "daily_breakdown": []
        })


class FakeMailer(Mailer):
    def __init__(self, config: EmailConfig) -> None:
        super().__init__(config)
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:  # type: ignore[override]
        self.sent.append(message)


def _make_csv(tmp_path: Path) -> Path:
    now = datetime(2026, 3, 16)
    recent_date = now.strftime("%Y-%m-%d")
    data = [
        {
            "rating": 5,
            "title": "Great onboarding",
            "text": "Signup flow was smooth.",
            "date": recent_date,
        },
        {
            "rating": 1,
            "title": "UPI payment failed",
            "text": "Transaction failed twice.",
            "date": recent_date,
        },
    ]
    df = pd.DataFrame(data)
    csv_path = tmp_path / "reviews.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


def test_full_pipeline_with_fakes(tmp_path: Path) -> None:
    csv_path = _make_csv(tmp_path)
    now = datetime(2026, 3, 16, 9, 0, 0)

    email_cfg = EmailConfig(
        host="smtp.example.com",
        port=587,
        username=None,
        password=None,
        use_tls=False,
        sender="pulse@example.com",
        recipient_alias="team@groww.com",
    )

    cfg = PipelineConfig(
        csv_path=csv_path,
        time_window_weeks=12,
        groq_api_key=None,  # we will inject a fake client instead
        groq_model="test-model",
        email=email_cfg,
    )

    fake_client = FakeGroqClient()
    fake_mailer = FakeMailer(email_cfg)

    result: PipelineResult = run_pipeline(
        cfg=cfg,
        now=now,
        groq_client=fake_client,
        mailer=fake_mailer,
    )

    # Phase 1: ingestion
    assert len(result.cleaned_reviews) == 2
    # Phase 2: classification produced summaries
    assert len(result.summaries) >= 1
    # Phase 3: pulse generated (now JSON)
    assert '"Payments"' in result.pulse.body_markdown
    # Phase 4: email sent via fake mailer
    assert len(fake_mailer.sent) == 1
    assert "Groww Weekly Pulse" in fake_mailer.sent[0].body_html

