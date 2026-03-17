from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from .phase1_ingestion import CleanedReview, ingest_and_clean_reviews
from .phase2_classification import (
    ThemeSummary,
    ThemedReview,
    classify_reviews,
    summarize_themes,
)
from .phase3.pulse_generation import GroqClient, PulseConfig, WeeklyPulse, generate_weekly_pulse
from .phase4.delivery import EmailConfig, Mailer, PulseRunMetadata, build_email_message


@dataclass
class PipelineConfig:
    csv_path: Path
    time_window_weeks: int = 12
    groq_api_key: Optional[str] = None
    groq_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    email: Optional[EmailConfig] = None


@dataclass
class PipelineResult:
    cleaned_reviews: List[CleanedReview]
    themed_reviews: List[ThemedReview]
    summaries: List[ThemeSummary]
    pulse: WeeklyPulse


def _week_range(now: Optional[datetime] = None) -> tuple[date, date, str]:
    """Compute a simple week range label (last 7 days)."""
    now_dt = now or datetime.utcnow()
    end = now_dt.date()
    start = end - timedelta(days=6)
    label = f"{start.isoformat()} to {end.isoformat()}"
    return start, end, label


def run_pipeline(
    cfg: PipelineConfig,
    now: Optional[datetime] = None,
    groq_client: Optional[GroqClient] = None,
    mailer: Optional[Mailer] = None,
) -> PipelineResult:
    """
    Connect all phases end-to-end.

    - Phase 1: ingest & clean reviews from CSV.
    - Phase 2: classify into themes and summarize.
    - Phase 3: generate weekly pulse via Groq.
    - Phase 4: build (and optionally send) email.
    """
    # Phase 1
    cleaned = ingest_and_clean_reviews(cfg.csv_path, time_window_weeks=cfg.time_window_weeks, now=now)

    # Phase 2
    themed = classify_reviews(cleaned)
    summaries = summarize_themes(themed)

    # Skip if nothing to summarize
    week_start, week_end, label = _week_range(now)
    pulse_cfg = PulseConfig(groq_api_key=cfg.groq_api_key, groq_model=cfg.groq_model)

    client = groq_client
    if client is None:
        if not cfg.groq_api_key:
            raise RuntimeError("Groq API key not provided and no GroqClient supplied.")
        client = GroqClient(api_key=cfg.groq_api_key, model=cfg.groq_model)

    pulse = generate_weekly_pulse(
        week_start=week_start,
        week_end=week_end,
        themed_reviews=themed,
        theme_summaries=summaries,
        cfg=pulse_cfg,
        client=client,
    )

    # Phase 4: email drafting & optional sending
    if cfg.email is not None:
        meta = PulseRunMetadata(
            week_range_label=label,
            total_reviews=len(cleaned),
            time_window_weeks=cfg.time_window_weeks,
            generated_at_iso=(now or datetime.utcnow()).isoformat(),
        )
        email_msg = build_email_message(cfg.email, pulse, meta)
        if mailer is None:
            mailer = Mailer(cfg.email)
        mailer.send(email_msg)

    return PipelineResult(
        cleaned_reviews=cleaned,
        themed_reviews=themed,
        summaries=summaries,
        pulse=pulse,
    )

