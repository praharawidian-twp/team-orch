#!/usr/bin/env python3
"""
ui-capture - Orchestrator CLI for UI Evidence Capture.
Zero external dependencies: 100% Python standard library only.
"""

import sys
import os
import json
import argparse
import re
import datetime
import subprocess
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Import backends and utilities
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from backends.base import (
        detect_human_challenge,
        sanitize_url_for_log,
        calculate_sha256,
        validate_path_safety,
        load_yaml_file,
        parse_simple_yaml,
        validate_page_authenticity,
        validate_section_target,
        build_dom_telemetry,
        DEFAULT_FORBIDDEN_ERROR_PATTERNS,
    )
    from backends.manual import ManualBackend
    from backends.playwright_python import PlaywrightPythonBackend
except ImportError:
    # If run directly as module or standalone
    from .backends.base import (
        detect_human_challenge,
        sanitize_url_for_log,
        calculate_sha256,
        validate_path_safety,
        load_yaml_file,
        parse_simple_yaml,
        validate_page_authenticity,
        validate_section_target,
        build_dom_telemetry,
        DEFAULT_FORBIDDEN_ERROR_PATTERNS,
    )
    from .backends.manual import ManualBackend
    from .backends.playwright_python import PlaywrightPythonBackend

# Standard Exit Codes
EXIT_OK = 0
EXIT_NEEDS_HUMAN_URL_CONFIRMATION = 3
EXIT_INVALID_UI_TARGET_PAGE = 4
EXIT_SECTION_VALIDATION_FAILED = 5
EXIT_CONSENT_REQUIRED = 10
EXIT_NO_BACKEND = 11
EXIT_AUTH_REQUIRED = 20
EXIT_HUMAN_CHALLENGE = 21
EXIT_ORIGIN_NOT_ALLOWED = 30
EXIT_READ_ONLY_VIOLATION = 31
EXIT_INVALID_ARGS = 40
EXIT_BACKEND_ERROR = 50

TOOL_DIR_DEFAULT = Path(os.environ.get("UI_CAPTURE_TOOL_DIR") or (Path.home() / ".gemini" / "tools" / "ui-capture"))

def get_project_paths(project_id: str) -> Tuple[Path, Path, Path]:
    """
    Resolve config_file, secrets_dir, and evidence_dir for project.
    """
    cwd = Path.cwd()
    # Check if we are inside project root with .agents/
    config_file = cwd / ".agents" / "config" / "qa-ui.config.json"
    secrets_dir = cwd / ".agents" / "secrets" / project_id
    evidence_dir = cwd / "docs" / "qa" / "evidence"

    # If not in cwd, check if project_id exists as subdirectory
    if not config_file.exists() and (cwd / project_id).is_dir():
        proj_root = cwd / project_id
        config_file = proj_root / ".agents" / "config" / "qa-ui.config.json"
        secrets_dir = proj_root / ".agents" / "secrets" / project_id
        evidence_dir = proj_root / "docs" / "qa" / "evidence"

    return config_file, secrets_dir, evidence_dir

def load_config(project_id: str) -> Dict[str, Any]:
    config_file, _, evidence_dir = get_project_paths(project_id)
    if config_file.exists():
        try:
            return json.loads(config_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[!] Warning: Gagal membaca config: {e}", file=sys.stderr)
    return {
        "project_id": project_id,
        "allowed_origins": [],
        "login_url": "",
        "post_login_selector": "",
        "read_only": True,
        "allow_mutation_paths": [],
        "session_ttl_hours": 8,
        "default_viewport": "1440x900",
        "mask_selectors": ["input[type=password]", "[data-sensitive]"],
        "backend_preference": "auto",
        "credential_model": "human_session",
        "evidence_root": str(evidence_dir.relative_to(Path.cwd()) if evidence_dir.is_relative_to(Path.cwd()) else "docs/qa/evidence")
    }

def detect_all_backends(tool_dir: Path = TOOL_DIR_DEFAULT) -> Dict[str, Any]:
    py_backend = PlaywrightPythonBackend()
    py_avail, py_ver, py_details = py_backend.detect(tool_dir)

    # Detect Node Playwright
    node_avail = False
    node_ver = ""
    try:
        node_res = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=3)
        if node_res.returncode == 0:
            node_ver = node_res.stdout.strip()
            node_pkg = tool_dir / "node" / "node_modules" / "playwright"
            if node_pkg.exists():
                node_avail = True
    except Exception:
        pass

    manual_backend = ManualBackend()
    man_avail, man_ver, man_details = manual_backend.detect(tool_dir)

    return {
        "playwright-python": {
            "available": py_avail,
            "version": py_ver,
            "details": py_details
        },
        "playwright-node": {
            "available": node_avail,
            "version": node_ver,
            "install_dir": str(tool_dir / "node")
        },
        "manual": {
            "available": man_avail,
            "version": man_ver,
            "details": man_details
        },
        "mcp": "agent-side, unknown"
    }

