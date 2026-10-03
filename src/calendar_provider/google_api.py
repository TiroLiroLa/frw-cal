"""Google Calendar API provider using OAuth 2.0 with dynamic calendar resolution."""

import json
import logging
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .base import BaseCalendarProvider, CalendarEvent

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CACHE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "google_cache.json"


class GoogleCalendarProvider(BaseCalendarProvider):
    """Fetches events using the official Google Calendar REST API v3 with auto-discovery."""

    def __init__(
        self,
        credentials_file: str,
        token_file: str,
        calendar_ids: Optional[List[str]] = None,
    ):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.calendar_ids = calendar_ids or ["primary", "birthdays", "holidays"]
        self.service = None

    def _authenticate(self) -> bool:
        creds = None
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            except Exception as e:
                logger.error(f"Error loading token file {self.token_file}: {e}")

        # Refresh token if expired
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

        if not creds or not creds.valid:
            return False

        try:
            self.service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            return True
        except Exception as e:
            logger.error(f"Failed to build Google Calendar service: {e}")
            return False

    def _get_user_calendars(self) -> List[Dict]:
        """Fetch all calendars available in the user's Google account."""
        try:
            res = self.service.calendarList().list().execute()
            items = res.get("items", [])
            logger.info(f"Retrieved {len(items)} calendars from Google account:")
            for c in items:
                logger.info(f"  -> '{c.get('summary')}' [ID: {c.get('id')}]")
            return items
        except Exception as e:
            logger.warning(f"Could not list account calendars: {e}")
            return []

    def _resolve_calendar_targets(self, user_calendars: List[Dict]) -> List[Tuple[str, str, str]]:
        """Resolves configured aliases ('birthdays', 'holidays', 'primary') to actual calendar IDs.
        
        Returns a list of tuples: (calendar_id, display_name, category)
        where category is 'primary', 'birthday', 'holiday', or 'general'.
        """
        targets = []
        cals_by_id = {c.get("id"): c for c in user_calendars}

        for req in self.calendar_ids:
            req_clean = req.strip()
            req_lower = req_clean.lower()

            # 1. Primary
            if req_lower == "primary":
                targets.append(("primary", "Principal", "primary"))
                continue

            # 2. Birthdays alias
            if req_lower in ("birthdays", "aniversarios", "aniversários", "birthday"):
                found = False
                for c in user_calendars:
                    summary = c.get("summary", "").lower()
                    cid = c.get("id", "").lower()
                    if ("aniversário" in summary or "aniversario" in summary or
                            "birthday" in summary or "contacts" in cid):
                        targets.append((c.get("id"), c.get("summary", "Aniversários"), "birthday"))
                        found = True
                        break
                if not found:
                    # Fallback to standard Google Contacts virtual calendar ID
                    targets.append(
                        ("addressbook#contacts@group.v.calendar.google.com", "Aniversários (Contatos)", "birthday")
                    )
                continue

            # 3. Holidays alias
            if req_lower in ("holidays", "feriados", "feriado"):
                found = False
                for c in user_calendars:
                    summary = c.get("summary", "").lower()
                    cid = c.get("id", "").lower()
                    if "feriado" in summary or "holiday" in summary or "holiday" in cid:
                        targets.append((c.get("id"), c.get("summary", "Feriados"), "holiday"))
                        found = True
                        break
                if not found:
                    # Fallback to standard Brazilian holiday calendar ID
                    targets.append(
                        ("pt-br.brazilian#holiday@group.v.calendar.google.com", "Feriados no Brasil", "holiday")
                    )
                continue

            # 4. Auto-correct common typo in Brazilian holiday calendar
            if "pt.brazilian#holiday" in req_clean:
                req_clean = req_clean.replace("pt.brazilian", "pt-br.brazilian")

            # 5. Direct ID or summary match
            category = "general"
            if "contacts" in req_clean or "anivers" in req_lower:
                category = "birthday"
            elif "holiday" in req_clean or "feriado" in req_lower:
                category = "holiday"

            name = cals_by_id.get(req_clean, {}).get("summary", req_clean)
            targets.append((req_clean, name, category))

        return targets

    def get_events(self, start_date: date, end_date: date) -> List[CalendarEvent]:
        events: List[CalendarEvent] = []

        if not self._authenticate():
            logger.warning("Google Calendar authentication failed. Falling back to cache.")
            return self._load_cache(start_date, end_date)

        # RFC3339 format with 'Z'
        time_min = datetime.combine(start_date, time.min).isoformat() + "Z"
        time_max = datetime.combine(end_date, time.max).isoformat() + "Z"

        user_calendars = self._get_user_calendars()
        targets = self._resolve_calendar_targets(user_calendars)

        fetched_any = False

        for cal_id, cal_name, category in targets:
            try:
                logger.info(f"Querying Google Calendar '{cal_name}' [ID: {cal_id}]...")

                # First try with orderBy='startTime' and singleEvents=True
                items = []
                try:
                    res = (
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
                    items = res.get("items", [])
                except Exception as e_order:
                    # Some virtual/contact calendars reject orderBy='startTime'
                    logger.debug(f"Query with orderBy failed for '{cal_name}' ({e_order}), retrying without orderBy...")
                    res = (
                        self.service.events()
                        .list(
                            calendarId=cal_id,
                            timeMin=time_min,
                            timeMax=time_max,
                            maxResults=50,
                            singleEvents=True,
                        )
                        .execute()
                    )
                    items = res.get("items", [])

                logger.info(f"Retrieved {len(items)} events from '{cal_name}'.")

                for item in items:
                    event = self._parse_google_event(item, cal_id, cal_name, category)
                    if event:
                        events.append(event)
                fetched_any = True

            except Exception as e:
                logger.warning(f"Could not fetch events from calendar '{cal_name}' ({cal_id}): {e}")

        if fetched_any:
            # Deduplicate events occurring across multiple calendars (e.g., primary + birthdays)
            unique_events: List[CalendarEvent] = []
            seen_indices = {}
            for ev in events:
                key = (ev.summary.strip().lower(), ev.start.date())
                if key not in seen_indices:
                    seen_indices[key] = len(unique_events)
                    unique_events.append(ev)
                else:
                    # If current duplicate has richer tags (birthday/holiday), keep the richer one
                    existing_idx = seen_indices[key]
                    if (ev.is_birthday or ev.is_holiday) and not (unique_events[existing_idx].is_birthday or unique_events[existing_idx].is_holiday):
                        unique_events[existing_idx] = ev

            events = unique_events
            self._save_cache(events)
            events.sort(key=lambda ev: ev.start)
            return events
        else:
            return self._load_cache(start_date, end_date)

    def _parse_google_event(
        self, item: dict, cal_id: str, cal_name: str, category: str
    ) -> Optional[CalendarEvent]:
        try:
            summary = item.get("summary", "Sem título")
            start_raw = item.get("start", {})
            end_raw = item.get("end", {})

            all_day = False
            if "date" in start_raw:
                all_day = True
                start_d = date.fromisoformat(start_raw["date"])
                start_dt = datetime.combine(start_d, time(0, 0))

                if "date" in end_raw:
                    end_d = date.fromisoformat(end_raw["date"])
                    # In Google Calendar / RFC 5545, end date for all-day events is exclusive (+1 day)
                    if end_d > start_d:
                        end_d = end_d - timedelta(days=1)
                    end_dt = datetime.combine(end_d, time(23, 59, 59))
                else:
                    end_dt = datetime.combine(start_d, time(23, 59, 59))
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

            summary_lower = summary.lower()

            if (category == "birthday" or
                    "contacts" in cal_id or
                    item.get("eventType") == "birthday" or
                    any(k in summary_lower for k in ["aniversário", "aniversario", "bday", "birthday"])):
                is_birthday = True

            if (category == "holiday" or
                    "holiday" in cal_id or
                    "feriado" in summary_lower or
                    "feriado" in cal_name.lower()):
                is_holiday = True

            return CalendarEvent(
                summary=summary,
                start=start_dt,
                end=end_dt,
                all_day=all_day,
                is_birthday=is_birthday,
                is_holiday=is_holiday,
                calendar_name=cal_name,
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
