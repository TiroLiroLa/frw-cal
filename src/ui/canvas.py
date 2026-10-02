"""Dual-layer canvas abstraction for 3-color (Black/White/Red) e-Paper displays."""

from typing import Tuple, Union
from PIL import Image, ImageDraw


class EPaperCanvas:
    """Manages separate 1-bit layers for Black and Red ink on a White background."""

    def __init__(self, width: int = 400, height: int = 300):
        self.width = width
        self.height = height
        # Mode '1': 255 is White (no ink), 0 is Ink (black or red)
        self.black_img = Image.new("1", (width, height), 255)
        self.red_img = Image.new("1", (width, height), 255)
        self.draw_b = ImageDraw.Draw(self.black_img)
        self.draw_r = ImageDraw.Draw(self.red_img)

    def draw_text(
        self,
        xy: Tuple[int, int],
        text: str,
        font,
        color: str = "black",
        anchor: str = None,
    ):
        """Draw text on black, red, or inverted white layer."""
        if color == "black":
            self.draw_b.text(xy, text, fill=0, font=font, anchor=anchor)
        elif color == "red":
            self.draw_r.text(xy, text, fill=0, font=font, anchor=anchor)
        elif color == "white":
            # White text: erase ink from both layers (value 255)
            self.draw_b.text(xy, text, fill=255, font=font, anchor=anchor)
            self.draw_r.text(xy, text, fill=255, font=font, anchor=anchor)

    def draw_line(
        self,
        xy: Union[Tuple[int, int, int, int], list],
        color: str = "black",
        width: int = 1,
    ):
        if color == "black":
            self.draw_b.line(xy, fill=0, width=width)
        elif color == "red":
            self.draw_r.line(xy, fill=0, width=width)
        elif color == "white":
            self.draw_b.line(xy, fill=255, width=width)
            self.draw_r.line(xy, fill=255, width=width)

    def draw_rectangle(
        self,
        xy: Tuple[int, int, int, int],
        fill: str = None,
        outline: str = None,
        width: int = 1,
    ):
        fill_b = 0 if fill == "black" else (255 if fill == "white" else None)
        outline_b = 0 if outline == "black" else (255 if outline == "white" else None)

        fill_r = 0 if fill == "red" else (255 if fill == "white" else None)
        outline_r = 0 if outline == "red" else (255 if outline == "white" else None)

        if fill == "black" or outline == "black":
            self.draw_b.rectangle(xy, fill=fill_b, outline=outline_b, width=width)
        if fill == "red" or outline == "red":
            self.draw_r.rectangle(xy, fill=fill_r, outline=outline_r, width=width)
        if fill == "white":
            self.draw_b.rectangle(xy, fill=255, outline=None)
            self.draw_r.rectangle(xy, fill=255, outline=None)

    def draw_rounded_rectangle(
        self,
        xy: Tuple[int, int, int, int],
        radius: int = 4,
        fill: str = None,
        outline: str = None,
        width: int = 1,
    ):
        if fill == "red":
            self.draw_r.rounded_rectangle(xy, radius=radius, fill=0, outline=None)
            # Clear black underneath to ensure pure red
            self.draw_b.rounded_rectangle(xy, radius=radius, fill=255, outline=None)
        elif fill == "black":
            self.draw_b.rounded_rectangle(xy, radius=radius, fill=0, outline=None)
            self.draw_r.rounded_rectangle(xy, radius=radius, fill=255, outline=None)
        elif fill == "white":
            self.draw_b.rounded_rectangle(xy, radius=radius, fill=255, outline=None)
            self.draw_r.rounded_rectangle(xy, radius=radius, fill=255, outline=None)

        if outline == "black":
            self.draw_b.rounded_rectangle(xy, radius=radius, outline=0, width=width)
        elif outline == "red":
            self.draw_r.rounded_rectangle(xy, radius=radius, outline=0, width=width)

    def draw_circle(
        self,
        center: Tuple[int, int],
        radius: int,
        fill: str = None,
        outline: str = None,
        width: int = 1,
    ):
        bbox = (
            center[0] - radius,
            center[1] - radius,
            center[0] + radius,
            center[1] + radius,
        )
        if fill == "red":
            self.draw_r.ellipse(bbox, fill=0, outline=None)
            self.draw_b.ellipse(bbox, fill=255, outline=None)
        elif fill == "black":
            self.draw_b.ellipse(bbox, fill=0, outline=None)
            self.draw_r.ellipse(bbox, fill=255, outline=None)
        elif fill == "white":
            self.draw_b.ellipse(bbox, fill=255, outline=None)
            self.draw_r.ellipse(bbox, fill=255, outline=None)

        if outline == "black":
            self.draw_b.ellipse(bbox, outline=0, width=width)
        elif outline == "red":
            self.draw_r.ellipse(bbox, outline=0, width=width)

    def get_images(self) -> Tuple[Image.Image, Image.Image]:
        """Returns (black_image, red_image)."""
        return self.black_img, self.red_img
