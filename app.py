from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash, Response
import os
import time
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from supabase import create_client, Client
import json

# Mengambil konfigurasi dari file .env
load_dotenv()

app = Flask(__name__)

# Mengamankan session enkripsi data cookie di browser
app.secret_key = os.getenv("FLASK_SECRET_KEY", "tubes_rekayasa_sistem_internet")

# Kredensial Akun Pengujian (Gatekeeper Authorization)
ADMIN_USERNAME = "marcel"
ADMIN_PASSWORD = "password123"

# 1. ENVIRONMENT VARIABLES CHECK
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

if not all([SUPABASE_URL, SUPABASE_ANON_KEY, MQTT_BROKER, MQTT_USER, MQTT_PASSWORD]):
    print("[ERROR] Ada konfigurasi di file .env yang belum terisi! Periksa kembali.")

# 2. KONEKSI KE DATABASE SUPABASE (REST API)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# 3. KONEKSI KE HIVEMQ MQTT BROKER (INTEGRATED PUBLISHER & SUBSCRIBER)
MQTT_PORT = 8883  # Port SSL/TLS aman untuk HiveMQ Cloud
MQTT_TOPIC_CMD = "kampus/smartcamera/cmd"
MQTT_TOPIC_LOGS = "smartcamera/tracking_logs" # Topik dari alat asli Raspberry Pi

mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
mqtt_client.tls_set()  # Wajib aktif untuk HiveMQ Cloud

# --- CALLBACK UNTUK MENDENGARKAN DATA DARI ALAT ASLI ---
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] Terhubung ke Broker. Reason Code: {reason_code}")
    if reason_code == 0:
        # Daftarkan diri agar VPS mendengarkan kiriman data pelacakan dari Raspi
        client.subscribe(MQTT_TOPIC_LOGS)
        print(f"[MQTT SUBSCRIBED] Mendengarkan aliran data asli pada topik: {MQTT_TOPIC_LOGS}")

def on_message(client, userdata, msg):
    # Filter: Hanya proses pesan yang berasal dari topik log pelacakan mikrofon
    if msg.topic == MQTT_TOPIC_LOGS:
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            print(f"[MQTT RECEIVED] Log Data Mikrofon Masuk: {payload}")
            
            # Petakan struktur JSON kiriman Raspi langsung ke nama kolom Supabase kamu
            data_insert = {
                "active_speaker": payload.get("active_speaker"),
                "pan_angle": payload.get("pan_angle"),
                "tilt_angle": payload.get("tilt_angle"),
                "rms_left": payload.get("rms_left"),
                "rms_right": payload.get("rms_right")
            }
            
            # Kirim data asli ke tabel database Supabase
            supabase.table("tracking_logs").insert(data_insert).execute()
            print("[SUPABASE] Log mic asli sukses dilempar ke database!")
            
        except Exception as e:
            print(f"[SERVER DATABASE ERROR] Gagal menyimpan log dari MQTT ke Supabase: {e}")

# Daftarkan fungsi callback ke dalam instance client MQTT v2
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print("[SUCCESS] MQTT Broker berhasil terhubung ke Cloud!")
except Exception as e:
    print(f"[MQTT ERROR] Gagal tersambung ke Broker: {e}")


# --- RUTE 1: HALAMAN UTAMA DASHBOARD (DIPROTEKSI SESSION) ---
@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))

    try:
        response = supabase.table("tracking_logs").select("*").order("created_at", desc=True).limit(1).execute()
        if response.data:
            latest_data = response.data[0]
        else:
            latest_data = {"active_speaker": "Belum Ada Data", "pan_angle": 90, "tilt_angle": 90, "rms_left": 0.0, "rms_right": 0.0}
    except Exception as e:
        print(f"[DATABASE ERROR] Gagal fetch data terbaru pada rute utama: {e}")
        latest_data = {"active_speaker": "Database Error", "pan_angle": 90, "tilt_angle": 90, "rms_left": 0.0, "rms_right": 0.0}
        
    return render_template('dashboard.html', latest=latest_data)


# --- RUTE BARU: PROSES LOGIN MENGGUNAKAN DATABASE SUPABASE ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')

        try:
            user_query = supabase.table("dashboard_users").select("*").eq("username", username).execute()
            
            if user_query.data and check_password_hash(user_query.data[0]['password_hash'], password):
                session['user'] = username  
                return redirect(url_for('index'))
            else:
                flash("Invalid username identity or password configuration token.", "error")
        except Exception as e:
            print(f"[LOGIN ERROR] Gagal melakukan autentikasi: {e}")
            flash("Database validation gateway timeout.", "error")

    return render_template('login.html')


# --- RUTE BARU: SISTEM REGISTRASI AKUN BARU (POST & GET) ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password')

        if not username or not password:
            flash("Username and password tokens cannot be empty.", "error")
            return render_template('register.html')

        try:
            existing_user = supabase.table("dashboard_users").select("username").eq("username", username).execute()
            if existing_user.data:
                flash("Username identity already registered in database context.", "error")
                return render_template('register.html')

            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

            supabase.table("dashboard_users").insert({
                "username": username,
                "password_hash": hashed_password
            }).execute()

            flash("Account context registration successful. Please sign in.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            print(f"[REGISTER ERROR] Gagal menyimpan user baru: {e}")
            flash("Failed to commit identity data payload to remote cluster.", "error")

    return render_template('register.html')


# --- RUTE BARU: PENGHANCUR SESSION (LOGOUT SYSTEM) ---
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# --- RUTE 2: REST API UNTUK DATA HISTORIS ---
@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        response = supabase.table("tracking_logs").select("*").order("created_at", desc=True).limit(20).execute()
        return jsonify({"status": "success", "data": response.data})
    except Exception as e:
        print(f"[REST API ERROR] Gagal menarik log data historis: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- RUTE 3: KIRIM COMMAND OVERRIDE VIA MQTT (Kontrol Jarak Jauh) ---
@app.route('/control', methods=['POST'])
def control_device():
    try:
        data = request.json
        target = data.get("target")
        
        payload = {}
        if target == "ORANG_A":
            payload = {"mode": "MANUAL", "pan": 45, "tilt": 90}
        elif target == "ORANG_B":
            payload = {"mode": "MANUAL", "pan": 135, "tilt": 90}
        elif target == "TENGAH":
            payload = {"mode": "MANUAL", "pan": 90, "tilt": 90}
        elif target == "AUTO":
            payload = {"mode": "AUTO"}
            
        mqtt_client.publish(MQTT_TOPIC_CMD, json.dumps(payload), qos=1)
        return jsonify({"status": "success", "message": f"Perintah {target} dikirim via MQTT"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ========================================================
# PIPELINE BARU: PENGURUS LIVE STREAMING PI CAMERA
# ========================================================
# Variabel global untuk menampung buffer gambar terakhir di memori VPS
latest_frame = None

@app.route('/api/upload_frame', methods=['POST'])
def upload_frame():
    global latest_frame
    # Tangkap data byte biner mentah dari Raspberry Pi
    latest_frame = request.data
    return jsonify({"status": "success"}), 200

def generate_mjpeg_stream():
    global latest_frame
    while True:
        if latest_frame:
            # Bungkus byte gambar ke dalam format part-boundary MJPEG standard
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + latest_frame + b'\r\n')
        time.sleep(0.04) # Batasi sekitar 25 FPS agar hemat load CPU VPS

@app.route('/api/video_feed')
def video_feed():
    # Mengeluarkan response multipart stream khusus yang dipahami langsung oleh tag <img> HTML
    return Response(generate_mjpeg_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    # Menjalankan server Flask lokal pada port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)