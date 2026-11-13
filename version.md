# Document Version & Release History

**Version Saat Ini** : `v0.4.0`  
**Tanggal Rilis**    : `2026-10-09`  
**Deskripsi Singkat** : Rilis besar arsitektur enterprise multi-agent: penegakan tata kelola agen (*Agent Governance & Stirring Matrix*), sistem pertahanan kredensial (*DevSecOps Guardian*), standar kepemimpinan teknis Analis (*Tech Lead Analyst Protocol*), guardrail anti-asumsi (*Discovery-First Protocol*), serta otomatisasi pipa eksekusi (*Autonomous Pipeline Runner*).

### List Fitur yang Berjalan di Versi Ini:
1. **Agent Governance & Stirring Matrix**: Pembatasan hak akses baca/tulis/perbarui agen berdasarkan zona direktori, kedaulatan mutlak manusia pada Knowledge Base (*Zero Self-Approval*), dan kesetaraan konteks manusia (*Human-Context Parity*).
2. **DevSecOps Guardian & Secret Sanitizer**: Intersepsi otomatis pada PreToolUse Hook untuk memblokir pembacaan file sensitif (`.env`, `~/.ssh/*`, `~/.aws/*`, `~/.kube/config`) dan pencegahan eksekusi perintah dump environment (`env`, `export`, dll).
3. **Tech Lead Analyst Quality Protocol**: Standar peran Analis sebagai Senior Lead Engineer (Dekomposisi C4 Model, template ADR resmi, audit kepatuhan boilerplate, rubrik evaluasi review 5 dimensi *beyond green tests*, serta skrip validator `verify-spec.py`).
4. **Anti-Assumption & Discovery-First Protocol**: PreToolUse Guardrail fisik yang menolak penyusunan PRD (`01-requirements.md`) tanpa transkrip wawancara kebutuhan langsung (*Discovery Log*) dan referensi basis boilerplate resmi.
5. **Standard 3-Step Project Inception Protocol**: Alur interaktif terstruktur bertahap (Pemilihan Workflow $\rightarrow$ Pemilihan Topologi Fleet/Silent $\rightarrow$ Discovery Wawancara).
6. **Autonomous Pipeline Runner (`team-orch auto`)**: Daemon mandiri untuk memantau, memverifikasi kelengkapan artefak, dan mengalirkan transisi tahap secara otonom hingga batas gerbang UAT.
7. **Knowledge Revocation & Staging Gate**: Sub-perintah `team-orch knowledge reject/revoke` untuk mencabut atau mengembalikan topik knowledge ke draf staging jika tidak disetujui manusia.
8. **DevOps & Infrastructure Role**: Penambahan peran `devops` dan workflow baru `enterprise-sdlc-devops` (6 tahap: PM $\rightarrow$ Analis $\rightarrow$ Coder $\rightarrow$ Analis $\rightarrow$ DevOps $\rightarrow$ Dokumenter).
9. **Dynamic Stage Override & Revision Rollback (`--stage`)**: Kemampuan melompat atau mengembalikan pipa ke tahap sebelumnya (misal: pengembalian ke Coder saat terdapat revisi dari Pengguna) dengan opsi `--stage <id_or_index>`.

---

## History Versi

### # version 0.4.0
- **Tanggal Edit**: `2026-10-09`
- **Deskripsi Singkat**: Implementasi sistem keamanan berlapis, protokol tata kelola agen, upgrade standar Analis/Tech Lead, dan hook penjaga kedaulatan manusia.
- **Tabel Rincian Perubahan**:

