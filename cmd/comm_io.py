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
import shutil
import subprocess
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


# ------------------------------------------------------------------------------
# Centralized Model Configuration, Tier Resolution & Dynamic Registry (v2.0.0)
# ------------------------------------------------------------------------------

DEFAULT_ROLE_TIERS: Dict[str, str] = {
    "pm": "medium",
    "project-manager": "medium",
    "analyst": "high",
    "analis": "high",
    "meta-architect": "high",
    "coder": "medium",
    "dev": "medium",
    "agent-builder": "medium",
    "documenter": "low",
    "doc": "low",
    "qa-engineer": "medium",
    "qa": "medium",
    "devops": "medium",
    "ops": "medium",
    "infra": "medium",
}

ROLE_ALIAS_MAP: Dict[str, str] = {
    "pm": "project-manager",
    "analis": "analyst",
    "dev": "coder",
    "doc": "documenter",
    "qa": "qa-engineer",
    "ops": "devops",
    "infra": "devops",
}

DEFAULT_MODEL_CONFIG: Dict[str, Any] = {
    "version": "2.0.0",
    "last_synced": "2026-11-19T10:48:00+07:00",
    "tiers": {
        "low": {
            "primary": "gemini-4-hydrogen-low",
            "fallback": "gemini-3.8-flash-low",
            "effort": "low",
            "subagent_model": "flash_lite",
            "label": "Simple / Light",
            "token_economy": "Maximum token savings (~80-90% quota preserved)",
            "description": "Fast lookups, file grep, linting, documentation sync, status checks."
        },
        "medium": {
            "primary": "gemini-4-neon-high",
            "fallback": "claude-sonnet-5-5-high",
            "effort": "medium",
            "subagent_model": "flash",
            "label": "Moderate / Standard",
            "token_economy": "Balanced high accuracy and token efficiency",
            "description": "Feature implementation, bug fixing, unit testing, QA validation, standard refactoring."
        },
        "high": {
            "primary": "gemini-4-argon-high",
            "fallback": "claude-opus-5-5-high",
            "effort": "high",
            "subagent_model": "pro",
            "label": "Complex / High-Reasoning",
            "token_economy": "Premium reasoning quota (use for architecture, tech lead review, security audit)",
            "description": "Deep architecture design, complex algorithms, gatekeeper code review, security audits."
        }
    },
    "available_models": [
        {"id": "gemini-4-neon-high", "display_name": "Gemini 4 Neon (High)", "source": "agy_runtime", "tier_hint": "medium"},
        {"id": "gemini-4-neon-xhigh", "display_name": "Gemini 4 Neon (XHigh)", "source": "agy_runtime", "tier_hint": "high"},
        {"id": "gemini-4-neon-medium", "display_name": "Gemini 4 Neon (Medium)", "source": "agy_runtime", "tier_hint": "medium"},
        {"id": "gemini-4-neon-low", "display_name": "Gemini 4 Neon (Low)", "source": "agy_runtime", "tier_hint": "low"},
        {"id": "gemini-4-argon-high", "display_name": "Gemini 4 Argon (High)", "source": "agy_runtime", "tier_hint": "high"},
        {"id": "gemini-4-argon-medium", "display_name": "Gemini 4 Argon (Medium)", "source": "agy_runtime", "tier_hint": "high"},
        {"id": "gemini-4-argon-low", "display_name": "Gemini 4 Argon (Low)", "source": "agy_runtime", "tier_hint": "high"},
        {"id": "gemini-4-hydrogen-xhigh", "display_name": "Gemini 4 Hydrogen (XHigh)", "source": "agy_runtime", "tier_hint": "high"},
        {"id": "gemini-4-hydrogen-high", "display_name": "Gemini 4 Hydrogen (High)", "source": "agy_runtime", "tier_hint": "medium"},
        {"id": "gemini-4-hydrogen-medium", "display_name": "Gemini 4 Hydrogen (Medium)", "source": "agy_runtime", "tier_hint": "medium"},
        {"id": "gemini-4-hydrogen-low", "display_name": "Gemini 4 Hydrogen (Low)", "source": "agy_runtime", "tier_hint": "low"},
        {"id": "gemini-pro-orchestrator-neon", "display_name": "Orchestrator (Neon)", "source": "agy_runtime", "tier_hint": "high"},
        {"id": "gemini-pro-orchestrator-g1-pro", "display_name": "Orchestrator (Argon)", "source": "agy_runtime", "tier_hint": "high"},
        {"id": "gemini-3.8-flash-high", "display_name": "Gemini 3.8 Flash (High)", "source": "agy_runtime", "tier_hint": "medium"},
        {"id": "gemini-3.8-flash-medium", "display_name": "Gemini 3.8 Flash (Medium)", "source": "agy_runtime", "tier_hint": "medium"},
        {"id": "gemini-3.8-flash-low", "display_name": "Gemini 3.8 Flash (Low)", "source": "agy_runtime", "tier_hint": "low"},
        {"id": "claude-opus-5-5-high", "display_name": "Claude Opus 5.5 (High)", "source": "agy_runtime", "tier_hint": "high"},
        {"id": "claude-opus-5-5-medium", "display_name": "Claude Opus 5.5 (Medium)", "source": "agy_runtime", "tier_hint": "high"},
        {"id": "claude-opus-5-5-low", "display_name": "Claude Opus 5.5 (Low)", "source": "agy_runtime", "tier_hint": "high"},
        {"id": "claude-sonnet-5-5-high", "display_name": "Claude Sonnet 5.5 (High)", "source": "agy_runtime", "tier_hint": "medium"},
        {"id": "claude-sonnet-5-5-medium", "display_name": "Claude Sonnet 5.5 (Medium)", "source": "agy_runtime", "tier_hint": "medium"},
        {"id": "claude-sonnet-5-5-low", "display_name": "Claude Sonnet 5.5 (Low)", "source": "agy_runtime", "tier_hint": "low"},
        {"id": "gpt-oss-120b-medium", "display_name": "GPT-OSS 120B (Medium)", "source": "agy_runtime", "tier_hint": "medium"},
    ],
    "api_key_models": []
}

