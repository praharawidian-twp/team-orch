# 📋 Rubrik Evaluasi Code Review 5 Dimensi (Senior Tech Lead Gatekeeping)

Dokumen ini adalah standar evaluasi teknis yang wajib diterapkan oleh Analis / Senior Tech Lead saat meninjau hasil implementasi kode yang diajukan oleh Coder.

> **Prinsip Utama**: *"A green unit test only proves that the code does what the author wrote; it does NOT prove that the code is right, robust, secure, or aligned with enterprise architecture."*

---

## 1. Matriks 5 Dimensi Evaluasi

Setiap sub-task yang diajukan Coder wajib dinilai berdasarkan 5 pilar berikut. Setiap pilar memiliki skor maksimal 20 poin (Total: 100 poin). **Ambang batas persetujuan (Approval Threshold) adalah 90 poin, tanpa adanya pelanggaran kategori CRITICAL di pilar manapun.**

```
                           ┌────────────────────────┐
                           │   Overall Quality      │
                           │   Target: >= 90/100    │
                           └───────────┬────────────┘
         ┌──────────────┬──────────────┼──────────────┬──────────────┐
         ▼              ▼              ▼              ▼              ▼
   [Dimensi 1]    [Dimensi 2]    [Dimensi 3]    [Dimensi 4]    [Dimensi 5]
   Requirement    Boilerplate    Clean Code     Security &     Test Sharpness
   Fidelity &     Compliance &   & Concurrency  Resilience     & Mutation
   Scope Check    Shared Utils   Safety         Engineering    Mindset
   (Max 20 pts)   (Max 20 pts)   (Max 20 pts)   (Max 20 pts)   (Max 20 pts)
```

---

### Dimensi 1: Kesesuaian Kebutuhan & Acceptance Criteria (Max 20 Poin)
Memastikan kode benar-benar menyelesaikan masalah bisnis tanpa ada penyimpangan.

- **Checklist Evaluasi**:
  - [ ] Apakah seluruh Acceptance Criteria untuk sub-task ini pada `01-requirements.md` terpenuhi 100%?
  - [ ] Apakah ada indikasi *Over-Engineering* (membuat abstraksi rumit yang tidak diminta oleh spesifikasi)?
  - [ ] Apakah ada indikasi *Under-Engineering* (melewatkan validasi atau aturan bisnis yang disyaratkan)?
  - [ ] Apakah kontrak data (request/response DTO) persis sesuai dengan yang disepakati di `02-technical-spec.md`?
- **Pelanggaran Kritis (Auto-Reject)**:
  - Mengabaikan aturan bisnis inti.
  - Memodifikasi skema publik atau API endpoint tanpa dasar spesifikasi.

---

### Dimensi 2: Penguasaan & Kepatuhan Boilerplate (Max 20 Poin)
Memastikan kode menyatu harmonis dengan repositori eksisting dan tidak menciptakan anarki arsitektural.

- **Checklist Evaluasi**:
  - [ ] **Utilisasi Modul Eksisting**: Apakah fungsi-fungsi umum (misal: JSON formatting, HTTP response helper, database transaction runner, hashing, logger) menggunakan modul yang sudah ada di *boilerplate*?
  - [ ] **Anti-Rogue Utility**: Apakah Coder dilarang keras membuat file `utils.go`, `helpers.py`, atau fungsi redundan jika modul serupa telah ada di repo?
  - [ ] **Kepatuhan Dependency**: Apakah ada penambahan library baru di `go.mod` / `package.json`? Jika ada tanpa catatan ADR di `02-technical-spec.md`, wajib ditolak!
  - [ ] **Konvensi Penamaan & Struktur**: Apakah penempatan berkas, package naming, dan struktur direktori mengikuti konvensi arsitektur proyek (misal: Clean Architecture / Ports & Adapters)?
- **Pelanggaran Kritis (Auto-Reject)**:
  - Menulis ulang fungsi utility yang sudah ada di *shared package*.
  - Menginstal third-party library tanpa izin dan review ADR.

---

### Dimensi 3: Kualitas Rekayasa Kode, Clean Architecture & Concurrency Safety (Max 20 Poin)
Mengevaluasi kerapian, kemudahan pemeliharaan (*maintainability*), dan keandalan runtime tingkat sistem.

- **Checklist Evaluasi**:
  - [ ] **Separation of Concerns (SoC)**: Apakah lapisan Handler/Controller hanya menangani serialisasi/deserialisasi HTTP? Apakah business logic murni berada di Service/Usecase? Apakah layer Repository murni berinteraksi dengan storage?
  - [ ] **SOLID Principles**: Apakah antarmuka (*interface*) ringkas (*Interface Segregation*) dan ketergantungan dibalikkan (*Dependency Inversion*)?
  - [ ] **Concurrency & Race Conditions**:
    - Apakah ada akses bersama terhadap memory/state tanpa synchronization (`sync.Mutex`, atomics, atau channels)?
    - Apakah goroutines / background workers memiliki mekanisme terminasi yang pasti (mencegah *goroutine leak*)?
    - Apakah pengujian dijalankan dengan flag race detector (`go test -race` atau ekuivalen)?
  - [ ] **Resource Management**: Apakah koneksi database, file descriptor, HTTP response body (`resp.Body.Close()`) selalu ditutup secara terjamin (`defer`)?
