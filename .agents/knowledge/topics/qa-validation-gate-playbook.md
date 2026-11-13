# 🛡️ QA Validation Gate & Contract Testing Playbook

> **Topik ID**: `qa-validation-gate-playbook`  
> **Akses**: `*` (Semua Peran: `qa-engineer`, `analyst`, `coder`, `project-manager`)  
> **Tingkat Kepatuhan**: `STRICT`

---

## 1. Filosofi & Peran Strategis QA Validation Gate
Dalam siklus rekayasa perangkat lunak otonom, kode yang lolos pengujian unit (*unit testing green*) belum tentu aman atau berfungsi dengan benar saat dipanggil dari luar. Unit test sering kali menggunakan mock yang mengasumsikan kondisi ideal dan tidak mencerminkan perilaku runtime terdistribusi.

**QA Validation Gate** hadir sebagai gerbang inspeksi independen sebelum sistem dinyatakan layak masuk ke tahap akhir (*UAT Sign-off*):
- **Coder** menguji komponen secara internal (*white-box*).
- **Analis** mereview arsitektur, clean code, dan boilerplate compliance.
- **QA Engineer** memverifikasi integritas sistem dari luar (*black-box & grey-box runtime validation*), menguji batas ekstrem, membuktikan kontrak API tidak bocor, serta memastikan pemanggilan berulang tidak merusak data (*state preservation*).

---

## 2. Metodologi 4-Dimensional Test Matrix
Setiap verifikasi QA wajib menguji 4 dimensi pengujian tanpa kompromi:

### Dimensi 1: Skenario Positif (Happy Path & Functional Acceptance)
- Memvalidasi seluruh skenario bisnis utama yang tercantum pada `01-requirements.md`.
- Memastikan HTTP status code sukses: `200 OK`, `201 Created`, atau `204 No Content`.
- Memastikan payload respons memiliki tipe data, struktur objek, dan nilai kembalian yang presisi.

### Dimensi 2: Skenario Batas & Negatif (Boundary & Error Handling)
- Menguji nilai batas: string kosong, string hanya spasi, angka negatif, melampaui batas maksimum (*oversized payload*), field wajib dihilangkan, format UUID/email tidak valid.
- Memastikan sistem menolak dengan HTTP status code semantik yang bersih: `400 Bad Request`, `404 Not Found`, atau `422 Unprocessable Entity`.
- **Aturan Keamanan Error**: Respons dilarang keras membocorkan stack trace bahasa pemrograman, query SQL mentah, atau path sistem operasi host.

### Dimensi 3: Idempotensi & State Preservation (Pencegahan Mutasi Liar)
- Menguji pemanggilan berulang (*repeat execution*) dengan parameter yang sama: sistem tidak boleh menghasilkan duplikasi data, korupsi state, atau inkonsistensi.
- Memverifikasi fitur granular sync seperti `only_new=true`:
  - Operasi atau data yang sudah ada di sistem tujuan **WAJIB TETAP UTUH (UNTOUCHED)**.
  - Hanya operasi/data baru yang ditambahkan ke sistem tujuan.
- Memverifikasi mode `dry_run=true`: seluruh proses komputasi dan diff berjalan normal, namun **ZERO STATE MUTATION** pada database atau gateway penyimpanan.

### Dimensi 4: Keamanan, Autentikasi & Konkurensi / Race Condition
- Memverifikasi proteksi endpoint: akses tanpa otentikasi atau dengan token/kredensial palsu wajib diblokir dengan `401 Unauthorized`.
- Memverifikasi sanitasi kredensial: tidak ada password atau secret key yang bocor di log atau respons.
- **Deteksi Race Condition**: Menjalankan race detector runtime (`go test -count=1 -race ./...`). Sistem wajib lulus 100% dengan **0 data race warnings**.

---

## 3. Protokol Isolasi Koleksi Dev vs QA
1. **Koleksi Dev (`bruno/<service>/` atau `.http`)**:
   - Dikelola oleh pengembang untuk kebutuhan manual debugging dan smoke testing lokal harian.
2. **Koleksi QA Suite (`bruno/qa-suite/` atau `tests/qa/`)**:
   - Dikelola eksklusif oleh QA Engineer.
   - Wajib memuat *automated assertions*, skenario negatif, validasi batas status code, dan skrip verifikasi otomatis.
   - Koleksi QA tidak boleh diubah atau ditimpa oleh Coder.

---

## 4. Protokol Penargetan Entitas Sandbox (Sandbox Entity Targeting)
- Seluruh pengujian yang melibatkan operasi mutasi (Create, Update, Delete) WAJIB menargetkan entitas sandbox/dummy:
  - Menggunakan dummy ID khusus: `test-dummy-999`, `qa-sandbox-id`, dsb.
  - Menggunakan penamaan sementara berawalan `qa-temp-`.
  - Mengaktifkan mode simulasi `dry_run=true` jika tersedia.
- Dilarang keras menargetkan entitas nyata, ID konfigurasi default, atau data produksi.

---

