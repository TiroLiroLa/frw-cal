"""Configuration loader and validation for frw-cal."""

import os
from pathlib import Path
from typing import Any, Dict, List
import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
EXAMPLE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.example.yaml"


class Config:
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @classmethod
    def load(cls, config_path: Path = None) -> "Config":
        if config_path is None:
            config_path = DEFAULT_CONFIG_PATH

        if not config_path.exists():
            if EXAMPLE_CONFIG_PATH.exists():
                with open(EXAMPLE_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                return cls(data)
            return cls({})

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(data)

    # General
    @property
    def language(self) -> str:
        return self._data.get("general", {}).get("language", "pt_BR")

    @property
    def timezone(self) -> str:
        return self._data.get("general", {}).get("timezone", "America/Sao_Paulo")

    @property
    def date_format(self) -> str:
        return self._data.get("general", {}).get("date_format", "%d/%m/%Y")

    @property
    def time_format(self) -> str:
        return self._data.get("general", {}).get("time_format", "%H:%M")

    # Display
    @property
    def display_type(self) -> str:
        return self._data.get("display", {}).get("type", "mock")

    @property
    def display_driver(self) -> str:
        return self._data.get("display", {}).get("driver", "ssd1683")

    @property
    def display_width(self) -> int:
        return self._data.get("display", {}).get("width", 400)

    @property
    def display_height(self) -> int:
        return self._data.get("display", {}).get("height", 300)

    @property
    def display_rotation(self) -> int:
        return self._data.get("display", {}).get("rotation", 0)

    @property
    def display_pins(self) -> Dict[str, int]:
        default_pins = {"cs": 8, "dc": 25, "rst": 17, "busy": 24}
        return self._data.get("display", {}).get("pins", default_pins)

    # Calendar
    @property
    def calendar_mode(self) -> str:
        return self._data.get("calendar", {}).get("mode", "mock")

    @property
    def google_credentials_file(self) -> str:
        path = self._data.get("calendar", {}).get("google_api", {}).get(
            "credentials_file", "config/credentials.json"
        )
        if not os.path.isabs(path):
            base_dir = Path(__file__).resolve().parent.parent
            path = str(base_dir / path)
        return path

    @property
    def google_token_file(self) -> str:
        path = self._data.get("calendar", {}).get("google_api", {}).get(
            "token_file", "config/token.json"
        )
        if not os.path.isabs(path):
            base_dir = Path(__file__).resolve().parent.parent
            path = str(base_dir / path)
        return path

    @property
    def google_calendar_ids(self) -> List[str]:
        return self._data.get("calendar", {}).get("google_api", {}).get(
            "calendar_ids", ["primary"]
        )

    @property
    def ical_urls(self) -> List[str]:
        return self._data.get("calendar", {}).get("ical", {}).get("urls", [])

    @property
    def max_upcoming_events(self) -> int:
        return self._data.get("calendar", {}).get("max_upcoming_events", 5)

    @property
    def lookahead_days(self) -> int:
        return self._data.get("calendar", {}).get("lookahead_days", 14)

    # Weather
    @property
    def weather_enabled(self) -> bool:
        return self._data.get("weather", {}).get("enabled", True)

    @property
    def weather_latitude(self) -> float:
        return float(self._data.get("weather", {}).get("latitude", -23.5505))

    @property
    def weather_longitude(self) -> float:
        return float(self._data.get("weather", {}).get("longitude", -46.6333))

    @property
    def weather_city_name(self) -> str:
        return self._data.get("weather", {}).get("city_name", "São Paulo")

    # Refresh
    @property
    def refresh_interval_minutes(self) -> int:
        return self._data.get("refresh", {}).get("interval_minutes", 30)

    @property
    def active_hours_start(self) -> int:
        return self._data.get("refresh", {}).get("active_hours_start", 6)

    @property
    def active_hours_end(self) -> int:
        return self._data.get("refresh", {}).get("active_hours_end", 23)

    @property
    def midnight_update(self) -> bool:
        return self._data.get("refresh", {}).get("midnight_update", True)
