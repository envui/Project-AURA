# Module Testing Report
**Project A.U.R.A. — Autonomous User-Responsive Assistant**
CECS 490B Senior Design | Spring 2026 | Team 4
*Tommy Truong, Anton Tran, Diego Davalos, Anthony Keroles, Kyle Leng, Abbas Mir*
Professor: Dan Cregg

---

## Purpose

The purpose of Step 3 is to implement and test each driver and module independently before system integration. Drivers provide **hardware-level control**, while modules implement **feature/application logic**.

Each module is tested independently using a dedicated test script (`module_test.py`) or test sketch (`ModuleTest.ino`). Each module includes:

- Two normal test cases
- One edge case test

All screenshots and videos showing module test output are stored in:

```
/evidence/Step3_ModuleTests/
```

All evidence files follow the required naming convention:

```
[TYPE]-[ID]_[ModuleOrFeature]_[ShortDescription].[ext]
```

For Step 3:

```
TYPE = MOD
```

Each screenshot contains **all three test cases for the module**.

Modules **TrackingPipeline, ServoControl, and RobotFace also include demonstration videos (.mp4)** showing physical hardware behavior.

---

## Module-Level Traceability Table

| Requirement | Responsible Module | Module Test Evidence |
|-------------|-------------------|----------------------|
| Picamera2 delivers frames at stable fps, buffer_count=2 | face_track_with_serial.py (Camera) | MOD-01_Camera_ModuleTest.png |
| YuNet detects face at SCORE_THRESH=0.8, selects best by score | face_track_with_serial.py (Detector) | MOD-02_Detector_ModuleTest.png |
| P controller computes correct pan/tilt delta, clamps to [0,180] | face_track_with_serial.py (Controller) | MOD-03_Tracking_ModuleTest.png + MOD-03_Tracking_ModuleTest.mp4 |
| Serial link transmits at 115,200 bps, rate-limited to 50 Hz | face_track_with_serial.py (Serial) | MOD-04_SerialLink_ModuleTest.png |
| Buffer flush occurs every 5 s; no overflow under sustained load | face_track_with_serial.py (BufferMgmt) | MOD-04_SerialLink_ModuleTest.png |
| PCA9685 drives MG90S servos via I²C correctly | Servo hardware (via Pi I²C) | MOD-05_Servo_ModuleTest.png + MOD-05_Servo_ModuleTest.mp4 |
| ST7789 animated eyes render and blink correctly | robot_face.ino (Eyes) | MOD-06_RobotFace_ModuleTest.png + MOD-06_RobotFace_ModuleTest.mp4 |
| 20-bar EQ visualizer animates at 30 ms update rate | robot_face.ino (EQ) | MOD-06_RobotFace_ModuleTest.png |
| AudioPlayerAsync plays PCM16 audio without dropout | audio_util.py | MOD-07_Audio_ModuleTest.png |
| OpenAI Realtime API connection established; session ID returned | push_to_talk_app.py (Connection) | MOD-08_RealtimeAPI_ModuleTest.png |
| Push-to-talk K key streams audio; Q key saves context | push_to_talk_app.py (PTT) | MOD-08_RealtimeAPI_ModuleTest.png |
| context.json loaded on startup; GPT-4o-mini merges on exit | push_to_talk_app.py (Memory) | MOD-09_Memory_ModuleTest.png |
| Local time override triggered by "time" in transcript | push_to_talk_app.py (TimeOverride) | MOD-09_Memory_ModuleTest.png |

---

## Module Test Results

### Normal Test Cases

