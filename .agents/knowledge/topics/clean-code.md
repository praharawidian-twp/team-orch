# 🧼 Standar Clean Code, Arsitektur & Separation of Concerns

> **Topik ID**: `clean-code`  
> **Akses**: `coder`, `analyst`  
> **Tingkat Kepatuhan**: `STRICT`

---

## 1. Prinsip Utama Rekayasa Kode
1. **Separation of Concerns (SoC)**:
   - Pisahkan logika bisnis (*domain logic*), akses database (*repository/data layer*), dan penanganan HTTP/CLI (*delivery layer*).
   - Jangan menaruh query SQL atau logika database di dalam controller / handler.
2. **Keterbacaan & Penamaan Eksplisit**:
   - Berikan nama fungsi dan variabel yang deskriptif dan mencerminkan tujuannya.
   - Hindari singkatan ambigu (misal: gunakan `customer_id` bukan `cid`).
3. **Kepatuhan Boilerplate Eksisting**:
   - Pelajari konvensi dan utilitas bersama (*shared utils*) yang sudah ada di proyek.
   - DILARANG membuat ulang fungsi utilitas yang sudah tersedia.

---

## 2. Penanganan Error (Graceful Error Handling)
1. Tangani setiap potensi error secara eksplisit (*no swallowed errors / bare exceptions*).
2. Berikan konteks error yang informatif untuk mempermudah debugging (sertakan ID entitas atau parameter yang gagal).
3. Jika berinteraksi dengan API eksternal, gunakan *timeout* dan mekanisme *retry* dengan batas yang wajar.

---

## 3. Disiplin Pengujian (Unit Test Requirement)
1. Setiap fitur atau perbaikan bug WAJIB disertai unit test.
2. Uji skenario normal (*happy path*), skenario kegagalan (*error path*), dan skenario batas (*edge cases*).
3. Unit test harus bersifat deterministik (tidak bergantung pada jaringan internet luar tanpa mocking).
