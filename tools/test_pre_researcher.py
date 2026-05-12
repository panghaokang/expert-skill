#!/usr/bin/env python3
"""Unit tests for pre_researcher.py (P2 discovery phase)."""

from __future__ import annotations

import json
import sys
import os
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import pre_researcher
from pre_researcher import (
    assemble_prompt,
    check_p2_quality_gate,
    read_material_file,
    read_materials,
    _extract_text_from_json,
    _update_meta_json,
    main,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MINIMAL_TEMPLATE = (
    "Name:{name} Title:{title} Domain:{domain} Years:{years} "
    "Type:{expertise_type} Materials:{materials} "
    "OpenResearch:{open_research} Desc:{expertise_description} "
    "BG:{domain_background}"
)

_FULL_TEMPLATE = (
    "{name} ({title}, {domain}, {years})\n"
    "Type: {expertise_type}\n"
    "Materials:\n{materials}\n"
    "Open research: {open_research}\n"
    "Desc: {expertise_description}\n"
    "Background: {domain_background}\n"
    "Note: {expertise_type} specialists usually discuss X."
)


def _make_valid_profile() -> dict:
    """Return a profile dict that passes both schema validation and P2 quality gate."""
    return {
        "identity": {"name": "张三", "title": "架构师", "domain": "分布式系统", "years_in_field": 10},
        "visible_knowledge": [
            {"rule": "先查连接池", "source": "doc1"},
            {"rule": "避免单点", "source": "doc2"},
            {"rule": "监控先行", "source": "doc3"},
        ],
        "known_decisions": [
            {"case": "DB选型", "context": "高并发", "decision": "PostgreSQL", "source": "doc1"},
            {"case": "缓存策略", "context": "读多写少", "decision": "Redis", "source": "doc2"},
        ],
        "domain_context": {
            "key_challenges": ["CAP theorem"],
            "common_pitfalls": ["over-sharding"],
            "methodology_clashes": ["microservices vs monolith"],
        },
        "suspected_gaps": [
            {"gap": "一致性协议选择", "reason": "同类架构师通常明确表达Raft vs Paxos立场，此专家未提及"},
            {"gap": "熔断策略", "reason": "分布式系统架构师通常讨论熔断，材料中完全缺失"},
            {"gap": "数据库分片策略", "reason": "高并发场景必然涉及分片，但材料中从未提到"},
        ],
    }


def _make_insufficient_profile() -> dict:
    """Return a profile dict that passes schema validation but fails P2 quality gate."""
    return {
        "identity": {"name": "李四"},
        "visible_knowledge": [{"rule": "only one rule", "source": "s1"}],
        "known_decisions": [{"case": "c1", "context": "ctx", "decision": "d", "source": "s"}],
        "domain_context": {
            "key_challenges": ["challenge1"],
            "common_pitfalls": ["pitfall1"],
            "methodology_clashes": ["clash1"],
        },
        "suspected_gaps": [{"gap": "gap1", "reason": "reason1"}],
    }


# ---------------------------------------------------------------------------
# Test 1: read_materials merges multiple text files
# ---------------------------------------------------------------------------

class TestMaterialsTextMerge(unittest.TestCase):
    def test_materials_text_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "file1.txt"
            p2 = Path(tmp) / "file2.txt"
            p1.write_text("content from file1", encoding="utf-8")
            p2.write_text("content from file2", encoding="utf-8")

            result = read_materials([p1, p2])

            self.assertIn("content from file1", result)
            self.assertIn("content from file2", result)
            self.assertIn("file1.txt", result)
            self.assertIn("file2.txt", result)


# ---------------------------------------------------------------------------
# Test 2: feishu JSON extraction
# ---------------------------------------------------------------------------

class TestFeishuJsonExtraction(unittest.TestCase):
    def test_feishu_json_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            feishu_data = {
                "messages": [
                    {"content": "消息一：先查连接池"},
                    {"content": "消息二：避免单点"},
                    {"content": None},       # missing content handled gracefully
                    {"other_field": "x"},    # missing content field
                ]
            }
            p = Path(tmp) / "feishu.json"
            p.write_text(json.dumps(feishu_data, ensure_ascii=False), encoding="utf-8")

            result = read_material_file(p)

            self.assertIn("消息一：先查连接池", result)
            self.assertIn("消息二：避免单点", result)

    def test_feishu_non_string_content_serialized(self):
        data = {"messages": [{"content": {"key": "value"}}]}
        result = _extract_text_from_json(data)
        self.assertIn("key", result)
        self.assertIn("value", result)


# ---------------------------------------------------------------------------
# Test 3: email JSON extraction
# ---------------------------------------------------------------------------

class TestEmailJsonExtraction(unittest.TestCase):
    def test_email_json_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            email_data = {
                "emails": [
                    {"subject": "架构评审", "body": "建议采用事件驱动架构"},
                    {"subject": "故障复盘", "body": "根因是连接池耗尽"},
                ]
            }
            p = Path(tmp) / "emails.json"
            p.write_text(json.dumps(email_data, ensure_ascii=False), encoding="utf-8")

            result = read_material_file(p)

            self.assertIn("架构评审", result)
            self.assertIn("建议采用事件驱动架构", result)
            self.assertIn("故障复盘", result)
            self.assertIn("连接池耗尽", result)

    def test_email_missing_fields_skipped(self):
        data = {"emails": [{"subject": "only subject"}, {"body": "only body"}, {}]}
        result = _extract_text_from_json(data)
        self.assertIn("only subject", result)
        self.assertIn("only body", result)


# ---------------------------------------------------------------------------
# Test 4: P2 quality gate pass
# ---------------------------------------------------------------------------

class TestP2QualityGatePass(unittest.TestCase):
    def test_p2_quality_gate_pass(self):
        profile = _make_valid_profile()
        errors = check_p2_quality_gate(profile)
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# Test 5: P2 quality gate fail — insufficient gaps
# ---------------------------------------------------------------------------

class TestP2QualityGateFailInsufficientGaps(unittest.TestCase):
    def test_p2_quality_gate_fail_insufficient_gaps(self):
        profile = _make_valid_profile()
        profile["suspected_gaps"] = [{"gap": "only one", "reason": "only one reason"}]
        errors = check_p2_quality_gate(profile)
        self.assertTrue(any("suspected_gaps" in e for e in errors))

    def test_p2_quality_gate_fail_insufficient_visible_knowledge(self):
        profile = _make_valid_profile()
        profile["visible_knowledge"] = [{"rule": "only one", "source": "s"}]
        errors = check_p2_quality_gate(profile)
        self.assertTrue(any("visible_knowledge" in e for e in errors))

    def test_p2_quality_gate_fail_insufficient_decisions(self):
        profile = _make_valid_profile()
        profile["known_decisions"] = [{"case": "c", "context": "ctx", "decision": "d", "source": "s"}]
        errors = check_p2_quality_gate(profile)
        self.assertTrue(any("known_decisions" in e for e in errors))


# ---------------------------------------------------------------------------
# Test 6: P2 quality gate fail — empty domain_context
# ---------------------------------------------------------------------------

class TestP2QualityGateFailEmptyDomainContext(unittest.TestCase):
    def test_p2_quality_gate_fail_empty_domain_context(self):
        profile = _make_valid_profile()
        profile["domain_context"]["key_challenges"] = []
        errors = check_p2_quality_gate(profile)
        self.assertTrue(any("key_challenges" in e for e in errors))

    def test_p2_quality_gate_fail_empty_pitfalls(self):
        profile = _make_valid_profile()
        profile["domain_context"]["common_pitfalls"] = []
        errors = check_p2_quality_gate(profile)
        self.assertTrue(any("common_pitfalls" in e for e in errors))

    def test_p2_quality_gate_fail_empty_clashes(self):
        profile = _make_valid_profile()
        profile["domain_context"]["methodology_clashes"] = []
        errors = check_p2_quality_gate(profile)
        self.assertTrue(any("methodology_clashes" in e for e in errors))


# ---------------------------------------------------------------------------
# Test 7: prompt assembly — no leftover {placeholders}
# ---------------------------------------------------------------------------

class TestPromptAssembly(unittest.TestCase):
    def test_prompt_assembly_no_leftover_placeholders(self):
        import re
        result = assemble_prompt(
            template=_FULL_TEMPLATE,
            name="张三",
            title="架构师",
            domain="分布式系统",
            years="10",
            expertise_type="architect",
            materials_text="一些材料文本",
            open_research="行业背景信息",
            expertise_description="擅长分布式设计",
            domain_background="云原生领域",
        )
        leftover = re.findall(r'\{[a-z_]+\}', result)
        self.assertEqual(leftover, [], f"Leftover placeholders found: {leftover}")

    def test_prompt_assembly_values_inserted(self):
        result = assemble_prompt(
            template=_MINIMAL_TEMPLATE,
            name="李四",
            title="高级工程师",
            domain="数据库",
            years="5",
            expertise_type="troubleshooter",
            materials_text="故障日志",
        )
        self.assertIn("李四", result)
        self.assertIn("高级工程师", result)
        self.assertIn("数据库", result)
        self.assertIn("troubleshooter", result)
        self.assertIn("故障日志", result)

    def test_prompt_assembly_expertise_type_replaced_multiple_times(self):
        template = "Type: {expertise_type}. As a {expertise_type} expert."
        result = assemble_prompt(
            template=template,
            name="x", title="", domain="", years="",
            expertise_type="reviewer",
            materials_text="",
        )
        self.assertEqual(result.count("reviewer"), 2)
        self.assertNotIn("{expertise_type}", result)

    def test_prompt_assembly_defaults_for_empty_optional_fields(self):
        result = assemble_prompt(
            template=_MINIMAL_TEMPLATE,
            name="王五",
            title="",
            domain="",
            years="",
            expertise_type="operator",
            materials_text="",
        )
        self.assertIn("（未填写）", result)
        self.assertIn("（未提供）", result)


# ---------------------------------------------------------------------------
# Test 8: parse_output saves expert_profile.json
# ---------------------------------------------------------------------------

class TestParseOutputSavesProfileJson(unittest.TestCase):
    def setUp(self):
        self._orig_template_path = pre_researcher.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        pre_researcher.PROMPT_TEMPLATE_PATH = self._orig_template_path

    def test_parse_output_saves_profile_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Create a minimal template
            template_file = tmp_path / "pre_research.md"
            template_file.write_text(_MINIMAL_TEMPLATE, encoding="utf-8")
            pre_researcher.PROMPT_TEMPLATE_PATH = template_file

            # Write valid AI output JSON
            output_file = tmp_path / "ai_output.json"
            output_file.write_text(
                json.dumps({"expert_profile": _make_valid_profile()}, ensure_ascii=False),
                encoding="utf-8",
            )

            base_dir = tmp_path / "skills" / "expert"
            rc = main([
                "--slug", "zhang-san",
                "--name", "张三",
                "--expertise-type", "architect",
                "--base-dir", str(base_dir),
                "--parse-output", str(output_file),
            ])

            self.assertEqual(rc, 0)
            profile_path = base_dir / "zhang-san" / "discovery" / "expert_profile.json"
            self.assertTrue(profile_path.exists(), "expert_profile.json should be created")

            saved = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["identity"]["name"], "张三")


