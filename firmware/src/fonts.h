#pragma once

#include <Arduino.h>

struct GlyphDef {
    uint32_t codepoint;
    uint8_t width;
    uint8_t height;
    int8_t xOffset;
    int8_t yOffset;
    uint8_t xAdvance;
    uint16_t dataOffset;
};

struct FontDef {
    const char* name;
    uint8_t size;
    int16_t ascent;
    int16_t descent;
    uint8_t lineHeight;
    uint16_t glyphCount;
    const GlyphDef* glyphs;
    const uint8_t* bitmapData;
};

extern const FontDef Font_LiberationSans_Bold_44;
extern const FontDef Font_LiberationSans_Bold_18;
extern const FontDef Font_LiberationSans_Bold_16;
extern const FontDef Font_LiberationSans_Bold_14;
extern const FontDef Font_LiberationSans_Bold_12;
#define Font_LiberationSans_Bold_10 Font_LiberationSans_Bold_12

// Helper functions for UTF-8 decoding and glyph lookup
uint32_t decodeUtf8(const char*& str);
const GlyphDef* getGlyph(const FontDef& font, uint32_t codepoint);
int getTextWidth(const char* text, const FontDef& font);