| Test ID | Module | Input / Action | Expected Output | Result |
|---------|--------|---------------|----------------|--------|
| TC-CAM-01 | Camera (Picamera2) | Initialize with buffer_count=2, RGB888, 640×480 | Frame stream starts; no init error | PASS |
| TC-CAM-02 | Camera (Picamera2) | Call `capture_request()` then `request.release()` | Frame returned as BGR array; buffer released immediately | PASS |
| TC-DET-01 | Detector (YuNet) | Subject at ~3 ft, standard indoor lighting | Score ≥ 0.8; bounding box printed; best face selected by score | PASS |
| TC-DET-02 | Detector (YuNet) | Two faces in frame simultaneously | Face with highest `f[14]` score selected; other ignored | PASS |
| TC-TRK-01 | P Controller | Face center at (420, 240) — offset right 100 px | err_x=100; pan_deg decreases by 6.0°; tilt unchanged | PASS |
| TC-TRK-02 | P Controller | Face centered at (320, 240) | err_x=0, err_y=0; pan_deg and tilt_deg unchanged | PASS |
| TC-SER-01 | Serial Link | Face detected; SERIAL_INTERVAL elapsed | `<cx,cy>\n` packet transmitted; last_serial_time updated | PASS |
| TC-SER-02 | Serial Link | No face detected; SERIAL_INTERVAL elapsed | `<-1,-1>\n` transmitted; Arduino holds position | PASS |
| TC-SRV-01 | Servo (PCA9685) | Command pan channel to 45° | MG90S pan servo moves to 45° position | PASS |
| TC-SRV-02 | Servo (PCA9685) | Command tilt channel to 135° | MG90S tilt servo moves to 135° position | PASS |
| TC-EYE-01 | robot_face.ino (Eyes) | Power on ESP32 | Eyes render open (openFraction=1.0), pupils and highlights visible | PASS |
| TC-EYE-02 | robot_face.ino (Blink) | Wait for blink timer | Eyes animate closed (80ms) then open (90ms) smoothly | PASS |
| TC-EQ-01 | robot_face.ino (EQ) | Monitor display for 30ms cycles | 20 EQ bars animate with gradient color and sine-wave motion | PASS |
| TC-AUD-01 | audio_util.py (AudioPlayerAsync) | Add PCM16 bytes via `add_data()` | Audio plays through USB speaker without dropout | PASS |
| TC-API-01 | push_to_talk_app.py (Connection) | Launch app with valid API key | Session ID displayed in TUI within 3 seconds | PASS |
| TC-API-02 | push_to_talk_app.py (PTT) | Hold K key; speak; release K | Audio streamed to API; response spoken in coral voice | PASS |
| TC-MEM-01 | push_to_talk_app.py (load_context) | `context.json` exists with prior data | Summary, key_facts, last_topic injected into instructions | PASS |
| TC-MEM-02 | push_to_talk_app.py (save_context) | Press Q after conversation | GPT-4o-mini merges transcript; `context.json` updated with all 3 fields | PASS |
| TC-TIME-01 | push_to_talk_app.py (TimeOverride) | Ask "what time is it" | In-progress response cancelled; local datetime injected; correct time spoken | PASS |
| TC-FLUSH-01 | Serial Buffer Mgmt | Run tracking for > 5 seconds | `reset_input_buffer()` and `reset_output_buffer()` called; no stale packets | PASS |

---

### Edge Case Tests

| Test ID | Module | Input / Action | Expected Output | Result |
|---------|--------|---------------|----------------|--------|
| TC-CAM-03 | Camera (Picamera2) | Camera physically disconnected at runtime | Exception caught; error printed; system exits cleanly | PASS |
| TC-DET-03 | Detector (YuNet) | Subject at ~8 ft (low confidence) | Score < 0.8; `<-1,-1>` sent; TRACKING not active | PASS |
| TC-TRK-03 | P Controller | Commanded pan_deg would exceed 180° | `clamp(pan_deg, 0.0, 180.0)` limits output; value stays at 180.0 | PASS |
| TC-SER-03 | Serial Link | Serial TX called before SERIAL_INTERVAL elapsed | Packet skipped; `last_serial_time` not updated | PASS |
| TC-EYE-03 | robot_face.ino (Eyes) | `openFraction` < 0.05 passed to `drawBothEyes()` | Flat closed-eye line drawn; no roundRect or pupil rendered | PASS |
| TC-AUD-03 | audio_util.py (AudioPlayerAsync) | `add_data()` called but output queue still draining | New chunk appended to queue; no dropout; playback continuous | PASS |
| TC-API-03 | push_to_talk_app.py | Invalid or expired API key at launch | Connection fails; error message shown in TUI; app does not crash | PASS |
| TC-MEM-03 | push_to_talk_app.py (load_context) | `context.json` does not exist | First-run instructions returned; no FileNotFoundError | PASS |
| TC-MEM-04 | push_to_talk_app.py (save_context) | Empty conversation (no transcript) | `save_context_and_exit()` skips API call; exits cleanly | PASS |
| TC-FLUSH-02 | Serial Buffer Mgmt | Serial port not found at startup (`/dev/ttyACM0` missing) | Exception caught; `ser = None`; script continues without serial | PASS |

---

## Test Case Explanations

### Camera Module (Picamera2)
The camera driver uses Picamera2 with `buffer_count=2` to minimize frame buffering. Testing verifies that frames are returned correctly and that `request.release()` is called immediately after pixel data is extracted, preventing buffer pool exhaustion during sustained operation. The edge case confirms clean recovery when the camera is disconnected.