| Berkas / Direktori | Jenis Perubahan | Alasan / Informasi Konteks | Impact ke Versi Sebelumnya | Kategori / Keamanan |
| :--- | :--- | :--- | :--- | :--- |
| `.agents/hooks/knowledge-guardrail.py` | Tambah & Perbaiki | Menjaga folder `topics/` & `registry.yaml` agar hanya dapat diubah oleh manusia, serta mendukung pengecekan diff utuh pada `replace_file_content`. | Mencegah modifikasi sepihak knowledge base oleh agen AI. | Security / Strict Hook |
| `.agents/hooks/anti-assumption-guardrail.py` | Berkas Baru | PreToolUse Hook yang mencegat penulisan `01-requirements.md` jika tidak memuat Discovery Log dan Boilerplate Reference. | Menghilangkan halusinasi spesifikasi sejak fase awal project inception. | Governance / Anti-Hallucination |
| `.agents/hooks/secret-sanitizer.py` | Berkas Baru | PreToolUse Hook untuk memblokir pembacaan file kredensial dan dump environment variables. | Menjamin 100% keamanan credential server dan confidential token host. | Security / Zero-Leak |
| `.agents/hooks.json` | Modifikasi | Perbaikan path skrip hook menjadi format relatif `hooks/*.py`. | Memperbaiki pemanggilan hook agar kompatibel dengan working dir runner `.agents/`. | Framework Core |
| `.agents/skills/agent-governance/` | Skill Baru | Modul tata kelola enterprise: stirring matrix, komunikasi file-driven via `task-handoff.md`, dan human parity. | Menjadi fondasi aturan perilaku seluruh peran agen di workspace. | Skill / Governance |
| `.agents/skills/devsecops-guardian/` | Skill Baru | Modul DevSecOps: safe actions (plan-first), non-root container benchmark, dan skrip `scan-secrets.py`. | Melindungi integritas infrastruktur dan supply-chain security. | Skill / DevSecOps |
| `.agents/skills/tech-lead-analyst/` | Skill Baru | Modul Tech Lead: rubrik review 5 dimensi, checklist kepatuhan boilerplate, template ADR, dan validator `verify-spec.py`. | Meningkatkan standar review Analis dari sekadar tes hijau ke rekayasa arsitektur handal. | Skill / Quality Assurance |
| `.agents/roles/analyst.yaml` & `.md` | Modifikasi | Mendaftarkan skill `tech-lead-analyst` dan `agent-governance`, serta mengunci tier model ke `gemini-3.1-pro-high`. | Memastikan Analis memiliki kapasitas penalaran tertinggi saat merancang arsitektur. | Role Configuration |
| `.agents/roles/devops.yaml` & `.md` | Berkas Baru | Definisi peran resmi untuk DevOps & Infrastructure Engineer. | Memungkinkan spesialisasi otomatisasi environment, container, dan CI/CD. | Role Configuration |
| `.agents/workflows/enterprise-sdlc-devops.yaml` | Berkas Baru | Blueprint alur kerja 6 tahap lengkap dengan gatekeeper Analis dan deployment DevOps. | Menambah opsi alur kerja berskala enterprise. | Workflow Blueprint |
| `cmd/team-orch` | Modifikasi | Penambahan perintah `team-orch auto`, `team-orch knowledge reject/revoke`, dan opsi `--stage` untuk navigasi/rollback tahap revisi. | Eksekusi pipa tim lebih otonom, kontrol penolakan draf lebih presisi, dan penugasan ulang revisi instan. | CLI Enhancement |
| `AGENTS.md` & `GEMINI.md` | Modifikasi | Penegasan aturan kernel Rule 10 (3-Step Inception), Rule 11 (Ad-Hoc Invocation), dan Rule 12 (Governance). | Sinkronisasi aturan sistem global dengan sesi Herdr orchestrator. | Kernel Rules |

---

### # version 0.3.0
- **Tanggal Edit**: `2026-09-23`
- **Deskripsi Singkat**: Rilis topologi Silent Mode, gerbang persetujuan akhir Pengguna (UAT Sign-off Gate), dan arsitektur agen terbuka.
- **Tabel Rincian Perubahan**:

