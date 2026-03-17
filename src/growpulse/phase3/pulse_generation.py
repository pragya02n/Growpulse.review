from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional, Sequence

from ..phase1_ingestion import CleanedReview
from ..phase2_classification import ThemeSummary, ThemedReview


@dataclass
class PulseConfig:
    """Configuration for weekly pulse generation."""

    top_n_themes: int = 3
    max_quotes: int = 3
    max_actions: int = 3
    max_reviews_per_theme: int = 20
    # Groq configuration
    groq_api_key: Optional[str] = None
    groq_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"


@dataclass
class WeeklyPulse:
    title: str
    body_markdown: str
    top_themes: List[ThemeSummary]
    quotes: List[str]
    actions: List[str]


def select_top_themes(
    summaries: Sequence[ThemeSummary],
    top_n: int,
) -> List[ThemeSummary]:
    """Pick the top N themes by count (already sorted in Phase 2), excluding 'other'."""
    filtered = [s for s in summaries if s.theme.lower() != "other"]
    return list(filtered[:top_n])


def preselect_reviews_for_prompt(
    themed_reviews: Iterable[ThemedReview],
    top_themes: Sequence[ThemeSummary],
    max_per_theme: int,
) -> List[ThemedReview]:
    """Select a bounded set of reviews per top theme for prompting."""
    selected: List[ThemedReview] = []
    remaining_per_theme = {t.theme: max_per_theme for t in top_themes}

    for tr in themed_reviews:
        theme = tr.theme
        if theme not in remaining_per_theme:
            continue
        if remaining_per_theme[theme] <= 0:
            continue
        selected.append(tr)
        remaining_per_theme[theme] -= 1

    return selected


def _build_groq_prompt(
    week_start: date,
    week_end: date,
    theme_summaries: Sequence[ThemeSummary],
    sample_reviews: Sequence[ThemedReview],
    cfg: PulseConfig,
) -> str:
    lines: List[str] = []
    lines.append(
        "You are an analyst generating a one-page 'Weekly Pulse' note "
        "for the Groww investment app, based on anonymized user reviews."
    )
    lines.append("")
    lines.append(
        "Strict rules:\n"
        f"- Focus only on the past week: {week_start.isoformat()} to {week_end.isoformat()}.\n"
        "- Never reveal personally identifiable information (PII). If you detect any, redact it.\n"
        f"- Output exactly {cfg.top_n_themes} distinct themes.\n"
        f"- Output exactly {cfg.max_quotes} anonymized user quotes that DIRECTLY ALIGN with the top themes.\n"
        f"- Output exactly {cfg.max_actions} strategic action ideas.\n"
        "- Emphasize readability, dashboard-like formatting, and clarity.\n"
    )
    lines.append("Theme metrics (pre-computed):")
    for s in theme_summaries:
        lines.append(
            f"- Theme: {s.theme} | reviews: {s.count} | avg rating: {s.average_rating:.2f}"
        )
    lines.append("")
    lines.append("Sample anonymized reviews grouped by theme:")
    current_theme = None
    idx = 1
    for tr in sample_reviews:
        if tr.theme != current_theme:
            current_theme = tr.theme
            lines.append(f"\n### Theme: {current_theme}")
        r = tr.review
        lines.append(f"- [{idx}] rating={r.rating} title='{r.title_clean}' text='{r.text_clean}'")
        idx += 1

    lines.append(
        "\nGenerate a detailed JSON object representing the weekly pulse dashboard. MUST output strictly valid JSON, no markdown formatting outside of the JSON.\n"
        "Schema requirement:\n"
        "{\n"
        '  "sentiment_score": float,\n'
        '  "themes": [\n'
        '    {\n'
        '      \"name\": \"Theme Name\",\n'
        '      \"mentions\": int,\n'
        '      \"priority\": \"CRITICAL\" | \"HIGH\" | \"MEDIUM\",\n'
        '      \"percentage_change\": \"str\",\n'
        '      \"action_text\": \"str\"\n'
        '    }\n'
        '  ],\n'
        '  "weekly_comparison": [\n'
        '    {\n'
        '      \"week_label\": \"str (e.g. Mar 09 - Mar 15)\",\n'
        '      \"volume\": int,\n'
        '      \"sentiment\": float,\n'
        '      \"wow_change\": \"str (e.g. +12%)\"\n'
        '    }\n'
        '  ],\n'
        '  "daily_breakdown": [\n'
        '    {\n'
        '      \"day\": \"Mon\",\n'
        '      \"volume\": int,\n'
        '      \"prevailing_issue\": \"str\"\n'
        '    }\n'
        '  ],\n'
        '  "severity_scores": [\n'
        '    {\n'
        '      \"theme\": \"str\",\n'
        '      \"frequency\": int,\n'
        '      \"sentiment_impact\": float,\n'
        '      \"business_impact\": float,\n'
        '      \"total_severity\": float\n'
        '    }\n'
        '  ],\n'
        '  "feature_impact": [\n'
        '    {\n'
        '      \"feature\": \"str\",\n'
        '      \"status\": \"Improving\" | \"Declining\" | \"Stable\",\n'
        '      \"sentiment\": float\n'
        '    }\n'
        '  ],\n'
        '  "theme_deep_dives": [\n'
        '    {\n'
        '      \"theme_name\": \"str\",\n'
        '      \"root_cause\": \"str\",\n'
        '      \"impact_analysis\": \"str\"\n'
        '    }\n'
        '  ],\n'
        '  "quotes": [\n'
        '    "quote 1",\n'
        '    "quote 2",\n'
        '    "quote 3"\n'
        '  ],\n'
        '  "actions": [\n'
        '    {\n'
        '      "text": "str",\n'
        '      "priority_label": "str",\n'
        '      "rice_score": {\n'
        '         "total": "str"\n'
        '      }\n'
        '    }\n'
        '  ]\n'
        "}\n"
    )

    return "\n".join(lines)


