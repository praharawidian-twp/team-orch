#!/usr/bin/env python3
"""
knowledge-guardrail.py - PreToolUse Guardrail Hook
Mengunci direktori .agents/knowledge/topics/ dan registry.yaml dari modifikasi liar agen.
Memaksa seluruh usulan knowledge baru wajib melalui gerbang .drafts/ dan disetujui Manusia.
"""

import json
import re
import sys
from pathlib import Path

def emit_decision(decision="allow", reason=None):
    resp = {"decision": decision}
    if reason:
        resp["reason"] = reason
    print(json.dumps(resp))
    sys.exit(0)

try:
    payload = {}
    if not sys.stdin.isatty():
        payload = json.load(sys.stdin)
except Exception:
    emit_decision("allow")

tool_call = payload.get("toolCall", {})
tool_name = tool_call.get("name", "")
args = tool_call.get("args", {})

# Pola file yang dilindungi ketat (Knowledge Core)
PROTECTED_PATTERNS = [
    r"\.agents/knowledge/topics/",
    r"\.agents/knowledge/registry\.yaml",
]

# 1. Pengecekan tool write_to_file & replace_file_content
if tool_name in ["write_to_file", "replace_file_content"]:
    target_file = str(args.get("TargetFile", ""))
    
    # Izinkan jika target adalah .drafts/
    if ".agents/knowledge/.drafts/" in target_file:
        emit_decision("allow")

    # Anti-Assumption PRD Guardrail: Blokir pembuatan PRD tanpa Discovery Log & Boilerplate Reference
    if target_file.endswith("01-requirements.md"):
        content = str(args.get("CodeContent", "")) or str(args.get("ReplacementContent", ""))
        if tool_name == "replace_file_content":
            try:
                import os
                if os.path.exists(target_file):
                    with open(target_file, "r", encoding="utf-8") as f:
                        file_text = f.read()
                    target_cnt = str(args.get("TargetContent", ""))
                    repl_cnt = str(args.get("ReplacementContent", ""))
                    if target_cnt in file_text:
                        content = file_text.replace(target_cnt, repl_cnt, 1)
                    else:
                        content = file_text
            except Exception:
                pass
        has_discovery = bool(re.search(r"(Discovery Log|Tanya-Jawab Kebutuhan|Wawancara Kebutuhan|Requirement Discovery)", content, re.IGNORECASE))
        has_boilerplate = bool(re.search(r"(Boilerplate Reference|Basis Boilerplate|Referensi Boilerplate)", content, re.IGNORECASE))
        if not (has_discovery and has_boilerplate):
            emit_decision(
                "deny",
                "🛑 [ACCESS DENIED / ANTI-ASSUMPTION GUARDRAIL]: Pembuatan '01-requirements.md' DICEGAT!\n"
                "Dokumen kebutuhan terdeteksi tidak memiliki elemen wajib:\n"
                "• '## 0. Discovery Log & Tanya-Jawab Kebutuhan Pengguna' (Wajib sesi wawancara langsung dengan Pengguna)\n"
                "• 'Referensi Boilerplate Resmi' (Wajib merujuk basis boilerplate proyek eksisting)\n\n"
                "⚠️ AI DILARANG menyusun PRD dari imajinasi/asumsi sepihak!\n"
                "PM wajib melakukan sesi wawancara klarifikasi langsung dengan Pengguna di Control Room terlebih dahulu."
            )

    # Blokir keras jika target adalah topics/ atau registry.yaml
    for pattern in PROTECTED_PATTERNS:
        if re.search(pattern, target_file):
            emit_decision(
                "deny",
                "🛑 [ACCESS DENIED / KNOWLEDGE GUARDRAIL]: Modifikasi langsung ke folder "
                "'.agents/knowledge/topics/' atau 'registry.yaml' DILARANG KERAS! "
                "Seluruh penambahan/perubahan knowledge WAJIB melalui gerbang draf resmi: "
                "'team-orch knowledge draft <topic_id>' dan hanya dapat disahkan oleh Manusia "
                "melalui 'team-orch knowledge approve <draft_id>'."
            )

# 2. Pengecekan tool run_command
elif tool_name == "run_command":
    cmd = str(args.get("CommandLine", ""))
    
    # Blokir keras jika AI agen mencoba mengeksekusi team-orch knowledge approve (Anti Self-Approval)
    if "team-orch knowledge approve" in cmd:
        emit_decision(
            "deny",
            "🛑 [ACCESS DENIED / HUMAN APPROVAL GATE]: AI DILARANG KERAS mengeksekusi 'team-orch knowledge approve'!\n"
            "Perintah pengesahan knowledge ini secara mutlak HANYA boleh dieksekusi secara manual oleh Pengguna Manusia di terminal Control Room.\n"
            "Tugas agen HANYA menyusun draf di .drafts/ dan mempresentasikan draf tersebut kepada Pengguna untuk ditinjau."
        )
        
    # Jika perintah shell mencoba memutasi topics/ atau registry.yaml (rm, cp, mv, echo >, sed, python overwrite)
    is_mutation = bool(re.search(r"\b(rm|cp|mv|touch|sed|echo|cat|python|sh|bash)\b", cmd))
    targets_protected = any(re.search(p, cmd) for p in PROTECTED_PATTERNS)
    
    if is_mutation and targets_protected and ".agents/knowledge/.drafts/" not in cmd:
        emit_decision(
            "deny",
            "🛑 [ACCESS DENIED / KNOWLEDGE GUARDRAIL]: Eksekusi shell yang memodifikasi langsung "
            "'.agents/knowledge/topics/' atau 'registry.yaml' dicegat oleh sistem. "
            "Gunakan jalur resmi: 'team-orch knowledge draft <topic_id>' lalu mintakan persetujuan Manusia."
        )

# Default: Loloskan eksekusi tool lainnya
emit_decision("allow")