_FRONTIER_FAMILIES = {"argon", "pro", "ultra", "opus", "carbon", "titanium", "titan", "orchestrator"}
_WORKHORSE_FAMILIES = {"neon", "hydrogen", "flash", "sonnet", "haiku", "gpt-oss", "mini", "lite"}
_SPINNER_RE = re.compile(r"[\r\u2800-\u28ff]+")


def _strip_inline_yaml_comment(val_str: str) -> str:
    """Strip inline YAML comments outside quoted strings."""
    in_single = False
    in_double = False
    for idx, ch in enumerate(val_str):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if idx == 0 or val_str[idx - 1].isspace():
                return val_str[:idx].strip()
    return val_str.strip()


def _parse_yaml_scalar(val_str: str) -> Any:
    val = _strip_inline_yaml_comment(val_str)
    if val in ("true", "True"):
        return True
    if val in ("false", "False"):
        return False
    if val in ("null", "None", "~", ""):
        return None
    if re.fullmatch(r"-?\d+", val):
        return int(val)
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_parse_yaml_scalar(x.strip()) for x in inner.split(",") if x.strip()]
    return val


def load_simple_yaml(filepath: Union[str, Path]) -> Any:
    """Zero-dependency YAML/JSON loader for team-orch & herdr-orch configs."""
    path = Path(filepath)
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    stripped_text = text.strip()
    if not stripped_text:
        return {}
    if stripped_text.startswith("{") or stripped_text.startswith("["):
        try:
            return json.loads(stripped_text)
        except Exception:
            pass

    lines = text.splitlines()

    def parse_block(line_idx: int, min_indent: int) -> Tuple[Any, int]:
        res: Dict[str, Any] = {}
        is_list: Optional[bool] = None
        list_res: List[Any] = []

        while line_idx < len(lines):
            line = lines[line_idx]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                line_idx += 1
                continue

            indent = len(line) - len(line.lstrip(" "))
            if indent < min_indent:
                break

            if stripped.startswith("- "):
                if is_list is None:
                    is_list = True
                content = stripped[2:].strip()
                if ":" in content and not content.startswith("{"):
                    k, v = content.split(":", 1)
                    k = k.strip()
                    v = _strip_inline_yaml_comment(v)
                    sub_dict: Dict[str, Any] = {}
                    if v in ("|", ">"):
                        ml_lines = []
                        line_idx += 1
                        while line_idx < len(lines):
                            ml_line = lines[line_idx]
                            if not ml_line.strip():
                                ml_lines.append("")
                                line_idx += 1
                                continue
                            ml_indent = len(ml_line) - len(ml_line.lstrip(" "))
                            if ml_indent <= indent:
                                break
                            ml_lines.append(ml_line[indent + 2:])
                            line_idx += 1
                        sub_dict[k] = "\n".join(ml_lines).strip()
                    elif v == "":
                        sub_res, line_idx = parse_block(line_idx + 1, indent + 2)
                        sub_dict[k] = sub_res
                    else:
                        sub_dict[k] = _parse_yaml_scalar(v)
                        line_idx += 1

                    while line_idx < len(lines):
                        nxt_line = lines[line_idx]
                        nxt_strip = nxt_line.strip()
                        if not nxt_strip or nxt_strip.startswith("#"):
                            line_idx += 1
                            continue
                        nxt_indent = len(nxt_line) - len(nxt_line.lstrip(" "))
                        if nxt_indent <= indent or nxt_strip.startswith("- "):
                            break
                        if ":" in nxt_strip:
                            nk, nv = nxt_strip.split(":", 1)
                            nk = nk.strip()
                            nv = _strip_inline_yaml_comment(nv)
                            if nv in ("|", ">"):
                                ml_lines = []
                                line_idx += 1
                                while line_idx < len(lines):
                                    ml_line = lines[line_idx]
                                    if not ml_line.strip():
                                        ml_lines.append("")
                                        line_idx += 1
                                        continue
                                    ml_indent = len(ml_line) - len(ml_line.lstrip(" "))
                                    if ml_indent <= nxt_indent:
                                        break
                                    ml_lines.append(ml_line[nxt_indent + 2:])
                                    line_idx += 1
                                sub_dict[nk] = "\n".join(ml_lines).strip()
                            elif nv == "":
                                sub_res, line_idx = parse_block(line_idx + 1, nxt_indent + 2)
                                sub_dict[nk] = sub_res
                            else:
                                sub_dict[nk] = _parse_yaml_scalar(nv)
                                line_idx += 1
                        else:
                            line_idx += 1
                    list_res.append(sub_dict)
                    continue
                else:
                    list_res.append(_parse_yaml_scalar(content))
                    line_idx += 1
                    continue
            else:
                if is_list is True:
                    break
                is_list = False
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = _strip_inline_yaml_comment(v)
                    if v in ("|", ">"):
                        ml_lines = []
                        line_idx += 1
                        while line_idx < len(lines):
                            ml_line = lines[line_idx]
                            if not ml_line.strip():
                                ml_lines.append("")
                                line_idx += 1
                                continue
                            ml_indent = len(ml_line) - len(ml_line.lstrip(" "))
                            if ml_indent <= indent:
                                break
                            ml_lines.append(ml_line[indent + 2:])
                            line_idx += 1
                        res[k] = "\n".join(ml_lines).strip()
                    elif v == "":
                        sub_res, line_idx = parse_block(line_idx + 1, indent + 2)
                        res[k] = sub_res
                    else:
                        res[k] = _parse_yaml_scalar(v)
                        line_idx += 1
                else:
                    line_idx += 1

        return (list_res if is_list else res), line_idx

    result, _ = parse_block(0, 0)
    return result


