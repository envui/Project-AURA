# System Integration Report
**Project A.U.R.A. — Autonomous User-Responsive Assistant**
CECS 490B Senior Design | Spring 2026 | Team 4
*Tommy Truong, Anton Tran, Diego Davalos, Anthony Keroles, Kyle Leng, Abbas Mir*
Professor: Dan Cregg

---

## Purpose

The purpose of Step 4 is to integrate all independently tested modules into a single functioning system and verify end-to-end behavior across all three operational modes. Integration testing confirms that:

- All inter-module interfaces operate correctly under combined load
- All system-level requirements (RQ-01 through RQ-12, CN-01 through CN-08) are satisfied
- All four development challenges are resolved and do not reappear under integration conditions

All screenshots and videos showing integration test output are stored in:

```
/evidence/Step4_IntegrationTests/
```

All evidence files follow the required naming convention:

```
[TYPE]-[ID]_[Feature]_[ShortDescription].[ext]

TYPE = INT
```

---

## Integration Strategy

Integration was performed incrementally in six phases:

| Phase | Modules Combined | Goal |
|-------|-----------------|------|
| 1 | Camera + YuNet Detector | Verify stable frame capture and detection under real load |
| 2 | Phase 1 + Serial Link | Verify `<cx,cy>\n` packets delivered to ESP32 at 50 Hz |
| 3 | Phase 2 + P Controller + Servos | Verify full tracking loop: face → error → servo movement |
| 4 | Phase 3 + ESP32 (robot_face.ino) | Verify display animates correctly alongside tracking |
| 5 | Phase 4 + push_to_talk_app.py + audio_util.py | Verify voice pipeline runs concurrently with tracking |
| 6 | Phase 5 + context.json memory + SolidWorks chassis | Full system validation: all three demo modes |

---

## System-Level Traceability Table

| Requirement | Integration Test | Evidence |
|-------------|-----------------|---------|
| RQ-01 — Init & animated face within 5 s | INT-01_Startup | INT-01_Startup_InitTest.png |
| RQ-02 — TRACKING / TARGET_LOST transitions | INT-02_StateTransitions | INT-02_StateTransitions_SerialLog.png |
| RQ-03 — YuNet SCORE_THRESH=0.8; best-face selection | INT-03_Detection | INT-03_Detection_ConfidenceTest.png |
| RQ-04 — P controller Kp=0.06; servo clamp [0°,180°] | INT-04_Controller | INT-04_Controller_AngleLog.png |
| RQ-05 — 50 Hz rate-limited serial; `<cx,cy>\n` format | INT-05_Serial | INT-05_Serial_PacketCapture.png |
| RQ-06 — Buffer flush every 5 s; no overflow | INT-06_BufferFlush | INT-06_BufferFlush_60sTest.png |
| RQ-07 — Picamera2 buffer_count=2; no frame starvation | INT-07_Camera | INT-07_Camera_5MinStressTest.png |
| RQ-08 — Realtime API PTT; 24kHz PCM; K key | INT-08_PTT | INT-08_PTT_SessionTest.png |
| RQ-09 — Server VAD 0.8; coral voice | INT-09_VAD | INT-09_VAD_ThresholdTest.png |
| RQ-10 — "time" keyword overrides response with local time | INT-10_TimeOverride | INT-10_TimeOverride_Test.png |
| RQ-11 — context.json loaded; prior context injected | INT-11_MemoryLoad | INT-11_MemoryLoad_SessionRestart.png |
| RQ-12 — GPT-4o-mini merges context on Q key | INT-12_MemorySave | INT-12_MemorySave_JSONVerify.png |
| CN-02 — ESP32 drives ST7789 independently | INT-13_Display | INT-13_Display_AnimationTest.mp4 |
| CN-03 — Servo/display on dedicated power rail | INT-14_Power | INT-14_Power_DVMTest.png |
| CN-04 — 115,200 bps non-blocking serial; no stall | INT-15_Serial | INT-06_BufferFlush_60sTest.png |
| CN-07 — Servo angle clamp [0°, 180°] | INT-04_Controller | INT-04_Controller_AngleLog.png |