# ---------------------------------------------------------------------------
# Test 9: parse_output does NOT save on quality gate fail
# ---------------------------------------------------------------------------

class TestParseOutputNoSaveOnGateFail(unittest.TestCase):
    def setUp(self):
        self._orig_template_path = pre_researcher.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        pre_researcher.PROMPT_TEMPLATE_PATH = self._orig_template_path

    def test_parse_output_no_save_on_gate_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            template_file = tmp_path / "pre_research.md"
            template_file.write_text(_MINIMAL_TEMPLATE, encoding="utf-8")
            pre_researcher.PROMPT_TEMPLATE_PATH = template_file

            # Write AI output that fails quality gate
            output_file = tmp_path / "ai_output.json"
            output_file.write_text(
                json.dumps({"expert_profile": _make_insufficient_profile()}, ensure_ascii=False),
                encoding="utf-8",
            )

            base_dir = tmp_path / "skills" / "expert"
            rc = main([
                "--slug", "li-si",
                "--name", "李四",
                "--expertise-type", "troubleshooter",
                "--base-dir", str(base_dir),
                "--parse-output", str(output_file),
            ])

            self.assertNotEqual(rc, 0)
            profile_path = base_dir / "li-si" / "discovery" / "expert_profile.json"
            self.assertFalse(profile_path.exists(), "expert_profile.json must NOT be created on gate fail")


