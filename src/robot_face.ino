#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>
#include <math.h>

#define TFT_CS    5
#define TFT_DC    2
#define TFT_RST   4
#define TFT_MOSI  23
#define TFT_SCLK  18

#define SCREEN_W  240
#define SCREEN_H  240

#define C_FACE      0x18C3
#define C_EYE_WHITE 0xAD75
#define C_EYE_PUPIL 0x051F
#define C_EYE_SHINE 0xFFFF
#define C_OUTLINE   0x4A69

#define EYE_W       52
#define EYE_H       40
#define EYE_RADIUS  10
#define EYE_L_X     62
#define EYE_R_X     178
#define EYE_Y       85

#define EQ_BARS       20
#define EQ_BAR_W      7
#define EQ_GAP        3
#define EQ_CENTER_Y   185
#define EQ_MAX_HALF   28
#define EQ_MIN_HALF   2
#define EQ_TOTAL_W    (EQ_BARS * (EQ_BAR_W + EQ_GAP) - EQ_GAP)
#define EQ_START_X    ((SCREEN_W - EQ_TOTAL_W) / 2)

#define BLINK_INTERVAL_MIN  2000
#define BLINK_INTERVAL_MAX  5000
#define BLINK_CLOSE_MS      80
#define BLINK_OPEN_MS       90
#define EQ_UPDATE_MS        30

Adafruit_ST7789 tft = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_RST);

float eqHeights[EQ_BARS];
unsigned long lastEqUpdate = 0;
unsigned long nextBlink    = 0;
bool  isBlinking           = false;
unsigned long blinkStart   = 0;
int   blinkPhase           = 0;

uint16_t gradientColor(float pos) {
  uint8_t r, g, b;
  if (pos < 0.5f) {
    float t = pos * 2.0f;
    r = (uint8_t)(80  + t * 175);
    g = (uint8_t)(20  + t * 20);
    b = (uint8_t)(200 - t * 170);
  } else {
    float t = (pos - 0.5f) * 2.0f;
    r = 255;
    g = (uint8_t)(40 + t * 80);
    b = (uint8_t)(30 - t * 20);
  }
  return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
}

void drawBothEyes(float openFraction) {
  if (openFraction < 0.0f) openFraction = 0.0f;
  if (openFraction > 1.0f) openFraction = 1.0f;

  int halfH = (int)(EYE_H / 2 * openFraction);

  tft.fillRect(EYE_L_X - EYE_W/2 - 2, EYE_Y - EYE_H/2 - 2, EYE_W + 4, EYE_H + 4, C_FACE);
  tft.fillRect(EYE_R_X - EYE_W/2 - 2, EYE_Y - EYE_H/2 - 2, EYE_W + 4, EYE_H + 4, C_FACE);

  if (openFraction < 0.05f) {
    tft.drawFastHLine(EYE_L_X - EYE_W/2 + 4, EYE_Y, EYE_W - 8, C_OUTLINE);
    tft.drawFastHLine(EYE_R_X - EYE_W/2 + 4, EYE_Y, EYE_W - 8, C_OUTLINE);
    return;
  }

  int h = halfH * 2;
  if (h < 1) h = 1;
  int r = min(EYE_RADIUS, h/2);

  tft.fillRoundRect(EYE_L_X - EYE_W/2, EYE_Y - halfH, EYE_W, h, r, C_EYE_WHITE);
  tft.fillRoundRect(EYE_R_X - EYE_W/2, EYE_Y - halfH, EYE_W, h, r, C_EYE_WHITE);

  int pupilR = (int)(9 * openFraction);
  if (pupilR > 1) {
    tft.fillCircle(EYE_L_X, EYE_Y, pupilR, C_EYE_PUPIL);
    tft.fillCircle(EYE_R_X, EYE_Y, pupilR, C_EYE_PUPIL);
    if (pupilR > 3) {
      tft.fillCircle(EYE_L_X - pupilR/3, EYE_Y - pupilR/3, max(1, pupilR/4), C_EYE_SHINE);
      tft.fillCircle(EYE_R_X - pupilR/3, EYE_Y - pupilR/3, max(1, pupilR/4), C_EYE_SHINE);
    }
  }

  tft.drawRoundRect(EYE_L_X - EYE_W/2, EYE_Y - halfH, EYE_W, h, r, C_OUTLINE);
  tft.drawRoundRect(EYE_R_X - EYE_W/2, EYE_Y - halfH, EYE_W, h, r, C_OUTLINE);
}

