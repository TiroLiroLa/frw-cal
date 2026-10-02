"""Hardware configuration and low-level SPI / GPIO driver for Raspberry Pi.

Supports both modern gpiozero (Raspberry Pi OS Bookworm+) and RPi.GPIO (legacy),
with automatic hardware Chip Select (CE0) handling to prevent 'GPIO not allocated' errors.
"""

import logging
import time

logger = logging.getLogger(__name__)

# Pin defaults (BCM numbering)
RST_PIN = 17
DC_PIN = 25
CS_PIN = 8
BUSY_PIN = 24

_SPI = None
_BACKEND = None  # "gpiozero" or "rpi_gpio"
_RST_DEV = None
_DC_DEV = None
_BUSY_DEV = None
_CS_DEV = None
_GPIO = None
_MANUAL_CS = False
_IS_RPI = False


def configure_pins(rst: int = 17, dc: int = 25, cs: int = 8, busy: int = 24):
    global RST_PIN, DC_PIN, CS_PIN, BUSY_PIN
    RST_PIN = rst
    DC_PIN = dc
    CS_PIN = cs
    BUSY_PIN = busy


def digital_write(pin, value):
    global _BACKEND, _RST_DEV, _DC_DEV, _CS_DEV, _GPIO, _MANUAL_CS

    # CS Pin: Hardware SPI (spidev) automatically controls CE0 (GPIO 8) on every transfer.
    if pin == CS_PIN and not _MANUAL_CS:
        return

    if _BACKEND == "gpiozero":
        if pin == RST_PIN and _RST_DEV:
            _RST_DEV.value = bool(value)
        elif pin == DC_PIN and _DC_DEV:
            _DC_DEV.value = bool(value)
        elif pin == CS_PIN and _CS_DEV:
            _CS_DEV.value = bool(value)
    elif _BACKEND == "rpi_gpio" and _GPIO:
        try:
            _GPIO.output(pin, bool(value))
        except Exception as e:
            logger.debug(f"digital_write error on pin {pin}: {e}")


def digital_read(pin):
    global _BACKEND, _BUSY_DEV, _GPIO

    if _BACKEND == "gpiozero":
        if pin == BUSY_PIN and _BUSY_DEV:
            return 1 if _BUSY_DEV.is_active else 0
    elif _BACKEND == "rpi_gpio" and _GPIO:
        try:
            return _GPIO.input(pin)
        except Exception:
            return 0
    return 0


def delay_ms(delaytime):
    time.sleep(delaytime / 1000.0)


def DEV_SPI_write(data):
    global _SPI
    if _SPI:
        _SPI.writebytes([data])


def DEV_SPI_read():
    global _SPI
    if _SPI:
        try:
            return _SPI.readbytes(1)[0]
        except Exception:
            return 0
    return 0


def spi_writebyte2(data):
    global _SPI
    if _SPI:
        # Chunk into 4096-byte blocks to prevent kernel SPI buffer overflow
        chunk_size = 4096
        if isinstance(data, (bytes, bytearray)):
            bdata = data
        else:
            bdata = bytes(data)
        for i in range(0, len(bdata), chunk_size):
            _SPI.writebytes(list(bdata[i : i + chunk_size]))


def module_init(cleanup=False):
    global _SPI, _BACKEND, _RST_DEV, _DC_DEV, _BUSY_DEV, _CS_DEV, _GPIO, _MANUAL_CS, _IS_RPI

    # 1. Initialize SPI
    try:
        import spidev

        _SPI = spidev.SpiDev()
        _SPI.open(0, 0)
        _SPI.max_speed_hz = 4000000
        _SPI.mode = 0b00
    except Exception as e:
        logger.error(
            f"Failed to open SPI bus (spidev0.0): {e}. "
            "Certifique-se de que a interface SPI está habilitada via 'sudo raspi-config'."
        )
        return -1

    # 2. Initialize GPIO (prefer gpiozero on Bookworm+, fallback to RPi.GPIO)
    # Note: On Raspberry Pi OS with SPI enabled, GPIO 8 (CE0) is claimed by the kernel SPI driver.
    # Attempting to claim it as a standard GPIO output causes 'GPIO not allocated' / 'GPIO busy'.
    # Because spidev already controls CE0 in hardware, manual CS setup is only done if CS != 8.
    _MANUAL_CS = (CS_PIN != 8)

    try:
        import gpiozero

        _RST_DEV = gpiozero.OutputDevice(RST_PIN, active_high=True, initial_value=True)
        _DC_DEV = gpiozero.OutputDevice(DC_PIN, active_high=True, initial_value=False)
        _BUSY_DEV = gpiozero.InputDevice(BUSY_PIN, pull_up=False)

        if _MANUAL_CS:
            try:
                _CS_DEV = gpiozero.OutputDevice(CS_PIN, active_high=True, initial_value=True)
            except Exception as e:
                logger.debug(f"Manual CS pin setup skipped: {e}")
                _MANUAL_CS = False

        _BACKEND = "gpiozero"
        _IS_RPI = True
        logger.info(
            f"GPIO initialized via 'gpiozero' (RST={RST_PIN}, DC={DC_PIN}, BUSY={BUSY_PIN}, "
            f"CS={'Hardware SPI (CE0)' if not _MANUAL_CS else CS_PIN})."
        )
        return 0
    except ImportError:
        logger.debug("gpiozero not installed, attempting RPi.GPIO fallback...")
    except Exception as e:
        logger.debug(f"gpiozero init failed ({e}), attempting RPi.GPIO fallback...")

    # Fallback to RPi.GPIO / rpi-lgpio
    try:
        import RPi.GPIO as GPIO

        _GPIO = GPIO
        _GPIO.setmode(_GPIO.BCM)
        _GPIO.setwarnings(False)

        _GPIO.setup(RST_PIN, _GPIO.OUT, initial=_GPIO.HIGH)
        _GPIO.setup(DC_PIN, _GPIO.OUT, initial=_GPIO.LOW)
        _GPIO.setup(BUSY_PIN, _GPIO.IN)

        if _MANUAL_CS:
            try:
                _GPIO.setup(CS_PIN, _GPIO.OUT, initial=_GPIO.HIGH)
            except Exception as e:
                logger.debug(f"RPi.GPIO CS setup skipped: {e}")
                _MANUAL_CS = False

        _BACKEND = "rpi_gpio"
        _IS_RPI = True
        logger.info(
            f"GPIO initialized via 'RPi.GPIO' (RST={RST_PIN}, DC={DC_PIN}, BUSY={BUSY_PIN}, "
            f"CS={'Hardware SPI (CE0)' if not _MANUAL_CS else CS_PIN})."
        )
        return 0
    except Exception as e:
        logger.error(f"Failed to initialize GPIO pins: {e}")
        return -1


def module_exit(cleanup=False):
    global _SPI, _BACKEND, _RST_DEV, _DC_DEV, _BUSY_DEV, _CS_DEV, _GPIO

    if _SPI:
        try:
            _SPI.close()
        except Exception:
            pass

    if _BACKEND == "gpiozero":
        try:
            if _RST_DEV:
                _RST_DEV.close()
            if _DC_DEV:
                _DC_DEV.close()
            if _BUSY_DEV:
                _BUSY_DEV.close()
            if _CS_DEV:
                _CS_DEV.close()
        except Exception:
            pass
    elif _BACKEND == "rpi_gpio" and _GPIO and cleanup:
        try:
            _GPIO.cleanup()
        except Exception:
            pass
