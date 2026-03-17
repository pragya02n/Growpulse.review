## Automated App Review "Weekly Pulse" Pipeline – System Architecture

This document describes the architecture for the **Groww App – Automated Weekly Pulse** system. The goal is to transform raw user reviews (from a local CSV) into a privacy-safe, concise, and actionable weekly note that can be emailed to a stakeholder alias.

The design is **file-system friendly** (runs on a local machine or a simple server where CSV files are accessible) and uses the **Groq LLM** as the primary model provider for all LLM-powered steps (classification, summarization, quote selection, and action idea generation).

---

## High-Level Overview

- **Input**: Local CSV file of Groww app reviews for the last 8–12 weeks, with at least: `rating`, `title`, `text`, `date`, and optionally `platform`, `language`, `device info`.
- **Core Responsibilities**:
  - Ingest and filter reviews by time window.
  - Strictly remove PII from the text.
  - Classify reviews into up to **5 core themes** (e.g., onboarding, KYC, payments, withdrawals, app performance).
  - Summarize and prioritize themes into a **one-page weekly pulse note**:
    - Top 3 themes.
    - 3 anonymized verbatim quotes.
    - 3 strategic action ideas.
  - Draft an **email** with the weekly pulse note to a configured alias.
- **Output**: 
  - A rendered weekly note (Markdown/HTML/plain text).
  - An email draft ready to send (via SMTP / mail API).

The system is divided into **four logical phases**:

1. Phase 1: Local Data Ingestion & PII Cleaning  
2. Phase 2: Theme Classification  
3. Phase 3: Weekly Pulse Generation  
4. Phase 4: Email Drafting & Delivery  

Additionally, there are **cross-cutting** concerns:

- Configuration & Secrets Management  
- Logging, Observability & Auditability  
- Evaluation & Testing (manual spot checks, LLM output sanity checks)

---

## Phase 1: Local Data Ingestion & PII Cleaning

### Objectives

- Read the local CSV containing app reviews.
- Filter reviews to the configured **time window** (e.g., last 8–12 weeks).
- Normalize and validate the review schema.
- **Aggressively remove PII** (names, phone numbers, emails, account IDs, etc.) *before* anything is sent to the LLM.

### Inputs & Outputs

- **Input**: Local CSV file path (configurable).
- **Output**: In-memory collection / serialized file of **cleaned reviews**:
  - `review_id` (synthetic ID).
  - `date` (normalized).
  - `rating` (normalized numeric).
  - `title_clean` (PII-stripped).
  - `text_clean` (PII-stripped).
  - Optional: `source_meta` (platform, language, version, etc. – likewise cleaned).

### Components

- **Config Loader**
  - Reads configuration from environment variables / config file:
    - `REVIEWS_CSV_PATH`
    - `TIME_WINDOW_WEEKS` (default: 8–12).
    - LLM provider keys (only used in later phases).
    - Email settings (SMTP host, port, sender, recipient alias, etc.).

- **CSV Reader**
  - Reads the CSV with schema validation:
    - Enforces minimum columns: `rating`, `title`, `text`, `date`.
    - Handles encoding issues (UTF-8 as default).
  - Applies time filter on `date`.

- **Text Normalizer**
  - Lowercasing/Unicode normalization.
  - Trimming whitespace, collapsing repeated punctuation.
  - Optional: language detection to drop unsupported languages.

- **PII Detection & Redaction Engine**
  - Uses deterministic rules and regex-based detectors:
    - Email addresses.
    - Phone numbers.
    - PAN/Aadhaar-style patterns (if relevant).
    - Account IDs, reference IDs, transaction IDs.
    - URLs and social handles.
  - Optional ML/NER model for names/locations (if required and available).
  - Replaces PII with generic tokens:
    - e.g., `[EMAIL]`, `[PHONE]`, `[ACCOUNT_ID]`, `[NAME]`.
  - Retains semantic content but ensures **no raw PII** appears in text sent to the LLM.

- **PII Compliance Guard**
  - Post-cleaning validation layer:
    - Re-runs PII checks on cleaned text.
    - If residual PII is found:
      - Either re-mask or drop the affected review from downstream processing.

### Data Storage/Flow

- Short-lived in-memory structures are fine for moderate volumes.
- Optional:
  - Persist a **sanitized reviews file** (e.g., `sanitized_reviews_<week>.jsonl`) for auditing and re-runs.

---

## Phase 2: Theme Classification

### Objectives

- Group all cleaned reviews into **up to 5 core themes**.
- Keep themes stable and interpretable (e.g., onboarding, KYC, payments, withdrawals, performance, UX).
- Allow for a mix of **rule-based** and **LLM-assisted** approaches.

### Inputs & Outputs

