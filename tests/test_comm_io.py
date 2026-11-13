"""
test_comm_io.py - Test Suite for Communication & I/O Standardization (Phase 1)
Tests safe_atomic_write, O_EXCL safe_append, sanitize_command, and compact_message_bus.
"""

import os
import sys
import time
import json
import tempfile
import unittest
import threading
from pathlib import Path
from datetime import datetime, timedelta

# Ensure cmd/ is on sys.path
CMD_DIR = Path(__file__).resolve().parent.parent / "cmd"
if str(CMD_DIR) not in sys.path:
    sys.path.insert(0, str(CMD_DIR))

from comm_io import (
    safe_atomic_write,
    safe_append,
    sanitize_command,
    sanitize_text,
    compact_message_bus,
    format_bus_event,
    SCHEMA_VERSION
)


class TestSafeAtomicWrite(unittest.TestCase):
    """Test safe_atomic_write functionality and zero partial reads."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.test_dir.name)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_atomic_write_new_file(self):
        target = self.dir_path / "subdir" / "test.txt"
        content = "Halo dari Safe Atomic Write!\nBaris kedua."
        safe_atomic_write(target, content)

        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), content)

    def test_atomic_write_overwrite_existing(self):
        target = self.dir_path / "replace_me.json"
        initial_content = '{"version": 1}'
        safe_atomic_write(target, initial_content)
        self.assertEqual(target.read_text(encoding="utf-8"), initial_content)

        updated_content = '{"version": 2, "updated": true}'
        safe_atomic_write(target, updated_content)
        self.assertEqual(target.read_text(encoding="utf-8"), updated_content)

    def test_atomic_write_utf8_and_unicode(self):
        target = self.dir_path / "unicode.md"
        content = "# 🛡️ DevSecOps & Meta-Studio: ✅ 100% 🚀"
        safe_atomic_write(target, content)
        self.assertEqual(target.read_text(encoding="utf-8"), content)


class TestSafeAppend(unittest.TestCase):
    """Test safe_append with filesystem O_EXCL lockfile."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.test_dir.name)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_single_append(self):
        target = self.dir_path / "log.txt"
        safe_append(target, "Entry 1")
        safe_append(target, "Entry 2\n")

        lines = target.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, ["Entry 1", "Entry 2"])

    def test_concurrent_appends_multithreaded(self):
        """Stress test: 10 concurrent threads appending 20 entries each = 200 entries."""
        target = self.dir_path / "concurrent.log"
        num_threads = 10
        entries_per_thread = 20

        def worker(thread_idx: int):
            for i in range(entries_per_thread):
                safe_append(target, f"T{thread_idx}-E{i}")

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        lines = target.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), num_threads * entries_per_thread)
        # Check no corrupt lines
        for line in lines:
            self.assertTrue(line.startswith("T") and "-E" in line)

    def test_lock_timeout(self):
        target = self.dir_path / "timeout.log"
        lock_file = str(target) + ".lock"

        # Manually hold lock
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            with self.assertRaises(TimeoutError):
                safe_append(target, "should fail", timeout=0.1)
        finally:
            os.close(fd)
            os.unlink(lock_file)

    def test_stale_lock_recovery(self):
        target = self.dir_path / "stale.log"
        lock_file = str(target) + ".lock"

        # Create lockfile and artificially set mtime to 30 seconds ago
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        stale_time = time.time() - 30.0
        os.utime(lock_file, (stale_time, stale_time))

        # safe_append should recognize stale lock, break it, and succeed
        safe_append(target, "Entry after stale recovery", timeout=1.0, stale_threshold=5.0)
        self.assertEqual(target.read_text(encoding="utf-8").strip(), "Entry after stale recovery")


class TestSanitization(unittest.TestCase):
    """Test ANSI escape, null-byte, and control sequence sanitization."""

    def test_sanitize_ansi_colors_and_cursor(self):
        malicious = "echo \x1b[31;1mRED\x1b[0m; \x1b[2J\x1b[Hclear"
        cleaned = sanitize_command(malicious)
        self.assertEqual(cleaned, "echo RED; clear")

    def test_sanitize_null_byte_poisoning(self):
        malicious = "malicious_script.sh\x00.png"
        cleaned = sanitize_command(malicious)
        self.assertEqual(cleaned, "malicious_script.sh.png")

    def test_sanitize_c0_controls(self):
        malicious = "hello\x07\x08world\x0c"  # Bell, backspace, formfeed
        cleaned = sanitize_command(malicious)
        self.assertEqual(cleaned, "helloworld")

    def test_sanitize_text_preserves_legitimate_input(self):
        legit = "Line 1\nLine 2\twith indentation and quotes: \"hello\" & 'world'"
        cleaned = sanitize_text(legit)
        self.assertEqual(cleaned, legit)


