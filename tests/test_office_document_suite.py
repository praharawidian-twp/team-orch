#!/usr/bin/env python3
"""
test_office_document_suite.py - Unit Test Suite for Office Document Suite (doc-tool.py).
Zero-dependency test suite using Python standard library.
"""

import sys
import unittest
import subprocess
import tempfile
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_TOOL = REPO_ROOT / ".agents" / "skills" / "office-document-suite" / "scripts" / "doc-tool.py"

class TestOfficeDocumentSuite(unittest.TestCase):
    def setUp(self):
        self.doc_tool = DOC_TOOL
        self.assertTrue(self.doc_tool.exists(), f"doc-tool.py not found at {self.doc_tool}")

    def test_doc_tool_cli_help(self):
        res = subprocess.run([sys.executable, str(self.doc_tool), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("inspect", res.stdout)
        self.assertIn("read", res.stdout)
        self.assertIn("write", res.stdout)

    def test_xlsx_multi_sheet_write_inspect_read_roundtrip(self):
        md_content = """# Executive Financial Summary

## Sheet: Portfolio Summary
| Customer ID | Customer Name | Gold Balance | Account Status |
| :--- | :--- | :---: | :---: |
| CUST-001 | Budi Santoso | 25.5 | ACTIVE |
| CUST-002 | Siti Rahmawati | 100.0 | ACTIVE |
| CUST-003 | Ahmad Fauzi | 0.0 | DORMANT |

## Sheet: Transaction Logs
| Ticket No | Date | Amount | Type |
| TXN-101 | 2026-11-12 | 1250000 | BUY_GOLD |
| TXN-102 | 2026-11-12 | 500000 | PAWN_LOAN |
"""
        with tempfile.TemporaryDirectory() as td:
            md_path = Path(td) / "input.md"
            xlsx_path = Path(td) / "output.xlsx"
            md_path.write_text(md_content, encoding="utf-8")

            # 1. Write XLSX
            res_w = subprocess.run([sys.executable, str(self.doc_tool), "write", str(md_path), str(xlsx_path)], capture_output=True, text=True)
            self.assertEqual(res_w.returncode, 0, f"Write XLSX failed: {res_w.stderr}")
            self.assertTrue(xlsx_path.exists())

            # 2. Inspect XLSX
            res_i = subprocess.run([sys.executable, str(self.doc_tool), "inspect", str(xlsx_path)], capture_output=True, text=True)
            self.assertEqual(res_i.returncode, 0, f"Inspect XLSX failed: {res_i.stderr}")
            info = json.loads(res_i.stdout)
            self.assertEqual(info.get("sheet_count"), 2)
            sheet_names = [s["name"] for s in info.get("sheets", [])]
            self.assertIn("Portfolio Summary", sheet_names)
            self.assertIn("Transaction Logs", sheet_names)

            # 3. Read XLSX (all sheets)
            res_r = subprocess.run([sys.executable, str(self.doc_tool), "read", str(xlsx_path)], capture_output=True, text=True)
            self.assertEqual(res_r.returncode, 0, f"Read XLSX failed: {res_r.stderr}")
            self.assertIn("Portfolio Summary", res_r.stdout)
            self.assertIn("Budi Santoso", res_r.stdout)
            self.assertIn("25.5", res_r.stdout)
            self.assertIn("Transaction Logs", res_r.stdout)
            self.assertIn("TXN-101", res_r.stdout)
            self.assertIn("1250000", res_r.stdout)

            # 4. Read XLSX (specific sheet)
            res_r_s = subprocess.run([sys.executable, str(self.doc_tool), "read", str(xlsx_path), "--sheet", "Transaction Logs"], capture_output=True, text=True)
            self.assertEqual(res_r_s.returncode, 0)
            self.assertIn("TXN-101", res_r_s.stdout)
            self.assertNotIn("Budi Santoso", res_r_s.stdout)

            # 5. Read XLSX with --max-rows
            res_r_limit = subprocess.run([sys.executable, str(self.doc_tool), "read", str(xlsx_path), "--sheet", "Portfolio Summary", "--max-rows", "2"], capture_output=True, text=True)
            self.assertEqual(res_r_limit.returncode, 0)
            self.assertIn("Menampilkan 2 dari 4 baris", res_r_limit.stdout)

    def test_docx_write_inspect_read_roundtrip(self):
        md_content = """# Architecture Design Specification

Dokumen ini menjelaskan arsitektur layanan mikro Sample Gateway Service.

## 1. Fitur Utama
- Sinkronisasi endpoint granular method dan path
- Proteksi mutasi liar menggunakan mode only_new
- Pengujian deterministik race detector

## 2. Matriks Pengujian
| Test ID | Skenario | Hasil |
| TC-01 | Happy Path | PASS |
| TC-02 | Boundary Negative | PASS |
"""
        with tempfile.TemporaryDirectory() as td:
            md_path = Path(td) / "spec.md"
            docx_path = Path(td) / "spec.docx"
            md_path.write_text(md_content, encoding="utf-8")

            # 1. Write DOCX
            res_w = subprocess.run([sys.executable, str(self.doc_tool), "write", str(md_path), str(docx_path), "--title", "Spesifikasi Layanan"], capture_output=True, text=True)
            self.assertEqual(res_w.returncode, 0, f"Write DOCX failed: {res_w.stderr}")
            self.assertTrue(docx_path.exists())

            # 2. Inspect DOCX
            res_i = subprocess.run([sys.executable, str(self.doc_tool), "inspect", str(docx_path)], capture_output=True, text=True)
            self.assertEqual(res_i.returncode, 0)
            info = json.loads(res_i.stdout)
            self.assertEqual(info.get("table_count"), 1)
            self.assertGreaterEqual(len(info.get("headings", [])), 2)

            # 3. Read DOCX
            res_r = subprocess.run([sys.executable, str(self.doc_tool), "read", str(docx_path)], capture_output=True, text=True)
            self.assertEqual(res_r.returncode, 0, f"Read DOCX failed: {res_r.stderr}")
            self.assertIn("Spesifikasi Layanan", res_r.stdout)
            self.assertIn("Sinkronisasi endpoint granular", res_r.stdout)
            self.assertIn("TC-01", res_r.stdout)
            self.assertIn("Happy Path", res_r.stdout)

    def test_csv_and_json_conversions(self):
        with tempfile.TemporaryDirectory() as td:
            # CSV Test
            csv_path = Path(td) / "data.csv"
            xlsx_from_csv = Path(td) / "data_csv.xlsx"
            csv_path.write_text("kode,nama,stok\nEMAS-01,Logam Mulia 1gr,50\nEMAS-05,Logam Mulia 5gr,20\n", encoding="utf-8")

            res_w_csv = subprocess.run([sys.executable, str(self.doc_tool), "write", str(csv_path), str(xlsx_from_csv)], capture_output=True, text=True)
            self.assertEqual(res_w_csv.returncode, 0)
            res_r_csv = subprocess.run([sys.executable, str(self.doc_tool), "read", str(xlsx_from_csv)], capture_output=True, text=True)
            self.assertIn("Logam Mulia 1gr", res_r_csv.stdout)
            self.assertIn("50", res_r_csv.stdout)

            # JSON Test
            json_path = Path(td) / "items.json"
            xlsx_from_json = Path(td) / "items_json.xlsx"
            json_data = [
                {"item_id": "ITM-01", "name": "Antam 10g", "price": 12500000},
                {"item_id": "ITM-02", "name": "UBS 5g", "price": 6250000}
            ]
            json_path.write_text(json.dumps(json_data), encoding="utf-8")

            res_w_json = subprocess.run([sys.executable, str(self.doc_tool), "write", str(json_path), str(xlsx_from_json)], capture_output=True, text=True)
            self.assertEqual(res_w_json.returncode, 0)
            res_r_json = subprocess.run([sys.executable, str(self.doc_tool), "read", str(xlsx_from_json)], capture_output=True, text=True)
            self.assertIn("Antam 10g", res_r_json.stdout)
            self.assertIn("12500000", res_r_json.stdout)

    def test_html_generation(self):
        with tempfile.TemporaryDirectory() as td:
            md_path = Path(td) / "doc.md"
            html_path = Path(td) / "doc.html"
            md_path.write_text("# Laporan\n\n| Kolom A | Kolom B |\n| Nilai 1 | Nilai 2 |\n", encoding="utf-8")

            res_w = subprocess.run([sys.executable, str(self.doc_tool), "write", str(md_path), str(html_path), "--title", "Laporan HTML"], capture_output=True, text=True)
            self.assertEqual(res_w.returncode, 0)
            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn("<table>", html_text)
            self.assertIn("Kolom A", html_text)
            self.assertIn("Nilai 1", html_text)
            self.assertIn("Laporan HTML", html_text)

    def test_real_template_inspection_and_reading(self):
        env_path = os.environ.get("TEST_EXTERNAL_XLSX_PATH", "").strip()
        if not env_path:
            self.skipTest("TEST_EXTERNAL_XLSX_PATH not set (external proprietary template)")
        template_file = Path(env_path)
        if not template_file.exists():
            self.skipTest(f"External template file not found: {template_file}")
            
        # Inspect
        res_i = subprocess.run([sys.executable, str(self.doc_tool), "inspect", str(template_file)], capture_output=True, text=True)
        self.assertEqual(res_i.returncode, 0)
        info = json.loads(res_i.stdout)
        self.assertGreaterEqual(info.get("sheet_count", 0), 1)
        
        # Read first sheet with max-rows
        first_sheet = info["sheets"][0]["name"]
        res_r = subprocess.run([sys.executable, str(self.doc_tool), "read", str(template_file), "--sheet", first_sheet, "--max-rows", "10"], capture_output=True, text=True)
        self.assertEqual(res_r.returncode, 0)

    def test_roles_integration(self):
        roles_dir = REPO_ROOT / ".agents" / "roles"
        target_roles = ["project-manager.yaml", "analyst.yaml", "qa-engineer.yaml", "documenter.yaml"]
        for rf in target_roles:
            p = roles_dir / rf
            self.assertTrue(p.exists(), f"Role file missing: {p}")
            content = p.read_text(encoding="utf-8")
            self.assertIn("office-document-suite", content, f"Role {rf} does not include skill office-document-suite")

    def test_pdf_stream_fast_inspect_no_backtracking(self):
        """Test that doc-tool inspect on large PDF with streams runs in < 0.5s without regex hang."""
        import time
        env_path = os.environ.get("TEST_EXTERNAL_PDF_PATH", "").strip()
        if not env_path:
            self.skipTest("TEST_EXTERNAL_PDF_PATH not set (external proprietary PDF)")
        pdf_file = Path(env_path)
        if not pdf_file.exists():
            self.skipTest(f"Reference PDF template not found: {pdf_file}")
            
        t0 = time.time()
        res = subprocess.run([sys.executable, str(self.doc_tool), "inspect", str(pdf_file)], capture_output=True, text=True)
        duration = time.time() - t0
        
        self.assertEqual(res.returncode, 0, f"Inspect failed: {res.stderr}")
        self.assertLess(duration, 0.5, f"doc-tool inspect took too long: {duration:.3f}s (must be < 0.5s)")
        info = json.loads(res.stdout)
        self.assertGreaterEqual(info.get("page_count", 0), 1)

    def test_docx_write_with_embedded_png_in_table_and_qad(self):
        """Test that doc-tool write for .docx embeds PNG images inside table cells and formats QAD."""
        import zipfile
        # Minimal valid 1x1 PNG bytes
        png_1x1 = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
            b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            img_path = td_path / "screenshot.png"
            img_path.write_bytes(png_1x1)
            
            md_content = f"""# Quality Assurance Document (QAD)
            
| Test Case TC-1 | |
| :--- | :--- |
| Scenario | [POSITIVE] Healthcheck Verification |
| Precondition(s) | Service is running |
| Test Details | Given service UP<br>When ping /healthz<br>Then status 200 |
| Actual Result | 1. Hit API successful.<br>![Evidence Screenshot]({img_path.name})<br>2. Verified healthy. |
| Final Result | PASSED |
"""
            md_path = td_path / "qad.md"
            docx_path = td_path / "qad.docx"
            md_path.write_text(md_content, encoding="utf-8")
            
            # Write DOCX
            res_w = subprocess.run([sys.executable, str(self.doc_tool), "write", str(md_path), str(docx_path)], capture_output=True, text=True)
            self.assertEqual(res_w.returncode, 0, f"Write DOCX failed: {res_w.stderr}")
            self.assertTrue(docx_path.exists())
            
            # Verify internal OpenXML packaging
            with zipfile.ZipFile(docx_path, "r") as zf:
                namelist = zf.namelist()
                self.assertIn("word/media/image1.png", namelist)
                rels_text = zf.read("word/_rels/document.xml.rels").decode("utf-8")
                self.assertIn("image1.png", rels_text)
                self.assertIn("relationships/image", rels_text)
                doc_xml = zf.read("word/document.xml").decode("utf-8")
                self.assertIn("<w:drawing>", doc_xml)
                self.assertIn("004D40", doc_xml)
                
            # Inspect DOCX via doc-tool
            res_i = subprocess.run([sys.executable, str(self.doc_tool), "inspect", str(docx_path)], capture_output=True, text=True)
            self.assertEqual(res_i.returncode, 0)
            info = json.loads(res_i.stdout)
            self.assertEqual(info.get("table_count"), 1)
            self.assertEqual(info.get("image_count"), 1)

    def test_write_qad_requires_domain_or_explicit_template_in_base(self):
        """Test write-qad refuses cleanly when active domain is 'base' and no --template is supplied."""
        with tempfile.TemporaryDirectory() as td:
            out_docx = Path(td) / "base_qad.docx"
            env = os.environ.copy()
            env["TEAM_ORCH_DOMAIN"] = "base"
            res = subprocess.run(
                [sys.executable, str(self.doc_tool), "write-qad", str(out_docx)],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("No QAD template (.docx) found", res.stderr + res.stdout)

    def test_write_qad_from_domain_template_when_present(self):
        """Test populating a Specific Domain QAD template (.docx) using explicit JSON data payload."""
        domains_root = REPO_ROOT / ".agents" / "domains"
        template_file = next(domains_root.glob("*/templates/qad-template.docx"), None) if domains_root.is_dir() else None
        if not template_file or not template_file.exists():
            self.skipTest("Optional Specific Domain qad-template.docx not present in .agents/domains/")

        domain_id = template_file.parents[1].name
        with tempfile.TemporaryDirectory() as td:
            img_path = Path(td) / "sample-proof.png"
            # Minimal valid 1x1 PNG bytes
            img_path.write_bytes(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00"
                b"\x00\x04\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            data_file = Path(td) / "qad-data.json"
            data_file.write_text(json.dumps({
                "project_no": "QAD-SAMPLE-2026",
                "title": "[TESTPLAN] Sample Domain-Driven QAD Document",
                "product": "Sample API Service",
                "revisions": [
                    {
                        "no": 1,
                        "pic": "QA Engineer",
                        "desc": "Dokumen Baru - Sample Domain QAD Verification",
                        "version": "1.0",
                    }
                ],
                "result_summary": "1 Test(s) PASSED",
                "test_cases": [
                    {
                        "id": "TC-01",
                        "scenario": "[POSITIVE] Health Check Verification",
                        "precondition": "Service active in sandbox",
                        "steps": ["Given service running", "When GET /healthz is called", "Then HTTP 200 returned"],
                        "actual": ["1. Service responded 200 OK."],
                        "screenshots": [str(img_path)],
                        "result": "PASSED",
                        "note": "Verified automatically",
                    }
                ],
            }), encoding="utf-8")

            out_docx = Path(td) / "test_qad.docx"
            res_w = subprocess.run([
                sys.executable, str(self.doc_tool), "write-qad",
                "--domain", domain_id,
                "--data", str(data_file),
                "--base-dir", td,
                str(out_docx)
            ], capture_output=True, text=True)
            self.assertEqual(res_w.returncode, 0, f"write-qad failed: {res_w.stderr}")
            self.assertTrue(out_docx.exists())
            
            # Inspect output
            res_i = subprocess.run([sys.executable, str(self.doc_tool), "inspect", str(out_docx)], capture_output=True, text=True)
            self.assertEqual(res_i.returncode, 0)
            info = json.loads(res_i.stdout)
            self.assertGreaterEqual(info.get("table_count", 0), 5)
            self.assertGreaterEqual(info.get("image_count", 0), 1)
            
            # Read output
            res_r = subprocess.run([sys.executable, str(self.doc_tool), "read", str(out_docx)], capture_output=True, text=True)
            self.assertEqual(res_r.returncode, 0)
            self.assertIn("QAD-SAMPLE-2026", res_r.stdout)
            self.assertIn("1 Test(s) PASSED", res_r.stdout)
            self.assertIn("Dokumen Baru - Sample Domain QAD Verification", res_r.stdout)

if __name__ == "__main__":
    unittest.main()
