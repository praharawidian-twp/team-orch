#!/usr/bin/env python3
"""
verify-qa-report.py - Deterministic Validator for QA Validation Gate Reports.

Validates that a QA report adheres strictly to the Enterprise QA Validation Gate standard:
1. Contains all 7 mandatory sections:
   - 1. Metadata & Lingkup Pengujian
   - 2. 4-Dimensional Test Matrix Summary
   - 3. Bukti Eksekusi Runtime & Assertion Logs
   - 4. Verifikasi Konkurensi & Race Condition
   - 5. Keputusan Gatekeeper (Verdict)
   - 6. Matriks Triage Validasi (Auto-Verified vs Human Validation Required)
   - 7. Review & Sign-Off Analis (Field-Realism Audit & Lead Directive)
2. Explicitly covers all 4 dimensions (Positive, Negative/Boundary, Idempotency/State, Security/Race).
3. Contains real execution logs and test commands.
4. Contains explicit final technical verdict (VERDICT: PASSED or VERDICT: REJECTED).
5. Contains explicit UAT Validation Triage categories (AUTO_VERIFIED and HUMAN_VALIDATION_REQUIRED).
6. Contains explicit Analyst Sign-Off (APPROVED or NEEDS_QA_REVISION).
"""

import sys
import os
import re
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List

