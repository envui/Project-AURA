# System Design
**Project A.U.R.A. — Autonomous User-Responsive Assistant**
CECS 490B Senior Design | Spring 2026 | Team 4
*Tommy Truong, Anton Tran, Diego Davalos, Anthony Keroles, Kyle Leng, Abbas Mir*
Professor: Dan Cregg

---

## 1. System Overview

Project AURA is an interactive robotic companion that integrates computer vision, servo-driven head tracking, animated facial display, and conversational AI. The Raspberry Pi 5 acts as the central processor running two independent pipelines: a real-time vision/servo loop (`face_track_with_serial.py`) and a push-to-talk voice assistant (`push_to_talk_app.py`). An ESP32 microcontroller independently drives the ST7789 animated face display (`robot_face.ino`). A PCA9685 HAT handles servo PWM generation over I²C.

### Hardware Communication Summary

| Link | Interface | Parameters |
|------|-----------|------------|
| Pi 5 ↔ ESP32 | USB/UART Serial | `/dev/ttyACM0`, 115,200 bps, timeout=0, write_timeout=0 |
| Pi 5 ↔ PCA9685 | I²C | SDA/SCL (GPIO 2/3), 100 kHz |
| ESP32 ↔ ST7789 LCD | Hardware SPI | CS=5, DC=2, RST=4, MOSI=23, SCLK=18 |
| PCA9685 ↔ MG90S Servos | PWM | 50 Hz, 0°–180° |
| Pi 5 ↔ Camera Module 3 | CSI-2 | 640×480, RGB888, buffer_count=2 |
| Pi 5 ↔ OpenAI API | HTTPS/WebSocket | Realtime API, gpt-4o-realtime-preview-2024-12-17 |

---

## 2. System Architecture

### Block Diagram

```
+------------------------------+
|    Developer / SSH Client    |
|    (VS Code Remote)          |
+------------------------------+
               |
         Wi-Fi / Ethernet
               |
+----------------------------------------------+
|              Raspberry Pi 5                  |
|              (Main Controller)               |
|----------------------------------------------|
|  face_track_with_serial.py                   |
|  - Picamera2 (640x480, buffer_count=2)       |
|  - YuNet ONNX (SCORE_THRESH=0.8)             |
|  - P Controller (Kp=0.06)                    |
|  - Serial TX: <cx,cy>\n @ 50Hz               |
|  - Buffer flush every 5 s                    |
|                                              |
|  push_to_talk_app.py                         |
|  - Textual TUI (K=record, Q=quit+save)       |
|  - OpenAI Realtime API (gpt-4o-realtime)     |
|  - Server VAD (threshold=0.8, 800ms silence) |
|  - AudioPlayerAsync (24kHz, mono, int16)     |
|  - context.json load/save (GPT-4o-mini)      |
|                                              |
|  audio_util.py                               |
|  - AudioPlayerAsync (sounddevice OutputStream)|
|  - send_audio_worker_sounddevice             |
|  - 20ms read chunks @ 24kHz                  |
+----------------------------------------------+
        |                    |
    USB Serial           I²C (100kHz)
    115,200 bps          SDA/SCL GPIO 2/3
        |                    |
        v                    v
+------------------+   +------------------+
|     ESP32        |   |   PCA9685 HAT    |
|  robot_face.ino  |   |  Servo Driver    |
|------------------|   |------------------|
| ST7789 240x240   |   | PWM @ 50Hz       |
| - Animated eyes  |   | Ch0 = Pan servo  |
| - Blink timer    |   | Ch1 = Tilt servo |
| - 20-bar EQ viz  |   +------------------+
| - gradient color |          |
| SPI: CS=5 DC=2   |          v
|      RST=4       |   +--------------+
|      MOSI=23     |   | MG90S x2     |
|      SCLK=18     |   | Pan / Tilt   |
+------------------+   +--------------+
```

### Data Flow