def dump_simple_yaml(data: Any, indent: int = 0) -> str:
    """Serialize dicts/lists/scalars to clean YAML without external dependencies."""
    lines: List[str] = []
    prefix = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                if not v:
                    lines.append(f"{prefix}{k}: {{}}")
                else:
                    lines.append(f"{prefix}{k}:")
                    lines.append(dump_simple_yaml(v, indent + 1))
            elif isinstance(v, list):
                if not v:
                    lines.append(f"{prefix}{k}: []")
                else:
                    lines.append(f"{prefix}{k}:")
                    lines.append(dump_simple_yaml(v, indent + 1))
            elif isinstance(v, str):
                if "\n" in v:
                    lines.append(f"{prefix}{k}: |")
                    for sub in v.splitlines():
                        lines.append(f"{prefix}  {sub}")
                else:
                    escaped = v.replace('"', '\\"')
                    lines.append(f'{prefix}{k}: "{escaped}"')
            elif v is None:
                lines.append(f"{prefix}{k}: null")
            elif isinstance(v, bool):
                lines.append(f"{prefix}{k}: {'true' if v else 'false'}")
            else:
                lines.append(f"{prefix}{k}: {v}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                first = True
                for k, v in item.items():
                    key_prefix = f"{prefix}- " if first else f"{prefix}  "
                    first = False
                    if isinstance(v, dict):
                        if not v:
                            lines.append(f"{key_prefix}{k}: {{}}")
                        else:
                            lines.append(f"{key_prefix}{k}:")
                            lines.append(dump_simple_yaml(v, indent + 2))
                    elif isinstance(v, list):
                        if not v:
                            lines.append(f"{key_prefix}{k}: []")
                        else:
                            lines.append(f"{key_prefix}{k}:")
                            lines.append(dump_simple_yaml(v, indent + 2))
                    elif isinstance(v, str):
                        escaped = v.replace('"', '\\"')
                        lines.append(f'{key_prefix}{k}: "{escaped}"')
                    elif v is None:
                        lines.append(f"{key_prefix}{k}: null")
                    elif isinstance(v, bool):
                        lines.append(f"{key_prefix}{k}: {'true' if v else 'false'}")
                    else:
                        lines.append(f"{key_prefix}{k}: {v}")
            elif isinstance(item, str):
                escaped = item.replace('"', '\\"')
                lines.append(f'{prefix}- "{escaped}"')
            else:
                lines.append(f"{prefix}- {item}")
    return "\n".join(l for l in lines if l is not None)


def find_workspace_root_for_models(start_dir: Optional[Path] = None) -> Path:
    cwd = (Path(start_dir) if start_dir else Path.cwd()).resolve()
    home = Path.home().resolve()
    for p in [cwd] + list(cwd.parents):
        if p == home or p in home.parents or str(p) == "/":
            break
        if (p / ".agents").exists() or (p / ".git").exists():
            return p
    return cwd


def get_model_config_path(
    workspace_root: Optional[Path] = None,
    write_target: bool = False,
    global_scope: bool = False
) -> Path:
    """Resolve centralized models.yaml path (env override > workspace > global)."""
    env_override = os.environ.get("TEAM_ORCH_MODELS_CONFIG", "").strip()
    if env_override:
        return Path(env_override).expanduser()

    global_cfg = Path.home() / ".gemini" / "team-orch" / "config" / "models.yaml"
    if global_scope:
        return global_cfg

    ws = Path(workspace_root).resolve() if workspace_root else find_workspace_root_for_models()
    local_cfg = ws / ".agents" / "config" / "models.yaml"
    if local_cfg.is_file():
        return local_cfg
    if write_target and (ws / ".agents").is_dir():
        return local_cfg
    if global_cfg.is_file():
        return global_cfg
    return local_cfg if (ws / ".agents").is_dir() else global_cfg


def _deepcopy_default_config() -> Dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_MODEL_CONFIG))


