#include <ESP32Servo.h>

const int PIN_SERVO_PAN  = 18;  
const int PIN_SERVO_TILT = 19;  

Servo servoPan;
Servo servoTilt;

// Nilai kalibrasi software yang sudah kamu dapatkan sebelumnya
const int PAN_OFFSET  = -30;  
const int TILT_OFFSET = -30;  

void kendaliServoPan(int sudutTarget) {
  int sudutTerkalibrasi = constrain(sudutTarget + PAN_OFFSET, 0, 180);
  servoPan.write(sudutTerkalibrasi);
}

void kendaliServoTilt(int sudutTarget) {
  int sudutTerkalibrasi = constrain(sudutTarget + TILT_OFFSET, 0, 180);
  servoTilt.write(sudutTerkalibrasi);
}

void setup() {
  // Nyalakan Serial dengan baudrate 115200 (Wajib disamakan dengan Raspi nanti)
  Serial.begin(115200);
  
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  servoPan.setPeriodHertz(50);
  servoTilt.setPeriodHertz(50);
  servoPan.attach(PIN_SERVO_PAN, 500, 2400);
  servoTilt.attach(PIN_SERVO_TILT, 500, 2400);

  // Set ke posisi tengah murni saat pertama kali menyala
  kendaliServoPan(90);
  kendaliServoTilt(90);
  Serial.println("ESP32_READY");
}

void loop() {
  // Cek apakah ada data teks masuk dari Raspberry Pi via kabel USB
  if (Serial.available() > 0) {
    String dataMasuk = Serial.readStringUntil('\n'); // Baca baris teks sampai selesai
    dataMasuk.trim(); // Bersihkan spasi atau karakter gaib
    
    // Logika pemecah teks perintah. Format perintah: "P:angka" atau "T:angka"
    // Contoh dari Raspi: "P:45" artinya Pan ke 45 derajat. "T:135" artinya Tilt ke 135 derajat.
    if (dataMasuk.startsWith("P:")) {
      int sudut = dataMasuk.substring(2).toInt();
      kendaliServoPan(sudut);
      Serial.println("ACK_PAN:" + String(sudut)); // Kirim balik konfirmasi ke Raspi
    } 
    else if (dataMasuk.startsWith("T:")) {
      int sudut = dataMasuk.substring(2).toInt();
      kendaliServoTilt(sudut);
      Serial.println("ACK_TILT:" + String(sudut));
    }
  }
}