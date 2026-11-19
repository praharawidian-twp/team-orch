# Panduan Kontribusi & Standar Git (Branching, Tagging & Commits)

Dokumen ini mendefinisikan standar manajemen Git resmi untuk repositori `agent` agar rapi, konsisten, dan mematuhi konvensi open-source modern (GitHub Flow + SemVer).

---

## 1. Strategi Percabangan (Branching Strategy: GitHub Flow)

Repositori ini menggunakan model **GitHub Flow** yang sederhana, stabil, dan ramah kolaborasi:

```
[main] ──────────────────────────●──────────────●──────────────● (v0.3.0)
         \                      /              /
          └── [feat/silent-mode] ──┘            /
                     \                         /
                      └── [fix/tab-bleed-guard] ──┘
```

### Aturan Baku Branch:
1. **`main` (Trunk / Default Branch)**:
   - Selalu menjadi *single source of truth* untuk kode stabil yang siap digunakan.
   - Semua rilis resmi ditandai (*tagged*) langsung pada commit di branch `main`.
   - Dilarang membuat branch yang dinamai sama dengan versi rilis (misal: jangan buat branch bernama `v0.3.0` untuk mencegah konflik dengan Git Tag).
2. **Feature & Bugfix Branches (Sementara / Ephemeral)**:
   - Dibuat dari `main` saat mengerjakan fitur, perbaikan bug, atau dokumentasi.
   - Setelah pekerjaan selesai, diuji, dan di-merge ke `main`, branch ini **wajib dihapus** (*delete after merge*) untuk menjaga repositori tetap bersih.

### Konvensi Penamaan Branch:
| Kategori | Format Penamaan | Contoh |
|---|---|---|
| Fitur Baru | `feat/<deskripsi-singkat>` | `feat/silent-mode`, `feat/custom-agents` |
| Perbaikan Bug | `fix/<deskripsi-singkat>` | `fix/tab-bleed`, `fix/self-delegation` |
| Dokumentasi | `docs/<topik>` | `docs/workflow-guide`, `docs/contributing` |
| Refactoring | `refactor/<modul>` | `refactor/bus-compaction` |
| Eksperimen / Scratch | `exp/<nama-ide>` | `exp/wasm-runtime` |

---

## 2. Strategi Tagging & Rilis (Semantic Versioning 2.0.0)

Rilis dan penomoran versi dikelola secara eksklusif menggunakan **Git Tag** (bukan branch).

### Format Tag: `vMAJOR.MINOR.PATCH`
* **`MAJOR`** (cth: `v1.0.0`): Perubahan arsitektur besar atau perubahan yang tidak kompatibel dengan versi sebelumnya (*breaking changes*).
* **`MINOR`** (cth: `v0.3.0`): Penambahan fitur baru yang *backward-compatible* (misal: Silent Mode, Framework Final User Sign-off Gate, Open Agent Architecture).
* **`PATCH`** (cth: `v0.3.1`): Perbaikan bug (*bugfix*) atau penyesuaian minor yang *backward-compatible*.

### Standar Pembuatan Tag (Wajib Annotated Tag):
Selalu gunakan **Annotated Tag** (`-a`) dengan pesan deskriptif:
```bash
# Format perintah
git tag -a v<VERSION> -m "Release v<VERSION>: <Ringkasan Fitur Utama>"

# Contoh rilis v0.3.0
git tag -a v0.3.0 -m "Release v0.3.0: Silent Mode, UAT Final Sign-off, and Modular Agent System"
```
> **Catatan**: Git Tag ini yang akan dibaca oleh GitHub Releases untuk mempublikasikan paket rilis resmi dan arsip tar/zip. Pengguna dapat meng-clone versi tertentu dengan perintah standar:  
> `git clone -b v1.2.0 https://github.com/praharawidian-twp/team-orch.git`

---

## 3. Konvensi Pesan Komit (Conventional Commits)

Setiap pesan komit harus jelas, deskriptif, dan mengikuti format [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <deskripsi singkat dalam bentuk imperatif / masa kini>

[body / penjelasan detail opsional]
```

### Tipe Komit (`<type>`):
* `feat`: Fitur atau fungsionalitas baru.
* `fix`: Perbaikan bug atau penanganan error.
* `docs`: Pembaruan dokumentasi (README, panduan, docstrings).
* `refactor`: Perubahan struktur kode tanpa mengubah fungsi bisnis atau API.
* `test`: Penambahan skenario uji atau pembaruan test harness.
* `chore`: Tugas pemeliharaan, upgrade dependensi, penyesuaian rilis.

*Contoh:*
```bash
git commit -m "feat(core): release v0.3.0 with silent mode topology, framework final user sign-off gate, and open agent architecture"
```

---

## 4. Kebijakan Keamanan Agen AI (Strict Git Read-Only Policy)

Untuk mencegah modifikasi yang tidak diinginkan pada riwayat repository:
* **Agen AI / Asisten Koding**: Secara mutlak hanya memiliki izin **Read-Only** pada Git (`git status`, `git diff`, `git log`, `git show`).
* **Pengguna / Human Engineer**: Bertindak sebagai *Release Master* yang mengeksekusi perintah mutasi Git (`git add`, `git commit`, `git tag`, `git push`, `git merge`).

---

## 5. Alur Kerja Kontribusi Standar (Step-by-Step)

```bash
# 1. Pastikan Anda berada di branch main terbaru
git checkout main
git pull origin main

# 2. Buat branch kerja baru
git checkout -b feat/nama-fitur-baru

# 3. Lakukan pengembangan & pastikan seluruh unit test lolos
python3 test_workflow/run_tests.py   # Target: 100% PASS

# 4. Tambahkan berkas & komit dengan Conventional Commits
git add .
git commit -m "feat(module): add new capability"

# 5. Gabungkan kembali ke main & tag versi baru (jika rilis)
git checkout main
git merge feat/nama-fitur-baru
git tag -a v0.3.0 -m "Release v0.3.0: Summary"

# 6. Push ke remote GitHub
git push origin main --tags

# 7. Bersihkan branch kerja lokal
git branch -d feat/nama-fitur-baru
```
