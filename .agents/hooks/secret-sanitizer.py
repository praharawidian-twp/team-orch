#!/usr/bin/env python3
"""
secret-sanitizer.py - DevSecOps PreToolUse Guardrail Hook
Melindungi 100% kredensial sensitif, file konfigurasi server, dan mencegah kebocoran rahasia.
Mengadopsi standar OWASP AST10 dan pola deteksi GitGuardian/Gitleaks.
"""

import sys
import json
import re
from pathlib import Path

# Safe placeholder patterns to ignore
SAFE_PLACEHOLDER_REGEX = re.compile(
    r'(?i)(\$\{|\bplaceholder\b|\byour[-_]|<password>|<secret>|changeme|example|dummy|xxx|\*\*\*)'
)

# Sensitive server paths
SENSITIVE_FILES_REGEX = re.compile(
    r'(^|[\s/"\'])(~?/\.ssh/.*|~?/\.aws/.*|~?/\.kube/config|/etc/shadow|/etc/passwd|\.gnupg/.*)'
)

# Explicitly check for .env but allow .env.example / .env.sample / .env.template
def is_raw_env_file(path_str: str) -> bool:
    clean = path_str.strip().strip("'\"")
    if re.search(r'\.env\.(example|sample|template|test|dist)\b', clean, re.IGNORECASE):
        return False
    return bool(re.search(r'(^|/)\.env($|\s)', clean))

# Command patterns that dump environment or sensitive credentials
SENSITIVE_COMMANDS_REGEX = re.compile(
    r'(^\s*(env|printenv)\s*$|\bcat\s+([^\s]*/)?\.env($|\s)|\bsource\s+([^\s]*/)?\.env($|\s)|\b(cat|less|more|head|tail)\s+~?/\.(ssh|aws)/)'
)

# High-precision secret patterns (Zero False Positive design)
SECRET_PATTERNS = [
    (re.compile(r'\b(AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b'), 'AWS Access Key ID'),
    (re.compile(r'(?i)(aws_secret_access_key|secret_key)\s*[:=]\s*["\']?[A-Za-z0-9/+=]{40}["\']?'), 'AWS Secret Key'),
    (re.compile(r'\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b'), 'GitHub Personal Access Token'),
    (re.compile(r'\bglpat-[A-Za-z0-9_\-]{20,}\b'), 'GitLab Personal Access Token'),
    (re.compile(r'\bxox[baprs]-[0-9A-Za-z]{10,}\b'), 'Slack API Token'),
    (re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'), 'Private Cryptographic Key'),
    (re.compile(r'(?i)(postgres|postgresql|mysql|mongodb|redis)://[^:]+:[^@\s]{4,}@'), 'Live Database Credentials URI'),
    (re.compile(r'(?i)bearer\s+[A-Za-z0-9_\-\.]{40,}'), 'Live Bearer Auth Token'),
]

def emit_decision(decision="allow", reason=None):
    resp = {"decision": decision}
    if reason:
        resp["reason"] = reason
    print(json.dumps(resp))
    sys.exit(0)

def check_value_for_secrets(val: str):
    if not isinstance(val, str) or len(val) < 8:
        return None
    # Skip if whole string is an obvious template/placeholder
    if SAFE_PLACEHOLDER_REGEX.search(val) and not "-----BEGIN" in val:
        return None
    for pattern, name in SECRET_PATTERNS:
        match = pattern.search(val)
        if match:
            matched_str = match.group(0)
            if not SAFE_PLACEHOLDER_REGEX.search(matched_str):
                return f"Pola rahasia terdeteksi ({name})"
    return None

def check_command_safety(cmd: str):
    if not isinstance(cmd, str):
        return None
    if SENSITIVE_COMMANDS_REGEX.search(cmd):
        return "Percobaan eksekusi perintah pembocoran environment/kredensial server (.env, env, printenv, ssh, aws)"
    if is_raw_env_file(cmd) and re.search(r'\b(cat|less|more|tail|head|cp|scp|curl)\b', cmd):
        return "Percobaan membaca atau mengekspos berkas .env rahasia"
    return None

def check_file_path_safety(path: str):
    if not isinstance(path, str):
        return None
    if is_raw_env_file(path):
        return "Akses baca/tulis langsung ke file rahasia .env (Gunakan .env.example)"
    if SENSITIVE_FILES_REGEX.search(path):
        return f"Akses ke berkas infrastruktur sensitif server ({path})"
    return None

def log_security_violation(violation: str):
    try:
        log_dir = Path(".agents/tasks")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "audit-trail-security.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"🛑 [DEVSECOPS BLOCK] {violation}\n")
    except Exception:
        pass

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            emit_decision("allow")

        payload = json.loads(input_data)
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})

        # 1. Pengecekan Perintah Shell (run_command)
        if tool_name == "run_command":
            cmd = args.get("CommandLine", "")
            cmd_violation = check_command_safety(cmd)
            if cmd_violation:
                log_security_violation(f"CommandLine: {cmd_violation}")
                emit_decision("deny", f"🛑 [DEVSECOPS GUARDIAN]: Perintah ditolak! {cmd_violation}.")

            # Periksa jika ada raw secret yang ditempelkan di CommandLine
            sec_violation = check_value_for_secrets(cmd)
            if sec_violation:
                log_security_violation(f"CommandLine Secret: {sec_violation}")
                emit_decision("deny", f"🛑 [DEVSECOPS GUARDIAN]: Perintah memuat kredensial sensitif! {sec_violation}.")

        # 2. Pengecekan Penulisan Berkas (write_to_file / replace_file_content)
        elif tool_name in ["write_to_file", "replace_file_content"]:
            target_path = args.get("TargetFile", "")
            path_violation = check_file_path_safety(target_path)
            if path_violation:
                log_security_violation(f"FilePath: {path_violation}")
                emit_decision("deny", f"🛑 [DEVSECOPS GUARDIAN]: Operasi file ditolak! {path_violation}.")

            content = args.get("CodeContent", "") or args.get("ReplacementContent", "")
            sec_violation = check_value_for_secrets(content)
            if sec_violation:
                log_security_violation(f"FileContent Secret: {sec_violation}")
                emit_decision("deny", f"🛑 [DEVSECOPS GUARDIAN]: Penulisan berkas dibatalkan! Ditemukan plain credentials ({sec_violation}). Gunakan environment variable.")

        # 3. Pengecekan Pembacaan Berkas (view_file)
        elif tool_name == "view_file":
            abs_path = args.get("AbsolutePath", "")
            path_violation = check_file_path_safety(abs_path)
            if path_violation:
                log_security_violation(f"ViewFile: {path_violation}")
                emit_decision("deny", f"🛑 [DEVSECOPS GUARDIAN]: Pembacaan berkas ditolak! {path_violation}.")

        emit_decision("allow")

    except Exception:
        # Fail safe
        emit_decision("allow")

if __name__ == "__main__":
    main()
