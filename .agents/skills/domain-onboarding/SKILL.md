---
name: domain-onboarding
description: Just-in-Time Specific Domain Discovery & Interactive Pack Builder. Activate on Day-1 when the framework is still in 'base' mode and a user requests project, QA, document, or boilerplate work that involves organization-specific context, or when the user invokes /grill-me to configure a company/project Specific Domain Pack.
---

# Specific Domain Onboarding & Discovery Protocol (`/grill-me` + CLI Wizard)

Skill ini menjembatani **Base Domain** (*Day-1 Employee / Zero Institutional Knowledge*) menuju pembuatan **Specific Domain Pack** yang terisolasi dan ter-`gitignore` di `.agents/domains/<domain_id>/` (serta tersinkron ke `~/.gemini/team-orch/domains/<domain_id>/`).

---

## 1. Kapan Skill Ini Dipicu (Just-in-Time Day-1 Detection)

Aktifkan protokol ini secara proaktif **sebelum** menyusun PRD, spesifikasi teknis, laporan QA, atau dokumen kantor apabila:
1. `team-orch domain current` masih berstatus **`base`**, **DAN**
2. Pengguna baru pertama kali meminta agen mengerjakan sesuatu (misal: *"buatkan layanan API..."*, *"susun laporan QA/QAD..."*, *"review repositori ini..."*, *"generate dokumen standar kantor..."*) yang menyiratkan adanya standar/aset institusional; **ATAU**
3. Pengguna secara eksplisit meminta konfigurasi domain baru atau menjalankan **`/grill-me`** untuk menggali konteks organisasi/proyek.

---

## 2. Langkah 0 — Konfirmasi Jalur Cepat (Consent & Scope Check)

Jangan memaksa wawancara panjang jika tugas pengguna memang murni personal atau generik. Sebelum menggali 5 pilar di bawah, tanyakan singkat (gunakan `ask_question` bila tersedia):
- **Opsi A (Direkomendasikan untuk kerja organisasi/tim)**: *"Aktifkan Specific Domain Onboarding — Saya wawancarai singkat (5 topik) untuk menyimpan nama organisasi, aplikasi, domain internal, template berlogo, pejabat, dan boilerplate secara permanen di `.agents/domains/` (gitignored)."*
- **Opsi B**: *"Lanjut di mode `base` generik tanpa konteks perusahaan khusus."*

Jika pengguna memilih **Opsi B**, langsung lanjutkan tugas menggunakan standar umum `base` domain dan jangan mengarang identitas institusi mana pun.

---

## 3. Protokol Wawancara Terstruktur 5 Pilar (Gaya `/grill-me`)

Gali kebutuhan secara bertahap (maksimal 2-3 poin pertanyaan per giliran agar pengguna tidak kewalahan, tanpa asumsi/halusinasi):

### Pilar 1 — Identitas Organisasi & Branding Dokumen
- Nama **`domain_id`** (`kebab-case`, misal `acme-core`, `fintech-ops`)
- Nama resmi **Organisasi / Perusahaan** & **Divisi / Unit**
- Warna tema aksen (**Brand Color Hex**, misal `#004D40`) untuk header tabel/dokumen
- Teks **Confidentiality Disclaimer** resmi pada dokumen (opsional)

### Pilar 2 — Daftar Pejabat / Approver Resmi
- Daftar peran dan nama PIC yang muncul pada Lembar Persetujuan dokumen atau UAT Gate (misal: `QA Manager`, `Tech Lead`, `Department Head`, `Product Owner`).

### Pilar 3 — Aplikasi, Portal & Domain Internal Resmi
- Daftar aplikasi yang dikelola tim (`id`, `name`)
- Daftar URL / Origin internal resmi per environment (`dev`, `staging`, `admin portal`) agar `ui-evidence-capture` (`qa-targets.yaml`) & kontrak API memiliki allowlist akurat tanpa menebak URL.

### Pilar 4 — Master Template Resmi & Standar Matriks (`.docx`, `.xlsx`, `.pdf`)
- Tanyakan apakah organisasi memiliki contoh template berlogo (`.docx` QAD/SDD/User Guide), standar kolom Excel Test Case (`.xlsx`), atau contoh PDF referensi.
- Jika pengguna memberikan path berkas/direktori template:
  1. Inspeksi otomatis strukturnya dengan:
     ```bash
     python3 .agents/skills/office-document-suite/scripts/doc-tool.py inspect "<path_template>"
     ```
  2. Salin master template terpilih ke `.agents/domains/<domain_id>/templates/` (mis. `templates/qad-template.docx`) atau catat direktori acuan eksternal pada `templates.external_reference_dir` di `domain.yaml`.

### Pilar 5 — Repositori Boilerplate & Konvensi / SOP Internal
- Tanyakan URL Git repositori boilerplate (jika ada), jenis stack/arsitekturnya (`service`, `frontend`, `gateway`, dsb.), dan pola branch (`main`, `master`, atau *branch-per-archetype*).
- Tanyakan aturan teknis/SOP unik kantor yang harus dipatuhi `analyst`, `coder`, maupun `qa-engineer`.
- Simpan konvensi khusus tersebut ke `.agents/domains/<domain_id>/knowledge/topics/<topik>.md` dan daftarkan ke `.agents/domains/<domain_id>/knowledge/registry.yaml`.

---

## 4. Materialisasi Otomatis & Lanjutkan Tugas Awal

Setelah wawancara tuntas:
1. Buat & isi Domain Pack (atau jalankan wizard CLI interaktif untuk pengguna terminal):
   ```bash
   team-orch domain init <domain_id> --interactive
   ```
   *(Atau tulis langsung `domain.yaml`, `boilerplates.yaml`, `knowledge/registry.yaml` ke `.agents/domains/<domain_id>/` sesuai skema `.agents/templates/domain-manifest-template.yaml`).*
2. Jika ada boilerplate Git pada `boilerplates.yaml`, tarik katalog cabangnya otomatis:
   ```bash
   sync-boilerplates --domain <domain_id>
   ```
3. Validasi, sinkronkan ke store global, lalu aktifkan:
   ```bash
   team-orch domain validate <domain_id>
   team-orch domain sync
   team-orch domain use <domain_id>
   ```
4. Jika sudah ada `<project_id>` aktif, ikat proyek tersebut agar konteks terkunci anti-halusinasi:
   ```bash
   team-orch domain bind <project_id> <domain_id>
   ```
5. **Segera lanjutkan tugas awal yang diminta pengguna** dengan memanfaatkan Specific Domain Pack yang baru terbentuk.
