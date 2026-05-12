#!/usr/bin/env python3
"""Unit tests for latent_variable_builder.py (P3 discovery phase)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import latent_variable_builder as lvb
from latent_variable_builder import (
    assemble_prompt,
    check_p3_extra_quality_gate,
    read_expert_profile,
    resolve_expertise_type,
    sort_candidates,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MINIMAL_TEMPLATE = (
    "Expert: {name} ({expertise_type})\n"
    "Profile:\n{expert_profile_json}"
)

_SAMPLE_PROFILE = {
    "identity": {"name": "张三", "title": "架构师", "domain": "分布式系统", "years_in_field": 10},
    "visible_knowledge": [{"rule": "先查连接池", "source": "doc1"}],
    "known_decisions": [{"case": "DB选型", "context": "高并发", "decision": "PostgreSQL", "source": "doc1"}],
    "domain_context": {"key_challenges": ["CAP"], "common_pitfalls": ["sharding"], "methodology_clashes": ["sync vs async"]},
    "suspected_gaps": [{"gap": "容灾等级判断", "reason": "同类架构师通常讨论容灾但此专家未提"}],
}


def _make_variable(
    id="lv_001",
    label="风险容忍",
    source_type="comparison_gap",
    testability="high",
    priority=8,
) -> dict:
    return {
        "id": id,
        "label": label,
        "source_type": source_type,
        "evidence_from_profile": "known_decisions[0] vs known_decisions[1]",
        "hypothesized_variable": {
            "name": "risk_tolerance",
            "description": "隐性风险边界",
            "why_latent": "专家从未命名该阈值",
        },
        "testability": testability,
        "priority": priority,
    }


def _make_valid_pool(count=6, high_medium_count=4, include_silent_topic=True) -> list[dict]:
    """Return a pool that passes all quality gates."""
    pool = []
    for i in range(count):
        t = "high" if i < high_medium_count else "low"
        st = "silent_topic" if (include_silent_topic and i == 0) else "comparison_gap"
        pool.append(_make_variable(
            id=f"lv_{i+1:03d}",
            label=f"变量{i+1}",
            source_type=st,
            testability=t,
            priority=max(1, 8 - i),
        ))
    return pool


def _write_profile(tmp_path: Path, profile: dict = _SAMPLE_PROFILE) -> Path:
    disc = tmp_path / "skills" / "expert" / "zhang-san" / "discovery"
    disc.mkdir(parents=True)
    p = disc / "expert_profile.json"
    p.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    return tmp_path / "skills" / "expert"


def _patch_template(path: Path) -> None:
    path.write_text(_MINIMAL_TEMPLATE, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1: prompt assembly — no leftover {placeholders}
# ---------------------------------------------------------------------------

class TestPromptAssemblyNoLeftover(unittest.TestCase):
    def test_prompt_assembly_no_leftover_placeholders(self):
        import re
        result = assemble_prompt(
            template=_MINIMAL_TEMPLATE,
            name="张三",
            expertise_type="architect",
            expert_profile_json='{"identity": {"name": "张三"}}',
        )
        leftover = re.findall(r'\{[a-z_]+\}', result)
        self.assertEqual(leftover, [], f"Leftover: {leftover}")


# ---------------------------------------------------------------------------
# Test 2: tool reads expert_profile.json and embeds content
# ---------------------------------------------------------------------------

class TestPromptReadsExpertProfileJson(unittest.TestCase):
    def setUp(self):
        self._orig = lvb.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        lvb.PROMPT_TEMPLATE_PATH = self._orig

    def test_prompt_reads_expert_profile_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_profile(tmp_path)

            tpl = tmp_path / "tpl.md"
            _patch_template(tpl)
            lvb.PROMPT_TEMPLATE_PATH = tpl

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir)])
            self.assertEqual(rc, 0)

            prompt_file = base_dir / "zhang-san" / "discovery" / "latent_variable_prompt.md"
            self.assertTrue(prompt_file.exists())
            content = prompt_file.read_text(encoding="utf-8")
            self.assertIn("张三", content)
            self.assertIn("分布式系统", content)


# ---------------------------------------------------------------------------
# Test 3: parse_output saves latent_variables.json on valid pool
# ---------------------------------------------------------------------------

class TestParseOutputSavesJson(unittest.TestCase):
    def setUp(self):
        self._orig = lvb.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        lvb.PROMPT_TEMPLATE_PATH = self._orig

    def test_parse_output_saves_latent_variables_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_profile(tmp_path)

            tpl = tmp_path / "tpl.md"
            _patch_template(tpl)
            lvb.PROMPT_TEMPLATE_PATH = tpl

            pool = _make_valid_pool()
            out = tmp_path / "ai_out.json"
            out.write_text(json.dumps({"latent_variables": pool}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertEqual(rc, 0)

            saved_path = base_dir / "zhang-san" / "discovery" / "latent_variables.json"
            self.assertTrue(saved_path.exists())
            saved = json.loads(saved_path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved), len(pool))


# ---------------------------------------------------------------------------
# Test 4: gate fail — count < 5
# ---------------------------------------------------------------------------

class TestParseOutputNoSaveOnGateFailCount(unittest.TestCase):
    def setUp(self):
        self._orig = lvb.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        lvb.PROMPT_TEMPLATE_PATH = self._orig

    def test_parse_output_no_save_on_gate_fail_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_profile(tmp_path)

            tpl = tmp_path / "tpl.md"
            _patch_template(tpl)
            lvb.PROMPT_TEMPLATE_PATH = tpl

            pool = _make_valid_pool(count=3, high_medium_count=3)
            out = tmp_path / "ai_out.json"
            out.write_text(json.dumps({"latent_variables": pool}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertNotEqual(rc, 0)
            saved_path = base_dir / "zhang-san" / "discovery" / "latent_variables.json"
            self.assertFalse(saved_path.exists())


# ---------------------------------------------------------------------------
# Test 5: gate fail — insufficient high/medium testability
# ---------------------------------------------------------------------------

class TestParseOutputNoSaveOnGateFailTestability(unittest.TestCase):
    def setUp(self):
        self._orig = lvb.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        lvb.PROMPT_TEMPLATE_PATH = self._orig

    def test_parse_output_no_save_on_gate_fail_testability(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_profile(tmp_path)

            tpl = tmp_path / "tpl.md"
            _patch_template(tpl)
            lvb.PROMPT_TEMPLATE_PATH = tpl

            # 6 candidates but only 2 high/medium
            pool = _make_valid_pool(count=6, high_medium_count=2)
            out = tmp_path / "ai_out.json"
            out.write_text(json.dumps({"latent_variables": pool}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertNotEqual(rc, 0)
            saved_path = base_dir / "zhang-san" / "discovery" / "latent_variables.json"
            self.assertFalse(saved_path.exists())


# ---------------------------------------------------------------------------
# Test 6: saved candidates sorted by priority descending
# ---------------------------------------------------------------------------

class TestCandidatesSortedByPriority(unittest.TestCase):
    def test_candidates_sorted_by_priority(self):
        pool = [
            _make_variable("lv_001", priority=3, testability="low"),
            _make_variable("lv_002", priority=9, testability="high"),
            _make_variable("lv_003", priority=6, testability="medium"),
        ]
        sorted_pool = sort_candidates(pool)
        priorities = [v["priority"] for v in sorted_pool]
        self.assertEqual(priorities, sorted(priorities, reverse=True))
        self.assertEqual(sorted_pool[0]["id"], "lv_002")

    def test_same_priority_testability_breaks_tie(self):
        pool = [
            _make_variable("lv_001", priority=5, testability="low"),
            _make_variable("lv_002", priority=5, testability="high"),
            _make_variable("lv_003", priority=5, testability="medium"),
        ]
        sorted_pool = sort_candidates(pool)
        self.assertEqual(sorted_pool[0]["id"], "lv_002")   # high first
        self.assertEqual(sorted_pool[1]["id"], "lv_003")   # medium second
        self.assertEqual(sorted_pool[2]["id"], "lv_001")   # low last


# ---------------------------------------------------------------------------
# Test 7: low testability candidates are preserved
# ---------------------------------------------------------------------------

class TestLowTestabilityCandidatesPreserved(unittest.TestCase):
    def setUp(self):
        self._orig = lvb.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        lvb.PROMPT_TEMPLATE_PATH = self._orig

    def test_low_testability_candidates_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_profile(tmp_path)

            tpl = tmp_path / "tpl.md"
            _patch_template(tpl)
            lvb.PROMPT_TEMPLATE_PATH = tpl

            pool = _make_valid_pool(count=7, high_medium_count=4)
            low_ids = [v["id"] for v in pool if v["testability"] == "low"]
            self.assertTrue(len(low_ids) > 0)

            out = tmp_path / "ai_out.json"
            out.write_text(json.dumps({"latent_variables": pool}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertEqual(rc, 0)

            saved = json.loads((base_dir / "zhang-san" / "discovery" / "latent_variables.json").read_text(encoding="utf-8"))
            saved_ids = [v["id"] for v in saved]
            for lid in low_ids:
                self.assertIn(lid, saved_ids, f"Low testability candidate {lid} was dropped")


# ---------------------------------------------------------------------------
# Test 8: schema validation rejects missing why_latent
# ---------------------------------------------------------------------------

class TestSchemaValidationRejectsMissingWhyLatent(unittest.TestCase):
    def setUp(self):
        self._orig = lvb.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        lvb.PROMPT_TEMPLATE_PATH = self._orig

    def test_schema_validation_rejects_missing_why_latent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_profile(tmp_path)

            tpl = tmp_path / "tpl.md"
            _patch_template(tpl)
            lvb.PROMPT_TEMPLATE_PATH = tpl

            pool = _make_valid_pool()
            # Remove why_latent from first candidate
            pool[0]["hypothesized_variable"].pop("why_latent")

            out = tmp_path / "ai_out.json"
            out.write_text(json.dumps({"latent_variables": pool}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertNotEqual(rc, 0)
            saved_path = base_dir / "zhang-san" / "discovery" / "latent_variables.json"
            self.assertFalse(saved_path.exists())


# ---------------------------------------------------------------------------
# Test 9: dry_run conflicts with parse_output
# ---------------------------------------------------------------------------

class TestDryRunConflictsWithParseOutput(unittest.TestCase):
    def test_dry_run_conflicts_with_parse_output(self):
        rc = main(["--slug", "test", "--dry-run", "--parse-output", "some.json"])
        self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# Test 10: dry_run does not write files
# ---------------------------------------------------------------------------

class TestDryRunDoesNotWriteFiles(unittest.TestCase):
    def setUp(self):
        self._orig = lvb.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        lvb.PROMPT_TEMPLATE_PATH = self._orig

    def test_dry_run_does_not_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_profile(tmp_path)

            tpl = tmp_path / "tpl.md"
            _patch_template(tpl)
            lvb.PROMPT_TEMPLATE_PATH = tpl

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--dry-run"])
            self.assertEqual(rc, 0)

            prompt_file = base_dir / "zhang-san" / "discovery" / "latent_variable_prompt.md"
            self.assertFalse(prompt_file.exists(), "dry-run must not write the prompt file")


# ---------------------------------------------------------------------------
# Test 11: parse_output updates meta status and count
# ---------------------------------------------------------------------------

class TestParseOutputUpdatesMetaStatus(unittest.TestCase):
    def setUp(self):
        self._orig = lvb.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        lvb.PROMPT_TEMPLATE_PATH = self._orig

    def test_parse_output_updates_meta_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_profile(tmp_path)

            tpl = tmp_path / "tpl.md"
            _patch_template(tpl)
            lvb.PROMPT_TEMPLATE_PATH = tpl

            # Pre-create meta.json
            meta_path = base_dir / "zhang-san" / "meta.json"
            meta_path.write_text(
                json.dumps({"slug": "zhang-san", "discovery": {"enabled": True, "status": "profile_ready"}}),
                encoding="utf-8",
            )

            pool = _make_valid_pool(count=6, high_medium_count=4)
            out = tmp_path / "ai_out.json"
            out.write_text(json.dumps({"latent_variables": pool}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertEqual(rc, 0)

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(meta["discovery"]["status"], "variables_ready")
            self.assertEqual(meta["discovery"]["latent_variable_count"], len(pool))


# ---------------------------------------------------------------------------
# Test 12: top-level list in AI output accepted
# ---------------------------------------------------------------------------

class TestParseOutputTopLevelListAccepted(unittest.TestCase):
    def setUp(self):
        self._orig = lvb.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        lvb.PROMPT_TEMPLATE_PATH = self._orig

    def test_parse_output_top_level_list_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_profile(tmp_path)

            tpl = tmp_path / "tpl.md"
            _patch_template(tpl)
            lvb.PROMPT_TEMPLATE_PATH = tpl

            pool = _make_valid_pool()
            out = tmp_path / "ai_out.json"
            # Top-level list (no wrapping key)
            out.write_text(json.dumps(pool), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertEqual(rc, 0)
            saved_path = base_dir / "zhang-san" / "discovery" / "latent_variables.json"
            self.assertTrue(saved_path.exists())


# ---------------------------------------------------------------------------
# Test 13: quality gate requires silent_topic
# ---------------------------------------------------------------------------

class TestQualityGateRequiresSilentTopic(unittest.TestCase):
    def test_quality_gate_requires_silent_topic(self):
        # Pool with no silent_topic candidate
        pool = _make_valid_pool(include_silent_topic=False)
        errors = check_p3_extra_quality_gate(pool)
        self.assertTrue(any("silent_topic" in e for e in errors))

    def test_quality_gate_passes_with_silent_topic(self):
        pool = _make_valid_pool(include_silent_topic=True)
        errors = check_p3_extra_quality_gate(pool)
        silent_topic_errors = [e for e in errors if "silent_topic" in e]
        self.assertEqual(silent_topic_errors, [])


# ---------------------------------------------------------------------------
# Test 14: priority must be integer 1-10
# ---------------------------------------------------------------------------

class TestPriorityMustBeInteger1To10(unittest.TestCase):
    def _pool_with_priority(self, priority) -> list[dict]:
        pool = _make_valid_pool()
        pool[0]["priority"] = priority
        return pool

    def test_priority_zero_rejected(self):
        errors = check_p3_extra_quality_gate(self._pool_with_priority(0))
        self.assertTrue(any("priority" in e for e in errors))

    def test_priority_eleven_rejected(self):
        errors = check_p3_extra_quality_gate(self._pool_with_priority(11))
        self.assertTrue(any("priority" in e for e in errors))

    def test_priority_float_rejected(self):
        errors = check_p3_extra_quality_gate(self._pool_with_priority(1.5))
        self.assertTrue(any("priority" in e for e in errors))

    def test_priority_one_accepted(self):
        pool = _make_valid_pool()
        for v in pool:
            v["priority"] = 1
        errors = check_p3_extra_quality_gate(pool)
        priority_errors = [e for e in errors if "priority" in e]
        self.assertEqual(priority_errors, [])

    def test_priority_ten_accepted(self):
        pool = _make_valid_pool()
        for v in pool:
            v["priority"] = 10
        errors = check_p3_extra_quality_gate(pool)
        priority_errors = [e for e in errors if "priority" in e]
        self.assertEqual(priority_errors, [])

    def test_validate_latent_variable_does_not_check_priority_range(self):
        """Confirm priority range is NOT checked by validate_latent_variable (schema only)."""
        from discovery_schema import validate_latent_variable
        v = _make_variable(priority=0)
        schema_errors = validate_latent_variable(v)
        priority_range_errors = [e for e in schema_errors if "1-10" in e or "range" in e]
        self.assertEqual(priority_range_errors, [], "validate_latent_variable must not enforce priority range")


# ---------------------------------------------------------------------------
# Test 15: expertise_type fallback from meta.json
# ---------------------------------------------------------------------------

class TestExpertiseTypeFallbackFromMeta(unittest.TestCase):
    def setUp(self):
        self._orig = lvb.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        lvb.PROMPT_TEMPLATE_PATH = self._orig

    def test_expertise_type_fallback_from_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_profile(tmp_path)

            # Write meta.json with expertise_type
            meta_path = base_dir / "zhang-san" / "meta.json"
            meta_path.write_text(
                json.dumps({"slug": "zhang-san", "expertise_type": "reviewer"}),
                encoding="utf-8",
            )

            tpl = tmp_path / "tpl.md"
            _patch_template(tpl)
            lvb.PROMPT_TEMPLATE_PATH = tpl

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir)])
            self.assertEqual(rc, 0)

            prompt_file = base_dir / "zhang-san" / "discovery" / "latent_variable_prompt.md"
            content = prompt_file.read_text(encoding="utf-8")
            self.assertIn("reviewer", content)

    def test_resolve_expertise_type_cli_overrides_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            meta_dir = tmp_path / "skills" / "expert" / "test-slug"
            meta_dir.mkdir(parents=True)
            (meta_dir / "meta.json").write_text(
                json.dumps({"expertise_type": "operator"}), encoding="utf-8"
            )
            base_dir = str(tmp_path / "skills" / "expert")
            result = resolve_expertise_type("architect", base_dir, "test-slug")
            self.assertEqual(result, "architect")


# ---------------------------------------------------------------------------
# Test 16: expertise_type defaults to troubleshooter with warning
# ---------------------------------------------------------------------------

class TestExpertiseTypeDefaultWarning(unittest.TestCase):
    def setUp(self):
        self._orig = lvb.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        lvb.PROMPT_TEMPLATE_PATH = self._orig

    def test_expertise_type_default_warning(self):
        import io
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_profile(tmp_path)
            # Ensure no meta.json exists
            meta_path = base_dir / "zhang-san" / "meta.json"
            if meta_path.exists():
                meta_path.unlink()

            tpl = tmp_path / "tpl.md"
            _patch_template(tpl)
            lvb.PROMPT_TEMPLATE_PATH = tpl

            stderr_capture = io.StringIO()
            import contextlib
            with contextlib.redirect_stderr(stderr_capture):
                rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir)])

            self.assertEqual(rc, 0)
            warning_output = stderr_capture.getvalue()
            self.assertIn("troubleshooter", warning_output)

            prompt_file = base_dir / "zhang-san" / "discovery" / "latent_variable_prompt.md"
            content = prompt_file.read_text(encoding="utf-8")
            self.assertIn("troubleshooter", content)

    def test_resolve_expertise_type_no_meta_returns_troubleshooter(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = resolve_expertise_type("", str(Path(tmp)), "nonexistent-slug")
            self.assertEqual(result, "troubleshooter")


if __name__ == "__main__":
    unittest.main()
