# Quality Assurance Document (QAD) & QA Validation Gate Report: [PROJECT_ID]

> **[ORGANIZATION_NAME]**  
> **[DIVISION_NAME]**  
> Dokumen: **[TESTPLAN] [PROJECT_TITLE]**  
> Nomor: **`DOC-[PROJECT_ID]-[YEAR]`** | Versi: **`1.0 - [DATE]`**  
> Gatekeeper: **QA & Test Automation Specialist (`qa-engineer`)**  
> Lead Reviewer: **Analis / Senior Lead Engineer (`analyst`)**  
> Status Kelayakan Teknis: **`VERDICT: [PASSED | REJECTED]`**  
> Status Sign-Off Analis: **`ANALYST STATUS: [APPROVED | NEEDS_QA_REVISION]`**  
> *Dokumen internal pengujian perangkat lunak; distribusi mengikuti kebijakan tata kelola informasi organisasi aktif.*

---

## DAFTAR ISI
1. [1. Metadata & Lingkup Pengujian (QAD Metadata)](#1-metadata--lingkup-pengujian)
2. [2. 4-Dimensional Test Matrix Summary (SCENARIO TEST)](#2-4-dimensional-test-matrix-summary)
3. [3. Bukti Eksekusi Runtime & Assertion Logs (REPORT Test Cases & Screenshots)](#3-bukti-eksekusi-runtime--assertion-logs)
4. [4. Verifikasi Konkurensi & Race Condition](#4-verifikasi-konkurensi--race-condition)
5. [5. Keputusan Gatekeeper (Verdict)](#5-keputusan-gatekeeper-verdict)
6. [6. Matriks Triage Validasi (Auto vs Human)](#6-matriks-triage-validasi-auto-vs-human)
7. [7. Review & Sign-Off Analis, LEMBAR PERSETUJUAN & Revision History](#7-review--sign-off-analis)

---

## 1. Metadata & Lingkup Pengujian

### 1.1. Tabel Metadata Baku Quality Assurance Document (QAD)

| Quality Assurance Document (QAD) | |
| :--- | :--- |
| **Project No.** | `DOC-[PROJECT_ID]-[YEAR]` |
| **Project Title** | [TESTPLAN] [PROJECT_TITLE] |
| **Date** | [DD Mon YYYY] |
| **Division** | `[ORGANIZATION_DIVISION]` |
| **Product/Module** | [NAMA_MODUL_PRODUK] |
| **Version** | 1.0 |
| **Test Plan Link** | [URL_TEST_PLAN_PORTAL] |
| **Supporting Document(s)** | [ ] Project Plan<br>[✔] PRD (01-requirements.md)<br>[✔] Technical Spec / SDD (02-technical-spec.md)<br>[ ] Other |

### 1.2. Ringkasan Parameter Teknis Pengujian

| Parameter | Nilai |
|---|---|
| **Project ID** | `[PROJECT_ID]` |
| **Fitur / Modul Diuji** | `[NAMA_FITUR / RUANG_LINGKUP]` |
| **Fase QA Saat Ini** | `[Fase 1: Positive QA Suite -> Dokumentasi Baku QAD (.docx, .xlsx, .md) -> Validasi Pengguna (UAT Gate)]` |
| **Tanggal Pengujian** | `[YYYY-MM-DD HH:MM WIB]` |
| **QA Engineer / Role** | `[QA_ENGINEER_NAME / qa-engineer]` |
| **Lead QA Reviewer** | `[ANALYST_NAME / analyst]` |
| **Target Service URL** | `[URL_TARGET_SANDBOX_LOCAL]` |
| **Test Collection Suite** | `[PATH_KOLEKSI_BRUNO_ATAU_TEST_SUITE]` |
| **Hasil Akhir Teknis** | **`VERDICT: [PASSED | REJECTED]`** |
| **Status Review Analis** | **`ANALYST STATUS: [APPROVED | NEEDS_QA_REVISION]`** |

### 1.3. Latar Belakang & Expected Result
- **Background**: [Jelaskan latar belakang teknis pembangunan fitur/layanan dan integrasinya pada organisasi aktif]
- **Expected Result**:
  1. [Hasil yang diharapkan 1]
  2. [Hasil yang diharapkan 2]
  3. [Hasil yang diharapkan 3]

---

## 2. 4-Dimensional Test Matrix Summary

Matriks uji holistik mencakup 4 dimensi pengujian: **1. Skenario Positif (Happy Path)**, **2. Skenario Batas & Negatif (Boundary)**, **3. Idempotensi & State Preservation**, serta **4. Keamanan & Konkurensi (Race Condition)**:

| ID Uji | Dimensi Pengujian | Skenario Pengujian (Scenario) | Expected Result (BDD Style) | Hasil Aktual | Evidence Folder | Kategori Triage | Status |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|
| **TC-01** | **1. Skenario Positif (Happy Path)** | [POSITIVE] `[Judul skenario positif]` | Then `[Ekspektasi BDD]`<br>And `[Kondisi lanjutan]` | `[Hasil observasi]` | `docs/qa/evidence/TC-1` | `AUTO_VERIFIED` | `PASS` |
| **TC-02** | **2. Skenario Batas & Negatif (Boundary)** | [NEGATIVE] `[Judul skenario batas/error]` | Then `[Ekspektasi pesan error/status 400]` | `[Hasil observasi]` | `docs/qa/evidence/TC-2` | `AUTO_VERIFIED` | `PASS` |
| **TC-03** | **3. Idempotensi & State Preservation** | [IDEMPOTENCY] `[Repeat execution / only_new check]` | Then `[State terlindungi, 0 mutasi liar]` | `[Hasil observasi]` | `docs/qa/evidence/TC-3` | `AUTO_VERIFIED` | `PASS` |
| **TC-04** | **4. Keamanan & Konkurensi (Race Condition)** | [SECURITY] `[Auth protection & race detector]` | Then `[401 Unauthorized & 0 data race warning]` | `[Hasil observasi]` | `docs/qa/evidence/TC-4` | `AUTO_VERIFIED` | `PASS` |
| **TC-05** | **1. Skenario Positif (Happy Path)** | [POSITIVE] `[Verifikasi UI & Integrasi Live]` | Then `[Tercermin di portal Admin UI]` | `[Hasil observasi]` | `docs/qa/evidence/TC-5` | `HUMAN_VALIDATION_REQUIRED` | `PASS` |

---

## 3. Bukti Eksekusi Runtime & Assertion Logs

### 3.1. Output Eksekusi Test Runner (cURL / Bruno / CLI)
```bash
[Lampirkan output perintah CLI pengujian di sini]
```

### 3.2. Detail Report Baku QAD per Test Case & Embedded Screenshots

| Test Case TC-01 | |
| :--- | :--- |
| **Scenario** | [POSITIVE] `[Judul Skenario Uji]` |
| **Precondition(s)** | `[Prasyarat pengujian]` |
| **Test Details** | **Scenario:** `[Nama Skenario]`<br>**Given** `[Kondisi awal]`<br>**When** `[Tindakan pengujian]`<br>**Then** `[Hasil yang diharapkan]`<br>**And** `[Kondisi verifikasi lanjutan]` |
| **Actual Result** | 1. `[Langkah aktual 1]`.<br>2. `[Langkah aktual 2]`.<br>3. `[Bukti tangkapan layar screenshot .png tersemat di sel tabel]`: <br>![TC-01 Hit Result](docs/qa/evidence/TC-1/01-hit-result.png) |
| **Final Result** | **PASSED** |
| **Note** | `[Catatan observasi teknis]` |

---

## 4. Verifikasi Konkurensi & Race Condition

Perintah dieksekusi: `go test -v -count=1 -race ./...`

```text
[Lampirkan ringkasan log race detector di sini]
```

**Evaluasi Konkurensi**:
- Status: `[100% PASS | TERDETEKSI RACE]`
- Data Race Warnings: `[0 Warnings | Ada Warning]`

---

## 5. Keputusan Gatekeeper (Verdict)

### Evaluasi Checklist Gatekeeper:
- [ ] **Kepatuhan Kontrak API**: Seluruh respons HTTP status code dan JSON Schema sesuai spesifikasi teknis.
- [ ] **Kehandalan Skenario Batas**: Seluruh error 400, 404, dan 422 ditangani secara elegan tanpa kebocoran stack trace.
- [ ] **Idempotensi & State Safety**: Data eksisting terlindungi dari mutasi liar saat pemanggilan berulang.
- [ ] **Thread-Safety & Konkurensi**: Lolos pengujian race detector tanpa peringatan data race.
- [ ] **Sanitasi Kredensial**: Tidak ada data rahasia atau kredensial yang terekspos ke log maupun payload.

### Keputusan Akhir Teknis:
**`VERDICT: [PASSED | REJECTED]`**

---

## 6. Matriks Triage Validasi (Auto vs Human)

### 6.1. Ringkasan Status Triage
| Total Skenario Uji | AUTO_VERIFIED (Mesin) | HUMAN_VALIDATION_REQUIRED (Manusia) |
| :---: | :---: | :---: |
| `[Total]` | `[Jumlah (%)]` | `[Jumlah (%)]` |

### 6.2. Item yang Tuntas Diverifikasi Mesin (`[AUTO_VERIFIED]`)
| ID Skenario | Deskripsi Verifikasi | Folder Bukti (Evidence) | Metode / Bukti Otomasi | Status |
| :--- | :--- | :--- | :--- | :---: |
| `[ID]` | `[Deskripsi]` | `[Folder evidence]` | `[Metode verifikasi otomasi]` | `PASSED` |

### 6.3. Checklist Validasi Khusus Pengguna Manusia (`[HUMAN_VALIDATION_REQUIRED]`)
| ID Skenario | Area Validasi Krusial | Folder Bukti (Evidence) | Mengapa Butuh Validasi Manusia? | Langkah Pemeriksaan bagi Pengguna UAT | Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| `[ID]` | `[Area]` | `[Folder evidence]` | `[Alasan teknis/bisnis]` | `[Langkah konkret cara cek]` | `PASSED` |

---

## 7. Review & Sign-Off Analis

- **Lead QA Reviewer**: `[Nama Analis / Senior Lead Engineer]`
- **Tanggal Review**: `[YYYY-MM-DD HH:MM WIB]`
- **Status Review Analis**: **`ANALYST STATUS: [APPROVED | NEEDS_QA_REVISION]`**

### 7.1. Evaluasi Relevansi Lapangan (Field-Realism Assessment)
- **Cakupan Skenario Operasional**: `[Memadai / Perlu Dilengkapi]`
- **Kualitas & Kedalaman Multi-Examples**: `[Sesuai Standar Enterprise / Minim Variasi]`
- **Ketajaman Uji Batas & Idempotensi**: `[Tajam & Mendalam / Terlalu Dangkal]`

### 7.2. Arahan Teknis Lead (Lead Directive)
```text
[Tuliskan catatan teknis dan arahan koreksi jika berstatus NEEDS_QA_REVISION, atau pernyataan sign-off resmi jika berstatus APPROVED]
```

### 7.3. Keputusan Final Analis:
**`ANALYST STATUS: [APPROVED | NEEDS_QA_REVISION]`**

---

| RESULT |
| :---: |
| **[X] Test(s) PASSED** |

<br>

| LEMBAR PERSETUJUAN | | | | |
| :---: | :--- | :--- | :---: | :---: |
| **No.** | **Roles** | **Nama** | **Tanggal** | **Tanda Tangan** |
| 1 | Tester | `[Nama QA Engineer]` | `[Tanggal]` | `(Signed)` |
| 2 | Reviewer | `[Nama Analis / Lead]` | `[Tanggal]` | `(Signed)` |
| 3 | QA Manager | (Menunggu Persetujuan) | `[Tanggal]` | |
| 4 | Department Head | (Menunggu Persetujuan) | `[Tanggal]` | |

---

| Revision History | | | | |
| :---: | :--- | :--- | :---: | :---: |
| **No.** | **PIC** | **Deskripsi** | **Versi** | **Tanggal** |
| 1 | `[Nama PIC]` | Dokumen Baru - QAD Positive Suite & Verifikasi Web UI Portal | 1.0 | `[Tanggal]` |
