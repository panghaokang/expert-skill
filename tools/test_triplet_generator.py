#!/usr/bin/env python3
"""Unit tests for triplet_generator.py (P4 discovery phase)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import triplet_generator as tg
from triplet_generator import (
    assemble_prompt,
    check_p4_extra_quality_gate,
    compute_ab_overlap,
    filter_target_variables,
    generate_interview_script,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MINIMAL_TEMPLATE = (
    "{name} ({expertise_type}, {domain})\n"
    "Targets: {target_variables_json}\n"
    "Profile: {expert_profile_json}\n"
    "Domain: {domain_context_json}\n"
    "Decisions: {known_decisions_json}"
)

_SAMPLE_PROFILE = {
    "identity": {"name": "张三", "title": "架构师", "domain": "分布式系统", "years_in_field": 10},
    "visible_knowledge": [{"rule": "先查连接池", "source": "doc1"}],
    "known_decisions": [
        {"case": "DB选型", "context": "高并发", "decision": "PostgreSQL", "source": "doc1"},
    ],
    "domain_context": {
        "key_challenges": ["CAP theorem"],
        "common_pitfalls": ["over-sharding"],
        "methodology_clashes": ["sync vs async"],
    },
    "suspected_gaps": [{"gap": "容灾等级判断", "reason": "架构师通常讨论容灾但此专家未提"}],
}

_SAMPLE_VARIABLES = [
    {
        "id": "lv_001", "label": "风险容忍阈值", "source_type": "comparison_gap",
        "evidence_from_profile": "evidence1",
        "hypothesized_variable": {"name": "risk", "description": "desc", "why_latent": "why"},
        "testability": "high", "priority": 8,
    },
    {
        "id": "lv_002", "label": "沉默话题变量", "source_type": "silent_topic",
        "evidence_from_profile": "evidence2",
        "hypothesized_variable": {"name": "silent", "description": "desc", "why_latent": "why"},
        "testability": "medium", "priority": 6,
    },
    {
        "id": "lv_003", "label": "低可测性变量", "source_type": "rule_boundary",
        "evidence_from_profile": "evidence3",
        "hypothesized_variable": {"name": "boundary", "description": "desc", "why_latent": "why"},
        "testability": "low", "priority": 4,
    },
]

_PROBES = {
    "primary": "您第一步会检查什么？",
    "followups": ["您如何判断是否需要立即处理？", "什么情况下您会升级？"],
    "signal_triggers": {
        "noticed": "您注意到什么不同了吗？",
        "hesitated": "您在权衡什么？",
        "boundary_invented": "这个边界是怎么形成的？",
        "contradiction": "这和刚才说的有些矛盾？",
        "pushback": "您觉得问题前提有问题？",
    },
}

_REVEALS = {
    "visible_rule": "先查连接池",
    "latent_variable": "风险容忍边界",
    "priority_signal": "是否触发介入阈值",
}

_QUALITY_NOTES = {
    "single_variable_control": "B 只改变系统规模",
    "unpredictability": "问题文本不提及目标变量名",
    "decision_difference": "A 倾向快速修复，B 转向保守验证",
}

_TEXT_A = "您负责的核心支付服务在凌晨出现间歇性超时（约5%请求），监控显示CPU和内存正常，数据库连接池使用率为60%。您会怎么处理？"
_TEXT_B = "您负责的核心支付服务在凌晨出现间歇性超时（约5%请求），监控显示CPU和内存正常，数据库连接池使用率为60%。但系统现在运行在100节点集群上。您会怎么处理？"
_TEXT_B_DIFFERENT = "一个零售库存系统正在经历每日批量结账导致的 OOM 事故，这与分布式事务有什么关联？"


def _make_group(
    id="tg_001",
    target_variable="lv_001",
    text_a=_TEXT_A,
    text_b=_TEXT_B,
    include_quality_notes=True,
    include_conflict_added=True,
    manual_override_reason: str = "",
) -> dict:
    g: dict = {
        "id": id,
        "target_variable": target_variable,
        "target_variable_label": "风险容忍阈值",
        "domain_context": "分布式系统场景",
        "control_notes": "B 只改变系统规模",
        "question_A": {"text": text_a, "probes": _PROBES, "expected_reveals": _REVEALS},
        "question_B": {
            "text": text_b, "variable_changed": "系统规模",
            "probes": _PROBES, "expected_reveals": _REVEALS,
        },
        "question_C": {
            "text": "同上，叠加SLA要求", "variable_changed": "沿用B",
            "probes": _PROBES, "expected_reveals": _REVEALS,
        },
    }
    if include_quality_notes:
        g["quality_notes"] = dict(_QUALITY_NOTES)
    if include_conflict_added:
        g["question_C"]["conflict_added"] = "叠加硬性SLA要求（99.99%可用性）"
    if manual_override_reason:
        g["manual_override_reason"] = manual_override_reason
    return g


def _write_inputs(tmp_path: Path, variables=None, profile=None) -> Path:
    base_dir = tmp_path / "skills" / "expert"
    disc = base_dir / "zhang-san" / "discovery"
    disc.mkdir(parents=True)
    (disc / "latent_variables.json").write_text(
        json.dumps(variables or _SAMPLE_VARIABLES, ensure_ascii=False), encoding="utf-8"
    )
    (disc / "expert_profile.json").write_text(
        json.dumps(profile or _SAMPLE_PROFILE, ensure_ascii=False), encoding="utf-8"
    )
    return base_dir


def _patch_template(tmp_path: Path) -> Path:
    tpl = tmp_path / "tpl.md"
    tpl.write_text(_MINIMAL_TEMPLATE, encoding="utf-8")
    return tpl


# ---------------------------------------------------------------------------
# Test 1: no leftover placeholders
# ---------------------------------------------------------------------------

class TestPromptAssemblyNoLeftover(unittest.TestCase):
    def test_prompt_assembly_no_leftover_placeholders(self):
        import re
        result = assemble_prompt(
            template=_MINIMAL_TEMPLATE,
            name="张三", expertise_type="architect", domain="分布式系统",
            target_variables_json="[]", expert_profile_json="{}",
            domain_context_json="{}", known_decisions_json="[]",
        )
        leftover = re.findall(r'\{[a-z_]+\}', result)
        self.assertEqual(leftover, [], f"Leftover: {leftover}")


# ---------------------------------------------------------------------------
# Test 2: only high/medium testability in target_variables
# ---------------------------------------------------------------------------

class TestFiltersHighMediumTestabilityOnly(unittest.TestCase):
    def test_filters_high_medium_testability_only(self):
        filtered = filter_target_variables(_SAMPLE_VARIABLES)
        ids = [v["id"] for v in filtered]
        self.assertIn("lv_001", ids)
        self.assertIn("lv_002", ids)
        self.assertNotIn("lv_003", ids)  # low testability excluded

    def setUp(self):
        self._orig = tg.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        tg.PROMPT_TEMPLATE_PATH = self._orig

    def test_low_testability_not_in_prompt_target_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_inputs(tmp_path)
            tpl = _patch_template(tmp_path)
            tg.PROMPT_TEMPLATE_PATH = tpl

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir)])
            self.assertEqual(rc, 0)

            prompt_content = (base_dir / "zhang-san" / "discovery" / "triplet_builder_prompt.md").read_text(encoding="utf-8")
            # lv_003 is low testability and should not appear in target_variables section
            # We check by looking at what the tool embedded in {target_variables_json}
            target_section_start = prompt_content.find("Targets: ")
            target_section_end = prompt_content.find("\nProfile: ")
            target_section = prompt_content[target_section_start:target_section_end]
            self.assertNotIn("lv_003", target_section)
            self.assertIn("lv_001", target_section)


# ---------------------------------------------------------------------------
# Test 3: --target-ids filter
# ---------------------------------------------------------------------------

class TestTargetIdsFilter(unittest.TestCase):
    def test_target_ids_filter(self):
        filtered = filter_target_variables(_SAMPLE_VARIABLES, target_ids=["lv_001"])
        ids = [v["id"] for v in filtered]
        self.assertEqual(ids, ["lv_001"])

    def test_target_ids_excludes_low_testability_even_if_specified(self):
        filtered = filter_target_variables(_SAMPLE_VARIABLES, target_ids=["lv_003"])
        self.assertEqual(filtered, [])


# ---------------------------------------------------------------------------
# Test 4: parse_output saves triplet_groups.json
# ---------------------------------------------------------------------------

class TestParseOutputSavesJson(unittest.TestCase):
    def setUp(self):
        self._orig = tg.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        tg.PROMPT_TEMPLATE_PATH = self._orig

    def test_parse_output_saves_triplet_groups_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_inputs(tmp_path)
            tpl = _patch_template(tmp_path)
            tg.PROMPT_TEMPLATE_PATH = tpl

            groups = [_make_group("tg_001", "lv_001"), _make_group("tg_002", "lv_002")]
            out = tmp_path / "out.json"
            out.write_text(json.dumps({"triplet_groups": groups}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertEqual(rc, 0)
            saved = base_dir / "zhang-san" / "discovery" / "triplet_groups.json"
            self.assertTrue(saved.exists())
            data = json.loads(saved.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 2)


# ---------------------------------------------------------------------------
# Test 5: schema validation rejects missing probes
# ---------------------------------------------------------------------------

class TestSchemaValidationRejectsMissingProbes(unittest.TestCase):
    def setUp(self):
        self._orig = tg.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        tg.PROMPT_TEMPLATE_PATH = self._orig

    def test_schema_validation_rejects_missing_probes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_inputs(tmp_path)
            tpl = _patch_template(tmp_path)
            tg.PROMPT_TEMPLATE_PATH = tpl

            g = _make_group("tg_001", "lv_001")
            del g["question_A"]["probes"]  # Remove probes
            out = tmp_path / "out.json"
            out.write_text(json.dumps({"triplet_groups": [g]}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertNotEqual(rc, 0)
            saved = base_dir / "zhang-san" / "discovery" / "triplet_groups.json"
            self.assertFalse(saved.exists())


# ---------------------------------------------------------------------------
# Test 6: P4 gate requires coverage per candidate
# ---------------------------------------------------------------------------

class TestP4GateRequiresCoveragePerCandidate(unittest.TestCase):
    def test_p4_gate_requires_coverage_per_candidate(self):
        groups = [_make_group("tg_001", "lv_001")]
        # lv_002 is not covered
        errors = check_p4_extra_quality_gate(groups, ["lv_001", "lv_002"])
        self.assertTrue(any("lv_002" in e for e in errors))

    def test_p4_gate_passes_when_all_covered(self):
        groups = [_make_group("tg_001", "lv_001"), _make_group("tg_002", "lv_002")]
        errors = check_p4_extra_quality_gate(groups, ["lv_001", "lv_002"])
        coverage_errors = [e for e in errors if "没有对应" in e]
        self.assertEqual(coverage_errors, [])


# ---------------------------------------------------------------------------
# Test 7: compute_ab_overlap high similarity
# ---------------------------------------------------------------------------

class TestComputeAbOverlapHighSimilarity(unittest.TestCase):
    def test_compute_ab_overlap_high_similarity(self):
        g = {"question_A": {"text": _TEXT_A}, "question_B": {"text": _TEXT_B}}
        score = compute_ab_overlap(g)
        self.assertGreaterEqual(score, 0.70, f"Expected ≥0.70 but got {score:.3f}")

    def test_identical_texts_give_score_one(self):
        g = {"question_A": {"text": "完全相同的文本"}, "question_B": {"text": "完全相同的文本"}}
        score = compute_ab_overlap(g)
        self.assertAlmostEqual(score, 1.0)


# ---------------------------------------------------------------------------
# Test 8: compute_ab_overlap low similarity
# ---------------------------------------------------------------------------

class TestComputeAbOverlapLowSimilarity(unittest.TestCase):
    def test_compute_ab_overlap_low_similarity(self):
        g = {"question_A": {"text": _TEXT_A}, "question_B": {"text": _TEXT_B_DIFFERENT}}
        score = compute_ab_overlap(g)
        self.assertLess(score, 0.70, f"Expected <0.70 but got {score:.3f}")

    def test_completely_different_texts(self):
        g = {"question_A": {"text": "AAAA"}, "question_B": {"text": "BBBB"}}
        score = compute_ab_overlap(g)
        self.assertLess(score, 0.5)


# ---------------------------------------------------------------------------
# Test 9: overlap < 0.70 without override blocks save
# ---------------------------------------------------------------------------

class TestOverlapBelowThresholdBlocksWithoutOverride(unittest.TestCase):
    def setUp(self):
        self._orig = tg.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        tg.PROMPT_TEMPLATE_PATH = self._orig

    def test_overlap_below_threshold_blocks_without_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_inputs(tmp_path)
            tpl = _patch_template(tmp_path)
            tg.PROMPT_TEMPLATE_PATH = tpl

            # Use low-overlap texts, no manual_override_reason
            g = _make_group("tg_001", "lv_001", text_a=_TEXT_A, text_b=_TEXT_B_DIFFERENT)
            g2 = _make_group("tg_002", "lv_002")
            out = tmp_path / "out.json"
            out.write_text(json.dumps({"triplet_groups": [g, g2]}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertNotEqual(rc, 0)
            saved = base_dir / "zhang-san" / "discovery" / "triplet_groups.json"
            self.assertFalse(saved.exists())


# ---------------------------------------------------------------------------
# Test 10: manual_override suppresses error but keeps overlap_warning
# ---------------------------------------------------------------------------

class TestManualOverrideSuppressesError(unittest.TestCase):
    def test_manual_override_suppresses_error(self):
        g = _make_group("tg_001", "lv_001", text_a=_TEXT_A, text_b=_TEXT_B_DIFFERENT,
                        manual_override_reason="场景语义等价但字面分数不足")
        score = compute_ab_overlap(g)
        g["ab_overlap_score"] = score
        if score < 0.70:
            g["overlap_warning"] = True

        errors = check_p4_extra_quality_gate([g], ["lv_001"])
        # Should NOT produce overlap error because manual_override_reason is set
        overlap_errors = [e for e in errors if "重叠率" in e]
        self.assertEqual(overlap_errors, [], f"Unexpected overlap errors: {overlap_errors}")
        # overlap_warning flag must remain True
        if score < 0.70:
            self.assertTrue(g.get("overlap_warning"))


# ---------------------------------------------------------------------------
# Test 11: interview_script.md is generated with A/B/C content
# ---------------------------------------------------------------------------

class TestInterviewScriptGenerated(unittest.TestCase):
    def setUp(self):
        self._orig = tg.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        tg.PROMPT_TEMPLATE_PATH = self._orig

    def test_interview_script_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_inputs(tmp_path)
            tpl = _patch_template(tmp_path)
            tg.PROMPT_TEMPLATE_PATH = tpl

            groups = [_make_group("tg_001", "lv_001"), _make_group("tg_002", "lv_002")]
            out = tmp_path / "out.json"
            out.write_text(json.dumps({"triplet_groups": groups}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertEqual(rc, 0)

            script_path = base_dir / "zhang-san" / "discovery" / "interview_script.md"
            self.assertTrue(script_path.exists())
            content = script_path.read_text(encoding="utf-8")
            self.assertIn("Question A", content)
            self.assertIn("Question B", content)
            self.assertIn("Question C", content)
            self.assertIn("⚠️", content)

    def test_interview_script_function_returns_string(self):
        groups = [_make_group()]
        result = generate_interview_script(groups, _SAMPLE_VARIABLES)
        self.assertIsInstance(result, str)
        self.assertIn("Question A", result)
        self.assertIn("Question B", result)
        self.assertIn("Question C", result)


# ---------------------------------------------------------------------------
# Test 12: dry_run conflicts with parse_output
# ---------------------------------------------------------------------------

class TestDryRunConflictsWithParseOutput(unittest.TestCase):
    def test_dry_run_conflicts_with_parse_output(self):
        rc = main(["--slug", "test", "--dry-run", "--parse-output", "some.json"])
        self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# Test 13: dry_run does not write files
# ---------------------------------------------------------------------------

class TestDryRunDoesNotWriteFiles(unittest.TestCase):
    def setUp(self):
        self._orig = tg.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        tg.PROMPT_TEMPLATE_PATH = self._orig

    def test_dry_run_does_not_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_inputs(tmp_path)
            tpl = _patch_template(tmp_path)
            tg.PROMPT_TEMPLATE_PATH = tpl

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--dry-run"])
            self.assertEqual(rc, 0)

            prompt_file = base_dir / "zhang-san" / "discovery" / "triplet_builder_prompt.md"
            self.assertFalse(prompt_file.exists())


# ---------------------------------------------------------------------------
# Test 14: parse_output updates meta status
# ---------------------------------------------------------------------------

class TestParseOutputUpdatesMetaStatus(unittest.TestCase):
    def setUp(self):
        self._orig = tg.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        tg.PROMPT_TEMPLATE_PATH = self._orig

    def test_parse_output_updates_meta_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_inputs(tmp_path)
            tpl = _patch_template(tmp_path)
            tg.PROMPT_TEMPLATE_PATH = tpl

            meta_path = base_dir / "zhang-san" / "meta.json"
            meta_path.write_text(
                json.dumps({"slug": "zhang-san", "discovery": {"status": "variables_ready"}}),
                encoding="utf-8",
            )

            groups = [_make_group("tg_001", "lv_001"), _make_group("tg_002", "lv_002")]
            out = tmp_path / "out.json"
            out.write_text(json.dumps({"triplet_groups": groups}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertEqual(rc, 0)

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(meta["discovery"]["status"], "triplets_ready")
            self.assertEqual(meta["discovery"]["triplet_count"], 2)


# ---------------------------------------------------------------------------
# Test 15: schema rejects probes as list
# ---------------------------------------------------------------------------

class TestSchemaValidationRejectsListProbes(unittest.TestCase):
    def setUp(self):
        self._orig = tg.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        tg.PROMPT_TEMPLATE_PATH = self._orig

    def test_schema_validation_rejects_list_probes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_inputs(tmp_path)
            tpl = _patch_template(tmp_path)
            tg.PROMPT_TEMPLATE_PATH = tpl

            g = _make_group()
            g["question_A"]["probes"] = ["probe1", "probe2"]  # list instead of dict
            out = tmp_path / "out.json"
            out.write_text(json.dumps({"triplet_groups": [g]}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# Test 16: schema rejects expected_reveals as list
# ---------------------------------------------------------------------------

class TestSchemaValidationRejectsListExpectedReveals(unittest.TestCase):
    def setUp(self):
        self._orig = tg.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        tg.PROMPT_TEMPLATE_PATH = self._orig

    def test_schema_validation_rejects_list_expected_reveals(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_dir = _write_inputs(tmp_path)
            tpl = _patch_template(tmp_path)
            tg.PROMPT_TEMPLATE_PATH = tpl

            g = _make_group()
            g["question_B"]["expected_reveals"] = ["reveal1", "reveal2"]  # list instead of dict
            out = tmp_path / "out.json"
            out.write_text(json.dumps({"triplet_groups": [g]}), encoding="utf-8")

            rc = main(["--slug", "zhang-san", "--base-dir", str(base_dir), "--parse-output", str(out)])
            self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# Test 17: P4 gate requires quality_notes
# ---------------------------------------------------------------------------

class TestP4GateRequiresQualityNotes(unittest.TestCase):
    def test_p4_gate_requires_single_variable_control(self):
        g = _make_group(include_quality_notes=True)
        del g["quality_notes"]["single_variable_control"]
        errors = check_p4_extra_quality_gate([g], ["lv_001"])
        self.assertTrue(any("single_variable_control" in e for e in errors))

    def test_p4_gate_requires_unpredictability(self):
        g = _make_group(include_quality_notes=True)
        del g["quality_notes"]["unpredictability"]
        errors = check_p4_extra_quality_gate([g], ["lv_001"])
        self.assertTrue(any("unpredictability" in e for e in errors))

    def test_p4_gate_requires_decision_difference(self):
        g = _make_group(include_quality_notes=True)
        del g["quality_notes"]["decision_difference"]
        errors = check_p4_extra_quality_gate([g], ["lv_001"])
        self.assertTrue(any("decision_difference" in e for e in errors))

    def test_p4_gate_requires_quality_notes_present(self):
        g = _make_group(include_quality_notes=False)
        errors = check_p4_extra_quality_gate([g], ["lv_001"])
        self.assertTrue(any("quality_notes" in e for e in errors))


# ---------------------------------------------------------------------------
# Test 18: P4 gate requires question_C.conflict_added
# ---------------------------------------------------------------------------

class TestP4GateRequiresQuestionCConflictAdded(unittest.TestCase):
    def test_p4_gate_requires_question_c_conflict_added(self):
        g = _make_group(include_conflict_added=False)
        errors = check_p4_extra_quality_gate([g], ["lv_001"])
        self.assertTrue(any("conflict_added" in e for e in errors))

    def test_p4_gate_passes_with_conflict_added(self):
        g = _make_group(include_conflict_added=True)
        errors = check_p4_extra_quality_gate([g], ["lv_001"])
        conflict_errors = [e for e in errors if "conflict_added" in e]
        self.assertEqual(conflict_errors, [])


if __name__ == "__main__":
    unittest.main()
