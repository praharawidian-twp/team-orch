#!/usr/bin/env python3
"""
playwright_python.py - Playwright Python Backend for UI Evidence Capture.
Supports both isolated tool venv (~/.gemini/tools/ui-capture/venv) and host python environment.
Safely imports and executes without breaking when playwright is not installed.
"""

import os
import sys
import json
import shutil
import datetime
import subprocess
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional
import urllib.parse

from .base import (
    BaseUIBackend,
    detect_human_challenge,
    sanitize_url_for_log,
    calculate_sha256,
    validate_page_authenticity,
    validate_section_target,
    build_dom_telemetry,
    DEFAULT_FORBIDDEN_ERROR_PATTERNS,
)

class PlaywrightPythonBackend(BaseUIBackend):
    name = "playwright-python"

    def _get_venv_python(self, tool_dir: Optional[Path] = None) -> Optional[Path]:
        if not tool_dir:
            tool_dir = Path.home() / ".gemini" / "tools" / "ui-capture"
        venv_py = tool_dir / "venv" / "bin" / "python3"
        if not venv_py.exists():
            venv_py = tool_dir / "venv" / "bin" / "python"
        if venv_py.exists() and os.access(venv_py, os.X_OK):
            return venv_py
        return None

    def _find_chromium_browser(self) -> Tuple[bool, str]:
        """Check if Playwright Chromium browser is installed."""
        cache_dirs = [
            Path.home() / "Library" / "Caches" / "ms-playwright",
            Path.home() / ".cache" / "ms-playwright",
            Path.home() / "AppData" / "Local" / "ms-playwright",
        ]
        for cdir in cache_dirs:
            if cdir.exists() and any(cdir.glob("chromium*")):
                return True, str(cdir)
        return False, "chromium_not_found"

    def detect(self, tool_dir: Optional[Path] = None) -> Tuple[bool, str, Dict[str, Any]]:
        # 1. Check isolated venv
        venv_py = self._get_venv_python(tool_dir)
        has_venv = False
        venv_ver = ""
        if venv_py:
            try:
                res = subprocess.run(
                    [str(venv_py), "-c", "import playwright; import importlib.metadata; print(importlib.metadata.version('playwright'))"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if res.returncode == 0:
                    has_venv = True
                    venv_ver = res.stdout.strip()
            except Exception:
                pass

        # 2. Check current/system python
        has_sys = False
        sys_ver = ""
        try:
            import playwright
            has_sys = True
            try:
                import importlib.metadata
                sys_ver = importlib.metadata.version("playwright")
            except Exception:
                sys_ver = "installed"
        except ImportError:
            pass
        except Exception:
            pass

        has_browser, browser_path = self._find_chromium_browser()

        is_available = (has_venv or has_sys) and has_browser
        chosen_py = str(venv_py) if has_venv else (sys.executable if has_sys else None)
        version_str = venv_ver if has_venv else sys_ver

        details = {
            "type": "playwright-python",
            "venv_available": has_venv,
            "venv_python": str(venv_py) if venv_py else None,
            "venv_version": venv_ver,
            "system_available": has_sys,
            "system_version": sys_ver,
            "active_python": chosen_py,
            "chromium_installed": has_browser,
            "chromium_location": browser_path,
        }

        status_str = f"playwright-python {version_str} (chromium ready)" if is_available else "not_installed"
        return is_available, status_str, details

    def login(
        self,
        config: Dict[str, Any],
        session_path: Path,
        meta_path: Path,
        headed: bool = True
    ) -> int:
        available, _, details = self.detect()
        if not available:
            print("[✗] Error: Playwright Python atau Chromium belum terpasang.")
            return 11

        python_bin = details.get("active_python") or sys.executable
        login_url = config.get("login_url", "")
        post_login_selector = config.get("post_login_selector", "")
        ttl_hours = config.get("session_ttl_hours", 8)

        if not login_url:
            print("[✗] Error: login_url tidak didefinisikan pada konfigurasi.")
            return 40

        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_storage_path = session_path.parent / "ui-session-storage.json"

        runner_script = f"""
import sys, os, time, json
from playwright.sync_api import sync_playwright

session_path = {repr(str(session_path))}
session_storage_path = {repr(str(session_storage_path))}
login_url = {repr(login_url)}
post_selector = {repr(post_login_selector)}

print("[*] Membuka browser Chromium untuk Human-Session Login...")
print(f"[*] Target URL: {{login_url}}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    page.goto(login_url)

    # 1. Tunggu form login selesai dimuat
    print("[*] Menunggu halaman login siap...")
    try:
        page.wait_for_selector('input[type="password"]', timeout=30000)
        print("[✓] Halaman login & input password terdeteksi.")
    except Exception:
        print("[*] Menunggu input user...")

    print("[*] Silakan lakukan login pada jendela browser yang terbuka.")
    print("[*] Deteksi otomatis aktif: menunggu URL meninggalkan #/login (timeout 300 detik)...")

    # 2. Polling loop untuk deteksi penyelesaian login
    start_time = time.time()
    logged_in = False
    while time.time() - start_time < 300:
        curr_url = page.url.lower()
        has_pwd = False
        try:
            has_pwd = page.locator('input[type="password"]').count() > 0
        except Exception:
            pass

        # Sukses login: URL meninggalkan #/login dan tidak ada input password lagi
        if ('#/login' not in curr_url) and (not has_pwd):
            logged_in = True
            print(f"[✓] Login berhasil terdeteksi! Rute aktif: {{page.url}}")
            break

        if post_selector:
            try:
                for sel in post_selector.split(','):
                    s = sel.strip()
                    if s and page.locator(s).count() > 0 and ('#/login' not in curr_url):
                        logged_in = True
                        print(f"[✓] Selector post-login ({{s}}) terdeteksi!")
                        break
                if logged_in:
                    break
            except Exception:
                pass

        page.wait_for_timeout(1000)

    if not logged_in:
        print("[!] Timeout 300 detik menunggu penyelesaian login.")
        browser.close()
        sys.exit(20)

    # 3. Tunggu 4 detik untuk finalisasi token sesi SPA & request XHR post-login
    print("[*] Menunggu 4 detik untuk finalisasi token sesi SPA aplikasi...")
    page.wait_for_timeout(4000)

    # 4. Simpan storage state (cookies & localStorage)
    context.storage_state(path=session_path)

    # 5. Simpan sessionStorage
    try:
        session_storage = page.evaluate("() => JSON.stringify(window.sessionStorage)")
        if session_storage and session_storage != "{{}}":
            with open(session_storage_path, "w", encoding="utf-8") as f:
                f.write(session_storage)
            print(f"[✓] SessionStorage SPA berhasil disimpan ke {{session_storage_path}}")
        else:
            print("[*] Catatan: window.sessionStorage kosong atau tidak digunakan.")
    except Exception as e:
        print(f"[!] Warning gagal mengekstrak sessionStorage: {{e}}")

    browser.close()
    print(f"[✓] Sesi login berhasil disimpan ke {{session_path}}")
    sys.exit(0)
"""

        try:
            proc = subprocess.run([python_bin, "-c", runner_script])
            if proc.returncode != 0:
                return proc.returncode

            # Apply strict 0600 permissions
            if session_path.exists():
                os.chmod(session_path, 0o600)
            if session_storage_path.exists():
                os.chmod(session_storage_path, 0o600)

            # Write auth metadata
            now = datetime.datetime.now(datetime.timezone.utc).astimezone()
            expires = now + datetime.timedelta(hours=ttl_hours)
            meta = {
                "created_at": now.isoformat(),
                "expires_at": expires.isoformat(),
                "ttl_hours": ttl_hours,
                "credential_model": config.get("credential_model", "human_session"),
                "login_url": login_url,
                "backend": "playwright-python"
            }
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            os.chmod(meta_path, 0o600)
            return 0
        except Exception as e:
            print(f"[✗] Login execution error: {e}")
            return 50

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
        click_text: Optional[str] = None,
        click_selector: Optional[str] = None
    ) -> Tuple[int, Dict[str, Any]]:
        available, _, details = self.detect()
        if not available:
            return 11, {"error": "NO_BACKEND", "message": "Playwright Python not installed"}

        python_bin = details.get("active_python") or sys.executable
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Parse viewport
        vw, vh = 1440, 900
        if "x" in viewport:
            parts = viewport.lower().split("x")
            try:
                vw, vh = int(parts[0]), int(parts[1])
            except ValueError:
                pass

        allowed_origins = config.get("allowed_origins", [])
        allow_mutation_paths = config.get("allow_mutation_paths", [])
        login_url = config.get("login_url", "")

        session_storage_data = ""
        session_storage_file = session_path.parent / "ui-session-storage.json" if session_path else None
        if session_storage_file and session_storage_file.exists():
            try:
                session_storage_data = session_storage_file.read_text(encoding="utf-8").strip()
            except Exception:
                session_storage_data = ""

        runner_payload = {
            "session_path": str(session_path) if session_path.exists() else None,
            "session_storage_data": session_storage_data,
            "url": url,
            "wait_for": wait_for,
            "expect_selector": expect_selector,
            "full_page": full_page,
            "mask": mask,
            "vw": vw,
            "vh": vh,
            "output_path": str(output_path),
            "allowed_origins": allowed_origins,
            "allow_mutation_paths": allow_mutation_paths,
            "login_url": login_url,
            "section": section,
            "section_text": section_text,
            "section_mode": section_mode or "highlight",
            "click_text": click_text,
            "click_selector": click_selector,
        }

        runner_script = f"""
import sys, os, json, urllib.parse, fnmatch
from playwright.sync_api import sync_playwright

payload = json.loads({repr(json.dumps(runner_payload))})

session_path = payload["session_path"]
session_storage_data = payload.get("session_storage_data")
target_url = payload["url"]
wait_for = payload["wait_for"]
expect_selector = payload.get("expect_selector")
full_page = payload["full_page"]
mask_selectors = payload["mask"]
vw = payload["vw"]
vh = payload["vh"]
output_path = payload["output_path"]
allowed_origins = payload["allowed_origins"]
allow_mutation_paths = payload["allow_mutation_paths"]
login_url = payload["login_url"]
section_selector = payload.get("section")
section_text_target = payload.get("section_text")
section_mode = payload.get("section_mode") or "highlight"
click_text = payload.get("click_text")
click_selector = payload.get("click_selector")

# Challenge indicators
CHALLENGE_KEYWORDS = [
    "recaptcha", "hcaptcha", "challenges.cloudflare.com", "cf-turnstile",
    "verify you are human", "checking your browser", "security check",
    "human verification", "bot detection", "two-factor authentication", "enter otp"
]

def check_html_challenge(html):
    if not html:
        return False
    lh = html.lower()
    return any(k in lh for k in CHALLENGE_KEYWORDS)

blocked_mutation_count = 0

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context_kwargs = {{
        "viewport": {{"width": vw, "height": vh}},
        "ignore_https_errors": True
    }}
    if session_path and os.path.exists(session_path):
        context_kwargs["storage_state"] = session_path

    context = browser.new_context(**context_kwargs)

    # Restore sessionStorage if available
    if session_storage_data:
        try:
            init_code = (
                "(() => {{\\n"
                "    try {{\\n"
                "        const obj = " + session_storage_data + ";\\n"
                "        for (const k in obj) {{\\n"
                "            window.sessionStorage.setItem(k, typeof obj[k] === '\''string'\'' ? obj[k] : JSON.stringify(obj[k]));\\n"
                "        }}\\n"
                "    }} catch (e) {{}}\\n"
                "}})();"
            )
            context.add_init_script(init_code)
        except Exception:
            pass

    page = context.new_page()

    def handle_route(route):
        global blocked_mutation_count
        req = route.request
        parsed = urllib.parse.urlsplit(req.url)
        origin = f"{{parsed.scheme}}://{{parsed.netloc}}"

        # Guard 1: Origin allowlist
        if allowed_origins and origin not in allowed_origins:
            route.abort()
            return

        # Guard 2: Read-only guard (abort mutation requests unless allowed)
        if req.method in ["POST", "PUT", "PATCH", "DELETE"]:
            is_allowed = False
            for pat in allow_mutation_paths:
                if pat == req.url or pat == parsed.path:
                    is_allowed = True
                    break
                if fnmatch.fnmatch(parsed.path, pat) or fnmatch.fnmatch(req.url, pat):
                    is_allowed = True
                    break
                if pat.endswith("/**") and parsed.path.startswith(pat[:-3]):
                    is_allowed = True
                    break
                if pat.endswith("/*") and parsed.path.startswith(pat[:-2]):
                    is_allowed = True
                    break

            if not is_allowed:
                blocked_mutation_count += 1
                route.abort()
                return

        route.continue_()

    page.route("**/*", handle_route)

    try:
        resp = page.goto(target_url, wait_until="networkidle", timeout=30000)
    except Exception as e:
        # Check if auth redirect or challenge occurred
        current_url = page.url
        if (login_url and current_url.startswith(login_url)) or ("#/login" in current_url.lower()):
            browser.close()
            print(json.dumps({{"exit_code": 20, "error": "AUTH_REQUIRED", "current_url": current_url}}))
            sys.exit(0)
        browser.close()
        print(json.dumps({{"exit_code": 50, "error": str(e)}}))
        sys.exit(0)

    # SPA hash-route settle check
    if "#/" in target_url or "#/" in page.url:
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(3000)

    current_url = page.url
    # Guard: Auth redirect check
    if resp and resp.status in [401, 403]:
        browser.close()
        print(json.dumps({{"exit_code": 20, "error": "AUTH_REQUIRED", "status": resp.status}}))
        sys.exit(0)

    if (login_url and current_url.startswith(login_url) and not target_url.startswith(login_url)) or ("#/login" in current_url.lower() and "#/login" not in target_url.lower()):
        browser.close()
        print(json.dumps({{"exit_code": 20, "error": "AUTH_REQUIRED", "current_url": current_url}}))
        sys.exit(0)

    # Guard: Challenge detector
    page_html = page.content()
    if check_html_challenge(page_html):
        browser.close()
        print(json.dumps({{"exit_code": 21, "error": "HUMAN_CHALLENGE"}}))
        sys.exit(0)

    if wait_for:
        try:
            page.wait_for_selector(wait_for, timeout=10000)
        except Exception:
            pass

    selector_found = True
    if expect_selector:
        try:
            page.wait_for_selector(expect_selector, timeout=10000)
            selector_found = True
        except Exception:
            selector_found = False

    # Click interaction if requested
    if click_selector:
        try:
            cloc = page.locator(click_selector)
            if cloc.count() > 0:
                cloc.first.scroll_into_view_if_needed()
                cloc.first.click()
                page.wait_for_timeout(2500)
        except Exception:
            pass
    elif click_text:
        try:
            found_click = False
            exact_loc = page.get_by_text(click_text, exact=True)
            for i in range(exact_loc.count()):
                el = exact_loc.nth(i)
                if el.is_visible():
                    el.scroll_into_view_if_needed()
                    el.click()
                    page.wait_for_timeout(2500)
                    found_click = True
                    break
            if not found_click:
                approx_loc = page.get_by_text(click_text, exact=False)
                for i in range(approx_loc.count()):
                    el = approx_loc.nth(i)
                    if el.is_visible():
                        el.scroll_into_view_if_needed()
                        el.click()
                        page.wait_for_timeout(2500)
                        break
        except Exception:
            pass

    # Section locator detection
    section_found = False
    is_visible = False
    bounding_box = None
    section_inner_text = ""
    target_query = section_selector or (("text:" + section_text_target) if section_text_target else None)
    target_locator = None

    if section_selector:
        try:
            loc = page.locator(section_selector)
            if loc.count() > 0:
                target_locator = loc.first
                section_found = True
        except Exception:
            pass
    elif section_text_target:
        try:
            finder_code = \"\"\"(targetText) => {{
                const lower = targetText.toLowerCase();
                const all = Array.from(document.querySelectorAll('*'));
                // 1. Prioritaskan EXACT text match dulu (pada leaf node atau heading)
                let el = all.find(e => (e.innerText || '').trim().toLowerCase() === lower && e.children.length === 0);
                if (!el) {{
                    el = all.find(e => (e.innerText || '').trim().toLowerCase() === lower);
                }}
                // 2. Fallback ke includes hanya jika exact tidak ditemukan
                if (!el) {{
                    el = all.find(e => {{
                        const t = (e.innerText || '').toLowerCase();
                        return t.includes(lower) && e.children.length === 0;
                    }}) || all.find(e => (e.innerText || '').toLowerCase().includes(lower));
                }}
                if (!el) return null;
                let curr = el;
                while (curr && curr !== document.body) {{
                    const tag = curr.tagName.toLowerCase();
                    const role = curr.getAttribute('role') || '';
                    const cls = typeof curr.className === 'string' ? curr.className.toLowerCase() : '';
                    const rect = curr.getBoundingClientRect();
                    if (['section', 'article', 'table', 'form'].includes(tag) ||
                        ['dialog', 'region'].includes(role) ||
                        cls.includes('card') || cls.includes('panel') ||
                        (tag === 'div' && rect.width > 100 && rect.height > 40)) {{
                        return curr;
                    }}
                    curr = curr.parentElement;
                }}
                return el;
            }}\"\"\"
            handle = page.evaluate_handle(finder_code, section_text_target)
            if handle:
                element = handle.as_element()
                if element:
                    target_locator = element
                    section_found = True
        except Exception:
            pass

    if target_locator:
        try:
            is_visible = target_locator.is_visible()
            if is_visible:
                bounding_box = target_locator.bounding_box()
                section_inner_text = target_locator.inner_text() or ""
        except Exception:
            pass

    # Apply masks
    mask_locators = []
    for sel in mask_selectors:
        try:
            mask_locators.append(page.locator(sel))
        except Exception:
            pass

    # Screenshot capture (crop vs highlight vs full)
    if (section_selector or section_text_target) and section_mode == "crop" and target_locator and is_visible:
        try:
            target_locator.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            target_locator.screenshot(path=output_path, mask=mask_locators)
        except Exception:
            page.screenshot(path=output_path, full_page=full_page, mask=mask_locators)
    else:
        if (section_selector or section_text_target) and section_mode == "highlight" and target_locator and is_visible:
            try:
                target_locator.scroll_into_view_if_needed()
                page.wait_for_timeout(300)
                target_locator.evaluate("el => {{ el.style.outline = '3px solid #ff1744 !important'; el.style.outlineOffset = '2px !important'; el.style.boxShadow = '0 0 12px rgba(255,23,68,0.45) !important'; }}")
            except Exception:
                pass
        page.screenshot(path=output_path, full_page=full_page, mask=mask_locators)

    page_title = page.title() or ""
    try:
        headings = page.evaluate("() => Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => (h.innerText || '').trim()).filter(Boolean)")
    except Exception:
        headings = []

    try:
        body_text = page.inner_text("body")
    except Exception:
        body_text = page.content() or ""

    try:
        interactive_counts = page.evaluate(\"\"\"() => ({{
            buttons: document.querySelectorAll('button, input[type=button], input[type=submit]').length,
            inputs: document.querySelectorAll('input:not([type=button]):not([type=submit]), textarea, select').length,
            tables: document.querySelectorAll('table').length,
            links: document.querySelectorAll('a[href]').length
        }})\"\"\")
    except Exception:
        interactive_counts = {{"buttons": 0, "inputs": 0, "tables": 0, "links": 0}}

    http_status = resp.status if resp else 0
    browser.close()

    print(json.dumps({{
        "exit_code": 0,
        "blocked_mutations": blocked_mutation_count,
        "http_status": http_status,
        "page_title": page_title,
        "headings": headings[:10],
        "body_text": body_text[:20000],
        "visible_text_excerpt": body_text[:300],
        "interactive_counts": interactive_counts,
        "selector_found": selector_found,
        "section_info": {{
            "requested": bool(section_selector or section_text_target),
            "target_query": target_query,
            "mode": section_mode,
            "found": section_found,
            "is_visible": is_visible,
            "bounding_box": bounding_box,
            "section_inner_text": section_inner_text
        }}
    }}))
    sys.exit(0)
"""

        try:
            proc = subprocess.run(
                [python_bin, "-c", runner_script],
                capture_output=True,
                text=True,
                timeout=90
            )

            if proc.returncode != 0:
                return 50, {"error": "BACKEND_ERROR", "details": proc.stderr}

            output_json = {}
            for line in proc.stdout.strip().splitlines():
                if line.startswith("{") and line.endswith("}"):
                    try:
                        output_json = json.loads(line)
                        break
                    except Exception:
                        pass

            exit_code = output_json.get("exit_code", 0)
            if exit_code != 0:
                return exit_code, output_json

            http_status = output_json.get("http_status", 0)
            page_title = output_json.get("page_title", "")
            body_text = output_json.get("body_text", "")
            selector_found = output_json.get("selector_found", True)

            # 1. Page Authenticity Validation
            is_authentic, auth_reason = validate_page_authenticity(
                http_status=http_status,
                body_text=body_text,
                page_title=page_title,
                expect_text=expect_text,
                allow_error_page=allow_error_page
            )

            if is_authentic and expect_selector and not selector_found:
                is_authentic = False
                auth_reason = f"Expected selector '{expect_selector}' not found on page"

            if not is_authentic:
                rejected_file_name = f"REJECTED-ERROR-PAGE-{name}.png"
                rejected_path = output_path.parent / rejected_file_name
                if output_path.exists():
                    if rejected_path.exists():
                        rejected_path.unlink()
                    output_path.rename(rejected_path)

                sha = calculate_sha256(rejected_path) if rejected_path.exists() else ""
                now_iso = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
                file_size_bytes = rejected_path.stat().st_size if rejected_path.exists() else 0

                dom_telemetry = build_dom_telemetry(
                    page_title=page_title,
                    visible_headings=output_json.get("headings", []),
                    visible_text_excerpt=output_json.get("visible_text_excerpt", ""),
                    interactive_counts=output_json.get("interactive_counts", {}),
                    file_size_bytes=file_size_bytes,
                    mode="full"
                )

                log_entry = {
                    "file": rejected_file_name,
                    "sha256": sha,
                    "url": sanitize_url_for_log(url),
                    "captured_at": now_iso,
                    "backend": "playwright-python",
                    "viewport": viewport,
                    "full_page": full_page,
                    "status": "REJECTED_ERROR_PAGE",
                    "http_status": http_status,
                    "rejection_reason": auth_reason,
                    "dom_telemetry": dom_telemetry,
                    "session_model": config.get("credential_model", "human_session"),
                    "operator": "qa-engineer"
                }

                # Update capture-log.json
                log_file = output_path.parent / "capture-log.json"
                existing_logs = []
                if log_file.exists():
                    try:
                        existing_logs = json.loads(log_file.read_text(encoding="utf-8"))
                        if not isinstance(existing_logs, list):
                            existing_logs = []
                    except Exception:
                        existing_logs = []

                existing_logs = [e for e in existing_logs if e.get("file") not in [f"{name}.png", rejected_file_name]]
                existing_logs.append(log_entry)
                log_file.write_text(json.dumps(existing_logs, indent=2), encoding="utf-8")

                return 4, log_entry

            # 2. Section Specific Validation (if requested)
            sec_info = output_json.get("section_info", {})
            sec_val = None
            if sec_info.get("requested"):
                sec_val = validate_section_target(
                    section_found=sec_info.get("found", False),
                    is_visible=sec_info.get("is_visible", False),
                    bounding_box=sec_info.get("bounding_box"),
                    section_inner_text=sec_info.get("section_inner_text", ""),
                    expect_section_text=expect_section_text
                )
                if not sec_val["is_valid"]:
                    status_tag = sec_val["status"]
                    rejected_file_name = f"REJECTED-SECTION-{status_tag}-{name}.png"
                    rejected_path = output_path.parent / rejected_file_name
                    if output_path.exists():
                        if rejected_path.exists():
                            rejected_path.unlink()
                        output_path.rename(rejected_path)

                    sha = calculate_sha256(rejected_path) if rejected_path.exists() else ""
                    now_iso = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
                    file_size_bytes = rejected_path.stat().st_size if rejected_path.exists() else 0

                    dom_telemetry = build_dom_telemetry(
                        page_title=page_title,
                        visible_headings=output_json.get("headings", []),
                        visible_text_excerpt=output_json.get("visible_text_excerpt", ""),
                        interactive_counts=output_json.get("interactive_counts", {}),
                        file_size_bytes=file_size_bytes,
                        mode=sec_info.get("mode", "highlight")
                    )

                    log_entry = {
                        "file": rejected_file_name,
                        "sha256": sha,
                        "url": sanitize_url_for_log(url),
                        "captured_at": now_iso,
                        "backend": "playwright-python",
                        "viewport": viewport,
                        "full_page": full_page,
                        "status": status_tag,
                        "http_status": http_status,
                        "rejection_reason": sec_val["reason"],
                        "dom_telemetry": dom_telemetry,
                        "section_validation": {
                            "target_query": sec_info.get("target_query"),
                            "mode": sec_info.get("mode"),
                            "status": status_tag,
                            "is_visible": sec_info.get("is_visible", False),
                            "bounding_box": sec_info.get("bounding_box"),
                            "extracted_section_text": sec_info.get("section_inner_text", "")[:300],
                            "expected_text_matched": False
                        },
                        "session_model": config.get("credential_model", "human_session"),
                        "operator": "qa-engineer"
                    }

                    # Update capture-log.json
                    log_file = output_path.parent / "capture-log.json"
                    existing_logs = []
                    if log_file.exists():
                        try:
                            existing_logs = json.loads(log_file.read_text(encoding="utf-8"))
                            if not isinstance(existing_logs, list):
                                existing_logs = []
                        except Exception:
                            existing_logs = []

                    existing_logs = [e for e in existing_logs if e.get("file") not in [f"{name}.png", rejected_file_name]]
                    existing_logs.append(log_entry)
                    log_file.write_text(json.dumps(existing_logs, indent=2), encoding="utf-8")

                    exit_code = 4 if status_tag == "REJECTED_ERROR_IN_SECTION" else 5
                    return exit_code, log_entry

            # 3. Successful Verification & DOM Telemetry
            sha = calculate_sha256(output_path) if output_path.exists() else ""
            now_iso = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
            file_size_bytes = output_path.stat().st_size if output_path.exists() else 0

            mode = sec_info.get("mode", "full") if sec_info.get("requested") else "full"
            dom_telemetry = build_dom_telemetry(
                page_title=page_title,
                visible_headings=output_json.get("headings", []),
                visible_text_excerpt=output_json.get("visible_text_excerpt", ""),
                interactive_counts=output_json.get("interactive_counts", {}),
                file_size_bytes=file_size_bytes,
                mode=mode
            )

            log_entry = {
                "file": f"{name}.png",
                "sha256": sha,
                "url": sanitize_url_for_log(url),
                "captured_at": now_iso,
                "backend": "playwright-python",
                "viewport": viewport,
                "full_page": full_page,
                "masked_selectors": mask,
                "blocked_mutation_requests": output_json.get("blocked_mutations", 0),
                "status": "verified",
                "http_status": http_status,
                "dom_telemetry": dom_telemetry,
                "session_model": config.get("credential_model", "human_session"),
                "operator": "qa-engineer"
            }

            if sec_info.get("requested"):
                log_entry["section_validation"] = {
                    "target_query": sec_info.get("target_query"),
                    "mode": sec_info.get("mode"),
                    "status": "SECTION_VERIFIED",
                    "is_visible": sec_info.get("is_visible", True),
                    "bounding_box": sec_info.get("bounding_box"),
                    "extracted_section_text": sec_info.get("section_inner_text", "")[:300],
                    "expected_text_matched": sec_val.get("expected_text_matched", False) if sec_val else True
                }

            # Update capture-log.json
            log_file = output_path.parent / "capture-log.json"
            existing_logs = []
            if log_file.exists():
                try:
                    existing_logs = json.loads(log_file.read_text(encoding="utf-8"))
                    if not isinstance(existing_logs, list):
                        existing_logs = []
                except Exception:
                    existing_logs = []

            # Remove previous rejected files for this name
            existing_logs = [e for e in existing_logs if not (e.get("file", "").startswith("REJECTED-") and name in e.get("file", "")) and e.get("file") != f"{name}.png"]
            existing_logs.append(log_entry)
            log_file.write_text(json.dumps(existing_logs, indent=2), encoding="utf-8")

            return 0, log_entry

        except subprocess.TimeoutExpired:
            return 50, {"error": "BACKEND_ERROR", "message": "Screenshot capture timed out after 60s"}
        except Exception as e:
            return 50, {"error": "BACKEND_ERROR", "message": str(e)}
