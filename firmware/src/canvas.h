#pragma once

#include <Arduino.h>
#include <vector>
#include "fonts.h"

enum Color {
    COLOR_WHITE,
    COLOR_BLACK,
    COLOR_RED
};

class Canvas {
public:
    static const int WIDTH = 400;
    static const int HEIGHT = 300;
    static const int BUFFER_SIZE = (WIDTH * HEIGHT) / 8; // 15000 bytes

    Canvas();
    ~Canvas();

    void clear(Color color = COLOR_WHITE);
    void setRotation(int rotation); // 0 or 180

    void drawPixel(int x, int y, Color color);
    void drawLine(int x0, int y0, int x1, int y1, Color color, int width = 1);
    void drawRect(int x0, int y0, int x1, int y1, Color color, int width = 1);
    void fillRect(int x0, int y0, int x1, int y1, Color color);
    void drawRoundRect(int x0, int y0, int x1, int y1, int radius, Color color, int width = 1);
    void fillRoundRect(int x0, int y0, int x1, int y1, int radius, Color color);
    void drawCircle(int cx, int cy, int r, Color color, int width = 1);
    void fillCircle(int cx, int cy, int r, Color color);

    void drawText(int x, int y, const char* text, const FontDef& font, Color color);
    
    // Text helpers
    void wrapText(const char* text, const FontDef& font, int maxWidth, int maxLines, std::vector<String>& lines);
    String truncateToWidth(const char* text, const FontDef& font, int maxWidth);

    const uint8_t* getBlackBuffer() const { return blackBuffer; }
    const uint8_t* getRedBuffer() const { return redBuffer; }

private:
    uint8_t* blackBuffer;
    uint8_t* redBuffer;
    int rotation;

    void drawPixelInternal(int x, int y, Color color);
};
