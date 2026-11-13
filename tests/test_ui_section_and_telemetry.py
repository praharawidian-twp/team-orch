#!/usr/bin/env python3
"""
test_ui_section_and_telemetry.py - Unit Test Suite for Section-Specific Capture,
Scoped Section Validation, and Zero-Vision-Token DOM Telemetry.
Zero external dependencies (pure Python standard library).
"""

import sys
import os
import json
import unittest
import tempfile
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_UI_DIR = REPO_ROOT / ".agents" / "skills" / "ui-evidence-capture"
SKILL_QA_DIR = REPO_ROOT / ".agents" / "skills" / "qa-test-specialist"

# Add scripts directories to sys.path
sys.path.insert(0, str(SKILL_UI_DIR / "scripts"))

from backends.base import (
    validate_section_target,
    build_dom_telemetry,
    validate_page_authenticity,
    DEFAULT_FORBIDDEN_ERROR_PATTERNS
)

# Dynamically import verify-qa-report.py
_spec = importlib.util.spec_from_file_location("verify_qa_report", SKILL_QA_DIR / "scripts" / "verify-qa-report.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate_qa_report = _mod.validate_qa_report

class TestUISectionAndTelemetry(unittest.TestCase):
    def test_01_section_validation_passes_valid_visible_section(self):
        """1. validate_section_target passes a visible section with valid bounding box and matching expected text."""
        bbox = {"x": 100, "y": 200, "width": 800, "height": 450}
        inner_text = "Daftar API Terdaftar | Service: sample-gateway-service | Status: ACTIVE | Version: 1.0.0"

        res = validate_section_target(
            section_found=True,
            is_visible=True,
            bounding_box=bbox,
            section_inner_text=inner_text,
            expect_section_text="sample-gateway-service, ACTIVE"
        )

        self.assertTrue(res["is_valid"])
        self.assertEqual(res["status"], "SECTION_VERIFIED")
        self.assertTrue(res["expected_text_matched"])
        self.assertEqual(res["bounding_box"], bbox)

    def test_02_section_validation_rejects_hidden_or_zero_size_section(self):
        """2. validate_section_target rejects not found, invisible, or zero-sized sections."""
        # 2.1 Section not found
        res_not_found = validate_section_target(
            section_found=False,
            is_visible=False,
            bounding_box=None,
            section_inner_text=""
        )
        self.assertFalse(res_not_found["is_valid"])
        self.assertEqual(res_not_found["status"], "REJECTED_SECTION_NOT_VISIBLE")

        # 2.2 Section found but not visible
        res_hidden = validate_section_target(
            section_found=True,
            is_visible=False,
            bounding_box={"x": 0, "y": 0, "width": 100, "height": 100},
            section_inner_text="Hidden element"
        )
        self.assertFalse(res_hidden["is_valid"])
        self.assertEqual(res_hidden["status"], "REJECTED_SECTION_NOT_VISIBLE")

        # 2.3 Section has 0 width or height (collapsed or display:none)
        res_zero = validate_section_target(
            section_found=True,
            is_visible=True,
            bounding_box={"x": 50, "y": 50, "width": 0, "height": 0},
            section_inner_text="Zero size"
        )
        self.assertFalse(res_zero["is_valid"])
        self.assertEqual(res_zero["status"], "REJECTED_SECTION_ZERO_SIZE")

        # 2.4 Section contains forbidden error patterns
        res_err = validate_section_target(
            section_found=True,
            is_visible=True,
            bounding_box={"x": 100, "y": 100, "width": 500, "height": 300},
            section_inner_text="Container error: Object Not Found (apigatewayui/)"
        )
        self.assertFalse(res_err["is_valid"])
        self.assertEqual(res_err["status"], "REJECTED_ERROR_IN_SECTION")

    def test_03_section_validation_rejects_mismatched_scoped_text(self):
        """3. validate_section_target rejects if expected section text is missing from target section content."""
        bbox = {"x": 100, "y": 200, "width": 600, "height": 300}
        section_text = "Laporan Transaksi Harian | Total Transaksi: 150"

        # Missing expected text in section
        res_mismatch = validate_section_target(
            section_found=True,
            is_visible=True,
            bounding_box=bbox,
            section_inner_text=section_text,
            expect_section_text="Konfirmasi Pembayaran Tagihan"
        )
        self.assertFalse(res_mismatch["is_valid"])
        self.assertEqual(res_mismatch["status"], "REJECTED_SECTION_TEXT_MISMATCH")
        self.assertIn("Konfirmasi Pembayaran Tagihan", res_mismatch["reason"])

    def test_04_dom_telemetry_zero_vision_token_flag(self):
        """4. build_dom_telemetry flags vision_check_needed=False for normal pages, and True for suspicious blank."""
        # 4.1 Normal authentic page with good size & DOM text -> vision_check_needed is False
        normal_telemetry = build_dom_telemetry(
            page_title="Portal API Gateway",
            visible_headings=["API Overview", "Active Endpoints"],
            visible_text_excerpt="Daftar endpoint layanan yang aktif dan terdaftar pada cluster...",
            interactive_counts={"buttons": 5, "inputs": 2, "tables": 1, "links": 12},
            file_size_bytes=48500,
            mode="highlight"
        )
        self.assertFalse(normal_telemetry["is_suspicious_blank"])
        self.assertFalse(normal_telemetry["vision_check_needed"])
        self.assertEqual(normal_telemetry["page_title"], "Portal API Gateway")
        self.assertEqual(len(normal_telemetry["visible_headings"]), 2)
        self.assertEqual(normal_telemetry["file_size_bytes"], 48500)

        # 4.2 Suspicious blank screen (file size < 15KB) -> vision_check_needed is True
        blank_telemetry = build_dom_telemetry(
            page_title="",
            visible_headings=[],
            visible_text_excerpt="",
            interactive_counts={"buttons": 0, "inputs": 0, "tables": 0, "links": 0},
            file_size_bytes=8200,
            mode="highlight"
        )
        self.assertTrue(blank_telemetry["is_suspicious_blank"])
        self.assertTrue(blank_telemetry["vision_check_needed"])

        # 4.3 Crop mode with valid text is NOT flagged suspicious despite smaller file size
        crop_telemetry = build_dom_telemetry(
            page_title="Portal API",
            visible_headings=["Card"],
            visible_text_excerpt="Active Status Card",
            interactive_counts={"buttons": 1, "inputs": 0, "tables": 0, "links": 0},
            file_size_bytes=11200,
            mode="crop"
        )
        self.assertFalse(crop_telemetry["is_suspicious_blank"])
        self.assertFalse(crop_telemetry["vision_check_needed"])

    def test_05_verify_qa_report_rejects_failed_section_captures(self):
        """5. verify-qa-report.py rejects capture-log.json containing unresolved REJECTED_SECTION_* entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            report_file = tmp_root / "tasks" / "test-proj" / "qa-test-report.md"
            report_file.parent.mkdir(parents=True, exist_ok=True)
            evidence_dir = tmp_root / "docs" / "qa" / "evidence" / "TC-15"
            evidence_dir.mkdir(parents=True, exist_ok=True)

            spec_file = tmp_root / "qa-evidence-spec.yaml"
            spec_file.write_text("""
project_id: "test-proj"
per_tc_overrides:
  TC-15:
    required_artifacts:
      - "01-summary.txt"
""", encoding="utf-8")

            # Minimal valid QA report content satisfying all 7 sections
            report_file.write_text("""# QA Report
## 1. Metadata & Lingkup Pengujian
Project test
## 2. 4-Dimensional Test Matrix Summary
- 1. Skenario Positif (Happy Path)
- 2. Skenario Batas & Negatif (Boundary)
- 3. Idempotensi & State Preservation
- 4. Keamanan & Konkurensi (Race Condition)
## 3. Bukti Eksekusi Runtime & Assertion Logs
```bash
curl http://localhost
```
## 4. Verifikasi Konkurensi & Race Condition
```bash
go test -race ./...
```
## 5. Keputusan Gatekeeper (Verdict)
VERDICT: PASSED
## 6. Matriks Triage Validasi (Auto vs Human)
- AUTO_VERIFIED
- HUMAN_VALIDATION_REQUIRED: TC-15
## 7. Review & Sign-Off Analis
ANALYST STATUS: APPROVED
""", encoding="utf-8")

            (evidence_dir / "01-summary.txt").write_text("OK", encoding="utf-8")
            log_file = evidence_dir / "capture-log.json"

            # 5.1 Case A: capture-log.json has REJECTED_SECTION_NOT_VISIBLE -> should FAIL
            log_file.write_text(json.dumps([
                {
                    "file": "REJECTED-SECTION-REJECTED_SECTION_NOT_VISIBLE-modal.png",
                    "status": "REJECTED_SECTION_NOT_VISIBLE",
                    "rejection_reason": "Target section was not found or is not visible in DOM"
                }
            ], indent=2), encoding="utf-8")

            is_valid = validate_qa_report(report_file, evidence_spec_path=spec_file)
            self.assertFalse(is_valid, "Expected validation to fail due to REJECTED_SECTION_NOT_VISIBLE")

            # 5.2 Case B: capture-log.json has REJECTED_SECTION_TEXT_MISMATCH -> should FAIL
            log_file.write_text(json.dumps([
                {
                    "file": "REJECTED-SECTION-REJECTED_SECTION_TEXT_MISMATCH-table.png",
                    "status": "REJECTED_SECTION_TEXT_MISMATCH",
                    "rejection_reason": "Expected section text not found in targeted section"
                }
            ], indent=2), encoding="utf-8")

            is_valid = validate_qa_report(report_file, evidence_spec_path=spec_file)
            self.assertFalse(is_valid, "Expected validation to fail due to REJECTED_SECTION_TEXT_MISMATCH")

            # 5.3 Case C: Fixed with verified section entry -> should PASS
            log_file.write_text(json.dumps([
                {
                    "file": "01-modal.png",
                    "status": "verified",
                    "section_validation": {
                        "status": "SECTION_VERIFIED",
                        "is_visible": True
                    }
                }
            ], indent=2), encoding="utf-8")

            is_valid = validate_qa_report(report_file, evidence_spec_path=spec_file)
            self.assertTrue(is_valid, "Expected validation to pass when section entry is verified")

if __name__ == "__main__":
    unittest.main()