# ----------------------------------------------------------------------
# Subcommand: DOCTOR
# ----------------------------------------------------------------------
def cmd_doctor(args: argparse.Namespace) -> int:
    backends_status = detect_all_backends()
    has_browser = (
        backends_status["playwright-python"]["available"] or
        backends_status["playwright-node"]["available"]
    )

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    node_ver = None
    try:
        n_res = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=3)
        if n_res.returncode == 0:
            node_ver = n_res.stdout.strip()
    except Exception:
        pass

    project_id = args.project or "default"
    config_file, secrets_dir, _ = get_project_paths(project_id)
    session_file = secrets_dir / "ui-auth-state.json"
    meta_file = secrets_dir / "ui-auth-meta.json"

    session_valid = False
    session_expires = None
    if session_file.exists() and meta_file.exists():
        try:
            m = json.loads(meta_file.read_text(encoding="utf-8"))
            exp_str = m.get("expires_at")
            if exp_str:
                exp_dt = datetime.datetime.fromisoformat(exp_str)
                now_dt = datetime.datetime.now(datetime.timezone.utc).astimezone()
                if exp_dt > now_dt:
                    session_valid = True
                    session_expires = exp_str
        except Exception:
            pass

    options = [
        {
            "option": 1,
            "name": "Playwright Python",
            "recommended": True,
            "install_dir": str(TOOL_DIR_DEFAULT / "venv"),
            "approx_size_mb": "150-200",
            "requires_network": True,
            "commands": [
                f"python3 -m venv {TOOL_DIR_DEFAULT}/venv",
                f"{TOOL_DIR_DEFAULT}/venv/bin/pip install playwright",
                f"{TOOL_DIR_DEFAULT}/venv/bin/python -m playwright install chromium"
            ]
        },
        {
            "option": 2,
            "name": "Playwright Node",
            "recommended": False,
            "install_dir": str(TOOL_DIR_DEFAULT / "node"),
            "approx_size_mb": "150-200",
            "requires_network": True,
            "commands": [
                f"npm --prefix {TOOL_DIR_DEFAULT}/node i playwright",
                f"npx --prefix {TOOL_DIR_DEFAULT}/node playwright install chromium"
            ]
        },
        {
            "option": 3,
            "name": "Playwright MCP",
            "recommended": False,
            "install_dir": None,
            "approx_size_mb": "0",
            "requires_network": False,
            "commands": []
        },
        {
            "option": 4,
            "name": "Manual",
            "recommended": False,
            "install_dir": None,
            "approx_size_mb": "0",
            "requires_network": False,
            "commands": []
        },
        {
            "option": 5,
            "name": "Tunda",
            "recommended": False,
            "install_dir": None,
            "approx_size_mb": "0",
            "requires_network": False,
            "commands": []
        }
    ]

    consent_prompt = (
        "Kebutuhan screenshot UI belum terpasang. Pilih salah satu:\n"
        "1. (Rekomendasi) Playwright Python — instal ke tool dir terisolasi ~/.gemini/tools/ui-capture/venv + Chromium (~150–200 MB). Tidak mengubah dependensi project.\n"
        "2. Playwright Node — instal ke ~/.gemini/tools/ui-capture/node + Chromium (~150–200 MB).\n"
        "3. Playwright MCP — tanpa instal oleh agent; saya berikan snippet konfigurasi MCP untuk Anda pasang sendiri.\n"
        "4. Manual — tanpa instalasi; saya buatkan panduan screenshot di folder evidence untuk Anda isi.\n"
        "5. Tunda — lewati screenshot untuk siklus ini."
    )

    if has_browser:
        active_b = "playwright-python" if backends_status["playwright-python"]["available"] else "playwright-node"
        result = {
            "status": "ready",
            "exit_code": EXIT_OK,
            "python3": py_ver,
            "node": node_ver,
            "backends": backends_status,
            "active_backend": active_b,
            "project_config": {
                "exists": config_file.exists(),
                "path": str(config_file)
            },
            "session": {
                "active": session_valid,
                "expires_at": session_expires
            }
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"[✓] UI Evidence Capture siap digunakan! Backend aktif: {active_b}")
        return EXIT_OK
    else:
        result = {
            "status": "no_backend",
            "exit_code": EXIT_NO_BACKEND,
            "recommended_action": "prompt_consent_gate",
            "message": "Kebutuhan screenshot UI belum terpasang.",
            "consent_prompt": consent_prompt,
            "options": options,
            "python3": py_ver,
            "node": node_ver,
            "backends": backends_status,
            "active_backend": "manual",
            "project_config": {
                "exists": config_file.exists(),
                "path": str(config_file)
            },
            "session": {
                "active": session_valid,
                "expires_at": session_expires
            }
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"[!] {consent_prompt}")
        return EXIT_NO_BACKEND

