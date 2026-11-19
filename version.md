# Document Version & Release History

**Version Saat Ini** : `v1.2.0`  
**Tanggal Rilis**    : `2026-11-19`  
**Deskripsi Singkat** : Implementasi Konfigurasi Model Terpusat (`.agents/config/models.yaml`), resolusi dinamis `role -> model_tier -> models.yaml -> worker`, *auto-sync* model runtime dari `agy models` (termasuk dukungan otomatis generasi `gemini-4-neon-*`, `gemini-4-hydrogen-*`, `gemini-4-argon-*`, dan generasi masa depan), serta dukungan pendaftaran model kustom berbasis API Key (BYOK) tanpa menyimpan rahasia plaintext.

### List Fitur yang Berjalan di Versi Ini:
1. **Centralized Model Configuration (`.agents/config/models.yaml` v2.0.0)**: Satu sumber kebenaran (*Single Source of Truth*) untuk pemetaan tier (`low`, `medium`, `high`) ke model AI aktif, sehingga file role (`.yaml` & `.md`) hanya cukup mengatur `model_tier` tanpa *hardcode* versi model.
2. **Dynamic Runtime Sync (`team-orch model sync` & `herdr-orch model-config sync`)**: Membaca daftar model langsung dari `agy models`, memeringkat generasi dan sub-keluarga model terbaru secara otomatis (misal *auto-upgrade* tier `medium` ke `gemini-4-neon-high`), dan menerapkannya ke seluruh role serta pekerja berikutnya.
3. **Custom API Key (BYOK) Model Registry**: Penambahan dan penghapusan model berbasis API Key (`add-api` / `remove-api`) dengan referensi variabel lingkungan (`api_key_env`) yang patuh terhadap prinsip DevSecOps.
4. **Sequential Worker Model Switching (`herdr-orch` v0.5.0)**: Perpindahan pekerja lintas role (`--reset-on-role-change` / `team-orch next`) otomatis membaca tier role berikutnya dari `models.yaml` dan menerapkan `/new` + `/model <target>` secara dinamis.
5. **Agent Governance, 2-Domain Isolation, Tech Lead & QA Validation Gate**: Seluruh kapabilitas versi sebelumnya (`v1.1.0`, `v1.0.0`, `v0.4.0`) tetap berjalan penuh dengan 76 unit test lulus 100%.

---

## History Versi

### # version 1.2.0
- **Tanggal Edit**: `2026-11-19`
- **Deskripsi Singkat**: Rilis Konfigurasi Model Terpusat (`.agents/config/models.yaml`), sinkronisasi otomatis runtime `agy models` (`gemini-4-neon-*`), dan dukungan model API Key (BYOK).
- **Tabel Rincian Perubahan**:

| Berkas / Direktori | Jenis Perubahan | Alasan / Informasi Konteks | Impact ke Versi Sebelumnya | Kategori / Keamanan |
| :--- | :--- | :--- | :--- | :--- |
| `.agents/config/models.yaml` | Upgrade (`v2.0.0`) | Menjadi satu konfigurasi terpusat pemetaan tier (`low`, `medium`, `high`), katalog 23 `available_models` runtime, dan `api_key_models`. | Perubahan model cukup di 1 file tanpa mengedit ratusan file role `.yaml` / `.md`. | Architecture / Config |
| `cmd/comm_io.py` | Tambah Engine Model | Menambahkan parser/dumper YAML-JSON terpusat, `resolve_role_tier_and_model`, `sync_model_config_from_runtime`, `score_and_classify_model`, `set_tier_model_in_config`, dan `add/remove_api_key_model`. | Menyatukan logika resolusi & pemeringkatan generasi model di seluruh CLI (`team-orch` & `herdr-orch`). | Core Engine / DevSecOps |
| `cmd/herdr-orch` | Upgrade (`v0.5.0`) | Membaca tier dinamis dari `models.yaml`, deteksi TUI dinamis (`detect_model_from_snippet`), dukungan `--tier` & transisi role otomatis di `delegate_task`, serta subcommand `model-config`. | Pekerja berikutnya otomatis menerapkan `/model` sesuai tier role dari konfigurasi terpusat. | Orchestrator CLI |
| `cmd/team-orch` | Upgrade (`v1.2.0`) | Menghapus `ROLE_MODELS` hardcode, memakai `resolve_role_model()`, dan menambahkan subcommand `team-orch model <show\|sync\|set-tier\|add-api\|remove-api>`. | Seluruh katalog role, audit log, dan stage dispatch selalu selaras dengan `models.yaml`. | Team Orchestrator CLI |
| `.agents/roles/*.md` & `templates/agent-role-template.yaml` | Modifikasi | Menghapus hardcode nama model spesifik dan merujuk penuh ke `model_tier` (`low`/`medium`/`high`) via `.agents/config/models.yaml`. | Menghilangkan beban perawatan manual pada definisi role saat ada rilis model baru. | Role Configuration |
| `.agents/skills/herdr-orchestrator/SKILL.md` & `installer/install.sh` | Modifikasi | Memperbarui dokumentasi CLI `model-config` / `team-orch model` dan menyalin `.agents/config/` serta `cmd/comm_io.py` saat instalasi global. | Memastikan instalasi bersih otomatis menyertakan engine & konfigurasi model terpusat. | Installer / Docs |
| `tests/test_centralized_model_config.py` | Berkas Baru | Menambahkan 6 unit test (resolusi tier, `set-tier`, ranking generasi baru, registrasi BYOK API key, transisi pekerja beruntun, dan validasi update `gemini-4-neon`). | Verifikasi deterministik 76/76 unit test lulus tanpa regresi. | Automated Testing |

---

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