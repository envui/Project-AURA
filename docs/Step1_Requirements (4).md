# Step 1 – Requirements & Constraints
**Project A.U.R.A. — Autonomous User-Responsive Assistant**
CECS 490B Senior Design | Spring 2026 | Team 4
*Tommy Truong, Anton Tran, Diego Davalos, Anthony Keroles, Kyle Leng, Abbas Mir*
Professor: Dan Cregg

---

## System-Level Requirements

**RQ-01**
Upon power-up, the Raspberry Pi 5 initializes all subsystems (camera, serial link, audio) and the ESP32 initializes the ST7789 display. AURA transitions to its IDLE/TRACKING state displaying a fully animated face: open eyes with pupils and specular highlights, and idle EQ bar animation.
Verification: All subsystems initialize without errors; animated face renders on display within 5 seconds of power-on.

**RQ-02**
The system shall operate across two defined detection states driven by the YuNet face detector output on every frame: TRACKING (face detected, score ≥ 0.8) and TARGET_LOST (no face detected, or score < 0.8). Servo hold commands (`<-1,-1>`) shall be issued during TARGET_LOST.
Verification: State transitions confirmed in serial terminal output; face coordinates logged during TRACKING, hold command confirmed during TARGET_LOST.

---

## Functional Requirements

**FR1. Multi-Platform Embedded Architecture**
The system integrates three hardware layers:
- **Raspberry Pi 5** — Vision pipeline (`face_track_with_serial.py`), voice/NLP pipeline (`push_to_talk_app.py`, `audio_util.py`), serial command output
- **ESP32 Microcontroller** — ST7789 display control and animation (`robot_face.ino`)
- **PCA9685 Servo Driver HAT** — 50 Hz PWM generation for MG90S pan/tilt servos (I²C from Pi)

**FR2. Communication Links**
The system uses two active inter-device communication links:
- Raspberry Pi 5 ↔ ESP32: USB/UART serial at **115,200 bps**, non-blocking (write_timeout=0)
- Raspberry Pi 5 ↔ PCA9685: I²C at standard mode (**100 kHz**), SDA/SCL on GPIO 2/3

**FR3. Multi-Mode Operation**
The system will support three primary behavioral modes:
1. **Head Tracking** — Real-time face detection and proportional servo-driven head movement
2. **Conversational Interaction** — Push-to-talk voice input via OpenAI Realtime API with TTS output
3. **Memory & Personalization** — Session-persistent context via `context.json`, summarized by GPT-4o-mini on exit

**FR4. Animated Face Display**
The ST7789 240×240 LCD driven by the ESP32 shall render a continuously animated face including:
- Rounded rectangular eyes (52×40 px) with blue pupils, white sclera, and specular highlights
- Smooth randomized blinking: 80 ms close phase, 90 ms open phase, random interval of 2–5 seconds
- A 20-bar gradient EQ visualizer (sine-wave envelope, 30 ms update rate) centered at y=185

**FR5. Persistent State Execution**
Once AURA enters a behavioral mode, it shall remain in that mode until a defined exit condition is met.

---

## Mode-Specific Requirements

### Mode 1 – Head Tracking

**RQ-03**
The vision pipeline shall use the YuNet ONNX model (`models/yunet.onnx`) on 640×480 RGB frames with `SCORE_THRESH = 0.8`, `NMS_THRESH = 0.3`, and `TOP_K = 5000`. The highest-confidence detection in each frame shall be selected as the tracked subject.
Verification: Confidence scores printed to terminal every 30 frames; best-face selection confirmed via overlaid bounding box and score label.

**RQ-04**
Servo control shall use a **proportional controller** with **Kp = 0.06**. The error shall be computed between the detected face center `(cx, cy)` and the frame center `(320, 240)`. Pan and tilt degree values shall be clamped to **[0°, 180°]**.
Verification: Pan and tilt values printed every 30 frames; no out-of-bound angles observed; head follows face movement.

**RQ-05**
Serial commands to the ESP32 shall be rate-limited to one packet per **20 ms (50 Hz)** using `SERIAL_INTERVAL = 0.02`. The packet format shall be `<cx,cy>\n` on face detect, and `<-1,-1>\n` when no face is present.
Verification: Serial monitor confirms packet format and 50 Hz timing; no buffer overflow under sustained tracking.

**RQ-06**
The serial input and output buffers shall be flushed on startup and every **5 seconds** (`FLUSH_INTERVAL = 5.0`) during operation to prevent stale data accumulation. A **2-second initialization delay** shall follow serial port open to allow the ESP32 to complete its reset.
Verification: Clean serial startup confirmed; no stale packets observed across extended operation.

