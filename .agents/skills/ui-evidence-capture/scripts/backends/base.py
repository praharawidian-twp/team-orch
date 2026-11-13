#!/usr/bin/env python3
"""
base.py - Base Interface and Utilities for UI Evidence Capture Backends.
Pure Python standard library.
"""

import os
import re
import hashlib
import urllib.parse
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional

# Challenge detection signatures (case-insensitive)
CHALLENGE_HTML_PATTERNS = [
    r"recaptcha",
    r"hcaptcha",
    r"challenges\.cloudflare\.com",
    r"cf-turnstile",
    r"verify\s+you\s+are\s+human",
    r"checking\s+your\s+browser",
    r"security\s+check",
    r"human\s+verification",
    r"bot\s+detection",
    r"enter\s+(?:the\s+)?otp",
    r"two-factor\s+authentication",
    r"mfa\s+verification",
]

# Standard forbidden error patterns indicating broken, unrouted, or 404 pages
DEFAULT_FORBIDDEN_ERROR_PATTERNS = [
    "Object Not Found",
    "404 Not Found",
    "502 Bad Gateway",
    "503 Service Unavailable",
    "Cannot GET ",
    "ERR_NAME_NOT_RESOLVED",
    "This site can’t be reached",
    "Internal Server Error"
]

