"""Calendar provider factory and exports."""

from .base import BaseCalendarProvider, CalendarEvent
from .google_api import GoogleCalendarProvider
from .ical_provider import ICalCalendarProvider
from .mock_provider import MockCalendarProvider
from ..config import Config


def get_calendar_provider(config: Config) -> BaseCalendarProvider:
    """Instantiate appropriate calendar provider according to configuration."""
    mode = config.calendar_mode.lower()

    if mode == "google_api":
        return GoogleCalendarProvider(
            credentials_file=config.google_credentials_file,
            token_file=config.google_token_file,
            calendar_ids=config.google_calendar_ids,
        )
    elif mode == "ical":
        return ICalCalendarProvider(urls=config.ical_urls)
    elif mode == "mock":
        return MockCalendarProvider()
    else:
        raise ValueError(f"Unknown calendar mode: {mode}. Choose 'mock', 'google_api', or 'ical'.")


__all__ = [
    "BaseCalendarProvider",
    "CalendarEvent",
    "GoogleCalendarProvider",
    "ICalCalendarProvider",
    "MockCalendarProvider",
    "get_calendar_provider",
]
