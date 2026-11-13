#!/usr/bin/env python3
"""
Self-Improvement Framework — Security Guardrail Hook (PreToolUse Interceptor)
==============================================================================
Komponen: Pilar 3 — Layer 3 Safety Guardrails (Anti-Drift System)
Referensi: .agents/tasks/active/self-improvement/02-technical-spec.md §3.3 & §3.4

Hook ini bertugas sebagai INTERCEPTOR yang berjalan SEBELUM setiap operasi
tulis file oleh agen AI. Dua fungsi utama:

1. FORBIDDEN_MUTATION_BY_AGENT:
   Memblok penulisan ke zona terlarang (knowledge/topics, skills produksi,
   cmd/, hooks/, registry.yaml) dan melempar ForbiddenMutationError.

2. HUMAN_TTY_GATE (approve commands):
   Memverifikasi bahwa perintah approve hanya dieksekusi oleh manusia
   yang berinteraksi langsung di terminal interaktif (bukan oleh agen/otomasi).

Cara Registrasi ke hooks.json:
  Tambahkan entry berikut ke .agents/hooks.json:
  {
    "hook_id": "self-improvement-guardrail",
    "type": "PreToolUse",
    "script": ".agents/hooks/self-improvement-guardrail.py",
    "enabled": true,
    "priority": 10,
    "description": "Anti-drift guardrail — blok mutasi agen ke zona terlarang & TTY check approval"
  }

Standalone testing:
  python3 .agents/hooks/self-improvement-guardrail.py --test
"""

import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Zona Terlarang (Forbidden Write Paths)
# AI TIDAK BOLEH menulis ke path manapun dalam daftar ini
# ---------------------------------------------------------------------------

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_WRITE_PATHS: list[str] = [
    # Knowledge produksi — hanya bisa diubah setelah Human Approval
    ".agents/knowledge/topics/",
    # Skills produksi — hanya bisa diubah setelah Human Approval
    ".agents/skills/",
    # Role produksi — hanya bisa diubah setelah Human Approval
    ".agents/roles/",
    # Framework CLI core — TIDAK PERNAH boleh diubah oleh agen pekerja
    "cmd/",
    # Guardrail hooks — agen tidak boleh mengubah mekanisme keamanannya sendiri
    ".agents/hooks/",
    # Knowledge registry — dikelola oleh framework, bukan agen
    ".agents/knowledge/registry.yaml",
    # Constitutional immutables — SACRED, tidak boleh disentuh AI
    ".agents/knowledge/topics/constitutional-immutables.md",
    # Konfigurasi self-improvement — dikelola Manusia
    ".agents/config/self-improvement.yaml",
]

# Pesan error untuk setiap kategori pelanggaran
FORBIDDEN_MESSAGES: dict[str, str] = {
    ".agents/knowledge/topics/":
        "Knowledge topics adalah READ-ONLY untuk agen. "
        "Gunakan: team-orch knowledge draft <topic_id> untuk membuat proposal.",
    ".agents/skills/":
        "Skills produksi adalah READ-ONLY untuk agen. "
        "Gunakan zona .agents/knowledge/.drafts/skills/ untuk proposal baru.",
    ".agents/roles/":
        "Role produksi adalah READ-ONLY untuk agen. "
        "Gunakan zona .agents/knowledge/.drafts/roles/ untuk proposal revisi.",
    "cmd/":
        "CLI framework adalah READ-ONLY untuk semua agen pekerja. "
        "Hanya Meta-Architect dengan persetujuan Manusia yang dapat memodifikasi cmd/.",
    ".agents/hooks/":
        "Guardrail hooks adalah READ-ONLY. "
        "Agen tidak diizinkan mengubah mekanisme keamanan mereka sendiri.",
    ".agents/knowledge/registry.yaml":
        "Knowledge registry dikelola oleh framework. "
        "Gunakan: team-orch knowledge draft untuk meregistrasi topik baru.",
    ".agents/knowledge/topics/constitutional-immutables.md":
        "Constitutional Immutables adalah dokumen SACRED — tidak dapat diubah oleh AI apapun.",
    ".agents/config/self-improvement.yaml":
        "File konfigurasi self-improvement hanya dapat diubah oleh Manusia di Control Room. "
        "Gunakan: team-orch self-improve config --set key=value",
}

