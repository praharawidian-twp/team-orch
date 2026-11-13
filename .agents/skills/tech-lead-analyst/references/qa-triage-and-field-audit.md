# Panduan Lead QA Review, Field-Realism Audit & UAT Validation Triage

Dokumen referensi ini menetapkan standar bagi **Senior Lead Engineer / Analis** dalam menjalankan perannya sebagai **Lead QA Reviewer & Field-Realism Gatekeeper**.

---

## 1. Konsep & Filosofi Gatekeeping QA oleh Analis

Sama seperti halnya implementasi kode Coder yang harus melewati *code review* ketat dari Analis, laporan dan skenario pengujian dari **QA Engineer** juga **WAJIB** diaudit dan ditinjau secara kritis oleh Analis sebelum perangkat lunak diajukan ke tahap User Acceptance Testing (UAT).

Tujuan utama audit ini:
1. **Mencegah Uji Formalitas (Happy-Path Bias)**: Memastikan pengujian tidak hanya menguji skenario ideal yang mudah lulus, melainkan benar-benar menggali skenario kritis, error handling, dan kondisi batas riil.
2. **Audit Relevansi Lapangan (*Field-Realism Audit*)**: Memastikan parameter, format data, header, urutan state, dan skenario kegagalan mencerminkan kondisi operasional produksi dan integrasi eksternal nyata.
3. **UAT Validation Triage**: Memetakan secara tegas bagian mana yang sudah **100% diverifikasi otomatis oleh mesin/agen (`AUTO_VERIFIED`)** dan bagian mana yang **wajib divalidasi oleh mata/tindakan manusia (`HUMAN_VALIDATION_REQUIRED`)**, sehingga sesi UAT manusia menjadi terarah, efisien, dan berdampak tinggi.

---

## 2. Kriteria Triage Validasi: `[AUTO_VERIFIED]` vs `[HUMAN_VALIDATION_REQUIRED]`

Analis wajib mengklasifikasikan setiap area verifikasi ke dalam salah satu dari dua kategori berikut:

### A. Kategori `[AUTO_VERIFIED]` (Verifikasi Otomatis Tuntas oleh Agen)
Item pengujian dapat diberi label `[AUTO_VERIFIED]` jika memenuhi kriteria:
- **Deterministik Penuh**: Hasil pengujian dapat dinilai secara objektif lewat kode program atau assertion otomatis (True/False, Status Code == 200, dsb).
- **Tercakup dalam Otomasi Runtime**: Telah dieksekusi oleh Bruno runner, Postman/Newman, atau HTTP probing test dengan assertion yang lulus 100%.
- **Validasi Sintaks & Skema**: Validasi JSON schema, struktur respon standar, header HTTP, format tanggal ISO, dan tipe data.
- **Race Condition & Thread-Safety**: Terbukti bebas data race melalui race detector compiler (misal `go test -race ./...`).
- **Simulasi Dry-Run**: Pembuktian bahwa flag `dry_run=true` tidak menimbulkan mutasi di storage/database.

### B. Kategori `[HUMAN_VALIDATION_REQUIRED]` (Wajib Validasi Manusia saat UAT)
Item pengujian **WAJIB** diberi label `[HUMAN_VALIDATION_REQUIRED]` jika melibatkan:
- **Verifikasi UI/Portal Eksternal**: Memastikan perubahan API/service tercermin dengan benar di GUI portal eksternal (contoh: visualisasi endpoint di API Gateway Admin Portal, API catalog portal, dashboard monitoring).
- **Efek Samping ke Eksternal / Pihak Ketiga**: Interaksi dengan gateway pihak ketiga di lingkungan sandbox (contoh: notifikasi SMS/WA gateway fisik, email delivery, perbankan/payment gateway sandbox).
- **Keputusan Bisnis & Kebijakan Lintas Tim**: Validasi apakah teks pesan error, alur approval, atau format penamaan bisnis sudah disepakati oleh stakeholder pemilik proses bisnis.
- **Observasi Kinerja & Beban Subjektif**: Penilaian kenyamanan latensi respons pada jaringan riil enterprise.