```
Camera Frame (640x480 @ ~30fps)
        |
        v
  YuNet Detection
  (SCORE_THRESH=0.8, NMS=0.3, TOP_K=5000)
        |
  Face found?
  ┌─────┴──────┐
 Yes           No
  |             |
  v             v
cx,cy        <-1,-1>
  |             |
  └──────┬──────┘
         |
  Rate limit check
  (SERIAL_INTERVAL = 0.02s)
         |
         v
  Serial TX → ESP32
  "<cx,cy>\n" or "<-1,-1>\n"
         |
         v
  P Controller (Kp=0.06)
  err_x = cx - 320
  err_y = cy - 240
  pan  -= Kp * err_x  → clamp [0,180]
  tilt -= Kp * err_y  → clamp [0,180]
         |
         v
  PCA9685 I²C → MG90S Servos
```

---

## 3. Functional Description of Modules

### 3.1 face_track_with_serial.py — Vision & Servo Pipeline

**Purpose:** Continuous face detection loop driving servo head movement via serial.

**Key parameters:**
```python
MODEL_PATH     = "models/yunet.onnx"
FRAME_W, FRAME_H = 640, 480
SERIAL_PORT    = '/dev/ttyACM0'
BAUD_RATE      = 115200
SCORE_THRESH   = 0.8
NMS_THRESH     = 0.3
TOP_K          = 5000
Kp             = 0.06
SERIAL_INTERVAL = 0.02   # 50 Hz max
FLUSH_INTERVAL  = 5.0    # Seconds between buffer flush
```

**Responsibilities:**
- Initialize Picamera2 with `buffer_count=2`, format `RGB888`, size 640×480
- Capture frames using `capture_request()` / `request.release()` to prevent buffer starvation
- Run YuNet detector; select best face by highest score (`best = max(faces_mat, key=lambda f: f[14])`)
- Compute pan/tilt error from face center vs. frame center (320, 240)
- Apply proportional control: `pan_deg -= Kp * err_x`, `tilt_deg -= Kp * err_y`
- Clamp angles to [0.0°, 180.0°] using `clamp(v, lo, hi)`
- Send `<cx,cy>\n` packet at ≤ 50 Hz; send `<-1,-1>\n` when no face detected
- Flush serial buffers every 5 seconds; log FPS, CPU%, RAM every 30 frames
- Display live OpenCV window with bounding box, score, and servo angle overlay
- Exit on `q` key; cleanly close camera and serial port

---

### 3.2 push_to_talk_app.py — Voice Assistant Pipeline

**Purpose:** Textual TUI connecting to the OpenAI Realtime API with persistent session memory.

**Key parameters:**
```python
MODEL         = "gpt-4o-realtime-preview-2024-12-17"
VOICE         = "coral"
VAD_THRESHOLD = 0.8
PREFIX_PAD_MS = 300
SILENCE_MS    = 800
MEMORY_FILE   = "context.json"
SUMMARIZER    = "gpt-4o-mini"
```

**Responsibilities:**
- Load `context.json` on startup via `load_context()` and inject into session instructions
- Connect to the OpenAI Realtime API; display session ID in TUI
- Stream microphone audio (`sounddevice.InputStream`, 24kHz, 16-bit, 20ms chunks) while K is held
- Detect "time" keyword in transcript and override with local `datetime.datetime.now()` response
- Accumulate full response transcripts in `acc_items` dictionary keyed by `item_id`
- On Q key: call `save_context_and_exit()` — summarize transcript with GPT-4o-mini, merge into `context.json`
- Audio playback via `AudioPlayerAsync` (non-blocking `sounddevice.OutputStream` with callback queue)

**Memory system (`context.json` schema):**
```json
{
  "summary": "2-3 sentence user overview",
  "key_facts": "bullet list of known facts",
  "last_topic": "most recent conversation subject"
}
```

---

### 3.3 audio_util.py — Audio I/O Utilities

**Purpose:** Shared audio constants and async audio player/sender used by the voice pipeline.

