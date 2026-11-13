#!/usr/bin/env python3
"""
test_qa_validation_gate.py - Test Suite for QA Validation Gate & Lead Reviewer Upgrade.
Zero-dependency test suite using Python standard library.
"""

import sys
import unittest
import subprocess
import tempfile
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestQAValidationGate(unittest.TestCase):
    def setUp(self):
        self.repo_root = REPO_ROOT
        self.workflows_dir = self.repo_root / ".agents" / "workflows"
        self.roles_dir = self.repo_root / ".agents" / "roles"
        self.templates_dir = self.repo_root / ".agents" / "templates"
        self.skills_dir = self.repo_root / ".agents" / "skills"

    def test_workflow_has_qa_validation_and_qa_review_stages(self):
        workflow_path = self.workflows_dir / "enterprise-sdlc-devops.yaml"
        self.assertTrue(workflow_path.exists(), f"Workflow not found: {workflow_path}")
        
        content = workflow_path.read_text(encoding="utf-8")
        
        # Verify qa-validation stage exists with role qa-engineer
        self.assertRegex(content, r'id:\s*"qa-validation"')
        self.assertRegex(content, r'role:\s*"qa-engineer"')
        self.assertIn("qa-test-report.md", content)

        # Verify qa-review stage exists with role analyst and correct loop_back
        self.assertRegex(content, r'id:\s*"qa-review"')
        self.assertRegex(content, r'role:\s*"analyst"')
        self.assertRegex(content, r'name:\s*"Lead QA Scenario Audit & UAT Triage Gate"')
        self.assertRegex(content, r'loop_back_to:\s*"qa-validation"')

    def test_analyst_role_and_responsibilities(self):
        analyst_yaml = self.roles_dir / "analyst.yaml"
        self.assertTrue(analyst_yaml.exists())
        yaml_content = analyst_yaml.read_text(encoding="utf-8").lower()
        self.assertIn("lead qa reviewer", yaml_content)
        self.assertIn("triage validasi uat", yaml_content)

        analyst_md = self.roles_dir / "analyst.md"
        self.assertTrue(analyst_md.exists())
        content = analyst_md.read_text(encoding="utf-8")
        self.assertIn("Lead QA Reviewer", content)
        self.assertIn("Tahap C: Review Hasil QA", content)
        self.assertIn("AUTO_VERIFIED", content)
        self.assertIn("HUMAN_VALIDATION_REQUIRED", content)
        self.assertIn("NEEDS_QA_REVISION", content)
        self.assertIn("APPROVED", content)

    def test_qa_engineer_role_and_responsibilities(self):
        qa_yaml = self.roles_dir / "qa-engineer.yaml"
        self.assertTrue(qa_yaml.exists())
        yaml_content = qa_yaml.read_text(encoding="utf-8").lower()
        self.assertIn("analis", yaml_content)
        self.assertIn("review", yaml_content)

        qa_md = self.roles_dir / "qa-engineer.md"
        self.assertTrue(qa_md.exists())
        content = qa_md.read_text(encoding="utf-8")
        self.assertIn("Kewajiban Review ke Analis", content)
        self.assertIn("NEEDS_QA_REVISION", content)

    def test_template_and_golden_example_sections(self):
        template_file = self.templates_dir / "qa-test-report-template.md"
        self.assertTrue(template_file.exists())
        t_content = template_file.read_text(encoding="utf-8")
        self.assertIn("Matriks Triage Validasi", t_content)
        self.assertIn("Review & Sign-Off Analis", t_content)
        self.assertIn("AUTO_VERIFIED", t_content)
        self.assertIn("HUMAN_VALIDATION_REQUIRED", t_content)

        golden_file = self.skills_dir / "qa-test-specialist" / "examples" / "golden-qa-report-example.md"
        self.assertTrue(golden_file.exists())
        g_content = golden_file.read_text(encoding="utf-8")
        self.assertIn("Matriks Triage Validasi", g_content)
        self.assertIn("Review & Sign-Off Analis", g_content)
        self.assertIn("AUTO_VERIFIED", g_content)
        self.assertIn("HUMAN_VALIDATION_REQUIRED", g_content)
        self.assertIn("VERDICT: PASSED", g_content)
        self.assertIn("ANALYST STATUS: APPROVED", g_content)

    def test_skills_and_references(self):
        ref_file = self.skills_dir / "tech-lead-analyst" / "references" / "qa-triage-and-field-audit.md"
        self.assertTrue(ref_file.exists())
        ref_content = ref_file.read_text(encoding="utf-8")
        self.assertIn("[AUTO_VERIFIED]", ref_content)
        self.assertIn("[HUMAN_VALIDATION_REQUIRED]", ref_content)
        self.assertIn("Field-Realism Audit", ref_content)
        self.assertIn("Lead Directive", ref_content)

        tech_lead_skill = self.skills_dir / "tech-lead-analyst" / "SKILL.md"
        self.assertTrue(tech_lead_skill.exists())
        self.assertIn("Phase 5: Lead QA Review & UAT Validation Triage", tech_lead_skill.read_text(encoding="utf-8"))

        qa_skill = self.skills_dir / "qa-test-specialist" / "SKILL.md"
        self.assertTrue(qa_skill.exists())
        self.assertIn("Mandatory Analyst Review Loop", qa_skill.read_text(encoding="utf-8"))

    def test_three_phase_human_controlled_lifecycle(self):
        qa_md = self.roles_dir / "qa-engineer.md"
        content_qa = qa_md.read_text(encoding="utf-8")
        self.assertIn("Fase 1", content_qa)
        self.assertIn("Fase 2", content_qa)
        self.assertIn("Fase 3", content_qa)
        self.assertIn("HARD STOP", content_qa)

        qa_skill = self.skills_dir / "qa-test-specialist" / "SKILL.md"
        content_skill = qa_skill.read_text(encoding="utf-8")
        self.assertIn("Fase 1", content_skill)
        self.assertIn("Fase 2", content_skill)
        self.assertIn("Fase 3", content_skill)
        self.assertIn("HARD STOP", content_skill)

        playbook = self.repo_root / ".agents" / "knowledge" / "topics" / "qa-validation-gate-playbook.md"
        content_playbook = playbook.read_text(encoding="utf-8")
        self.assertIn("Fase 1", content_playbook)
        self.assertIn("Fase 2", content_playbook)
        self.assertIn("Fase 3", content_playbook)

    def test_evidence_folder_standard(self):
        qa_md = self.roles_dir / "qa-engineer.md"
        self.assertIn("docs/qa/evidence/TC-", qa_md.read_text(encoding="utf-8"))

        qa_skill = self.skills_dir / "qa-test-specialist" / "SKILL.md"
        self.assertIn("docs/qa/evidence/TC-", qa_skill.read_text(encoding="utf-8"))

        template_file = self.templates_dir / "qa-test-report-template.md"
        self.assertIn("Evidence Folder", template_file.read_text(encoding="utf-8"))

    def test_pre_automation_discovery_gate(self):
        qa_md = self.roles_dir / "qa-engineer.md"
        content = qa_md.read_text(encoding="utf-8").lower()
        self.assertIn("framework", content)
        self.assertIn("base on", content)

        qa_skill = self.skills_dir / "qa-test-specialist" / "SKILL.md"
        content_skill = qa_skill.read_text(encoding="utf-8").lower()
        self.assertIn("framework", content_skill)
        self.assertIn("base on", content_skill)

    def test_smart_regression_warning_gate(self):
        qa_md = self.roles_dir / "qa-engineer.md"
        content = qa_md.read_text(encoding="utf-8")
        self.assertIn("peringatan", content.lower())
        self.assertIn("dokumen-dokumen lama", content.lower())

        qa_skill = self.skills_dir / "qa-test-specialist" / "SKILL.md"
        content_skill = qa_skill.read_text(encoding="utf-8")
        self.assertIn("peringatan", content_skill.lower())
        self.assertIn("dokumen-dokumen lama", content_skill.lower())

    def test_analyst_enforces_evidence_and_hard_stop(self):
        analyst_md = self.roles_dir / "analyst.md"
        content = analyst_md.read_text(encoding="utf-8")
        self.assertIn("docs/qa/evidence/TC-", content)
        self.assertIn("HARD STOP", content)

        tech_lead_skill = self.skills_dir / "tech-lead-analyst" / "SKILL.md"
        content_skill = tech_lead_skill.read_text(encoding="utf-8")
        self.assertIn("docs/qa/evidence/TC-", content_skill)
        self.assertIn("HARD STOP", content_skill)

    def test_verify_qa_report_script_validates_golden_and_rejects_incomplete(self):
        script_file = self.skills_dir / "qa-test-specialist" / "scripts" / "verify-qa-report.py"
        self.assertTrue(script_file.exists())
        golden_file = self.skills_dir / "qa-test-specialist" / "examples" / "golden-qa-report-example.md"

        # Golden file should PASS (exit code 0)
        res = subprocess.run([sys.executable, str(script_file), str(golden_file)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Script failed on golden example: {res.stdout}\n{res.stderr}")
        self.assertIn("SUCCESS: Laporan QA memenuhi 100% kriteria", res.stdout)

        # Incomplete report without Section 6 and Section 7 should FAIL (exit code 1)
        with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
            tmp.write("""# QA Report: Missing sections
## 1. Metadata
TC-01
## 2. 4-Dimensional Test Matrix Summary
positif, negatif, idempotensi, race
## 3. Bukti Eksekusi Runtime
```bash
bru run
```
## 4. Verifikasi Konkurensi
go test -race
## 5. Keputusan Gatekeeper
VERDICT: PASSED
""")
            tmp.flush()
            res_fail = subprocess.run([sys.executable, str(script_file), tmp.name], capture_output=True, text=True)
            self.assertNotEqual(res_fail.returncode, 0, "Script should have failed for missing sections 6 & 7")
            self.assertIn("MISSING SECTION", res_fail.stdout)

if __name__ == "__main__":
    unittest.main()
