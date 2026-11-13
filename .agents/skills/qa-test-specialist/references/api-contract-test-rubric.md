# Rubrik Penilaian Kontrak API & Pengujian Runtime Skala Enterprise

Dokumen ini merupakan panduan teknis mendalam (*reference guide*) bagi QA Engineer dalam mengevaluasi kepatuhan kontrak API, penanganan skenario batas (*edge cases*), idempotensi, dan stabilitas runtime.

---

## 1. Matriks Standar HTTP Status Code

Setiap endpoint HTTP yang diuji WAJIB mengembalikan status code yang semantik dan presisi sesuai standar RFC 9110:

| HTTP Status | Kategori | Kriteria Penggunaan Baku | Contoh Skenario Uji |
|---|---|---|---|
| **200 OK** | Sukses | Request berhasil diproses dan mengembalikan data (GET, PUT, PATCH, atau POST sinkron). | Mengambil detail resource, sinkronisasi endpoint dengan mode `dry_run=true`. |
| **201 Created** | Sukses Mutasi | Resource baru berhasil dibuat di sistem atau database. Respons wajib menyertakan ID atau referensi resource baru. | `POST /api/v1/apis/create` atau membuat record baru. |
| **204 No Content** | Sukses Kosong | Aksi berhasil dieksekusi tanpa body respons (biasanya operasi DELETE atau update tanpa payload kembalian). | `DELETE /api/v1/resources/{id}`. |
| **400 Bad Request** | Error Klien (Sintaks) | Format request rusak, sintaks JSON malformed, header wajib tidak ada, atau multipart boundary tidak valid. | Mengirimkan JSON tidak lengkap (`{"name": `), format multipart boundary hilang. |
| **401 Unauthorized** | Error Otentikasi | Request membutuhkan otentikasi tetapi kredensial tidak disertakan, tidak lengkap, atau tidak valid. | Mengakses endpoint privat tanpa header `Authorization` atau tanpa Basic Auth yang valid. |
| **403 Forbidden** | Error Otorisasi | Kredensial valid tetapi pemanggil tidak memiliki izin akses (*permission*) pada resource terkait. | User biasa mencoba mengakses endpoint konfigurasi internal admin. |
| **404 Not Found** | Error Klien (Resource) | Target URI, endpoint path, atau resource ID tidak ditemukan di dalam sistem. | Mencari API yang belum pernah terdaftar di gateway/database. |
| **422 Unprocessable Entity** | Error Klien (Semantik) | Sintaks JSON valid, namun melanggar aturan bisnis (*business validation failure*), misalnya pola nama tidak sesuai regex, atau field wajib bernilai kosong. | Mengirim nama API dengan spasi (`"MY API"`) saat standar mewajibkan format `kebab-case`. |
| **500 Internal Server Error** | Error Server (Dilarang) | **PELANGGARAN KONTRAK**: Terjadi unhandled exception, panic, atau crash internal. Input klien tidak boleh menghasilkan 500. | Server panic akibat null pointer dereference saat menerima field opsional bernilai null. |
| **502 Bad Gateway** | Error Upstream | Layanan upstream (backend eksternal / third-party service) tidak merespons atau mengembalikan error. | Gateway pihak ketiga mati saat proses proxy sinkronisasi. |

---

## 2. Rubrik Evaluasi JSON Schema & Data Fidelity

1. **Struktur Respons Baku**:
   Setiap respons JSON wajib memiliki pembungkus terstandarisasi:
   ```json
   {
     "status": 200,
     "message": "Deskripsi hasil yang jelas dan ramah pengguna",
     "data": { ... }
   }
   ```
2. **Format Respons Error**:
   Respons error wajib terstruktur dan informatif tanpa mengekspos rincian internal server:
   ```json
   {
     "status": 422,
     "error": "Validation failed",
     "details": [
       {
         "field": "api_name",
         "message": "api_name wajib berformat kebab-case tanpa spasi"
       }
     ]
   }
   ```
3. **Pemeriksaan Tipe Data Ketat (Type Safety)**:
   - Nilai integer tidak boleh dikembalikan sebagai string (misal `"total_paths": 5` bukan `"total_paths": "5"`).
   - Nilai boolean harus bernilai literal `true` / `false` (bukan `"true"` atau `1`).
   - Field array kosong wajib diserialisasi sebagai array kosong `[]`, bukan `null`.

---

## 3. Rubrik Pengujian Skenario Batas (Boundary & Edge Cases)

QA Engineer wajib memvalidasi skenario batas berikut:

