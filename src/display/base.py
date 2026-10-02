"""Base interface for e-Paper displays."""

from abc import ABC, abstractmethod
from PIL import Image


class BaseDisplay(ABC):
    """Abstract interface for e-paper display hardware or simulator."""

    @abstractmethod
    def init(self) -> None:
        """Initialize display hardware/resources."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear the display to white."""
        pass

    @abstractmethod
    def display(self, image_black: Image.Image, image_red: Image.Image) -> None:
        """Send the 1-bit black and red image buffers to the display."""
        pass

    @abstractmethod
    def sleep(self) -> None:
        """Put display into ultra-low-power sleep mode."""
        pass