# Perintah yang memerlukan verifikasi Human TTY
HUMAN_GATE_COMMANDS: set[str] = {
    "knowledge approve",
    "self-improve approve",
    "self-improve activate",
    "complete",
    "knowledge activate",
}


# ---------------------------------------------------------------------------
# Exception Classes
# ---------------------------------------------------------------------------

class ForbiddenMutationError(PermissionError):
    """Dilempar ketika agen mencoba menulis ke zona terlarang."""
    pass


class HumanGateViolationError(PermissionError):
    """Dilempar ketika perintah approve dieksekusi di luar terminal interaktif."""
    pass


# ---------------------------------------------------------------------------
# Core Guardrail Functions
# ---------------------------------------------------------------------------

def normalize_path(raw_path: str) -> str:
    """
    Normalisasi path ke format relatif dari workspace root.
    Mendukung path relatif (tanpa leading slash) dan path absolut.
    """
    try:
        p = Path(raw_path)
        # Coba resolusi absolut terhadap workspace root
        if p.is_absolute():
            abs_path = p.resolve()
            try:
                rel_path = str(abs_path.relative_to(WORKSPACE_ROOT))
                return rel_path.replace("\\", "/")
            except ValueError:
                # Path di luar workspace — kembalikan apa adanya
                return raw_path.replace("\\", "/")
        else:
            # Path sudah relatif — normalisasi saja
            # Hapus leading "./" jika ada
            normalized = raw_path.replace("\\", "/").lstrip("./")
            return str(Path(raw_path)).replace("\\", "/")
    except Exception:
        return raw_path


def _path_matches_forbidden(target: str, forbidden: str) -> bool:
    """
    Cek apakah target cocok dengan pattern forbidden.
    Mendukung matching pada path relatif maupun absolut.
    """
    # Normalisasi keduanya ke forward slash, strip trailing slash
    t = target.replace("\\", "/").rstrip("/")
    f = forbidden.replace("\\", "/").rstrip("/")

    # Direct relative match (paling sering dari test cases)
    if t == f or t.startswith(f + "/"):
        return True

    # Match pada bagian akhir path (jika target adalah path absolut yang berisi forbidden sebagai suffix)
    if t.endswith("/" + f) or ("/" + f + "/") in t or t.endswith(f):
        return True

    # Resolve absolut dan cek
    try:
        abs_target = str(Path(target).resolve()).replace("\\", "/")
        abs_forbidden = str((WORKSPACE_ROOT / f).resolve()).replace("\\", "/").rstrip("/")
        if abs_target == abs_forbidden or abs_target.startswith(abs_forbidden + "/"):
            return True
    except Exception:
        pass

    return False


def check_forbidden_path(target_path: str) -> tuple[bool, str]:
    """
    Periksa apakah target_path berada di zona terlarang.

    Returns:
        (is_forbidden: bool, error_message: str)
    """
    for forbidden in FORBIDDEN_WRITE_PATHS:
        if _path_matches_forbidden(target_path, forbidden):
            # Cari pesan spesifik (coba exact match dulu, lalu prefix match)
            message = FORBIDDEN_MESSAGES.get(forbidden)
            if not message:
                # Cari pesan berdasarkan prefix yang cocok
                for key in FORBIDDEN_MESSAGES:
                    if forbidden.startswith(key) or key.startswith(forbidden.rstrip("/")):
                        message = FORBIDDEN_MESSAGES[key]
                        break
            if not message:
                message = f"Path '{target_path}' berada di zona terlarang untuk agen AI."
            return True, message

    return False, ""


