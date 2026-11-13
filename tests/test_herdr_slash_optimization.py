#!/usr/bin/env python3
"""
test_herdr_slash_optimization.py - Unit Test Suite for herdr-orch v0.4.0 Slash Command Optimization.
Tests dynamic /model switching, clean-room /new on role change, proactive /compact, /btw, and team-orch integration.
Zero external dependencies (pure Python standard library).
"""

import sys
import os
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from importlib.machinery import SourceFileLoader
import importlib.util

REPO_ROOT = Path(__file__).resolve().parent.parent
HERDR_ORCH_PATH = REPO_ROOT / "cmd" / "herdr-orch"
TEAM_ORCH_PATH = REPO_ROOT / "cmd" / "team-orch"

# Load herdr-orch module dynamically
loader = SourceFileLoader("herdr_orch", str(HERDR_ORCH_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
herdr_orch = importlib.util.module_from_spec(spec)
loader.exec_module(herdr_orch)

class TestHerdrSlashOptimization(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / ".pane-state.json"
        os.environ["HERDR_PANE_STATE_FILE"] = str(self.state_file)
        os.environ["HERDR_TEST_MODE"] = "1"
        os.environ["HERDR_PANE_ID"] = "w1:p1"

    def tearDown(self):
        self.temp_dir.cleanup()
        os.environ.pop("HERDR_PANE_STATE_FILE", None)
        os.environ.pop("HERDR_TEST_MODE", None)

    # 1. Dynamic /model switch on existing agent pane
    @patch.object(herdr_orch, "run_herdr_cmd")
    def test_01_dynamic_model_switch_on_existing_agent(self, mock_run):
        # Initial state: pane has gemini-3.8-flash-high
        state = {
            "w1:p2": {
                "active_model": "gemini-3.8-flash-high",
                "active_role": "coder",
                "task_count_since_compact": 0
            }
        }
        self.state_file.write_text(json.dumps(state), encoding="utf-8")

        # Mock herdr commands
        def fake_herdr(args, timeout=15):
            if args[:2] == ["agent", "get"]:
                return 0, "active", ""
            if args[:2] == ["pane", "read"]:
                return 0, "Clean terminal output", ""
            if args[:2] == ["agent", "read"]:
                return 0, "Task completed successfully", ""
            if args[:2] == ["agent", "prompt"]:
                return 0, "Prompt queued", ""
            return 0, "OK", ""

        mock_run.side_effect = fake_herdr

        res = herdr_orch.delegate_task(
            target_pane="w1:p2",
            task_prompt="Implement complex algorithm",
            model="gemini-3.1-pro-high",
            role="coder"
        )

        self.assertEqual(res.get("status"), "success")
        lifecycle = res.get("lifecycle_actions", {})
        self.assertEqual(lifecycle.get("model_switched_to"), "gemini-3.1-pro-high")
        self.assertFalse(lifecycle.get("context_reset_new"))

        # Check prompt calls
        prompt_calls = [call_args[0][0] for call_args in mock_run.call_args_list if len(call_args[0]) > 0]
        # Should have sent /model gemini-3.1-pro-high
        has_model_switch = any(
            c[:3] == ["agent", "prompt", "w1:p2"] and c[3] == "/model gemini-3.1-pro-high"
            for c in prompt_calls
        )
        self.assertTrue(has_model_switch, f"Expected /model command not found in calls: {prompt_calls}")

        # Check persisted state
        updated_state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(updated_state["w1:p2"]["active_model"], "gemini-3.1-pro-high")

    # 2. Clean-room role switch triggers /new
    @patch.object(herdr_orch, "run_herdr_cmd")
    def test_02_clean_room_role_switch_triggers_new(self, mock_run):
        # Initial state: pane previously handled 'coder'
        state = {
            "w1:p2": {
                "active_model": "gemini-3.8-flash-high",
                "active_role": "coder",
                "task_count_since_compact": 2
            }
        }
        self.state_file.write_text(json.dumps(state), encoding="utf-8")

        def fake_herdr(args, timeout=15):
            if args[:2] == ["agent", "get"]:
                return 0, "active", ""
            if args[:2] == ["pane", "read"]:
                return 0, "Clean terminal output", ""
            if args[:2] == ["agent", "read"]:
                return 0, "QA report generated", ""
            return 0, "OK", ""

        mock_run.side_effect = fake_herdr

        # Dispatch next stage to qa-engineer with reset_on_role_change=True
        res = herdr_orch.delegate_task(
            target_pane="w1:p2",
            task_prompt="Audit QA matrix",
            role="qa-engineer",
            reset_on_role_change=True
        )

        self.assertEqual(res.get("status"), "success")
        lifecycle = res.get("lifecycle_actions", {})
        self.assertTrue(lifecycle.get("context_reset_new"))

        # Verify /new command was sent
        prompt_calls = [call_args[0][0] for call_args in mock_run.call_args_list if len(call_args[0]) > 0]
        has_new_cmd = any(
            c[:3] == ["agent", "prompt", "w1:p2"] and c[3] == "/new"
            for c in prompt_calls
        )
        self.assertTrue(has_new_cmd, f"/new command was not sent: {prompt_calls}")

        # Verify persisted state updated role and reset count to 1 (0 after reset + 1 for this task)
        updated_state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(updated_state["w1:p2"]["active_role"], "qa-engineer")
        self.assertEqual(updated_state["w1:p2"]["task_count_since_compact"], 1)

    # 3. Same role preserves context until threshold triggers /compact
    @patch.object(herdr_orch, "run_herdr_cmd")
    def test_03_same_role_preserves_context_until_threshold(self, mock_run):
        # Initial state: task count is already at 3 (threshold)
        state = {
            "w1:p2": {
                "active_model": "gemini-3.8-flash-high",
                "active_role": "coder",
                "task_count_since_compact": 3
            }
        }
        self.state_file.write_text(json.dumps(state), encoding="utf-8")

        def fake_herdr(args, timeout=15):
            if args[:2] == ["agent", "get"]:
                return 0, "active", ""
            if args[:2] == ["pane", "read"]:
                return 0, "Clean output", ""
            return 0, "OK", ""

        mock_run.side_effect = fake_herdr

        res = herdr_orch.delegate_task(
            target_pane="w1:p2",
            task_prompt="Implement next subtask",
            role="coder",
            reset_on_role_change=True,
            auto_compact_threshold=3
        )

        self.assertEqual(res.get("status"), "success")
        lifecycle = res.get("lifecycle_actions", {})
        # /new should NOT be sent because role is unchanged
        self.assertFalse(lifecycle.get("context_reset_new"))
        # /compact SHOULD be sent because task_count (3) >= threshold (3)
        self.assertTrue(lifecycle.get("context_compacted"))

        prompt_calls = [call_args[0][0] for call_args in mock_run.call_args_list if len(call_args[0]) > 0]
        has_compact = any(
            c[:3] == ["agent", "prompt", "w1:p2"] and c[3] == "/compact"
            for c in prompt_calls
        )
        self.assertTrue(has_compact, f"/compact command was not sent: {prompt_calls}")

        # After compaction, task_count was reset to 0, then incremented to 1
        updated_state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(updated_state["w1:p2"]["task_count_since_compact"], 1)

    # 4. btw subcommand allows sending to busy/working pane without blocking
    @patch.object(herdr_orch, "run_herdr_cmd")
    def test_04_btw_subcommand_allows_busy_pane(self, mock_run):
        def fake_herdr(args, timeout=15):
            if args[:2] == ["pane", "read"]:
                # Output showing pane is busy running tests
                return 0, "Running test suite... in progress", ""
            if args[:2] == ["agent", "get"]:
                return 0, "active", ""
            return 0, "OK", ""

        mock_run.side_effect = fake_herdr

        res = herdr_orch.send_btw_question("w1:p2", "How many tests passed so far?")
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("action"), "btw")

        prompt_calls = [call_args[0][0] for call_args in mock_run.call_args_list if len(call_args[0]) > 0]
        has_btw = any(
            c[:3] == ["agent", "prompt", "w1:p2"] and "/btw How many tests passed so far?" in c[3]
            for c in prompt_calls
        )
        self.assertTrue(has_btw, f"/btw command not sent: {prompt_calls}")

    # 5. Standalone compact, reset, and switch-model subcommands
    @patch.object(herdr_orch, "run_herdr_cmd")
    def test_05_standalone_compact_reset_switch_model(self, mock_run):
        mock_run.return_value = (0, "OK", "")

        # 1. Switch model
        res_sw = herdr_orch.switch_pane_model("w1:p3", "gemini-3.8-flash-low")
        self.assertEqual(res_sw.get("status"), "success")
        state1 = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state1["w1:p3"]["active_model"], "gemini-3.8-flash-low")

        # 2. Compact
        state1["w1:p3"]["task_count_since_compact"] = 5
        self.state_file.write_text(json.dumps(state1), encoding="utf-8")
        res_cpt = herdr_orch.compact_pane("w1:p3")
        self.assertEqual(res_cpt.get("status"), "success")
        state2 = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state2["w1:p3"]["task_count_since_compact"], 0)

        # 3. Reset
        state2["w1:p3"]["active_role"] = "documenter"
        self.state_file.write_text(json.dumps(state2), encoding="utf-8")
        res_rst = herdr_orch.reset_pane("w1:p3")
        self.assertEqual(res_rst.get("status"), "success")
        state3 = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertIsNone(state3["w1:p3"]["active_role"])
        self.assertEqual(state3["w1:p3"]["task_count_since_compact"], 0)

    # 6. Team-orch passes --role and --reset-on-role-change to herdr-orch delegate
    def test_06_team_orch_passes_role_and_reset_flag(self):
        team_orch_text = TEAM_ORCH_PATH.read_text(encoding="utf-8")
        self.assertIn('"--role", role', team_orch_text)
        self.assertIn('"--reset-on-role-change"', team_orch_text)
        self.assertIn('/diff', team_orch_text)
        self.assertIn('/btw', team_orch_text)
        self.assertIn('/learn', team_orch_text)

if __name__ == "__main__":
    unittest.main()