class GroqClient:
    """
    Thin wrapper for Groq LLM calls.

    This is intentionally minimal and depends on the `groq` Python client
    (to be added once an API key is available and the dependency is desired).
    """

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        # Lazy import to avoid optional dependency issues until configured.
        try:  # pragma: no cover - environment-specific
            from groq import Groq  # type: ignore

            self._client = Groq(api_key=api_key)
        except Exception as exc:  # pragma: no cover - environment-specific
            raise RuntimeError(
                "Groq client is not available. Install the `groq` package "
                "and ensure the API key is correct."
            ) from exc

    def generate_pulse(self, prompt: str) -> str:
        """
        Call Groq chat completion with a single system/user-style prompt and
        return the assistant content as Markdown text.
        """
        # Deliberately light implementation; exact schema may be adjusted
        # once the Groq client is wired with a real key.
        completion = self._client.chat.completions.create(  # type: ignore[attr-defined]
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a concise data processor that ONLY outputs valid JSON representing a dashboard state. Ensure values are accurate."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        return completion.choices[0].message.content  # type: ignore[index]


def generate_weekly_pulse(
    week_start: date,
    week_end: date,
    themed_reviews: Iterable[ThemedReview],
    theme_summaries: Sequence[ThemeSummary],
    cfg: PulseConfig,
    client: Optional[GroqClient] = None,
) -> WeeklyPulse:
    """
    High-level orchestration for Phase 3.

    - Selects top N themes.
    - Pre-selects a bounded set of reviews per theme.
    - Builds a structured prompt.
    - Calls Groq LLM (if a client is provided) to generate the Markdown note.

    If `client` is None, this function only builds the title and raises
    a clear error to avoid accidental network calls.
    """
    top_themes = select_top_themes(theme_summaries, cfg.top_n_themes)
    samples = preselect_reviews_for_prompt(themed_reviews, top_themes, cfg.max_reviews_per_theme)
    prompt = _build_groq_prompt(week_start, week_end, top_themes, samples, cfg)

    title = f"Groww App – Weekly Pulse, Week of {week_start.isoformat()} to {week_end.isoformat()}"

    if client is None:
        raise RuntimeError(
            "GroqClient is not provided. Construct a GroqClient with a valid API key "
            "and pass it to generate_weekly_pulse."
        )

    body_md = client.generate_pulse(prompt)

    # For now, we return empty lists for quotes/actions; in a later step we can
    # parse the Markdown or request a machine-readable side-channel structure.
    return WeeklyPulse(
        title=title,
        body_markdown=body_md,
        top_themes=list(top_themes),
        quotes=[],
        actions=[],
    )

