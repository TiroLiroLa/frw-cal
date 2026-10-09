#include "epd_ssd1683.h"

EPD_SSD1683::EPD_SSD1683(int csPin, int dcPin, int rstPin, int busyPin, int sckPin, int mosiPin)
    : _csPin(csPin), _dcPin(dcPin), _rstPin(rstPin), _busyPin(busyPin), _sckPin(sckPin), _mosiPin(mosiPin) {}

bool EPD_SSD1683::init() {
    pinMode(_csPin, OUTPUT);
    pinMode(_dcPin, OUTPUT);
    pinMode(_rstPin, OUTPUT);
    pinMode(_busyPin, INPUT);

    digitalWrite(_csPin, HIGH);

    SPI.begin(_sckPin, -1, _mosiPin, _csPin);
    SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));

    reset();
    readBusy();

    // SW Reset
    sendCommand(0x12);
    readBusy();

    // Border Waveform Control
    sendCommand(0x3C);
    sendData(0x05);

    // Temperature Sensor Selection
    sendCommand(0x18);
    sendData(0x80);

    // Data Entry Mode: X increment, Y increment
    sendCommand(0x11);
    sendData(0x03);

    // Set RAM X address start/end: 0 to (400/8 - 1) = 0 to 49
    sendCommand(0x44);
    sendData(0x00);
    sendData((WIDTH / 8) - 1);

    // Set RAM Y address start/end: 0 to 299
    sendCommand(0x45);
    sendData(0x00);
    sendData(0x00);
    sendData((HEIGHT - 1) % 256);
    sendData((HEIGHT - 1) / 256);

    // Set RAM X address counter
    sendCommand(0x4E);
    sendData(0x00);

    // Set RAM Y address counter
    sendCommand(0x4F);
    sendData(0x00);
    sendData(0x00);
    readBusy();

    return true;
}

void EPD_SSD1683::reset() {
    digitalWrite(_rstPin, HIGH);
    delay(200);
    digitalWrite(_rstPin, LOW);
    delay(10);
    digitalWrite(_rstPin, HIGH);
    delay(200);
}

void EPD_SSD1683::sendCommand(uint8_t command) {
    digitalWrite(_dcPin, LOW);
    digitalWrite(_csPin, LOW);
    SPI.transfer(command);
    digitalWrite(_csPin, HIGH);
}

void EPD_SSD1683::sendData(uint8_t data) {
    digitalWrite(_dcPin, HIGH);
    digitalWrite(_csPin, LOW);
    SPI.transfer(data);
    digitalWrite(_csPin, HIGH);
}

void EPD_SSD1683::sendDataBuffer(const uint8_t* buffer, size_t length, bool invert) {
    digitalWrite(_dcPin, HIGH);
    digitalWrite(_csPin, LOW);
    if (!invert) {
        SPI.transferBytes(const_cast<uint8_t*>(buffer), nullptr, length);
    } else {
        // Invert bytes for red RAM
        const size_t CHUNK = 512;
        uint8_t temp[CHUNK];
        size_t offset = 0;
        while (offset < length) {
            size_t n = std::min(CHUNK, length - offset);
            for (size_t i = 0; i < n; i++) {
                temp[i] = ~buffer[offset + i];
            }
            SPI.transferBytes(temp, nullptr, n);
            offset += n;
        }
    }
    digitalWrite(_csPin, HIGH);
}

void EPD_SSD1683::readBusy(unsigned long timeoutMs) {
    unsigned long start = millis();
    // High level indicates busy on SSD1683
    while (digitalRead(_busyPin) == HIGH) {
        delay(20);
        if (millis() - start > timeoutMs) {
            Serial.println("[EPD] Warning: Timeout waiting for BUSY signal release.");
            break;
        }
    }
}

void EPD_SSD1683::turnOnDisplay() {
    Serial.println("[EPD] Refreshing screen...");
    sendCommand(0x22); // Display Update Control
    sendData(0xF7);
    sendCommand(0x20); // Master Activation
    readBusy();
    Serial.println("[EPD] Refresh complete.");
}

void EPD_SSD1683::display(const uint8_t* blackBuf, const uint8_t* redBuf) {
    // 1. Write Black/White RAM (0x24)
    sendCommand(0x24);
    sendDataBuffer(blackBuf, BUFFER_SIZE, false);

    // 2. Write Red RAM (0x26) - inverted
    sendCommand(0x26);
    sendDataBuffer(redBuf, BUFFER_SIZE, true);

    // 3. Trigger display update
    turnOnDisplay();
}

void EPD_SSD1683::clear() {
    uint8_t whiteBuf[512];
    memset(whiteBuf, 0xFF, sizeof(whiteBuf));
    uint8_t zeroBuf[512];
    memset(zeroBuf, 0x00, sizeof(zeroBuf));

    sendCommand(0x24);
    digitalWrite(_dcPin, HIGH);
    digitalWrite(_csPin, LOW);
    for (size_t i = 0; i < BUFFER_SIZE; i += sizeof(whiteBuf)) {
        size_t n = std::min(sizeof(whiteBuf), (size_t)(BUFFER_SIZE - i));
        SPI.transferBytes(whiteBuf, nullptr, n);
    }
    digitalWrite(_csPin, HIGH);

    sendCommand(0x26);
    digitalWrite(_dcPin, HIGH);
    digitalWrite(_csPin, LOW);
    for (size_t i = 0; i < BUFFER_SIZE; i += sizeof(zeroBuf)) {
        size_t n = std::min(sizeof(zeroBuf), (size_t)(BUFFER_SIZE - i));
        SPI.transferBytes(zeroBuf, nullptr, n);
    }
    digitalWrite(_csPin, HIGH);

    turnOnDisplay();
}

void EPD_SSD1683::sleep() {
    Serial.println("[EPD] Putting display into deep sleep...");
    sendCommand(0x10); // Deep sleep command
    sendData(0x03);    // Mode 1
    delay(100);
    digitalWrite(_csPin, HIGH);
    digitalWrite(_dcPin, LOW);
    digitalWrite(_rstPin, LOW);
}