- **Input**: List of cleaned reviews from Phase 1.
- **Output**:
  - A small, stable set of **theme definitions** (max 5).
  - For each review:
    - Assigned primary theme.
    - Optional secondary theme.
  - Aggregated theme metrics:
    - Review count per theme.
    - Average rating per theme.
    - Distribution across the time window.

### Components

- **Theme Taxonomy Definition**
  - Configurable list of allowed themes (seed list), e.g.:
    - `onboarding`, `kyc`, `payments`, `withdrawals`, `app_performance`, `other`.
  - Stored in a config file (e.g., `themes.yaml`) so product teams can adjust.

- **Feature Extraction Layer**
  - Converts cleaned title+text to simple features:
    - Keyword presence.
    - Rating bucket (e.g., 1–2 = negative, 3 = neutral, 4–5 = positive).
  - Optional: vector embeddings using local or remote model (if available).

- **Classifier Engine**
  - **Option A: Rule-based baseline**:
    - Hard-coded keyword patterns per theme (e.g., “KYC”, “PAN”, “Aadhaar” → `kyc`).
  - **Option B: LLM-assisted classification**:
    - Batch multiple reviews into a single prompt, instructing LLM to assign one of the predefined themes to each review using a structured output format (e.g., JSON).
  - A hybrid strategy can:
    - Apply rule-based classification first.
    - Defer only “uncertain/other” reviews to the LLM.

- **Theme Consolidator**
  - Ensures the final number of distinct themes \(\leq 5\).
  - Optionally merges low-volume themes into `other` or nearest high-volume theme.
  - Produces a **ranked list of themes** by volume and severity.

### Data Storage/Flow

- Output can remain in memory or be written as:
  - `classified_reviews_<week>.jsonl` (review_id, theme_id, rating, date, text_clean).
  - `themes_summary_<week>.json` (per-theme stats).

---

## Phase 3: Weekly Pulse Generation (Groq LLM–backed)

### Objectives

- From classified and cleaned reviews, generate a single **one-page weekly note** containing:
  - Top 3 themes with concise descriptions and metrics.
  - 3 anonymized, representative user quotes.
  - 3 strategic, product-facing action ideas.

### Inputs & Outputs

- **Input**:
  - Classified reviews from Phase 2.
  - Theme metrics and ranking.
  - Config (e.g., maximum token limits, style preferences, tone guidelines).
- **Output**:
  - Weekly pulse note in a text format (e.g., Markdown), containing:
    - Title (e.g., “Groww App – Weekly Pulse, Week of 2026-03-16”).
    - Sections for Top 3 themes.
    - Selected quotes.
    - Action recommendations.

### Components

- **Content Pre-Selector**
  - Chooses a subset of reviews used to prompt the LLM:
    - For each top theme, select a small, balanced sample of reviews (e.g., 10–20 per theme).
    - Filter out extremely short/low-information reviews.
  - Ensures total prompt size stays under the configured token limit.

- **Quote Selector**
  - Scores reviews per theme for:
    - Representativeness (typical of the cluster).
    - Clarity and emotional salience.
  - Either:
    - Uses heuristics (review length, rating, sentiment words).
    - Or asks the LLM to select 3 best quotes from a supplied set.
  - Enforces **no PII** in selected quotes by re-running PII guard on final choices.

- **LLM Prompt Builder**
  - Constructs structured prompts to the LLM with:
    - Clear system message: privacy constraints, tone guidelines, format requirements.
    - Example response (few-shot) to standardize output.
    - Input sections:
      - Summary of theme metrics.
      - Balanced sample of anonymized reviews grouped by theme.
  - Specifies very explicit instructions:
    - Limit to **Top 3 themes** based on impact (volume, severity).
    - Include **exactly 3 user quotes** (fully anonymized).
    - Include **exactly 3 action ideas**.
    - Keep entire note within a one-page constraint (e.g., ~500–700 words).

- **LLM Client (Groq)**
  - Thin wrapper over the **Groq** LLM provider:
    - Handles Groq API key and base URL from environment.
    - Encapsulates model name/parameters for different tasks (e.g., theme summarization vs. quote selection).
    - Implements retry/backoff on transient failures.
    - Enforces maximum cost and rate limits.

- **Response Validator & Post-Processor**
  - Validates LLM output format:
    - All required sections present.
    - Exactly 3 quotes and 3 actions.
  - Re-runs **PII Compliance Guard** on the final note:
    - If PII is detected, can:
      - Auto-redact.
      - Or re-prompt the LLM with stricter instructions and a smaller sample.
  - Converts the final note into:
    - Markdown or HTML for email body.
    - Optional text log file (`weekly_pulse_<week>.md`).

---

## Phase 4: UI, Email Drafting & Delivery

### Objectives