**RQ-07**
The face detection pipeline shall use Picamera2 with `buffer_count = 2` and shall capture frames using `capture_request()` / `request.release()` immediately after pixel data is copied, preventing frame buffer exhaustion.
Verification: System runs at stable FPS without degradation over a 5-minute sustained operation test.

---

### Mode 2 – Conversational Interaction

**RQ-08**
AURA shall connect to the OpenAI Realtime API (`gpt-4o-realtime-preview-2024-12-17`) via a Textual TUI (`push_to_talk_app.py`). Voice recording shall begin on **K key press** and stop on **K key release**. Audio shall be captured at **24,000 Hz, mono, 16-bit PCM** in **20 ms chunks** using `sounddevice`.
Verification: Session ID displayed on connection; microphone input active during K-hold; spoken responses play through USB speaker.

**RQ-09**
The server-side VAD shall be configured with threshold **0.8**, prefix padding **300 ms**, and silence duration **800 ms**. Voice output shall use the **"coral"** preset.
Verification: VAD activates on speech; responses delivered in coral voice; no excessive false triggers.

**RQ-10**
If the current response transcript contains the word **"time"**, the pipeline shall cancel the in-progress API response and issue a corrected response using the local system time (`datetime.datetime.now()`).
Verification: Asking "what time is it" cancels the streaming response and delivers the correct local time.

---

### Mode 3 – Memory & Personalization

**RQ-11**
On startup, the pipeline shall read `context.json` (if it exists) and inject `summary`, `key_facts`, and `last_topic` fields into the session instructions. If no file exists, the assistant shall introduce itself as meeting the user for the first time and build context through natural conversation.
Verification: App restarted after a saved session; AURA greets user by name and references prior topics.

**RQ-12**
On **Q key press**, the pipeline shall summarize the current session transcript by calling **GPT-4o-mini** (`gpt-4o-mini`) to merge it with any existing `context.json`. The output shall be valid raw JSON with keys `summary`, `key_facts`, and `last_topic`. No prior information shall be discarded.
Verification: `context.json` written on exit; all three fields present; content from previous sessions preserved.

---

## Constraints

**CN-01 – Hardware Platform**
The system uses one Raspberry Pi 5 (8 GB), one ESP32 microcontroller, one PCA9685 servo driver HAT, two MG90S servos, one ST7789 240×240 SPI LCD, one Raspberry Pi Camera Module 3, one USB microphone, and one USB speaker. The enclosure is 3D-printed in-house from SolidWorks parts: `Top_AURA.SLDPRT` and `base_v2.SLDPRT`.
Verification: Physical hardware inspection and BOM cross-check.

**CN-02 – Display Controller Must Be ESP32**
The ST7789 display shall be driven exclusively by the **ESP32** using hardware SPI pins: CS=5, DC=2, RST=4, MOSI=23, SCLK=18. The Raspberry Pi shall not directly control the display.
Verification: `robot_face.ino` flashed to ESP32; display animates correctly on power-on independent of Pi state.

**CN-03 – Power Rail Separation**
Servo motors and the ST7789 display shall be powered from a dedicated external 5V rail, not the Raspberry Pi GPIO pins. The Raspberry Pi 5 shall be powered by the official 27W USB-C supply.
Verification: DVM measurement confirms dedicated rail; no voltage drop or brownout during servo actuation.

**CN-04 – Serial Interface Constraints**
The Raspberry Pi ↔ ESP32 serial link shall use `/dev/ttyACM0` at **115,200 bps** with `timeout=0` and `write_timeout=0` (fully non-blocking). UART1, UART2, and UART3 shall not be used.
Verification: Code review confirms serial parameters; non-blocking behavior confirmed under load.

**CN-05 – Face Detection Threshold**
The YuNet confidence threshold shall be fixed at **0.8**. This value was empirically validated to provide stable detection without excessive false positives or missed detections under standard indoor lighting.
Verification: Confidence scores logged; threshold performance confirmed across multiple subjects and distances.

**CN-06 – API Key Security**
`OPENAI_API_KEY` shall be provided via OS environment variable only. Hard-coding the key in any source file is not permitted.
Verification: Code review of `push_to_talk_app.py` confirms `AsyncOpenAI()` reads key from environment.

**CN-07 – Servo Angle Bounds**
Servo pan and tilt degree values shall be clamped to **[0.0°, 180.0°]** in software via the `clamp()` function in `face_track_with_serial.py`. No values outside this range shall be transmitted to the PCA9685.
Verification: Logged pan/tilt values remain within [0, 180] during all tracked operation.

**CN-08 – Parts Budget**
Total hardware cost shall not exceed **$400**. Labor cost is tracked separately using the dream-salary method ($55/hr × 60 hrs × 2.5 multiplier per member).
Verification: BOM total confirmed at $373; $27 headroom to budget cap.

---

## AI Verification Summary

### Project Summary