---

## Integration Test Results

### Phase 1–3: Vision, Controller, and Servo Loop

| Test ID | Description | Expected | Result |
|---------|-------------|----------|--------|
| INT-01 | Full power-on initialization | All modules init; animated face renders; serial connected | PASS |
| INT-02 | TRACKING state: face at 3 ft | `<cx,cy>\n` packets sent; servo angles update each 20 ms | PASS |
| INT-03 | TARGET_LOST state: face removed | `<-1,-1>\n` sent; servo holds last position | PASS |
| INT-04 | Re-acquisition: face returns at 3 ft | TRACKING resumes; correct packets resume | PASS |
| INT-05 | Controller output: face offset 100 px left | pan_deg increases by 6°; tilt unchanged | PASS |
| INT-06 | Servo angle clamp: face at frame edge | pan_deg reaches 180.0° and holds; no values exceed bound | PASS |
| INT-07 | Serial rate-limit: multiple faces detected per 20 ms | Only one packet per 20 ms window transmitted | PASS |
| INT-08 | Serial buffer flush (60 s sustained tracking) | Flush triggered at ~5 s intervals; no stale packets observed | PASS |
| INT-09 | FPS logging (frame 30, 60, 90…) | FPS, CPU%, RAM printed; system runs at stable rate | PASS |

### Phase 4: Display Integration

| Test ID | Description | Expected | Result |
|---------|-------------|----------|--------|
| INT-10 | ESP32 boot independent of Pi state | Face display animates on power-on without any serial input | PASS |
| INT-11 | Eye blink during concurrent tracking | Blink timer fires at random 2–5 s; tracking not interrupted | PASS |
| INT-12 | EQ animation at 30 ms update rate | All 20 bars animate smoothly; gradient colors render correctly | PASS |
| INT-13 | Display visible with TRACKING active | Animated face and servo movement operate simultaneously without interference | PASS |

### Phase 5: Voice Pipeline Integration

| Test ID | Description | Expected | Result |
|---------|-------------|----------|--------|
| INT-14 | App launch: API key from environment | Session ID displayed in TUI within 3 s | PASS |
| INT-15 | K key PTT: hold, speak, release | Audio streamed during hold; response committed on release | PASS |
| INT-16 | Server VAD activation | VAD detects speech start/end correctly; no clipping of start | PASS |
| INT-17 | TTS playback through USB speaker | Coral voice response plays clearly through speaker | PASS |
| INT-18 | "time" keyword override | Response cancelled mid-stream; local `datetime.now()` spoken | PASS |
| INT-19 | Concurrent tracking + voice | `face_track_with_serial.py` and `push_to_talk_app.py` run simultaneously without resource conflict | PASS |

### Phase 6: Memory and Full System Validation

| Test ID | Description | Expected | Result |
|---------|-------------|----------|--------|
| INT-20 | First run (no context.json) | First-run greeting issued; AURA asks to learn about user | PASS |
| INT-21 | Q key save: GPT-4o-mini merge | `context.json` written; all 3 fields (`summary`, `key_facts`, `last_topic`) present | PASS |
| INT-22 | Session restart with prior context | AURA greets user by name; references prior topic; behavioral difference confirmed | PASS |
| INT-23 | Memory merge: prior + new session | Previous key_facts preserved; new information added | PASS |
| INT-24 | Empty transcript: Q with no speech | `save_context_and_exit()` skips GPT call; exits cleanly | PASS |
| INT-25 | Full Demo 1: tracking + display | Head follows user; animated face visible; EQ and blink continuous | PASS |
| INT-26 | Full Demo 2: voice + tracking | AURA responds to voice while head tracks user | PASS |
| INT-27 | Full Demo 3: memory + adaptation | Returning user receives personalized greeting; first-time user does not | PASS |

---

## Edge Case Integration Tests

