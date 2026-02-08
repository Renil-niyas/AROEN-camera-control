from flask import Flask, render_template, Response, jsonify, request
from picamera2 import Picamera2
import cv2, time, os, libcamera, random, subprocess, os, fcntl

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

        # SAFETY: handle 4-channel frames if libcamera changes
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        ret, buffer = cv2.imencode(
            ".jpg", frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        )
        if not ret:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            buffer.tobytes() + b"\r\n"
        )
        time.sleep(0.05)

# ================== UART (RAW, SHELL-LIKE) ==================
UART_DEV = "/dev/serial0"

def uart_send(cmd):
    try:
        with open(UART_DEV, "wb", buffering=0) as f:
            f.write((cmd + "\n").encode())
    except Exception as e:
        print("UART error:", e)

# ================== PI TEMP ==================
def get_pi_temp():
    try:
        out = subprocess.check_output(
            ["vcgencmd", "measure_temp"]
        ).decode()
        return float(out.split("=")[1].replace("'C", ""))
    except:
        return None

# ================== ROUTES ==================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/video")
def video():
    return Response(
        gen_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/move/<cmd>")
def move(cmd):
    uart_send(cmd)
    return jsonify(status="ok", cmd=cmd)

@app.route("/capture")
def capture():
    frame = picam2.capture_array()
    name = f"img_{int(time.time())}.jpg"
    path = os.path.join(CAPTURE_DIR, name)
    cv2.imwrite(path, frame)
    return jsonify(status="ok", file=f"/static/captures/{name}")

@app.route("/images")
def images():
    files = sorted(os.listdir(CAPTURE_DIR), reverse=True)
    return jsonify(files=[f"/static/captures/{f}" for f in files])

@app.route("/delete", methods=["POST"])
def delete_image():
    path = request.json.get("path", "")
    real = path.replace("/static/", "static/")
    if os.path.exists(real):
        os.remove(real)
        return jsonify(status="ok")
    return jsonify(status="error")

@app.route("/sensors")
def sensors():
    return jsonify({
        "gas1": random.randint(180, 300),
        "gas2": random.randint(150, 280),
        "temp": random.randint(27, 35),
        "hum": random.randint(45, 70),
        "pi_temp": get_pi_temp()
    })

# ================== MAIN ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
