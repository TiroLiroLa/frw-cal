"""Mock e-Paper display driver for local development and preview generation."""

import logging
from pathlib import Path
from PIL import Image
from .base import BaseDisplay

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"


class MockDisplay(BaseDisplay):
    """Simulated display that renders outputs to PNG files."""

    def __init__(self, width: int = 400, height: int = 300):
        self.width = width
        self.height = height
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def init(self) -> None:
        logger.info(f"Initialized MockDisplay ({self.width}x{self.height} px)")

    def clear(self) -> None:
        logger.info("MockDisplay cleared (White screen).")

    def display(self, image_black: Image.Image, image_red: Image.Image) -> None:
        """Combine black and red 1-bit images into a realistic tri-color e-Paper preview."""
        logger.info("Compositing mock e-Paper display image...")

        # Ensure correct size and mode '1'
        img_b = image_black.convert("1")
        img_r = image_red.convert("1")

        # Create realistic paper background (slight off-white realistic e-ink look)
        paper_bg = (248, 248, 246)
        ink_black = (20, 20, 20)
        ink_red = (215, 38, 56)  # Warm, rich e-paper red

        preview = Image.new("RGB", (self.width, self.height), paper_bg)
        pixels_preview = preview.load()
        pixels_b = img_b.load()
        pixels_r = img_r.load()

        # In PIL mode '1', 0 is black (ink), 255 is white (no ink)
        for y in range(self.height):
            for x in range(self.width):
                # Red ink takes priority or blends
                is_black = (pixels_b[x, y] == 0)
                is_red = (pixels_r[x, y] == 0)

                if is_red:
                    pixels_preview[x, y] = ink_red
                elif is_black:
                    pixels_preview[x, y] = ink_black
                else:
                    pixels_preview[x, y] = paper_bg

        # Save files
        preview_path = OUTPUT_DIR / "preview.png"
        black_path = OUTPUT_DIR / "black_channel.png"
        red_path = OUTPUT_DIR / "red_channel.png"

        preview.save(preview_path)
        img_b.save(black_path)
        img_r.save(red_path)

        logger.info(f"Preview generated successfully: {preview_path}")

    def sleep(self) -> None:
        logger.info("MockDisplay entering sleep mode.")