- **Pelanggaran Kritis (Auto-Reject)**:
  - Terdeteksi potensi Data Race atau Memory/Goroutine Leak.
  - Kebocoran domain logic ke lapisan transport (misal: query SQL di dalam handler HTTP).

---

### Dimensi 4: Keamanan, DevSecOps & Ketahanan Sistem (Max 20 Poin)
Menjamin aplikasi tangguh menghadapi skenario kegagalan dan bebas celah keamanan.

- **Checklist Evaluasi**:
  - [ ] **Sanitasi Input & Parameterized Queries**: Apakah seluruh query database menggunakan prepared statements/parameter bindings (bebas SQL Injection)?
  - [ ] **Zero Hardcoded Secrets**: Tidak ada token, API key, password, connection string, atau URL internal yang ditulis langsung di kode (*hardcoded*). Wajib lewat environment variables atau config injection.
  - [ ] **Context Propagation & Timeout**: Apakah setiap operasi I/O (database, RPC, HTTP call) menerima dan meneruskan parameter `context.Context` dengan batas waktu (*timeout*) yang wajar?
  - [ ] **Error Wrapping & Sanitasi**:
    - Apakah error dibungkus dengan konteks informatif (misal: `fmt.Errorf("failed to fetch user %s: %w", id, err)`)?
    - Apakah pesan error yang dikembalikan ke klien eksternal disanitasi (tidak membocorkan raw SQL error, stack trace, atau path server)?
- **Pelanggaran Kritis (Auto-Reject)**:
  - Adanya potensi SQLi, XSS, SSRF, atau command injection.
  - Kredensial rahasia tertulis mentah di berkas kode.

---

### Dimensi 5: Ketajaman Pengujian & Pola Pikir Mutasi (Mutation Mindset) (Max 20 Poin)
Menguji seberapa tajam unit test dalam mendeteksi bug nyata, bukan sekadar mengejar angka *code coverage*.

- **Checklist Evaluasi**:
  - [ ] **Pengujian Nilai Batas (Boundary / Edge Cases)**: Apakah ada pengujian untuk input kosong, string whitespace, bilangan negatif, nilai maksimum integer, string sangat panjang, karakter khusus/Unicode?
  - [ ] **Negative & Failure Paths**: Apakah ada pengujian ketika database mengembalikan error, jaringan timeout, atau otentikasi gagal?
  - [ ] **Ketajaman Asersi (Assertion Sharpness)**: Apakah asersi memeriksa nilai spesifik dari field data yang dihasilkan (bukan sekadar `assert.NoError(t, err)` atau `assert.NotNil(t, res)`)?
  - [ ] **Pola Pikir Uji Mutasi (Mutation Mindset)**: *"Jika saya sengaja membalik logika `if x > 0` menjadi `if x >= 0` atau mengubah nilai default kembalian, apakah ada unit test yang akan GAGAL?"* Jika semua test tetap hijau saat logika diubah, maka unit test tersebut **TIDAK TAJAM**.
- **Pelanggaran Kritis (Auto-Reject)**:
  - Test palsu (*vacuous tests*) yang tidak memiliki asersi bermakna.
  - Hanya ada 1 pengujian *happy-path* tanpa ada pengujian skenario error sama sekali.

---

## 2. Format Pelaporan Review di `review-log.md`

Setiap kali Analis menyelesaikan review, Analis wajib mengisi entri review di `tasks/<project_id>/review-log.md` dengan format baku berikut:

```markdown
### Review: [TASK-XX] - [Judul Task]
- **Reviewer**: Analis (Senior Lead Engineer)
- **Waktu**: YYYY-MM-DD HH:MM:SS
- **Status Vonis**: APPROVED | NEEDS_REVISION | REJECTED

#### Skor Evaluasi 5 Dimensi:
1. Kesesuaian Requirement: [Skor/20] - [Catatan ringkas]
2. Kepatuhan Boilerplate: [Skor/20] - [Catatan ringkas]
3. Kualitas Kode & Concurrency: [Skor/20] - [Catatan ringkas]
4. Keamanan & Ketahanan: [Skor/20] - [Catatan ringkas]
5. Ketajaman Pengujian: [Skor/20] - [Catatan ringkas]
**Total Skor**: [Total]/100 (Threshold: 90)

#### Temuan & Arahan Bimbingan Teknis (Actionable Mentoring Feedback):
- **[File:Baris]** (misal: `internal/service/user.go:42`):
  - *Isu*: Query database dieksekusi tanpa meneruskan `ctx`.
  - *Dampak Teknis*: Jika koneksi HTTP dibatalkan oleh klien, query akan tetap menggantung di database (memicu penumpukan koneksi pool).
  - *Arahan Perbaikan*: Ganti `r.db.Query(...)` dengan `r.db.QueryContext(ctx, ...)`.

- **[File:Baris]** (misal: `internal/service/user_test.go:88`):
  - *Isu*: Test hanya menguji saat data ditemukan (`status 200`). Tidak ada test untuk kasus `sql.ErrNoRows`.
  - *Arahan Perbaikan*: Tambahkan sub-test `t.Run("UserNotFound_ReturnsErrNotFound", ...)` dan asersikan error code bernilai domain `ErrNotFound`.
```