def load_model_config(workspace_root: Optional[Path] = None) -> Dict[str, Any]:
    """Load centralized model configuration with safe fallback merging."""
    cfg = _deepcopy_default_config()
    cfg_path = get_model_config_path(workspace_root=workspace_root, write_target=False)
    if not cfg_path.is_file():
        global_cfg = Path.home() / ".gemini" / "team-orch" / "config" / "models.yaml"
        if global_cfg.is_file():
            cfg_path = global_cfg

    if not cfg_path.is_file():
        return cfg

    try:
        parsed = load_simple_yaml(cfg_path)
    except Exception:
        return cfg

    if not isinstance(parsed, dict) or not parsed:
        return cfg

    if parsed.get("version"):
        cfg["version"] = str(parsed["version"])
    if parsed.get("last_synced"):
        cfg["last_synced"] = str(parsed["last_synced"])

    parsed_tiers = parsed.get("tiers")
    if isinstance(parsed_tiers, dict):
        for t_name in ("low", "medium", "high"):
            if isinstance(parsed_tiers.get(t_name), dict):
                merged_tier = dict(cfg["tiers"][t_name])
                for k, v in parsed_tiers[t_name].items():
                    if v is not None:
                        merged_tier[k] = v
                cfg["tiers"][t_name] = merged_tier

    if "available_models" in parsed and isinstance(parsed["available_models"], list):
        normalized_avail: List[Dict[str, Any]] = []
        for item in parsed["available_models"]:
            if isinstance(item, dict) and item.get("id"):
                normalized_avail.append(item)
            elif isinstance(item, str) and item.strip():
                normalized_avail.append({
                    "id": item.strip(),
                    "display_name": item.strip(),
                    "source": "agy_runtime",
                    "tier_hint": score_and_classify_model(item.strip()).get("tier_hint", "medium")
                })
        if normalized_avail:
            cfg["available_models"] = normalized_avail

    if "api_key_models" in parsed:
        api_list = parsed.get("api_key_models")
        cfg["api_key_models"] = [x for x in api_list if isinstance(x, dict) and x.get("id")] if isinstance(api_list, list) else []

    return cfg


