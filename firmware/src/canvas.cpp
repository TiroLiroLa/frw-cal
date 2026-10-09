#include "canvas.h"
#include <cstring>
#include <cmath>

Canvas::Canvas() : rotation(0) {
    blackBuffer = new uint8_t[BUFFER_SIZE];
    redBuffer = new uint8_t[BUFFER_SIZE];
    clear(COLOR_WHITE);
}

Canvas::~Canvas() {
    delete[] blackBuffer;
    delete[] redBuffer;
}

void Canvas::clear(Color color) {
    if (color == COLOR_WHITE) {
        memset(blackBuffer, 0xFF, BUFFER_SIZE);
        memset(redBuffer, 0xFF, BUFFER_SIZE);
    } else if (color == COLOR_BLACK) {
        memset(blackBuffer, 0x00, BUFFER_SIZE);
        memset(redBuffer, 0xFF, BUFFER_SIZE);
    } else if (color == COLOR_RED) {
        memset(blackBuffer, 0xFF, BUFFER_SIZE);
        memset(redBuffer, 0x00, BUFFER_SIZE);
    }
}

void Canvas::setRotation(int rot) {
    rotation = (rot == 180) ? 180 : 0;
}

void Canvas::drawPixelInternal(int x, int y, Color color) {
    if (x < 0 || x >= WIDTH || y < 0 || y >= HEIGHT) return;
    int index = (x + y * WIDTH) / 8;
    uint8_t mask = 0x80 >> (x % 8);

    if (color == COLOR_BLACK) {
        blackBuffer[index] &= ~mask;
        redBuffer[index] |= mask;
    } else if (color == COLOR_RED) {
        redBuffer[index] &= ~mask;
        blackBuffer[index] |= mask;
    } else if (color == COLOR_WHITE) {
        blackBuffer[index] |= mask;
        redBuffer[index] |= mask;
    }
}

void Canvas::drawPixel(int x, int y, Color color) {
    if (rotation == 180) {
        drawPixelInternal(WIDTH - 1 - x, HEIGHT - 1 - y, color);
    } else {
        drawPixelInternal(x, y, color);
    }
}

