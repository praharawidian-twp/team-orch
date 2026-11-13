"""
comm_io.py - Universal Portable I/O, Safe Concurrency & Message Bus Utilities
Standardized communications for Autonomous Multi-Agent Framework (v1.1.0)

Features:
- safe_atomic_write: Cross-platform atomic replacement via temporary file and os.replace
- safe_append: Concurrency-safe append using kernel-level filesystem O_EXCL lockfile
- sanitize_command & sanitize_text: ANSI escape, null-byte, and control sequence elimination
- compact_message_bus: Zero-data-loss atomic compaction for JSONL message bus with retention rules
- Schema versioning (v1.1.0) and Graceful Forward Compatibility
"""

import os
import sys
import time
import tempfile
import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

SCHEMA_VERSION = "1.1.0"

# ANSI escape sequence regex (CSI, OSC, ESC sequences)
ANSI_ESCAPE_REGEX = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
# C0 control characters regex (excluding \t, \n, \r)
C0_CONTROL_REGEX = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')


def safe_atomic_write(target_path: Union[str, Path], content: str) -> None:
    """
    Penulisan atomik lintas platform (POSIX, macOS, Windows NT).
    Menjamin tidak ada pembacaan berkas dalam kondisi setengah-tulis (partial read).
    
    Operasi:
    1. Membuat direktori target bila belum ada.
    2. Menulis konten ke berkas temporer di direktori yang sama (same filesystem mount).
    3. Mengganti target_path secara atomik via os.replace.
    4. Membersihkan berkas temporer jika terjadi kesalahan.
    """
    path_obj = Path(target_path).resolve()
    dir_path = path_obj.parent
    dir_path.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(dir_path),
        delete=False,
        prefix=".tmp.",
        suffix=".atomic"
    ) as tmp:
        tmp.write(content)
        tmp.flush()
        tmp_path = tmp.name

    try:
        os.replace(tmp_path, str(path_obj))
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def safe_append(
    target_path: Union[str, Path],
    entry: str,
    timeout: float = 5.0,
    stale_threshold: float = 10.0
) -> None:
    """
    Append log aman lintas platform dengan locking O_EXCL berbasis filesystem.
    Atomik di tingkat kernel VFS tanpa bergantung pada fcntl.flock yang bermasalah di NFS/CIFS.

    Parameters:
    - target_path: Jalur berkas target
    - entry: Baris teks yang akan di-append
    - timeout: Batas waktu maksimal menunggu lock (default 5.0 detik)
    - stale_threshold: Batas waktu pembersihan lockfile usang/terbengkalai (default 10.0 detik)
    """
    path_obj = Path(target_path).resolve()
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    lock_path = str(path_obj) + ".lock"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        # Periksa potensi stale lock dari proses yang crash
        if os.path.exists(lock_path):
            try:
                st = os.stat(lock_path)
                if (time.time() - st.st_mtime) > stale_threshold:
                    try:
                        os.unlink(lock_path)
                    except OSError:
                        pass
            except OSError:
                pass

        try:
            # os.O_CREAT | os.O_EXCL adalah atomik di tingkat VFS kernel
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                with open(str(path_obj), "a", encoding="utf-8") as f:
                    entry_clean = entry.rstrip("\n") + "\n"
                    f.write(entry_clean)
                    f.flush()
            finally:
                os.close(fd)
                try:
                    os.unlink(lock_path)
                except OSError:
                    pass
            return
        except FileExistsError:
            time.sleep(0.02)  # Backoff 20 ms

    raise TimeoutError(f"Gagal memperoleh exclusive lock untuk {target_path} dalam {timeout}s")


def sanitize_command(command: str) -> str:
    """
    [SECURITY] Sanitasi perintah sebelum dikirim ke terminal target.
    Mencegah ANSI control sequence injection, null-byte poisoning, dan shell control sequence.
    """
    # 1. Hapus escape sequence ANSI
    sanitized = ANSI_ESCAPE_REGEX.sub('', command)

    # 2. Hapus null-byte (\x00)
    sanitized = sanitized.replace('\x00', '')

    # 3. Hapus karakter kontrol C0 berbahaya (selain tab, newline, carriage return)
    sanitized = C0_CONTROL_REGEX.sub('', sanitized)

    # 4. Log peringatan jika terjadi manipulasi input mencurigakan
    if sanitized != command:
        logging.warning("[SECURITY] Karakter kontrol berbahaya dihapus dari instruksi terminal.")

    return sanitized


def sanitize_text(text: str) -> str:
    """
    Sanitasi teks umum untuk event payload, pesan log, dan deskripsi tugas.
    Menghilangkan escape sequence ANSI dan null-bytes.
    """
    if not isinstance(text, str):
        return text
    sanitized = ANSI_ESCAPE_REGEX.sub('', text)
    sanitized = sanitized.replace('\x00', '')
    return sanitized