# ---------------------------------------------------------------------------
# Test 10: dry_run conflicts with parse_output
# ---------------------------------------------------------------------------

class TestDryRunConflictsWithParseOutput(unittest.TestCase):
    def test_dry_run_conflicts_with_parse_output(self):
        rc = main([
            "--slug", "test",
            "--name", "Test",
            "--expertise-type", "architect",
            "--dry-run",
            "--parse-output", "some_file.json",
        ])
        self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# Test 11: unknown JSON falls back to full text dump
# ---------------------------------------------------------------------------

class TestUnknownJsonFallbackToText(unittest.TestCase):
    def test_unknown_json_fallback_to_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            unknown_data = {"foo": "bar", "nested": {"x": 1}}
            p = Path(tmp) / "unknown.json"
            p.write_text(json.dumps(unknown_data, ensure_ascii=False), encoding="utf-8")

            result = read_material_file(p)

            self.assertIn("foo", result)
            self.assertIn("bar", result)
            self.assertIn("nested", result)

    def test_unknown_json_does_not_lose_content(self):
        data = {"custom_key": "custom_value_12345"}
        result = _extract_text_from_json(data)
        self.assertIn("custom_value_12345", result)


# ---------------------------------------------------------------------------
# Test 12: parse_output updates meta.json when it exists
# ---------------------------------------------------------------------------