# ----------------------------------------------------------------------
# Subcommand: SETUP
# ----------------------------------------------------------------------
def cmd_setup(args: argparse.Namespace) -> int:
    backend = args.backend
    tool_dir = TOOL_DIR_DEFAULT

    if backend == "playwright-python":
        install_dir = tool_dir / "venv"
        cmds = [
            f"python3 -m venv {install_dir}",
            f"{install_dir}/bin/pip install playwright",
            f"{install_dir}/bin/python -m playwright install chromium"
        ]
    elif backend == "playwright-node":
        install_dir = tool_dir / "node"
        cmds = [
            f"npm --prefix {install_dir} i playwright",
            f"npx --prefix {install_dir} playwright install chromium"
        ]
    else:
        print(f"[✗] Backend tidak dikenali: {backend}", file=sys.stderr)
        return EXIT_INVALID_ARGS

    if not args.yes:
        # Dry-run plan only without modifying the system
        plan = {
            "action": "setup_plan",
            "exit_code": EXIT_CONSENT_REQUIRED,
            "backend": backend,
            "install_directory": str(install_dir),
            "estimated_size_mb": "150-200",
            "requires_network": True,
            "commands": cmds,
            "message": "Persetujuan manusia (--yes) diperlukan sebelum mengeksekusi instalasi."
        }
        if args.json:
            print(json.dumps(plan, indent=2))
        else:
            print("[*] Rencana Instalasi Backend Browser:")
            print(f"  Backend      : {backend}")
            print(f"  Lokasi       : {install_dir}")
            print(f"  Estimasi     : ~150-200 MB")
            print("  Perintah yang akan dijalankan:")
            for c in cmds:
                print(f"    $ {c}")
            print("\n[!] PERINGATAN: Gunakan flag --yes hanya setelah persetujuan eksplisit pengguna.")
        return EXIT_CONSENT_REQUIRED

    # Execute installation with explicit consent
    print(f"[*] Menjalankan instalasi backend {backend} ke {install_dir}...")
    install_dir.mkdir(parents=True, exist_ok=True)
    for c in cmds:
        print(f"[*] $ {c}")
        res = subprocess.run(c, shell=True)
        if res.returncode != 0:
            print(f"[✗] Gagal menjalankan: {c}", file=sys.stderr)
            return EXIT_BACKEND_ERROR

    print(f"[✓] Backend {backend} berhasil dipasang!")
    return EXIT_OK

