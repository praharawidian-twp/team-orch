---
name: office-document-suite
version: 1.0.0
description: >-
  Token-Efficient Office Document Suite Protocol & CLI (doc-tool). Provides zero-dependency native readers and writers for .xlsx, .docx, .pptx, .pdf, .doc, .rtf, .csv, and .json. Enforces the Markdown-First Document Engineering pattern to save 85-90% token budget when processing and generating enterprise spreadsheets and documents.
author: Meta-Studio Platform Engineering
tags: [office, excel, word, pdf, docx, xlsx, pptx, doc-tool, token-efficiency]
---

# 📑 Office Document Suite Protocol (`office-document-suite`)

## 1. Context & Business Intent

Dalam alur kerja rekayasa perangkat lunak enterprise, agen otonom sering kali berinteraksi dengan artefak dokumen kantor:
1. **Membaca Dokumen Masukan**: Dokumen kebutuhan bisnis (BRD/PRD dalam `.docx`), kamus data atau matriks pengujian dalam `.xlsx`, paparan arsitektur dalam `.pptx`, serta spesifikasi teknis dalam `.pdf`.
2. **Membuat Dokumen Keluaran (Deliverables)**: Mengekspor Matriks Pengujian UAT multi-sheet ke format Excel (`.xlsx`), menyusun dokumen arsitektur atau User Runbook ke format Word (`.docx`), atau membuat ringkasan eksekutif.

### Masalah Pola Lama (High Token Inefficiency):
- Jika agen menulis skrip Python ad-hoc (misal menggunakan library pihak ketiga) setiap kali membuat file `.xlsx` atau `.docx`, agen menghabiskan ribuan token untuk menulis kode boilerplate styling, openpyxl, dsb.
- Jika library tidak terinstal di sistem target (`ModuleNotFoundError`), alur kerja agen terhenti dan mengalami kegagalan fatal.

### Solusi: Pola "Markdown-First + Deterministic Converter":
Skill **`office-document-suite`** menyediakan utilitas resmi **`doc-tool.py`** yang:
- **Zero-Dependency Resilient**: 100% menggunakan Python standard library (`zipfile`, `xml.etree.ElementTree`, `csv`, `json`) dan utilitas bawaan macOS (`/usr/bin/textutil`, JXA `PDFKit`). Tidak membutuhkan instalasi paket eksternal (`pip` / `brew`).
- **Token-Efficient**: Agen cukup bekerja dengan Markdown bersih (`.md`), lalu mengonversinya secara deterministik ke `.xlsx` atau `.docx` dengan styling enterprise otomatis. Hemat ~85–90% token output!

---

## 2. CLI Tooling: `doc-tool.py`

Path CLI Resmi:
- `.agents/skills/office-document-suite/scripts/doc-tool.py`

### 1. `inspect <file>` — Mengintip Struktur Dokumen Sebelum Dibaca
Gunakan perintah ini untuk memeriksa struktur, daftar nama sheet, dimensi baris/kolom, atau jumlah halaman tanpa memboroskan token context window.

```bash
python3 .agents/skills/office-document-suite/scripts/doc-tool.py inspect dokumen.xlsx
python3 .agents/skills/office-document-suite/scripts/doc-tool.py inspect spesifikasi.docx
python3 .agents/skills/office-document-suite/scripts/doc-tool.py inspect panduan.pdf
```

Output berupa JSON ringkas:
```json
{
  "file_name": "dokumen.xlsx",
  "extension": ".xlsx",
  "file_size_human": "14.2 KB",
  "sheet_count": 2,
  "sheets": [
    {"name": "Ringkasan", "rows": 10, "columns": 5},
    {"name": "Detail Transaksi", "rows": 250, "columns": 8}
  ]
}
```

### 2. `read <file> [--sheet <name>] [--max-rows <N>] [--output <out.md>]` — Mengekstrak ke Markdown
Mengonversi isi dokumen menjadi tabel atau teks Markdown bersih.