def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Zero-dependency lightweight YAML parser for dictionaries and lists."""
    root = {}
    lines = text.splitlines()
    stack = [(-1, root, None)]

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.rstrip()
        i += 1
        if not line or line.strip().startswith('#'):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        # Check list item
        if stripped.startswith('- '):
            val = stripped[2:].strip().strip('\"\'')
            if ' #' in val:
                val = val.split(' #', 1)[0].strip().strip('\"\'')
            if val.lower() == 'true': val = True
            elif val.lower() == 'false': val = False
            elif val.lower() in ('null', '~'): val = None

            while stack and stack[-1][0] >= indent:
                stack.pop()

            parent = stack[-1][1]
            parent_key = stack[-1][2]
            if isinstance(parent, list):
                parent.append(val)
            elif parent_key and isinstance(parent.get(parent_key), list):
                parent[parent_key].append(val)
            continue

        if ':' in stripped:
            parts = stripped.split(':', 1)
            k = parts[0].strip()
            raw_v = parts[1].strip()
            if ' #' in raw_v:
                raw_v = raw_v.split(' #', 1)[0].strip()

            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1]

            if not raw_v:
                # Lookahead to see if next non-empty line starts with '- '
                next_is_list = False
                for j in range(i, len(lines)):
                    nxt = lines[j].strip()
                    if nxt and not nxt.startswith('#'):
                        if nxt.startswith('- '):
                            next_is_list = True
                        break

                if next_is_list:
                    new_list = []
                    parent[k] = new_list
                    stack.append((indent, parent, k))
                else:
                    new_dict = {}
                    parent[k] = new_dict
                    stack.append((indent, new_dict, None))
            else:
                v = raw_v.strip('\"\'')
                if v.lower() == 'true': v = True
                elif v.lower() == 'false': v = False
                elif v.lower() in ('null', '~'): v = None
                parent[k] = v

    return root

def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        return {}
    try:
        return parse_simple_yaml(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

REQUIRED_SECTIONS = [
    ("1. Metadata & Lingkup Pengujian", [r"#+\s*(?:1\.\s*)?metadata", r"#+\s*lingkup pengujian"]),
    ("2. 4-Dimensional Test Matrix Summary", [r"#+\s*(?:2\.\s*)?4-dimensional test matrix", r"#+\s*matriks uji 4-dimensi"]),
    ("3. Bukti Eksekusi Runtime & Assertion Logs", [r"#+\s*(?:3\.\s*)?bukti eksekusi runtime", r"#+\s*runtime evidence", r"#+\s*assertion logs"]),
    ("4. Verifikasi Konkurensi & Race Condition", [r"#+\s*(?:4\.\s*)?verifikasi konkurensi", r"#+\s*race condition", r"#+\s*concurrency"]),
    ("5. Keputusan Gatekeeper (Verdict)", [r"#+\s*(?:5\.\s*)?keputusan gatekeeper", r"#+\s*verdict"]),
    ("6. Matriks Triage Validasi (Auto vs Human)", [r"#+\s*(?:6\.\s*)?matriks triage validasi", r"#+\s*triage validasi", r"#+\s*auto-verified.*human validation"]),
    ("7. Review & Sign-Off Analis", [r"#+\s*(?:7\.\s*)?review\s*&\s*sign-off analis", r"#+\s*field-realism audit", r"#+\s*lead directive"])
]

REQUIRED_DIMENSIONS = [
    ("1. Skenario Positif (Happy Path)", [r"positif", r"happy path", r"functional acceptance"]),
    ("2. Skenario Batas & Negatif (Boundary)", [r"negatif", r"negative", r"boundary", r"error"]),
    ("3. Idempotensi & State Preservation", [r"idempotensi", r"idempotency", r"state preservation", r"only_new", r"dry_run"]),
    ("4. Keamanan & Konkurensi (Race Condition)", [r"keamanan", r"security", r"konkurensi", r"race", r"concurrency"])
]

def validate_qa_report(report_path: Path, evidence_spec_path: Optional[Path] = None) -> bool:
    print(f"[*] Validating QA Validation Report: {report_path.name}")
    
    if not report_path.exists():
        print(f"[✗] Error: File does not exist: {report_path}")
        return False

    content = report_path.read_text(encoding="utf-8")
    if not content.strip():
        print(f"[✗] Error: File is empty: {report_path}")
        return False

    passed = True
    content_lower = content.lower()

    # 1. Check Mandatory Sections (All 7 Sections)
    print("\n--- 1. Struktur 7 Bab Wajib ---")
    for sec_name, patterns in REQUIRED_SECTIONS:
        found = any(re.search(pat, content_lower) for pat in patterns)
        if found:
            print(f"  [✓] {sec_name}")
        else:
            print(f"  [✗] MISSING SECTION: {sec_name}")
            passed = False

    # 2. Check 4-Dimensional Test Matrix Coverage
    print("\n--- 2. Cakupan 4-Dimensional Test Matrix ---")
    for dim_name, patterns in REQUIRED_DIMENSIONS:
        found = any(re.search(pat, content_lower) for pat in patterns)
        if found:
            print(f"  [✓] {dim_name}")
        else:
            print(f"  [✗] MISSING DIMENSION: {dim_name}")
            passed = False

    # 3. Check Real Execution Evidence
    print("\n--- 3. Bukti Eksekusi & Test Logs ---")
    has_cli_cmd = bool(re.search(r"```(?:bash|sh|text|json)?[\s\S]*?(?:bru|go test|curl|http|test)[\s\S]*?```", content_lower))
    if has_cli_cmd:
        print("  [✓] Bukti log perintah terminal / assertion output terdeteksi")
    else:
        print("  [✗] Tidak ditemukan blok bukti eksekusi perintah terminal (bru / go test / curl)")
        passed = False

    # 4. Check Explicit Technical Verdict
    print("\n--- 4. Keputusan Gatekeeper (Verdict) ---")
    has_passed = "verdict: passed" in content_lower
    has_rejected = "verdict: rejected" in content_lower

    if has_passed and not has_rejected:
        print("  [✓] Status Verdict Teknis: PASSED")
    elif has_rejected and not has_passed:
        print("  [✓] Status Verdict Teknis: REJECTED (Bug Rejection Loop aktif)")
    elif has_passed and has_rejected:
        print("  [✗] Konflik Status Teknis: Ditemukan PASSED dan REJECTED secara bersamaan")
        passed = False
    else:
        print("  [✗] Format Verdict tidak ditemukan! Wajib mencantumkan 'VERDICT: PASSED' atau 'VERDICT: REJECTED'")
        passed = False

    # 5. Check UAT Validation Triage Categories
    print("\n--- 5. UAT Validation Triage Categories ---")
    has_auto_verified = bool(re.search(r"auto[_\s-]verified", content_lower))
    has_human_validation = bool(re.search(r"human[_\s-]validation[_\s-]required", content_lower))

    if has_auto_verified:
        print("  [✓] Label Triage AUTO_VERIFIED terdeteksi")
    else:
        print("  [✗] Label Triage AUTO_VERIFIED tidak ditemukan di laporan!")
        passed = False

    if has_human_validation:
        print("  [✓] Label Triage HUMAN_VALIDATION_REQUIRED terdeteksi")
    else:
        print("  [✗] Label Triage HUMAN_VALIDATION_REQUIRED tidak ditemukan di laporan!")
        passed = False

    # 6. Check Analyst Review & Sign-Off
    print("\n--- 6. Review & Sign-Off Analis (Field-Realism Audit) ---")
    has_analyst_approved = bool(re.search(r"(?:analyst\s*status[:\s]+approved|status\s*review\s*analis[:\s]+approved)", content_lower))
    has_analyst_revision = bool(re.search(r"(?:analyst\s*status[:\s]+needs_qa_revision|status\s*review\s*analis[:\s]+needs_qa_revision)", content_lower))

    if has_analyst_approved and not has_analyst_revision:
        print("  [✓] Status Sign-Off Analis: APPROVED (Lolos Field-Realism Audit)")
    elif has_analyst_revision and not has_analyst_approved:
        print("  [✓] Status Sign-Off Analis: NEEDS_QA_REVISION (Menunggu revisi skenario QA)")
    elif has_analyst_approved and has_analyst_revision:
        print("  [✗] Konflik Status Analis: Ditemukan APPROVED dan NEEDS_QA_REVISION bersamaan")
        passed = False
    else:
        print("  [✗] Status Review Analis tidak ditemukan! Wajib mencantumkan 'ANALYST STATUS: APPROVED' atau 'NEEDS_QA_REVISION'")
        passed = False

    # 7. Check UI Screenshot Evidence & Capture Logs (Layer 3 Integrity Check)
    print("\n--- 7. Verifikasi Bukti Tangkapan Layar UI & Capture Logs ---")
    evidence_dirs = [
        report_path.parent.parent.parent / "docs" / "qa" / "evidence",
        Path.cwd() / "docs" / "qa" / "evidence",
        report_path.parent / "docs" / "qa" / "evidence"
    ]
    evidence_root = next((d for d in evidence_dirs if d.exists()), None)
    
    if evidence_root and evidence_root.is_dir():
        # Scan all capture-log.json for rejected error pages
        for log_path in evidence_root.glob("TC-*/capture-log.json"):
            tc_name = log_path.parent.name
            try:
                logs = json.loads(log_path.read_text(encoding="utf-8"))
                if isinstance(logs, list):
                    for entry in logs:
                        st = entry.get("status", "")
                        if st.startswith("REJECTED_"):
                            # Check if replaced by verified entry
                            rej_file = entry.get("file", "")
                            base_target = re.sub(r"^REJECTED-(?:ERROR-PAGE|SECTION-[A-Z_]+)-", "", rej_file)
                            is_replaced = any(e.get("file") == base_target and e.get("status") == "verified" for e in logs)
                            if not is_replaced:
                                print(f"  [✗] REJECTED SCREENSHOT DETECTED in {tc_name}: {rej_file} (status: {st}, reason: {entry.get('rejection_reason')})")
                                passed = False
            except Exception as e:
                print(f"  [!] Warning reading {log_path}: {e}")

    shot_matches = re.findall(r"(TC-\d+)[\s\S]{0,100}?(?:screenshot|\.png|tangkapan layar)", content, re.IGNORECASE)
    if shot_matches and evidence_root:
        for tc_id in sorted(set(shot_matches)):
            tc_dir = evidence_root / tc_id
            if tc_dir.exists():
                png_files = list(tc_dir.glob("*.png"))
                has_log = (tc_dir / "capture-log.json").exists()
                has_guide = (tc_dir / "README-EVIDENCE-GUIDE.txt").exists()
                if png_files and has_log:
                    print(f"  [✓] Bukti screenshot & capture-log.json terverifikasi di {tc_id}")
                elif has_guide:
                    print(f"  [!] NOTICE: Bukti screenshot {tc_id} berstatus panduan manual (README-EVIDENCE-GUIDE.txt)")
                else:
                    print(f"  [!] WARNING: Referensi screenshot pada {tc_id} belum memiliki file .png atau capture-log.json")
    else:
        print("  [✓] Tidak ada referensi screenshot khusus atau folder evidence siap diuji")

    # 8. Check Dynamic Evidence Spec (if provided)
    if evidence_spec_path:
        print(f"\n--- 8. Verifikasi Kontrak Evidence Dinamis ({evidence_spec_path.name}) ---")
        if not evidence_spec_path.exists():
            print(f"  [✗] File evidence spec tidak ditemukan: {evidence_spec_path}")
            passed = False
        else:
            spec = load_yaml_file(evidence_spec_path)
            default_artifacts = spec.get("default_required_artifacts", [])
            overrides = spec.get("per_tc_overrides", {})

            # Gather all test cases with overrides or present in evidence_root
            all_tcs = set(overrides.keys())
            if evidence_root and evidence_root.is_dir():
                for tc_dir in evidence_root.glob("TC-*"):
                    if tc_dir.is_dir():
                        all_tcs.add(tc_dir.name)

            for tc_id in sorted(all_tcs):
                tc_dir = (evidence_root / tc_id) if evidence_root else None
                reqs = list(default_artifacts)
                if tc_id in overrides and isinstance(overrides[tc_id], dict):
                    ov = overrides[tc_id]
                    if "required_artifacts" in ov:
                        reqs = ov["required_artifacts"]

                for art in reqs:
                    if not tc_dir or not (tc_dir / art).exists():
                        print(f"  [✗] MISSING REQUIRED ARTIFACT in {tc_id}: '{art}' (Kontrak: {evidence_spec_path.name})")
                        passed = False
                    else:
                        print(f"  [✓] {tc_id} -> '{art}' hadir dan terverifikasi")

    print("\n-------------------------------------------")
    if passed:
        print("[✓] SUCCESS: Laporan QA memenuhi 100% kriteria Enterprise Validation Gate & Lead Review.")
    else:
        print("[✗] FAILED: Laporan QA tidak lengkap atau tidak memenuhi standar.")
    return passed

def main():
    parser = argparse.ArgumentParser(description="Deterministic Validator for QA Validation Gate Reports.")
    parser.add_argument("report_path", help="Path ke berkas laporan QA markdown")
    parser.add_argument("--evidence-spec", help="Path ke berkas kontrak evidence dinamis qa-evidence-spec.yaml")
    args = parser.parse_args()

    report_path = Path(args.report_path)
    spec_path = Path(args.evidence_spec) if args.evidence_spec else None

    is_valid = validate_qa_report(report_path, evidence_spec_path=spec_path)
    sys.exit(0 if is_valid else 1)

if __name__ == "__main__":
    main()
