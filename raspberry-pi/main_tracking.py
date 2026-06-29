import sounddevice as sd
import numpy as np
import serial
import time
import sys
import json
import paho.mqtt.client as mqtt

print("====================================================")
print("=== SMART CAMERA SYSTEM: DUAL-MODE BI-DIRECTIONAL ===")
print("====================================================\n")

# --- 1. PARAMETER SUDUT & AUDIO ---
SUDUT_ORANG_A = 45   
SUDUT_ORANG_B = 135  
SUDUT_NETRAL  = 90   
SUDUT_TILT_DEFAULT = 90 

THRESHOLD_A = 0.08  
THRESHOLD_B = 0.08  
RATIO_SENSITIVITY = 1.8  
SILENCE_TIMEOUT = 3.0  

SAMPLING_RATE = 44100  
DURATION = 0.1         
waktu_terakhir_bicara = time.time()

# --- STATUS MODE UTAMA (STATE MACHINE) ---
current_mode = "AUTO" # Default awal sistem adalah otomatis tracking mic

# --- 2. KONFIGURASI HIVEMQ CLOUD ---
MQTT_BROKER = "0ed1ff3fca884fe292de73340d7ca5d1.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "marcel"
MQTT_PASS = "RekayasaInternet123"
MQTT_TOPIC_LOGS = "smartcamera/tracking_logs"
MQTT_TOPIC_CMD = "kampus/smartcamera/cmd" # Topik dengar dari dashboard web

# --- FUNGSI TELEMETRI & HARDWARE KONTROL ---
def hitung_rms(audio_data):
    if len(audio_data) == 0:
        return 0
    return float(np.sqrt(np.mean(audio_data**2)))

def kirim_perintah_servo(sudut):
    perintah = f"P:{sudut}\n"
    ser.write(perintah.encode('utf-8'))
    time.sleep(0.02)
    if ser.in_waiting > 0:
        return ser.readline().decode('utf-8').strip()
    return "NO_ACK"

def kirim_telemetri_cloud(speaker, pan, tilt, rms_l, rms_r):
    payload = {
        "active_speaker": speaker,
        "pan_angle": int(pan),
        "tilt_angle": int(tilt),
        "rms_left": float(rms_l),
        "rms_right": float(rms_r)
    }
    json_data = json.dumps(payload)
    client.publish(MQTT_TOPIC_LOGS, json_data, qos=1)

# --- 3. CALLBACK UNTUK MENDENGARKAN PERINTAH MANUAL DARI WEB ---
def on_connect(client, userdata, flags, rc):
    print(f"[CLOUD] Terhubung ke Broker. Status: {rc}")
    # Raspi mendaftarkan diri untuk mendengar perintah tombol dari VPS
    client.subscribe(MQTT_TOPIC_CMD)
    print(f"[CLOUD SUBSCRIBED] Mendengarkan perintah manual pada: {MQTT_TOPIC_CMD}\n")

def on_message(client, userdata, msg):
    global current_mode, posisi_sekarang, waktu_terakhir_bicara
    if msg.topic == MQTT_TOPIC_CMD:
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            mode_request = payload.get("mode")
            
            if mode_request == "MANUAL":
                current_mode = "MANUAL"
                pan = payload.get("pan", 90)
                print(f"[OVERRIDE MANUAL] Mengunci tracking mic! Kamera dialihkan ke sudut: {pan}°")
                kirim_perintah_servo(pan)
                posisi_sekarang = pan
                # Setor status "Manual" ke Supabase agar tombol di dashboard terbuka
                kirim_telemetri_cloud("Manual", pan, SUDUT_TILT_DEFAULT, 0.0, 0.0)
                
            elif mode_request == "AUTO":
                current_mode = "AUTO"
                waktu_terakhir_bicara = time.time()
                print("[OVERRIDE AUTO] Kamera dikembalikan ke kendali mikrofon otomatis.")
                kirim_telemetri_cloud("Hening", posisi_sekarang, SUDUT_TILT_DEFAULT, 0.0, 0.0)
                
        except Exception as e:
            print(f"[ERROR COMMAND] Gagal mengeksekusi instruksi dashboard: {e}")

