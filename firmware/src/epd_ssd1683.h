#pragma once

#include <Arduino.h>
#include <SPI.h>

class EPD_SSD1683 {
public:
    static const int WIDTH = 400;
    static const int HEIGHT = 300;
    static const int BUFFER_SIZE = (WIDTH * HEIGHT) / 8; // 15000 bytes

    EPD_SSD1683(int csPin, int dcPin, int rstPin, int busyPin, int sckPin = 18, int mosiPin = 23);

    bool init();
    void reset();
    void display(const uint8_t* blackBuf, const uint8_t* redBuf);
    void clear();
    void sleep();

private:
    int _csPin;
    int _dcPin;
    int _rstPin;
    int _busyPin;
    int _sckPin;
    int _mosiPin;

    void sendCommand(uint8_t command);
    void sendData(uint8_t data);
    void sendDataBuffer(const uint8_t* buffer, size_t length, bool invert = false);
    void readBusy(unsigned long timeoutMs = 30000);
    void turnOnDisplay();
};
