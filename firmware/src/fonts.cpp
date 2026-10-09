#include "fonts.h"
#include "fonts_data.h"

uint32_t decodeUtf8(const char*& str) {
    if (!str || !*str) return 0;
    
    uint8_t c = (uint8_t)*str++;
    if (c < 0x80) {
        return c;
    } else if ((c & 0xE0) == 0xC0) {
        uint8_t c2 = (uint8_t)*str++;
        if ((c2 & 0xC0) != 0x80) return '?';
        return ((c & 0x1F) << 6) | (c2 & 0x3F);
    } else if ((c & 0xF0) == 0xE0) {
        uint8_t c2 = (uint8_t)*str++;
        uint8_t c3 = (uint8_t)*str++;
        if ((c2 & 0xC0) != 0x80 || (c3 & 0xC0) != 0x80) return '?';
        return ((c & 0x0F) << 12) | ((c2 & 0x3F) << 6) | (c3 & 0x3F);
    } else if ((c & 0xF8) == 0xF0) {
        uint8_t c2 = (uint8_t)*str++;
        uint8_t c3 = (uint8_t)*str++;
        uint8_t c4 = (uint8_t)*str++;
        if ((c2 & 0xC0) != 0x80 || (c3 & 0xC0) != 0x80 || (c4 & 0xC0) != 0x80) return '?';
        return ((c & 0x07) << 18) | ((c2 & 0x3F) << 12) | ((c3 & 0x3F) << 6) | (c4 & 0x3F);
    }
    return '?';
}

const GlyphDef* getGlyph(const FontDef& font, uint32_t codepoint) {
    int low = 0;
    int high = font.glyphCount - 1;
    
    while (low <= high) {
        int mid = low + (high - low) / 2;
        const GlyphDef* g = &font.glyphs[mid];
        if (g->codepoint == codepoint) {
            return g;
        } else if (g->codepoint < codepoint) {
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }
    
    // Fallback: try space if not found, or '?'
    if (codepoint != ' ' && codepoint != '?') {
        const GlyphDef* fallback = getGlyph(font, '?');
        if (fallback) return fallback;
        return getGlyph(font, ' ');
    }
    
    return nullptr;
}

int getTextWidth(const char* text, const FontDef& font) {
    if (!text) return 0;
    int width = 0;
    const char* ptr = text;
    while (*ptr) {
        uint32_t cp = decodeUtf8(ptr);
        const GlyphDef* g = getGlyph(font, cp);
        if (g) {
            width += g->xAdvance;
        }
    }
    return width;
}
