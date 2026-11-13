#!/usr/bin/env python3
"""
Unit tests for 2-Domain Architecture, Multi-Domain Switching, Knowledge Isolation,
and Anti-Hallucination Context Binding Guardrails in cmd/team-orch & cmd/sync-boilerplates.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEAM_ORCH = REPO_ROOT / "cmd" / "team-orch"
SYNC_BOILERPLATES = REPO_ROOT / "cmd" / "sync-boilerplates"


class TestDomainIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="domain_iso_test_"))
        self.home_dir = self.tmp_root / "home"
        self.ws_dir = self.tmp_root / "workspace"
        self.home_dir.mkdir(parents=True)
        self.ws_dir.mkdir(parents=True)

        # Copy base roles, workflows, templates, and base knowledge into isolated workspace
        shutil.copytree(REPO_ROOT / ".agents" / "roles", self.ws_dir / ".agents" / "roles")
        shutil.copytree(REPO_ROOT / ".agents" / "workflows", self.ws_dir / ".agents" / "workflows")
        shutil.copytree(REPO_ROOT / ".agents" / "templates", self.ws_dir / ".agents" / "templates")
        shutil.copytree(REPO_ROOT / ".agents" / "knowledge", self.ws_dir / ".agents" / "knowledge")
        (self.ws_dir / ".agents" / "tasks" / "active").mkdir(parents=True)
        (self.ws_dir / ".agents" / "tasks" / "completed").mkdir(parents=True)

        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home_dir)
        self.env.pop("TEAM_ORCH_DOMAIN", None)

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _run_orch(self, *args, extra_env=None):
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(TEAM_ORCH), *args],
            cwd=str(self.ws_dir),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_01_default_base_domain_has_zero_institutional_knowledge(self):
        res_cur = self._run_orch("domain", "current")
        self.assertEqual(res_cur.returncode, 0, res_cur.stderr)
        self.assertIn("base", res_cur.stdout.lower())

        res_kb = self._run_orch("knowledge", "list")
        self.assertEqual(res_kb.returncode, 0, res_kb.stderr)
        self.assertIn("[BASE]", res_kb.stdout)
        self.assertNotIn("[DOMAIN:", res_kb.stdout)

    def test_02_domain_init_validate_use_sync_and_scoped_knowledge(self):
        # Create Domain A
        res_init = self._run_orch(
            "domain", "init", "acme-corp",
            "--org", "Acme Corp",
            "--name", "Acme Enterprise Platform",
        )
        self.assertEqual(res_init.returncode, 0, res_init.stderr)
        dom_a_dir = self.ws_dir / ".agents" / "domains" / "acme-corp"
        self.assertTrue((dom_a_dir / "domain.yaml").is_file())
        self.assertTrue((dom_a_dir / "boilerplates.yaml").is_file())

        # Create dummy QAD template & domain-specific knowledge for acme-corp
        (dom_a_dir / "templates" / "qad-template.docx").write_bytes(b"PK\x05\x06" + b"\x00" * 18)
        (dom_a_dir / "knowledge" / "topics" / "acme-secrets-sop.md").write_text(
            "# Acme Internal SOP\nInternal domain rules for Acme Corp.\n",
            encoding="utf-8",
        )
        (dom_a_dir / "knowledge" / "registry.yaml").write_text(
            'knowledge_catalog:\n'
            '  - id: "acme-secrets-sop"\n'
            '    title: "Acme Internal SOP"\n'
            '    category: "domain-standard"\n'
            '    file: "topics/acme-secrets-sop.md"\n'
            '    access: [analyst, coder]\n'
            '    strictness: "STRICT"\n'
            '    summary: "SOP internal Acme Corp"\n',
            encoding="utf-8",
        )

        # Validate acme-corp
        res_val = self._run_orch("domain", "validate", "acme-corp")
        self.assertEqual(res_val.returncode, 0, res_val.stderr + res_val.stdout)

        # Switch active domain to acme-corp
        res_use = self._run_orch("domain", "use", "acme-corp")
        self.assertEqual(res_use.returncode, 0, res_use.stderr)

        # Knowledge list should now expose acme-secrets-sop tagged as domain
        res_kb_a = self._run_orch("knowledge", "list")
        self.assertEqual(res_kb_a.returncode, 0, res_kb_a.stderr)
        self.assertIn("acme-secrets-sop", res_kb_a.stdout)

        # Switch to Domain B (beta-bank) -> Domain A knowledge MUST disappear completely
        self._run_orch("domain", "init", "beta-bank", "--org", "Beta Bank")
        self._run_orch("domain", "use", "beta-bank")
        res_kb_b = self._run_orch("knowledge", "list")
        self.assertEqual(res_kb_b.returncode, 0, res_kb_b.stderr)
        self.assertNotIn("acme-secrets-sop", res_kb_b.stdout)

        # Sync local domains to global ~/.gemini/team-orch/domains/
        res_sync = self._run_orch("domain", "sync")
        self.assertEqual(res_sync.returncode, 0, res_sync.stderr)
        self.assertTrue((self.home_dir / ".gemini" / "team-orch" / "domains" / "acme-corp" / "domain.yaml").is_file())

    def test_03_project_domain_mismatch_guard_prevents_hallucination(self):
        # Initialize two distinct domains
        self._run_orch("domain", "init", "acme-corp", "--org", "Acme Corp")
        self._run_orch("domain", "init", "beta-bank", "--org", "Beta Bank")

        # Initialize project pinned to acme-corp
        res_proj = self._run_orch("init", "proj-acme", "--workflow", "rapid-prototype", "--domain", "acme-corp", "--silent")
        self.assertEqual(res_proj.returncode, 0, res_proj.stderr + res_proj.stdout)

        # Switch active global domain to beta-bank
        self._run_orch("domain", "use", "beta-bank")

        # Attempting `team-orch next proj-acme` MUST abort due to domain mismatch!
        res_next_mismatch = self._run_orch("next", "proj-acme")
        self.assertNotEqual(res_next_mismatch.returncode, 0)
        combined = res_next_mismatch.stdout + res_next_mismatch.stderr
        self.assertIn("DOMAIN CONTEXT MISMATCH GUARD", combined.upper())

        # Switching back to acme-corp makes next proceed past the domain guard and injects Acme Corp into build_stage_prompt
        self._run_orch("domain", "use", "acme-corp")
        res_next_a = self._run_orch("next", "proj-acme", "--silent", extra_env={"HERDR_ENV": "0"})
        self.assertEqual(res_next_a.returncode, 0, res_next_a.stderr + res_next_a.stdout)

        prompt_code = (
            "import importlib.machinery, importlib.util; "
            f"loader = importlib.machinery.SourceFileLoader('to', '{TEAM_ORCH}'); "
            "spec = importlib.util.spec_from_loader('to', loader); "
            "mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); "
            "print(mod.build_stage_prompt('project-manager', 'proj-acme'))"
        )
        res_p_a = subprocess.run([sys.executable, "-c", prompt_code], cwd=str(self.ws_dir), env=self.env, capture_output=True, text=True)
        self.assertEqual(res_p_a.returncode, 0, res_p_a.stderr)
        self.assertIn("[ACTIVE DOMAIN CONTEXT:", res_p_a.stdout)
        self.assertIn("acme-corp", res_p_a.stdout)
        self.assertIn("Acme Corp", res_p_a.stdout)
        self.assertNotIn("Beta Bank", res_p_a.stdout)

        # Rebind project to beta-bank via `domain bind`, then switch active domain -> works under beta-bank
        res_bind = self._run_orch("domain", "bind", "proj-acme", "beta-bank")
        self.assertEqual(res_bind.returncode, 0, res_bind.stderr)
        self._run_orch("domain", "use", "beta-bank")
        res_next_b = self._run_orch("next", "proj-acme", "--silent", extra_env={"HERDR_ENV": "0"})
        self.assertEqual(res_next_b.returncode, 0, res_next_b.stderr + res_next_b.stdout)
        res_p_b = subprocess.run([sys.executable, "-c", prompt_code], cwd=str(self.ws_dir), env=self.env, capture_output=True, text=True)
        self.assertEqual(res_p_b.returncode, 0, res_p_b.stderr)
        self.assertIn("Beta Bank", res_p_b.stdout)
        self.assertNotIn("Acme Corp", res_p_b.stdout)

    def test_04_sync_boilerplates_skips_cleanly_in_base_domain(self):
        res = subprocess.run(
            [sys.executable, str(SYNC_BOILERPLATES), "--domain", "base"],
            cwd=str(self.ws_dir),
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr + res.stdout)
        self.assertIn("base", res.stdout.lower())

    def test_05_interactive_domain_init_wizard(self):
        # Create dummy QAD template file to be copied by wizard
        src_qad = self.tmp_root / "corp-qad.docx"
        src_qad.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

        answers = "\n".join([
            "Delta Corp",                          # Organization name
            "Delta Engineering Domain",            # Display name
            "Platform & QA",                       # Division
            "#004D40",                             # Brand color
            "Confidential Delta Corp.",            # Notice
            "QA Manager:Alice;Dept Head:Bob",      # Officials
            "delta-api",                           # App ID
            "Delta Gateway Service",               # App name
            "https://dev.delta.local,https://admin.delta.local",  # Internal domains
            str(src_qad),                          # QAD docx template path
            "",                                    # External ref dir
            "https://git.delta.local/starter.git", # Boilerplate URL
            "service",                             # Boilerplate type
            "y",                                   # Activate & sync now
        ]) + "\n"

        res = subprocess.run(
            [sys.executable, str(TEAM_ORCH), "domain", "init", "delta-corp", "--interactive"],
            cwd=str(self.ws_dir),
            env=self.env,
            input=answers,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr + res.stdout)
        dom_dir = self.ws_dir / ".agents" / "domains" / "delta-corp"
        self.assertTrue((dom_dir / "domain.yaml").is_file())
        self.assertTrue((dom_dir / "templates" / "qad-template.docx").is_file())
        self.assertTrue((self.home_dir / ".gemini" / "team-orch" / "domains" / "delta-corp" / "domain.yaml").is_file())

        domain_yaml = (dom_dir / "domain.yaml").read_text(encoding="utf-8")
        self.assertIn("Delta Corp", domain_yaml)
        self.assertIn("Alice", domain_yaml)
        self.assertIn("https://dev.delta.local", domain_yaml)

        bp_yaml = (dom_dir / "boilerplates.yaml").read_text(encoding="utf-8")
        self.assertIn("https://git.delta.local/starter.git", bp_yaml)

        # Must already be active domain and pass validation
        res_cur = self._run_orch("domain", "current")
        self.assertEqual(res_cur.returncode, 0)
        self.assertIn("delta-corp", res_cur.stdout)

        res_val = self._run_orch("domain", "validate", "delta-corp")
        self.assertEqual(res_val.returncode, 0, res_val.stderr + res_val.stdout)


if __name__ == "__main__":
    unittest.main()