| Test ID | Scenario | Expected | Result |
|---------|----------|----------|--------|
| INT-EC-01 | Multiple faces in frame during integration | Highest-score face tracked; others ignored | PASS |
| INT-EC-02 | Serial port `/dev/ttyACM0` not found on boot | `ser = None`; vision loop continues; no crash | PASS |
| INT-EC-03 | Subject moves to frame edge (pan near 180°) | Servo clamped at 180°; no packet out of range | PASS |
| INT-EC-04 | ESP32 disconnected while Pi tracking | Tracking continues; serial write fails silently; no crash | PASS |
| INT-EC-05 | API call during active face tracking | Voice and tracking pipelines do not block each other | PASS |
| INT-EC-06 | `context.json` deleted between sessions | First-run instructions used; no FileNotFoundError | PASS |

---

## Challenges Encountered During Integration

### Challenge 1 — Serial Communication Buffer Overflow
**Problem:** After initial integration the system degraded to approximately one frame every 10 seconds within 3 seconds of operation. A single CPU core was pegged at 100%, indicating a blocking I/O call rather than compute load.

**Root Cause:** The ESP32 was transmitting debug output back to the Pi at 50 Hz. At the original 9,600 bps baud rate, the 64-byte transmit buffer filled faster than the Pi could consume data. Once full, `Serial.println()` blocked, stalling the entire vision pipeline.

**Resolution:**
1. Baud rate increased from 9,600 to **115,200 bps** (`BAUD_RATE = 115200` in `face_track_with_serial.py`), providing 12× throughput headroom
2. Arduino/ESP32 debug output throttled (debug echo sent every 10th packet only)
3. Serial initialized as non-blocking (`timeout=0`, `write_timeout=0`)

**Verification:** 60-second sustained tracking test showed stable FPS with no blocking events.

---

### Challenge 2 — Camera Frame Buffer Exhaustion
**Problem:** After resolving the serial issue, the system ran correctly for approximately 30 seconds before degrading to the same slow rate. The consistent 30-second degradation pattern pointed to resource accumulation rather than a thermal or compute issue.

**Root Cause:** Picamera2's default buffer allocation holds multiple frames in queue. When the face detection loop could not consistently keep pace with 30 fps capture, unprocessed frames accumulated until all buffers were occupied. `capture_array()` then blocked waiting for a free buffer.

**Resolution:**
1. `buffer_count=2` set in `picam2.create_preview_configuration()` to minimize the queue
2. Capture method changed from `capture_array()` to `capture_request()` with immediate `request.release()` after copying the frame array — this returns the buffer to the free pool before any detection work begins

**Verification:** 5-minute stress test showed no FPS degradation or blocking events.

---

### Challenge 3 — Servo Jitter and Oscillation
**Problem:** Initial servo control exhibited continuous micro-jitter even for stationary subjects, and overshoot when tracking rapid lateral movement. Increasing the software dead zone helped but did not eliminate the issue.

**Root Cause:** YuNet detection coordinates fluctuate by several pixels frame-to-frame due to model-level noise, even for a perfectly still subject. A pure proportional controller continuously corrects based on current error with no damping mechanism, causing oscillation.

**Resolution:** Two-layer approach applied:
1. Rate limiting via `SERIAL_INTERVAL=0.02` prevents redundant serial writes between frames
2. The dead zone between valid frame center and detected center absorbs small noise fluctuations
3. Kp tuned empirically to **0.06** — lower than initial values that caused overshoot

**Note:** A PD controller with an EMA filter was considered but not implemented in the current codebase. The tuned P controller at Kp=0.06 with rate-limited serial transmission achieves acceptable stability.

**Verification:** Video demo (`MOD-03_Tracking_ModuleTest.mp4`) shows stable tracking with no observable jitter during stationary hold.

---

### Challenge 4 — Color Channel Inversion in Camera Output
**Problem:** The camera preview showed faces with a blue tint; red objects appeared cyan.

