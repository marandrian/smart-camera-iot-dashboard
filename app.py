from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash
import os
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

# 3. KONEKSI KE HIVEMQ MQTT BROKER
MQTT_PORT = 8883  # Port SSL/TLS aman untuk HiveMQ Cloud
MQTT_TOPIC_CMD = "kampus/smartcamera/cmd"

mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
mqtt_client.tls_set()  # Wajib aktif untuk HiveMQ Cloud

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
            # Query ke database Supabase untuk mencari username yang cocok
            user_query = supabase.table("dashboard_users").select("*").eq("username", username).execute()
            
            # Jika user ditemukan, cek apakah hash password-nya cocok
            if user_query.data and check_password_hash(user_query.data[0]['password_hash'], password):
                session['user'] = username  # Set session login sukses
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
            # Cek apakah username sudah pernah terdaftar sebelumnya
            existing_user = supabase.table("dashboard_users").select("username").eq("username", username).execute()
            if existing_user.data:
                flash("Username identity already registered in database context.", "error")
                return render_template('register.html')

            # ENKRIPSI: Ubah password polos menjadi hash acak demi keamanan data
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

            # Simpan data user baru ke dalam tabel Supabase
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
        # Menarik 20 log data terstruktur terakhir dari Supabase SQL
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
            
        # Mempublikasikan perintah ke topik kontrol MQTT dengan QoS 1
        mqtt_client.publish(MQTT_TOPIC_CMD, json.dumps(payload), qos=1)
        return jsonify({"status": "success", "message": f"Perintah {target} dikirim via MQTT"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    # Menjalankan server Flask lokal pada port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)