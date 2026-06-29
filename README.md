# Smart Camera Tracking System Berbasis Multi-Sensor Fusion IoT

proyek sistem tracking kamera yang menggabungkan parameter spasial audio (Dual Microphone Array) dan visual (Computer Vision) menggunakan metode multi-sensor fusion di tingkat lokal / edge computing. sistem ini terintegrasi dengan Cloud VPS melalui protokol MQTT untuk kontrol manual dan sinkronisasi data riwayat ke database Supabase.

---

## Pemodelan Matematika Sistem

sistem ini mengadopsi perhitungan fisis dan fungsional terstruktur sebagai berikut:

### 1. Ekstraksi Gain Audio (RMS level)
intensitas sinyal suara dihitung secara diskrit menggunakan formula RMS untuk menyaring threshold keheningan:
* RMS = akar dari (1/N * jumlah dari x[i]^2)

### 2. Koreksi Error Offset Kamera
koreksi arah kamera dihitung berdasarkan selisih posisi titik tengah koordinat horizontal wajah terhadap titik tengah lensa kamera (resolusi horizontal W = 320px):
* Error Offset (ex) = (x + w/2) - 160

### 3. Fungsi Deadzone Kendali Aktuator
Untuk mencegah fenomena servo bergetar akibat noise, dipasang deadzone sebesar 15px:
* jika |ex| > 15 dan State = AUTO -> jalankan koreksi sudut servo diskrit.
* jika |ex| <= 15 -> servo mempertahankan posisi (lock target).

---

## Struktur Repo

ekosistem proyek dibagi jadi tiga bagian kerja utama:

smart-camera-iot-system/
├── cloud-vps/                 # Backend & Frontend yang berjalan di Cloud Server
│   ├── app.py                 # Web Server Flask, Session Auth, dan MQTT Subscriber
│   └── templates/
│       └── dashboard.html     # Web Dashboard antarmuka berbasis Swiss Design
│
├── raspberry-pi/              # Node Edge Processing Lokal
│   └── main_tracking.py       # Algoritma Utama Audio RMS & OpenCV Face Tracking
│
└── esp32-executor/            # Node Aktuasi Hardware
    └── esp32-executor.ino     # Firmware Driver Servo Pan-Tilt Base Kit

---

## Infrastruktur Jaringan & Protokol Komunikasi

### Topologi Topik MQTT (HiveMQ Cloud Broker)
komunikasi data asinkronus dua arah dikelola melalui dua pipa utama:
* smartcamera/tracking_logs (QoS 1): jalur uplink bagi Raspberry Pi untuk memublikasikan data koordinat, level RMS mic, dan nama pembicara aktif menuju database cloud.
* kampus/smartcamera/cmd (QoS 0): jalur downlink bagi Cloud VPS untuk mengirimkan paket perintah kendali interupsi manual dari dashboard menuju pergerakan servo lokal.

### Arsitektur REST API Endpoints (HTTP/REST)
* GET /login & POST /login : mengurus fungsi auth akun pengguna.
* GET / : merender halaman utama dashboard.
* POST /control : menerima perintah ketukan manual dari dashboard untuk diteruskan ke MQTT.
* POST /api/upload_frame : pipa pengunggahan byte gambar JPEG mentah dari kamera lokal secara paralel.
* GET /api/video_feed : menyemburkan aliran gambar (video streaming) menggunakan MIME tipe multipart/x-mixed-replace.
* GET /api/logs : AJAX Polling berkala (setiap 2 detik) untuk menarik riwayat log terbaru dari database remote Supabase.

---

## Komponen Perangkat Keras yang Digunakan
* Edge Gateway Utama: Raspberry Pi 3 Model B+ (Debian GNU/Linux 12).
* Dedicated I/O Controller: ESP32.
* Sensor: 2 x USB Microphone Array & Modul Pi Camera OV5647.
* Aktuator: 2 x Motor Servo SG90.
* Komunikasi Lokal: USB Serial Bus (pyserial) @ 115200 bps.