# ----------------------------------------------------------------------
# Subcommand: INIT
# ----------------------------------------------------------------------
def cmd_init(args: argparse.Namespace) -> int:
    project_id = args.project
    origin = args.origin
    login_url = args.login_url or f"{origin.rstrip('/')}/login"

    config_file, secrets_dir, evidence_dir = get_project_paths(project_id)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    secrets_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(secrets_dir, 0o700)
    except Exception:
        pass

    # 1. Write or update qa-ui.config.json
    cfg = {
        "project_id": project_id,
        "allowed_origins": [origin],
        "login_url": login_url,
        "post_login_selector": "",
        "read_only": True,
        "allow_mutation_paths": [],
        "session_ttl_hours": 8,
        "default_viewport": "1440x900",
        "mask_selectors": ["input[type=password]", "[data-sensitive]"],
        "backend_preference": "auto",
        "credential_model": "human_session",
        "evidence_root": "docs/qa/evidence"
    }
    config_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    # 2. Add .agents/secrets/ to .gitignore (idempotent)
    gitignore_path = Path.cwd() / ".gitignore"
    if not gitignore_path.exists():
        # Check parent or project directory
        if (Path.cwd() / project_id / ".gitignore").exists():
            gitignore_path = Path.cwd() / project_id / ".gitignore"

    secret_entry = ".agents/secrets/"
    gitignore_updated = False
    if gitignore_path.exists():
        lines = gitignore_path.read_text(encoding="utf-8").splitlines()
        has_entry = any(l.strip() in [secret_entry, ".agents/secrets", ".agents/secrets/*"] for l in lines)
        if not has_entry:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write(f"\n# UI Evidence Auth Secrets\n{secret_entry}\n")
            gitignore_updated = True
    else:
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(f"# UI Evidence Auth Secrets\n{secret_entry}\n")
        gitignore_updated = True

    res = {
        "status": "initialized",
        "exit_code": EXIT_OK,
        "project_id": project_id,
        "config_file": str(config_file),
        "gitignore_updated": gitignore_updated
    }
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"[✓] Konfigurasi UI Evidence dibuat di: {config_file}")
        print(f"[✓] .gitignore diperiksa: .agents/secrets/ diamankan.")
    return EXIT_OK

# ----------------------------------------------------------------------
# Subcommand: LOGIN
# ----------------------------------------------------------------------
def cmd_login(args: argparse.Namespace) -> int:
    project_id = args.project
    config = load_config(project_id)
    _, secrets_dir, _ = get_project_paths(project_id)
    secrets_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(secrets_dir, 0o700)
    except Exception:
        pass

    session_path = secrets_dir / "ui-auth-state.json"
    meta_path = secrets_dir / "ui-auth-meta.json"

    backends = detect_all_backends()
    if backends["playwright-python"]["available"]:
        backend = PlaywrightPythonBackend()
        return backend.login(config, session_path, meta_path, headed=True)
    elif backends["playwright-node"]["available"]:
        # Node login
        print("[*] Menggunakan backend Playwright Node untuk login...")
        node_script = SCRIPT_DIR / "backends" / "playwright_node.mjs"
        payload = {
            "login_url": config.get("login_url"),
            "session_path": str(session_path),
            "post_login_selector": config.get("post_login_selector")
        }
        res = subprocess.run(["node", str(node_script), "login"], input=json.dumps(payload), text=True)
        return res.returncode
    else:
        print("[!] Backend browser tidak tersedia untuk login interaktif.", file=sys.stderr)
        return EXIT_NO_BACKEND