### Face Detector Module (YuNet)
The YuNet ONNX model runs on each 640×480 BGR frame with `SCORE_THRESH=0.8`. Testing verifies that the correct face is selected using `max(faces_mat, key=lambda f: f[14])` (index 14 = score), that low-confidence detections are rejected, and that multi-face scenes select the highest-scoring detection.

### Proportional Controller
The P controller computes `pan_deg -= Kp * err_x` and `tilt_deg -= Kp * err_y` where `Kp=0.06` and the error is relative to the 640×480 frame center (320, 240). Tests verify correct delta magnitude, proper behavior at center (zero error), and clamping to [0.0°, 180.0°] via the `clamp()` function.

### Serial Link Module
The serial link transmits packets at a maximum rate of 50 Hz using `SERIAL_INTERVAL=0.02`. Testing verifies correct packet format (`<cx,cy>\n` and `<-1,-1>\n`), rate limiting, and periodic buffer flushing every 5 seconds. The edge case confirms that a missing serial port does not crash the main application.

### Servo Control (PCA9685 + MG90S)
The PCA9685 HAT generates 50 Hz PWM for two MG90S servos via I²C from the Raspberry Pi. Testing verifies angle mapping and smooth actuation across the full 0°–180° range.

A video demonstration (`MOD-05_Servo_ModuleTest.mp4`) shows physical pan/tilt head movement.

### Robot Face Display (robot_face.ino)
The ESP32 runs a standalone animated face on the ST7789 240×240 LCD. Testing verifies:
- **Eyes:** `drawBothEyes(openFraction)` smoothly transitions from open to closed based on blink phase timing (80 ms close, 90 ms open)
- **EQ visualizer:** `updateEqualizer()` recomputes 20 bar heights every 30 ms using a sine-wave envelope; `gradientColor()` maps bar position to an RGB565 gradient (purple→orange)
- **Edge case:** When `openFraction < 0.05`, a flat horizontal line is drawn instead of the rounded rect eye

A video demonstration (`MOD-06_RobotFace_ModuleTest.mp4`) shows the animated face with blinking and EQ motion.

### Audio Utility Module (audio_util.py)
`AudioPlayerAsync` uses a thread-safe queue with a `sounddevice.OutputStream` callback. Testing verifies PCM16 byte ingestion, correct numpy array conversion, and dropout-free playback. The edge case verifies that adding data to an already-draining queue does not cause interruption.

### OpenAI Realtime API Module (push_to_talk_app.py — Connection)
The `RealtimeApp` connects to `gpt-4o-realtime-preview-2024-12-17` and configures the session with the loaded context instructions, coral voice, and server VAD. Testing verifies session ID display, push-to-talk audio streaming, and spoken response playback.

### Session Memory Module (push_to_talk_app.py — Memory)
`load_context()` reads `context.json` and builds a system prompt injecting `summary`, `key_facts`, and `last_topic`. `save_context_and_exit()` sends the transcript to GPT-4o-mini for merging and writes clean JSON. Edge cases verify graceful handling of a missing file (first-run) and an empty transcript (no API call made).

### Local Time Override (push_to_talk_app.py — TimeOverride)
When "time" appears in the accumulated `response.output_audio_transcript.delta`, the pipeline sends `response.cancel`, calls `get_current_time()` to get `datetime.datetime.now()`, and issues a new `response.create` with the local time as instructions. Testing verifies successful cancellation and correct local time playback.

---

## Evidence Files

All module test evidence is stored in:

```
/evidence/Step3_ModuleTests/
```

Evidence files:

```
MOD-01_Camera_ModuleTest.png
MOD-02_Detector_ModuleTest.png
MOD-03_Tracking_ModuleTest.png
MOD-03_Tracking_ModuleTest.mp4
MOD-04_SerialLink_ModuleTest.png
MOD-05_Servo_ModuleTest.png
MOD-05_Servo_ModuleTest.mp4
MOD-06_RobotFace_ModuleTest.png
MOD-06_RobotFace_ModuleTest.mp4
MOD-07_Audio_ModuleTest.png
MOD-08_RealtimeAPI_ModuleTest.png
MOD-09_Memory_ModuleTest.png
```

---

## Conclusion

All drivers and modules were successfully implemented and tested independently. Results confirm correct operation of the Picamera2 frame capture pipeline, YuNet face detection and best-face selection, proportional servo control with clamping, rate-limited serial packet transmission with buffer flush management, ESP32 animated face display with smooth blinking and EQ animation, AudioPlayerAsync PCM16 playback, OpenAI Realtime API push-to-talk interaction, and session memory load/save using GPT-4o-mini.

With module testing complete, the system is ready to proceed to **Step 4 – System Integration**.