def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Zero-dependency lightweight YAML parser for dictionaries and lists."""
    root = {}
    lines = text.splitlines()
    stack = [(-1, root, None)]

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.rstrip()
        i += 1
        if not line or line.strip().startswith('#'):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        # Check list item
        if stripped.startswith('- '):
            val = stripped[2:].strip().strip('\"\'')
            if ' #' in val:
                val = val.split(' #', 1)[0].strip().strip('\"\'')
            if val.lower() == 'true': val = True
            elif val.lower() == 'false': val = False
            elif val.lower() in ('null', '~'): val = None

            while stack and stack[-1][0] >= indent:
                stack.pop()

            parent = stack[-1][1]
            parent_key = stack[-1][2]
            if isinstance(parent, list):
                parent.append(val)
            elif parent_key and isinstance(parent.get(parent_key), list):
                parent[parent_key].append(val)
            continue

        if ':' in stripped:
            parts = stripped.split(':', 1)
            k = parts[0].strip()
            raw_v = parts[1].strip()
            if ' #' in raw_v:
                raw_v = raw_v.split(' #', 1)[0].strip()

            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1]

            if not raw_v:
                # Lookahead to see if next non-empty line starts with '- '
                next_is_list = False
                for j in range(i, len(lines)):
                    nxt = lines[j].strip()
                    if nxt and not nxt.startswith('#'):
                        if nxt.startswith('- '):
                            next_is_list = True
                        break

                if next_is_list:
                    new_val = []
                    parent[k] = new_val
                    stack.append((indent, parent, k))
                else:
                    new_val = {}
                    parent[k] = new_val
                    stack.append((indent, new_val, k))
            else:
                v = raw_v.strip('\"\'')
                if v == '[]': v = []
                elif v == '{}': v = {}
                elif v.lower() == 'true': v = True
                elif v.lower() == 'false': v = False
                elif v.lower() in ('null', '~'): v = None
                parent[k] = v

    return root

def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Safely load and parse YAML file using standard library."""
    if not path.exists():
        return {}
    try:
        return parse_simple_yaml(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def validate_page_authenticity(
    http_status: int,
    body_text: str,
    page_title: str = "",
    expect_text: Optional[List[str]] = None,
    forbidden_patterns: Optional[List[str]] = None,
    allow_error_page: bool = False
) -> Tuple[bool, str]:
    """
    Validate that the loaded page is an authentic application view,
    not a 404/500/Object Not Found error page or blank canvas.
    """
    if allow_error_page:
        return True, "Allowed by explicit --allow-error-page flag"

    if http_status >= 400:
        return False, f"HTTP Error Status {http_status}"

    combined_text = f"{page_title} {body_text}".lower()

    patterns = forbidden_patterns or DEFAULT_FORBIDDEN_ERROR_PATTERNS
    for pat in patterns:
        if pat.lower() in combined_text:
            return False, f"Forbidden error text detected: '{pat}'"

    clean_body = body_text.strip() if body_text else ""
    if len(clean_body) < 10 and not any(tag in (body_text or "").lower() for tag in ["<canvas", "<svg", "<img"]):
        return False, "Page content appears blank or unrendered (length < 10)"

    if expect_text:
        if isinstance(expect_text, str):
            expect_text = [expect_text]
        found_expected = any(t.lower() in combined_text for t in expect_text if t.strip())
        if not found_expected:
            return False, f"Expected text {expect_text} not found on page"

    return True, "Page content is authentic"

def validate_section_target(
    section_found: bool,
    is_visible: bool,
    bounding_box: Optional[Dict[str, Any]],
    section_inner_text: str,
    expect_section_text: Optional[Any] = None,
    forbidden_patterns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Validate targeted section existence, visibility, dimensions,
    and scoped text assertions.
    """
    if not section_found or not is_visible:
        return {
            "is_valid": False,
            "status": "REJECTED_SECTION_NOT_VISIBLE",
            "reason": "Target section was not found or is not visible in DOM"
        }

    if not bounding_box or bounding_box.get("width", 0) < 10 or bounding_box.get("height", 0) < 10:
        return {
            "is_valid": False,
            "status": "REJECTED_SECTION_ZERO_SIZE",
            "reason": f"Target section dimensions too small or 0px: {bounding_box}"
        }

    # Check for forbidden error patterns in section text
    patterns = forbidden_patterns or DEFAULT_FORBIDDEN_ERROR_PATTERNS
    lower_text = (section_inner_text or "").lower()
    for pat in patterns:
        if pat.lower() in lower_text:
            return {
                "is_valid": False,
                "status": "REJECTED_ERROR_IN_SECTION",
                "reason": f"Forbidden error text detected in section: '{pat}'"
            }

    # Check scoped expected text
    if expect_section_text:
        if isinstance(expect_section_text, str):
            keywords = [k.strip() for k in expect_section_text.split(",") if k.strip()]
        elif isinstance(expect_section_text, list):
            keywords = [str(k).strip() for k in expect_section_text if str(k).strip()]
        else:
            keywords = []

        for kw in keywords:
            if kw.lower() not in lower_text:
                return {
                    "is_valid": False,
                    "status": "REJECTED_SECTION_TEXT_MISMATCH",
                    "reason": f"Expected section text '{kw}' not found in targeted section"
                }

    return {
        "is_valid": True,
        "status": "SECTION_VERIFIED",
        "reason": "Section is visible, properly sized, and verified",
        "bounding_box": bounding_box,
        "expected_text_matched": bool(expect_section_text)
    }

def build_dom_telemetry(
    page_title: str,
    visible_headings: List[str],
    visible_text_excerpt: str,
    interactive_counts: Dict[str, int],
    file_size_bytes: int,
    mode: str = "full"
) -> Dict[str, Any]:
    """
    Construct rich DOM telemetry for Zero-Vision-Token verification.
    Detects if screenshot is suspicious blank, avoiding multimodal token usage.
    """
    clean_excerpt = (visible_text_excerpt or "").strip()
    total_interactive = sum(interactive_counts.values()) if interactive_counts else 0

    if mode == "crop":
        is_suspicious_blank = len(clean_excerpt) < 5 and total_interactive == 0
    else:
        is_suspicious_blank = (file_size_bytes > 0 and file_size_bytes < 15000) or (len(clean_excerpt) < 15 and total_interactive == 0)

    return {
        "page_title": page_title or "",
        "visible_headings": visible_headings or [],
        "visible_text_excerpt": clean_excerpt,
        "interactive_counts": interactive_counts or {},
        "file_size_bytes": file_size_bytes,
        "is_suspicious_blank": is_suspicious_blank,
        "vision_check_needed": is_suspicious_blank
    }

def detect_human_challenge(html_content: str) -> bool:
    """Detect if page HTML content contains bot challenges, CAPTCHAs, or MFA prompts."""
    if not html_content:
        return False
    lower_html = html_content.lower()
    for pattern in CHALLENGE_HTML_PATTERNS:
        if re.search(pattern, lower_html):
            return True
    return False

def sanitize_url_for_log(url: str) -> str:
    """
    Redact query string parameters from URLs for privacy and security.
    Example: https://host/path?token=secret -> https://host/path?<redacted>
    """
    if not url:
        return ""
    parsed = urllib.parse.urlsplit(url)
    redacted = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        redacted += "?<redacted>"
    if parsed.fragment:
        # If fragment contains query-like params, redact them too
        frag = parsed.fragment
        if "?" in frag:
            frag_base, _ = frag.split("?", 1)
            redacted += f"#{frag_base}?<redacted>"
        else:
            redacted += f"#{frag}"
    return redacted

def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def validate_path_safety(tc: str, name: str, evidence_root: Path) -> Tuple[bool, Optional[Path], str]:
    """
    Validates --tc format (^TC-[0-9]+$) and --name format (^[A-Za-z0-9._-]+$),
    and ensures target file is strictly confined within evidence_root.
    """
    if not tc or not re.match(r"^TC-[0-9]+$", tc):
        return False, None, f"Invalid TC identifier '{tc}'. Must match pattern '^TC-[0-9]+$' (e.g. TC-15)."

    if not name or not re.match(r"^[A-Za-z0-9._-]+$", name):
        return False, None, f"Invalid evidence name '{name}'. Must contain only alphanumeric, dot, underscore, or dash."

    try:
        resolved_root = evidence_root.resolve()
        target_dir = (evidence_root / tc).resolve()
        target_file = (target_dir / f"{name}.png").resolve()

        if not str(target_file).startswith(str(resolved_root)):
            return False, None, f"Path traversal violation: target '{target_file}' is outside evidence root '{resolved_root}'."

        return True, target_file, ""
    except Exception as e:
        return False, None, f"Path resolution error: {e}"

class BaseUIBackend(ABC):
    """Abstract base class for all UI screenshot capture backends."""

    name: str = "base"

    @abstractmethod
    def detect(self, tool_dir: Optional[Path] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if backend is installed and usable.
        Returns: (is_available, version_or_status, details_dict)
        Must be safe, read-only, and fast.
        """
        pass

    @abstractmethod
    def login(
        self,
        config: Dict[str, Any],
        session_path: Path,
        meta_path: Path,
        headed: bool = True
    ) -> int:
        """
        Interactive login to save session state.
        Returns exit code (0 for OK, 21 for challenge, 50 for backend error).
        """
        pass

    @abstractmethod
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
        expect_section_text: Optional[str] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Take a read-only screenshot adhering to all safety guards.
        Returns: (exit_code, log_entry_or_error_info)
        """
        pass