class TestParseOutputUpdatesMetaWhenExists(unittest.TestCase):
    def setUp(self):
        self._orig_template_path = pre_researcher.PROMPT_TEMPLATE_PATH

    def tearDown(self):
        pre_researcher.PROMPT_TEMPLATE_PATH = self._orig_template_path

    def test_parse_output_updates_meta_when_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            template_file = tmp_path / "pre_research.md"
            template_file.write_text(_MINIMAL_TEMPLATE, encoding="utf-8")
            pre_researcher.PROMPT_TEMPLATE_PATH = template_file

            # Write valid AI output JSON
            output_file = tmp_path / "ai_output.json"
            output_file.write_text(
                json.dumps({"expert_profile": _make_valid_profile()}, ensure_ascii=False),
                encoding="utf-8",
            )

            base_dir = tmp_path / "skills" / "expert"
            slug_dir = base_dir / "zhang-san"
            slug_dir.mkdir(parents=True)

            # Pre-create meta.json with discovery disabled
            meta_path = slug_dir / "meta.json"
            meta_path.write_text(
                json.dumps({"slug": "zhang-san", "discovery": {"enabled": False, "status": "not_started"}}),
                encoding="utf-8",
            )

            rc = main([
                "--slug", "zhang-san",
                "--name", "张三",
                "--expertise-type", "architect",
                "--base-dir", str(base_dir),
                "--parse-output", str(output_file),
            ])

            self.assertEqual(rc, 0)

            meta_updated = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertTrue(meta_updated["discovery"]["enabled"])
            self.assertEqual(meta_updated["discovery"]["status"], "profile_ready")

    def test_update_meta_json_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "meta.json"
            meta_path.write_text(
                json.dumps({"slug": "test", "discovery": {"enabled": False, "status": "not_started"}}),
                encoding="utf-8",
            )
            _update_meta_json(meta_path)
            result = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertTrue(result["discovery"]["enabled"])
            self.assertEqual(result["discovery"]["status"], "profile_ready")


if __name__ == "__main__":
    unittest.main()
