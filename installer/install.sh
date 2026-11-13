#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}  🚀 Antigravity Autonomous Multi-Agent Framework Installer     ${NC}"
echo -e "${BLUE}================================================================${NC}"

echo -e "\n[*] Memeriksa prasyarat sistem (Prerequisites)..."

# 1. Cek Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}[!] Python 3 tidak ditemukan. Silakan pasang Python 3.8+ terlebih dahulu.${NC}"
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}[✓] Python 3 terdeteksi: ${PY_VER}${NC}"

# 2. Cek Herdr (Terminal Workspace Manager)
if command -v herdr &> /dev/null; then
    HERDR_VER=$(herdr --version 2>/dev/null || echo "terpasang")
    echo -e "${GREEN}[✓] Herdr terdeteksi: ${HERDR_VER}${NC}"
else
    echo -e "${YELLOW}[!] Herdr belum terpasang di komputer ini.${NC}"
    if [[ "$OSTYPE" == "darwin"* ]] && command -v brew &> /dev/null; then
        echo -e "${CYAN}    → Untuk memasang Herdr di macOS, jalankan: brew install herdr${NC}"
    else
        echo -e "${CYAN}    → Untuk memasang Herdr di Linux/macOS, jalankan: curl -fsSL https://herdr.dev/install.sh | bash${NC}"
    fi
fi

# 3. Konfigurasi Otomatis Herdr (~/.config/herdr/config.toml)
HERDR_CONFIG_DIR="${HOME}/.config/herdr"
HERDR_CONFIG_FILE="${HERDR_CONFIG_DIR}/config.toml"
if [ ! -f "${HERDR_CONFIG_FILE}" ]; then
    echo -e "[*] Menyiapkan konfigurasi default Herdr..."
    mkdir -p "${HERDR_CONFIG_DIR}"
    cat << 'CFG_EOF' > "${HERDR_CONFIG_FILE}"
onboarding = false
CFG_EOF
    echo -e "${GREEN}[✓] Konfigurasi Herdr dibuat: ${HERDR_CONFIG_FILE} (onboarding dinonaktifkan).${NC}"
else
    echo -e "${GREEN}[✓] Konfigurasi Herdr sudah ada: ${HERDR_CONFIG_FILE}${NC}"
fi

INSTALL_DIR="${HOME}/.gemini/team-orch"
LOCAL_BIN="${HOME}/.local/bin"
SKILL_DIR="${HOME}/.gemini/config/skills/team-orchestrator"
GLOBAL_RULES="${HOME}/.gemini/GEMINI.md"

echo -e "\n[*] Menyiapkan direktori framework..."
mkdir -p "${INSTALL_DIR}/roles" "${INSTALL_DIR}/templates" "${INSTALL_DIR}/docs" "${INSTALL_DIR}/scripts" "${INSTALL_DIR}/knowledge" "${INSTALL_DIR}/domains" "${INSTALL_DIR}/skills"
mkdir -p "${LOCAL_BIN}"
mkdir -p "${SKILL_DIR}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo -e "[*] Menyalin Base Domain (roles, templates, docs, knowledge, skills)..."
if [ -d "${REPO_DIR}/.agents/roles" ]; then
    cp -r "${REPO_DIR}/.agents/roles/"* "${INSTALL_DIR}/roles/"
fi
if [ -d "${REPO_DIR}/.agents/templates" ]; then
    cp -r "${REPO_DIR}/.agents/templates/"* "${INSTALL_DIR}/templates/"
fi
if [ -d "${REPO_DIR}/.agents/docs" ]; then
    cp -r "${REPO_DIR}/.agents/docs/"* "${INSTALL_DIR}/docs/"
fi
if [ -d "${REPO_DIR}/.agents/knowledge" ]; then
    cp -r "${REPO_DIR}/.agents/knowledge/"* "${INSTALL_DIR}/knowledge/"
fi
if [ -d "${REPO_DIR}/.agents/skills" ]; then
    cp -r "${REPO_DIR}/.agents/skills/"* "${INSTALL_DIR}/skills/"
fi

# Inisialisasi default active domain ke 'base' bila belum ada
if [ ! -f "${INSTALL_DIR}/active-domain.yaml" ]; then
    cat << 'DOM_EOF' > "${INSTALL_DIR}/active-domain.yaml"
active_domain: base
DOM_EOF
fi

echo -e "[*] Memasang CLI tools ke ${LOCAL_BIN}..."
if [ -f "${REPO_DIR}/cmd/team-orch" ]; then
    cp "${REPO_DIR}/cmd/team-orch" "${INSTALL_DIR}/team-orch"
    chmod +x "${INSTALL_DIR}/team-orch"
    ln -sf "${INSTALL_DIR}/team-orch" "${LOCAL_BIN}/team-orch"
