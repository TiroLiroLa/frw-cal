"""Hardware driver for WeAct Studio 4.2-inch Black/White/Red E-Paper (SSD1683)."""

import logging
from PIL import Image
from . import epdconfig
from .base import BaseDisplay

logger = logging.getLogger(__name__)

EPD_WIDTH = 400
EPD_HEIGHT = 300


class EPD4in2B_V2(BaseDisplay):
    """Driver for WeAct Studio / Waveshare 4.2inch E-Paper (B) V2 (400x300, Black/White/Red)."""

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
        self.flag = 0

    def init(self):
        logger.info("Initializing 4.2inch BWR e-paper display...")
        if epdconfig.module_init(cleanup=True) != 0:
            logger.warning("Could not initialize hardware module. Check SPI/GPIO.")
            return -1

        self.reset()
        self.send_command(0x2F)
        epdconfig.delay_ms(100)
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        i = epdconfig.DEV_SPI_read()
        epdconfig.digital_write(self.cs_pin, 1)

        if i == 0x01:
            self.flag = 1
            self.ReadBusy()
            self.send_command(0x12)
            self.ReadBusy()

            self.send_command(0x3C)
            self.send_data(0x05)

            self.send_command(0x18)
            self.send_data(0x80)

            self.send_command(0x11)
            self.send_data(0x03)

            self.send_command(0x44)
            self.send_data(0x00)
            self.send_data(self.width // 8 - 1)

            self.send_command(0x45)
            self.send_data(0x00)
            self.send_data(0x00)
            self.send_data((self.height - 1) % 256)
            self.send_data((self.height - 1) // 256)

            self.send_command(0x4E)
            self.send_data(0x00)
            self.send_command(0x4F)
            self.send_data(0x00)
            self.send_data(0x00)
            self.ReadBusy()
        else:
            self.flag = 0
            self.send_command(0x04)  # POWER_ON
            self.ReadBusy()
            self.send_command(0x00)  # Panel setting
            self.send_data(0x0F)

        logger.info("4.2inch e-paper display initialized successfully.")
        return 0

    def reset(self):
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(200)
        epdconfig.digital_write(self.reset_pin, 0)
        epdconfig.delay_ms(5)
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(200)

    def send_command(self, command):
        epdconfig.digital_write(self.dc_pin, 0)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.DEV_SPI_write(command)
        epdconfig.digital_write(self.cs_pin, 1)

    def send_data(self, data):
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.DEV_SPI_write(data)
        epdconfig.digital_write(self.cs_pin, 1)

    def ReadBusy(self):
        logger.debug("Waiting for e-Paper BUSY signal release...")
        if self.flag == 1:
            while epdconfig.digital_read(self.busy_pin) == 1:
                epdconfig.delay_ms(100)
        else:
            while epdconfig.digital_read(self.busy_pin) == 0:
                epdconfig.delay_ms(100)
        logger.debug("e-Paper is ready.")

    def TurnOnDisplay(self):
        logger.info("Refreshing e-paper screen...")
        if self.flag == 1:
            self.send_command(0x22)
            self.send_data(0xF7)
            self.send_command(0x20)
            self.ReadBusy()
        else:
            self.send_command(0x12)
            epdconfig.delay_ms(100)
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

        high = self.height
        wide = self.width // 8 if (self.width % 8 == 0) else (self.width // 8 + 1)

        if self.flag == 1:
            self.send_command(0x24)
            for j in range(0, high):
                for i in range(0, wide):
                    self.send_data(buf_black[i + j * wide])

            self.send_command(0x26)
            for j in range(0, high):
                for i in range(0, wide):
                    self.send_data(~buf_red[i + j * wide] & 0xFF)
        else:
            self.send_command(0x10)
            for j in range(0, high):
                for i in range(0, wide):
                    self.send_data(buf_black[i + j * wide])

            self.send_command(0x13)
            for j in range(0, high):
                for i in range(0, wide):
                    self.send_data(~buf_red[i + j * wide] & 0xFF)

        self.TurnOnDisplay()

    def clear(self):
        high = self.height
        wide = self.width // 8 if (self.width % 8 == 0) else (self.width // 8 + 1)

        if self.flag == 1:
            self.send_command(0x24)
            for j in range(0, high):
                for i in range(0, wide):
                    self.send_data(0xFF)

            self.send_command(0x26)
            for j in range(0, high):
                for i in range(0, wide):
                    self.send_data(0x00)
        else:
            self.send_command(0x10)
            for j in range(0, high):
                for i in range(0, wide):
                    self.send_data(0xFF)

            self.send_command(0x13)
            for j in range(0, high):
                for i in range(0, wide):
                    self.send_data(0x00)

        self.TurnOnDisplay()

    def sleep(self):
        logger.info("Putting e-paper display to sleep...")
        if self.flag == 1:
            self.send_command(0x10)
            self.send_data(0x03)
        else:
            self.send_command(0x50)
            self.send_data(0xF7)
        epdconfig.delay_ms(100)
