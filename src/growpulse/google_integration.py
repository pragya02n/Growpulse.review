from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from .phase1_ingestion import CleanedReview, _parse_date, _within_window, _ensure_no_pii, _redact_pii

class GoogleSheetsIngestor:
    """Reads reviews from a Google Sheet."""

    def __init__(self, credentials_path: str):
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        self.creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=self.scopes
        )
        self.service = build('sheets', 'v4', credentials=self.creds)

    def fetch_reviews(
        self, 
        spreadsheet_id: str, 
        range_name: str = 'Sheet1!A:Z',
        time_window_weeks: int = 12,
        now: Optional[datetime] = None
    ) -> list[CleanedReview]:
        """
        Fetch reviews from Google Sheets and apply the same cleaning as CSV ingestion.
        Assumes columns: rating, title, text, date (any order, by header).
        """
        sheet = self.service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get('values', [])

        if not values:
            return []

        # Convert to DataFrame for easier processing
        headers = values[0]
        data = values[1:]
        df = pd.DataFrame(data, columns=headers)

        required_cols = {"rating", "title", "text", "date"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Google Sheet missing required columns: {', '.join(sorted(missing))}")

        cleaned_reviews = []
        now_value = now or datetime.utcnow()

        for idx, row in df.iterrows():
            try:
                raw_date = _parse_date(row["date"])
            except Exception:
                continue

            if not _within_window(raw_date, time_window_weeks, now=now_value):
                continue

            try:
                rating = float(row["rating"])
            except Exception:
                continue

            title_raw = str(row.get("title", "") or "")
            text_raw = str(row.get("text", "") or "")

            if not (_ensure_no_pii(title_raw) and _ensure_no_pii(text_raw)):
                continue

            title_clean = _redact_pii(title_raw)
            text_clean = _redact_pii(text_raw)

            if not (_ensure_no_pii(title_clean) and _ensure_no_pii(text_clean)):
                continue

            review_id = f"gsheets-{spreadsheet_id[:8]}-{idx}"

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

class GoogleCalendarSync:
    """Syncs pulse summaries to Google Calendar."""

    def __init__(self, credentials_path: str):
        self.scopes = ['https://www.googleapis.com/auth/calendar']
        self.creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=self.scopes
        )
        self.service = build('calendar', 'v3', credentials=self.creds)

    def create_pulse_event(self, calendar_id: str, title: str, summary: str):
        """Creates a calendar event for the weekly pulse."""
        event = {
            'summary': title,
            'description': summary,
            'start': {
                'dateTime': datetime.utcnow().isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': datetime.utcnow().isoformat() + 'Z', # Zero-duration marker
                'timeZone': 'UTC',
            },
        }
        return self.service.events().insert(calendarId=calendar_id, body=event).execute()