def check_human_tty(command: str) -> tuple[bool, str]:
    """
    Verifikasi bahwa perintah approve hanya dieksekusi oleh Manusia di terminal.

    Returns:
        (is_blocked: bool, reason: str)
    """
    # Cek apakah command ini memerlukan TTY
    requires_human = any(gate_cmd in command.lower() for gate_cmd in HUMAN_GATE_COMMANDS)
    if not requires_human:
        return False, ""

    # Check 1: stdin harus berupa terminal interaktif
    if not sys.stdin.isatty():
        return True, (
            "HUMAN_GATE: Perintah ini hanya dapat dieksekusi oleh manusia di terminal interaktif. "
            "stdin bukan TTY — kemungkinan dipanggil dari skrip atau pipeline otomatis."
        )

    # Check 2: Tidak boleh dalam mode otomasi Herdr
    if os.environ.get("HERDR_AUTOMATION_PANEL") == "1":
        return True, (
            "HUMAN_GATE: Perintah approve diblok dalam mode otomasi agen (HERDR_AUTOMATION_PANEL=1)."
        )

    # Check 3: Tidak boleh dipanggil sebagai subagent AGY
    if os.environ.get("AGY_SUBAGENT") == "1":
        return True, (
            "HUMAN_GATE: Perintah approve diblok saat dieksekusi oleh subagent "
            "(AGY_SUBAGENT=1)."
        )

    # Check 4: Tidak boleh dalam environment CI/CD
    ci_indicators = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_HOME", "BUILDKITE"]
    for ci_var in ci_indicators:
        if os.environ.get(ci_var):
            return True, (
                f"HUMAN_GATE: Perintah approve diblok dalam environment CI/CD "
                f"({ci_var}={os.environ.get(ci_var)})."
            )

    return False, ""


# ---------------------------------------------------------------------------
# Hook Entry Point (dipanggil oleh framework Antigravity)
# ---------------------------------------------------------------------------

def pre_tool_use(tool_name: str, args: dict) -> dict:
    """
    Entry point hook PreToolUse.

    Args:
        tool_name: Nama tool yang akan dieksekusi (misal: "write_file", "edit_file")
        args: Parameter tool sebagai dict

    Returns:
        dict dengan key:
          - "allowed": bool — apakah tool boleh dilanjutkan
          - "reason": str — pesan jika ditolak
          - "action": str — "block" | "allow"
    """
    # ── Guardrail 1: Forbidden Path Check ──────────────────────────────────
    write_tools = {"write_file", "edit_file", "create_file", "write_to_file",
                   "replace_file_content", "append_to_file"}

    if tool_name in write_tools:
        target_path = (
            args.get("path") or
            args.get("Path") or
            args.get("file_path") or
            args.get("target") or
            ""
        )

        if target_path:
            is_forbidden, reason = check_forbidden_path(str(target_path))
            if is_forbidden:
                error_msg = (
                    f"FORBIDDEN_MUTATION_BY_AGENT: Penulisan ke '{target_path}' diblok.\n"
                    f"Alasan: {reason}"
                )
                print(f"\n[GUARDRAIL] 🚫 {error_msg}", file=sys.stderr)
                return {
                    "allowed": False,
                    "action": "block",
                    "reason": error_msg,
                    "error_code": "FORBIDDEN_MUTATION_BY_AGENT",
                }

    # ── Guardrail 2: Human TTY Gate (untuk perintah approve) ───────────────
    command_tools = {"run_command", "execute_command", "bash", "shell"}
    if tool_name in command_tools:
        command = str(
            args.get("command") or
            args.get("CommandLine") or
            args.get("cmd") or
            ""
        )
        is_blocked, reason = check_human_tty(command)
        if is_blocked:
            error_msg = f"{reason}"
            print(f"\n[GUARDRAIL] 🚫 {error_msg}", file=sys.stderr)
            return {
                "allowed": False,
                "action": "block",
                "reason": error_msg,
                "error_code": "HUMAN_GATE_VIOLATION",
            }

    # ── Semua check lolos ───────────────────────────────────────────────────
    return {"allowed": True, "action": "allow", "reason": ""}


# ---------------------------------------------------------------------------
# Standalone Test Runner
# ---------------------------------------------------------------------------

