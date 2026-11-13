#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== VERIFIKASI SETUP FRAMEWORK MULTI-AGEN ===${NC}"

FAIL=0

# 1. Check local cmd/ tools
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -x "${REPO_ROOT}/cmd/team-orch" ] && [ -x "${REPO_ROOT}/cmd/herdr-orch" ] && [ -x "${REPO_ROOT}/cmd/agy-auto" ]; then
    echo -e "${GREEN}[PASS] Local self-contained tools di ./cmd/:${NC} OK (team-orch, herdr-orch, agy-auto, env.sh)"
else
    echo -e "${YELLOW}[WARN] Berkas di direktori ./cmd/ belum lengkap atau belum executable.${NC}"
fi

# 2. Check team-orch CLI
if command -v team-orch &> /dev/null; then
    echo -e "${GREEN}[PASS] team-orch CLI in PATH:${NC} $(which team-orch)"
elif [ -x "${REPO_ROOT}/cmd/team-orch" ]; then
    echo -e "${GREEN}[PASS] team-orch CLI:${NC} ${REPO_ROOT}/cmd/team-orch (Local cmd/)"
else
    echo -e "${RED}[FAIL] team-orch CLI tidak ditemukan.${NC}"
    FAIL=1
fi

# 3. Check herdr-orch CLI
if command -v herdr-orch &> /dev/null; then
    echo -e "${GREEN}[PASS] herdr-orch CLI in PATH:${NC} $(which herdr-orch)"
elif [ -x "${REPO_ROOT}/cmd/herdr-orch" ]; then
    echo -e "${GREEN}[PASS] herdr-orch CLI:${NC} ${REPO_ROOT}/cmd/herdr-orch (Local cmd/)"
else
    echo -e "${RED}[FAIL] herdr-orch CLI tidak ditemukan.${NC}"
    FAIL=1
fi


# 3. Check uninstaller
if [ -f "${HOME}/.local/bin/team-orch-uninstall" ] || [ -f "$(dirname "$0")/uninstall.sh" ]; then
    echo -e "${GREEN}[PASS] Skrip Pembersih (Uninstaller):${NC} Siap digunakan"
else
    echo -e "${YELLOW}[WARN] Skrip uninstall belum terdaftar di PATH.${NC}"
fi

# 4. Check global store (roles & templates)
ROLE_COUNT=$(ls -1 "${HOME}/.gemini/team-orch/roles"/*.md 2>/dev/null | wc -l | tr -d ' ')
TMPL_COUNT=$(ls -1 "${HOME}/.gemini/team-orch/templates"/*.md 2>/dev/null | wc -l | tr -d ' ')

if [ "${ROLE_COUNT}" -ge 4 ] && [ "${TMPL_COUNT}" -ge 5 ]; then
    echo -e "${GREEN}[PASS] Global roles (${ROLE_COUNT}) & templates (${TMPL_COUNT}) di ~/.gemini/team-orch/${NC}"
else
    echo -e "${RED}[FAIL] Berkas peran atau template di ~/.gemini/team-orch/ tidak lengkap.${NC}"
    FAIL=1
fi

# 5. Check global knowledge base & domain store
KB_COUNT=$(ls -1 "${HOME}/.gemini/team-orch/knowledge/topics"/*.md 2>/dev/null | wc -l | tr -d ' ')
if [ -f "${HOME}/.gemini/team-orch/knowledge/registry.yaml" ] && [ "${KB_COUNT}" -ge 3 ]; then
    echo -e "${GREEN}[PASS] Scoped Knowledge Base (${KB_COUNT} base topics) di ~/.gemini/team-orch/knowledge/${NC}"
else
    echo -e "${YELLOW}[WARN] Scoped Knowledge Base di ~/.gemini/team-orch/ belum terpasang atau belum lengkap.${NC}"
fi
if [ -d "${HOME}/.gemini/team-orch/domains" ]; then
    echo -e "${GREEN}[PASS] Specific Domain Store siap di ~/.gemini/team-orch/domains/${NC}"
fi

# 6. Check global skill
if [ -f "${HOME}/.gemini/config/skills/team-orchestrator/SKILL.md" ]; then
    echo -e "${GREEN}[PASS] Global skill terdaftar:${NC} ~/.gemini/config/skills/team-orchestrator/SKILL.md"
else
    echo -e "${RED}[FAIL] Global skill team-orchestrator tidak ditemukan.${NC}"
    FAIL=1
fi

# 7. Check global rules
if grep -q "Strict Git Policy" "${HOME}/.gemini/GEMINI.md" 2>/dev/null; then
    echo -e "${GREEN}[PASS] Aturan global (Git Read-Only, Tech Lead, dll) aktif di ~/.gemini/GEMINI.md${NC}"
else
    echo -e "${RED}[FAIL] Aturan Strict Git Policy tidak ditemukan di ~/.gemini/GEMINI.md.${NC}"
    FAIL=1
fi

# 8. Check Herdr status
if command -v herdr &> /dev/null; then
    echo -e "${GREEN}[PASS] Herdr terminal manager:${NC} $(herdr --version 2>/dev/null || echo 'terpasang')"
else
    echo -e "${YELLOW}[INFO] Herdr belum terpasang (Opsional, diperlukan jika menggunakan multi-pane Herdr).${NC}"
fi

# 9. Check ui-capture CLI & doctor capability
if command -v ui-capture &> /dev/null || [ -x "${REPO_ROOT}/.agents/skills/ui-evidence-capture/scripts/ui-capture.py" ]; then
    UI_BIN="$(command -v ui-capture 2>/dev/null || echo "${REPO_ROOT}/.agents/skills/ui-evidence-capture/scripts/ui-capture.py")"
    DOC_OUT=$(python3 "${UI_BIN}" doctor --json 2>/dev/null || true)
    if echo "${DOC_OUT}" | grep -q '"status":'; then
        echo -e "${GREEN}[PASS] ui-capture CLI & doctor check:${NC} OK (Consent gate & doctor responsif)"
    else
        echo -e "${YELLOW}[WARN] ui-capture doctor tidak mengembalikan skema JSON yang valid.${NC}"
    fi
else
    echo -e "${YELLOW}[WARN] ui-capture belum terdaftar di PATH.${NC}"
fi

echo -e "${BLUE}=============================================${NC}"

if [ "${FAIL}" -eq 0 ]; then
    echo -e "${GREEN}[ALL CHECKS PASSED - FRAMEWORK SIAP DIGUNAKAN DI SEMUA PERANGKAT]${NC}"
    exit 0
else
    echo -e "${RED}[BEBERAPA PEMERIKSAAN GAGAL - SILAKAN JALANKAN ULANG ./installer/install.sh]${NC}"
    exit 1
fi
