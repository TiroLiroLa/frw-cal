"""iCalendar (.ics) provider for Google Calendar private iCal links."""

import json
import logging
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import List, Optional
import dateutil.parser
import requests
from icalendar import Calendar
from .base import BaseCalendarProvider, CalendarEvent

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "ical_cache.json"


class ICalCalendarProvider(BaseCalendarProvider):
    """Fetches calendar events from Google Calendar's private iCal (.ics) URLs."""

    def __init__(self, urls: List[str]):
        self.urls = urls

    def get_events(self, start_date: date, end_date: date) -> List[CalendarEvent]:
        events: List[CalendarEvent] = []

        if not self.urls:
            logger.warning("No iCal URLs configured.")
            return self._load_cache(start_date, end_date)

        fetched_any = False
        for url in self.urls:
            try:
                logger.info(f"Fetching iCal feed from: {url[:30]}...")
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                parsed = self._parse_ics_content(resp.text, start_date, end_date)
                events.extend(parsed)
                fetched_any = True
            except Exception as e:
                logger.error(f"Error fetching iCal feed: {e}")

        if fetched_any:
            self._save_cache(events)
            events.sort(key=lambda ev: ev.start)
            return events
        else:
            logger.info("Using cached events due to network failure.")
            return self._load_cache(start_date, end_date)

    def _parse_ics_content(
        self, ics_content: str, start_date: date, end_date: date
    ) -> List[CalendarEvent]:
        events: List[CalendarEvent] = []
        try:
            cal = Calendar.from_ical(ics_content)
            for component in cal.walk():
                if component.name == "VEVENT":
                    event = self._convert_component_to_event(component)
                    if event and event.end.date() >= start_date and event.start.date() <= end_date:
                        events.append(event)
        except Exception as e:
            logger.error(f"Error parsing iCalendar content: {e}")
        return events

    def _convert_component_to_event(self, component) -> Optional[CalendarEvent]:
        try:
            summary = str(component.get("summary", "Sem título"))
            dtstart = component.get("dtstart")
            dtend = component.get("dtend")

            if not dtstart:
                return None

            start_val = dtstart.dt
            all_day = False

            if isinstance(start_val, date) and not isinstance(start_val, datetime):
                all_day = True
                start_dt = datetime.combine(start_val, time(0, 0))
                if dtend:
                    end_val = dtend.dt
                    end_dt = datetime.combine(end_val, time(23, 59))
                else:
                    end_dt = datetime.combine(start_val, time(23, 59))
            else:
                # Is datetime
                start_dt = self._normalize_datetime(start_val)
                if dtend:
                    end_dt = self._normalize_datetime(dtend.dt)
                else:
                    end_dt = start_dt

            # Check birthday keywords
            is_birthday = False
            summary_lower = summary.lower()
            if any(k in summary_lower for k in ["aniversário", "aniversario", "bday", "birthday"]):
                is_birthday = True

            description = str(component.get("description", "")) if component.get("description") else None
            location = str(component.get("location", "")) if component.get("location") else None

            return CalendarEvent(
                summary=summary,
                start=start_dt,
                end=end_dt,
                all_day=all_day,
                is_birthday=is_birthday,
                description=description,
                location=location,
            )
        except Exception as e:
            logger.debug(f"Failed to convert event component: {e}")
            return None

    def _normalize_datetime(self, dt: datetime) -> datetime:
        # Convert timezone-aware datetime to naive local datetime
        if dt.tzinfo is not None:
            return dt.astimezone().replace(tzinfo=None)
        return dt

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
                    "location": e.location,
                }
                for e in events
            ]
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save iCal cache: {e}")

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
                    location=item.get("location"),
                )
                if ev.end.date() >= start_date and ev.start.date() <= end_date:
                    events.append(ev)
            events.sort(key=lambda ev: ev.start)
            return events
        except Exception as e:
            logger.error(f"Failed to load iCal cache: {e}")
            return []