def save_model_config(
    config_data: Dict[str, Any],
    target_path: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
    global_scope: bool = False
) -> Path:
    """Atomically write centralized model configuration to models.yaml."""
    dest = Path(target_path) if target_path else get_model_config_path(
        workspace_root=workspace_root,
        write_target=True,
        global_scope=global_scope
    )
    header = (
        "# ==============================================================================\n"
        "# CENTRALIZED MODEL CONFIGURATION & TIER REGISTRY\n"
        "# ==============================================================================\n"
        "# File: .agents/config/models.yaml\n"
        "# Single Source of Truth untuk pemetaan Tier (low / medium / high) ke Model AI.\n"
        "# ==============================================================================\n\n"
    )
    body = dump_simple_yaml(config_data) + "\n"
    safe_atomic_write(dest, header + body)
    return dest


def normalize_tier_name(tier: Optional[str]) -> str:
    t = str(tier or "medium").strip().lower()
    if t in ("low", "simple", "ringan", "light"):
        return "low"
    if t in ("high", "complex", "kompleks", "berat", "pro", "xhigh"):
        return "high"
    return "medium"


def resolve_tier_config(tier: Optional[str], workspace_root: Optional[Path] = None) -> Dict[str, Any]:
    """Return full tier definition from centralized models.yaml."""
    norm = normalize_tier_name(tier)
    cfg = load_model_config(workspace_root=workspace_root)
    tier_data = dict(cfg.get("tiers", {}).get(norm, DEFAULT_MODEL_CONFIG["tiers"][norm]))
    tier_data["tier"] = norm
    return tier_data


def resolve_model_for_tier(
    tier: Optional[str],
    workspace_root: Optional[Path] = None,
    use_fallback: bool = False
) -> str:
    """Resolve concrete model ID for a given tier ('low', 'medium', 'high')."""
    tier_cfg = resolve_tier_config(tier, workspace_root=workspace_root)
    if use_fallback:
        return str(tier_cfg.get("fallback") or tier_cfg.get("primary") or DEFAULT_MODEL_CONFIG["tiers"]["medium"]["primary"])
    return str(tier_cfg.get("primary") or DEFAULT_MODEL_CONFIG["tiers"]["medium"]["primary"])


def resolve_role_tier_and_model(
    role_id: str,
    role_data: Optional[Dict[str, Any]] = None,
    workspace_root: Optional[Path] = None
) -> Tuple[str, str]:
    """
    Resolve (tier, model_id) dynamically for a role:
    role -> model_tier (role YAML or default) -> centralized models.yaml -> model_id.
    """
    raw_id = str(role_id or "").strip().lower()
    norm_id = ROLE_ALIAS_MAP.get(raw_id, raw_id)
    raw_tier: Optional[str] = None

    if isinstance(role_data, dict) and role_data.get("model_tier"):
        raw_tier = str(role_data.get("model_tier"))
    else:
        ws = Path(workspace_root).resolve() if workspace_root else find_workspace_root_for_models()
        candidate_dirs = [ws / ".agents" / "roles", Path.home() / ".gemini" / "team-orch" / "roles"]
        for r_dir in candidate_dirs:
            yaml_path = r_dir / f"{norm_id}.yaml"
            if yaml_path.is_file():
                try:
                    parsed_role = load_simple_yaml(yaml_path)
                    if isinstance(parsed_role, dict) and parsed_role.get("model_tier"):
                        raw_tier = str(parsed_role["model_tier"])
                        break
                except Exception:
                    pass

    if not raw_tier:
        raw_tier = DEFAULT_ROLE_TIERS.get(raw_id) or DEFAULT_ROLE_TIERS.get(norm_id) or "medium"

    tier = normalize_tier_name(raw_tier)
    model_id = resolve_model_for_tier(tier, workspace_root=workspace_root)
    return tier, model_id


def get_model_runtime_spec(model_id: str, workspace_root: Optional[Path] = None) -> Dict[str, Any]:
    """Return runtime metadata for a model ID (agy_runtime vs api_key BYOK)."""
    cfg = load_model_config(workspace_root=workspace_root)
    target = str(model_id or "").strip()
    for api_m in cfg.get("api_key_models", []):
        if str(api_m.get("id", "")).strip() == target:
            spec = dict(api_m)
            spec["source"] = "api_key"
            return spec
    for av_m in cfg.get("available_models", []):
        if str(av_m.get("id", "")).strip() == target:
            spec = dict(av_m)
            spec.setdefault("source", "agy_runtime")
            return spec
    return {"id": target, "source": "agy_runtime"}