```bash
# Membaca seluruh sheet Excel menjadi tabel Markdown
python3 .agents/skills/office-document-suite/scripts/doc-tool.py read laporan.xlsx

# Membaca sheet tertentu saja (hemat token)
python3 .agents/skills/office-document-suite/scripts/doc-tool.py read laporan.xlsx --sheet "Ringkasan"

# Membatasi jumlah baris per sheet untuk inspeksi cepat
python3 .agents/skills/office-document-suite/scripts/doc-tool.py read transaksi_besar.xlsx --max-rows 20

# Mengekstrak dokumen Word (.docx) lengkap dengan heading dan tabel utuh
python3 .agents/skills/office-document-suite/scripts/doc-tool.py read spesifikasi.docx --output spec.md

# Membaca file presentasi (.pptx) atau PDF (.pdf)
python3 .agents/skills/office-document-suite/scripts/doc-tool.py read presentasi.pptx
python3 .agents/skills/office-document-suite/scripts/doc-tool.py read panduan.pdf
```

### 3. `write <input> <output> [--title <title>]` — Menghasilkan Dokumen Kantor Resmi
Mengonversi file Markdown (`.md`), CSV, atau JSON menjadi dokumen Excel (`.xlsx`), Word (`.docx`), atau HTML (`.html`) berformat elegan.

```bash
# 1. Menghasilkan Spreadsheet Multi-Sheet Excel dari Markdown
python3 .agents/skills/office-document-suite/scripts/doc-tool.py write input.md laporan_hasil_uji.xlsx

# 2. Menghasilkan Dokumen Word dari Markdown
python3 .agents/skills/office-document-suite/scripts/doc-tool.py write dokumentasi.md panduan_sistem.docx --title "Panduan Operasional"

# 3. Menghasilkan Spreadsheet Excel dari CSV atau JSON
python3 .agents/skills/office-document-suite/scripts/doc-tool.py write data.csv tabel_data.xlsx
```

### 4. `write-qad <output.docx> [--template <tmpl.docx>] [--domain <domain_id>] [--data <data.md/json>] [--base-dir <dir>]` — Menghasilkan Dokumen Baku Quality Assurance Document (QAD)
Mempopulasikan template Word resmi dari **Specific Domain Pack** yang sedang aktif (`.agents/domains/<domain_id>/templates/qad-template.docx` atau `~/.gemini/team-orch/domains/<domain_id>/templates/qad-template.docx`), atau path khusus via `--template`. Mempertahankan seluruh tipografi, logo, header/footer disclaimer, layout cover, dan warna tema template domain tersebut, lengkap dengan penyematan bukti screenshot visual di sel `Actual Result`. Jika aktif domain adalah `base` tanpa `--template`, harap aktifkan Specific Domain Pack via `./cmd/team-orch domain use <domain_id>` atau tentukan `--template <path.docx>`.

```bash
# Menghasilkan dokumen QAD otomatis menggunakan template & metadata Active Domain:
python3 .agents/skills/office-document-suite/scripts/doc-tool.py write-qad "docs/qa/QAD - sample-api - Automated Validation Report.docx" --base-dir docs/qa --data qa-data.json

# Atau tentukan domain / template secara eksplisit:
python3 .agents/skills/office-document-suite/scripts/doc-tool.py write-qad "docs/qa/QAD - Report.docx" --domain <domain_id> --base-dir docs/qa
```

---

## 3. Fitur Desain Otomatis pada Dokumen Hasil Generate

### Pada Dokumen Excel (`.xlsx`):
1. **Multi-Sheet Mapping**: Setiap heading `## Sheet: <Nama Sheet>` atau `## <Nama Sheet>` sebelum tabel Markdown otomatis menjadi sheet terpisah.
2. **Professional Styling**: Header tabel diwarnai dengan warna tema gelap (`#1B4D3E`), teks putih tebal, dan border tipis.
3. **Zebra Striping**: Baris genap diarsir dengan warna latar hijau muda lembut (`#F4F8F6`).
4. **Freeze Header Row**: Baris pertama otomatis terkunci (*frozen header*), memudahkan pembacaan saat data digulir ke bawah.
5. **Auto-fit Column Widths**: Lebar kolom disesuaikan secara otomatis dengan panjang teks data.
6. **Smart Type Detection**: Angka integer dan desimal otomatis disimpan sebagai numeric cell (`<v>`), sehingga siap dioperasikan dengan formula Excel.

