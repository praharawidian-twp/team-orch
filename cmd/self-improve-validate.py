#!/usr/bin/env python3
"""
Self-Improvement Framework — Canary Validator (Pre-Human-Review Gate)
======================================================================
Komponen: Pilar 3 — Layer 8 (Automated Canary Validation)
Referensi: .agents/tasks/active/self-improvement/02-technical-spec.md §3.8

Menjalankan validasi deterministik lokal (0-token) terhadap draf proposal
SEBELUM diajukan ke Manusia di Control Room untuk ditinjau.

Jenis validasi:
  - Markdown: Frontmatter YAML valid + semua required heading hadir
  - YAML config: Schema validator (structural check)
  - Python script: Syntax check via py_compile
  - Shell script: Syntax check via 'bash -n'
  - AMEND mode: Diff section tidak boleh kosong

Exit codes:
  0 = [CANARY_PASS] — Draf valid, siap diajukan ke Manusia
  1 = [INVALID_DRAFT_SYNTAX] — Draf memiliki error, dikembalikan ke agen

Usage:
  python3 cmd/self-improve-validate.py --draft <path_to_draft.md>
  python3 cmd/self-improve-validate.py --draft <path> --type knowledge
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# Required frontmatter fields untuk setiap tipe draf
REQUIRED_FRONTMATTER: dict[str, list[str]] = {
    "knowledge": ["draft_id", "category", "status", "generated_at", "generated_by"],
    "skill": ["draft_id", "category", "status", "generated_at"],
    "role": ["draft_id", "category", "status", "generated_at", "generated_by"],
    "default": ["draft_id", "category", "status"],
}

# Required headings untuk setiap tipe draf
REQUIRED_HEADINGS: dict[str, list[str]] = {
    "knowledge": [
        "## 1. Masalah yang Dideteksi",
        "## 2. Analisis Root Cause",
        "## 3. Solusi yang Diusulkan",
        "## 4. Diff Terhadap Versi Sebelumnya",
        "## 5. Dampak yang Diharapkan",
        "## 6. Risk Assessment",
    ],
    "skill": [
        "## 1. Masalah yang Dideteksi",
        "## 3. Solusi yang Diusulkan",
    ],
    "role": [
        "## 1. Masalah yang Dideteksi",
        "## 3. Solusi yang Diusulkan",
        "## 4. Diff Terhadap Versi Sebelumnya",
    ],
    "default": ["## 1. Masalah yang Dideteksi", "## 3. Solusi yang Diusulkan"],
}


def validate_markdown_draft(content: str, draft_type: str) -> list[str]:
    """Validasi struktur Markdown draf proposal."""
    errors = []

    # 1. Frontmatter check
    if not content.startswith("---"):
        errors.append("Frontmatter YAML tidak ditemukan. Draf harus dimulai dengan '---'.")
    else:
        fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            errors.append("Frontmatter YAML tidak tertutup dengan '---'.")
        else:
            fm_content = fm_match.group(1)
            required_fields = REQUIRED_FRONTMATTER.get(
                draft_type, REQUIRED_FRONTMATTER["default"]
            )
            for field in required_fields:
                if not re.search(rf"^{re.escape(field)}\s*:", fm_content, re.MULTILINE):
                    errors.append(f"Frontmatter field wajib tidak ditemukan: '{field}'.")

            # Cek status value
            status_match = re.search(r"^status\s*:\s*(.+)$", fm_content, re.MULTILINE)
            if status_match:
                status = status_match.group(1).strip().strip('"').strip("'")
                valid_statuses = {"PENDING_HUMAN_APPROVAL", "DRAFT", "AMENDING"}
                if status not in valid_statuses:
                    errors.append(
                        f"Status '{status}' tidak valid. "
                        f"Gunakan salah satu: {valid_statuses}"
                    )

    # 2. Required headings check
    required_headings = REQUIRED_HEADINGS.get(draft_type, REQUIRED_HEADINGS["default"])
    for heading in required_headings:
        # Normalize heading check (case-insensitive partial match)
        heading_keyword = heading.split(". ", 1)[-1] if ". " in heading else heading.lstrip("#").strip()
        if heading_keyword.lower() not in content.lower():
            errors.append(f"Required heading tidak ditemukan: '{heading}'.")

    # 3. AMEND mode: diff section tidak boleh kosong
    diff_match = re.search(
        r"## 4\. Diff Terhadap Versi Sebelumnya\s*\n(.*?)(?=\n## |\Z)",
        content,
        re.DOTALL,
    )
    if diff_match:
        diff_content = diff_match.group(1).strip()
        if not diff_content or diff_content == "<!-- WAJIB: tampilkan diff eksplisit -->":
            errors.append(
                "Section 'Diff Terhadap Versi Sebelumnya' kosong. "
                "Jika ini adalah revisi (AMEND), wajib menyertakan diff eksplisit. "
                "Jika ini entitas baru, tulis 'N/A - Entitas Baru'."
            )

    # 4. Cek context_snippet di dalam draf (tidak boleh ada yang kosong)
    empty_snippet = re.search(r"context_snippet[\"']?\s*:\s*[\"']{2}", content)
    if empty_snippet:
        errors.append(
            "Terdapat context_snippet kosong dalam draf. "
            "Setiap signature harus memiliki context_snippet yang deskriptif."
        )

    return errors


def validate_yaml_config(content: str) -> list[str]:
    """Validasi struktur YAML konfigurasi."""
    errors = []
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            errors.append("File YAML harus berupa mapping (dict) di level teratas.")
    except ImportError:
        # Fallback: validasi manual sederhana
        required_keys = ["version", "enabled"]
        for key in required_keys:
            if not re.search(rf"^{re.escape(key)}\s*:", content, re.MULTILINE):
                errors.append(f"Required YAML key tidak ditemukan: '{key}'.")
    except Exception as e:
        errors.append(f"Error parsing YAML: {e}")
    return errors


def validate_python_script(content: str) -> list[str]:
    """Validasi syntax Python menggunakan py_compile."""
    errors = []
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", tmp_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            error_msg = result.stderr.replace(tmp_path, "<script>")
            errors.append(f"Python syntax error: {error_msg.strip()}")
    except subprocess.TimeoutExpired:
        errors.append("Python syntax check timeout (>10 detik).")
    except Exception as e:
        errors.append(f"Error saat validasi Python: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return errors


def validate_shell_script(content: str) -> list[str]:
    """Validasi syntax shell script menggunakan bash -n."""
    errors = []
    with tempfile.NamedTemporaryFile(suffix=".sh", mode="w", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            ["bash", "-n", tmp_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            error_msg = result.stderr.replace(tmp_path, "<script>")
            errors.append(f"Shell syntax error: {error_msg.strip()}")
    except FileNotFoundError:
        pass  # bash tidak tersedia — skip
    except subprocess.TimeoutExpired:
        errors.append("Shell syntax check timeout (>10 detik).")
    except Exception as e:
        errors.append(f"Error saat validasi shell: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return errors


def detect_draft_type(content: str, draft_path: Path) -> str:
    """Deteksi tipe draf dari frontmatter atau path."""
    # Cek frontmatter category
    cat_match = re.search(r"^category\s*:\s*[\"']?(\w+)", content, re.MULTILINE)
    if cat_match:
        cat = cat_match.group(1).lower()
        if "knowledge" in cat:
            return "knowledge"
        if "skill" in cat:
            return "skill"
        if "role" in cat:
            return "role"

    # Fallback ke path
    path_str = str(draft_path).lower()
    if "skill" in path_str:
        return "skill"
    if "role" in path_str:
        return "role"

    return "knowledge"  # default


def validate_draft(draft_path: Path, draft_type: str | None = None) -> tuple[bool, list[str]]:
    """
    Validasi file draf secara komprehensif.

    Returns:
        (is_valid: bool, errors: list[str])
    """
    if not draft_path.exists():
        return False, [f"File draf tidak ditemukan: {draft_path}"]

    content = draft_path.read_text(encoding="utf-8", errors="replace")
    suffix = draft_path.suffix.lower()
    all_errors: list[str] = []

    # Deteksi tipe jika belum ditentukan
    if not draft_type:
        if suffix in (".md", ".markdown"):
            draft_type = detect_draft_type(content, draft_path)
        elif suffix in (".yaml", ".yml"):
            draft_type = "yaml"
        elif suffix == ".py":
            draft_type = "python"
        elif suffix == ".sh":
            draft_type = "shell"
        else:
            draft_type = "default"

    # Jalankan validator sesuai tipe
    if suffix in (".md", ".markdown"):
        all_errors.extend(validate_markdown_draft(content, draft_type))
    elif suffix in (".yaml", ".yml"):
        all_errors.extend(validate_yaml_config(content))
    elif suffix == ".py":
        all_errors.extend(validate_python_script(content))
    elif suffix == ".sh":
        all_errors.extend(validate_shell_script(content))

    # Universal: cek ukuran file (draf tidak boleh terlalu besar)
    size_bytes = len(content.encode("utf-8"))
    if size_bytes > 50_000:  # 50 KB limit
        all_errors.append(
            f"Ukuran draf ({size_bytes:,} bytes) melebihi batas 50 KB. "
            "Pecah proposal menjadi beberapa draf yang lebih fokus."
        )

    return len(all_errors) == 0, all_errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Self-Improvement Canary Validator — Pre-Human-Review Gate",
    )
    parser.add_argument(
        "--draft", "-d",
        required=True,
        help="Path ke file draf yang akan divalidasi",
    )
    parser.add_argument(
        "--type", "-t",
        choices=["knowledge", "skill", "role", "yaml", "python", "shell", "default"],
        help="Tipe draf (auto-detect jika tidak ditentukan)",
    )
    args = parser.parse_args()

    draft_path = Path(args.draft)
    print(f"[CANARY] Memvalidasi draf: {draft_path}")

    is_valid, errors = validate_draft(draft_path, args.type)

    if is_valid:
        print("[CANARY_PASS] ✓ Draf valid — siap diajukan ke Manusia untuk ditinjau.")
        return 0
    else:
        print("[INVALID_DRAFT_SYNTAX] ✗ Draf memiliki error:")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
        print()
        print("Silakan perbaiki error di atas sebelum mengajukan ulang ke Human Review Queue.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
