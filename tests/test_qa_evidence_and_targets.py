#!/usr/bin/env python3
"""
test_qa_evidence_and_targets.py - Test Suite for QA Targets Registry,
Dynamic Evidence Contracts, and 3-Layer Evidence Authenticity Verification.
Zero external dependencies (pure Python standard library).
"""

import sys
import os
import json
import unittest
import tempfile
import subprocess
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_UI_DIR = REPO_ROOT / ".agents" / "skills" / "ui-evidence-capture"
SKILL_QA_DIR = REPO_ROOT / ".agents" / "skills" / "qa-test-specialist"

# Add scripts directories to sys.path
sys.path.insert(0, str(SKILL_UI_DIR / "scripts"))

from backends.base import (
    validate_page_authenticity,
    DEFAULT_FORBIDDEN_ERROR_PATTERNS,
    parse_simple_yaml,
    load_yaml_file
)

# Dynamically import verify-qa-report.py
_spec = importlib.util.spec_from_file_location("verify_qa_report", SKILL_QA_DIR / "scripts" / "verify-qa-report.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate_qa_report = _mod.validate_qa_report

class TestQAEvidenceAndTargets(unittest.TestCase):
    def setUp(self):
        self.ui_capture_cli = SKILL_UI_DIR / "scripts" / "ui-capture.py"
        self.verify_qa_report_cli = SKILL_QA_DIR / "scripts" / "verify-qa-report.py"
        self.assertTrue(self.ui_capture_cli.exists(), f"ui-capture.py not found at {self.ui_capture_cli}")
        self.assertTrue(self.verify_qa_report_cli.exists(), f"verify-qa-report.py not found at {self.verify_qa_report_cli}")

    def test_01_rejects_object_not_found_and_404_pages(self):
        """1. validate_page_authenticity rejects 404, 502, blank content, and 'Object Not Found' text."""
        # 1.1 HTTP 404
        is_valid, reason = validate_page_authenticity(
            http_status=404,
            body_text="404 Not Found"
        )
        self.assertFalse(is_valid)
        self.assertIn("404", reason)

        # 1.2 Object Not Found (apigatewayui/) with HTTP 200
        is_valid, reason = validate_page_authenticity(
            http_status=200,
            body_text="<html><body>Object Not Found (apigatewayui/)</body></html>",
            page_title="Error"
        )
        self.assertFalse(is_valid)
        self.assertIn("Object Not Found", reason)

        # 1.3 502 Bad Gateway
        is_valid, reason = validate_page_authenticity(
            http_status=502,
            body_text="502 Bad Gateway"
        )
        self.assertFalse(is_valid)

        # 1.4 Blank or unrendered content (length < 10)
        is_valid, reason = validate_page_authenticity(
            http_status=200,
            body_text="   "
        )
        self.assertFalse(is_valid)
        self.assertIn("blank", reason.lower())

    def test_02_accepts_valid_portal_page_with_expected_text(self):
        """2. validate_page_authenticity accepts valid HTTP 200 portal page with expected business text."""
        body = """
        <div id="app">
          <h1>Portal Manajemen API Gateway</h1>
          <p>Daftar API Terdaftar: sample-gateway-service, payment-gateway</p>
          <div class="status">Status: ACTIVE</div>
        </div>
        """
        # With single string expected text
        is_valid, reason = validate_page_authenticity(
            http_status=200,
            body_text=body,
            page_title="Portal Manajemen API Gateway",
            expect_text="Portal Manajemen API Gateway"
        )
        self.assertTrue(is_valid)
        self.assertEqual(reason, "Page content is authentic")

        # With list of expected texts
        is_valid, reason = validate_page_authenticity(
            http_status=200,
            body_text=body,
            page_title="Portal Manajemen API Gateway",
            expect_text=["sample-gateway-service", "ACTIVE"]
        )
        self.assertTrue(is_valid)

        # Failure when expected text is missing
        is_valid, reason = validate_page_authenticity(
            http_status=200,
            body_text=body,
            page_title="Portal Manajemen API Gateway",
            expect_text="Halaman Pembayaran Pelanggan"
        )
        self.assertFalse(is_valid)
        self.assertIn("Expected text", reason)

    def test_03_allows_error_page_only_when_explicit_flag_set(self):
        """3. --allow-error-page flag permits error screenshots strictly for negative test cases."""
        # When allow_error_page=True, HTTP 404 is allowed
        is_valid, reason = validate_page_authenticity(
            http_status=404,
            body_text="404 Not Found - Skenario Uji Negatif",
            allow_error_page=True
        )
        self.assertTrue(is_valid)
        self.assertIn("allow-error-page", reason.lower())

        # When allow_error_page=True, forbidden error text is allowed
        is_valid, reason = validate_page_authenticity(
            http_status=500,
            body_text="Internal Server Error - Simulating Crash",
            allow_error_page=True
        )
        self.assertTrue(is_valid)

        # When allow_error_page=False, same input is rejected
        is_valid, reason = validate_page_authenticity(
            http_status=500,
            body_text="Internal Server Error - Simulating Crash",
            allow_error_page=False
        )
        self.assertFalse(is_valid)

    def test_04_ui_capture_targets_blocks_unconfirmed_url(self):
        """4. ui-capture targets blocks execution with exit code 3 if URL is unconfirmed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            targets_file = Path(tmpdir) / "qa-targets.yaml"
            targets_file.write_text("""
project_id: "test-proj"
ui_targets:
  admin_web_portal:
    name: "Gateway Web Management Portal"
    status: "NEEDS_HUMAN_URL_CONFIRMATION"
    base_url: ""
    human_confirmed: false
""", encoding="utf-8")

            # 4.1 Check targets: Should exit with Code 3 (NEEDS_HUMAN_URL_CONFIRMATION)
            res = subprocess.run(
                [
                    sys.executable, str(self.ui_capture_cli), "targets",
                    "--project", "test-proj",
                    "--targets-file", str(targets_file),
                    "--json"
                ],
                capture_output=True,
                text=True
            )
            self.assertEqual(res.returncode, 3, f"Expected exit code 3, got {res.returncode}. Output: {res.stdout}")
            data = json.loads(res.stdout)
            self.assertEqual(data.get("status"), "NEEDS_HUMAN_URL_CONFIRMATION")
            self.assertEqual(data.get("exit_code"), 3)

            # 4.2 Update target to confirmed state
            targets_file.write_text("""
project_id: "test-proj"
ui_targets:
  admin_web_portal:
    name: "Gateway Web Management Portal"
    status: "CONFIRMED"
    base_url: "https://portal.example.internal/web"
    human_confirmed: true
""", encoding="utf-8")

            # 4.3 Check targets again: Should exit with Code 0 (OK)
            res_confirmed = subprocess.run(
                [
                    sys.executable, str(self.ui_capture_cli), "targets",
                    "--project", "test-proj",
                    "--targets-file", str(targets_file),
                    "--json"
                ],
                capture_output=True,
                text=True
            )
            self.assertEqual(res_confirmed.returncode, 0, f"Expected exit code 0, got {res_confirmed.returncode}")
            data_confirmed = json.loads(res_confirmed.stdout)
            self.assertEqual(data_confirmed.get("status"), "confirmed")
            self.assertEqual(data_confirmed.get("exit_code"), 0)

    def test_05_verify_qa_report_validates_dynamic_evidence_spec(self):
        """5. verify-qa-report.py validates dynamic evidence spec contract and rejects REJECTED_ERROR_PAGE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            report_file = tmp_root / "tasks" / "test-proj" / "qa-test-report.md"
            report_file.parent.mkdir(parents=True, exist_ok=True)
            evidence_dir = tmp_root / "docs" / "qa" / "evidence" / "TC-15"
            evidence_dir.mkdir(parents=True, exist_ok=True)

            spec_file = tmp_root / "qa-evidence-spec.yaml"
            spec_file.write_text("""
project_id: "test-proj"
default_required_artifacts:
  - "03-verification-summary.txt"
per_tc_overrides:
  TC-15:
    required_artifacts:
      - "01-upstream-api-catalog-view.json"
      - "02-upstream-sync-status.txt"
      - "03-verification-summary.txt"
""", encoding="utf-8")

            # Valid full QA report content adhering to all 7 sections & 4 dimensions
            report_content = """# QA Test Report: test-proj

## 1. Metadata & Lingkup Pengujian
- Project: test-proj
- Tested: TC-15

## 2. 4-Dimensional Test Matrix Summary
- 1. Skenario Positif (Happy Path): Lolos
- 2. Skenario Batas & Negatif (Boundary): Lolos
- 3. Idempotensi & State Preservation: Lolos
- 4. Keamanan & Konkurensi (Race Condition): Lolos

## 3. Bukti Eksekusi Runtime & Assertion Logs
```bash
curl -X GET https://localhost:8080/health
```

## 4. Verifikasi Konkurensi & Race Condition
```bash
go test -race ./...
```

## 5. Keputusan Gatekeeper (Verdict)
VERDICT: PASSED

## 6. Matriks Triage Validasi (Auto vs Human)
- AUTO_VERIFIED: TC-1 s/d TC-14
- HUMAN_VALIDATION_REQUIRED: TC-15

## 7. Review & Sign-Off Analis
ANALYST STATUS: APPROVED
"""
            report_file.write_text(report_content, encoding="utf-8")

            # 5.1 Missing required artifacts -> should FAIL
            is_valid = validate_qa_report(report_file, evidence_spec_path=spec_file)
            self.assertFalse(is_valid, "Expected validation to fail due to missing TC-15 artifacts")

            # 5.2 Add all required artifacts
            (evidence_dir / "01-upstream-api-catalog-view.json").write_text("{}", encoding="utf-8")
            (evidence_dir / "02-upstream-sync-status.txt").write_text("SYNC OK", encoding="utf-8")
            (evidence_dir / "03-verification-summary.txt").write_text("VERIFIED", encoding="utf-8")

            # 5.3 Add capture-log.json with REJECTED_ERROR_PAGE -> should FAIL
            log_file = evidence_dir / "capture-log.json"
            log_file.write_text(json.dumps([
                {
                    "file": "REJECTED-ERROR-PAGE-portal.png",
                    "status": "REJECTED_ERROR_PAGE",
                    "rejection_reason": "Forbidden error text detected: 'Object Not Found'"
                }
            ], indent=2), encoding="utf-8")

            is_valid = validate_qa_report(report_file, evidence_spec_path=spec_file)
            self.assertFalse(is_valid, "Expected validation to fail due to unresolved REJECTED_ERROR_PAGE")

            # 5.4 Fix capture-log.json with verified entry -> should PASS
            log_file.write_text(json.dumps([
                {
                    "file": "01-upstream-api-catalog-view.json",
                    "status": "verified"
                }
            ], indent=2), encoding="utf-8")

            is_valid = validate_qa_report(report_file, evidence_spec_path=spec_file)
            self.assertTrue(is_valid, "Expected validation to pass when all artifacts and log statuses are verified")

if __name__ == "__main__":
    unittest.main()
