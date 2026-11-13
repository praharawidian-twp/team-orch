# 🗄️ Konvensi Skema Database, Naming & Migrasi

> **Topik ID**: `database-conventions`  
> **Akses**: `coder`, `analyst`  
> **Tingkat Kepatuhan**: `STRICT`

---

## 1. Standar Penamaan (Naming Conventions)
1. Nama tabel wajib berbentuk jamak (*plural*) dan menggunakan huruf kecil dengan garis bawah (*snake_case*), contoh: `users`, `order_items`, `payment_transactions`.
2. Nama kolom wajib menggunakan *snake_case*, contoh: `created_at`, `user_id`, `is_active`.
3. Kolom *Primary Key* wajib bernama `id` (UUID atau BigSerial).
4. Kolom *Foreign Key* wajib menggunakan format `<nama_tabel_tunggal>_id`, contoh: `user_id`, `product_id`.

---

## 2. Standar Kolom Wajib (Audit Columns)
Setiap tabel utama wajib menyertakan kolom jejak waktu (*timestamp* UTC):
- `created_at` (TIMESTAMPTZ, default: now)
- `updated_at` (TIMESTAMPTZ, default: now)
- `deleted_at` (TIMESTAMPTZ, nullable, jika mendukung soft delete)

---

## 3. Aturan Migrasi Database
1. Migrasi wajib bersifat non-destruktif.
2. DILARANG mengeksekusi `DROP TABLE` atau `DROP COLUMN` secara mendadak tanpa backward compatibility.
3. Selalu buatkan pasangan migrasi *Up* dan *Down* (Rollback).
4. Kolom foreign key dan kolom yang sering dicari dalam filter query wajib memiliki *INDEX*.
