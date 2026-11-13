#!/usr/bin/env python3
"""
anti-assumption-guardrail.py - PreToolUse Guardrail Hook
Mencegah agen AI menyusun dokumen 01-requirements.md (PRD) secara sepihak
berdasarkan asumsi/imajinasi tanpa proses wawancara Discovery langsung dengan Pengguna
dan tanpa menentukan referensi boilerplate resmi.
"""

import json
import re
import sys

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

# Hanya periksa penulisan berkas 01-requirements.md
if tool_name in ["write_to_file", "replace_file_content"]:
    target_file = str(args.get("TargetFile", ""))
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
        
        # Validasi 1: Wajib ada sesi Discovery Log / Tanya-Jawab
        has_discovery = bool(re.search(r"(Discovery Log|Tanya-Jawab Kebutuhan|Wawancara Kebutuhan|Requirement Discovery)", content, re.IGNORECASE))
        
        # Validasi 2: Wajib ada penentuan basis Boilerplate resmi
        has_boilerplate = bool(re.search(r"(Boilerplate Reference|Basis Boilerplate|Referensi Boilerplate)", content, re.IGNORECASE))
        
        if not (has_discovery and has_boilerplate):
            missing = []
            if not has_discovery:
                missing.append("• Bagian 'Discovery Log & Tanya-Jawab Kebutuhan' (Wajib sesi wawancara riil dengan Pengguna)")
            if not has_boilerplate:
                missing.append("• Bagian 'Referensi Boilerplate' (Wajib merujuk basis repositori/arketipe boilerplate resmi)")
            
            missing_msg = "\n".join(missing)
            emit_decision(
                "deny",
                f"🛑 [ACCESS DENIED / ANTI-ASSUMPTION GUARDRAIL]: Pembuatan '01-requirements.md' DICEGAT!\n\n"
                f"Dokumen kebutuhan terdeteksi tidak memiliki elemen wajib berikut:\n{missing_msg}\n\n"
                f"⚠️ ATURAN KERNEL: AI DILARANG KERAS menyusun PRD dari imajinasi/asumsi sepihak!\n"
                f"PM wajib melakukan wawancara klarifikasi langsung dengan Pengguna di Control Room terlebih dahulu, "
                f"lalu mencatat transkrip kesepakatan tersebut di dalam PRD."
            )

# Loloskan eksekusi tool lainnya
emit_decision("allow")