---

## 3. Matriks Triage Validasi (Format Standar)

Dalam dokumen `qa-test-report.md`, Bagian 6 wajib menyajikan tabel pemisahan ini:

```markdown
## 6. Matriks Triage Validasi (Auto-Verified vs Human Validation Required)

### 6.1 Ringkasan Status Triage
| Total Skenario Uji | AUTO_VERIFIED (Mesin) | HUMAN_VALIDATION_REQUIRED (Manusia) |
| :---: | :---: | :---: |
| 7 | 5 (71%) | 2 (29%) |

### 6.2 Item yang Tuntas Diverifikasi Mesin (`[AUTO_VERIFIED]`)
| ID Skenario | Deskripsi Verifikasi | Metode / Bukti Otomasi | Status |
| :--- | :--- | :--- | :---: |
| `QA-01` | Validasi Happy Path HTTP 200 & Payload JSON Schema | Bruno CLI Assertion `res.status == 200` | PASSED |
| `QA-02` | Penolakan Bad Request 400 jika required field kosong | Bruno CLI Assertion `res.status == 400` | PASSED |
| `QA-04` | Proteksi Autentikasi 401 Unauthorized | Bruno CLI Assertion `res.status == 401` | PASSED |
| `QA-05` | Zero Memory Race pada eksekusi konkuren | `go test -count=1 -race ./...` (0 race warnings) | PASSED |
| `QA-06` | Preservasi State pada mode dry_run=true | Diff check: 0 mutasi database tercatat | PASSED |

### 6.3 Checklist Validasi Khusus Pengguna Manusia (`[HUMAN_VALIDATION_REQUIRED]`)
| ID Fokus | Area Validasi Krusial | Mengapa Butuh Validasi Manusia? | Langkah Pemeriksaan bagi Pengguna UAT |
| :--- | :--- | :--- | :--- |
| `UAT-01` | Verifikasi Tampilan di UI Portal Admin Gateway | Agen CLI hanya memanggil REST API backend; rendering visual service di portal UI admin membutuhkan observasi mata manusia. | Buka browser ke portal API Gateway Admin -> Masuk menu APIs -> Pastikan service baru berstatus 'Active' dan policy routing terpasang benar. |
| `UAT-02` | Notifikasi Alert Slack / Email Ops | Memastikan integrasi webhook pengiriman pesan notifikasi benar-benar masuk ke channel monitoring tim ops. | Cek channel `#api-monitoring-alerts` di workspace Slack, verifikasi format alert dan link korelasi transaksi. |
```

---

## 4. Panduan Pelaksanaan Field-Realism Audit

Ketika Analis mengaudit laporan QA, gunakan 4 pilar audit berikut:

### Pilar 1: Karakteristik Payload Riil Lapangan
- Apakah payload uji mencakup karakter khusus yang lazim di lapangan (spasi, tanda hubung, petik satu pada nama, karakter non-ASCII/unicode)?
- Apakah format ID yang diuji realistis (misal UUID v4, kode transaksi berformat enterprise seperti `TXN-20261112-00129`)?
- Apakah ada pengujian boundary ukuran payload (misal payload mendekati batas 1MB atau array dengan 100+ item)?

### Pilar 2: Keberagaman Contoh Gagal (Multi-Examples Fidelity)
- Apakah koleksi uji memiliki ragam respon gagal yang kaya?
- **Aturan Minimum**: Untuk setiap resource/endpoint utama, harus ada minimal:
  - 1 contoh sukses (`200 OK` atau `201 Created`).
  - 1 contoh validasi request tidak valid (`400 Bad Request` atau `422 Unprocessable Entity`).
  - 1 contoh resource tidak ditemukan atau konflik (`404 Not Found` atau `409 Conflict`).
  - 1 contoh kegagalan otentikasi/otorisasi (`401 Unauthorized` atau `403 Forbidden`).

### Pilar 3: Perilaku Kegagalan & Batas Jaringan (Network & Downstream Boundaries)
- Bagaimana perilaku aplikasi saat dependensi database/gateway downstream mengalami timeout?
- Apakah pesan error membocorkan string koneksi, nama server internal, atau stack trace?
- Apakah status kode HTTP sesuai standar RFC (contoh: bukan mengembalikan HTTP 200 dengan `{ "status": "error" }`)?

### Pilar 4: Idempotensi & Mitigasi Mutasi Ganda
- Apakah pengujian membuktikan bahwa pengiriman ulang (*duplicate request*) tidak menghasilkan duplikasi record?
- Apakah flag `only_new=true` benar-benar melindungi data lama dari modifikasi yang tidak diinginkan?

### Pilar 5: Audit Folder Bukti Pengujian Terisolasi (`docs/qa/evidence/TC-1...`)
- Apakah setiap test case memiliki folder bukti mandiri (`docs/qa/evidence/TC-1/`, `TC-2/`, dst.)?
- Apakah berkas bukti (`01-request-info.txt`, `02-response-output.json` / `.yaml`, `03-verification-summary.txt`, atau `README-EVIDENCE-GUIDE.txt`) lengkap dan dapat diverifikasi secara fisik?
- Apakah kolom `Status Automation` pada berkas Excel berstatus `Manual Verified (Pending Automation)` dan kolom `Evidence Folder` terisi tautan folder yang valid?

---

## 5. Penegakan Hard Stop Gate (Validasi Manusia Akhir Fase 1)

Setelah Analis memberikan sign-off `APPROVED` pada Laporan Fase 1:
1. **Mandatory Hard Stop**: Sistem **WAJIB BERHENTI (STOP)** dan menyerahkan hasil evaluasi kepada Pengguna Manusia di Control Room.
2. **Larangan Melompat Fase**: Agen dilarang keras langsung melanjutkan ke pembuatan Automation Test (Fase 2) atau Regression Test (Fase 3) tanpa instruksi eksplisit dari Manusia.
3. **Kesiapan Fase 2**: Jika Manusia meminta lanjut ke Automation Test, agen wajib menjalankan **Pre-Automation Discovery Gate** (bertanya framework dan basis rujukan terlebih dahulu).

---

## 6. Standar Format Sign-Off & Lead Directive Analis

Setelah audit selesai, Analis wajib mengisi Bagian 7 pada `qa-test-report.md`:

```markdown
## 7. Review & Sign-Off Analis (Field-Realism Audit & Lead Directive)

