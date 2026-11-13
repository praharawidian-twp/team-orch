# 🛡️ Matriks Hak Akses & Pembatasan Agen (Stirring Matrix)

Matriks ini mengatur hak baca (*Read*), tulis (*Write*), dan perbarui (*Update*) secara terperinci untuk setiap peran agen dalam sistem.

---

## 1. Matriks Akses Peran vs Wilayah Direktori

| Wilayah Direktori | PM | Analis | Coder | DevOps | Dokumenter | QA |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`sandbox/<prj>/` (Source Code)** | R | R | **RWU** | **RWU** (infra files) | R | R (tests) |
| **`.agents/tasks/active/<prj>/01-requirements.md`** | **RWU** | R | R | R | R | R |
| **`.agents/tasks/active/<prj>/02-technical-spec.md`** | R | **RWU** | R | R | R | R |
| **`.agents/tasks/active/<prj>/03-task-list.md`** | R | **RWU** | R | R | R | R |
| **`.agents/tasks/active/<prj>/review-log.md`** | R | **RWU** (verdict) | **RWU** (submit) | R | R | R |
| **`.agents/tasks/active/<prj>/audit-trail.md`** | **Append** | **Append** | **Append** | **Append** | **Append** | **Append** |
| **`.agents/tasks/active/<prj>/scratch/`** | R | **RWU** | **RWU** | **RWU** | R | **RWU** |
| **`.agents/knowledge/.drafts/`** | **RWU** | **RWU** | **RWU** | **RWU** | **RWU** | **RWU** |
| **`.agents/knowledge/topics/` (Active Master)** | **READ** | **READ** | **READ** | **READ** | **READ** | **READ** |
| **`.agents/knowledge/registry.yaml`** | **READ** | **READ** | **READ** | **READ** | **READ** | **READ** |
| **`cmd/` (CLI Tools)** | **READ/EXEC** | **READ/EXEC** | **READ/EXEC** | **READ/EXEC** | **READ/EXEC** | **READ/EXEC** |
| **Root Workspace (`/`)** | **READ** | **READ** | **READ** | **READ** | **READ** | **READ** |
| **Git Metadata (`.git/`)** | **READ** | **READ** | **READ** | **READ** | **READ** | **READ** |

*Keterangan*:
- **R**: Read-Only
- **RWU**: Read, Write, Update
- **Append**: Hanya menambahkan catatan ke akhir berkas (via `team-orch log`)
- **READ/EXEC**: Hanya membaca atau mengeksekusi biner/skrip

---

## 2. Aturan Larangan Spesifik (Strict Denials)
1. **Dilarang Menulis di Root Workspace**: Tidak diperbolehkan membuat berkas pengujian liar (`test.py`, `script.sh`, `output.txt`) langsung di root direktori proyek. Selalu gunakan folder `scratch/` di dalam task aktif.
2. **Dilarang Mutasi Git**: Seluruh agen secara mutlak dilarang memanggil `git commit`, `git push`, `git checkout -b`, `git merge`. Hanya `git status`, `git diff`, `git log` yang diizinkan.
3. **Dilarang Self-Approval Knowledge**: Perintah `team-orch knowledge approve` diblokir keras bagi seluruh peran agen AI.
4. **Dilarang Self-Completion Project**: Perintah `team-orch complete` diblokir keras bagi agen pekerja.
