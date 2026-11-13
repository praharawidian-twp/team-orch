#!/usr/bin/env python3
"""
Self-Improvement Framework — Signal Collector & 0-Token Scanner
================================================================
Komponen: Pilar 1 — Observasi & Deteksi (Log Intelligence Layer)
Referensi: .agents/tasks/active/self-improvement/02-technical-spec.md §1.1

Skrip ini berjalan TANPA memanggil LLM apapun (0-token footprint).
Memindai audit-trail.md dan review-log.md untuk mendeteksi pola anomali
menggunakan regex dan counter deterministik.

Exit codes:
  0 = Tidak ada anomali yang melampaui threshold — tidak ada aksi diperlukan
  1 = Anomali terdeteksi — signals.json telah ditulis, siap untuk analisis LLM
  2 = Error konfigurasi atau file tidak ditemukan
  3 = Cooldown aktif — belum waktunya menjalankan self-improvement

Usage:
  python3 cmd/self-improve-scan.py --project <project_id>
  python3 cmd/self-improve-scan.py --project <project_id> --force
  python3 cmd/self-improve-scan.py --project <project_id> --dry-run
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Konstanta & Konfigurasi Default
# ---------------------------------------------------------------------------

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = WORKSPACE_ROOT / ".agents" / "config" / "self-improvement.yaml"
SIGNALS_PATH = WORKSPACE_ROOT / ".agents" / "tasks" / "active" / "self-improvement" / "signals.json"
LAST_RUN_PATH = WORKSPACE_ROOT / ".agents" / "tasks" / "active" / "self-improvement" / ".last-run"

# Normalized taxonomy untuk kategori anomali
CATEGORY_MAP = {
    "REJECTED":                     "review_rejection",
    "REVISION_REQUESTED":           "review_rejection",
    "NEEDS_REVISION":               "review_rejection",
    "CIRCUIT_BREAKER_TRIGGERED":    "circuit_breaker",
    "SECURITY_ALERT":               "security_alert",
    "BOILERPLATE_MISMATCH":         "boilerplate_deviation",
    "[BOILERPLATE_MISMATCH]":       "boilerplate_deviation",
    "CLEAN_CODE_VIOLATION":         "clean_code_violation",
    "[CLEAN_CODE_VIOLATION]":       "clean_code_violation",
    "MISSING_EDGE_CASE":            "missing_edge_case",
    "[MISSING_EDGE_CASE]":          "missing_edge_case",
    "ERROR":                        "generic_error",
    "PREFLIGHT_FAIL":               "preflight_violation",
}

# Routing recommendation berdasarkan kategori
ROUTING_MAP = {
    "review_rejection":     "knowledge_draft",
    "boilerplate_deviation":"knowledge_draft",
    "clean_code_violation": "knowledge_draft",
    "missing_edge_case":    "knowledge_draft",
    "circuit_breaker":      "role_prompt_patch",
    "security_alert":       "meta_studio_mcp",
    "preflight_violation":  "knowledge_draft",
    "generic_error":        "knowledge_draft",
}

# ---------------------------------------------------------------------------
# Config Loader (simple YAML tanpa dependency eksternal)
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load konfigurasi dari self-improvement.yaml dengan fallback ke defaults."""
    defaults = {
        "enabled": True,
        "cooldown_cycles": 3,
        "thresholds": {
            "rejections_per_task": 2,
            "repeated_pattern_count": 3,
            "preflight_fail_rate": 0.4,
            "bottleneck_stage_minutes": 60,
        },
    }
    if not CONFIG_PATH.exists():
        print(f"[WARN] Config tidak ditemukan di {CONFIG_PATH} — menggunakan defaults.", file=sys.stderr)
        return defaults

    try:
        # Parse YAML secara manual (hindari dependency PyYAML untuk portabilitas)
        config = dict(defaults)
        current_section = None
        with open(CONFIG_PATH, "r") as f:
            for line in f:
                line = line.rstrip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("thresholds:"):
                    current_section = "thresholds"
                    continue
                if current_section == "thresholds" and line.startswith("  "):
                    key, _, val = line.strip().partition(":")
                    val = val.strip().split("#")[0].strip()
                    try:
                        config["thresholds"][key] = float(val) if "." in val else int(val)
                    except ValueError:
                        pass
                elif ":" in line and not line.startswith(" "):
                    current_section = None
                    key, _, val = line.partition(":")
                    val = val.strip().split("#")[0].strip()
                    if val in ("true", "True"):
                        config[key] = True
                    elif val in ("false", "False"):
                        config[key] = False
                    elif val.isdigit():
                        config[key] = int(val)
        return config
    except Exception as e:
        print(f"[WARN] Gagal parse config: {e} — menggunakan defaults.", file=sys.stderr)
        return defaults


