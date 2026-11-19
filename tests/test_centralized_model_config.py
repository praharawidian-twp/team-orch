#!/usr/bin/env python3
"""
test_centralized_model_config.py - Unit Test Suite for Centralized Dynamic Model Config (models.yaml).
Tests tier resolution, single-point updates propagating to all roles, runtime auto-sync generation ranking,
API-key (BYOK) model registration, and sequential worker transitions.
Zero external dependencies (pure Python standard library).
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
CMD_DIR = REPO_ROOT / "cmd"
if str(CMD_DIR) not in sys.path:
    sys.path.insert(0, str(CMD_DIR))

import comm_io

loader = SourceFileLoader("herdr_orch_central", str(CMD_DIR / "herdr-orch"))
spec = importlib.util.spec_from_loader(loader.name, loader)
herdr_orch = importlib.util.module_from_spec(spec)
loader.exec_module(herdr_orch)


class TestCentralizedModelConfig(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.models_yaml = self.temp_path / "models.yaml"
        self.state_file = self.temp_path / ".pane-state.json"

        # Seed temp config from repo's centralized models.yaml
        repo_models_yaml = REPO_ROOT / ".agents" / "config" / "models.yaml"
        self.models_yaml.write_text(repo_models_yaml.read_text(encoding="utf-8"), encoding="utf-8")

        self.prev_env_cfg = os.environ.get("TEAM_ORCH_MODELS_CONFIG")
        self.prev_env_state = os.environ.get("HERDR_PANE_STATE_FILE")
        self.prev_env_test = os.environ.get("HERDR_TEST_MODE")
        self.prev_env_pane = os.environ.get("HERDR_PANE_ID")

        os.environ["TEAM_ORCH_MODELS_CONFIG"] = str(self.models_yaml)
        os.environ["HERDR_PANE_STATE_FILE"] = str(self.state_file)
        os.environ["HERDR_TEST_MODE"] = "1"
        os.environ["HERDR_PANE_ID"] = "w1:p1"

    def tearDown(self):
        self.temp_dir.cleanup()
        for key, prev in [
            ("TEAM_ORCH_MODELS_CONFIG", self.prev_env_cfg),
            ("HERDR_PANE_STATE_FILE", self.prev_env_state),
            ("HERDR_TEST_MODE", self.prev_env_test),
            ("HERDR_PANE_ID", self.prev_env_pane),
        ]:
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev

    def test_01_role_resolves_model_from_central_config(self):
        tier_doc, model_doc = comm_io.resolve_role_tier_and_model("documenter", workspace_root=REPO_ROOT)
        tier_coder, model_coder = comm_io.resolve_role_tier_and_model("coder", workspace_root=REPO_ROOT)
        tier_analyst, model_analyst = comm_io.resolve_role_tier_and_model("analyst", workspace_root=REPO_ROOT)

        self.assertEqual(tier_doc, "low")
        self.assertEqual(model_doc, "gemini-4-hydrogen-low")
        self.assertEqual(tier_coder, "medium")
        self.assertEqual(model_coder, "gemini-4-neon-high")
        self.assertEqual(tier_analyst, "high")
        self.assertEqual(model_analyst, "gemini-4-argon-high")

    def test_02_dynamic_set_tier_updates_all_roles_instantly(self):
        res = comm_io.set_tier_model_in_config(
            tier="medium",
            primary_model="claude-sonnet-5-5-high",
            workspace_root=REPO_ROOT,
        )
        self.assertEqual(res.get("status"), "success")

        # Every medium-tier role + arbitrary custom medium role immediately resolves to the updated model
        for role_name in ("coder", "qa-engineer", "project-manager", "devops"):
            tier, resolved = comm_io.resolve_role_tier_and_model(role_name, workspace_root=REPO_ROOT)
            self.assertEqual(tier, "medium")
            self.assertEqual(resolved, "claude-sonnet-5-5-high")

        custom_tier, custom_resolved = comm_io.resolve_role_tier_and_model(
            "custom-role-99",
            role_data={"id": "custom-role-99", "model_tier": "medium"},
            workspace_root=REPO_ROOT,
        )
        self.assertEqual(custom_tier, "medium")
        self.assertEqual(custom_resolved, "claude-sonnet-5-5-high")

    def test_03_auto_sync_ranks_newer_generations_higher(self):
        simulated_agy_output = (
            "\r⠋ Fetching available models...\n"
            "gemini-3.8-flash-low            Gemini 3.8 Flash (Low)\n"
            "gemini-3.8-flash-high           Gemini 3.8 Flash (High)\n"
            "gemini-4-hydrogen-low           Gemini 4 Hydrogen (Low)\n"
            "gemini-4-hydrogen-high          Gemini 4 Hydrogen (High)\n"
            "gemini-4-argon-high             Gemini 4 Argon (High)\n"
            "gemini-5-hydrogen-low           Gemini 5 Hydrogen (Low)\n"
            "gemini-5-nebula-high            Gemini 5 Nebula (High)\n"
            "claude-sonnet-5-5-high          Claude Sonnet 5.5 (High)\n"
            "claude-opus-5-5-high            Claude Opus 5.5 (High)\n"
        )
        res = comm_io.sync_model_config_from_runtime(
            auto_assign=True,
            workspace_root=REPO_ROOT,
            raw_output=simulated_agy_output,
        )
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("discovered_count"), 9)
        self.assertEqual(res["tiers"]["low"]["primary"], "gemini-5-hydrogen-low")
        self.assertEqual(res["tiers"]["medium"]["primary"], "gemini-5-nebula-high")
        self.assertEqual(res["tiers"]["high"]["primary"], "gemini-5-nebula-high")

        # Also test with explicit frontier gen 5 (gemini-5-argon-high)
        simulated_with_argon5 = simulated_agy_output + "gemini-5-argon-high             Gemini 5 Argon (High)\n"
        res2 = comm_io.sync_model_config_from_runtime(
            auto_assign=True,
            workspace_root=REPO_ROOT,
            raw_output=simulated_with_argon5,
        )
        self.assertEqual(res2["tiers"]["high"]["primary"], "gemini-5-argon-high")

    def test_04_api_key_model_registration_and_resolution(self):
        add_res = comm_io.add_api_key_model_to_config(
            model_id="gpt-5-turbo-custom",
            tier="high",
            provider="openai",
            api_key_env="OPENAI_API_KEY",
            display_name="GPT-5 Turbo (BYOK)",
            base_url="https://api.openai.com/v1",
            set_primary=True,
            workspace_root=REPO_ROOT,
        )
        self.assertEqual(add_res.get("status"), "success")
        self.assertEqual(comm_io.resolve_model_for_tier("high", workspace_root=REPO_ROOT), "gpt-5-turbo-custom")

        spec_info = comm_io.get_model_runtime_spec("gpt-5-turbo-custom", workspace_root=REPO_ROOT)
        self.assertEqual(spec_info.get("source"), "api_key")
        self.assertEqual(spec_info.get("provider"), "openai")
        self.assertEqual(spec_info.get("api_key_env"), "OPENAI_API_KEY")

        # Remove restores tier primary away from removed model
        rm_res = comm_io.remove_api_key_model_from_config("gpt-5-turbo-custom", workspace_root=REPO_ROOT)
        self.assertEqual(rm_res.get("status"), "success")
        self.assertEqual(rm_res.get("removed_count"), 1)
        self.assertNotEqual(comm_io.resolve_model_for_tier("high", workspace_root=REPO_ROOT), "gpt-5-turbo-custom")

    @patch.object(herdr_orch, "run_herdr_cmd")
    def test_05_worker_pipeline_follows_central_config_across_role_transitions(self, mock_run):
        def fake_herdr(args, timeout=15):
            if args[:2] == ["agent", "get"]:
                return 0, "active", ""
            if args[:2] == ["pane", "read"]:
                return 0, "Clean terminal output", ""
            if args[:2] == ["agent", "read"]:
                return 0, "Stage completed", ""
            if args[:2] == ["agent", "prompt"]:
                return 0, "Prompt queued", ""
            return 0, "OK", ""

        mock_run.side_effect = fake_herdr

        # 1. Worker starts as coder (medium -> gemini-4-neon-high)
        res1 = herdr_orch.delegate_task(
            target_pane="w1:p2",
            task_prompt="Implement feature X",
            role="coder",
            reset_on_role_change=True,
        )
        self.assertEqual(res1.get("status"), "success")
        self.assertEqual(res1["lifecycle_actions"].get("resolved_model"), "gemini-4-neon-high")

        # 2. Next worker is analyst (high -> gemini-4-argon-high) -> /new + /model gemini-4-argon-high
        res2 = herdr_orch.delegate_task(
            target_pane="w1:p2",
            task_prompt="Review feature X",
            role="analyst",
            reset_on_role_change=True,
        )
        self.assertEqual(res2.get("status"), "success")
        self.assertTrue(res2["lifecycle_actions"].get("context_reset_new"))
        self.assertEqual(res2["lifecycle_actions"].get("model_switched_to"), "gemini-4-argon-high")

        # 3. Dynamically update low tier in centralized config, then dispatch next worker (documenter)
        comm_io.set_tier_model_in_config("low", "claude-sonnet-5-5-low", workspace_root=REPO_ROOT)
        res3 = herdr_orch.delegate_task(
            target_pane="w1:p2",
            task_prompt="Write docs for feature X",
            role="documenter",
            reset_on_role_change=True,
        )
        self.assertEqual(res3.get("status"), "success")
        self.assertTrue(res3["lifecycle_actions"].get("context_reset_new"))
        self.assertEqual(res3["lifecycle_actions"].get("model_switched_to"), "claude-sonnet-5-5-low")

        prompt_calls = [c[0][0] for c in mock_run.call_args_list if c[0]]
        self.assertTrue(any(c[:3] == ["agent", "prompt", "w1:p2"] and c[3] == "/model gemini-4-argon-high" for c in prompt_calls))
        self.assertTrue(any(c[:3] == ["agent", "prompt", "w1:p2"] and c[3] == "/model claude-sonnet-5-5-low" for c in prompt_calls))

    def test_06_neon_model_update_auto_upgrades_medium_tier(self):
        live_23_model_output = (
            "\r⠋ Fetching available models...\n"
            "gemini-4-neon-high              Gemini 4 Neon (High)\n"
            "gemini-4-neon-xhigh             Gemini 4 Neon (XHigh)\n"
            "gemini-4-neon-medium            Gemini 4 Neon (Medium)\n"
            "gemini-4-neon-low               Gemini 4 Neon (Low)\n"
            "gemini-4-argon-medium           Gemini 4 Argon (Medium)\n"
            "gemini-4-argon-high             Gemini 4 Argon (High)\n"
            "gemini-4-argon-low              Gemini 4 Argon (Low)\n"
            "gemini-4-hydrogen-high          Gemini 4 Hydrogen (High)\n"
            "gemini-4-hydrogen-xhigh         Gemini 4 Hydrogen (XHigh)\n"
            "gemini-4-hydrogen-medium        Gemini 4 Hydrogen (Medium)\n"
            "gemini-4-hydrogen-low           Gemini 4 Hydrogen (Low)\n"
            "gemini-pro-orchestrator-neon    Orchestrator (Neon)\n"
            "gemini-pro-orchestrator-g1-pro  Orchestrator (Argon)\n"
            "gemini-3.8-flash-high           Gemini 3.8 Flash (High)\n"
            "gemini-3.8-flash-medium         Gemini 3.8 Flash (Medium)\n"
            "gemini-3.8-flash-low            Gemini 3.8 Flash (Low)\n"
            "claude-opus-5-5-low             Claude Opus 5.5 (Low)\n"
            "claude-opus-5-5-medium          Claude Opus 5.5 (Medium)\n"
            "claude-opus-5-5-high            Claude Opus 5.5 (High)\n"
            "claude-sonnet-5-5-low           Claude Sonnet 5.5 (Low)\n"
            "claude-sonnet-5-5-medium        Claude Sonnet 5.5 (Medium)\n"
            "claude-sonnet-5-5-high          Claude Sonnet 5.5 (High)\n"
            "gpt-oss-120b-medium             GPT-OSS 120B (Medium)\n"
        )
        res = comm_io.sync_model_config_from_runtime(
            auto_assign=True,
            workspace_root=REPO_ROOT,
            raw_output=live_23_model_output,
        )
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("discovered_count"), 23)
        self.assertEqual(res["tiers"]["low"]["primary"], "gemini-4-hydrogen-low")
        self.assertEqual(res["tiers"]["medium"]["primary"], "gemini-4-neon-high")
        self.assertEqual(res["tiers"]["high"]["primary"], "gemini-4-argon-high")

        for role_name in ("coder", "qa-engineer", "project-manager", "devops"):
            tier, resolved = comm_io.resolve_role_tier_and_model(role_name, workspace_root=REPO_ROOT)
            self.assertEqual(tier, "medium")
            self.assertEqual(resolved, "gemini-4-neon-high")


if __name__ == "__main__":
    unittest.main()