1. **String Kosong & Whitespace**:
   - String hanya berisi spasi (`"   "`): Wajib ditolak atau di-trim dengan benar.
   - String kosong (`""`) pada parameter wajib: Wajib menghasilkan `400 Bad Request` atau `422 Unprocessable Entity`.
2. **Karakter Spesial & Injeksi Input**:
   - Menguji string yang mengandung karakter kutip tunggal/ganda, backslash, tag HTML (`<script>`), dan karakter kontrol terminal (`\x1b`, `\r`).
   - Sistem wajib melakukan sanitasi atau escape yang aman tanpa mengeksekusi karakter kontrol tersebut.
3. **Ukuran Payload Ekstrem (Oversized Payload)**:
   - File upload melampaui batas maksimum (misal file > 10MB): Sistem wajib menolak dengan `413 Payload Too Large` atau error multipart yang bersih, bukan crash memori OOM (*Out of Memory*).
4. **Parameter Ekstra yang Tidak Dikenal (*Unknown Fields*)**:
   - Mengirim field JSON atau form value tambahan yang tidak ada di spesifikasi: Sistem harus mengabaikan secara aman atau menolak sesuai kebijakan strict parsing, tanpa mengalami error internal.

---

## 4. Rubrik Idempotensi & State Preservation

Pengujian mutasi berulang sangat penting untuk mencegah kerusakan data pada sistem terdistribusi:

1. **Idempotensi Pemanggilan Berulang**:
   - Panggilan berulang pada endpoint dengan parameter yang sama persis tidak boleh menghasilkan duplikasi data atau state yang tidak konsisten.
2. **Pencegahan Overwrite pada Operasi Granular (`only_new=true`)**:
   - Jika flag `only_new=true` aktif:
     - Endpoint atau operasi yang sudah ada di sistem tujuan **TIDAK BOLEH BERUBAH** (summary, parameter, header, schema respons wajib tetap identik dengan kondisi awal).
     - Hanya endpoint atau operasi baru yang ditambahkan.
     - Ringkasan diff wajib secara akurat menempatkan endpoint lama ke `unchanged_operations` dan endpoint baru ke `added_operations`.
3. **Imunitas Efek Samping pada Mode Dry-Run (`dry_run=true`)**:
   - Saat `dry_run=true`, seluruh proses transformasi, validasi, dan komputasi diff dieksekusi normal.
   - **TIDAK ADA SATU PUN PERUBAHAN** yang disimpan ke database, gateway, atau sistem penyimpanan persisten.
   - Panggilan status berikutnya wajib membuktikan state sistem persis sama seperti sebelum dry-run dijalankan.

---

## 5. Rubrik Keamanan, Sanitasi & Konkurensi

1. **Sanitasi Kredensial & Secrets**:
   - Respons body dan file log tidak boleh memuat password, secret token, private key, atau Authorization header secara plain text.
2. **Proteksi Stack Trace**:
   - Dalam kondisi error terburuk sekalipun, pesan respons klien dilarang menampilkan baris stack trace bahasa pemrograman (misal `goroutine 1 [running]:`, `at com.example...`, atau `Traceback (most recent call last):`).
3. **Verifikasi Thread-Safety & Bebas Race Condition**:
   - Menjalankan unit & integration test menggunakan runtime race detector:
     ```bash
     go test -count=1 -race ./...
     ```
   - **Kriteria Lolos Mutlak**: 0 warnings, 0 data races terdeteksi (`WARNING: DATA RACE`).
   - Pada pengujian beban konkurensi (misal 50 request serentak ke endpoint yang sama), tidak boleh terjadi crash, deadlock, atau mutasi variabel bersama tanpa penguncian (*mutex lock*).

---

## 6. Format Keputusan Akhir (Gatekeeper Verdict)

| Status | Syarat Kelayakan | Tindakan QA Engineer |
|---|---|---|
| **PASSED** | 100% skenario pada seluruh 4 dimensi pengujian berhasil lulus tanpa cacat kontrak, tanpa data race, dan tanpa kebocoran keamanan. | Menyetujui hasil, menerbitkan laporan, dan meneruskan ke Control Room untuk UAT sign-off. |
| **REJECTED** | Ditemukan 1 atau lebih cacat kritis (status code salah, mutasi liar pada data eksisting, data race terdeteksi, atau server crash/500). | Menolak hasil, menyusun laporan reproduksi bug mendalam, dan mengembalikan tugas ke Coder untuk diperbaiki. |