fi

if [ -f "${REPO_DIR}/cmd/herdr-orch" ]; then
    cp "${REPO_DIR}/cmd/herdr-orch" "${INSTALL_DIR}/herdr-orch"
    chmod +x "${INSTALL_DIR}/herdr-orch"
    ln -sf "${INSTALL_DIR}/herdr-orch" "${LOCAL_BIN}/herdr-orch"
fi

if [ -f "${REPO_DIR}/cmd/agy-auto" ]; then
    cp "${REPO_DIR}/cmd/agy-auto" "${INSTALL_DIR}/agy-auto"
    chmod +x "${INSTALL_DIR}/agy-auto"
    ln -sf "${INSTALL_DIR}/agy-auto" "${LOCAL_BIN}/agy-auto"
fi

if [ -f "${REPO_DIR}/cmd/sync-boilerplates" ]; then
    cp "${REPO_DIR}/cmd/sync-boilerplates" "${INSTALL_DIR}/sync-boilerplates"
    chmod +x "${INSTALL_DIR}/sync-boilerplates"
    ln -sf "${INSTALL_DIR}/sync-boilerplates" "${LOCAL_BIN}/sync-boilerplates"
fi

if [ -f "${REPO_DIR}/installer/uninstall.sh" ]; then
    cp "${REPO_DIR}/installer/uninstall.sh" "${INSTALL_DIR}/uninstall.sh"
    chmod +x "${INSTALL_DIR}/uninstall.sh"
    ln -sf "${INSTALL_DIR}/uninstall.sh" "${LOCAL_BIN}/team-orch-uninstall"
fi

if [ -f "${REPO_DIR}/.agents/skills/ui-evidence-capture/scripts/ui-capture.py" ]; then
    chmod +x "${REPO_DIR}/.agents/skills/ui-evidence-capture/scripts/ui-capture.py"
    ln -sf "${REPO_DIR}/.agents/skills/ui-evidence-capture/scripts/ui-capture.py" "${LOCAL_BIN}/ui-capture"
fi

# Clean up legacy scripts if present
rm -f "${INSTALL_DIR}/herdr-orchestrator.py"
rm -f "${LOCAL_BIN}/herdr-orchestrator.py"

echo -e "[*] Memasang aturan global & skill Antigravity..."
if [ -f "${REPO_DIR}/GEMINI.md" ]; then
    cp "${REPO_DIR}/GEMINI.md" "${GLOBAL_RULES}"
fi

cat << 'SKILL_EOF' > "${SKILL_DIR}/SKILL.md"
---
name: team-orchestrator
description: Autonomous Multi-Agent Team Orchestrator (PM, Senior Lead Engineer/Analis, Coder, Dokumenter). Use when managing multi-agent software engineering workflows, Herdr cross-pane task delegation, strict gatekeeper code reviews, read-only Git policy, and transparent audit trails.
---

# Autonomous Multi-Agent Team Orchestration

Sistem orkestrator tim rekayasa perangkat lunak otonom terintegrasi dengan Herdr multi-pane dan Antigravity.

---

## 1. Peran Tim & Hierarki

1. **Project Manager (PM)** (`gemini-3.8-flash-high`):
   - **Komunikasi Manusia**: Berdialog dengan pengguna dalam bahasa manusia yang ramah, ringkas, dan empatik.
   - **Proactive Clarification**: Dilarang berasumsi. Jika ada ambiguitas logika bisnis atau batasan sistem, PM wajib bertanya balik ke Pengguna sebelum menyusun dokumen kebutuhan.
   - **Output**: `tasks/<project_id>/01-requirements.md` (Wajib persetujuan Pengguna / Approval Gate).

2. **Analis / Senior Lead Engineer (Tech Lead)** (`gemini-3.1-pro-high`):
   - **Audit Boilerplate**: Menyelidiki struktur direktori, konvensi penamaan, dan utilitas yang sudah ada di repositori sebelum merancang kode baru.
   - **Technical Stewardship**: Menjaga Clean Code, keamanan (no hardcoded secrets, input sanitasi), prinsip SOLID, dan performa.
   - **Bukan Sekadar Tes Hijau**: Unit test adalah syarat minimal, Analis wajib menilai kualitas kode dan kesesuaian kebutuhan.
   - **Output**: `02-technical-spec.md`, `03-task-list.md`, dan `review-log.md`.

3. **Coder (Software Developer)** (`gemini-3.8-flash-high`):
   - Mengimplementasikan sub-task atomik sesuai spesifikasi teknis.
   - Wajib menyertakan unit test menyeluruh dan menjalankannya sampai 100% *PASS*.
   - Tidak boleh memodifikasi Git (`git add`, `git commit`, `git push` dilarang).

