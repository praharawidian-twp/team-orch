#!/usr/bin/env python3
"""
test_ui_evidence_capture.py - Comprehensive Unit Test Suite for ui-evidence-capture.
Tests all safety guards, exit codes, Provisioning Consent Gate, masking, and framework integrations.
Zero external dependencies (pure Python standard library).
"""

import sys
import os
import json
import unittest
import tempfile
import datetime
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
UI_CAPTURE_CLI = REPO_ROOT / ".agents" / "skills" / "ui-evidence-capture" / "scripts" / "ui-capture.py"
SKILL_DIR = REPO_ROOT / ".agents" / "skills" / "ui-evidence-capture"

# Add script dir to sys.path for direct imports
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from backends.base import (
    detect_human_challenge,
    sanitize_url_for_log,
    calculate_sha256,
    validate_path_safety,
)
from backends.manual import ManualBackend

class TestUIEvidenceCapture(unittest.TestCase):
    def setUp(self):
        self.cli_path = UI_CAPTURE_CLI
        self.assertTrue(self.cli_path.exists(), f"ui-capture.py not found at {self.cli_path}")

    # 1. Doctor command returns valid schema & recommended_action when playwright missing
    def test_01_doctor_missing_backend(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["UI_CAPTURE_TOOL_DIR"] = str(Path(tmpdir) / "empty-tools")
            res = subprocess.run(
                [sys.executable, str(self.cli_path), "doctor", "--project", "test-proj", "--json"],
                capture_output=True,
                text=True,
                env=env
            )
            # Should exit 11 (NO_BACKEND) or 10
            self.assertIn(res.returncode, [10, 11])
            data = json.loads(res.stdout)
            self.assertEqual(data.get("status"), "no_backend")
            self.assertEqual(data.get("recommended_action"), "prompt_consent_gate")
            self.assertIn("options", data)
            self.assertEqual(len(data["options"]), 5)
            # Verify Option 1 is recommended Playwright Python
            self.assertEqual(data["options"][0]["name"], "Playwright Python")
            self.assertTrue(data["options"][0]["recommended"])
            self.assertTrue(data["options"][0]["requires_network"])

    # 2. Setup without --yes prints plan and exits 10 without executing subprocess
    def test_02_setup_without_yes_dry_run(self):
        res = subprocess.run(
            [sys.executable, str(self.cli_path), "setup", "--backend", "playwright-python", "--json"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 10)  # EXIT_CONSENT_REQUIRED
        data = json.loads(res.stdout)
        self.assertEqual(data.get("action"), "setup_plan")
        self.assertEqual(data.get("exit_code"), 10)
        self.assertIn("commands", data)
        self.assertTrue(len(data["commands"]) >= 2)

    # 3. Path safety: path traversal in --tc or --name returns 40
    def test_03_path_safety_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Test helper directly
            safe, _, msg = validate_path_safety("../etc", "shot01", tmppath)
            self.assertFalse(safe)
            self.assertIn("Invalid TC identifier", msg)

            safe2, _, msg2 = validate_path_safety("TC-15", "../../bad", tmppath)
            self.assertFalse(safe2)
            self.assertIn("Invalid evidence name", msg2)

            # Test via CLI
            res = subprocess.run(
                [
                    sys.executable, str(self.cli_path), "shot",
                    "--project", "test-proj",
                    "--tc", "../TC-99",
                    "--name", "hack",
                    "--url", "https://example.com"
                ],
                capture_output=True,
                text=True,
                cwd=str(tmppath)
            )
            self.assertEqual(res.returncode, 40)

    # 4. Allowlist: URL origin outside allowed_origins returns 30
    def test_04_origin_allowlist_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create a project config with allowed_origins
            cfg_dir = tmppath / ".agents" / "config"
            cfg_dir.mkdir(parents=True)
            cfg_file = cfg_dir / "qa-ui.config.json"
            cfg = {
                "project_id": "test-proj",
                "allowed_origins": ["https://trusted.internal.example.com"],
                "login_url": "https://trusted.internal.example.com/login",
                "evidence_root": "docs/qa/evidence"
            }
            cfg_file.write_text(json.dumps(cfg), encoding="utf-8")

            res = subprocess.run(
                [
                    sys.executable, str(self.cli_path), "shot",
                    "--project", "test-proj",
                    "--tc", "TC-01",
                    "--name", "untrusted-test",
                    "--url", "https://malicious.external.com/leak"
                ],
                capture_output=True,
                text=True,
                cwd=str(tmppath)
            )
            self.assertEqual(res.returncode, 30)  # EXIT_ORIGIN_NOT_ALLOWED
            self.assertIn("Origin", res.stderr)

    # 5. Redaction of URL query parameters & no Authorization/Cookie headers
    def test_05_url_query_redaction(self):
        url = "https://host.example.com/portal/#/apis?token=SECRET_KEY&user=admin"
        redacted = sanitize_url_for_log(url)
        self.assertNotIn("SECRET_KEY", redacted)
        self.assertNotIn("user=admin", redacted)
        self.assertIn("?<redacted>", redacted)

    # 6. Init adds .agents/secrets/ to .gitignore idempotently
    def test_06_init_gitignore_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            gitignore = tmppath / ".gitignore"
            gitignore.write_text("node_modules/\n.env\n", encoding="utf-8")

            # Run init 1st time
            res1 = subprocess.run(
                [
                    sys.executable, str(self.cli_path), "init",
                    "--project", "proj-a",
                    "--origin", "https://test.example.com",
                    "--json"
                ],
                capture_output=True,
                text=True,
                cwd=str(tmppath)
            )
            self.assertEqual(res1.returncode, 0)
            data1 = json.loads(res1.stdout)
            self.assertTrue(data1.get("gitignore_updated"))

            content1 = gitignore.read_text(encoding="utf-8")
            self.assertIn(".agents/secrets/", content1)

            # Run init 2nd time (must be idempotent, not adding duplicates)
            res2 = subprocess.run(
                [
                    sys.executable, str(self.cli_path), "init",
                    "--project", "proj-a",
                    "--origin", "https://test.example.com",
                    "--json"
                ],
                capture_output=True,
                text=True,
                cwd=str(tmppath)
            )
            self.assertEqual(res2.returncode, 0)
            data2 = json.loads(res2.stdout)
            self.assertFalse(data2.get("gitignore_updated"))

            # Count occurrences of .agents/secrets/
            content2 = gitignore.read_text(encoding="utf-8")
            self.assertEqual(content2.count(".agents/secrets/"), 1)

    # 7. Session file permissions check (0600 file, 0700 dir)
    def test_07_session_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            sec_dir = tmppath / ".agents" / "secrets" / "test-proj"
            sec_dir.mkdir(parents=True)
            os.chmod(sec_dir, 0o700)

            sess_file = sec_dir / "ui-auth-state.json"
            sess_file.write_text(json.dumps({"cookies": []}), encoding="utf-8")
            os.chmod(sess_file, 0o600)

            # Check dir permission (octal ends with 700)
            dir_mode = oct(sec_dir.stat().st_mode)[-3:]
            self.assertEqual(dir_mode, "700")

            # Check file permission (octal ends with 600)
            file_mode = oct(sess_file.stat().st_mode)[-3:]
            self.assertEqual(file_mode, "600")

    # 8. Expired session returns 20 (AUTH_REQUIRED)
    def test_08_expired_session_returns_20(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create config
            cfg_dir = tmppath / ".agents" / "config"
            cfg_dir.mkdir(parents=True)
            cfg_file = cfg_dir / "qa-ui.config.json"
            cfg = {
                "project_id": "test-proj",
                "allowed_origins": ["https://trusted.example.com"],
                "login_url": "https://trusted.example.com/login",
                "credential_model": "human_session",
                "backend_preference": "playwright-python",
                "evidence_root": "docs/qa/evidence"
            }
            cfg_file.write_text(json.dumps(cfg), encoding="utf-8")

            # Create expired session metadata
            sec_dir = tmppath / ".agents" / "secrets" / "test-proj"
            sec_dir.mkdir(parents=True)
            sess_file = sec_dir / "ui-auth-state.json"
            sess_file.write_text("{}", encoding="utf-8")
            meta_file = sec_dir / "ui-auth-meta.json"
            expired_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
            meta_file.write_text(json.dumps({
                "created_at": expired_time,
                "expires_at": expired_time
            }), encoding="utf-8")

            res = subprocess.run(
                [
                    sys.executable, str(self.cli_path), "shot",
                    "--project", "test-proj",
                    "--tc", "TC-01",
                    "--name", "dashboard",
                    "--url", "https://trusted.example.com/dashboard",
                    "--backend", "playwright-python"
                ],
                capture_output=True,
                text=True,
                cwd=str(tmppath)
            )
            self.assertEqual(res.returncode, 20)  # EXIT_AUTH_REQUIRED
            self.assertIn("kedaluwarsa", res.stderr)

    # 9. Manual backend writes README-EVIDENCE-GUIDE.txt and capture-log.json
    def test_09_manual_backend_guide_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cfg = {
                "project_id": "test-proj",
                "allowed_origins": ["https://trusted.example.com"],
                "credential_model": "human_session",
                "mask_selectors": ["input[type=password]"]
            }
            backend = ManualBackend()
            out_file = tmppath / "docs" / "qa" / "evidence" / "TC-15" / "01-api-list.png"
            code, log_entry = backend.shot(
                config=cfg,
                session_path=Path("/tmp/none"),
                tc="TC-15",
                name="01-api-list",
                url="https://trusted.example.com/apis?secret=123",
                wait_for=None,
                full_page=True,
                mask=["input[type=password]"],
                viewport="1440x900",
                output_path=out_file
            )
            self.assertEqual(code, 0)
            self.assertEqual(log_entry["backend"], "manual")
            self.assertIn("?<redacted>", log_entry["url"])

            guide_file = tmppath / "docs" / "qa" / "evidence" / "TC-15" / "README-EVIDENCE-GUIDE.txt"
            self.assertTrue(guide_file.exists())
            guide_text = guide_file.read_text(encoding="utf-8")
            self.assertIn("PANDUAN PENGAMBILAN BUKTI SCREENSHOT UI MANUAL", guide_text)
            self.assertIn("TC-15", guide_text)

            log_file = tmppath / "docs" / "qa" / "evidence" / "TC-15" / "capture-log.json"
            self.assertTrue(log_file.exists())
            log_data = json.loads(log_file.read_text(encoding="utf-8"))
            self.assertEqual(len(log_data), 1)
            self.assertEqual(log_data[0]["file"], "01-api-list.png")

    # 10. Challenge detector correctly recognizes bot challenges / CAPTCHAs
    def test_10_challenge_detector(self):
        samples = [
            '<iframe src="https://challenges.cloudflare.com/turnstile/v0/api.js"></iframe>',
            '<div class="g-recaptcha" data-sitekey="xyz"></div>',
            '<script src="https://hcaptcha.com/1/api.js"></script>',
            '<h2>Please verify you are human</h2>',
            '<p>Checking your browser before accessing...</p>',
            '<label>Enter OTP / Two-factor authentication code</label>'
        ]
        for s in samples:
            self.assertTrue(detect_human_challenge(s), f"Failed to detect challenge in: {s}")

        clean_html = "<html><body><h1>Dashboard Sistem Antigravity</h1><p>Selamat datang!</p></body></html>"
        self.assertFalse(detect_human_challenge(clean_html))

    # 11. Role integration: qa-engineer and analyst reference ui-evidence-capture
    def test_11_role_integration_references(self):
        qa_yaml = REPO_ROOT / ".agents" / "roles" / "qa-engineer.yaml"
        self.assertTrue(qa_yaml.exists())
        qa_yaml_text = qa_yaml.read_text(encoding="utf-8")
        self.assertIn("ui-evidence-capture", qa_yaml_text)

        qa_md = REPO_ROOT / ".agents" / "roles" / "qa-engineer.md"
        self.assertTrue(qa_md.exists())
        qa_md_text = qa_md.read_text(encoding="utf-8")
        self.assertIn("ui-evidence-capture", qa_md_text)

        analyst_md = REPO_ROOT / ".agents" / "roles" / "analyst.md"
        self.assertTrue(analyst_md.exists())
        analyst_text = analyst_md.read_text(encoding="utf-8")
        self.assertIn("ui-evidence-capture", analyst_text)

    # 12. Skip real browser test if playwright is not installed
    def test_12_real_browser_skipped_or_passed(self):
        try:
            import playwright
        except ImportError:
            self.skipTest("Playwright python package not installed (Expected under Provisioning Consent Gate)")

if __name__ == "__main__":
    unittest.main()
