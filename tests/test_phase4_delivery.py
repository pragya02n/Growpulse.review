from datetime import datetime

from growpulse.phase3.pulse_generation import ThemeSummary, WeeklyPulse
from growpulse.phase4.delivery import (
    EmailConfig,
    EmailMessage,
    Mailer,
    PulseRunMetadata,
    build_email_message,
    render_pulse_html,
)


def _sample_pulse() -> WeeklyPulse:
    themes = [
        ThemeSummary(theme="payments", count=10, average_rating=2.1),
        ThemeSummary(theme="onboarding", count=5, average_rating=4.2),
    ]
    return WeeklyPulse(
        title="Groww App – Weekly Pulse, Week of 2026-03-09 to 2026-03-15",
        body_markdown="# Weekly Pulse\n\nSome summary here.",
        top_themes=themes,
        quotes=[],
        actions=[],
    )


def _sample_meta() -> PulseRunMetadata:
    return PulseRunMetadata(
        week_range_label="2026-03-09 to 2026-03-15",
        total_reviews=123,
        generated_at_iso=datetime(2026, 3, 16, 8, 30).isoformat(),
    )


def test_render_pulse_html_contains_key_details() -> None:
    pulse = _sample_pulse()
    meta = _sample_meta()

    html = render_pulse_html(pulse, meta)

    assert "Groww App – Weekly Pulse" in html
    assert meta.week_range_label in html
    assert "payments" in html
    assert "onboarding" in html


def test_build_email_message_uses_template_and_pulse() -> None:
    pulse = _sample_pulse()
    meta = _sample_meta()

    cfg = EmailConfig(
        host="smtp.example.com",
        port=587,
        username="user",
        password="pass",
        use_tls=True,
        sender="pulse@example.com",
        recipient_alias="team@groww.com",
        subject_template="Groww Pulse | {week_range}",
    )

    msg: EmailMessage = build_email_message(cfg, pulse, meta)

    assert msg.subject == "Groww Pulse | 2026-03-09 to 2026-03-15"
    assert msg.sender == "pulse@example.com"
    assert msg.recipient == "team@groww.com"
    assert "Weekly Pulse" in msg.body_text
    assert "Weekly Pulse" in msg.body_html


class FakeMailer(Mailer):
    """Test double that records if send was called, without real SMTP."""

    def __init__(self, config: EmailConfig) -> None:
        super().__init__(config)
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:  # type: ignore[override]
        self.sent.append(message)


def test_fake_mailer_records_sent_message() -> None:
    pulse = _sample_pulse()
    meta = _sample_meta()

    cfg = EmailConfig(
        host="smtp.example.com",
        port=587,
        username=None,
        password=None,
        use_tls=False,
        sender="pulse@example.com",
        recipient_alias="team@groww.com",
    )
    msg = build_email_message(cfg, pulse, meta)

    mailer = FakeMailer(cfg)
    mailer.send(msg)

    assert len(mailer.sent) == 1
    stored = mailer.sent[0]
    assert stored.subject == msg.subject
    assert stored.recipient == msg.recipient