void Canvas::drawLine(int x0, int y0, int x1, int y1, Color color, int width) {
    int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    int err = dx + dy, e2;

    while (true) {
        if (width <= 1) {
            drawPixel(x0, y0, color);
        } else {
            int half_w = width / 2;
            for (int wx = -half_w; wx <= half_w; wx++) {
                for (int wy = -half_w; wy <= half_w; wy++) {
                    drawPixel(x0 + wx, y0 + wy, color);
                }
            }
        }
        if (x0 == x1 && y0 == y1) break;
        e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

void Canvas::drawRect(int x0, int y0, int x1, int y1, Color color, int width) {
    if (x0 > x1) std::swap(x0, x1);
    if (y0 > y1) std::swap(y0, y1);
    for (int w = 0; w < width; w++) {
        drawLine(x0 + w, y0 + w, x1 - w, y0 + w, color, 1);
        drawLine(x0 + w, y1 - w, x1 - w, y1 - w, color, 1);
        drawLine(x0 + w, y0 + w, x0 + w, y1 - w, color, 1);
        drawLine(x1 - w, y0 + w, x1 - w, y1 - w, color, 1);
    }
}

void Canvas::fillRect(int x0, int y0, int x1, int y1, Color color) {
    if (x0 > x1) std::swap(x0, x1);
    if (y0 > y1) std::swap(y0, y1);
    for (int y = y0; y <= y1; y++) {
        for (int x = x0; x <= x1; x++) {
            drawPixel(x, y, color);
        }
    }
}

void Canvas::drawRoundRect(int x0, int y0, int x1, int y1, int radius, Color color, int width) {
    if (x0 > x1) std::swap(x0, x1);
    if (y0 > y1) std::swap(y0, y1);
    int w = x1 - x0;
    int h = y1 - y0;
    if (radius * 2 > w) radius = w / 2;
    if (radius * 2 > h) radius = h / 2;
    if (radius <= 0) {
        drawRect(x0, y0, x1, y1, color, width);
        return;
    }

    for (int t = 0; t < width; t++) {
        int r = radius - t;
        int cur_x0 = x0 + t;
        int cur_x1 = x1 - t;
        int cur_y0 = y0 + t;
        int cur_y1 = y1 - t;
        if (r <= 0) {
            drawRect(cur_x0, cur_y0, cur_x1, cur_y1, color, 1);
            continue;
        }

        // Horizontal straight lines
        drawLine(cur_x0 + r, cur_y0, cur_x1 - r, cur_y0, color, 1);
        drawLine(cur_x0 + r, cur_y1, cur_x1 - r, cur_y1, color, 1);

        // Vertical straight lines
        drawLine(cur_x0, cur_y0 + r, cur_x0, cur_y1 - r, color, 1);
        drawLine(cur_x1, cur_y0 + r, cur_x1, cur_y1 - r, color, 1);

        // 4 corner arcs
        for (int dy = 0; dy <= r; dy++) {
            int dx = (int)round(sqrt((float)(r * r - dy * dy)));
            // Top-left
            drawPixel(cur_x0 + r - dx, cur_y0 + r - dy, color);
            drawPixel(cur_x0 + r - dy, cur_y0 + r - dx, color);
            // Top-right
            drawPixel(cur_x1 - r + dx, cur_y0 + r - dy, color);
            drawPixel(cur_x1 - r + dy, cur_y0 + r - dx, color);
            // Bottom-left
            drawPixel(cur_x0 + r - dx, cur_y1 - r + dy, color);
            drawPixel(cur_x0 + r - dy, cur_y1 - r + dx, color);
            // Bottom-right
            drawPixel(cur_x1 - r + dx, cur_y1 - r + dy, color);
            drawPixel(cur_x1 - r + dy, cur_y1 - r + dx, color);
        }
    }
}

void Canvas::fillRoundRect(int x0, int y0, int x1, int y1, int radius, Color color) {
    if (x0 > x1) std::swap(x0, x1);
    if (y0 > y1) std::swap(y0, y1);
    int w = x1 - x0;
    int h = y1 - y0;
    if (radius * 2 > w) radius = w / 2;
    if (radius * 2 > h) radius = h / 2;
    if (radius <= 0) {
        fillRect(x0, y0, x1, y1, color);
        return;
    }

    // Fill the rectangular middle body
    fillRect(x0, y0 + radius, x1, y1 - radius, color);

    // Fill rounded top and bottom horizontal slices
    for (int dy = 0; dy < radius; dy++) {
        int dist_y = radius - dy;
        int dist_x = (int)round(sqrt((float)(radius * radius - dist_y * dist_y)));

        int line_x0 = x0 + radius - dist_x;
        int line_x1 = x1 - radius + dist_x;

        // Top line
        drawLine(line_x0, y0 + dy, line_x1, y0 + dy, color, 1);
        // Bottom line
        drawLine(line_x0, y1 - dy, line_x1, y1 - dy, color, 1);
    }
}

void Canvas::drawCircle(int cx, int cy, int r, Color color, int width) {
    int f = 1 - r;
    int ddF_x = 1;
    int ddF_y = -2 * r;
    int x = 0;
    int y = r;

    while (x <= y) {
        for (int w = 0; w < width; w++) {
            drawPixel(cx + x + w, cy + y, color);
            drawPixel(cx - x - w, cy + y, color);
            drawPixel(cx + x + w, cy - y, color);
            drawPixel(cx - x - w, cy - y, color);
            drawPixel(cx + y + w, cy + x, color);
            drawPixel(cx - y - w, cy + x, color);
            drawPixel(cx + y + w, cy - x, color);
            drawPixel(cx - y - w, cy - x, color);
        }
        if (f >= 0) {
            y--;
            ddF_y += 2;
            f += ddF_y;
        }
        x++;
        ddF_x += 2;
        f += ddF_x;
    }
}

void Canvas::fillCircle(int cx, int cy, int r, Color color) {
    if (r <= 0) {
        drawPixel(cx, cy, color);
        return;
    }
    for (int dy = -r; dy <= r; dy++) {
        int dx = (int)round(sqrt((float)(r * r - dy * dy)));
        drawLine(cx - dx, cy + dy, cx + dx, cy + dy, color, 1);
    }
}

void Canvas::drawText(int x, int y, const char* text, const FontDef& font, Color color) {
    if (!text) return;
    int cursor_x = x;
    const char* ptr = text;

    while (*ptr) {
        uint32_t cp = decodeUtf8(ptr);
        const GlyphDef* g = getGlyph(font, cp);
        if (!g) continue;

        if (g->width > 0 && g->height > 0) {
            int row_bytes = (g->width + 7) / 8;
            for (int gy = 0; gy < g->height; gy++) {
                for (int gx = 0; gx < g->width; gx++) {
                    int byte_idx = g->dataOffset + gy * row_bytes + (gx / 8);
                    uint8_t b = pgm_read_byte(&font.bitmapData[byte_idx]);
                    if (b & (0x80 >> (gx % 8))) {
                        drawPixel(cursor_x + g->xOffset + gx, y + g->yOffset + gy, color);
                    }
                }
            }
        }
        cursor_x += g->xAdvance;
    }
}

void Canvas::wrapText(const char* text, const FontDef& font, int maxWidth, int maxLines, std::vector<String>& lines) {
    lines.clear();
    if (!text || !*text) return;

    String currentLine = "";
    String currentWord = "";
    const char* ptr = text;

    while (*ptr) {
        char c = *ptr++;
        if (c == ' ' || c == '\n') {
            if (currentWord.length() > 0) {
                String testLine = currentLine.length() == 0 ? currentWord : (currentLine + " " + currentWord);
                if (getTextWidth(testLine.c_str(), font) <= maxWidth) {
                    currentLine = testLine;
                } else {
                    if (currentLine.length() > 0) {
                        lines.push_back(currentLine);
                        if ((int)lines.size() >= maxLines) return;
                        currentLine = currentWord;
                    } else {
                        lines.push_back(truncateToWidth(currentWord.c_str(), font, maxWidth));
                        if ((int)lines.size() >= maxLines) return;
                        currentLine = "";
                    }
                }
                currentWord = "";
            }
            if (c == '\n') {
                if (currentLine.length() > 0) {
                    lines.push_back(currentLine);
                    if ((int)lines.size() >= maxLines) return;
                    currentLine = "";
                }
            }
        } else {
            currentWord += c;
        }
    }

    if (currentWord.length() > 0) {
        String testLine = currentLine.length() == 0 ? currentWord : (currentLine + " " + currentWord);
        if (getTextWidth(testLine.c_str(), font) <= maxWidth) {
            currentLine = testLine;
        } else {
            if (currentLine.length() > 0) {
                lines.push_back(currentLine);
                if ((int)lines.size() < maxLines) {
                    lines.push_back(truncateToWidth(currentWord.c_str(), font, maxWidth));
                }
                return;
            } else {
                currentLine = truncateToWidth(currentWord.c_str(), font, maxWidth);
            }
        }
    }

    if (currentLine.length() > 0 && (int)lines.size() < maxLines) {
        lines.push_back(currentLine);
    }
}

String Canvas::truncateToWidth(const char* text, const FontDef& font, int maxWidth) {
    if (!text || !*text) return "";
    if (getTextWidth(text, font) <= maxWidth) return String(text);

    const char* ellipsis = "...";
    int ell_w = getTextWidth(ellipsis, font);
    int target_w = maxWidth - ell_w;
    if (target_w < 5) target_w = maxWidth;

    String result = "";
    int cur_w = 0;
    const char* ptr = text;
    while (*ptr) {
        const char* prev_ptr = ptr;
        uint32_t cp = decodeUtf8(ptr);
        const GlyphDef* g = getGlyph(font, cp);
        int adv = g ? g->xAdvance : 6;
        if (cur_w + adv > target_w) {
            break;
        }
        cur_w += adv;
        while (prev_ptr < ptr) {
            result += *prev_ptr++;
        }
    }

    return result + ellipsis;
}

