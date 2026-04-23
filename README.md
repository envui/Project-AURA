<div align="center">

# 🤖 A.U.R.A.
### Autonomous User-Responsive Assistant

**CECS 490B Senior Design — Team 4 | CSULB Spring 2026**

*Tommy Truong · Anton Tran · Diego Davalos · Anthony Keroles · Kyle Leng · Abbas Mir*

Professor: Dan Cregg

---

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Arduino](https://img.shields.io/badge/Arduino-ESP32-00979D?style=flat-square&logo=arduino&logoColor=white)](https://arduino.cc)
[![OpenAI](https://img.shields.io/badge/OpenAI-Realtime_API-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com)
[![OpenCV](https://img.shields.io/badge/OpenCV-YuNet-5C3EE8?style=flat-square&logo=opencv&logoColor=white)](https://opencv.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

---

## Overview

AURA is a real-time interactive companion robot that combines computer vision, servo-driven head tracking, animated facial display, and conversational AI into a single embedded platform.

The system uses a **Raspberry Pi 5** to detect and track a user's face in real time, physically orienting the robot's head toward them using a pan-tilt servo mechanism. An **ESP32** independently drives an animated 240×240 LCD face with smooth blinking eyes and a live EQ visualizer. A **push-to-talk voice interface** connects to the OpenAI Realtime API for natural conversation, with session memory that persists and grows across interactions.

<div align="center">

| Demo 1 | Demo 2 | Demo 3 |
|:------:|:------:|:------:|
| 👁️ Head Tracking | 🎙️ Voice Interaction | 🧠 Memory & Personalization |
| Face detection + servo movement | Push-to-talk + GPT-4o responses | Persistent context via `context.json` |

</div>

---

## Features

- **Real-time face tracking** using YuNet ONNX on 640×480 frames via Picamera2
- **Proportional servo control** (Kp=0.06) with 50 Hz rate-limited serial commands to an ESP32
- **Animated robot face** on ST7789 240×240 LCD — blinking eyes, gradient 20-bar EQ visualizer
- **Push-to-talk voice assistant** using the OpenAI Realtime API (`gpt-4o-realtime-preview`)
- **Session memory** — GPT-4o-mini summarizes each conversation into a persistent `context.json` profile
- **Local time awareness** — automatically overrides API response when "time" is mentioned
- **Robust pipeline** — buffer-safe Picamera2 capture, non-blocking serial, periodic flush every 5 s

---

## System Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Raspberry Pi 5                     │
│                                                      │
│  face_track_with_serial.py      push_to_talk_app.py  │
│  ┌─────────────────────────┐   ┌──────────────────┐  │
│  │ Picamera2 (640×480)     │   │ Textual TUI      │  │
│  │ YuNet (score ≥ 0.8)     │   │ K = PTT record   │  │
│  │ P Controller (Kp=0.06)  │   │ Q = save + exit  │  │
│  │ Serial TX <cx,cy>@50Hz  │   │ OpenAI Realtime  │  │
│  └──────────┬──────────────┘   │ GPT-4o-mini mem  │  │
│             │ USB/UART          └──────────────────┘  │
│             │ 115,200 bps                             │
└─────────────┼────────────────────┬────────────────────┘
              │                    │ I²C (100 kHz)
              ▼                    ▼
       ┌─────────────┐      ┌──────────────┐
       │    ESP32    │      │   PCA9685    │
       │ robot_face  │      │  Servo HAT   │
       │   .ino      │      │  PWM @ 50Hz  │
       │             │      └──────┬───────┘
       │ ST7789 LCD  │             │
       │ 240×240 SPI │      ┌──────┴───────┐
       │ Blink + EQ  │      │  MG90S ×2   │
       └─────────────┘      │  Pan / Tilt  │
                            └─────────────┘
```

---

## Hardware

| Component | Specification | Role |
|-----------|--------------|------|
| Raspberry Pi 5 (8 GB) | ARM Cortex-A76, 4-core | Main controller — vision & voice |
| Raspberry Pi Camera Module 3 | CSI-2, autofocus | Face detection input |
| ESP32 Microcontroller | 240MHz dual-core | Display controller |
| PCA9685 Servo Driver HAT | 16-ch I²C PWM | Servo PWM generation |
| MG90S Micro Servo ×2 | Metal gear, 180° | Pan/tilt head movement |
| ST7789 LCD (240×240) | SPI, 1.3" | Animated face display |
| USB Microphone | Plug-and-play | Voice input |
| USB Speaker | Compact, USB-powered | TTS audio output |
| 27W USB-C Power Supply | Official Pi 5 PSU | Pi power |
| 5V Breadboard PSU | Dedicated rail | Servo + display power |
| 3D-Printed Enclosure | `Top_AURA.sldprt`, `base_v2.sldprt` | Chassis (in-house) |

**Total BOM cost: $373** (budget cap: $400)

### Wiring Summary

| Link | Interface | Parameters |
|------|-----------|------------|
| Pi 5 ↔ ESP32 | USB/UART | `/dev/ttyACM0`, 115,200 bps, non-blocking |
| Pi 5 ↔ PCA9685 | I²C | GPIO 2 (SDA) / GPIO 3 (SCL), 100 kHz |
| ESP32 ↔ ST7789 | Hardware SPI | CS=5, DC=2, RST=4, MOSI=23, SCLK=18 |
| PCA9685 ↔ MG90S | PWM | 50 Hz, Ch0=Pan, Ch1=Tilt |

> ⚠️ Servos and display must be powered from a **dedicated 5V rail**, not the Raspberry Pi GPIO.

---

## Software

### Repository Structure

```
aura/
├── raspberry_pi/
│   ├── face_track_with_serial.py   # Vision pipeline + servo control
│   ├── push_to_talk_app.py         # Voice assistant TUI
│   ├── audio_util.py               # Audio I/O utilities
│   ├── models/
│   │   └── yunet.onnx              # YuNet face detector model
│   └── context.json                # Session memory (auto-generated)
│
├── esp32/
│   └── robot_face/
│       └── robot_face.ino          # Animated face display firmware
│
└── mechanical/
    ├── Top_AURA.SLDPRT             # Top enclosure / faceplate
    └── base_v2.SLDPRT              # Base enclosure v2
```

---

## Getting Started

### Prerequisites

**Raspberry Pi 5:**
```bash
sudo apt update && sudo apt install -y python3-pip libopencv-dev ffmpeg portaudio19-dev
pip install picamera2 opencv-python numpy pyserial psutil \
            openai textual sounddevice pyaudio pydub
```

**Download the YuNet ONNX model:**
```bash
mkdir -p models
wget -O models/yunet.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
```

**Set your OpenAI API key:**
```bash
cp .env.example .env
# Edit .env and add your key
```

**ESP32 (Arduino IDE):**
Install the following libraries via Library Manager:
- `Adafruit GFX Library`
- `Adafruit ST7789`

Flash `esp32/robot_face/robot_face.ino` to your ESP32 at 115,200 baud.

---

### Running AURA

**1. Start head tracking** (vision + servo control):
```bash
cd raspberry_pi
python face_track_with_serial.py
```
> Press `q` in the OpenCV window to stop.

**2. Start the voice assistant** (in a separate terminal):
```bash
cd raspberry_pi
python push_to_talk_app.py
```
> Hold `K` to record · Release `K` to send · Press `Q` to save memory and exit

Both scripts can run **simultaneously** — they operate on independent resources.

---

## How It Works

### Face Tracking Pipeline

```
Camera Frame (640×480 @ ~30 fps)
    │
    ▼
YuNet Detection (SCORE_THRESH = 0.8)
    │
    ├─ Face found ──► Select highest-confidence face
    │                  Compute error from frame center (320, 240)
    │                  P controller: pan -= 0.06 × err_x
    │                                tilt -= 0.06 × err_y
    │                  Clamp to [0°, 180°]
    │                  Send <cx,cy>↵ at ≤ 50 Hz
    │
    └─ No face ──────► Send <-1,-1>↵ (hold position)

Serial buffers flushed every 5 s to prevent stale data
```

### Animated Face (robot_face.ino)

The ESP32 runs a fully standalone animated face independent of the Raspberry Pi:

- **Eyes:** Rounded rectangles (52×40 px) with blue pupils (`0x051F`), off-white sclera (`0xAD75`), and specular highlight dots. Open fraction lerps smoothly from 1.0 → 0.0 → 1.0 during each blink.
- **Blink timing:** Random interval 2–5 s · 80 ms close phase · 90 ms open phase
- **EQ visualizer:** 20 bars animated using a time-varying sine-wave envelope:
  ```cpp
  float envelope = expf(-5.0f * (pos - 0.5f) * (pos - 0.5f));
  float wave     = sinf(pos * 4.0f * PI - t * 5.0f);
  ```
  Bars are colored with a gradient from purple/blue (center) to orange/red (edges).

### Session Memory

AURA remembers users across sessions using a rolling `context.json` profile:

```json
{
  "summary":    "2–3 sentence overview of the user",
  "key_facts":  "bullet list of everything known about the user",
  "last_topic": "what was discussed in the last session"
}
```

On **startup** → injected into session instructions via `load_context()`  
On **exit (Q key)** → current transcript merged with prior memory by GPT-4o-mini → written back to `context.json`

No information is ever discarded between sessions.

---

## Configuration

Key parameters in `face_track_with_serial.py`:

```python
SERIAL_PORT     = '/dev/ttyACM0'   # ESP32 serial port
BAUD_RATE       = 115200           # Must match ESP32 Serial.begin()
SCORE_THRESH    = 0.8              # YuNet confidence threshold
Kp              = 0.06             # Proportional gain
SERIAL_INTERVAL = 0.02             # Max serial rate: 50 Hz
FLUSH_INTERVAL  = 5.0              # Buffer flush period (seconds)
FRAME_W, FRAME_H = 640, 480       # Camera resolution
```

Key parameters in `push_to_talk_app.py`:

```python
MODEL         = "gpt-4o-realtime-preview-2024-12-17"
VOICE         = "coral"
VAD_THRESHOLD = 0.8
SILENCE_MS    = 800
SUMMARIZER    = "gpt-4o-mini"     # Used to merge context on exit
```

---

## Known Challenges & Solutions

| Challenge | Root Cause | Solution |
|-----------|-----------|----------|
| Serial pipeline blocked after ~3 s | ESP32 debug echo at 50 Hz overwhelmed 9,600 bps buffer | Increased to **115,200 bps**; throttled debug to every 10th packet; `write_timeout=0` |
| Vision degraded after ~30 s | Picamera2 frame buffer pool exhausted by slow consumer | Set `buffer_count=2`; switched to `capture_request()` + immediate `request.release()` |
| Servo jitter on stationary target | P-controller over-corrects on YuNet coordinate noise | Tuned **Kp=0.06**; added 50 Hz rate-limiting; serial rate cap absorbs small frame-to-frame noise |
| Blue tint on camera output | Picamera2 outputs BGR natively despite `RGB888` config label | Removed `cvtColor()` — frame array used as-is in BGR |

---

## Team

| Member | Role | Contributions |
|--------|------|---------------|
| **Tommy Truong** | Project Manager | Team coordination, milestone tracking, presentations, base chassis design |
| **Kyle Leng** | Head Tracking | P controller tuning, serial integration, tracking pipeline |
| **Diego Davalos** | Raspberry Pi & AI Camera | Picamera2 setup, YuNet integration, buffer management |
| **Anton Tran** | Servo Control | PCA9685 configuration, I²C servo angle mapping |
| **Anthony Keroles** | Mechanical Design | SolidWorks enclosure, servo mounts, chassis assembly |
| **Abbas Mir** | Fabrication & Display | 3D printing, `robot_face.ino` animation, ESP32 firmware |

---

## References

**Hardware & Drivers**
- [Raspberry Pi 5 Documentation](https://www.raspberrypi.com/documentation/)
- [Picamera2 Library](https://github.com/raspberrypi/picamera2)
- [Adafruit PCA9685 Guide](https://learn.adafruit.com/16-channel-pwm-servo-driver)
- [Adafruit ST7789 Library](https://github.com/adafruit/Adafruit-ST7735-Library)

**Computer Vision**
- [OpenCV YuNet Face Detector](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [ArduCAM Raspberry Pi Face Tracking](https://github.com/ArduCAM/RaspberryPiFaceTracking)

**Voice & AI**
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime)
- [OpenWakeWord](https://github.com/dscripka/openWakeWord)

---

<div align="center">

*CECS 490B Senior Design · California State University, Long Beach · Spring 2026*

</div>