4. **Dokumenter** (`gemini-3.8-flash-low`):
   - Menyusun dokumentasi teknis dan panduan pemakaian di folder `docs/`.

---

## 2. Aturan Baku Sistem

1. **Git Policy (CRITICAL - Read-Only)**:
   - Seluruh agen DILARANG menjalankan `git add`, `git commit`, `git push`, `git merge`, dll.
   - Hanya operasi inspeksi yang diperbolehkan (`git status`, `git diff`, `git log`).
2. **Audit Trail Mandatori**:
   - Seluruh tindakan teknis dan verifikasi keamanan wajib dicatat di `tasks/<project_id>/audit-trail.md` melalui `team-orch log`.
   - Setiap agen wajib mengamati log audit sebelumnya sebelum bertindak untuk mencegah regresi/anomali.
3. **Pustaka Reusable Scripts**:
   - Skrip otomasi yang bermanfaat disimpan secara permanen di `.agents/scripts/` (atau `~/.gemini/team-orch/scripts/`), bukan skrip sekali-pakai (*scratch script*), untuk menghemat hingga 90% kuota token.

---

## 3. Perintah CLI Utama (`team-orch`)

```bash
# Global Mission Control Dashboard (Multi-project & Worker Fleet)
team-orch status

# Status detail proyek tertentu
team-orch status <project_id>

# Mulai proyek baru
team-orch init <project_id>

# User Approval Gate
team-orch approve <project_id>

# Lihat riwayat audit trail transparan
team-orch audit <project_id> [-n 10]

# Catat aksi ke audit trail
team-orch log <project_id> -r <role> -e <event> -d "<deskripsi>"

# Generate prompt peran lengkap
team-orch prompt <role> <project_id>

# Delegasikan ke Herdr worker pane
team-orch dispatch <role> <project_id> --pane <pane_id>

# Arsipkan proyek yang tuntas
team-orch complete <project_id>
```

---

## 4. Native Slash-Command Optimization & Shortcuts

1. **Clean-Room Role Switch (`/new`)**: Dispatch antar-tahap otomatis memicu `/new` pada pane worker untuk mencegah polusi memori chat lama dan menghemat 60-80% kuota token.
2. **Review Kode & Inline Comment (`/diff`)**: Saat mereview kode yang dihasilkan Coder, jalankan `/diff` dan tekan `c` untuk memberi komentar langsung pada baris kode yang ingin direvisi.
3. **Side-Questions Tanpa Polusi (`/btw`)**: Kirim pertanyaan sampingan ke worker pane menggunakan `herdr-orch btw <pane> "<pertanyaan>"` atau `/btw <pertanyaan>`.
4. **Penyimpanan Koreksi / Kebiasaan Baru (`/learn`)**: Gunakan `/learn` untuk menyimpan feedback atau aturan baru secara permanen.
SKILL_EOF

chmod +x "${LOCAL_BIN}/team-orch" "${LOCAL_BIN}/herdr-orch" 2>/dev/null || true

echo -e "\n${GREEN}================================================================${NC}"
echo -e "${GREEN}  🎉 Instalasi Selesai! Framework Multi-Agen 2-Domain Siap.     ${NC}"
echo -e "${GREEN}================================================================${NC}"
echo -e "${BLUE}[*] Arsitektur Domain:${NC}"
echo -e "    • Active Domain Default : ${CYAN}base${NC} (Day-1 Zero Institutional Knowledge)"
echo -e "    • Domain Pack Store     : ${INSTALL_DIR}/domains/ (dan .agents/domains/ per repo)"
echo -e "    • Kelola / Switch Domain: ${YELLOW}team-orch domain list | use <id> | init <id>${NC}"
echo -e "\n${BLUE}[*] Bundled Skills Bawaan (Siap Pakai):${NC}"
echo -e "    • Governance & Ops  : agent-governance, devsecops-guardian, herdr-orchestrator"
echo -e "    • Engineering & QA  : tech-lead-analyst, qa-test-specialist, ui-evidence-capture, office-document-suite"
echo -e "    • ECC Suite Bundle  : ecc, ecc-guide, ecc-recipes (verification, TDD, context budget)"
echo -e "    • Meta & Discovery  : .agents/meta-studio/ (upgrade & cetak biru agen/skill baru)"
echo -e "\nPerintah untuk mencoba: ${YELLOW}team-orch status${NC} atau ${YELLOW}team-orch domain current${NC}"
echo -e "Untuk menghapus kapan saja: ${CYAN}team-orch-uninstall${NC} (atau ./installer/uninstall.sh)"