class TestMessageBusCompactionAndVersioning(unittest.TestCase):
    """Test Message Bus compaction, retention rules, and schema versioning."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.test_dir.name)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_schema_version_in_format_bus_event(self):
        event = format_bus_event(
            project_id="test-proj",
            from_role="coder",
            to_role="analyst",
            event_type="TASK_PROGRESS",
            message="Implementasi siap \x1b[32mOK\x1b[0m",
            status="PENDING"
        )
        self.assertEqual(event["schema_version"], SCHEMA_VERSION)
        self.assertEqual(event["schema_version"], "1.1.0")
        self.assertEqual(event["status"], "PENDING")
        self.assertEqual(event["message"], "Implementasi siap OK")  # ANSI stripped

    def test_compaction_retention_rules(self):
        """
        Retention rules (Spec 2.4 / GAP-06):
        - PROCESSED > 7 days -> ELIMINATED
        - PROCESSED <= 7 days -> RETAINED
        - FAILED > 30 days -> ELIMINATED
        - FAILED <= 30 days -> RETAINED
        - PENDING -> ALWAYS RETAINED (NEVER DELETED)
        """
        bus_file = self.dir_path / "queue.jsonl"
        now = datetime.now()

        events = [
            # 1. PENDING, 10 days old -> MUST BE RETAINED
            {
                "event_id": "EVT-PENDING-OLD",
                "timestamp": (now - timedelta(days=10)).isoformat(),
                "status": "PENDING",
                "type": "TASK_HANDOFF",
                "message": "Belum diproses worker"
            },
            # 2. PROCESSED, 8 days old -> MUST BE ELIMINATED
            {
                "event_id": "EVT-PROCESSED-OLD",
                "timestamp": (now - timedelta(days=8)).isoformat(),
                "status": "PROCESSED",
                "type": "TASK_PROGRESS",
                "message": "Sudah selesai minggu lalu"
            },
            # 3. PROCESSED, 3 days old -> MUST BE RETAINED
            {
                "event_id": "EVT-PROCESSED-NEW",
                "timestamp": (now - timedelta(days=3)).isoformat(),
                "status": "PROCESSED",
                "type": "TASK_PROGRESS",
                "message": "Selesai kemarin"
            },
            # 4. FAILED, 35 days old -> MUST BE ELIMINATED
            {
                "event_id": "EVT-FAILED-OLD",
                "timestamp": (now - timedelta(days=35)).isoformat(),
                "status": "FAILED",
                "type": "FATAL_ERROR",
                "message": "Crash sebulan lalu"
            },
            # 5. FAILED, 15 days old -> MUST BE RETAINED (retention is 30 days)
            {
                "event_id": "EVT-FAILED-NEW",
                "timestamp": (now - timedelta(days=15)).isoformat(),
                "status": "FAILED",
                "type": "FATAL_ERROR",
                "message": "Crash 2 minggu lalu (audit investigasi)"
            },
        ]

        # Write initial events
        raw_text = "\n".join(json.dumps(e) for e in events) + "\n"
        bus_file.write_text(raw_text, encoding="utf-8")

        # Run compaction with force=True
        result = compact_message_bus(bus_file, force=True)
        self.assertEqual(result["status"], "compacted")
        self.assertEqual(result["original_count"], 5)
        self.assertEqual(result["removed_count"], 2)
        self.assertEqual(result["retained_count"], 3)

        # Verify which events survived
        remaining_lines = bus_file.read_text(encoding="utf-8").splitlines()
        remaining_ids = [json.loads(l)["event_id"] for l in remaining_lines]

        self.assertIn("EVT-PENDING-OLD", remaining_ids)
        self.assertIn("EVT-PROCESSED-NEW", remaining_ids)
        self.assertIn("EVT-FAILED-NEW", remaining_ids)
        self.assertNotIn("EVT-PROCESSED-OLD", remaining_ids)
        self.assertNotIn("EVT-FAILED-OLD", remaining_ids)

    def test_compaction_project_filter(self):
        bus_file = self.dir_path / "queue.jsonl"
        now = datetime.now()

        events = [
            # Event for project A (PROCESSED > 7 days -> eliminated if project_id="proj-a")
            {
                "event_id": "EVT-A-OLD",
                "project_id": "proj-a",
                "timestamp": (now - timedelta(days=9)).isoformat(),
                "status": "PROCESSED"
            },
            # Event for project B (PROCESSED > 7 days -> MUST BE KEPT because project_id="proj-a" was requested)
            {
                "event_id": "EVT-B-OLD",
                "project_id": "proj-b",
                "timestamp": (now - timedelta(days=9)).isoformat(),
                "status": "PROCESSED"
            }
        ]

        bus_file.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

        result = compact_message_bus(bus_file, force=True, project_id="proj-a")
        self.assertEqual(result["removed_count"], 1)
        self.assertEqual(result["retained_count"], 1)

        remaining_ids = [json.loads(l)["event_id"] for l in bus_file.read_text(encoding="utf-8").splitlines()]
        self.assertIn("EVT-B-OLD", remaining_ids)
        self.assertNotIn("EVT-A-OLD", remaining_ids)

    def test_compaction_size_threshold(self):
        bus_file = self.dir_path / "queue.jsonl"
        bus_file.write_text('{"event_id": "test"}\n', encoding="utf-8")

        # Size is tiny (< 5MB), force=False -> skipped
        result = compact_message_bus(bus_file, max_size_bytes=5 * 1024 * 1024, force=False)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "size_below_threshold")


if __name__ == "__main__":
    unittest.main()
