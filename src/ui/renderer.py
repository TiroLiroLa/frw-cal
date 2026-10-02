"""Main UI Renderer: coordinates layout, components, and produces final e-paper image buffers."""

import logging
from datetime import date, datetime
from typing import List, Optional, Tuple
from PIL import Image

from .canvas import EPaperCanvas
from .components.header import render_header
from .components.month_grid import render_month_grid
from .components.event_list import render_event_list
from .components.status_bar import render_status_bar
from ..calendar_provider.base import CalendarEvent
from ..weather import WeatherInfo
from ..config import Config

logger = logging.getLogger(__name__)


class CalendarRenderer:
    """Renders the smart calendar interface for 400x300 e-paper displays."""

    def __init__(self, config: Config):
        self.config = config
        self.width = config.display_width
        self.height = config.display_height
        self.rotation = config.display_rotation

    def render(
        self,
        current_date: date,
        events: List[CalendarEvent],
        weather: Optional[WeatherInfo] = None,
        last_update: Optional[datetime] = None,
    ) -> Tuple[Image.Image, Image.Image]:
        """Draws all UI components onto the dual-layer canvas and returns (black_img, red_img)."""
        logger.info(f"Rendering calendar UI for {current_date.isoformat()}...")
        canvas = EPaperCanvas(width=self.width, height=self.height)
        update_time = last_update or datetime.now()

        # Coordinate layout definitions (400x300 px)
        # Left column: 0 to 180 px
        header_rect = (8, 6, 178, 86)
        month_grid_rect = (8, 90, 178, 268)
        status_bar_rect = (8, 274, 178, 294)

        # Center vertical divider
        canvas.draw_line((184, 8, 184, 292), color="black", width=1)

        # Right column: 192 to 394 px
        event_list_rect = (192, 6, 394, 294)

        # 1. Render Left Column Components
        render_header(canvas, current_date, header_rect)
        render_month_grid(canvas, current_date, events, month_grid_rect)
        render_status_bar(canvas, update_time, status_bar_rect)

        # 2. Render Right Column Component
        render_event_list(
            canvas,
            current_date,
            events,
            weather,
            event_list_rect,
            max_events=self.config.max_upcoming_events,
        )

        black_img, red_img = canvas.get_images()

        # Handle screen rotation if mounted upside down (180 degrees)
        if self.rotation == 180:
            black_img = black_img.rotate(180)
            red_img = red_img.rotate(180)

        return black_img, red_img