# ----------------------------------------------------------------------
# Subcommand: TARGETS (Target Registry & Anti-Guessing Gate)
# ----------------------------------------------------------------------
def find_targets_file(project_id: str, custom_path: Optional[str] = None) -> Optional[Path]:
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            return p
        cwd_p = Path.cwd() / custom_path
        if cwd_p.exists():
            return cwd_p
        return None

    candidates = [
        Path.cwd() / ".agents" / "tasks" / "active" / project_id / "qa-targets.yaml",
        Path.cwd() / project_id / ".agents" / "tasks" / "active" / project_id / "qa-targets.yaml",
        Path.cwd() / ".agents" / "config" / "qa-targets.yaml",
        Path.cwd() / "docs" / "qa" / "qa-targets.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

def cmd_targets(args: argparse.Namespace) -> int:
    project_id = args.project
    targets_file = find_targets_file(project_id, getattr(args, "targets_file", None))
    if not targets_file or not targets_file.exists():
        err = {"status": "error", "message": f"File qa-targets.yaml tidak ditemukan untuk project '{project_id}'."}
        if getattr(args, "json", False):
            print(json.dumps(err, indent=2))
        else:
            print(f"[✗] Error: {err['message']}", file=sys.stderr)
        return EXIT_INVALID_ARGS

    data = load_yaml_file(targets_file)
    ui_targets = data.get("ui_targets", {})
    api_targets = data.get("api_targets", {})

    target_name = getattr(args, "target", None)
    if target_name:
        target = ui_targets.get(target_name) or api_targets.get(target_name)
        if not target:
            err = {"status": "error", "message": f"Target '{target_name}' tidak ditemukan di {targets_file}"}
            if getattr(args, "json", False):
                print(json.dumps(err, indent=2))
            else:
                print(f"[✗] Error: {err['message']}", file=sys.stderr)
            return EXIT_INVALID_ARGS

        st = target.get("status", "")
        base_url = target.get("base_url", "")
        human_conf = target.get("human_confirmed", False)

        if st == "NEEDS_HUMAN_URL_CONFIRMATION" or not base_url or human_conf is False:
            res = {
                "status": "NEEDS_HUMAN_URL_CONFIRMATION",
                "exit_code": EXIT_NEEDS_HUMAN_URL_CONFIRMATION,
                "project_id": project_id,
                "target": target_name,
                "target_info": target,
                "message": f"Target '{target_name}' memerlukan konfirmasi URL dari Pengguna manusia sebelum eksekusi."
            }
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2))
            else:
                print(f"[!] PERHATIAN: Target '{target_name}' memerlukan konfirmasi URL manusia (status={st}, base_url='{base_url}').")
            return EXIT_NEEDS_HUMAN_URL_CONFIRMATION
        else:
            res = {
                "status": "confirmed",
                "exit_code": EXIT_OK,
                "project_id": project_id,
                "target": target_name,
                "target_info": target
            }
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2))
            else:
                print(f"[✓] Target '{target_name}' terverifikasi siap ({base_url}).")
            return EXIT_OK

    # Check all ui_targets
    unconfirmed = []
    for t_name, t_val in ui_targets.items():
        if isinstance(t_val, dict):
            st = t_val.get("status", "")
            base_url = t_val.get("base_url", "")
            human_conf = t_val.get("human_confirmed", False)
            if st == "NEEDS_HUMAN_URL_CONFIRMATION" or not base_url or human_conf is False:
                unconfirmed.append({"target": t_name, "status": st, "base_url": base_url, "details": t_val})

    if unconfirmed:
        res = {
            "status": "NEEDS_HUMAN_URL_CONFIRMATION",
            "exit_code": EXIT_NEEDS_HUMAN_URL_CONFIRMATION,
            "project_id": project_id,
            "unconfirmed_targets": unconfirmed,
            "message": "Satu atau lebih UI target memerlukan konfirmasi URL manusia."
        }
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            print("[!] Satu atau lebih target UI belum dikonfirmasi oleh manusia:")
            for u in unconfirmed:
                print(f"  - {u['target']}: status={u['status']}, base_url={u['base_url']}")
        return EXIT_NEEDS_HUMAN_URL_CONFIRMATION

    res = {
        "status": "confirmed",
        "exit_code": EXIT_OK,
        "project_id": project_id,
        "ui_targets": ui_targets,
        "api_targets": api_targets
    }
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2))
    else:
        print(f"[✓] Seluruh target pada {targets_file} terkonfirmasi sah.")
    return EXIT_OK

