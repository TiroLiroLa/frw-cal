"""Hardware driver for WeAct Studio 4.2-inch Black/White/Red E-Paper (SSD1683)."""

import logging
import time
from PIL import Image
from . import epdconfig
from .base import BaseDisplay

logger = logging.getLogger(__name__)

EPD_WIDTH = 400
EPD_HEIGHT = 300


class EPD4in2B_V2(BaseDisplay):
    """Driver for WeAct Studio / Waveshare 4.2inch E-Paper (B) V2 (400x300, Black/White/Red, SSD1683)."""

    def __init__(self, pins: dict = None):
        if pins:
            epdconfig.configure_pins(
                rst=pins.get("rst", 17),
                dc=pins.get("dc", 25),
                cs=pins.get("cs", 8),
                busy=pins.get("busy", 24),
            )
        self.reset_pin = epdconfig.RST_PIN
        self.dc_pin = epdconfig.DC_PIN
        self.busy_pin = epdconfig.BUSY_PIN
        self.cs_pin = epdconfig.CS_PIN
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT
        self.flag = 1  # WeAct Studio 4.2" BWR uses SSD1683 controller

    def init(self):
        logger.info("Initializing 4.2inch BWR e-paper display (SSD1683)...")
        if epdconfig.module_init(cleanup=True) != 0:
            raise RuntimeError(
                "Falha ao inicializar o hardware SPI/GPIO no Raspberry Pi. "
                "Verifique se o SPI está ativado em 'sudo raspi-config' e se os pinos estão conectados."
            )

        self.reset()
        self.ReadBusy()

        # SW Reset
        self.send_command(0x12)
        self.ReadBusy()

        # Border Waveform Control
        self.send_command(0x3C)
        self.send_data(0x05)

        # Temperature Sensor Selection
        self.send_command(0x18)
        self.send_data(0x80)

        # Data Entry Mode: X increment, Y increment
        self.send_command(0x11)
        self.send_data(0x03)

        # Set RAM X address start/end: 0 to (400/8 - 1) = 0 to 49
        self.send_command(0x44)
        self.send_data(0x00)
        self.send_data(self.width // 8 - 1)

        # Set RAM Y address start/end: 0 to 299
        self.send_command(0x45)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data((self.height - 1) % 256)
        self.send_data((self.height - 1) // 256)

        # Set RAM X address counter
        self.send_command(0x4E)
        self.send_data(0x00)

        # Set RAM Y address counter
        self.send_command(0x4F)
        self.send_data(0x00)
        self.send_data(0x00)
        self.ReadBusy()

        logger.info("4.2inch e-paper display initialized successfully.")
        return 0

    def reset(self):
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(200)
        epdconfig.digital_write(self.reset_pin, 0)
        epdconfig.delay_ms(5)
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(200)

    def send_command(self, command: int):
        epdconfig.digital_write(self.dc_pin, 0)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.DEV_SPI_write(command)
        epdconfig.digital_write(self.cs_pin, 1)

    def send_data(self, data: int):
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.DEV_SPI_write(data)
        epdconfig.digital_write(self.cs_pin, 1)

    def send_data_buffer(self, buffer):
        """Send byte buffer over SPI quickly."""
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte2(buffer)
        epdconfig.digital_write(self.cs_pin, 1)

    def ReadBusy(self, timeout_sec: float = 30.0):
        """Wait for e-Paper BUSY signal to clear (low level indicates idle on SSD1683)."""
        logger.debug("Waiting for e-Paper BUSY signal release...")
        start_time = time.time()
        while epdconfig.digital_read(self.busy_pin) == 1:
            epdconfig.delay_ms(50)
            if time.time() - start_time > timeout_sec:
                logger.warning(
                    f"Timeout ({timeout_sec}s) waiting for BUSY release! "
                    "Verifique a conexão física do pino BUSY (GPIO 24)."
                )
                break
        logger.debug("e-Paper is ready.")

    def TurnOnDisplay(self):
        logger.info("Refreshing e-paper screen...")
        self.send_command(0x22)  # Display Update Control
        self.send_data(0xF7)
        self.send_command(0x20)  # Master Activation
        self.ReadBusy()
        logger.info("Screen refresh complete.")

    def getbuffer(self, image: Image.Image):
        buf = [0xFF] * (int(self.width / 8) * self.height)
        image_monocolor = image.convert("1")
        imwidth, imheight = image_monocolor.size
        pixels = image_monocolor.load()

        if imwidth == self.width and imheight == self.height:
            for y in range(imheight):
                for x in range(imwidth):
                    if pixels[x, y] == 0:
                        buf[int((x + y * self.width) / 8)] &= ~(0x80 >> (x % 8))
        elif imwidth == self.height and imheight == self.width:
            for y in range(imheight):
                for x in range(imwidth):
                    newx = y
                    newy = self.height - x - 1
                    if pixels[x, y] == 0:
                        buf[int((newx + newy * self.width) / 8)] &= ~(0x80 >> (y % 8))
        return buf

    def display(self, image_black: Image.Image, image_red: Image.Image):
        buf_black = self.getbuffer(image_black)
        buf_red = self.getbuffer(image_red)

        # Write Black/White RAM (0x24)
        self.send_command(0x24)
        self.send_data_buffer(buf_black)

        # Write Red RAM (0x26) - inverted
        inverted_red = [~b & 0xFF for b in buf_red]
        self.send_command(0x26)
        self.send_data_buffer(inverted_red)

        # Trigger display refresh
        self.TurnOnDisplay()

    def clear(self):
        buf_size = (self.width // 8) * self.height
        white_buf = [0xFF] * buf_size
        black_buf = [0x00] * buf_size

        self.send_command(0x24)
        self.send_data_buffer(white_buf)

        self.send_command(0x26)
        self.send_data_buffer(black_buf)

        self.TurnOnDisplay()

    def sleep(self):
        logger.info("Putting e-paper display to sleep...")
        self.send_command(0x10)  # Deep sleep command
        self.send_data(0x03)     # Enter deep sleep mode 1
        epdconfig.delay_ms(100)
        # Release SPI bus and GPIO handles during sleep to prevent resource lockups between cycles
        epdconfig.module_exit(cleanup=False)
