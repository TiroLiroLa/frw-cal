"""Hardware configuration and low-level SPI / GPIO driver for Raspberry Pi."""

import logging
import time

logger = logging.getLogger(__name__)

# Pin defaults (BCM numbering)
RST_PIN = 17
DC_PIN = 25
CS_PIN = 8
BUSY_PIN = 24

_SPI = None
_GPIO = None
_IS_RPI = False


def configure_pins(rst: int = 17, dc: int = 25, cs: int = 8, busy: int = 24):
    global RST_PIN, DC_PIN, CS_PIN, BUSY_PIN
    RST_PIN = rst
    DC_PIN = dc
    CS_PIN = cs
    BUSY_PIN = busy


def digital_write(pin, value):
    if _GPIO:
        _GPIO.output(pin, value)


def digital_read(pin):
    if _GPIO:
        return _GPIO.input(pin)
    return 0


def delay_ms(delaytime):
    time.sleep(delaytime / 1000.0)


def DEV_SPI_write(data):
    if _SPI:
        _SPI.writebytes([data])


def DEV_SPI_read():
    if _SPI:
        return _SPI.readbytes(1)[0]
    return 0


def spi_writebyte2(data):
    if _SPI:
        _SPI.writebytes2(data)


def module_init(cleanup=False):
    global _SPI, _GPIO, _IS_RPI

    try:
        import spidev
        import RPi.GPIO as GPIO

        _GPIO = GPIO
        _GPIO.setmode(_GPIO.BCM)
        _GPIO.setwarnings(False)

        _GPIO.setup(RST_PIN, _GPIO.OUT)
        _GPIO.setup(DC_PIN, _GPIO.OUT)
        _GPIO.setup(CS_PIN, _GPIO.OUT)
        _GPIO.setup(BUSY_PIN, _GPIO.IN)

        _SPI = spidev.SpiDev(0, 0)
        _SPI.max_speed_hz = 4000000
        _SPI.mode = 0b00
        _IS_RPI = True
        logger.info("SPI and GPIO hardware successfully initialized.")
        return 0
    except ImportError as e:
        logger.warning(
            f"Hardware libraries not available ({e}). Running in simulated hardware mode."
        )
        return -1
    except Exception as e:
        logger.error(f"Failed to initialize hardware SPI/GPIO: {e}")
        return -1


def module_exit(cleanup=False):
    global _SPI, _GPIO
    if _SPI:
        try:
            _SPI.close()
        except Exception:
            pass
    if _GPIO and cleanup:
        try:
            _GPIO.output(RST_PIN, 0)
            _GPIO.output(DC_PIN, 0)
            _GPIO.cleanup()
        except Exception:
            pass
