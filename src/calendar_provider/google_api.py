"""Google Calendar API provider using OAuth 2.0."""

import json
import logging
import os
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .base import BaseCalendarProvider, CalendarEvent

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CACHE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "google_cache.json"


class GoogleCalendarProvider(BaseCalendarProvider):
    """Fetches events using the official Google Calendar REST API v3."""

    def __init__(
        self,
        credentials_file: str,
        token_file: str,
        calendar_ids: Optional[List[str]] = None,
    ):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.calendar_ids = calendar_ids or ["primary"]
        self.service = None

    def _authenticate(self) -> bool:
        creds = None
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            except Exception as e:
                logger.error(f"Error loading token file {self.token_file}: {e}")

        # If there are no valid credentials, try refresh or prompt
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired Google Calendar access token...")
                    creds.refresh(Request())
                    with open(self.token_file, "w") as token:
                        token.write(creds.to_json())
                except Exception as e:
                    logger.error(f"Error refreshing token: {e}")
                    creds = None
            else:
                if not os.path.exists(self.credentials_file):
                    logger.error(
                        f"Credentials file '{self.credentials_file}' not found. "
                        "Please configure OAuth credentials or run src/auth.py."
                    )
                    return False

        if not creds or not creds.valid:
            return False

        try:
            self.service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            return True
        except Exception as e:
            logger.error(f"Failed to build Google Calendar service: {e}")
            return False

    def get_events(self, start_date: date, end_date: date) -> List[CalendarEvent]:
        events: List[CalendarEvent] = []

        if not self._authenticate():
            logger.warning("Google Calendar authentication failed. Falling back to cache.")
            return self._load_cache(start_date, end_date)

        # RFC3339 format with 'Z'
        time_min = datetime.combine(start_date, time.min).isoformat() + "Z"
        time_max = datetime.combine(end_date, time.max).isoformat() + "Z"

        fetched_any = False

        for cal_id in self.calendar_ids:
            try:
                logger.info(f"Querying Google Calendar: {cal_id}")
                events_result = (
                    self.service.events()
                    .list(
                        calendarId=cal_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        maxResults=50,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )

                items = events_result.get("items", [])
                logger.info(f"Found {len(items)} events in {cal_id}")

                for item in items:
                    event = self._parse_google_event(item, cal_id)
                    if event:
                        events.append(event)
                fetched_any = True
            except Exception as e:
                logger.error(f"Error fetching from calendar '{cal_id}': {e}")

        if fetched_any:
            self._save_cache(events)
            events.sort(key=lambda ev: ev.start)
            return events
        else:
            return self._load_cache(start_date, end_date)

    def _parse_google_event(self, item: dict, cal_id: str) -> Optional[CalendarEvent]:
        try:
            summary = item.get("summary", "Sem título")
            start_raw = item.get("start", {})
            end_raw = item.get("end", {})

            all_day = False
            if "date" in start_raw:
                # All day event (YYYY-MM-DD)
                all_day = True
                start_d = date.fromisoformat(start_raw["date"])
                start_dt = datetime.combine(start_d, time(0, 0))

                if "date" in end_raw:
                    end_d = date.fromisoformat(end_raw["date"])
                    end_dt = datetime.combine(end_d, time(23, 59))
                else:
                    end_dt = datetime.combine(start_d, time(23, 59))
            elif "dateTime" in start_raw:
                start_iso = start_raw["dateTime"]
                start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                if start_dt.tzinfo is not None:
                    start_dt = start_dt.astimezone().replace(tzinfo=None)

                if "dateTime" in end_raw:
                    end_iso = end_raw["dateTime"]
                    end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
                    if end_dt.tzinfo is not None:
                        end_dt = end_dt.astimezone().replace(tzinfo=None)
                else:
                    end_dt = start_dt
            else:
                return None

            # Detect birthday or holiday
            is_birthday = False
            is_holiday = False

            if "contacts" in cal_id or item.get("eventType") == "birthday":
                is_birthday = True

            summary_lower = summary.lower()
            if any(k in summary_lower for k in ["aniversário", "aniversario", "bday", "birthday"]):
                is_birthday = True

            if "holiday" in cal_id or "feriado" in summary_lower:
                is_holiday = True

            return CalendarEvent(
                summary=summary,
                start=start_dt,
                end=end_dt,
                all_day=all_day,
                is_birthday=is_birthday,
                is_holiday=is_holiday,
                calendar_name=cal_id,
                description=item.get("description"),
                location=item.get("location"),
            )
        except Exception as e:
            logger.debug(f"Failed to parse Google event: {e}")
            return None

    def _save_cache(self, events: List[CalendarEvent]):
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "summary": e.summary,
                    "start": e.start.isoformat(),
                    "end": e.end.isoformat(),
                    "all_day": e.all_day,
                    "is_birthday": e.is_birthday,
                    "is_holiday": e.is_holiday,
                    "calendar_name": e.calendar_name,
                    "location": e.location,
                }
                for e in events
            ]
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save Google cache: {e}")

    def _load_cache(self, start_date: date, end_date: date) -> List[CalendarEvent]:
        if not CACHE_FILE.exists():
            return []
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            events = []
            for item in data:
                ev = CalendarEvent(
                    summary=item["summary"],
                    start=datetime.fromisoformat(item["start"]),
                    end=datetime.fromisoformat(item["end"]),
                    all_day=item.get("all_day", False),
                    is_birthday=item.get("is_birthday", False),
                    is_holiday=item.get("is_holiday", False),
                    calendar_name=item.get("calendar_name"),
                    location=item.get("location"),
                )
                if ev.end.date() >= start_date and ev.start.date() <= end_date:
                    events.append(ev)
            events.sort(key=lambda ev: ev.start)
            return events
        except Exception as e:
            logger.error(f"Failed to load Google cache: {e}")
            return []