void drawEqualizer() {
  for (int i = 0; i < EQ_BARS; i++) {
    int halfH = (int)eqHeights[i];
    int bx    = EQ_START_X + i * (EQ_BAR_W + EQ_GAP);
    float posFromCentre = 1.0f - abs((float)i / (EQ_BARS - 1) - 0.5f) * 2.0f;
    uint16_t col = gradientColor(posFromCentre);
    tft.fillRect(bx, EQ_CENTER_Y - EQ_MAX_HALF, EQ_BAR_W, EQ_MAX_HALF * 2, C_FACE);
    tft.fillRoundRect(bx, EQ_CENTER_Y - halfH, EQ_BAR_W, halfH, 2, col);
    tft.fillRoundRect(bx, EQ_CENTER_Y,          EQ_BAR_W, halfH, 2, col);
  }
}

void updateEqualizer() {
  float t = millis() / 1000.0f;
  for (int i = 0; i < EQ_BARS; i++) {
    float pos      = (float)i / (EQ_BARS - 1);
    float envelope = expf(-5.0f * (pos - 0.5f) * (pos - 0.5f));
    float wave     = sinf(pos * 4.0f * PI - t * 5.0f);
    float pulse    = 0.25f * sinf(t * 2.0f);
    float combined = constrain((wave * envelope + pulse + 1.0f) / 2.0f, 0.0f, 1.0f);
    eqHeights[i]   = EQ_MIN_HALF + combined * (EQ_MAX_HALF - EQ_MIN_HALF);
  }
}

void setup() {
  Serial.begin(115200);
  tft.init(SCREEN_W, SCREEN_H);
  tft.setRotation(0);
  tft.fillScreen(C_FACE);

  tft.fillRoundRect(10, 10, SCREEN_W - 20, SCREEN_H - 20, 18, C_FACE);
  tft.drawRoundRect(10, 10, SCREEN_W - 20, SCREEN_H - 20, 18, C_OUTLINE);

  for (int rx : {20, SCREEN_W - 20})
    for (int ry : {20, SCREEN_H - 20})
      tft.fillCircle(rx, ry, 3, C_OUTLINE);

  for (int i = 0; i < EQ_BARS; i++) eqHeights[i] = EQ_MIN_HALF;

  drawBothEyes(1.0f);
  drawEqualizer();

  randomSeed(analogRead(0));
  nextBlink = millis() + BLINK_INTERVAL_MIN + random(BLINK_INTERVAL_MAX - BLINK_INTERVAL_MIN);
}

void loop() {
  unsigned long now = millis();

  if (now - lastEqUpdate >= EQ_UPDATE_MS) {
    lastEqUpdate = now;
    updateEqualizer();
    if (!isBlinking) drawEqualizer();
  }

  if (!isBlinking && now >= nextBlink) {
    isBlinking = true;
    blinkPhase = 0;
    blinkStart = now;
  }

  if (isBlinking) {
    unsigned long elapsed = now - blinkStart;
    float fraction;

    if (blinkPhase == 0) {
      fraction = 1.0f - (float)elapsed / BLINK_CLOSE_MS;
      if (fraction < 0.0f) {
        fraction   = 0.0f;
        blinkPhase = 1;
        blinkStart = now;
      }
    } else {
      fraction = (float)elapsed / BLINK_OPEN_MS;
      if (fraction >= 1.0f) {
        fraction   = 1.0f;
        isBlinking = false;
        nextBlink  = now + BLINK_INTERVAL_MIN + random(BLINK_INTERVAL_MAX - BLINK_INTERVAL_MIN);
      }
    }

    drawBothEyes(fraction);
    drawEqualizer();
  }

  delay(10);
}