from flask import Flask, render_template, Response, jsonify, request
from picamera2 import Picamera2
import cv2, time, os, libcamera
import serial, threading

app = Flask(__name__)

CAPTURE_DIR = "static/captures"
os.makedirs(CAPTURE_DIR, exist_ok=True)

# ================== CAMERA ==================
picam2 = Picamera2()
config = picam2.create_video_configuration(
    main={"size": (1280, 720), "format": "RGB888"},
    transform=libcamera.Transform(rotation=180)
)
picam2.configure(config)
picam2.start()
time.sleep(1)

def gen_frames():
    while True:
        frame = picam2.capture_array()
        ret, buffer = cv2.imencode(".jpg", frame)
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" +
               buffer.tobytes() + b"\r\n")

# ================== UART ==================
ser = serial.Serial("/dev/serial0", 115200, timeout=1)

sensor_data = {
    "iaq": 0,
    "eco2": 0,
    "temp": 0,
    "hum": 0,
    "roll": 0,
    "pitch": 0,
    "status": "NORMAL",
    "calibrating": True,
    "remaining": 0
}

def uart_reader():
    global sensor_data
    while True:
        try:
            line = ser.readline().decode().strip()
            if not line:
                continue

            parts = line.split(",")

            # CALIBRATION MODE
            if parts[0] == "CAL":
                sensor_data["calibrating"] = True
                sensor_data["remaining"] = parts[1]
                sensor_data["temp"] = float(parts[2])
                sensor_data["hum"] = float(parts[3])

            # NORMAL MODE (8 values now)
            elif len(parts) == 8:
                sensor_data["calibrating"] = False
                sensor_data["iaq"] = int(parts[1])
                sensor_data["eco2"] = int(parts[2])
                sensor_data["temp"] = float(parts[3])
                sensor_data["hum"] = float(parts[4])
                sensor_data["roll"] = float(parts[5])
                sensor_data["pitch"] = float(parts[6])
                sensor_data["status"] = parts[7]

        except:
            pass

threading.Thread(target=uart_reader, daemon=True).start()

# ================== ROUTES ==================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/video")
def video():
    return Response(gen_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/sensors")
def sensors():
    return jsonify(sensor_data)

@app.route("/move/<cmd>")
def move(cmd):
    ser.write((cmd + "\n").encode())
    return jsonify(status="ok")

@app.route("/set_threshold/<value>")
def set_threshold(value):
    ser.write(f"THR:{value}\n".encode())
    return jsonify(status="ok")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