### Pada Dokumen Word (`.docx`):
1. **Tipografi Hierarkis Enterprise**: `# Heading 1`, `## Heading 2`, `### Heading 3` diformat dengan ukuran konsisten dan warna tema aksen (`#004D40`).
2. **Tabel Bergaris Rapi**: Tabel Markdown dikonversi menjadi tabel Word bergaris dengan header berwarna gelap (`#004D40`), teks putih tebal, zebra striping, dan cell padding rapi.
3. **Dukungan Format Baku Quality Assurance Document (QAD) via Specific Domain**:
   - Template QAD berlogo perusahaan disimpan terisolasi di Specific Domain Pack (`templates/qad-template.docx`).
   - Mendukung banner header tabel satu kolom (`RESULT`, `Quality Assurance Document (QAD)`, `Test Case TC-X`) dengan warna aksen tema dan teks putih tebal.
4. **Penyematan Gambar Asli (.png) di Dalam Sel Tabel (Embedded Screenshots)**:
   - Sintaks Markdown `![caption](path/to/image.png)` baik di paragraf biasa maupun di dalam sel tabel (khususnya baris `Actual Result` pada QAD) dikonversi menjadi gambar OpenXML drawing inline (`word/media/imageN.png`) dengan aspect ratio proporsional.
5. **Linear O(N) PDF Stream Parser**:
   - Membaca dan menginspeksi PDF besar (>3.6 MB) yang sarat binary image stream dalam waktu linear (<0.2 detik) tanpa risiko catastrophic regex backtracking.
6. **Page Break Otomatis**: Baris `---` atau `<pagebreak/>` otomatis dikonversi menjadi page break Word (`<w:br w:type="page"/>`).

---

## 4. Panduan Format Markdown

Untuk memastikan konversi menghasilkan layout terbaik, ikuti konvensi penulisan pada dokumen referensi:
- `.agents/skills/office-document-suite/references/markdown-to-office-conventions.md`

---

## 5. Master Template Dokumen Organisasi (Specific Domain Pack)

Base Domain publik **tidak menyertakan** template berlogo, dokumen internal, atau standar milik perusahaan mana pun (prinsip *Zero Institutional Knowledge*). Jika organisasi Anda memiliki master template resmi, kelola melalui **Specific Domain Pack**:
- **Lokasi Master Template Domain**: `.agents/domains/<domain_id>/templates/` (atau `~/.gemini/team-orch/domains/<domain_id>/templates/`)
- **Referensi Kustom Domain**: Didefinisikan di `domain.yaml` masing-masing domain pada kunci `templates:` dan `documents:`.

### Struktur Kolom Standar QA Default (10 Kolom Generik):
Saat mengekstrak atau menyusun laporan pengujian Test Case Excel (`.xlsx`), gunakan 10 kolom standar berikut (atau ikuti skema kustom pada Specific Domain Pack aktif):
1. **`Test ID`**: Identifikasi unik pengujian (contoh: `1.0`, `TC-01`).
2. **`Summary`**: Ringkasan skenario dengan tag kategori (contoh: `[POSITIVE] Pengecekan Jurnal...` atau `[NEGATIVE] Validasi Request...`).
3. **`Description`**: Deskripsi detail skenario bisnis.
4. **`Test Type`**: Jenis pengujian (contoh: `Cucumber`, `Manual`, `API Contract`).
5. **`Gherkin Definition`**: Spesifikasi sintaks `Given ... And ... When ... Then ...`.
6. **`Cucumber Test Type`**: Kategori automated test runner.
7. **`Environment`**: Target lingkungan (contoh: `Local`, `Sandbox`, `Development`).
8. **`Expected Result`**: Ekspektasi hasil pengujian secara presisi.
9. **`Reporter`**: Nama/role pembuat laporan (`qa-engineer`).
10. **`Status Automation`**: Status kesiapan script automasi (`Done`, `Pending`, `Manual Only`).

---

## 6. Integrasi Peran Agen

- **Project Manager (`project-manager`)**: Menggunakan `doc-tool.py read` untuk membedah dokumen BRD/PRD dari pengguna tanpa merusak format tabel.
- **Analis (`analyst`)**: Menggunakan `doc-tool.py inspect & read` untuk menganalisis kamus data referensi dari pengguna.
- **QA Engineer (`qa-engineer`)**: Menggunakan `doc-tool.py write` untuk mengekspor Matriks UAT Triage ke dalam file Excel resmi (`.xlsx`).
- **Dokumenter (`documenter`)**: Menggunakan `doc-tool.py write` untuk mengonversi berkas dokumentasi Markdown ke dokumen Word (`.docx`) atau Excel terstruktur bagi stakeholder bisnis.
