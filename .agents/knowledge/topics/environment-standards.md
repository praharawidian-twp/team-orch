# ⚙️ Standar Environment, Konfigurasi & Sanitasi Secrets

> **Topik ID**: `environment-standards`  
> **Akses**: `*` (Global - Semua Agen)  
> **Tingkat Kepatuhan**: `STRICT`

---

## 1. Penanganan Variabel Lingkungan (.env)
1. Berkas `.env` asli berstatus rahasia dan **TIDAK BOLEH** dilacak di Git.
2. Setiap proyek wajib menyediakan berkas `.env.example` yang mencantumkan seluruh kunci konfigurasi dengan nilai dummy/placeholder yang aman.
3. Contoh:
   ```bash
   DATABASE_URL="postgres://user:password@localhost:5432/dbname"
   API_SECRET_KEY="your-secret-key-here"
   APP_PORT=8000
   ```

---

## 2. Zero Hardcoded Secrets Policy
1. DILARANG KERAS menuliskan kredensial rahasia (API Key, Private Key, Token, Password Database) langsung di dalam kode program (*plain hardcoded*).
2. Kredensial wajib dibaca dari variabel lingkungan (`process.env` atau `os.environ`).
3. Selalu sediakan *fallback* atau pesan error yang ramah jika variabel lingkungan belum disetel.

---

## 3. Isolasi Lingkungan (Dev vs Staging vs Production)
1. Port default lokal wajib menggunakan range non-konflik (misal: 3000, 8000, 8080).
2. Database pengujian wajib menggunakan database terisolasi (misal SQLite in-memory atau database lokal dev), DILARANG menembak langsung database produksi saat pengujian.