# ---------------------------------------------------------------------------
# Cooldown Check
# ---------------------------------------------------------------------------

def check_cooldown(config: dict, force: bool = False) -> tuple[bool, int]:
    """
    Periksa apakah cooldown masih aktif.
    Returns: (cooldown_active: bool, cycles_since_last_run: int)
    """
    if force:
        return False, 999

    cooldown_cycles = config.get("cooldown_cycles", 3)
    if not LAST_RUN_PATH.exists():
        return False, 999

    try:
        with open(LAST_RUN_PATH, "r") as f:
            data = json.load(f)
        projects_completed_since = data.get("projects_completed_since", 0)
        if projects_completed_since < cooldown_cycles:
            return True, projects_completed_since
        return False, projects_completed_since
    except Exception:
        return False, 999


# ---------------------------------------------------------------------------
# Log Scanner Functions
# ---------------------------------------------------------------------------

def scan_audit_trail(project_id: str) -> dict:
    """
    Pindai audit-trail.md untuk mendeteksi event anomali.
    Returns: dict berisi counter per kategori anomali.
    """
    audit_path = (
        WORKSPACE_ROOT
        / ".agents" / "tasks" / "active" / project_id / "audit-trail.md"
    )

    results = {
        "found": False,
        "total_rejections": 0,
        "circuit_breaker_invoked": False,
        "security_alerts": 0,
        "preflight_violations": 0,
        "review_cycles": 0,
        "patterns": Counter(),
        "raw_snippets": [],
    }

    if not audit_path.exists():
        print(f"[SCAN] audit-trail.md tidak ditemukan: {audit_path}", file=sys.stderr)
        return results

    results["found"] = True
    content = audit_path.read_text(encoding="utf-8", errors="replace")

    # Hitung event REJECTED / REVISION_REQUESTED
    rejection_pattern = re.compile(
        r"\b(REJECTED|REVISION_REQUESTED|NEEDS_REVISION)\b", re.IGNORECASE
    )
    rejections = rejection_pattern.findall(content)
    results["total_rejections"] = len(rejections)

    # Deteksi circuit breaker
    if re.search(r"CIRCUIT_BREAKER_TRIGGERED", content, re.IGNORECASE):
        results["circuit_breaker_invoked"] = True

    # Deteksi security alerts
    security_hits = re.findall(r"SECURITY_ALERT", content, re.IGNORECASE)
    results["security_alerts"] = len(security_hits)

    # Hitung preflight violations
    preflight_hits = re.findall(r"PREFLIGHT_FAIL|preflight.*fail", content, re.IGNORECASE)
    results["preflight_violations"] = len(preflight_hits)

    # Hitung review cycles (baris yang mengandung stage review)
    review_cycles = re.findall(r"review|code.?review", content, re.IGNORECASE)
    results["review_cycles"] = len(review_cycles)

    # Extract snippets (konteks terbatas 200 karakter per match)
    for match in rejection_pattern.finditer(content):
        start = max(0, match.start() - 40)
        end = min(len(content), match.end() + 80)
        snippet = content[start:end].replace("\n", " ").strip()[:200]
        results["raw_snippets"].append(snippet)
        results["patterns"][CATEGORY_MAP.get(match.group().upper(), "review_rejection")] += 1

    return results