- **Lead QA Reviewer**: Analis / Senior Lead Engineer
- **Tanggal Review**: 2026-11-12
- **Status Review Analis**: `APPROVED` / `NEEDS_QA_REVISION`

### Evaluasi Relevansi Lapangan (Field-Realism Assessment)
- **Cakupan Skenario**: [Memadai / Perlu Dilengkapi]
- **Kualitas Multi-Examples**: [Sesuai Standar Enterprise / Minim Variasi]
- **Ketajaman Uji Batas**: [Tajam & Mendalam / Terlalu Dangkal]

### Arahan Teknis Lead (Lead Directive)
*(Jika status APPROVED)*:
> "Skenario pengujian telah memenuhi seluruh kriteria operasional riil lapangan. Matriks triage validasi telah memetakan dengan jelas batas otomatisasi agen versus observasi pengguna manusia. Disetujui untuk maju ke tahap UAT."

*(Jika status NEEDS_QA_REVISION)*:
> "Ditemukan kekurangan pada skenario pengujian lapangan:
> 1. Belum ada pengujian saat payload berukuran >500KB (boundary payload limit).
> 2. Contoh respon error 409 Conflict saat duplikasi UUID belum dimasukkan ke dalam collection.
> QA Engineer wajib melengkapi kedua skenario tersebut di bruno/qa-suite/, mengeksekusi ulang, dan mengajukan kembali laporan ini."
```