# --- 4. RUNNING CLIENT MQTT ON RASPI ---
print("[CLOUD] Menginisialisasi jembatan data MQTT...")
client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.tls_set() 
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
except Exception as e:
    print(f"[ERROR CLOUD] Gagal handshake: {e}")
    sys.exit()

# --- 5. KONEKSI SERIAL LOCAL ---
print("[PORT] Menghubungkan ke ESP32...")
try:
    ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
    time.sleep(2) 
    print("[PORT] Sukses terhubung via USB Serial.\n")
except Exception as e:
    print(f"[ERROR PORT] Jalur serial lokal gagal: {e}")
    sys.exit()

# --- 6. AUDIO SCANNING ---
semua_device = sd.query_devices()
usb_mics = []
for indeks, dev in enumerate(semua_device):
    if dev['max_input_channels'] > 0 and ('USB' in dev['name'] or 'Device' in dev['name']):
        usb_mics.append((indeks, dev['name']))

if len(usb_mics) < 2:
    print("\n[ERROR] Gagal menemukan 2 perangkat USB Mic.")
    sys.exit()

MIC_ORANG_A = usb_mics[0][0]
MIC_ORANG_B = usb_mics[1][0]

# Posisi awal
posisi_sekarang = SUDUT_NETRAL
kirim_perintah_servo(SUDUT_NETRAL)

try:
    while True:
        # Jika mode sedang MANUAL, matikan fungsi pembacaan mic agar servo tidak bentrok
        if current_mode == "MANUAL":
            time.sleep(0.2) # Jeda hemat CPU, murni menunggu instruksi MQTT selanjutnya
            continue
            
        # ─── LOGIKA OTOMATIS (HANYA JALAN SAAT MODE AUTO) ───
        audio_a = sd.rec(int(DURATION * SAMPLING_RATE), samplerate=SAMPLING_RATE, channels=1, device=MIC_ORANG_A, dtype='float32')
        audio_b = sd.rec(int(DURATION * SAMPLING_RATE), samplerate=SAMPLING_RATE, channels=1, device=MIC_ORANG_B, dtype='float32')
        sd.wait()
        
        rms_a = hitung_rms(audio_a)
        rms_b = hitung_rms(audio_b)
        
        ada_yang_bicara = False
        
        if rms_a > THRESHOLD_A and rms_a > (rms_b * RATIO_SENSITIVITY):
            ada_yang_bicara = True
            waktu_terakhir_bicara = time.time()
            if posisi_sekarang != SUDUT_ORANG_A:
                print(f"[TRACKING] Orang A Aktif.")
                kirim_perintah_servo(SUDUT_ORANG_A)
                posisi_sekarang = SUDUT_ORANG_A
                kirim_telemetri_cloud("Orang A", SUDUT_ORANG_A, SUDUT_TILT_DEFAULT, rms_a, rms_b)
                
        elif rms_b > THRESHOLD_B and rms_b > (rms_a * RATIO_SENSITIVITY):
            ada_yang_bicara = True
            waktu_terakhir_bicara = time.time()
            if posisi_sekarang != SUDUT_ORANG_B:
                print(f"[TRACKING] Orang B Aktif.")
                kirim_perintah_servo(SUDUT_ORANG_B)
                posisi_sekarang = SUDUT_ORANG_B
                kirim_telemetri_cloud("Orang B", SUDUT_ORANG_B, SUDUT_TILT_DEFAULT, rms_a, rms_b)
                
        if not ada_yang_bicara:
            durasi_hening = time.time() - waktu_terakhir_bicara
            if durasi_hening >= SILENCE_TIMEOUT and posisi_sekarang != SUDUT_NETRAL:
                print(f"[SILENCE] Hening -> Kembali ke Tengah.")
                kirim_perintah_servo(SUDUT_NETRAL)
                posisi_sekarang = SUDUT_NETRAL
                kirim_telemetri_cloud("Hening", SUDUT_NETRAL, SUDUT_TILT_DEFAULT, rms_a, rms_b)
                
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n[INFO] Menutup sistem...")
    kirim_perintah_servo(SUDUT_NETRAL)
    client.loop_stop()
    client.disconnect()
    ser.close()
