# 🤖 Extensible Autonomous Multi-Agent Orchestration Framework

Sebuah *universal engine* untuk merancang, mengorkestrasi, dan menjalankan **tim agen AI otonom** di berbagai domain rekayasa (Software Engineering, Game Studio, Cyber Security, QA Automation, Data Pipelines, dsb.) berbasis **Antigravity** dan **Herdr** multi-pane orchestration.

Framework ini dirancang agar siapapun dapat **membuat peran agen baru**, **menentukan basis pengetahuan (SOP/RBAC)**, dan **merangkai alur kerja (workflow)** khusus sesuai kebutuhan bisnis dengan disiplin tinggi, efisiensi kuota token cerdas (*adaptive model auto-switching*), dan perlindungan kendali manusia (*Human-in-the-Loop & UAT Sign-off*).

---

## 📋 Daftar Isi
1. [Konsep Inti: 3 Pilar Modular Framework](#-konsep-inti-3-pilar-modular-framework)
2. [Dual Execution Topology (Fleet vs Silent Mode)](#-dual-execution-topology-fleet-vs-silent-mode)
3. [Katalog Preset Bawaan (Starter Kits)](#-katalog-preset-bawaan-starter-kits)
4. [Dua Cara Penggunaan (User Experience)](#-dua-cara-penggunaan-user-experience)
   - [Metode A: Delegasi Percakapan ke Asisten AI (Rekomendasi)](#metode-a-delegasi-percakapan-ke-asisten-ai-rekomendasi)
   - [Metode B: Kontrol Mandiri via CLI `team-orch`](#metode-b-kontrol-mandiri-via-cli-team-orch)
5. [Instalasi Cepat (1-Klik Multi-Device)](#-instalasi-cepat-1-klik-multi-device)
6. [Struktur Direktori Framework](#-struktur-direktori-framework)
7. [Aturan Rekayasa & Standar Keamanan](#-aturan-rekayasa--standar-keamanan)
8. [Referensi Perintah Lengkap CLI](#-referensi-perintah-lengkap-cli)

---

## 🌟 Konsep Inti: 3 Pilar Modular Framework

Framework ini dibangun di atas 3 pilar modular yang dapat dikombinasikan secara bebas:

```
                  ┌──────────────────────────────────────────────┐
                  │          1. MODULAR AGENT ROLES              │
                  │   Definisi Persona, Model AI Tier & Tugas    │
                  │       (Game Designer, Security, Coder)       │
                  └──────────────────────┬───────────────────────┘
                                         │
                  ┌──────────────────────▼───────────────────────┐
                  │       2. SCOPED KNOWLEDGE BASE & RBAC        │
                  │   Pedoman, SOP & Hak Akses Berbasis Peran    │
                  │    (Clean Code, GDD Standard, API Rules)     │
                  └──────────────────────┬───────────────────────┘
                                         │
                  ┌──────────────────────▼───────────────────────┐
                  │        3. WORKFLOW STATE MACHINE             │
                  │  Rangkaian Tahapan Kerja & Gerbang Evaluasi  │
                  │    (Artifact Gates -> Final UAT Sign-off)    │
                  └──────────────────────────────────────────────┘
```

### 1. Modular Agent Roles (`team-orch role`)
Bebas mendefinisikan peran agen spesialis apa pun dengan model AI tier yang tepat:
* **Tier Low (`gemini-3.8-flash-low`)**: Dokumenter, syntax checker, formatter, status tracker (hemat kuota 90%).
* **Tier Medium (`gemini-3.8-flash-high`)**: Developer, bug fixer, QA tester, logic builder.
* **Tier High (`gemini-3.1-pro-high`)**: Tech Lead/Analis, Game Designer, Security Auditor, System Architect.

### 2. Scoped Knowledge Base & RBAC (`team-orch knowledge`)
* **Anti-Prompt Stuffing**: Agen tidak dijejali semua panduan di prompt awal. Materi teknis disimpan terstruktur dan diakses sesuai kebutuhan (*pull-on-demand*).
* **Role-Based Access Control (RBAC)**: Dokumen knowledge hanya dapat dibaca oleh agen yang berwenang (misal: aturan database hanya untuk `coder` dan `analyst`).
* **Human-Governed Knowledge**: Agen hanya dapat mengusulkan draf (`draft`). Draf baru resmi terbit setelah disetujui manusia (`approve`).

### 3. Arsitektur 2 Domain & Multi-Domain Isolation (`team-orch domain`)
Framework memisahkan secara tegas antara **Base Domain** (publik, *Day-1 Employee / Zero Institutional Knowledge*) dan **Specific Domain Packs** (aset privat organisasi seperti nama aplikasi, domain internal, template berlogo, pejabat, dan boilerplate khusus — disimpan di `.agents/domains/` yang otomatis di-`gitignore` serta `~/.gemini/team-orch/domains/` untuk penggunaan lintas-proyek):
* **`base` Domain Default**: Siap pakai di proyek mana pun tanpa bias institusional.
* **Domain Switching & Project Binding Guard**: Setiap proyek mengunci `domain_id`-nya di `project.yaml`. `team-orch next` akan memblokir eksekusi apabila domain aktif berbeda dengan domain proyek guna mencegah konteks bercampur (*anti-hallucination guardrail*).
* **Meta-Studio Discovery & Upgrade (`.agents/meta-studio/`)**: Mekanisme bawaan untuk meriset, merancang, dan meng-upgrade role, skill, maupun domain pack baru di instalasi mana pun.

### 3. Workflow State Machine & Artifact Gates (`team-orch workflow`)
* Menghubungkan agen-agen ke dalam tahapan sekuensial dengan kontrak berkas yang jelas (*input & output artifacts*).
* **Artifact Barrier**: Agen di tahap selanjutnya tidak akan dijalankan sebelum artefak dari tahap sebelumnya benar-benar valid di disk (mencegah halusinasi atau lompat tahapan).
* **Framework Final User Sign-off Gate (UAT)**: Agen pekerja DILARANG mengarsipkan proyek secara sepihak. Setelah seluruh tahapan agen selesai, proyek otomatis menunggu peninjauan dan persetujuan akhir Pengguna di Control Room via `team-orch complete`.

---

## 🔀 Dual Execution Topology (Fleet vs Silent Mode)

Framework mendukung 2 mode eksekusi terminal di Herdr:

| Mode Eksekusi | Opsi Perintah | Karakteristik | Cocok Untuk |
|---|---|---|---|
| **🌐 FLEET MODE (Default)** | *(tanpa flag)* | **1 Agen = 1 Dedicated Terminal Pane**.<br>Menghadirkan dinamika visual transparan di mana agen saling berdialog dan berkolaborasi secara real-time di layar. | Demo tim, pemantauan visual langsung, audit kerja transparan. |
| **🔕 SILENT MODE** | `--silent` | **Single Shared Worker Pane**.<br>Seluruh agen pekerja dieksekusi bergantian secara sekuensial di 1 jendela terminal latar belakang tanpa membelah layar. | Menghemat jendela terminal, pengerjaan senyap di background, perangkat dengan layar terbatas. |

---

## 📦 Katalog Preset Bawaan (Starter Kits)

Framework menyediakan preset bawaan yang langsung siap digunakan atau dijadikan rujukan:

1. **`standard-software-house` (5-Tier SDLC)**:
   * Alur: PM (Scope) $\rightarrow$ Analis (Tech Spec) $\rightarrow$ Coder (TDD Build) $\rightarrow$ Analis (Quality Review) $\rightarrow$ Dokumenter (Docs) $\rightarrow$ UAT Pengguna.
2. **`rapid-prototype` (Fast MVP)**:
   * Alur: PM (Scope) $\rightarrow$ Coder (Direct Build) $\rightarrow$ Dokumenter (Quick Notes) $\rightarrow$ UAT Pengguna.
3. **`bug-fix-squad` (Hotfix / Incident)**:
   * Alur: Analis (Root Cause Analysis) $\rightarrow$ Coder (Patch & Regression Test) $\rightarrow$ Analis (Verification) $\rightarrow$ UAT Pengguna.
4. **Custom Domain Workflows**:
   * Pengguna bebas membuat alur baru seperti `game-studio-pipeline`, `devsecops-audit`, atau `data-pipeline` via `team-orch workflow create`.

---

## 👥 Dua Cara Penggunaan (User Experience)

### Metode A: Delegasi Percakapan ke Asisten AI (Rekomendasi)
Jika Anda menggunakan Antigravity IDE atau `agy` CLI, Anda tidak perlu menghafal dan mengetik perintah CLI satu per satu. **Cukup beri instruksi manusia ke agen AI Anda**:

> *"Tolong buatkan agen Game Designer ber-tier high, buatkan draf knowledge standar GDD, dan rangkai workflow game-studio-pipeline untuk membuat game indie."*

Asisten AI Anda akan langsung mengeksekusi perintah pembuatan berkas, menyusun draf knowledge, dan merangkai alur kerja untuk Anda secara instan di workspace!

---

### Metode B: Kontrol Mandiri via CLI `team-orch`

Jika Anda lebih menyukai kendali penuh lewat terminal, gunakan perintah CLI berikut:

#### 1. Membuat Role Agen Baru:
```bash
team-orch role create game-designer \
  --title "Game Designer & Mechanics Architect" \
  --tier high \
  --desc "Merancang gameplay loop, sistem mekanika, balancing ekonomi, dan menyusun GDD"
```

#### 2. Membuat & Mengesahkan Knowledge Baru:
```bash
# 1. Siapkan draf materi
team-orch knowledge draft gdd-standard --title "Standar Game Design Document"

# 2. (Edit isi draf di .agents/knowledge/.drafts/gdd-standard.md)

# 3. Sahkan draf dan tetapkan izin akses (RBAC)
team-orch knowledge approve gdd-standard --access game-designer,coder --category gamedev
```

#### 3. Membuat Cetak Biru Workflow Baru:
```bash
team-orch workflow create game-studio-pipeline \
  --name "Indie Game Studio Pipeline" \
  --desc "Alur: Game Designer (GDD) -> Coder (Prototype) -> Game Designer (Audit) -> Dokumenter"
```

#### 4. Menjalankan Proyek:
```bash
# Inisialisasi proyek baru dengan workflow kustom
team-orch init retro-platformer --workflow game-studio-pipeline [--silent]

# Jalankan tahapan kerja
team-orch next retro-platformer

# Pantau status proyek
team-orch status retro-platformer

# Tinjau hasil kerja (UAT) dan arsipkan setelah tuntas
team-orch complete retro-platformer
```

---

## ⚡ Instalasi Cepat (1-Klik Multi-Device)

### 1-Prompt Setup via Agen AI (Laptop/Komputer Baru)
Kirim prompt berikut ke agen AI di komputer baru Anda:

> *"Tolong terapkan dan pasang autonomous multi-agent framework dari repositori ini: https://github.com/praharawidian-twp/team-orch"*

Agen AI akan secara otomatis meng-clone repositori, menjalankan instalasi wizard, mengonfigurasi binary ke PATH, dan memverifikasi kesiapan lingkungan.

### Setup Manual via Terminal:
```bash
git clone https://github.com/praharawidian-twp/team-orch.git team-orch
cd team-orch
./cmd/team-orch setup
source cmd/env.sh
```

### Bundled Skills Bawaan (Saat Instalasi Pertama):
Framework ini membawa paket skill siap pakai di `.agents/skills/` (disalin ke `~/.gemini/team-orch/skills/` saat instalasi):
- **Governance & Orchestration**: `agent-governance`, `devsecops-guardian`, `herdr-orchestrator`, `team-orchestrator`
- **Engineering & QA**: `tech-lead-analyst`, `qa-test-specialist`, `ui-evidence-capture`, `office-document-suite`
- **Everything Claude Code (ECC) Bundle**: `ecc`, `ecc-guide`, `ecc-recipes` (verification loops, TDD, context budget, strategic compact)
- **Meta & Discovery**: `.agents/meta-studio/` (`agent-builder`, blueprint role/skill upgrade)

---

## 📂 Struktur Direktori Framework

```text
agent-framework/
├── .agents/
│   ├── knowledge/                # 📚 Scoped Knowledge Base & Access Control (RBAC)
│   │   ├── registry.yaml         # Master Access Control List (ACL)
│   │   ├── topics/               # Dokumen panduan aktif berbasis topik
│   │   └── drafts/               # Tempat draf knowledge menunggu persetujuan
│   ├── roles/                    # 🎭 Definisi persona dan sistem prompt agen
│   │   ├── project-manager.yaml
│   │   ├── analyst.yaml
│   │   ├── coder.yaml
│   │   ├── documenter.yaml
│   │   └── <custom-role>.yaml    # Peran agen baru buatan pengguna
│   ├── workflows/                # 🔄 Cetak biru alur kerja (State Machine DAG)
│   │   ├── standard-software-house.yaml
│   │   ├── rapid-prototype.yaml
│   │   ├── bug-fix-squad.yaml
│   │   └── <custom-workflow>.yaml
│   ├── tasks/                    # 📁 Task Scratchpad & Isolasi Proyek
│   │   ├── active/               # Proyek yang sedang berjalan
│   │   └── completed/            # Arsip proyek yang telah disetujui Pengguna (UAT)
│   ├── bus/                      # 📨 Inter-Agent Message Bus & Event Queue
│   └── templates/                # Template dokumen baku & starter blueprints
├── cmd/                          # 🛠️ Tools & Utilitas Mandiri (Self-Contained Executables)
│   ├── team-orch                 # Core Orchestrator CLI
│   ├── herdr-orch                # Herdr Multi-Pane Engine & Adaptive Model Switcher
│   ├── agy-auto                  # Wrapper Autonomous Antigravity Runner
│   └── env.sh                    # Shell helper untuk menambahkan ./cmd ke $PATH
├── installer/                    # Skrip install, verify, dan clean uninstall
├── CONTRIBUTING.md               # Standar resmi Git Branching, Tagging & Conventional Commits
├── AGENTS.md                     # Aturan baku orkestrasi & batasan agen
├── GEMINI.md                     # Aturan global workspace Antigravity
└── README.md                     # Dokumentasi utama framework
```

---

## 🛡️ Aturan Rekayasa & Standar Keamanan

1. **Strict Git Read-Only Policy**: Seluruh agen AI secara mutlak **DILARANG** menjalankan perintah pemutasi Git (`git add`, `git commit`, `git push`, dll). Hanya Pengguna/Human yang berwenang melakukan mutasi Git.
2. **Deterministic 0-Token Preflight (`team-orch preflight <id>`)**: Memvalidasi sintaks kode (Python AST, JSON, Node syntax) secara deterministik lokal sebelum diajukan ke tahap review untuk mencegah pemborosan token model.
3. **Circuit Breaker Guardrail**: Menghentikan perdebatan atau revisi berulang tanpa akhir secara otomatis (maksimal 2 putaran tanya-jawab dan 3 penolakan revisi) demi mencegah token burn.
4. **Context Budgeting (`team-orch contract <id> --role <role>`)**: Memangkas penggunaan context window 60-75% dengan hanya mengekstrak artefak yang relevan bagi peran yang sedang bertugas.

---

## 🛠️ Referensi Perintah Lengkap CLI

```bash
# === MANAJEMEN ROLE AGEN ===
team-orch role list                                  # Daftar seluruh peran agen terdaftar
team-orch role create <id> --title <t> --tier <low|medium|high>  # Buat peran agen baru

# === MANAJEMEN KNOWLEDGE BASE (RBAC) ===
team-orch knowledge list [--role <role>]             # Katalog materi sesuai izin akses
team-orch knowledge read <topic_id> [--role <role>]  # Baca dokumen panduan resmi
team-orch knowledge draft <topic_id> --title <t>     # Buat draf panduan baru
team-orch knowledge approve <draft_id> --access <a>  # Sahkan draf menjadi dokumen aktif

# === MANAJEMEN WORKFLOW ===
team-orch workflow list                              # Katalog cetak biru alur kerja
team-orch workflow show <workflow_id>                # Tampilkan diagram tahapan workflow
team-orch workflow create <id> --name <n>            # Buat alur kerja kustom baru

# === MANAJEMEN DOMAIN (2-DOMAIN ISOLATION & SWITCHING) ===
team-orch domain list                                # Daftar domain (base + specific domain packs)
team-orch domain current                             # Cek active domain & context binding saat ini
team-orch domain init <id> --org <org>               # Buat skeleton Specific Domain Pack baru
team-orch domain use <id|base>                       # Switch active domain pack global
team-orch domain bind <project_id> <id|base>         # Ikat proyek ke domain spesifik
team-orch domain validate [<id>]                     # Audit kelengkapan domain pack
team-orch domain sync <id>                           # Sinkronkan domain pack lokal <-> ~/.gemini/team-orch/domains/

# === EKSEKUSI PROYEK & TAHAPAN ===
team-orch init <project_id> [--workflow <id>] [--domain <id>] [--silent]  # Mulai proyek (Fleet / Silent)
team-orch next <project_id> [--silent] [--force]          # Jalankan tahapan berikutnya
team-orch approve <project_id>                            # Setujui dokumen kebutuhan awal
team-orch status [project_id]                             # Pantau dasbor Mission Control
team-orch complete <project_id>                           # Verifikasi UAT & arsipkan proyek

# === AUDIT & TELEMETRI ===
team-orch audit <project_id> [-n 10]                      # Riwayat transparansi audit trail
team-orch log <id> -r <role> -e <event> -d "<deskripsi>"  # Catat aktivitas ke audit trail
team-orch resolve <project_id>                            # Buka kunci Circuit Breaker
```

---

## 📄 Lisensi
Framework ini dirilis di bawah [Lisensi MIT](LICENSE). Bebas diadaptasi, diperluas, dan digunakan untuk kebutuhan tim engineering atau studio AI Anda.
