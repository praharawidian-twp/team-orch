# 📦 Panduan Instalasi & Pembersihan (Installer & Uninstaller)

Direktori ini menyediakan skrip otomatisasi untuk memasang (*install*), memverifikasi (*verify*), dan membersihkan (*uninstall*) framework multi-agen otonom pada sistem operasi macOS atau Linux.

---

## 🚀 1. Pemasangan di Device Baru (Pilih Salah Satu)

### Cara A: 1-Prompt Setup Lewat Agen AI (Paling Praktis)
Jika Anda membuka Antigravity IDE atau Antigravity CLI (`agy`) di komputer baru, Anda cukup memberikan instruksi berikut ke agen:

> **Prompt ke AI Agen:**  
> *"Tolong terapkan dan pasang autonomous multi-agent framework dari repositori ini: https://github.com/praharawidian-twp/team-orch"*

Agen AI akan secara otomatis:
1. Meng-clone repositori dari `https://github.com/praharawidian-twp/team-orch`.
2. Menjalankan `./cmd/team-orch setup --yes`.
3. Memastikan konfigurasi Herdr (`~/.config/herdr/config.toml`) siap.
4. Menjalankan `./cmd/team-orch status` dan `./cmd/team-orch domain list` untuk memastikan seluruh agen (PM, Analis, Coder, QA Engineer, Dokumenter) dan konteks domain aktif siap digunakan.

---

### Cara B: Pemasangan Manual via Terminal
Jalankan langkah berikut di terminal laptop/komputer baru Anda:

```bash
# 1. Clone repositori framework
git clone https://github.com/praharawidian-twp/team-orch.git team-orch
cd team-orch

# 2. Jalankan setup wizard
./cmd/team-orch setup

# 3. Aktifkan environment
source cmd/env.sh
```

---

## 🔍 2. Apa Saja yang Dikonfigurasi oleh `install.sh`?

1. **Memeriksa Prasyarat**: Memastikan Python 3.8+ dan mendeteksi ketersediaan Herdr.
2. **Auto-Config Herdr**: Jika Herdr sudah terpasang namun belum pernah dibuka, skrip akan membuat file `~/.config/herdr/config.toml` dengan `onboarding = false` agar tidak terhambat wizard awal.
3. **Global Store**: Menempatkan *system prompts* peran (PM, Analis/Tech Lead, Coder, QA Engineer, Dokumenter), dokumen template, bundled skills, dan store Specific Domain Pack ke `~/.gemini/team-orch/` (termasuk `~/.gemini/team-orch/domains/`).
4. **Symlink CLI**: Mendaftarkan `team-orch`, `herdr-orch`, `agy-auto`, `sync-boilerplates`, dan `team-orch-uninstall` ke `~/.local/bin/`.
5. **Skill & Rules**: Mendaftarkan custom skill `team-orchestrator` serta 10 skill bawaan framework (termasuk ECC suite: `ecc`, `ecc-guide`, `ecc-recipes`, serta skill inti rekayasa seperti `agent-governance`, `devsecops-guardian`, `herdr-orchestrator`, `office-document-suite`, `qa-test-specialist`, `tech-lead-analyst`, `ui-evidence-capture`) dan aturan ketat ke `~/.gemini/GEMINI.md`.

---

## 🗑️ 3. Cara Menghapus Framework Secara Utuh (Clean Uninstall)

Jika Anda atau rekan yang Anda bagikan framework ini ingin menghapusnya secara total dari komputer tanpa meninggalkan sampah konfigurasi:

Jalankan perintah ini dari terminal mana saja:
```bash
team-orch-uninstall
```
Atau langsung dari folder repositori:
```bash
./installer/uninstall.sh
```

### Apa yang dibersihkan oleh `uninstall.sh`?
- Menghapus symlink CLI (`team-orch`, `herdr-orch`, `team-orch-uninstall`) dari `~/.local/bin/`.
- Menghapus seluruh direktori data global `~/.gemini/team-orch/`.
- Menghapus pendaftaran skill `~/.gemini/config/skills/team-orchestrator/`.
- Mencadangkan dan menonaktifkan aturan `~/.gemini/GEMINI.md`.
- Komputer kembali bersih seperti semula.