# ----------------------------------------------------------------------
# Subcommand: SHOT
# ----------------------------------------------------------------------
def cmd_shot(args: argparse.Namespace) -> int:
    project_id = args.project
    tc = args.tc
    name = args.name
    url = getattr(args, "url", None)

    # Resolve target-name from qa-targets.yaml if supplied
    target_name = getattr(args, "target_name", None)
    if target_name:
        targets_file = find_targets_file(project_id, getattr(args, "targets_file", None))
        if not targets_file or not targets_file.exists():
            print(f"[✗] Error: qa-targets.yaml tidak ditemukan untuk lookup target '{target_name}'.", file=sys.stderr)
            return EXIT_INVALID_ARGS

        data = load_yaml_file(targets_file)
        t_info = data.get("ui_targets", {}).get(target_name) or data.get("api_targets", {}).get(target_name)
        if not t_info:
            print(f"[✗] Error: target-name '{target_name}' tidak ditemukan di {targets_file}", file=sys.stderr)
            return EXIT_INVALID_ARGS

        st = t_info.get("status", "")
        base_url = t_info.get("base_url", "")
        human_conf = t_info.get("human_confirmed", False)
        if st == "NEEDS_HUMAN_URL_CONFIRMATION" or not base_url or human_conf is False:
            res = {
                "status": "NEEDS_HUMAN_URL_CONFIRMATION",
                "exit_code": EXIT_NEEDS_HUMAN_URL_CONFIRMATION,
                "project_id": project_id,
                "target": target_name,
                "message": f"Target '{target_name}' berstatus NEEDS_HUMAN_URL_CONFIRMATION. Tanya manusia terlebih dahulu!"
            }
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2))
            else:
                print(f"[!] PERHATIAN: Target '{target_name}' belum dikonfirmasi manusia: {base_url}", file=sys.stderr)
            return EXIT_NEEDS_HUMAN_URL_CONFIRMATION

        if not url:
            url = base_url

    if not url:
        print("[✗] Error: URL target wajib diberikan melalui --url atau --target-name yang valid.", file=sys.stderr)
        return EXIT_INVALID_ARGS

    # 1. Path Safety Check
    config = load_config(project_id)
    cwd = Path.cwd()
    evidence_root = Path(config.get("evidence_root", "docs/qa/evidence"))
    if not evidence_root.is_absolute():
        evidence_root = cwd / evidence_root

    is_safe, output_path, err_msg = validate_path_safety(tc, name, evidence_root)
    if not is_safe:
        print(f"[✗] Error: {err_msg}", file=sys.stderr)
        return EXIT_INVALID_ARGS

    # 2. Allowed Origin Check
    allowed_origins = list(config.get("allowed_origins", []))
    parsed_url = urllib.parse.urlsplit(url)
    origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
    if target_name and origin not in allowed_origins:
        allowed_origins.append(origin)
    if allowed_origins and origin not in allowed_origins:
        print(f"[✗] Origin '{origin}' tidak terdaftar pada allowed_origins!", file=sys.stderr)
        return EXIT_ORIGIN_NOT_ALLOWED

    # 3. Session Check (if human_session model)
    _, secrets_dir, _ = get_project_paths(project_id)
    session_path = secrets_dir / "ui-auth-state.json"
    meta_path = secrets_dir / "ui-auth-meta.json"

    backend_choice = args.backend or config.get("backend_preference", "auto")

    # If backend is not explicitly manual, verify session
    if backend_choice != "manual":
        if config.get("credential_model") == "human_session":
            login_url = config.get("login_url", "")
            is_login_page = bool(login_url and (url == login_url or url.startswith(login_url)))
            if not is_login_page:
                if not session_path.exists() or not meta_path.exists():
                    print(f"[!] Session tidak ditemukan. Minta pengguna menjalankan: ui-capture login --project {project_id}", file=sys.stderr)
                    return EXIT_AUTH_REQUIRED
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    exp_dt = datetime.datetime.fromisoformat(meta["expires_at"])
                    now_dt = datetime.datetime.now(datetime.timezone.utc).astimezone()
                    if exp_dt <= now_dt:
                        print(f"[!] Session telah kedaluwarsa ({meta['expires_at']}). Minta pengguna login ulang.", file=sys.stderr)
                        return EXIT_AUTH_REQUIRED
                except Exception as e:
                    print(f"[!] Metadata sesi rusak: {e}", file=sys.stderr)
                    return EXIT_AUTH_REQUIRED

    # Determine backend to execute
    backends = detect_all_backends()
    selected_backend = None

    if backend_choice == "playwright-python" and backends["playwright-python"]["available"]:
        selected_backend = PlaywrightPythonBackend()
    elif backend_choice == "playwright-node" and backends["playwright-node"]["available"]:
        # Fall back to python or manual if node backend
        pass
    elif backend_choice == "manual":
        selected_backend = ManualBackend()
    elif backend_choice == "auto":
        if backends["playwright-python"]["available"]:
            selected_backend = PlaywrightPythonBackend()
        else:
            selected_backend = ManualBackend()
    else:
        selected_backend = ManualBackend()

    # Mask selectors merge
    masks = list(config.get("mask_selectors", []))
    if args.mask:
        masks.extend(args.mask)
    # Deduplicate
    masks = list(dict.fromkeys(masks))

    viewport = args.viewport or config.get("default_viewport", "1440x900")

    expect_texts = []
    if getattr(args, "expect_text", None):
        if isinstance(args.expect_text, list):
            expect_texts = args.expect_text
        elif isinstance(args.expect_text, str):
            expect_texts = [t.strip() for t in args.expect_text.split(",") if t.strip()]

    expect_selector = getattr(args, "expect_selector", None)
    allow_error_page = getattr(args, "allow_error_page", False)
    section = getattr(args, "section", None)
    section_text = getattr(args, "section_text", None)
    section_mode = getattr(args, "section_mode", "highlight")
    expect_section_text = getattr(args, "expect_section_text", None)
    click_text = getattr(args, "click_text", None)
    click_selector = getattr(args, "click_selector", None)

    exit_code, log_or_err = selected_backend.shot(
        config=config,
        session_path=session_path,
        tc=tc,
        name=name,
        url=url,
        wait_for=args.wait_for,
        full_page=args.full_page,
        mask=masks,
        viewport=viewport,
        output_path=output_path,
        expect_text=expect_texts,
        expect_selector=expect_selector,
        allow_error_page=allow_error_page,
        section=section,
        section_text=section_text,
        section_mode=section_mode,
        expect_section_text=expect_section_text,
        click_text=click_text,
        click_selector=click_selector
    )

    if args.json:
        print(json.dumps({"exit_code": exit_code, "data": log_or_err}, indent=2))
    return exit_code

