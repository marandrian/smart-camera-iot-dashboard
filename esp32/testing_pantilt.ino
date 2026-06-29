#include <ESP32Servo.h>

// --- KONFIGURASI PIN GPIO ---
const int PIN_SERVO_PAN  = 18;  
const int PIN_SERVO_TILT = 19;  

// Inisialisasi Objek Servo
Servo servoPan;
Servo servoTilt;

// --- NILAI KALIBRASI SOFTWARE (OFFSET) ---
// Silakan ubah angka ini secara berkala sampai posisinya lurus sempurna.
// Nilai bisa POSITIF (+) atau NEGATIF (-) tergantung arah kemiringan servo fisikmu.
const int PAN_OFFSET  = -30;  // Contoh: Kurangi 5 derajat jika netralnya terlalu ke kanan
const int TILT_OFFSET = -30;   // Contoh: Tambah 3 derajat jika netralnya terlalu menunduk

// Fungsi Kustom untuk Menggerakkan Servo Sekaligus Menghitung Kalibrasi
void kendaliServoPan(int sudutTarget) {
  int sudutTerkalibrasi = constrain(sudutTarget + PAN_OFFSET, 0, 180);
  servoPan.write(sudutTerkalibrasi);
}

void kendaliServoTilt(int sudutTarget) {
  int sudutTerkalibrasi = constrain(sudutTarget + TILT_OFFSET, 0, 180);
  servoTilt.write(sudutTerkalibrasi);
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== SYSTEM: STARTING CALIBRATED SERVO SYSTEM ===");

  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);

  servoPan.setPeriodHertz(50);
  servoTilt.setPeriodHertz(50);

  servoPan.attach(PIN_SERVO_PAN, 500, 2400);
  servoTilt.attach(PIN_SERVO_TILT, 500, 2400);

  // KALIBRASI AWAL: Memanggil fungsi kustom pada sudut netral 90
  Serial.println("[INFO] Mengunci posisi netral terkalibrasi (90°)...");
  kendaliServoPan(90);
  kendaliServoTilt(90);
  
  delay(3000); 
  Serial.println("[INFO] Kalibrasi selesai. Memulai simulasi...");
}

void loop() {
  // FASE 1: UJI COBA SUMBU PAN (Menggunakan fungsi kendali terkalibrasi)
  Serial.println("\n[PAN] Menengok Kiri (Sudut Asli: 45°)...");
  kendaliServoPan(45);
  delay(2000);

  Serial.println("[PAN] Kembali ke Tengah Netral (Sudut Asli: 90°)...");
  kendaliServoPan(90);
  delay(2000);

  Serial.println("[PAN] Menengok Kanan (Sudut Asli: 135°)...");
  kendaliServoPan(135);
  delay(2000);

  Serial.println("[PAN] Mengunci Posisi Tengah Netral (Sudut Asli: 90°)...");
  kendaliServoPan(90);
  delay(2000);

  // FASE 2: UJI COBA SUMBU TILT (Menggunakan fungsi kendali terkalibrasi)
  Serial.println("\n[TILT] Menengadah Atas (Sudut Asli: 135°)...");
  kendaliServoTilt(135);
  delay(2000);

  Serial.println("[TILT] Kembali ke Tengah Netral (Sudut Asli: 90°)...");
  kendaliServoTilt(90);
  delay(2000);

  Serial.println("[TILT] Menunduk Bawah (Sudut Asli: 45°)...");
  kendaliServoTilt(45);
  delay(2000);

  Serial.println("[TILT] Mengunci Posisi Tengah Netral (Sudut Asli: 90°)...");
  kendaliServoTilt(90);
  
  Serial.println("\n=== Sesi Uji Coba Berhasil. Istirahat 4 Detik ===");
  delay(4000); 
}