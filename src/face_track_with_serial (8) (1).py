import cv2
import numpy as np
from picamera2 import Picamera2
import serial
import time
import psutil
import os
import threading

MODEL_PATH = "models/yunet.onnx"

FRAME_W, FRAME_H = 640, 480

# Serial configuration
SERIAL_PORT = '/dev/ttyACM0'  # Your Arduino port
BAUD_RATE = 115200  # Increased from 9600 for faster throughput

SCORE_THRESH = 0.8
NMS_THRESH = 0.3
TOP_K = 5000


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def main():
    global stop_flag
    stop_flag = False
    
    # Initialize serial connection to Arduino
    try:
        # Non-blocking serial with no write timeout and disabled output buffering
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0, write_timeout=0)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(2)  # Wait for Arduino to reset after serial connection
        print(f"Connected to Arduino on {SERIAL_PORT} at {BAUD_RATE} baud")
    except Exception as e:
        print(f"Failed to connect to Arduino: {e}")
        print("Continuing without serial output...")
        ser = None

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (FRAME_W, FRAME_H)},
        buffer_count=2  # Minimum buffers to prevent backlog buildup
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(0.5)  # Let camera warm up

    detector = cv2.FaceDetectorYN.create(
        MODEL_PATH,
        "",
        (FRAME_W, FRAME_H),
        SCORE_THRESH,
        NMS_THRESH,
        TOP_K
    )

    pan_deg = 90.0
    tilt_deg = 90.0
    Kp = 0.06
    
    frame_count = 0
    start_time = time.time()
    process = psutil.Process(os.getpid())
    
    last_serial_time = 0
    SERIAL_INTERVAL = 0.02  # Send to Arduino max every 20ms (50Hz)
    last_flush_time = 0
    FLUSH_INTERVAL = 5.0  # Flush buffers every 5 seconds

    while True:
        frame_count += 1

        # Periodically flush serial buffers to prevent overflow
        current_time = time.time()
        if ser is not None and (current_time - last_flush_time) >= FLUSH_INTERVAL:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            last_flush_time = current_time

        # Capture frame - explicitly grab and release to avoid buffer starvation
        request = picam2.capture_request()
        frame_bgr = request.make_array("main")  # Already in BGR format despite config
        request.release()  # Release buffer immediately so camera can reuse it

        retval, faces_mat = detector.detect(frame_bgr)

        if faces_mat is not None and len(faces_mat) > 0:
            best = max(faces_mat, key=lambda f: f[14])
            x, y, w, h = best[0], best[1], best[2], best[3]
            score = best[14]

            x1 = int(clamp(x, 0, FRAME_W - 1))
            y1 = int(clamp(y, 0, FRAME_H - 1))
            x2 = int(clamp(x + w, 0, FRAME_W - 1))
            y2 = int(clamp(y + h, 0, FRAME_H - 1))

            # OpenCV draw coords stay normal (x,y)
            tl = (x1, y1)
            tr = (x2, y1)
            br = (x2, y2)
            bl = (x1, y2)

            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)

            cv2.rectangle(frame_bgr, tl, br, (0, 255, 0), 2)
            cv2.circle(frame_bgr, (cx, cy), 4, (0, 255, 0), -1)
            cv2.putText(frame_bgr, f"score={score:.2f}", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # ---- OUTPUT COORDINATES FLIPPED TO (y, x) ----
            tl_yx = (y1, x1)
            tr_yx = (y1, x2)
            br_yx = (y2, x2)
            bl_yx = (y2, x1)

            corners = {"tl": tl_yx, "tr": tr_yx, "br": br_yx, "bl": bl_yx}
            center = (cy, cx)  # (y, x)
            box_yx = (y1, x1, y2, x2)  # (y1, x1, y2, x2)

            # ---- SERVO CONTROL USING FLIPPED AXES ----
            # In (y,x) world:
            img_y = FRAME_H / 2
            img_x = FRAME_W / 2

            err_y = center[0] - img_y   # (cy - H/2)
            err_x = center[1] - img_x   # (cx - W/2)

            # Same control law, now with the corrected axes
            pan_deg  -= Kp * err_x
            tilt_deg -= Kp * err_y

            pan_deg = clamp(pan_deg, 0.0, 180.0)
            tilt_deg = clamp(tilt_deg, 0.0, 180.0)

            # Send coordinates to Arduino via serial (rate limited)
            current_time = time.time()
            if ser is not None and (current_time - last_serial_time) >= SERIAL_INTERVAL:
                packet = f"<{int(center[1])},{int(center[0])}>\n"
                ser.write(packet.encode())
                ser.flush()
                last_serial_time = current_time
            
            # Print status every 30 frames
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                cpu_percent = process.cpu_percent()
                mem_info = process.memory_info()
                mem_mb = mem_info.rss / 1024 / 1024  # Convert to MB
                
                print(f"Frame {frame_count}: Face at ({cx},{cy}) | "
                      f"FPS={fps:.1f} | CPU={cpu_percent:.1f}% | "
                      f"RAM={mem_mb:.1f}MB | Pan={pan_deg:.1f} Tilt={tilt_deg:.1f}")

            cv2.putText(frame_bgr, f"pan={pan_deg:.1f} tilt={tilt_deg:.1f}",
                        (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        else:
            # No face detected - send marker to Arduino to hold position (rate limited)
            current_time = time.time()
            if ser is not None and (current_time - last_serial_time) >= SERIAL_INTERVAL:
                ser.write(b"<-1,-1>\n")
                ser.flush()
                last_serial_time = current_time
            
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                cpu_percent = process.cpu_percent()
                mem_info = process.memory_info()
                mem_mb = mem_info.rss / 1024 / 1024
                
                print(f"Frame {frame_count}: No face | "
                      f"FPS={fps:.1f} | CPU={cpu_percent:.1f}% | RAM={mem_mb:.1f}MB")
            
            cv2.putText(frame_bgr, "No face", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Show camera feed with face detection overlay
        cv2.imshow("Face Tracker", frame_bgr)
        # Press q to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    picam2.stop()
    if ser is not None:
        ser.close()
        print("Serial connection closed")
    print("Stopped.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCtrl+C detected, stopping...")
        stop_flag = True