# ----------------------------------------------------------------------
# Subcommand: STATUS
# ----------------------------------------------------------------------
def cmd_status(args: argparse.Namespace) -> int:
    project_id = args.project
    config = load_config(project_id)
    _, secrets_dir, _ = get_project_paths(project_id)
    session_file = secrets_dir / "ui-auth-state.json"
    meta_file = secrets_dir / "ui-auth-meta.json"

    backends = detect_all_backends()
    active_b = "playwright-python" if backends["playwright-python"]["available"] else "manual"

    session_info = {"exists": False, "valid": False}
    if session_file.exists() and meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            exp_str = meta.get("expires_at")
            exp_dt = datetime.datetime.fromisoformat(exp_str)
            now_dt = datetime.datetime.now(datetime.timezone.utc).astimezone()
            is_valid = exp_dt > now_dt
            ttl_remaining_mins = max(0, int((exp_dt - now_dt).total_seconds() / 60))
            session_info = {
                "exists": True,
                "valid": is_valid,
                "created_at": meta.get("created_at"),
                "expires_at": exp_str,
                "ttl_remaining_minutes": ttl_remaining_mins,
                "credential_model": meta.get("credential_model")
            }
        except Exception as e:
            session_info["error"] = str(e)

    result = {
        "status": "ok",
        "exit_code": EXIT_OK,
        "project_id": project_id,
        "active_backend": active_b,
        "backends": backends,
        "session": session_info
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Project       : {project_id}")
        print(f"Active Backend: {active_b}")
        print(f"Session Valid : {session_info['valid']}")
        if session_info.get("ttl_remaining_minutes") is not None:
            print(f"TTL Sisa      : {session_info['ttl_remaining_minutes']} menit")
    return EXIT_OK

# ----------------------------------------------------------------------
# Subcommand: LOGOUT
# ----------------------------------------------------------------------
def cmd_logout(args: argparse.Namespace) -> int:
    project_id = args.project
    _, secrets_dir, _ = get_project_paths(project_id)
    session_file = secrets_dir / "ui-auth-state.json"
    session_storage_file = secrets_dir / "ui-session-storage.json"
    meta_file = secrets_dir / "ui-auth-meta.json"

    removed = False
    if session_file.exists():
        session_file.unlink()
        removed = True
    if session_storage_file.exists():
        session_storage_file.unlink()
        removed = True
    if meta_file.exists():
        meta_file.unlink()
        removed = True

    res = {
        "status": "logged_out",
        "exit_code": EXIT_OK,
        "project_id": project_id,
        "session_removed": removed
    }
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"[✓] Sesi login untuk project '{project_id}' telah dibersihkan.")
    return EXIT_OK

