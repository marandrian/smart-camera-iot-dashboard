import os
import time
import random
import json
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from supabase import create_client, Client

# Load konfigurasi dari file .env yang sama
load_dotenv()

# 1. INSALISASI KLIEN SUPABASE (HTTP/REST API)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# 2. KONFIGURASI HIVEMQ MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_PORT = 8883
MQTT_TOPIC_CMD = "kampus/smartcamera/cmd"

# Variabel kontrol global untuk menyimulasikan status perangkat
current_mode = "AUTO"  # Pilihan: AUTO atau MANUAL
simulated_pan = 90
simulated_tilt = 90

# --- CALLBACK MQTT: KETIKA BERHASIL TERHUBUNG ---
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Terhubung ke Broker dengan kode respon: {rc}")
    # Subscribe ke topik perintah dari web dashboard cloud
    client.subscribe(MQTT_TOPIC_CMD, qos=1)
    print(f"[MQTT] Mendengarkan perintah pada topik: {MQTT_TOPIC_CMD}")

# --- CALLBACK MQTT: KETIKA MENERIMA COMMAND DARI DASHBOARD ---
def on_message(client, userdata, msg):
    global current_mode, simulated_pan, simulated_tilt
    try:
        payload = json.loads(msg.payload.decode())
        print(f"\n[MQTT CMD] Menerima data perintah: {payload}")
        
        # Ekstraksi instruksi kendali sesuai isi payload dari Flask
        current_mode = payload.get("mode", "AUTO")
        
        if current_mode == "MANUAL":
            simulated_pan = payload.get("pan", 90)
            simulated_tilt = payload.get("tilt", 90)
            print(f"[EXECUTOR] Sumbu digerakkan secara MANUAL ke -> Pan: {simulated_pan}°, Tilt: {simulated_tilt}°")
        else:
            print("[EXECUTOR] Sistem dikembalikan ke mode AUTOMATIC (Pelacakan Suara)")
            
    except Exception as e:
        print(f"Gagal memproses perintah MQTT: {e}")

# Inisialisasi Klien MQTT dengan proteksi TLS/SSL
device_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
device_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
device_client.tls_set()
device_client.on_connect = on_connect
device_client.on_message = on_message

try:
    device_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    device_client.loop_start()
except Exception as e:
    print(f"Koneksi MQTT Perangkat Gagal: {e}")

print("\n=== SIMULATOR RASPBERRY PI 3 MULAI BERJALAN ===")

# --- LOOP UTAMA: SIMULASI PEMBACAAN SENSOR DAN EDGE LOGIC ---
try:
    while True:
        # 1. Menyimulasikan nilai pembacaan tingkat energi suara (RMS)
        # Kondisi acak: sesekali Orang A keras, sesekali Orang B keras, sesekali hening
        skenario = random.choice(["A", "B", "HENING"])
        
        if skenario == "A":
            rms_left = round(random.uniform(0.15, 0.45), 4)
            rms_right = round(random.uniform(0.01, 0.05), 4)
        elif skenario == "B":
            rms_left = round(random.uniform(0.01, 0.05), 4)
            rms_right = round(random.uniform(0.15, 0.45), 4)
        else:
            rms_left = round(random.uniform(0.01, 0.04), 4)
            rms_right = round(random.uniform(0.01, 0.04), 4)

        # 2. PROSES EDGE COMPUTING (Rule-Based Threshold & Filtering lokal)
        # Batas minimal suara diakui (Noise Floor) = 0.08
        THRESHOLD_NOISE = 0.08
        
        if current_mode == "AUTO":
            if rms_left > THRESHOLD_NOISE and rms_left > (rms_right + 0.05):
                active_speaker = "Orang A"
                simulated_pan = 45
                simulated_tilt = 90
            elif rms_right > THRESHOLD_NOISE and rms_right > (rms_left + 0.05):
                active_speaker = "Orang B"
                simulated_pan = 135
                simulated_tilt = 90
            else:
                active_speaker = "Hening"
                # Posisi sudut servo tetap mempertahankan posisi terakhir jika hening
        else:
            active_speaker = "MANUAL OVERRIDE"

        print(f"\n[EDGE] Skenario: {skenario} | Speaker Aktif: {active_speaker}")
        print(f"[EDGE] Nilai Sensor -> RMS Left: {rms_left} | RMS Right: {rms_right}")
        print(f"[EDGE] Posisi Fisik -> Pan: {simulated_pan}° | Tilt: {simulated_tilt}°")

        # 3. INTEGRASI DATABASE: Kirim log data ke Supabase menggunakan REST API
        try:
            log_data = {
                "active_speaker": active_speaker,
                "pan_angle": simulated_pan,
                "tilt_angle": simulated_tilt,
                "rms_left": rms_left,
                "rms_right": rms_right
            }
            # Eksekusi insert data terstruktur ke tabel SQL
            response = supabase.table("tracking_logs").insert(log_data).execute()
            print("[DATABASE] Log data berhasil disimpan ke Supabase SQL terstruktur.")
        except Exception as e:
            print(f"[DATABASE] Gagal mengunggah data ke Supabase: {e}")

        # Tunda pengiriman data berikutnya selama 3 detik
        time.sleep(3)

except KeyboardInterrupt:
    print("\nSimulator dimatikan secara aman.")
    device_client.loop_stop()
    device_client.disconnect()