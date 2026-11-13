# 📐 Checklist Kepatuhan Boilerplate & Tata Kelola Dependensi

Dokumen ini menjadi acuan mutlak bagi Analis / Senior Tech Lead dalam mengaudit repositori eksisting sebelum mendesain spesifikasi teknis, serta dalam mengawasi agar Coder tidak menciptakan deviasi arsitektural.

---

## 1. Protokol Audit Boilerplate Pra-Desain (Pre-Design Audit)

Sebelum merancang `02-technical-spec.md`, Analis **WAJIB** mengeksekusi audit terhadap 5 pilar struktur repositori:

```
┌─────────────────────────────────────────────────────────────┐
│             Audit Repositori Eksisting                      │
└──────────────────────────────┬──────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
 1. Dependency Tree      2. Layer Architecture   3. Shared Utilities
    (go.mod / pkg.json)     (Folder Structure)      (Existing Packages)
       │                       │                       │
       └───────────────────────┼───────────────────────┘
                               │
       ┌───────────────────────┴───────────────────────┐
       ▼                                               ▼
 4. Error & Response Formats                     5. Testing & Mock Patterns
    (Envelopes & Domain Errors)                     (Fixtures, Suites, Harness)
```

### Checklist Pemeriksaan:
1. **Dependency Tree & Version Lock**:
   - Apa framework HTTP / RPC yang digunakan? (misal: Chi, Gin, Fiber, Echo, Express, FastAPI, NestJS).
   - Apa ORM / SQL driver yang dipakai? (misal: pgx, sqlx, gorm, Prisma, SQLAlchemy).
   - Apakah terdapat library validasi standar? (misal: `go-playground/validator`, `zod`, `pydantic`).
2. **Arsitektur Lapisan (Layering Standard)**:
   - Di mana domain model didefinisikan?
   - Bagaimana dependensi diinjeksikan? (misal: manual constructor injection `NewService(repo)`, wire, Fx, Nest DI).
   - Apakah domain entities murni independen dari transport protocol (HTTP/gRPC)?
3. **Shared Utilities & Cross-Cutting Concerns**:
   - Di mana helper hashing, token generator, atau string manipulation berada?
   - Bagaimana logger diinisialisasi? (misal: zap, zerolog, winston, structlog).
   - Apakah database connection pool telah diekspos melalui singleton atau interface?
4. **Error Envelope & Status Code Mapping**:
   - Apa format payload response standar API organisasi?
   - Apakah ada utilitas `response.Success(w, data)` dan `response.Error(w, httpCode, msg)`?
5. **Testing Harness & Mocking Standard**:
   - Apakah pengujian unit menggunakan mockery, gomock, testify suite, atau in-memory mock?
   - Apakah ada helper test database (testcontainers / docker-compose)?

---

## 2. Aturan Baku Anti-Rogue Utility (Larangan Utilitas Liar)

Salah satu penyebab terbesar *technical debt* dalam codebase agen AI adalah kecenderungan agen Coder membuat modul utilitas baru secara sembarangan ketika membutuhkan fungsi pembantu.

### Aturan Baku:
1. **DILARANG membuat file utilitas generik baru**:
   - Pembuatan file seperti `internal/utils/utils.go`, `src/helpers.js`, atau `app/common/functions.py` yang bersifat acak dilarang keras.
   - Jika suatu fungsi belum ada di repositori, fungsinya harus ditempatkan sedekat mungkin dengan domain yang membutuhkannya (*Package by Feature*), atau diajukan sebagai modul resmi dengan persetujuan Analis.
2. **Kewajiban Reuse Modul Eksisting**:
   - Jika repositori sudah memiliki `pkg/response` atau `pkg/crypto`, Coder **WAJIB** mengimpor package tersebut.
   - Analis wajib mencantumkan daftar package eksisting yang relevan pada `02-technical-spec.md` dan `03-task-list.md`.
3. **Konsekuensi Pelanggaran**:
   - Jika PR/diff memuat duplikasi fungsi (misal: fungsi formatting waktu atau parsing UUID yang dibuat manual padahal sudah ada utilitas bersama), Analis **WAJIB memberikan status REVISION**.

---

## 3. Kebijakan Tata Kelola Dependensi (Dependency Governance)

Setiap penambahan pustaka pihak ketiga (*third-party library*) membawa risiko keamanan rantai pasok (*supply chain security*), pembengkakan ukuran binary/bundle, dan potensi kerentanan CVE.

### Aturan Baku Dependensi:
1. **Prinsip Zero-New-Dependencies by Default**:
   - Tugas implementasi fitur baru harus semaksimal mungkin diselesaikan menggunakan standard library atau pustaka yang sudah terdaftar dalam `go.mod`, `package.json`, atau `pyproject.toml`.
2. **Mekanisme Pengecualian melalui ADR**:
   - Library pihak ketiga baru HANYA diizinkan jika:
     1. Masalah yang diselesaikan sangat kompleks (misal: implementasi enkripsi standar militer, parser format biner khusus).
     2. Analis telah mengevaluasi reputasi repo, lisensi (misal: MIT/Apache-2.0, bukan GPL copyleft), dan status pemeliharaan library tersebut.
     3. Keputusan tersebut dicatat secara formal dalam Architectural Decision Record (ADR) di `02-technical-spec.md`.
3. **Larangan untuk Coder**:
   - Coder dilarang menjalankan `go get <new-lib>`, `npm install <new-lib>`, atau `pip install <new-lib>` tanpa mandat eksplisit dari `02-technical-spec.md`.

---

## 4. Konvensi Penamaan & Idiom Bahasa

Analis wajib menegakkan kepatuhan terhadap standar idiom bahasa pemrograman yang digunakan oleh proyek:

### A. Go (Golang) Idioms:
- Return error sebagai nilai terakhir: `func DoSomething() (*Result, error)`.
- Jangan pernah abaikan error menggunakan blank identifier (`_ = doSomething()`).
- Nama interface singkat dan berorientasi kapabilitas (misal: `Reader`, `Writer`, `UserRepository`).
- Receiver name pendek dan konsisten (misal: `func (s *userService) FindByID(...)`, bukan `this` atau `self`).
- Hindari *naked returns* pada fungsi yang memiliki lebih dari 3 baris logika.

### B. TypeScript / Node.js Idioms:
- Strict typing tanpa penggunaan tipe `any` (gunakan `unknown` dengan type-guard jika dinamis).
- Penanganan error async selalu terbungkus `try/catch` atau monadic Result type.
- Immutabilitas data (prefer `const`, `readonly`, dan functional array methods).

### C. Python Idioms:
- Wajib menggunakan Type Hints (`typing` / `types`).
- Ikuti PEP-8 untuk penamaan (`snake_case` untuk fungsi/variabel, `PascalCase` untuk kelas).
- Hindari `except Exception:` tanpa re-raise atau logging terstruktur.
