# 📋 Standar Penyusunan PRD & Acceptance Criteria Anti-Asumsi

> **Topik ID**: `prd-rubric`  
> **Akses**: `project-manager`, `analyst`  
> **Tingkat Kepatuhan**: `STRICT`

---

## 1. Prinsip Utama Anti-Asumsi (No Guesswork)
1. Jika instruksi Pengguna memiliki bagian yang ambigu, PM **WAJIB** bertanya balik untuk klarifikasi sebelum menyusun spesifikasi final.
2. Dilarang berasumsi tentang integrasi pihak ketiga, teknologi database, atau arsitektur tanpa konfirmasi eksplisit.

---

## 2. Struktur Dokumen Kebutuhan (01-requirements.md)
Setiap PRD wajib memuat:
1. **Latar Belakang & Sasaran Bisnis**: Mengapa fitur ini dibutuhkan dan apa dampaknya.
2. **Batasan Lingkup (In-Scope vs Out-of-Scope)**: Secara tegas menuliskan apa yang akan dikerjakan dan apa yang TIDAK dikerjakan pada rilis ini.
3. **Acceptance Criteria (Kriteria Keberterimaan Terukur)**:
   - Format penomoran: `AC-01`, `AC-02`, dst.
   - Menggunakan format BDD atau checklist teruji:
     - *Given* [kondisi awal]
     - *When* [aksi dilakukan]
     - *Then* [hasil terukur yang diharapkan]

---

## 3. Human Approval Gate
1. PM **TIDAK BOLEH** langsung mengoper pekerjaan ke Coder sebelum dokumen `01-requirements.md` disetujui secara resmi oleh Pengguna (`team-orch approve <project_id>`).