def scan_review_log(project_id: str) -> dict:
    """
    Pindai review-log.md untuk mengidentifikasi kategori penolakan spesifik.
    Returns: dict berisi detail pola penolakan per kategori.
    """
    review_path = (
        WORKSPACE_ROOT
        / ".agents" / "tasks" / "active" / project_id / "review-log.md"
    )

    results = {
        "found": False,
        "failing_role": "unknown",
        "primary_failure_code": "UNKNOWN",
        "category_counts": Counter(),
        "anomaly_signatures": [],
    }

    if not review_path.exists():
        print(f"[SCAN] review-log.md tidak ditemukan: {review_path}", file=sys.stderr)
        return results

    results["found"] = True
    content = review_path.read_text(encoding="utf-8", errors="replace")

    # Deteksi kategori penolakan terformat
    category_pattern = re.compile(
        r"\[(BOILERPLATE_MISMATCH|CLEAN_CODE_VIOLATION|MISSING_EDGE_CASE|"
        r"SECURITY_VIOLATION|ARCH_DEVIATION|MISSING_TEST)\]",
        re.IGNORECASE,
    )
    for match in category_pattern.finditer(content):
        cat_key = match.group(1).upper()
        normalized = CATEGORY_MAP.get(cat_key, cat_key.lower())
        results["category_counts"][normalized] += 1

        # Ambil snippet konteks
        start = max(0, match.start() - 30)
        end = min(len(content), match.end() + 120)
        snippet = content[start:end].replace("\n", " ").strip()[:200]

        # Cek apakah signature ini sudah ada
        existing = next(
            (s for s in results["anomaly_signatures"] if s["category"] == normalized),
            None,
        )
        if existing:
            existing["count"] += 1
        else:
            results["anomaly_signatures"].append(
                {
                    "signature_id": f"SIG_{normalized.upper()}_{len(results['anomaly_signatures']):02d}",
                    "category": normalized,
                    "count": 1,
                    "context_snippet": snippet,
                    "recommended_route": ROUTING_MAP.get(normalized, "knowledge_draft"),
                }
            )

    # Deteksi peran yang paling sering gagal
    role_pattern = re.compile(
        r"(?:Role|Peran|role)\s*[:=]\s*(coder|analis|pm|devops|dokumenter|meta-architect)",
        re.IGNORECASE,
    )
    role_hits = role_pattern.findall(content)
    if role_hits:
        role_counter = Counter(r.lower() for r in role_hits)
        results["failing_role"] = role_counter.most_common(1)[0][0]

    # Primary failure code = kategori dengan count terbanyak
    if results["category_counts"]:
        top_cat = results["category_counts"].most_common(1)[0][0]
        results["primary_failure_code"] = f"ERR_{top_cat.upper()}"

    return results


# ---------------------------------------------------------------------------
# Anomaly Score & Threshold Check
# ---------------------------------------------------------------------------

def compute_anomaly_score(audit: dict, review: dict, config: dict) -> float:
    """
    Hitung anomaly score komposit berdasarkan hasil scan.
    Score > 1.0 = threshold terlampaui → LLM perlu dipanggil.
    """
    thresholds = config.get("thresholds", {})
    score = 0.0

    # Komponen 1: Rejection rate
    rejection_threshold = thresholds.get("rejections_per_task", 2)
    if audit["total_rejections"] >= rejection_threshold:
        score += audit["total_rejections"] / rejection_threshold

    # Komponen 2: Repeated pattern
    pattern_threshold = thresholds.get("repeated_pattern_count", 3)
    for cat, count in review["category_counts"].items():
        if count >= pattern_threshold:
            score += count / pattern_threshold

    # Komponen 3: Circuit breaker (hard trigger)
    if audit["circuit_breaker_invoked"]:
        score += 2.0

    # Komponen 4: Security alerts (hard trigger)
    if audit["security_alerts"] > 0:
        score += 2.0

    # Komponen 5: Preflight fail rate
    preflight_threshold = thresholds.get("preflight_fail_rate", 0.4)
    review_cycles = max(audit["review_cycles"], 1)
    if audit["preflight_violations"] / review_cycles >= preflight_threshold:
        score += 0.5

    return score


# ---------------------------------------------------------------------------
# signals.json Builder
# ---------------------------------------------------------------------------