def run_tests() -> int:
    """Jalankan test suite sederhana untuk validasi guardrail."""
    print("=" * 60)
    print("Self-Improvement Guardrail — Test Suite")
    print("=" * 60)

    test_cases = [
        # (description, tool_name, args, expected_allowed)
        (
            "BLOCK: tulis ke knowledge/topics/ (zona terlarang)",
            "write_file",
            {"path": ".agents/knowledge/topics/new-rule.md"},
            False,
        ),
        (
            "BLOCK: tulis ke skills/ produksi",
            "edit_file",
            {"Path": ".agents/skills/agent-governance/SKILL.md"},
            False,
        ),
        (
            "BLOCK: tulis ke cmd/ (CLI core)",
            "write_file",
            {"path": "cmd/team-orch"},
            False,
        ),
        (
            "BLOCK: tulis ke hooks/ (guardrail scripts)",
            "write_file",
            {"path": ".agents/hooks/some-hook.py"},
            False,
        ),
        (
            "BLOCK: tulis ke constitutional-immutables.md",
            "write_file",
            {"path": ".agents/knowledge/topics/constitutional-immutables.md"},
            False,
        ),
        (
            "BLOCK: tulis ke config/self-improvement.yaml",
            "write_file",
            {"path": ".agents/config/self-improvement.yaml"},
            False,
        ),
        (
            "ALLOW: tulis ke .agents/knowledge/.drafts/ (zona staging)",
            "write_file",
            {"path": ".agents/knowledge/.drafts/new-proposal.md"},
            True,
        ),
        (
            "ALLOW: tulis ke .agents/tasks/active/project/ (SDLC docs)",
            "write_file",
            {"path": ".agents/tasks/active/my-project/audit-trail.md"},
            True,
        ),
        (
            "ALLOW: tulis ke sandbox/ (implementasi kode)",
            "write_file",
            {"path": "sandbox/payment-gateway/src/main.py"},
            True,
        ),
        (
            "ALLOW: perintah non-approve (tidak memerlukan TTY)",
            "run_command",
            {"CommandLine": "team-orch self-improve scan --project test"},
            True,
        ),
    ]

    passed = 0
    failed = 0

    for description, tool_name, args, expected_allowed in test_cases:
        result = pre_tool_use(tool_name, args)
        actual_allowed = result.get("allowed", True)
        status = "✓ PASS" if actual_allowed == expected_allowed else "✗ FAIL"

        if actual_allowed == expected_allowed:
            passed += 1
        else:
            failed += 1

        print(f"\n{status} | {description}")
        if actual_allowed != expected_allowed:
            print(f"       Expected: allowed={expected_allowed}")
            print(f"       Actual  : allowed={actual_allowed}")
            print(f"       Reason  : {result.get('reason', '')[:100]}")

    print()
    print("=" * 60)
    print(f"Hasil: {passed} passed, {failed} failed")
    print("=" * 60)
    return 0 if failed == 0 else 1


def main_hook_stdin() -> int:
    """
    Entry point saat hook dipanggil oleh framework via stdin JSON.
    Format input: {"tool_name": "...", "args": {...}}
    Format output: {"allowed": bool, "action": "...", "reason": "..."}
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload = json.loads(raw)
        tool_name = payload.get("tool_name", "")
        args = payload.get("args", {})
        result = pre_tool_use(tool_name, args)
        print(json.dumps(result))
        return 0 if result.get("allowed") else 1
    except json.JSONDecodeError as e:
        print(json.dumps({
            "allowed": False,
            "action": "block",
            "reason": f"Guardrail: invalid JSON input — {e}",
            "error_code": "GUARDRAIL_PARSE_ERROR",
        }))
        return 1
    except Exception as e:
        # Fail-open: jika guardrail error, jangan blok workflow (log saja)
        print(json.dumps({
            "allowed": True,
            "action": "allow",
            "reason": f"Guardrail warning: internal error (fail-open) — {e}",
        }))
        return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(run_tests())
    else:
        sys.exit(main_hook_stdin())
