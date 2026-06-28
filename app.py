import os
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from supabase import create_client, Client
import json

# Load file .env
load_dotenv()

app = Flask(__name__)

# 1. KONFIGURASI SUPABASE
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# 2. KONFIGURASI HIVEMQ MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_PORT = 8883  # Port standar untuk TLS/SSL aman di HiveMQ Cloud
MQTT_TOPIC_CMD = "kampus/smartcamera/cmd"

# Inisialisasi MQTT Client dengan TLS aman
mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
mqtt_client.tls_set()  # Wajib diaktifkan untuk koneksi HiveMQ Cloud

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print("Koneksi MQTT Broker sukses terhubung!")
except Exception as e:
    print(f"Gagal terhubung ke MQTT Broker: {e}")

# --- ROUTE 1: HALAMAN UTAMA DASHBOARD ---
@app.route('/')
def index():
    # Mengambil 1 data terbaru dari database untuk status real-time saat web di-refresh
    try:
        response = supabase.table("tracking_logs").select("*").order("created_at", desc=True).limit(1).execute()
        latest_data = response.data[0] if response.data else {
            "active_speaker": "Hening", "pan_angle": 90, "tilt_angle": 90, "rms_left": 0.0, "rms_right": 0.0
        }
    except Exception as e:
        print(f"Error fetch data terbaru: {e}")
        latest_data = {"active_speaker": "Error", "pan_angle": 90, "tilt_angle": 90, "rms_left": 0.0, "rms_right": 0.0}
        
    return render_template('dashboard.html', latest=latest_data)

# --- ROUTE 2: REST API DATA HISTORY (Sesuai Syarat Kelayakan Proyek) ---
@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        # Ambil 20 data log pelacakan terakhir dari Supabase
        response = supabase.table("tracking_logs").select("*").order("created_at", desc=True).limit(20).execute()
        return jsonify({"status": "success", "data": response.data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ROUTE 3: KONTROL MANUAL OVERRIDE (Mengirim Command via MQTT) ---
@app.route('/control', methods=['POST'])
def control_device():
    try:
        data = request.json
        target = data.get("target")  # Menerima input 'ORANG_A', 'ORANG_B', atau 'TENGAH'
        
        # Pemetaan perintah manual ke sudut servo derajat
        payload = {}
        if target == "ORANG_A":
            payload = {"mode": "MANUAL", "pan": 45, "tilt": 90}
        elif target == "ORANG_B":
            payload = {"mode": "MANUAL", "pan": 135, "tilt": 90}
        elif target == "TENGAH":
            payload = {"mode": "MANUAL", "pan": 90, "tilt": 90}
        elif target == "AUTO":
            payload = {"mode": "AUTO"}  # Mengembalikan kendali ke deteksi suara lokal
            
        # Publish perintah ke MQTT Broker
        mqtt_client.publish(MQTT_TOPIC_CMD, json.dumps(payload), qos=1)
        return jsonify({"status": "success", "message": f"Perintah manual {target} berhasil dikirim via MQTT"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Jalankan lokal untuk testing, port standar Flask adalah 5000
    app.run(host='0.0.0.0', port=5000, debug=True)