- Provide a simple **UI page** to run and view the weekly pulse.
- Automatically draft and (optionally) send the weekly pulse email to a configured alias.

### Inputs & Outputs

- **Input**:
  - Final weekly pulse note (Markdown/HTML/string).
  - Metadata for the run (week/date range, counts per theme, run status).
  - Email configuration (sender, recipient alias, subject template).
- **Output**:
  - A rendered UI page showing the latest (and recent) weekly pulses.
  - Sent email (if auto-send is enabled) **or**
  - Draft email ready for manual review/approval.

### Components

- **Weekly Pulse UI Page**
  - A lightweight web UI (single-page app or simple server-rendered page) that:
    - Shows the most recent weekly pulse note (title, Top 3 themes, quotes, actions).
    - Exposes a control to **trigger a new run** of the pipeline (for the current week) when appropriate.
    - Displays basic run metadata (generation time, number of reviews processed, top themes).
  - Backend/API integration:
    - Reads the latest generated `weekly_pulse_<week>.md` (or equivalent persisted format).
    - Optionally lists historical pulses for quick comparison.
  - Authentication/Access:
    - Basic auth or internal-only access (depending on deployment context) to keep internal signals private.

- **Email Template Engine**
  - Wraps the weekly pulse content into a standard template:
    - Subject: e.g., “Groww App – Weekly Pulse | Week of {{date_range}}”.
    - Greeting, short intro, summary at top.
    - Embedded weekly note.
    - Footer with opt-out or comment instructions.

- **Mailer Client**
  - Backend could be:
    - SMTP (e.g., company mail server, Gmail).
    - Email service API (e.g., SendGrid, SES, Outlook API).
  - Configured via environment variables:
    - `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_USE_TLS`, etc.
    - `MAIL_SENDER`, `MAIL_RECIPIENT_ALIAS`.

- **Delivery Controller**
  - Two operating modes:
    - **Draft-only**: write the email body to a local EML/HTML file, or open default mail client with prefilled draft.
    - **Auto-send**: send directly via SMTP/API and log result.
  - Logs:
    - Timestamp, recipient, subject.
    - Whether send succeeded or failed.

---

## Cross-Cutting Concerns

### Configuration & Secrets

- All sensitive data (LLM API keys, SMTP credentials) stored as environment variables or in a secure secrets store.
- `.env` should **never** be committed to version control.
- Provide a `config.example.env` template with non-sensitive sample values.

### Logging & Observability

- Centralized logging with levels: INFO, WARN, ERROR.
- Logged events:
  - CSV ingestion stats (rows read, rows kept after date filter).
  - PII cleaning stats (redaction counts).
  - Classification stats (volume per theme).
  - LLM call metadata (token usage, latency, success/failure).
  - Email delivery status.
- Optional:
  - Structured logs in JSON for future ingestion into dashboards.

### Evaluation & QA

- **Offline evaluation**:
  - Periodically sample:
    - Cleaned text for PII leaks.
    - Theme assignments compared to human labels.
  - Maintain a small labeled set of reviews for spot-checking LLM theme accuracy.

- **On-output QA**:
  - Allow a human-in-the-loop step:
    - Option to pause before sending and display the draft in a simple UI or as a local file for review.

---

## Deployment & Execution Model

- **Execution Pattern**
  - Typically run as a **scheduled job**:
    - Weekly (e.g., Monday mornings) via:
      - OS scheduler (cron on Linux/macOS, Task Scheduler on Windows).
      - CI/CD pipeline or lightweight orchestrator.
  - Single-entry CLI command, e.g.:
    - `python run_weekly_pulse.py --config config.yaml`

- **Environment**
  - Initial target: local machine or a small VM with:
    - Access to the reviews CSV path.
    - Network access to LLM provider and mail server.

---

## Error Handling & Failure Modes

- **CSV Load Failures**:
  - Log error with file path and environment.
  - Abort pipeline with a clear message.

- **PII Guard Failures**:
  - If residual PII cannot be reliably removed, abort before any LLM calls.

- **LLM API Failures**:
  - Retry with backoff.
  - If still failing, fall back to:
    - Minimal rule-based summary.
    - Or skip that week but log the failure.

- **Email Delivery Failures**:
  - Retry once or twice.
  - If persistent errors:
    - Save weekly pulse note to disk.
    - Log error and warn user to send manually.

---

## Extensibility Considerations

- Add support for:
  - Multiple apps or product surfaces (tags per app).
  - Multi-lingual reviews (language-specific PII and themes).
  - Richer analytics (trend lines, deltas vs. last week).
- Swap out:
  - LLM providers behind a simple client interface.
  - Mail providers via adapter pattern.

This architecture keeps PII safety, interpretability (themes and quotes), and operational simplicity as first-class concerns while remaining flexible for future product evolution.

