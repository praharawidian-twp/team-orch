"""
backends package for ui-evidence-capture.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from .base import (
    BaseUIBackend,
    detect_human_challenge,
    sanitize_url_for_log,
    calculate_sha256,
    validate_path_safety,
    DEFAULT_FORBIDDEN_ERROR_PATTERNS,
    validate_page_authenticity,
    validate_section_target,
    build_dom_telemetry,
    parse_simple_yaml,
    load_yaml_file,
)
from .manual import ManualBackend
from .playwright_python import PlaywrightPythonBackend

def get_backend_instances(tool_dir: Optional[Path] = None) -> Dict[str, BaseUIBackend]:
    return {
        "playwright-python": PlaywrightPythonBackend(),
        "manual": ManualBackend(),
    }

__all__ = [
    "BaseUIBackend",
    "ManualBackend",
    "PlaywrightPythonBackend",
    "get_backend_instances",
    "detect_human_challenge",
    "sanitize_url_for_log",
    "calculate_sha256",
    "validate_path_safety",
    "DEFAULT_FORBIDDEN_ERROR_PATTERNS",
    "validate_page_authenticity",
    "validate_section_target",
    "build_dom_telemetry",
    "parse_simple_yaml",
    "load_yaml_file",
]
