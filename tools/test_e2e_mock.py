#!/usr/bin/env python3
"""
End-to-end smoke tests using the mock_expert/ fixture directory.

Validates the full P2-P7 pipeline without network or AI dependencies.
All P7 write tests use pytest tmp_path to avoid polluting mock_expert/.

Scope note
----------
These tests are *smoke tests*: they verify the main chain (P2→P7) using a
2-triplet fixture, not full coverage of all P3 candidates.  The P4 full-coverage
quality gate (every high/medium candidate has a triplet) is exercised separately
in ``test_p4_gate_requires_all_selected_high_medium_targets_covered`` below.
The mock fixture intentionally covers only the variables targeted by its two
triplet groups; passing ``target_ids`` as the full P3 pool to
``check_p4_extra_quality_gate`` would (correctly) fail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from discovery_schema import (
    DISCOVERY_STATUSES,
    validate_expert_profile,
    validate_latent_variable,
    validate_latent_variables_pool,
    validate_triplet_group,
)
from latent_variable_builder import check_p3_extra_quality_gate
from triplet_generator import check_p4_extra_quality_gate
from interview_session import check_p5_quality_gate
from interview_analyzer import check_p6_quality_gate
import skill_writer as sw

MOCK_DIR = Path(__file__).parent.parent / "mock_expert"
MOCK_DISCOVERY = MOCK_DIR / "discovery"


# ---------------------------------------------------------------------------
# Fixture loader helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_mock_meta() -> dict:
    return _load_json(MOCK_DIR / "meta.json")


def _load_mock_analysis() -> dict:
    return _load_json(MOCK_DISCOVERY / "interview_analysis.json")


def _load_mock_transcript() -> list:
    return _load_json(MOCK_DISCOVERY / "interview_transcript.json")


def _write_skill_in_tmp(tmp_path: Path) -> Path:
    """Create mock-troubleshooter skill in tmp_path and return base_dir."""
    base_dir = str(tmp_path / "skills" / "expert")
    meta = _load_mock_meta()
    analysis = _load_mock_analysis()
    latent_report = (MOCK_DISCOVERY / "latent_report.md").read_text(encoding="utf-8")
    transcript_md = (MOCK_DISCOVERY / "interview_transcript.md").read_text(encoding="utf-8")

    sw.write_expert_skill(
        base_dir=base_dir,
        slug="mock-troubleshooter",
        name="Mock Troubleshooter",
        expertise_type="troubleshooter",
        expertise_content="专业知识内容：分布式系统故障排查。",
        domain_summary="分布式系统可用性与性能调优。",
        meta=meta,
        latent_report=latent_report,
        interview_transcript=transcript_md,
        discovery_meta=analysis,
    )
    return tmp_path / "skills" / "expert"


# ---------------------------------------------------------------------------
# P2: expert_profile.json schema
# ---------------------------------------------------------------------------

def test_mock_expert_profile_passes_schema():
    profile = _load_json(MOCK_DISCOVERY / "expert_profile.json")
    errors = validate_expert_profile(profile)
    assert errors == [], f"expert_profile.json schema errors: {errors}"


# ---------------------------------------------------------------------------
# P3: latent_variables.json schema + pool validation
# ---------------------------------------------------------------------------

def test_mock_latent_variables_pass_schema():
    variables = _load_json(MOCK_DISCOVERY / "latent_variables.json")
    all_errors = []
    for var in variables:
        errs = validate_latent_variable(var)
        if errs:
            all_errors.extend([f"[{var.get('id')}] {e}" for e in errs])
    assert all_errors == [], f"latent_variables.json schema errors: {all_errors}"
    pool_errors = validate_latent_variables_pool(variables)
    assert pool_errors == [], f"pool validation errors: {pool_errors}"


def test_mock_latent_variables_pass_p3_gate():
    variables = _load_json(MOCK_DISCOVERY / "latent_variables.json")
    errors = check_p3_extra_quality_gate(variables)
    assert errors == [], f"P3 gate errors: {errors}"


# ---------------------------------------------------------------------------
# P4: triplet_groups.json schema + gate
# ---------------------------------------------------------------------------

def test_mock_triplet_groups_pass_schema():
    groups = _load_json(MOCK_DISCOVERY / "triplet_groups.json")
    all_errors = []
    for g in groups:
        errs = validate_triplet_group(g)
        if errs:
            all_errors.extend([f"[{g.get('id', '?')}] {e}" for e in errs])
    assert all_errors == [], f"triplet_groups.json schema errors: {all_errors}"


def test_mock_triplet_groups_pass_p4_gate():
    groups = _load_json(MOCK_DISCOVERY / "triplet_groups.json")
    # Only pass the variable IDs actually covered by the mock triplets
    target_ids = [g["target_variable"] for g in groups]
    errors = check_p4_extra_quality_gate(groups, target_ids)
    assert errors == [], f"P4 gate errors: {errors}"


# ---------------------------------------------------------------------------
# P5: interview_transcript.json quality gate
# ---------------------------------------------------------------------------

def test_mock_transcript_passes_p5_gate():
    records = _load_mock_transcript()
    errors = check_p5_quality_gate(records)
    assert errors == [], f"P5 gate errors: {errors}"


# ---------------------------------------------------------------------------
# P6: interview_analysis.json quality gate
# ---------------------------------------------------------------------------

def test_mock_analysis_passes_p6_gate():
    result = _load_mock_analysis()
    transcript = _load_mock_transcript()
    errors, warnings = check_p6_quality_gate(result, transcript)
    assert errors == [], f"P6 gate errors: {errors}"
    assert warnings == [], f"P6 gate warnings: {warnings}"


# ---------------------------------------------------------------------------
# P7: write_expert_skill with discovery_meta
# ---------------------------------------------------------------------------

def test_p7_write_produces_latent_heuristics(tmp_path):
    base_dir = _write_skill_in_tmp(tmp_path)
    heuristics_path = base_dir / "mock-troubleshooter" / "heuristics.json"
    assert heuristics_path.exists(), "heuristics.json was not created"
    heuristics = json.loads(heuristics_path.read_text(encoding="utf-8"))
    assert "latent_variables" in heuristics
    assert "priority_rules" in heuristics
    assert "boundary_conditions" in heuristics
    non_empty = (
        len(heuristics["latent_variables"]) > 0
        or len(heuristics["priority_rules"]) > 0
        or len(heuristics["boundary_conditions"]) > 0
    )
    assert non_empty, "All three latent fields are empty; expected at least one to be non-empty"


def test_p7_write_produces_expertise_with_latent_section(tmp_path):
    base_dir = _write_skill_in_tmp(tmp_path)
    expertise_path = base_dir / "mock-troubleshooter" / "expertise.md"
    assert expertise_path.exists(), "expertise.md was not created"
    content = expertise_path.read_text(encoding="utf-8")
    assert "## 隐性知识增强" in content, "expertise.md does not contain '## 隐性知识增强'"


def test_p7_write_produces_knowledge_graph_with_tables(tmp_path):
    base_dir = _write_skill_in_tmp(tmp_path)
    kg_path = base_dir / "mock-troubleshooter" / "knowledge_graph.md"
    assert kg_path.exists(), "knowledge_graph.md was not created"
    content = kg_path.read_text(encoding="utf-8")
    has_table = any(
        section in content
        for section in ("## 隐性变量节点", "## 规则冲突关系", "## 边界条件")
    )
    assert has_table, "knowledge_graph.md does not contain any expected table section"


def test_p7_write_enables_discovery_meta(tmp_path):
    base_dir = _write_skill_in_tmp(tmp_path)
    meta_path = base_dir / "mock-troubleshooter" / "meta.json"
    assert meta_path.exists(), "meta.json was not created"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    discovery = meta.get("discovery", {})
    assert discovery.get("enabled") is True, f"discovery.enabled should be True, got {discovery.get('enabled')}"


def test_full_chain_meta_status_reaches_merged(tmp_path):
    base_dir = _write_skill_in_tmp(tmp_path)
    meta_path = base_dir / "mock-troubleshooter" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # Manually advance status to 'merged' (as the pipeline control would do post-P7)
    meta.setdefault("discovery", {})["status"] = "merged"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Verify the status is legal
    updated_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    status = updated_meta["discovery"]["status"]
    assert status in DISCOVERY_STATUSES, f"'{status}' is not in DISCOVERY_STATUSES"
    assert status == "merged"


# ---------------------------------------------------------------------------
# P4 full-coverage quality gate — independent of the smoke fixture
# ---------------------------------------------------------------------------

def test_p4_gate_requires_all_selected_high_medium_targets_covered():
    """Verify check_p4_extra_quality_gate fails when a high/medium target has no triplet.

    This test is separate from the smoke fixture (which only covers 2 of 5 P3 candidates).
    It proves the quality gate correctly enforces full coverage when all high/medium
    target_ids are passed in.
    """
    # 5 latent variables — 3 high/medium, 2 low
    variables = [
        {"id": "lv_001", "testability": "high"},
        {"id": "lv_002", "testability": "high"},
        {"id": "lv_003", "testability": "medium"},
        {"id": "lv_004", "testability": "low"},
        {"id": "lv_005", "testability": "low"},
    ]
    high_medium_ids = [v["id"] for v in variables if v["testability"] in ("high", "medium")]
    # ["lv_001", "lv_002", "lv_003"]

    # Groups cover lv_001 and lv_002 but intentionally omit lv_003
    groups = [
        {
            "id": "tg_001",
            "target_variable": "lv_001",
            "quality_notes": {
                "single_variable_control": "yes",
                "unpredictability": "yes",
                "decision_difference": "yes",
            },
            "question_C": {"conflict_added": "冲突描述"},
        },
        {
            "id": "tg_002",
            "target_variable": "lv_002",
            "quality_notes": {
                "single_variable_control": "yes",
                "unpredictability": "yes",
                "decision_difference": "yes",
            },
            "question_C": {"conflict_added": "冲突描述"},
        },
    ]

    errors = check_p4_extra_quality_gate(groups, high_medium_ids)
    assert any("lv_003" in e for e in errors), (
        f"Expected coverage error for lv_003, got: {errors}"
    )