**Constants:**
```python
CHUNK_LENGTH_S = 0.05
SAMPLE_RATE    = 24000
FORMAT         = pyaudio.paInt16
CHANNELS       = 1
```

**Classes/Functions:**

`AudioPlayerAsync` — Thread-safe non-blocking audio output:
- Maintains an internal queue of `numpy.int16` audio chunks
- `sounddevice.OutputStream` callback dequeues chunks to fill output buffer
- `add_data(bytes)` converts raw PCM16 bytes to numpy array and enqueues
- `stop()` flushes queue and halts stream; `reset_frame_count()` tracks playback position

`audio_to_pcm16_base64(audio_bytes)` — Converts arbitrary audio file bytes to 24kHz mono PCM16 via `pydub.AudioSegment`

`send_audio_worker_sounddevice(connection, should_send, start_send)` — Async coroutine reading from `sounddevice.InputStream` and streaming to the Realtime API `input_audio_buffer`

---

### 3.4 robot_face.ino — ESP32 Animated Display

**Purpose:** Standalone animated robot face running on the ESP32, driving the ST7789 240×240 LCD.

**Pin definitions:**
```cpp
TFT_CS   = 5    // ESP32 GPIO
TFT_DC   = 2
TFT_RST  = 4
TFT_MOSI = 23
TFT_SCLK = 18
```

**Display constants:**
```cpp
SCREEN_W = 240, SCREEN_H = 240
EYE_W = 52, EYE_H = 40, EYE_RADIUS = 10
EYE_L_X = 62, EYE_R_X = 178, EYE_Y = 85
EQ_BARS = 20, EQ_BAR_W = 7, EQ_GAP = 3
EQ_CENTER_Y = 185, EQ_MAX_HALF = 28, EQ_MIN_HALF = 2
BLINK_INTERVAL_MIN = 2000, BLINK_INTERVAL_MAX = 5000
BLINK_CLOSE_MS = 80, BLINK_OPEN_MS = 90
EQ_UPDATE_MS = 30
```

**Color palette:**
```cpp
C_FACE      = 0x18C3   // Dark teal background
C_EYE_WHITE = 0xAD75   // Off-white sclera
C_EYE_PUPIL = 0x051F   // Deep blue pupil
C_EYE_SHINE = 0xFFFF   // White specular highlight
C_OUTLINE   = 0x4A69   // Dark outline/border
```

**Key functions:**

`drawBothEyes(float openFraction)` — Renders both eyes scaled by openFraction [0,1]. At openFraction < 0.05, draws flat closed-eye lines. Otherwise draws rounded rect sclera, filled pupil circle (radius scales with openFraction), and specular highlight dot.

`updateEqualizer()` — Computes 20 bar heights using a time-varying sine-wave formula:
```cpp
float envelope = expf(-5.0f * (pos - 0.5f) * (pos - 0.5f));
float wave     = sinf(pos * 4.0f * PI - t * 5.0f);
float pulse    = 0.25f * sinf(t * 2.0f);
```

`gradientColor(float pos)` — Maps bar position to RGB565 gradient (purple/blue center → orange/red edges).

`drawEqualizer()` — Renders EQ bars as symmetric up/down `fillRoundRect` pairs centered at y=185.

**Loop behavior:**
- EQ updated every 30 ms
- Blink triggered by random timer; animates eye close (80 ms) then open (90 ms) phases
- Serial initialized at 115,200 bps (currently receives but does not parse tracking packets — display is standalone)

---

### 3.5 SolidWorks Mechanical Parts

**Top_AURA.SLDPRT** — Top enclosure / face plate of the AURA robot chassis. Houses the ST7789 display opening and camera mounting point.

**base_v2.SLDPRT** — Base/body enclosure (version 2). Houses the servo mounts, electronics bay, and cable routing. Version 2 reflects iterative improvements to servo bracket fitment and internal clearance.

Both parts are 3D-printed in-house using PLA or equivalent filament.

---

## 4. Software Design

### 4.1 Vision Pipeline Pseudocode (face_track_with_serial.py)