def _extract_model_version(model_id: str) -> Tuple[int, int]:
    """Extract comparable (major, minor) generation version without confusing parameter sizes like 120b."""
    low = model_id.lower()
    patterns = [
        r"^gemini-(\d+)\.(\d+)-",
        r"^gemini-(\d+)-",
        r"^claude-[a-z]+-(\d+)-(\d+)",
        r"^claude-[a-z]+-(\d+)\.(\d+)",
        r"^claude-[a-z]+-(\d+)",
        r"^gpt-(\d+)\.(\d+)",
        r"^gpt-(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, low)
        if m:
            major = int(m.group(1))
            minor = int(m.group(2)) if m.lastindex and m.lastindex >= 2 else 0
            return (major, minor)
    return (0, 0)


def score_and_classify_model(model_id: str, display_name: str = "") -> Dict[str, Any]:
    """
    Classify and rank a model ID across generations and families.
    Ensures newer generations (e.g. gemini-5 > gemini-4 > gemini-3.8) rank higher.
    """
    low_id = str(model_id or "").strip().lower()
    low_disp = str(display_name or "").strip().lower()
    tokens = [t for t in re.split(r"[-_\s]+", low_id) if t]

    provider = "other"
    if low_id.startswith("gemini"):
        provider = "gemini"
    elif low_id.startswith("claude"):
        provider = "claude"
    elif low_id.startswith("gpt"):
        provider = "gpt"

    effort = "medium"
    for eff in ("xhigh", "max", "high", "medium", "low"):
        if tokens and tokens[-1] == eff:
            effort = eff
            break

    family_class = "unknown"
    is_orchestrator_alias = "orchestrator" in low_id
    if any(f in tokens for f in _FRONTIER_FAMILIES) or "pro" in tokens:
        family_class = "frontier"
    elif any(f in tokens for f in _WORKHORSE_FAMILIES) or "gpt-oss" in low_id:
        family_class = "workhorse"

    version = _extract_model_version(low_id)

    if effort == "low" and family_class != "frontier":
        tier_hint = "low"
    elif family_class == "frontier" or effort in ("xhigh", "max"):
        tier_hint = "high"
    else:
        tier_hint = "medium"

    provider_bonus = 2 if provider == "gemini" else (1 if provider == "claude" else 0)
    priority_score = (version[0] * 1000) + (version[1] * 100) + (provider_bonus * 10)
    if is_orchestrator_alias:
        priority_score -= 500

    return {
        "id": model_id,
        "display_name": display_name or model_id,
        "provider": provider,
        "version": version,
        "family_class": family_class,
        "effort": effort,
        "tier_hint": tier_hint,
        "is_orchestrator_alias": is_orchestrator_alias,
        "priority_score": priority_score,
    }


def _parse_agy_models_output(raw_output: str) -> List[Dict[str, Any]]:
    clean = ANSI_ESCAPE_REGEX.sub("", raw_output or "")
    clean = _SPINNER_RE.sub("\n", clean)
    models: List[Dict[str, Any]] = []
    seen = set()
    for line in clean.splitlines():
        line_s = line.strip()
        if not line_s:
            continue
        if line_s.startswith("Usage:") or line_s.startswith("Fetching") or line_s.startswith("List ") or line_s.startswith("Flags:"):
            continue
        m = re.match(r"^([a-z0-9][a-z0-9._-]+)\s+(.+?)$", line_s)
        if not m:
            continue
        mid, disp = m.group(1).strip(), m.group(2).strip()
        if mid in seen:
            continue
        seen.add(mid)
        meta = score_and_classify_model(mid, disp)
        models.append({
            "id": mid,
            "display_name": disp,
            "source": "agy_runtime",
            "tier_hint": meta["tier_hint"],
        })
    return models


def _sub_family_weight(model_id: str, tier: str, family_class: str = "") -> int:
    """Rank sub-families within the same generation (lightest for low, strongest coding workhorse for medium)."""
    tokens = set(re.split(r"[-_\s]+", str(model_id or "").lower()))
    if tier == "low":
        if "hydrogen" in tokens:
            return 3
        if "neon" in tokens:
            return 2
        if "flash" in tokens:
            return 1
        return 0
    if tier == "medium":
        if "neon" in tokens:
            return 3
        if family_class == "unknown":
            return 2
        if "hydrogen" in tokens:
            return 1
        return 0
    return 0


def _pick_best_for_tier(metas: List[Dict[str, Any]], tier: str) -> Tuple[Optional[str], Optional[str]]:
    """Select best primary and fallback model IDs for a tier using generation + provider ranking."""
    if tier == "low":
        pool = [m for m in metas if m["effort"] == "low" and m["family_class"] != "frontier"]
        if not pool:
            pool = [m for m in metas if m["effort"] == "low"]
        ranked = sorted(
            pool,
            key=lambda m: (
                0 if m["is_orchestrator_alias"] else 1,
                2 if m["family_class"] == "workhorse" else 1,
                1 if m["provider"] == "gemini" else 0,
                m["version"],
                _sub_family_weight(m["id"], "low", m["family_class"]),
            ),
            reverse=True,
        )
    elif tier == "medium":
        pool = [m for m in metas if m["family_class"] != "frontier" and m["effort"] != "low"]
        if not pool:
            pool = list(metas)
        ranked = sorted(
            pool,
            key=lambda m: (
                0 if m["is_orchestrator_alias"] else 1,
                1 if m["provider"] == "gemini" else 0,
                m["version"],
                _sub_family_weight(m["id"], "medium", m["family_class"]),
                {"high": 4, "medium": 3, "xhigh": 2, "low": 1}.get(m["effort"], 0),
            ),
            reverse=True,
        )
    else:
        pool = [m for m in metas if m["family_class"] == "frontier" and m["effort"] in ("high", "xhigh", "medium")]
        # Allow newer-generation unknown families to compete within their provider when they outrank existing frontier models
        max_ver_by_prov: Dict[str, Tuple[int, int]] = {}
        for m in pool:
            pv = m["provider"]
            if m["version"] > max_ver_by_prov.get(pv, (0, 0)):
                max_ver_by_prov[pv] = m["version"]
        newer_unknowns = [
            m for m in metas
            if m["family_class"] == "unknown"
            and m["effort"] in ("high", "xhigh")
            and m["version"] > max_ver_by_prov.get(m["provider"], (0, 0))
        ]
        pool.extend(newer_unknowns)
        if not pool:
            pool = list(metas)
        ranked = sorted(
            pool,
            key=lambda m: (
                0 if m["is_orchestrator_alias"] else 1,
                1 if m["provider"] == "gemini" else 0,
                m["version"],
                2 if m["family_class"] == "frontier" else 1,
                {"high": 4, "xhigh": 3, "medium": 2, "low": 1}.get(m["effort"], 0),
            ),
            reverse=True,
        )

    if not ranked:
        return None, None

    primary = ranked[0]["id"]
    fallback = None
    primary_prov = ranked[0]["provider"]
    for cand in ranked[1:]:
        if cand["provider"] != primary_prov:
            fallback = cand["id"]
            break
    if not fallback and len(ranked) > 1:
        fallback = ranked[1]["id"]
    return primary, fallback


def sync_model_config_from_runtime(
    auto_assign: bool = True,
    workspace_root: Optional[Path] = None,
    global_scope: bool = False,
    raw_output: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sync available models from `agy models` into centralized models.yaml,
    optionally auto-upgrading tier primary/fallback mappings to newest generations.
    """
    if raw_output is None:
        agy_bin = shutil.which("agy")
        if not agy_bin:
            return {"status": "error", "error": "Binary 'agy' tidak ditemukan di PATH."}
        try:
            proc = subprocess.run([agy_bin, "models"], capture_output=True, text=True, timeout=30)
            raw_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            if proc.returncode != 0 and not _parse_agy_models_output(raw_output):
                return {"status": "error", "error": f"agy models gagal (exit {proc.returncode}): {raw_output.strip()}"}
        except Exception as exc:
            return {"status": "error", "error": f"Gagal menjalankan 'agy models': {exc}"}

    discovered = _parse_agy_models_output(raw_output)
    if not discovered:
        return {"status": "error", "error": "Tidak ada model valid yang terdeteksi dari output agy models."}

    cfg = load_model_config(workspace_root=workspace_root)
    cfg["available_models"] = discovered
    cfg["last_synced"] = datetime.now(timezone.utc).astimezone().isoformat()

    metas = [score_and_classify_model(m["id"], m["display_name"]) for m in discovered]
    tier_changes: Dict[str, Dict[str, Optional[str]]] = {}

    if auto_assign:
        for t in ("low", "medium", "high"):
            pri, fb = _pick_best_for_tier(metas, t)
            if pri:
                old_pri = cfg["tiers"][t].get("primary")
                cfg["tiers"][t]["primary"] = pri
                if fb:
                    cfg["tiers"][t]["fallback"] = fb
                tier_changes[t] = {"old_primary": old_pri, "new_primary": pri, "fallback": fb}

    saved_path = save_model_config(cfg, workspace_root=workspace_root, global_scope=global_scope)
    return {
        "status": "success",
        "config_path": str(saved_path),
        "discovered_count": len(discovered),
        "auto_assign": auto_assign,
        "tier_changes": tier_changes,
        "tiers": {t: {"primary": cfg["tiers"][t]["primary"], "fallback": cfg["tiers"][t].get("fallback")} for t in ("low", "medium", "high")},
    }


def set_tier_model_in_config(
    tier: str,
    primary_model: str,
    fallback_model: Optional[str] = None,
    effort: Optional[str] = None,
    workspace_root: Optional[Path] = None,
    global_scope: bool = False
) -> Dict[str, Any]:
    """Update primary/fallback/effort for a tier in centralized models.yaml."""
    norm = normalize_tier_name(tier)
    cfg = load_model_config(workspace_root=workspace_root)
    tier_obj = cfg["tiers"].setdefault(norm, dict(DEFAULT_MODEL_CONFIG["tiers"][norm]))
    old_primary = tier_obj.get("primary")
    tier_obj["primary"] = str(primary_model).strip()
    if fallback_model:
        tier_obj["fallback"] = str(fallback_model).strip()
    if effort:
        tier_obj["effort"] = str(effort).strip().lower()

    saved_path = save_model_config(cfg, workspace_root=workspace_root, global_scope=global_scope)
    return {
        "status": "success",
        "config_path": str(saved_path),
        "tier": norm,
        "old_primary": old_primary,
        "primary": tier_obj["primary"],
        "fallback": tier_obj.get("fallback"),
        "effort": tier_obj.get("effort"),
    }


def add_api_key_model_to_config(
    model_id: str,
    tier: str,
    provider: str,
    api_key_env: str,
    display_name: Optional[str] = None,
    base_url: Optional[str] = None,
    set_primary: bool = False,
    workspace_root: Optional[Path] = None,
    global_scope: bool = False
) -> Dict[str, Any]:
    """Register or update a BYOK / API-key model entry without storing raw secrets."""
    norm_tier = normalize_tier_name(tier)
    clean_id = str(model_id).strip()
    clean_env = str(api_key_env).strip()
    if not clean_id or not clean_env:
        return {"status": "error", "error": "model_id dan api_key_env wajib diisi."}

    cfg = load_model_config(workspace_root=workspace_root)
    api_models: List[Dict[str, Any]] = [
        m for m in cfg.get("api_key_models", []) if str(m.get("id", "")).strip() != clean_id
    ]
    entry: Dict[str, Any] = {
        "id": clean_id,
        "display_name": (display_name or clean_id).strip(),
        "provider": str(provider).strip().lower(),
        "api_key_env": clean_env,
        "tier": norm_tier,
        "source": "api_key",
    }
    if base_url:
        entry["base_url"] = str(base_url).strip()

    api_models.append(entry)
    cfg["api_key_models"] = api_models

    if set_primary:
        cfg["tiers"][norm_tier]["primary"] = clean_id

    saved_path = save_model_config(cfg, workspace_root=workspace_root, global_scope=global_scope)
    return {
        "status": "success",
        "config_path": str(saved_path),
        "model": entry,
        "set_primary": set_primary,
    }


def remove_api_key_model_from_config(
    model_id: str,
    workspace_root: Optional[Path] = None,
    global_scope: bool = False
) -> Dict[str, Any]:
    """Remove a registered API-key model entry from centralized models.yaml."""
    clean_id = str(model_id).strip()
    cfg = load_model_config(workspace_root=workspace_root)
    existing = cfg.get("api_key_models", [])
    remaining = [m for m in existing if str(m.get("id", "")).strip() != clean_id]
    removed = len(existing) - len(remaining)
    cfg["api_key_models"] = remaining

    # Reset any tier primary that pointed to the removed model back to default fallback/default
    for t_name in ("low", "medium", "high"):
        t_obj = cfg["tiers"].get(t_name, {})
        if t_obj.get("primary") == clean_id:
            t_obj["primary"] = t_obj.get("fallback") or DEFAULT_MODEL_CONFIG["tiers"][t_name]["primary"]

    saved_path = save_model_config(cfg, workspace_root=workspace_root, global_scope=global_scope)
    return {
        "status": "success" if removed > 0 else "not_found",
        "config_path": str(saved_path),
        "removed_count": removed,
        "model_id": clean_id,
    }