def build_signals_json(project_id: str, audit: dict, review: dict, score: float) -> dict:
    """
    Bangun payload signals.json yang sesuai schema v1.0.0.
    Semua context_snippet dibatasi max 200 karakter.
    """
    # Gabungkan anomaly signatures dari review log
    all_signatures = list(review["anomaly_signatures"])

    # Tambahkan signature dari audit jika belum ada di review
    for cat, count in audit["patterns"].items():
        existing = next((s for s in all_signatures if s["category"] == cat), None)
        if not existing:
            snippet = ""
            if audit["raw_snippets"]:
                snippet = audit["raw_snippets"][0][:200]
            all_signatures.append(
                {
                    "signature_id": f"SIG_{cat.upper()}_{len(all_signatures):02d}",
                    "category": cat,
                    "count": count,
                    "context_snippet": snippet,
                    "recommended_route": ROUTING_MAP.get(cat, "knowledge_draft"),
                }
            )

    # Pastikan context_snippet <= 200 karakter
    for sig in all_signatures:
        sig["context_snippet"] = sig["context_snippet"][:200]

    primary_failure = review.get("primary_failure_code", "ERR_REVIEW_REJECTION")
    if audit["circuit_breaker_invoked"]:
        primary_failure = "ERR_CIRCUIT_BREAKER"
    if audit["security_alerts"] > 0:
        primary_failure = "ERR_SECURITY_ALERT"

    return {
        "version": "1.0.0",
        "project_id": project_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "anomaly_score": round(score, 3),
        "friction_summary": {
            "total_rejections": audit["total_rejections"],
            "primary_failure_code": primary_failure,
            "failing_role": review.get("failing_role", "unknown"),
            "stage": "implementation",
        },
        "anomaly_signatures": all_signatures,
        "metrics": {
            "review_cycles": audit["review_cycles"],
            "preflight_violations": audit["preflight_violations"],
            "security_alerts": audit["security_alerts"],
            "circuit_breaker_invoked": audit["circuit_breaker_invoked"],
        },
    }


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Self-Improvement Framework — 0-Token Signal Collector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--project", "-p",
        required=True,
        help="Project ID yang akan dipindai (folder di .agents/tasks/active/)",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Paksa scan meski cooldown masih aktif",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tampilkan hasil tanpa menulis signals.json",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Tampilkan detail scan",
    )
    args = parser.parse_args()

    print(f"[SCAN] Self-Improvement Signal Collector v1.0.0")
    print(f"[SCAN] Project: {args.project} | Workspace: {WORKSPACE_ROOT}")
    print(f"[SCAN] Mode: {'DRY-RUN' if args.dry_run else 'LIVE'} | Force: {args.force}")
    print()

    # 1. Load konfigurasi
    config = load_config()
    if not config.get("enabled", True):
        print("[SKIP] Self-Improvement Framework dinonaktifkan di konfigurasi.")
        return 0

    # 2. Cooldown check
    cooldown_active, cycles_done = check_cooldown(config, args.force)
    if cooldown_active:
        cooldown_required = config.get("cooldown_cycles", 3)
        print(
            f"[COOLDOWN] Aktif. Proyek selesai sejak last-run: {cycles_done}/{cooldown_required}. "
            f"Gunakan --force untuk override."
        )
        return 3

    # 3. Scan audit-trail.md
    print("[SCAN] Memindai audit-trail.md ...")
    audit_results = scan_audit_trail(args.project)
    if args.verbose:
        print(f"         Total rejections : {audit_results['total_rejections']}")
        print(f"         Preflight violations: {audit_results['preflight_violations']}")
        print(f"         Circuit breaker   : {audit_results['circuit_breaker_invoked']}")
        print(f"         Security alerts   : {audit_results['security_alerts']}")

    # 4. Scan review-log.md
    print("[SCAN] Memindai review-log.md ...")
    review_results = scan_review_log(args.project)
    if args.verbose and review_results["found"]:
        print(f"         Primary failure   : {review_results['primary_failure_code']}")
        print(f"         Failing role      : {review_results['failing_role']}")
        print(f"         Categories        : {dict(review_results['category_counts'])}")

    # 5. Compute anomaly score & fast-fail gate
    score = compute_anomaly_score(audit_results, review_results, config)
    print(f"[SCORE] Anomaly score: {score:.3f}")

    if score < 1.0:
        print("[PASS] ✓ Tidak ada anomali signifikan. Self-improvement tidak diperlukan saat ini.")
        print("        (Fast-fail: 0 LLM token dikonsumsi)")
        return 0

    # 6. Anomali terdeteksi — bangun signals.json
    print(f"[ALERT] ⚠ Anomali terdeteksi (score={score:.3f} ≥ 1.0) — membangun signals.json ...")
    signals = build_signals_json(args.project, audit_results, review_results, score)

    # Validasi ukuran (harus < 2KB)
    signals_json_str = json.dumps(signals, indent=2, ensure_ascii=False)
    if len(signals_json_str.encode("utf-8")) > 2048:
        # Potong anomaly_signatures jika terlalu besar
        while len(json.dumps(signals, indent=2, ensure_ascii=False).encode("utf-8")) > 2048:
            if signals["anomaly_signatures"]:
                signals["anomaly_signatures"].pop()
            else:
                break
        signals_json_str = json.dumps(signals, indent=2, ensure_ascii=False)

    if args.verbose:
        print("\n[SIGNALS] Payload:")
        print(signals_json_str)

    if not args.dry_run:
        SIGNALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SIGNALS_PATH.write_text(signals_json_str, encoding="utf-8")
        print(f"[WRITE] signals.json ditulis ke: {SIGNALS_PATH}")
        print(f"        Ukuran: {len(signals_json_str.encode('utf-8'))} bytes (batas: 2048 bytes)")
    else:
        print("[DRY-RUN] signals.json TIDAK ditulis (dry-run mode aktif).")

    print()
    print("[DONE] ✓ Signal Collector selesai. Exit 1 = LLM analysis diperlukan.")
    print("        Jalankan: team-orch self-improve analyze --project", args.project)
    return 1


if __name__ == "__main__":
    sys.exit(main())
