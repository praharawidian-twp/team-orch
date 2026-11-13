#!/usr/bin/env python3
"""
manual.py - Manual Fallback Backend for UI Evidence Capture.
Zero external dependencies (Python standard library only).
Generates README-EVIDENCE-GUIDE.txt in the test case evidence folder.
"""

import os
import json
import datetime
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional

from .base import BaseUIBackend, sanitize_url_for_log

MANUAL_GUIDE_TEMPLATE = """================================================================================
PANDUAN PENGAMBILAN BUKTI SCREENSHOT UI MANUAL (EVIDENCE GUIDE)
Test Case       : {tc}
Nama Bukti      : {name}
Target URL      : {url}
Dibuat Pada     : {created_at}
Model Sesi      : {session_model}
Viewport Target : {viewport}
================================================================================

1. PRASYARAT
   - Buka browser pilihan Anda (Chrome, Firefox, Safari, Edge).
   - Pastikan Anda sudah login ke lingkungan target ({url}) menggunakan
     kredensial yang sah (termasuk verifikasi SSO / MFA jika diperlukan).
   - Atur resolusi jendela browser mendekati viewport {viewport}.

2. LANGKAH PENGAMBILAN BUKTI
   - Navigasi ke URL target:
     {url}
   - Verifikasi bahwa halaman telah selesai dirender secara sempurna.
   - Lakukan inspeksi visual sesuai kriteria verifikasi Test Case {tc}.
   - Ambil screenshot halaman penuh (full-page) atau viewport aktif.

3. ATURAN MASKING & PRIVASI (WAJIB)
   - Jangan pernah menyertakan informasi sensitif dalam tangkapan layar!
   - Area yang wajib disamarkan (blur / black-box / sensor):
     * Kata sandi / PIN / token rahasia
     * Nomor identitas pribadi lengkap (NIK, Nomor Kartu Kredit/Rekening)
     * Mask selectors acuan: {masked_selectors}

4. PENYIMPANAN BERKAS BUKTI
   - Simpan berkas gambar screenshot dengan format PNG di direktori ini:
     {output_dir}/{name}.png
   - Berkas screenshot ini akan diaudit oleh Analis / Senior Tech Lead
     sebelum UAT pengguna.

================================================================================
"""

class ManualBackend(BaseUIBackend):
    name = "manual"

    def detect(self, tool_dir: Optional[Path] = None) -> Tuple[bool, str, Dict[str, Any]]:
        return True, "manual-ready", {
            "type": "manual",
            "description": "Manual fallback guide generator (always available, 0 dependency)"
        }

    def login(
        self,
        config: Dict[str, Any],
        session_path: Path,
        meta_path: Path,
        headed: bool = True
    ) -> int:
        print("[*] Backend Manual: Pengguna dapat login langsung melalui web browser biasa.")
        return 0

    def shot(
        self,
        config: Dict[str, Any],
        session_path: Path,
        tc: str,
        name: str,
        url: str,
        wait_for: Optional[str],
        full_page: bool,
        mask: List[str],
        viewport: str,
        output_path: Path,
        expect_text: Optional[List[str]] = None,
        expect_selector: Optional[str] = None,
        allow_error_page: bool = False,
        section: Optional[str] = None,
        section_text: Optional[str] = None,
        section_mode: str = "highlight",
        expect_section_text: Optional[str] = None,
        *args,
        **kwargs
    ) -> Tuple[int, Dict[str, Any]]:
        output_dir = output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        guide_file = output_dir / "README-EVIDENCE-GUIDE.txt"
        now_iso = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
        masked_list_str = ", ".join(mask) if mask else "None"

        content = MANUAL_GUIDE_TEMPLATE.format(
            tc=tc,
            name=name,
            url=url,
            created_at=now_iso,
            session_model=config.get("credential_model", "human_session"),
            viewport=viewport,
            masked_selectors=masked_list_str,
            output_dir=str(output_dir)
        )
        guide_file.write_text(content, encoding="utf-8")

        log_entry = {
            "file": f"{name}.png",
            "sha256": "manual_pending",
            "url": sanitize_url_for_log(url),
            "captured_at": now_iso,
            "backend": "manual",
            "viewport": viewport,
            "full_page": full_page,
            "masked_selectors": mask,
            "blocked_mutation_requests": 0,
            "session_model": config.get("credential_model", "human_session"),
            "operator": "human_guided",
            "status": "manual_guide_generated"
        }

        # Update capture-log.json
        log_file = output_dir / "capture-log.json"
        existing_logs = []
        if log_file.exists():
            try:
                existing_logs = json.loads(log_file.read_text(encoding="utf-8"))
                if not isinstance(existing_logs, list):
                    existing_logs = []
            except Exception:
                existing_logs = []

        # Replace or append entry for this file
        existing_logs = [e for e in existing_logs if e.get("file") != f"{name}.png"]
        existing_logs.append(log_entry)
        log_file.write_text(json.dumps(existing_logs, indent=2), encoding="utf-8")

        print(f"[✓] Manual Evidence Guide created: {guide_file}")
        return 0, log_entry
