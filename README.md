# Smart Presentation Tracking Camera Berbasis IoT dan Edge Computing

Proyek sistem tracking kamera yang menggabungkan parameter spasial audio-visual menggunakan metode Multi-Sensor Fusion di tingkat lokal / edge computing. Sistem ini terintegrasi dengan Cloud VPS melalui protokol MQTT untuk kontrol manual dan sinkronisasi data riwayat ke database Supabase.

Proyek dikembangkan oleh:
* Athaillah Daffa Andara (140910240015)
* Rifa Yulia Putri (140910240028)
* Marcel Andrian Naftali (140910240043)
* Atha Zaky Anargya (140910240044)

---

## Pemodelan Matematika Sistem

Sistem ini mengadopsi perhitungan fisis dan fungsional terstruktur sebagai berikut:

### 1. Ekstraksi Gain Audio (RMS level)
Intensitas sinyal suara dihitung secara diskrit menggunakan formula RMS untuk menyaring threshold keheningan:
* RMS = akar dari (1/N * jumlah dari x[i]^2)

### 2. Koreksi Error Offset Kamera
Koreksi arah kamera dihitung berdasarkan selisih posisi titik tengah koordinat horizontal wajah terhadap titik tengah lensa kamera (resolusi horizontal W = 320px):
* Error Offset (ex) = (x + w/2) - 160

### 3. Fungsi Deadzone Kendali Aktuator
Untuk mencegah fenomena servo bergetar akibat noise, dipasang deadzone sebesar 15px:
* jika |ex| > 15 dan State = AUTO -> jalankan koreksi sudut servo diskrit.
* jika |ex| <= 15 -> servo mempertahankan posisi (lock target).

---

## Struktur Repo
Ekosistem proyek dibagi jadi tiga bagian kerja utama:

```text
smart-camera-iot-dashboard/
├── esp32/
│   └── pantilt_control.ino      # Firmware Driver Servo Pan-Tilt C++ (Arduino)
│   └── testing_pantilt.ino      # Script percobaan Servo untuk pertama kalinya
├── raspberry-pi/
│   └── main_tracking.py        # Algoritma Fusion Lokal (Audio RMS + OpenCV Face Tracking)
├── templates/
│   └── dashboard.html          # Halaman Dashboard
│   └── dashboard2.html         # Backup outdated dari dashboard.html
│   └── login.html              # Halaman Login
│   └── register.html           # Halaman Register
├── venv/                       # Python Virtual Environment
├── .gitignore                  # Berkas instruksi pengabaian file sensitif (.env)
├── README.md                   # Dokumentasi utama arsitektur IoT & metode sistem
├── app.py                      # Web Server API Flask & MQTT Subscriber (Cloud VPS)
├── dashboard.html              # Backup outdated dari templates/dashboard.html
├── mock_device.py              # Script simulator pengujian pengiriman data telemetri
└── requirements.txt            # Daftar dependensi library Python backend Flask
```

---

## Infrastruktur Jaringan & Protokol Komunikasi

### Topic MQTT (HiveMQ Cloud Broker)
Komunikasi data asinkronus dua arah dikelola melalui dua pipa utama:
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