def parse_event_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO-8601 timestamp with fallback support."""
    if not ts_str:
        return None
    try:
        # Handles 2026-09-18T11:19:45.778475 or 2026-09-18T11:19:45
        return datetime.fromisoformat(ts_str)
    except Exception:
        pass
    # Try standard strptime formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts_str, fmt)
        except Exception:
            continue
    return None


def compact_message_bus(
    bus_file: Union[str, Path],
    max_size_bytes: int = 5 * 1024 * 1024,
    force: bool = False,
    project_id: Optional[str] = None,
    processed_retention_days: int = 7,
    failed_retention_days: int = 30
) -> Dict[str, Any]:
    """
    Kebijakan Kompaksi & Retensi Message Bus (Zero-Data-Loss Atomic Rewrite)
    Merujuk pada spesifikasi GAP-06 v1.1.0.

    Aturan Retensi:
    - Event 'PROCESSED' dengan usia > 7 hari -> Dieliminasi (dikompaksi)
    - Event 'FAILED' dengan usia > 30 hari -> Dieliminasi
    - Event 'PENDING' -> MUTLAK DILARANG DIHAPUS (belum diproses worker)
    - Event tanpa status / legacy -> Mengikuti aturan PROCESSED (> 7 hari dieliminasi)
    - Bila parameter project_id diberikan -> Hanya mengevaluasi retensi untuk proyek bersangkutan,
      mempertahankan event proyek lain secara utuh.

    Trigger:
    - Otomatis saat ukuran berkas > 5 MB (max_size_bytes)
    - Manual bila force=True
    """
    path_obj = Path(bus_file).resolve()
    if not path_obj.exists():
        return {
            "status": "skipped",
            "reason": "file_not_found",
            "file": str(path_obj),
            "original_count": 0,
            "retained_count": 0,
            "removed_count": 0
        }

    current_size = path_obj.stat().st_size
    if not force and current_size < max_size_bytes:
        return {
            "status": "skipped",
            "reason": "size_below_threshold",
            "current_size_bytes": current_size,
            "threshold_bytes": max_size_bytes,
            "file": str(path_obj)
        }

    lock_path = str(path_obj) + ".lock"
    deadline = time.monotonic() + 10.0
    fd = None

    while time.monotonic() < deadline:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.05)

    if fd is None:
        raise TimeoutError(f"Gagal memperoleh exclusive lock untuk kompaksi {path_obj}")

    now = datetime.now()

    try:
        raw_content = path_obj.read_text(encoding="utf-8")
        lines = [line.strip() for line in raw_content.splitlines() if line.strip()]

        retained_lines: List[str] = []
        removed_count = 0

        for line in lines:
            try:
                ev = json.loads(line)
            except Exception:
                # Corrupted or non-JSON line: preserve to avoid silent data destruction
                retained_lines.append(line)
                continue

            # Graceful Forward Compatibility: Process known fields, preserve unhandled fields
            ev_status = str(ev.get("status", "PROCESSED")).upper()
            ev_project = ev.get("project_id")
            ev_ts = parse_event_timestamp(ev.get("timestamp"))

            # Filter by project if requested
            if project_id and ev_project != project_id:
                # Event milik proyek lain, pertahankan
                retained_lines.append(line)
                continue

            # Rule 1: PENDING events are strictly protected from deletion
            if ev_status == "PENDING":
                retained_lines.append(line)
                continue

            # Rule 2: Evaluate age for PROCESSED / FAILED
            if ev_ts is None:
                # Jika tidak bisa diparse timestamp-nya, simpan dengan aman
                retained_lines.append(line)
                continue

            age_days = (now - ev_ts).total_seconds() / 86400.0

            if ev_status == "FAILED":
                if age_days > failed_retention_days:
                    removed_count += 1
                else:
                    retained_lines.append(line)
            else:
                # PROCESSED or unspecified status
                if age_days > processed_retention_days:
                    removed_count += 1
                else:
                    retained_lines.append(line)

        # Zero-Data-Loss Atomic Rewrite
        dir_path = path_obj.parent
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(dir_path),
            delete=False,
            prefix=".tmp.compact.",
            suffix=".jsonl"
        ) as tmp:
            if retained_lines:
                tmp.write("\n".join(retained_lines) + "\n")
            else:
                tmp.write("")
            tmp.flush()
            tmp_path = tmp.name

        os.replace(tmp_path, str(path_obj))

        new_size = path_obj.stat().st_size
        return {
            "status": "compacted",
            "file": str(path_obj),
            "original_count": len(lines),
            "retained_count": len(retained_lines),
            "removed_count": removed_count,
            "original_size_bytes": current_size,
            "new_size_bytes": new_size
        }

    finally:
        os.close(fd)
        try:
            os.unlink(lock_path)
        except OSError:
            pass


def format_bus_event(
    project_id: Optional[str],
    from_role: str,
    to_role: str,
    event_type: str,
    message: str,
    payload: Optional[Dict[str, Any]] = None,
    severity: Optional[str] = None,
    status: str = "PENDING"
) -> Dict[str, Any]:
    """
    Format standard Message Bus Event compliant with Schema Version 1.1.0.
    """
    now = datetime.now()
    event_id = f"EVT-{int(now.timestamp() * 1000)}"

    clean_message = sanitize_text(message)

    return {
        "event_id": event_id,
        "timestamp": now.isoformat(),
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "from_role": from_role,
        "to_role": to_role,
        "type": event_type.upper(),
        "severity": severity or "SILENT",
        "status": status.upper(),
        "message": clean_message,
        "payload": payload or {}
    }
