# 🛡️ Kebijakan Git Read-Only & Higienitas Repositori

> **Topik ID**: `git-guidelines`  
> **Akses**: `*` (Global - Semua Agen)  
> **Tingkat Kepatuhan**: `STRICT` (Pelanggaran mengakibatkan diskualifikasi/reject)

---

## 1. Aturan Mutlak Git Read-Only
1. **DILARANG KERAS mengeksekusi perintah manipulasi Git**:
   - Dilarang: `git add`, `git commit`, `git push`, `git merge`, `git rebase`, `git tag`, `git checkout -b`, `git branch -D`, `git stash apply`.
2. **HANYA PERINTAH INSPEKSI YANG DIIZINKAN**:
   - Diizinkan: `git status`, `git diff`, `git log -n <N>`, `git show <commit>`, `git branch --list`.
3. **Pemberian Wewenang Commit**: Seluruh perubahan berkas lokal diserahkan secara manual kepada Pengguna (Manusia) untuk di-review dan di-commit.

---

## 2. Kekebalan Framework (Framework Immutability)
1. Berkas di direktori `cmd/`, `installer/`, dan konfigurasi engine `.agents/` berstatus **IMMUTABLE (READ-ONLY)** bagi agen pekerja.
2. Agen dilarang keras mengedit `cmd/team-orch`, `cmd/herdr-orch`, atau skrip engine lainnya.
3. Wilayah kerja agen HANYA di dalam `target_dir` yang telah ditentukan dalam manifest proyek.

---

## 3. Disiplin Berkas & Higienitas Repositori
1. DILARANG membuat skrip liar atau file sementara di root workspace.
2. Jika membutuhkan skrip pembantu atau runner uji coba, simpanlah di folder scratchpad proyek:
   `.agents/tasks/active/<project_id>/scratch/`
3. Selalu periksa `git status` sebelum handoff untuk memastikan tidak ada file sampah (`.DS_Store`, `__pycache__`) yang tertinggal.
