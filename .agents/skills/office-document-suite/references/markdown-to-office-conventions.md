# Konvensi Penulisan Dokumen: Markdown-First to Office Suite

Dokumen ini menjelaskan konvensi penyusunan berkas Markdown (`.md`) agar saat dikonversi menggunakan `doc-tool.py` menghasilkan dokumen kantor tingkat enterprise (`.xlsx` dan `.docx`) dengan kualitas visual dan tipografi terbaik.

---

## 1. Konvensi Penyusunan Multi-Sheet Excel (`.xlsx`)

`doc-tool.py` menggunakan heading Markdown terdekat sebelum tabel untuk menentukan **Nama Sheet** pada workbook Excel.

### Format Standar:
```markdown
# Laporan Keuangan & Operasional

## Sheet: Ringkasan Portofolio
| ID Pelanggan | Nama Pelanggan | Saldo Poin / Unit | Status Akun |
| :--- | :--- | :---: | :---: |
| CUST-001 | Budi Santoso | 25.5 | ACTIVE |
| CUST-002 | Siti Rahmawati | 100.0 | ACTIVE |
| CUST-003 | Ahmad Fauzi | 0.0 | DORMANT |

## Sheet: Log Transaksi Harian
| No Tiket | Tanggal | Nominal (IDR) | Jenis Transaksi |
| :--- | :---: | :---: | :--- |
| TXN-20261112-001 | 2026-11-12 | 1250000 | TOPUP |
| TXN-20261112-002 | 2026-11-12 | 500000 | PAYMENT |
```

### Aturan & Fitur Otomatis:
1. **Nama Tab / Sheet**:
   - Teks setelah `## Sheet:` atau `## ` otomatis menjadi nama tab di Excel.
   - Karakter terlarang (`\ / ? * [ ] :`) otomatis disanitasi menjadi underscore (`_`).
   - Panjang nama sheet dibatasi maksimal 31 karakter sesuai standar OpenXML.
2. **Styling Header Otomatis**:
   - Baris pertama tabel diformat dengan latar belakang hijau gelap tema (`#1B4D3E`), teks putih tebal (*bold*), dan rata tengah (*center aligned*).
3. **Freeze Panes**:
   - Baris header pertama otomatis di-*freeze* (`ySplit=1`), sehingga saat pengguna menggulir ribuan baris data ke bawah, header kolom tetap terlihat.
4. **Auto-fit Column Widths**:
   - Lebar kolom dihitung secara dinamis berdasarkan panjang karakter teks terpanjang pada kolom tersebut.
5. **Deteksi Tipe Data Otomatis**:
   - Angka desimal dan integer otomatis disimpan sebagai numeric cell (`<v>`), sehingga pengguna di Excel langsung bisa melakukan rumus SUM, AVERAGE, dsb. tanpa perlu konversi manual dari teks.

---

## 2. Konvensi Penyusunan Dokumen Word (`.docx`)

### Format Standar:
```markdown
# Spesifikasi Arsitektur Sistem Gateway Service

Dokumen ini mendefinisikan rancangan arsitektur dan spesifikasi integrasi API Gateway.

## 1. Ruang Lingkup Integrasi
Layanan ini menyediakan mekanisme sinkronisasi granular tingkat method dan path.

- Mendukung sinkronisasi parsial method HTTP (`GET`, `POST`, `PUT`, `DELETE`).
- Menjamin preservasi endpoint eksisting melalui mode `only_new=true`.
- Menyediakan simulasi dry-run tanpa mutasi persisten.

## 2. Matriks Pengujian Validasi UAT
| ID Uji | Skenario Pengujian | Hasil Aktual | Kategori Triage |
| :--- | :--- | :---: | :---: |
| TC-01 | Sinkronisasi Endpoint Baru | 200 OK | AUTO_VERIFIED |
| TC-02 | Verifikasi Visual Portal Admin | Aktif di UI | HUMAN_VALIDATION_REQUIRED |
```

### Aturan & Fitur Otomatis:
1. **Tipografi Hierarkis**:
   - `# Heading 1` diformat sebagai Judul Utama 16pt Bold dengan warna tema (`#1B4D3E`).
   - `## Heading 2` diformat sebagai Sub-Judul 13pt Bold dengan warna tema.
   - `### Heading 3` diformat sebagai Sub-Judul Bagian 11pt Bold dengan warna abu gelap (`#2F4F4F`).
2. **Tabel Bergaris Elegan (Bordered Tables)**:
   - Header tabel diarsir dengan warna latar tema (`#1B4D3E`) dan teks putih tebal.
   - Baris genap diarsir dengan warna latar abu sangat muda (*zebra striping* `#F9FBF9`).
   - Padding sel (*cell margins*) diatur rapi (atas/bawah 6pt, kiri/kanan 8pt).
3. **Daftar Poin (Bullet Lists)**:
   - Baris berawalan `- ` atau `* ` otomatis dikonversi menjadi bullet list dengan simbol `•`.

---

## 3. Alur Kerja Rekomendasi untuk Agen

1. **Membaca Dokumen Masukan**:
   ```bash
   # 1. Periksa struktur dokumen
   ./cmd/doc-tool inspect dokumen_spesifikasi.docx
   
   # 2. Ekstrak dokumen menjadi Markdown untuk dianalisis
   ./cmd/doc-tool read dokumen_spesifikasi.docx --output draft_kebutuhan.md
   ```

2. **Membuat Dokumen Keluaran (Export)**:
   ```bash
   # 1. Agen menyusun tabel data dalam Markdown (hemat token ~90%)
   cat << 'EOF' > hasil_triage.md
   ## Sheet: UAT Triage
   | Modul | Status |
   | API | AUTO_VERIFIED |
   EOF
   
   # 2. Konversi deterministik menjadi Excel resmi
   ./cmd/doc-tool write hasil_triage.md dist/UAT_Triage_Matrix.xlsx
   ```