# ----------------------------------------------------------------------
# CLI Argument Parser
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ui-capture",
        description="UI Evidence Capture Orchestrator CLI (Python stdlib only)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # doctor
    p_doc = subparsers.add_parser("doctor", help="Periksa status kapabilitas dan backend")
    p_doc.add_argument("--project", default="default", help="Nama project")
    p_doc.add_argument("--json", action="store_true", help="Output format JSON")

    # setup
    p_setup = subparsers.add_parser("setup", help="Pasang backend ke tool dir terisolasi")
    p_setup.add_argument("--backend", choices=["playwright-python", "playwright-node"], required=True)
    p_setup.add_argument("--yes", action="store_true", help="Setujui eksekusi instalasi")
    p_setup.add_argument("--json", action="store_true", help="Output format JSON")

    # init
    p_init = subparsers.add_parser("init", help="Inisialisasi konfigurasi qa-ui.config.json")
    p_init.add_argument("--project", required=True, help="Nama project")
    p_init.add_argument("--origin", required=True, help="Origin URL yang diizinkan (misal https://example.com)")
    p_init.add_argument("--login-url", help="URL Login portal")
    p_init.add_argument("--json", action="store_true", help="Output format JSON")

    # login
    p_login = subparsers.add_parser("login", help="Buka browser headed untuk login sesi manusia")
    p_login.add_argument("--project", required=True, help="Nama project")
    p_login.add_argument("--json", action="store_true", help="Output format JSON")

    # targets
    p_targets = subparsers.add_parser("targets", help="Validasi target URL dan anti-guessing gate")
    p_targets.add_argument("--project", required=True, help="Nama project")
    p_targets.add_argument("--targets-file", help="Path khusus ke file qa-targets.yaml")
    p_targets.add_argument("--target", help="Nama target spesifik yang ingin divalidasi")
    p_targets.add_argument("--json", action="store_true", help="Output format JSON")

    # shot
    p_shot = subparsers.add_parser("shot", help="Ambil screenshot UI read-only")
    p_shot.add_argument("--project", required=True, help="Nama project")
    p_shot.add_argument("--tc", required=True, help="Test Case id (contoh TC-15)")
    p_shot.add_argument("--name", required=True, help="Nama berkas screenshot (tanpa .png)")
    p_shot.add_argument("--url", help="URL target")
    p_shot.add_argument("--target-name", help="Nama target dari qa-targets.yaml (misal admin_web_portal)")
    p_shot.add_argument("--targets-file", help="Path khusus ke file qa-targets.yaml")
    p_shot.add_argument("--expect-text", help="Teks yang diharapkan muncul pada halaman (Layer 1)")
    p_shot.add_argument("--expect-selector", help="CSS selector yang wajib ada pada halaman")
    p_shot.add_argument("--allow-error-page", action="store_true", help="Izinkan screenshot halaman error")
    p_shot.add_argument("--section", help="CSS selector elemen/bagian spesifik untuk difokuskan")
    p_shot.add_argument("--section-text", help="Teks judul/label bagian untuk pencarian semantik cerdas (Smart Section Finder)")
    p_shot.add_argument("--section-mode", choices=["crop", "highlight"], default="highlight", help="Mode capture: crop (hanya bagian itu) atau highlight (bingkai merah)")
    p_shot.add_argument("--expect-section-text", help="Teks yang wajib ada di dalam bagian yang ditargetkan")
    p_shot.add_argument("--click-text", help="Teks elemen untuk di-klik sebelum screenshot")
    p_shot.add_argument("--click-selector", help="CSS selector elemen untuk di-klik sebelum screenshot")
    p_shot.add_argument("--wait-for", help="CSS selector yang ditunggu sebelum screenshot")
    p_shot.add_argument("--full-page", action="store_true", help="Tangkapan layar penuh")
    p_shot.add_argument("--mask", action="append", default=[], help="CSS selector untuk di-masking")
    p_shot.add_argument("--viewport", help="Resolusi layar (contoh 1440x900)")
    p_shot.add_argument("--backend", choices=["playwright-python", "playwright-node", "manual", "auto"], default="auto")
    p_shot.add_argument("--json", action="store_true", help="Output format JSON")

    # status
    p_stat = subparsers.add_parser("status", help="Tampilkan status backend dan umur sesi")
    p_stat.add_argument("--project", required=True, help="Nama project")
    p_stat.add_argument("--json", action="store_true", help="Output format JSON")

    # logout
    p_logout = subparsers.add_parser("logout", help="Hapus berkas sesi login")
    p_logout.add_argument("--project", required=True, help="Nama project")
    p_logout.add_argument("--json", action="store_true", help="Output format JSON")

    args = parser.parse_args()

    handlers = {
        "doctor": cmd_doctor,
        "setup": cmd_setup,
        "init": cmd_init,
        "login": cmd_login,
        "targets": cmd_targets,
        "shot": cmd_shot,
        "status": cmd_status,
        "logout": cmd_logout,
    }

    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(EXIT_INVALID_ARGS)

if __name__ == "__main__":
    main()
