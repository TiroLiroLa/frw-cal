"""Display driver package and factory function."""

from .base import BaseDisplay
from .epd4in2b_v2 import EPD4in2B_V2
from .mock_display import MockDisplay
from ..config import Config


def get_display(config: Config) -> BaseDisplay:
    """Instantiate display hardware or mock simulator."""
    dtype = config.display_type.lower()

    if dtype == "epaper":
        return EPD4in2B_V2(pins=config.display_pins)
    elif dtype == "mock":
        return MockDisplay(width=config.display_width, height=config.display_height)
    else:
        raise ValueError(f"Unknown display type: {dtype}. Choose 'mock' or 'epaper'.")


__all__ = ["BaseDisplay", "EPD4in2B_V2", "MockDisplay", "get_display"]