**Root Cause:** The Picamera2 config specified `format="RGB888"`, and the code applied `cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)`. However, Picamera2 outputs data in **BGR order** natively despite the config label, due to a firmware behavior. The conversion was double-swapping the already-correct channels.

**Resolution:** The color conversion step was removed entirely. The comment in `face_track_with_serial.py` now reads:
```python
frame_bgr = request.make_array("main")  # Already in BGR format despite config
```
This resolved the inversion with zero performance cost.

**Verification:** Live preview shows correct skin tones and colors; red objects appear red.

---

## System-Level Verification Summary

| Requirement | Description | Status | Notes |
|-------------|-------------|--------|-------|
| RQ-01 | Init & animated IDLE face | ✅ PASS | Init time ~3.8 s |
| RQ-02 | TRACKING / TARGET_LOST transitions | ✅ PASS | Confirmed via serial log |
| RQ-03 | YuNet SCORE_THRESH=0.8; best-face | ✅ PASS | None |
| RQ-04 | P controller Kp=0.06; clamp [0°,180°] | ✅ PASS | No out-of-bound angles observed |
| RQ-05 | 50 Hz serial; `<cx,cy>\n` format | ✅ PASS | SERIAL_INTERVAL=0.02 confirmed |
| RQ-06 | Buffer flush every 5 s | ✅ PASS | FLUSH_INTERVAL=5.0 confirmed |
| RQ-07 | Picamera2 buffer_count=2; immediate release | ✅ PASS | No starvation in 5-min test |
| RQ-08 | Realtime API PTT; K key; 24kHz PCM | ✅ PASS | None |
| RQ-09 | Server VAD 0.8; coral voice | ✅ PASS | None |
| RQ-10 | "time" override with local datetime | ✅ PASS | Cancellation and re-issue confirmed |
| RQ-11 | context.json loaded on startup | ✅ PASS | load_context() confirmed |
| RQ-12 | GPT-4o-mini merges context on Q key | ✅ PASS | All 3 JSON fields present |
| CN-01 | Hardware platform + SolidWorks parts | ✅ PASS | Physical inspection |
| CN-02 | ESP32 drives ST7789 independently | ✅ PASS | Standalone animation confirmed |
| CN-03 | Power rail separation | ✅ PASS | DVM: no voltage drop under servo load |
| CN-04 | 115,200 bps, non-blocking | ✅ PASS | timeout=0, write_timeout=0 confirmed |
| CN-05 | SCORE_THRESH = 0.8 | ✅ PASS | None |
| CN-06 | API key via environment variable | ✅ PASS | Code review confirmed |
| CN-07 | Servo clamp [0°, 180°] | ✅ PASS | clamp() confirmed in all tracking paths |
| CN-08 | Parts budget ≤ $400 | ✅ PASS | Confirmed total: $373 |

---

## Evidence Files

All system integration test evidence is stored in:

```
/evidence/Step4_IntegrationTests/
```

Key evidence files:

```
INT-01_Startup_InitTest.png
INT-02_StateTransitions_SerialLog.png
INT-03_Detection_ConfidenceTest.png
INT-04_Controller_AngleLog.png
INT-05_Serial_PacketCapture.png
INT-06_BufferFlush_60sTest.png
INT-07_Camera_5MinStressTest.png
INT-08_PTT_SessionTest.png
INT-09_VAD_ThresholdTest.png
INT-10_TimeOverride_Test.png
INT-11_MemoryLoad_SessionRestart.png
INT-12_MemorySave_JSONVerify.png
INT-13_Display_AnimationTest.mp4
INT-14_Power_DVMTest.png
INT-EC_EdgeCases_Combined.png
```

---

## Conclusion

All modules were successfully integrated and validated across the full three-mode operational envelope. The four integration challenges — serial buffer overflow, camera frame buffer exhaustion, servo jitter, and color channel inversion — were each diagnosed, resolved with targeted code changes, and verified under sustained operation before system sign-off.

All 20 requirements and constraints carry a PASS status. The AURA system is complete and ready for the **Final Demonstration**.
