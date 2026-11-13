# ✍️ Pedoman Penulisan Dokumentasi & Release Notes

> **Topik ID**: `technical-writing`  
> **Akses**: `documenter`  
> **Tingkat Kepatuhan**: `ADVISORY`

---

## 1. Sasaran Dokumentasi
1. Menjelaskan kepada pengembang dan pengguna baru bagaimana cara mengonfigurasi, menjalankan, dan menguji fitur yang baru selesai dibangun.
2. Seluruh dokumentasi harus sinkron 100% dengan implementasi riil (tidak mendokumentasikan fitur khayalan).

---

## 2. Struktur Standar Dokumen Pengguna (README / User Guide)
1. **Ringkasan Singkat**: 2-3 kalimat pengantar tentang tujuan modul.
2. **Prasyarat & Konfigurasi**: Dependency, environment variables, dan port.
3. **Panduan Cepat (Quick Start)**: Contoh perintah satu baris untuk menjalankan aplikasi.
4. **Referensi API / Interface**: Endpoint, request payload, response status, dan contoh kode curl/fetch.
5. **Panduan Pengujian**: Perintah untuk menjalankan unit test lokal.

---

## 3. Gaya Bahasa & Format
1. Gunakan format GitHub Flavored Markdown (GFM) yang bersih.
2. Sertakan tautan berkas yang dapat diklik (*clickable links*).
3. Buat diagram alur atau sequence diagram menggunakan sintaks `mermaid` jika menjelaskan alur multi-step.