```
Initialize:
  ser = Serial('/dev/ttyACM0', 115200, timeout=0, write_timeout=0)
  ser.reset_input_buffer(); ser.reset_output_buffer()
  sleep(2)  // ESP32 reset delay

  picam2 = Picamera2(buffer_count=2, format='RGB888', size=(640,480))
  picam2.start(); sleep(0.5)

  detector = FaceDetectorYN('yunet.onnx', (640,480), score=0.8, nms=0.3, topk=5000)
  pan_deg = 90.0; tilt_deg = 90.0; Kp = 0.06

LOOP:
  if (now - last_flush) >= 5.0:
    flush serial buffers

  request = picam2.capture_request()
  frame = request.make_array("main")   // Already BGR
  request.release()                     // Return buffer immediately

  faces = detector.detect(frame)

  if faces found:
    best = face with highest score
    cx, cy = center of best face bounding box
    err_x = cx - 320;  err_y = cy - 240
    pan_deg  -= Kp * err_x  → clamp(0, 180)
    tilt_deg -= Kp * err_y  → clamp(0, 180)

    if (now - last_serial_time) >= 0.02:
      send "<cx,cy>\n"
      last_serial_time = now

  else:
    if (now - last_serial_time) >= 0.02:
      send "<-1,-1>\n"
      last_serial_time = now

  Draw overlay; show frame
  if 'q' pressed: break

Cleanup: destroyAllWindows; picam2.stop; ser.close
```

### 4.2 Voice Pipeline State Flow (push_to_talk_app.py)

```
Startup:
  context = load_context()   // Read context.json or first-run prompt
  Connect to OpenAI Realtime API
  Update session: instructions=context, voice=coral, VAD={threshold:0.8, silence:800ms}
  Inject memory as conversation.item.create (role=user)

EVENT LOOP:
  session.created   → display session ID
  session.updated   → store session object
  response.cancelled → flush audio player
  response.output_audio.delta → add PCM16 data to AudioPlayerAsync queue
  response.output_audio_transcript.delta:
    accumulate in acc_items[item_id]
    if "time" in transcript → cancel response, inject local time, create new response

KEY EVENTS:
  K pressed  → should_send_audio.set()  (start streaming mic)
  K released → should_send_audio.clear() (stop; commit buffer; create response)
  Q pressed  → save_context_and_exit()

save_context_and_exit():
  transcript = join(acc_items.values())
  previous = read context.json (if exists)
  call GPT-4o-mini to merge previous + transcript
  write result to context.json as raw JSON
  exit()
```

### 4.3 ESP32 Display Loop (robot_face.ino)

```
setup():
  Serial.begin(115200)
  tft.init(240, 240); fillScreen(C_FACE)
  Draw rounded rect border + corner dots
  drawBothEyes(1.0f); drawEqualizer()
  nextBlink = millis() + random(2000, 5000)

loop():
  now = millis()

  if (now - lastEqUpdate) >= 30:
    updateEqualizer()   // Recompute 20 bar heights
    if not blinking: drawEqualizer()
    lastEqUpdate = now

  if not blinking AND now >= nextBlink:
    Start blink: isBlinking=true, blinkPhase=0

  if isBlinking:
    Phase 0 (closing, 80ms):
      openFraction = 1.0 - elapsed/80
      if elapsed >= 80: switch to phase 1
    Phase 1 (opening, 90ms):
      openFraction = elapsed/90
      if elapsed >= 90: done, schedule nextBlink

    drawBothEyes(openFraction)
    drawEqualizer()

  delay(10)
```

### 4.4 Project File Organization

```
aura/
├── raspberry_pi/
│   ├── face_track_with_serial.py    # Vision + servo pipeline
│   ├── push_to_talk_app.py          # Voice assistant TUI
│   ├── audio_util.py                # Audio I/O utilities
│   ├── models/
│   │   └── yunet.onnx               # YuNet face detector model
│   └── context.json                 # Session memory (auto-generated)
│
├── esp32/
│   └── robot_face/
│       └── robot_face.ino           # Animated face display
│
└── mechanical/
    ├── Top_AURA.SLDPRT              # Top enclosure / faceplate
    └── base_v2.SLDPRT              # Base enclosure v2
```