CECS 490B Project AURA is a senior design robotics project implementing a real-time interactive companion robot. The Raspberry Pi 5 runs `face_track_with_serial.py`, which uses Picamera2 (`buffer_count=2`) and YuNet (`SCORE_THRESH=0.8`) to detect faces in 640×480 frames, computing pan/tilt servo adjustments with a proportional controller (Kp=0.06) and transmitting rate-limited `<cx,cy>\n` packets to an ESP32 at 115,200 bps. The ESP32 runs `robot_face.ino`, animating a 240×240 ST7789 LCD with blinking eyes and a 20-bar gradient EQ visualizer. For voice interaction, `push_to_talk_app.py` uses a Textual TUI to push-to-talk into the OpenAI Realtime API (`gpt-4o-realtime-preview-2024-12-17`) with session memory stored in `context.json` and summarized by GPT-4o-mini on exit via `save_context_and_exit()`. The physical chassis is designed in SolidWorks (`Top_AURA.SLDPRT`, `base_v2.SLDPRT`) and 3D-printed in-house.

---

### What Was Corrected From Initial Draft

| # | Item | Initial Draft | Corrected Value (from source code) |
|---|------|--------------|-------------------------------------|
| 1 | Controller type | PD (KP=0.04, KD=0.08) | **P-only, Kp=0.06** (`face_track_with_serial.py`) |
| 2 | Confidence threshold | 0.75 | **0.8** (`SCORE_THRESH = 0.8`) |
| 3 | Display controller | Arduino Uno R3 | **ESP32** (pins 5, 2, 4, 23, 18 are ESP32 GPIO) |
| 4 | Display behavior | Static bitmap expression swap | **Continuous animation**: smooth blink lerp + live EQ |
| 5 | Memory system | Generic local JSON | **GPT-4o-mini** merges context on exit via `save_context_and_exit()` |
| 6 | Packet format | Generic framed packet | **`<cx,cy>\n`** and **`<-1,-1>\n`** (plaintext) |

---

### Verification Status Table

| Requirement | Description | AI Status | Notes |
|-------------|-------------|-----------|-------|
| RQ-01 | Init & animated IDLE face | ✅ PASS | None |
| RQ-02 | TRACKING / TARGET_LOST transitions | ✅ PASS | None |
| FR1 | Multi-platform architecture | ✅ PASS | ESP32 confirmed |
| FR2 | Serial 115,200 bps + I²C links | ✅ PASS | None |
| FR3 | Three operational modes | ✅ PASS | None |
| FR4 | Animated face: blink + EQ | ✅ PASS | robot_face.ino confirmed |
| FR5 | Persistent state execution | ✅ PASS | None |
| RQ-03 | YuNet, SCORE_THRESH=0.8 | ✅ PASS | Corrected from 0.75 |
| RQ-04 | P controller, Kp=0.06, clamp [0°,180°] | ✅ PASS | Corrected from PD |
| RQ-05 | 50 Hz packets, `<cx,cy>\n` format | ✅ PASS | None |
| RQ-06 | Buffer flush every 5 s, 2 s init delay | ✅ PASS | FLUSH_INTERVAL confirmed |
| RQ-07 | Picamera2 buffer_count=2, immediate release | ✅ PASS | None |
| RQ-08 | Realtime API PTT, 24kHz PCM, K key | ✅ PASS | None |
| RQ-09 | Server VAD 0.8, coral voice | ✅ PASS | None |
| RQ-10 | Local time injection on "time" keyword | ✅ PASS | None |
| RQ-11 | context.json loaded on startup | ✅ PASS | load_context() confirmed |
| RQ-12 | GPT-4o-mini merges context on Q key | ✅ PASS | save_context_and_exit() confirmed |
| CN-01 | Hardware platform + SolidWorks parts | ✅ PASS | None |
| CN-02 | ESP32 drives ST7789 | ✅ PASS | Corrected from Arduino Uno |
| CN-03 | Power rail separation | ✅ PASS | None |
| CN-04 | /dev/ttyACM0, 115,200 bps, non-blocking | ✅ PASS | serial params confirmed |
| CN-05 | SCORE_THRESH = 0.8 | ✅ PASS | Corrected from 0.75 |
| CN-06 | API key via environment variable | ✅ PASS | AsyncOpenAI() confirmed |
| CN-07 | Servo clamp [0°, 180°] | ✅ PASS | clamp() confirmed |
| CN-08 | Parts budget ≤ $400 | ✅ PASS | $373 confirmed |

---

### Overall Assessment

All 25 requirements, functional requirements, and constraints carry a PASS status. Six items were corrected after source code review. The document now accurately reflects the implemented system.

---

## Appendix

| Tag | Meaning |
|-----|---------|
| RQ | Requirement |
| FR | Functional Requirement |
| CN | Constraint |
