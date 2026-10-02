"""Weather provider using Open-Meteo free API (no API key required)."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import requests

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "weather_cache.json"

# WMO Weather interpretation codes
WMO_DESCRIPTIONS = {
    0: ("Ensolarado", "☀️"),
    1: ("Predom. Ensolarado", "🌤️"),
    2: ("Parcialm. Nublado", "⛅"),
    3: ("Nublado", "☁️"),
    45: ("Nevoeiro", "🌫️"),
    48: ("Nevoeiro rime", "🌫️"),
    51: ("Garoa leve", "🌦️"),
    53: ("Garoa moderada", "🌦️"),
    55: ("Garoa densa", "🌧️"),
    61: ("Chuva leve", "🌧️"),
    63: ("Chuva moderada", "🌧️"),
    65: ("Chuva forte", "🌧️"),
    71: ("Neve leve", "🌨️"),
    80: ("Pancadas de chuva", "🌦️"),
    81: ("Pancadas fortes", "🌧️"),
    95: ("Trovoada", "⛈️"),
}


@dataclass
class WeatherInfo:
    temperature: float
    description: str
    icon: str
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None


class WeatherProvider:
    def __init__(self, latitude: float, longitude: float, enabled: bool = True):
        self.latitude = latitude
        self.longitude = longitude
        self.enabled = enabled

    def get_weather(self) -> Optional[WeatherInfo]:
        if not self.enabled:
            return None

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            current = data.get("current", {})
            temp = float(current.get("temperature_2m", 0.0))
            code = int(current.get("weather_code", 0))

            daily = data.get("daily", {})
            temp_max = daily.get("temperature_2m_max", [None])[0]
            temp_min = daily.get("temperature_2m_min", [None])[0]

            desc, icon = WMO_DESCRIPTIONS.get(code, ("Tempo Estável", "🌤️"))

            info = WeatherInfo(
                temperature=round(temp, 1),
                description=desc,
                icon=icon,
                temp_min=round(temp_min, 1) if temp_min is not None else None,
                temp_max=round(temp_max, 1) if temp_max is not None else None,
            )
            self._save_cache(info)
            return info
        except Exception as e:
            logger.error(f"Error fetching weather from Open-Meteo: {e}")
            return self._load_cache()

    def _save_cache(self, info: WeatherInfo):
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "temperature": info.temperature,
                        "description": info.description,
                        "icon": info.icon,
                        "temp_min": info.temp_min,
                        "temp_max": info.temp_max,
                    },
                    f,
                )
        except Exception as e:
            logger.debug(f"Failed to cache weather: {e}")

    def _load_cache(self) -> Optional[WeatherInfo]:
        if not CACHE_FILE.exists():
            return None
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return WeatherInfo(
                temperature=data["temperature"],
                description=data["description"],
                icon=data["icon"],
                temp_min=data.get("temp_min"),
                temp_max=data.get("temp_max"),
            )
        except Exception:
            return None