---

## 5. Development Steps and Task Assignments

### Task Assignment Table

| Team Member | Role | Assigned Tasks |
|-------------|------|----------------|
| Tommy Truong | Project Manager | Coordination, milestones, presentation slides, base chassis design |
| Kyle Leng | Head Tracking | P controller tuning, serial integration, tracking pipeline testing |
| Diego Davalos | Raspberry Pi & AI Camera | Picamera2 setup, YuNet integration, buffer management, serial TX |
| Anton Tran | Servo Control | PCA9685 configuration, servo angle mapping, I²C integration |
| Anthony Keroles | Mechanical Design | SolidWorks faceplate and base design, servo mount fitment |
| Abbas Mir | Fabrication & Display | 3D printing, `robot_face.ino` animation, ESP32 flashing and validation |

### Collaboration Tools

- **GitHub Classroom** — Version control and code sharing
- **Visual Studio Code (Remote SSH)** — Python development on Raspberry Pi 5
- **Arduino IDE** — `robot_face.ino` development and ESP32 flashing
- **SolidWorks** — Mechanical enclosure design
- **Tera Term / Serial Monitor** — UART debugging and packet verification

---

## 6. Hardware Design

### Schematic Summary

- Raspberry Pi 5 connects to PCA9685 HAT via I²C (GPIO 2 = SDA, GPIO 3 = SCL)
- PCA9685 generates 50 Hz PWM on channels 0 (pan) and 1 (tilt) for the two MG90S servos
- Raspberry Pi 5 connects to ESP32 via USB (UART, `/dev/ttyACM0`, 115,200 bps)
- ESP32 drives ST7789 via hardware SPI (MOSI=23, SCLK=18, CS=5, DC=2, RST=4)
- Servos and ST7789 powered from dedicated 5V external supply (not from Pi GPIO)
- Raspberry Pi 5 powered by official 27W USB-C supply
- All components share common ground

### Bill of Materials

| Component | Specification | Qty | Status |
|-----------|--------------|-----|--------|
| Raspberry Pi 5 | 8 GB, ARM Cortex-A76 | 1 | Purchased |
| Raspberry Pi Camera Module 3 | CSI-2, autofocus | 1 | Purchased |
| ESP32 | 240MHz dual-core, Wi-Fi/BT | 1 | Purchased |
| PCA9685 Servo Driver HAT | 16-ch I²C PWM | 1 | Purchased |
| MG90S Micro Servo | Metal gear, 180° | 2 | Purchased |
| ST7789 LCD (240×240) | SPI, 1.3" | 1 | Purchased |
| USB Microphone | Plug-and-play | 1 | Purchased |
| USB Speaker | Compact, USB-powered | 1 | Purchased |
| MicroSD Card (256 GB) | OS + models + logs | 1 | Purchased |
| Pi 5 Active Cooler | Official cooler | 1 | Purchased |
| 27W USB-C Power Supply | Official Pi 5 PSU | 1 | Purchased |
| 5V Breadboard Power Supply | Servo / display rail | 1 | Purchased |
| Jumper wires, standoffs | Interconnect & mounting | 1 set | Purchased |
| 3D-printed enclosure | `Top_AURA.SLDPRT`, `base_v2.SLDPRT` | 1 set | In-house |

---

## 7. Conclusion

The AURA system design uses a clean three-platform architecture: Raspberry Pi 5 for vision and voice, ESP32 for expressive display, and PCA9685 for servo control. The two Raspberry Pi pipelines (`face_track_with_serial.py` and `push_to_talk_app.py`) operate independently and can run concurrently. The ESP32 runs autonomously once flashed with `robot_face.ino`. With all modules defined and responsibilities assigned, the system is ready to proceed to **Step 3 – Module Testing**.
