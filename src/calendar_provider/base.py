"""Base classes and data structures for calendar events."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional


@dataclass
class CalendarEvent:
    summary: str
    start: datetime
    end: datetime
    all_day: bool = False
    is_birthday: bool = False
    is_holiday: bool = False
    calendar_name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None

    @property
    def start_date(self) -> date:
        return self.start.date()

    def is_on_date(self, target_date: date) -> bool:
        """Checks if this event occurs on the given date."""
        return self.start.date() <= target_date <= self.end.date()

    def is_today(self, reference_date: Optional[date] = None) -> bool:
        today = reference_date or date.today()
        return self.is_on_date(today)

    def is_tomorrow(self, reference_date: Optional[date] = None) -> bool:
        from datetime import timedelta
        today = reference_date or date.today()
        tomorrow = today + timedelta(days=1)
        return self.is_on_date(tomorrow)


class BaseCalendarProvider(ABC):
    """Abstract base class for calendar providers."""

    @abstractmethod
    def get_events(self, start_date: date, end_date: date) -> List[CalendarEvent]:
        """Fetch all events occurring between start_date and end_date (inclusive)."""
        pass
