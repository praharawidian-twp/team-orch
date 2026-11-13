# Constitutional Immutables — Self-Improvement Framework

> **Status**: SACRED — READ-ONLY untuk seluruh agen AI tanpa pengecualian
> **Authority**: Dikelola EKSKLUSIF oleh Pengguna (Human) di Control Room
> **Referensi**: `.agents/tasks/active/self-improvement/02-technical-spec.md §3.1`
> **Last Updated**: 2026-10-22

---

## ⚠️ Peringatan Kritis untuk Semua Agen

Dokumen ini mendefinisikan **prinsip-prinsip yang DIKECUALIKAN SEPENUHNYA** dari mekanisme
Self-Improvement Framework. Tidak ada siklus self-improvement, proposal draf, atau perubahan
arsitektur yang boleh menargetkan, melemahkan, atau memodifikasi prinsip-prinsip berikut.

**Melanggar Constitutional Immutables adalah pelanggaran tertinggi dalam ekosistem ini.**

---

## Prinsip Immutable #1 — Zero Self-Approval

**Pernyataan**: AI DILARANG KERAS mengeksekusi perintah yang menyetujui perubahan pada
knowledge base, skill, atau role framework.

**Implementasi Teknis**:
- Perintah `team-orch knowledge approve` dan `team-orch self-improve activate` memverifikasi
  `sys.stdin.isatty()` dan menolak eksekusi dari konteks otomasi.
- Hook guardrail memblok penulisan langsung ke `knowledge/topics/`.
- Tidak ada bypass atau override yang diperbolehkan oleh agen.

**Tidak dapat diubah oleh**: Siapapun kecuali Pengguna secara eksplisit di terminal Control Room.

---

## Prinsip Immutable #2 — Human Gatekeeper Sovereignty (3 Gates)

**Pernyataan**: Tiga gerbang dalam SDLC framework hanya dapat dibuka oleh Manusia:

1. **User Approval Gate**: Menyetujui PRD sebelum Analis merancang arsitektur.
   - Perintah: `team-orch approve <project_id>`

2. **Knowledge Approval Gate**: Menyetujui draf knowledge menjadi materi aktif.
   - Perintah: `team-orch knowledge approve <draft_id>`

3. **Final UAT & Sign-off Gate**: Menyetujui hasil akhir proyek.
   - Perintah: `team-orch complete <project_id>`

**Tidak dapat diubah oleh**: Agen pekerja, Meta-Architect, atau proses otomasi apapun.

---

## Prinsip Immutable #3 — Read-Only Git Policy

**Pernyataan**: Seluruh agen AI dalam ekosistem ini DILARANG KERAS menjalankan perintah
Git yang bersifat mutating.

**Perintah yang Dilarang** (daftar non-exhaustive):
- `git add`, `git commit`, `git push`, `git push --force`
- `git merge`, `git rebase`, `git reset --hard`
- `git tag`, `git branch -d`, `git checkout -b`
- `git stash pop`, `git cherry-pick`

**Perintah yang Diizinkan** (read-only):
- `git status`, `git diff`, `git log`, `git show`
- `git branch --list`, `git remote -v`

**Tidak dapat diubah oleh**: Siapapun kecuali Pengguna melalui revisi eksplisit dokumen ini.

---

## Prinsip Immutable #4 — Workspace Confinement

**Pernyataan**: Setiap agen HANYA boleh menulis ke zona direktori yang telah ditentukan
sesuai perannya. Dilarang membuat file liar di root workspace.

**Zona Terlarang** (mutlak, tanpa pengecualian):
- Root workspace (`/`) — dilarang membuat file di root
- `.git/` — Read-Only sepenuhnya
- `cmd/` — READ-ONLY untuk agen pekerja
- `.agents/hooks/` — READ-ONLY untuk agen pekerja
- `.agents/knowledge/topics/` — READ-ONLY, hanya bisa diubah setelah Human Approval

**Tidak dapat diubah oleh**: Siapapun kecuali Pengguna melalui revisi eksplisit dokumen ini.

---

## Prinsip Immutable #5 — Control Room Sanctity

**Pernyataan**: Pane Control Room (`$HERDR_PANE_ID`) adalah ruang kendali eksklusif Manusia.

- Dilarang menjalankan proses eksekusi kode berat atau blocking loop di Control Room.
- Dilarang menimpa atau mengganggu input/output Manusia di terminal Control Room.
- Seluruh komunikasi agen ke Control Room bersifat informatif (output text), bukan interaktif.

**Tidak dapat diubah oleh**: Siapapun kecuali Pengguna melalui revisi eksplisit dokumen ini.

---

## Prinsip Immutable #6 — File-Driven Handoff Mandate

**Pernyataan**: Seluruh penyerahan instruksi teknis antar-agen WAJIB dilakukan melalui
berkas task-handoff.md, bukan melalui wall-of-text di terminal.

- Sinyal di terminal hanya boleh berupa trigger minimalis (1-2 baris).
- Spesifikasi penuh dan instruksi kerja wajib di-write ke berkas task-handoff.md.
- Dilarang menyuntikkan prompt panjang langsung ke pane agen lain.

**Tidak dapat diubah oleh**: Siapapun kecuali Pengguna melalui revisi eksplisit dokumen ini.

---

## Cara Mengamandemen Dokumen Ini

Hanya Pengguna di Control Room yang dapat menambah, merevisi, atau menghapus prinsip di dokumen ini.
Prosedur:
1. Pengguna mengedit dokumen ini secara manual di terminal Control Room.
2. Perubahan dicatat di `audit-trail.md` project `self-improvement` dengan tag `[CONSTITUTIONAL_AMENDMENT]`.
3. Tidak ada agen yang boleh mengusulkan amandemen terhadap dokumen ini melalui mekanisme self-improvement.

---

*Dokumen ini adalah fondasi keamanan dan kedaulatan manusia dalam ekosistem agen otonom ini.*
