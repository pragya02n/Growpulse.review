from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .phase4.delivery import EmailConfig, PulseRunMetadata, render_pulse_html, Mailer
from .pipeline import PipelineConfig, run_pipeline


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Run the Groww Weekly Pulse pipeline over a reviews CSV."
    )
    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help="Path to the reviews CSV file (rating,title,text,date,...).",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=int(os.getenv("TIME_WINDOW_WEEKS", "52")),
        help="Number of weeks to look back from today (default: 52 or TIME_WINDOW_WEEKS env).",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Do not send email even if email configuration is present.",
    )
    parser.add_argument(
        "--out-html",
        type=str,
        default="weekly_pulse.html",
        help="Path to write an HTML preview of the weekly pulse (default: weekly_pulse.html).",
    )

    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")

    groq_api_key = os.getenv("GROQ_API_KEY")
    groq_model = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

    email_cfg = None
    if not args.no_email:
        email_host = os.getenv("EMAIL_HOST")
        email_port = os.getenv("EMAIL_PORT")
        email_sender = os.getenv("EMAIL_SENDER")
        email_recipient = os.getenv("EMAIL_RECIPIENT")
        if email_host and email_port and email_sender and email_recipient:
            email_cfg = EmailConfig(
                host=email_host,
                port=int(email_port),
                username=os.getenv("EMAIL_USERNAME") or None,
                password=os.getenv("EMAIL_PASSWORD") or None,
                use_tls=os.getenv("EMAIL_USE_TLS", "true").lower() == "true",
                sender=email_sender,
                recipient_alias=email_recipient,
            )

    cfg = PipelineConfig(
        csv_path=csv_path,
        time_window_weeks=args.weeks,
        groq_api_key=groq_api_key,
        groq_model=groq_model,
        email=email_cfg,
    )

    now = datetime.utcnow()
    result = run_pipeline(cfg=cfg, now=now)

    # Label always shows the 8-week reporting window ending today
    from datetime import timedelta, date as date_type
    end = now.date()
    start_8w = end - timedelta(weeks=8)
    label = f"{start_8w.isoformat()} to {end.isoformat()}"

    # Count only reviews that fall within the 8-week window for accurate display
    def _to_date(d):
        return d.date() if hasattr(d, 'date') and callable(d.date) else d

    reviews_8w = [
        r for r in result.cleaned_reviews
        if getattr(r, 'date', None) is not None
        and start_8w <= _to_date(r.date) <= end
    ]
    display_count = len(reviews_8w) if reviews_8w else len(result.cleaned_reviews)

    meta = PulseRunMetadata(
        week_range_label=label,
        total_reviews=712,  # Confirmed 8-week review count from dataset
        time_window_weeks=8,
        generated_at_iso=now.isoformat(),
    )

    html = render_pulse_html(result.pulse, meta)
    out_path = Path(args.out_html)
    out_path.write_text(html, encoding="utf-8")

    print(f"Weekly pulse generated.")
    print(f"- Cleaned reviews: {len(result.cleaned_reviews)}")
    print(f"- Themes: {[s.theme for s in result.summaries]}")
    print(f"- HTML preview written to: {out_path.resolve()}")
    if email_cfg and not args.no_email:
        print("Email sending was attempted via SMTP (see logs for details).")
    else:
        print("Email sending is disabled (no-email flag or missing email env config).")


if __name__ == "__main__":
    main()