## 5. Alur Penolakan Cacat (Bug Rejection Loop)
Jika salah satu dari 4 dimensi pengujian gagal:
1. QA Engineer menerbitkan laporan di `tasks/<project_id>/qa-test-report.md` dengan status **`VERDICT: REJECTED`**.
2. Cantumkan bukti reproduksi presisi:
   - Perintah cURL atau skrip runner lengkap.
   - Payload request yang dikirimkan.
   - Respons aktual (*Actual Output*) vs Respons yang diharapkan (*Expected Contract*).
   - Tingkat keparahan (*Severity: CRITICAL / MAJOR / MINOR*).
3. Handoff kembali ke Coder untuk perbaikan dan verifikasi ulang.

---

## 6. Verifikasi Otomatis Laporan QA
Laporan QA wajib diverifikasi menggunakan skrip deterministik framework sebelum dianggap sah:
```bash
python3 .agents/skills/qa-test-specialist/scripts/verify-qa-report.py tasks/<project_id>/qa-test-report.md
```
Skrip akan memastikan kelengkapan bab, cakupan 4 dimensi pengujian, bukti log eksekusi, dan kejelasan status akhir (*VERDICT*).

---

## 7. Tata Kelola 3 Fase Bertahap di Bawah Kendali Manusia

Siklus QA tunduk mutlak pada kendali manusia di Control Room dan dipecah menjadi 3 fase independen:

### 1. Fase 1 (Default saat QA Dipanggil): Manual Test -> Dokumentasi -> Validasi Manusia (HARD STOP)
- Eksekusi test case secara bertahap dan terukur (`TC-1`, `TC-2`, ..., `TC-N`).
- Setiap test case menyimpan bukti fisik terisolasi di `docs/qa/evidence/TC-1/`, `TC-2/`, dst.
- Susun dokumentasi spreadsheet `Test-Cases-and-Defects-<project>.xlsx` (Status Automation: `Manual Verified (Pending Automation)`), laporan Word `.docx`, dan `.md`.
- Lakukan review Analis (Field-Realism & kelengkapan bukti).
- **HARD STOP GATE**: Agen WAJIB BERHENTI dan menyerahkan hasil ke Manusia di Control Room. DILARANG membuat automation atau regression tanpa instruksi eksplisit manusia.

### 2. Fase 2 (On-Demand): Pre-Automation Discovery -> Automation Test -> Dokumentasi
- **Pre-Automation Discovery Gate (Wajib Tanya)**: Agen WAJIB bertanya kepada manusia:
  1. *"Ingin menggunakan framework/tools automation apa?"*
  2. *"Automation ini dibuat berdasarkan (base on) apa?"*
- Setelah dijawab, agen membangun dan menjalankan script otomasi, menyimpan bukti di `docs/qa/evidence/automation/`, dan memperbarui status otomasi di dokumen menjadi `Done`.

### 3. Fase 3 (On-Demand): Smart Regression Check
- **Jika Belum Ada Automation**: Agen WAJIB mengeluarkan WARNING eksplisit bahwa regresi akan menggunakan dokumen lama (`.xlsx` dan `docs/qa/evidence/TC-*`) sebagai acuan.
- **Jika Sudah Ada Automation**: Agen menjalankan Auto Regresi secara mandiri menggunakan suite otomasi yang tersedia dan menyimpan bukti di `docs/qa/evidence/regression/`.

---

## 8. Standar Direktori Bukti Pengujian Terisolasi (`docs/qa/evidence/TC-1...`)

```text
docs/qa/evidence/
├── TC-1/
│   ├── 01-request-info.txt
│   ├── 02-response-output.json (atau .yaml)
│   └── 03-verification-summary.txt
├── TC-2/
│   ├── ...
├── TC-N/
│   └── README-EVIDENCE-GUIDE.txt (khusus HUMAN_VALIDATION_REQUIRED)
├── automation/ (hanya dibuat pada Fase 2 jika disetujui Manusia)
└── regression/ (hanya dibuat pada Fase 3 jika dijalankan regresi)
```
- Setiap baris test case pada dokumen Excel wajib memuat kolom referensi `Evidence Folder` yang merujuk langsung ke folder bukti masing-masing.

---

## 9. UI Evidence Capture (Read-Only, Human-Consented)

Untuk skenario pengujian dengan antarmuka pengguna web/portal:
1. **Prinsip Read-Only**: Pengambilan bukti screenshot UI murni bersifat read-only tanpa mutasi data via antarmuka.
2. **Provisioning Consent Gate**: Tidak boleh ada penginstalan Playwright/Chromium secara diam-diam. Jika belum terpasang, tanyakan 5 opsi baku ke pengguna manusia di Control Room.
3. **Autentikasi Sesi Manusia (Opsi B - Default)**: Manusia login langsung di browser headed (`ui-capture login`). File sesi tersimpan di `.agents/secrets/<project>/ui-auth-state.json` dengan permission `600`.
4. **Keamanan & Guarding**:
   - Pembatasan domain via `allowed_origins`.
   - Pemblokiran request mutasi HTTP (`POST/PUT/PATCH/DELETE`).
   - Deteksi tantangan keamanan/CAPTCHA/Turnstile langsung memicu stop (exit code 21).
   - Sensor/masking wajib pada input password dan elemen bertanda `[data-sensitive]`.
   - Setiap tangkapan layar dicatat dalam `docs/qa/evidence/TC-*/capture-log.json`.