| Berkas / Direktori | Jenis Perubahan | Alasan / Informasi Konteks | Impact ke Versi Sebelumnya | Kategori / Keamanan |
| :--- | :--- | :--- | :--- | :--- |
| `cmd/team-orch` | Fitur Baru | Penambahan opsi `--mode silent` / `--silent` untuk menjalankan seluruh pekerja di 1 single worker pane. | Pengguna dapat memilih antara visual multi-pane (Fleet) atau latar belakang senyap (Silent). | Architecture / Usability |
| `.agents/workflows/*.yaml` | Modifikasi | Pemberlakuan aturan framework invariant: seluruh alur kerja diakhiri Final UAT Gate oleh Pengguna. | Agen pekerja dilarang menyelesaikan proyek secara sepihak (`team-orch complete` dibatasi ke manusia). | Governance / Control |
| `cmd/team-orch` | Peningkatan | Pemisahan status stage index dan lock guardrail untuk mencegah multi-process race conditions. | Menjaga stabilitas manifest state saat agen worker beroperasi bersamaan. | Core Stability |

---

### # version 0.2.1
- **Tanggal Edit**: `2026-09-14`
- **Deskripsi Singkat**: Pengenalan sistem Scoped Knowledge Base (RBAC), deterministic preflight checks, dan context budgeting.
- **Tabel Rincian Perubahan**:

| Berkas / Direktori | Jenis Perubahan | Alasan / Informasi Konteks | Impact ke Versi Sebelumnya | Kategori / Keamanan |
| :--- | :--- | :--- | :--- | :--- |
| `.agents/knowledge/` | Fitur Baru | Pembagian topik knowledge berbasis role (`--role`) dan kategori. | Agen hanya memuat materi yang relevan dengan tugasnya, menghemat token konteks secara masif. | Optimization / Tokens |
| `cmd/team-orch` | Fitur Baru | Penambahan sub-perintah `team-orch preflight` dan validasi dependency lingkungan sebelum mulai. | Kegagalan sistem terdeteksi di awal sebelum memicu pembakaran kuota API agen. | Reliability |
| `cmd/team-orch` | Fitur Baru | Pemadatan event bus (`bus compaction`) dan rotasi event bus log otomatis. | Mencegah file bus log membengkak pada proyek jangka panjang. | Maintenance |

---

### # version 0.2.0
- **Tanggal Edit**: `2026-09-11`
- **Deskripsi Singkat**: Integrasi orkestrasi terminal multi-pane Herdr (`HERDR_ENV=1`) dan mekanisme Adaptive Model Auto-Switching.
- **Tabel Rincian Perubahan**:

| Berkas / Direktori | Jenis Perubahan | Alasan / Informasi Konteks | Impact ke Versi Sebelumnya | Kategori / Keamanan |
| :--- | :--- | :--- | :--- | :--- |
| `cmd/herdr-orch` | Berkas Baru | CLI utilitas untuk discovery status pane, delegasi prompt lintas terminal, dan rate-limit check. | Memungkinkan Control Room membagi tugas ke sibling terminal panes di Herdr. | Multi-Pane Fleet |
| `cmd/agy-auto` | Berkas Baru | Wrapper otomatisasi peluncuran Antigravity CLI dengan parameter headless `--dangerously-skip-permissions`. | Mengurangi intervensi manual klik konfirmasi untuk agen pekerja di background. | Automation |
| `AGENTS.md` | Aturan Baru | Penambahan protokol Adaptive Model Auto-Switching berdasarkan kompleksitas tugas (Low, Medium, High). | Menghemat hingga 90% kuota token pada tugas-tugas operasional ringan. | Quota Economy |

---

## Rekomendasi Penyesuaian Lanjutan (Enhancement Suggestions)

Berikut beberapa bagian tambahan yang direkomendasikan untuk melengkapi dokumentasi versi proyek di masa mendatang:

1. **Panduan Migrasi Antar-Versi (Migration & Upgrade Guide)**:
   - Menyediakan langkah-langkah praktis bagi pengguna saat beralih versi (contoh: verifikasi `hooks.json`, penyiapan environment `HERDR_ENV`, dan registrasi global skill ke `~/.gemini/config/skills/`).
2. **Matriks Kepatuhan Keamanan (DevSecOps & Compliance Posture)**:
   - Mencantumkan status proteksi terhadap OWASP Agentic Top 10 (AST10), zero hardcoded secrets, dan sanitasi input database/shell.
3. **Pemberitahuan Deprekasi (Deprecation Notices)**:
   - Memberikan peringatan dini jika terdapat perintah CLI atau format manifest yang akan dihentikan pada rilis berikutnya.