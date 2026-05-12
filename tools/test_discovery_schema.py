#!/usr/bin/env python3
"""Unit tests for discovery_schema.py and related skill_schema.py extensions."""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from discovery_schema import (
    DISCOVERY_STATUSES,
    build_expert_profile,
    build_latent_variable,
    build_triplet_group,
    build_triplet_analysis,
    validate_expert_profile,
    validate_latent_variable,
    validate_triplet_group,
    validate_latent_variables_pool,
    get_discovery_dir,
    get_discovery_file_path,
)
from skill_schema import enrich_expert_meta, build_manifest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_probes(label="Q"):
    return {
        "primary": f"{label} primary probe",
        "followups": [f"{label} followup 1"],
        "signal_triggers": {
            "noticed": "noticed trigger",
            "hesitated": "hesitated trigger",
            "boundary_invented": "boundary trigger",
            "contradiction": "contradiction trigger",
            "pushback": "pushback trigger",
        },
    }


def _make_expected_reveals():
    return {
        "visible_rule": "some visible rule",
        "latent_variable": "some latent variable",
        "priority_signal": "some priority signal",
    }


def _make_question(label="A", include_variable_changed=False, include_conflict=False):
    q = {
        "text": f"Question {label} text",
        "probes": _make_probes(label),
        "expected_reveals": _make_expected_reveals(),
    }
    if include_variable_changed:
        q["variable_changed"] = "some_variable"
    if include_conflict:
        q["conflict_added"] = "some_conflict"
    return q


def _make_latent_variable(id="lv_001", testability="high"):
    return build_latent_variable(
        id=id,
        label="Risk tolerance threshold",
        source_type="comparison_gap",
        evidence_from_profile="Expert chose A over B without explanation",
        hypothesized_variable={
            "name": "risk_tolerance",
            "description": "The implicit risk level the expert tolerates",
            "why_latent": "Expert never named it but it drives every decision",
        },
        testability=testability,
        priority=5,
    )


def _make_pool(count=6, high_medium_count=4):
    pool = []
    for i in range(count):
        t = "high" if i < high_medium_count else "low"
        pool.append(_make_latent_variable(id=f"lv_{i:03d}", testability=t))
    return pool


# ---------------------------------------------------------------------------
# Test: DISCOVERY_STATUSES
# ---------------------------------------------------------------------------

class TestDiscoveryStatuses(unittest.TestCase):
    def test_contains_all_nine_statuses(self):
        expected = {
            "not_started", "profile_ready", "variables_ready", "triplets_ready",
            "interview_in_progress", "interview_completed", "analysis_ready",
            "merged", "aborted",
        }
        self.assertEqual(set(DISCOVERY_STATUSES), expected)
        self.assertEqual(len(DISCOVERY_STATUSES), 9)


# ---------------------------------------------------------------------------
# Test: build_expert_profile
# ---------------------------------------------------------------------------

class TestBuildExpertProfile(unittest.TestCase):
    def test_full_profile(self):
        profile = build_expert_profile(
            name="张三",
            title="高级架构师",
            domain="分布式系统",
            years_in_field=10,
            visible_knowledge=[{"rule": "prefer idempotent ops", "source": "doc1"}],
            known_decisions=[{"case": "DB选型", "context": "高并发", "decision": "PostgreSQL", "source": "doc2"}],
            domain_context={
                "key_challenges": ["CAP theorem"],
                "common_pitfalls": ["over-sharding"],
                "methodology_clashes": ["microservices vs monolith"],
            },
            suspected_gaps=[{"gap": "consensus protocol choice", "reason": "never mentioned in materials"}],
        )
        self.assertEqual(profile["identity"]["name"], "张三")
        self.assertEqual(profile["identity"]["years_in_field"], 10)
        self.assertEqual(len(profile["visible_knowledge"]), 1)
        self.assertEqual(len(profile["known_decisions"]), 1)
        self.assertEqual(profile["domain_context"]["key_challenges"], ["CAP theorem"])
        self.assertEqual(len(profile["suspected_gaps"]), 1)

    def test_defaults_produce_empty_lists(self):
        profile = build_expert_profile(name="李四")
        self.assertEqual(profile["visible_knowledge"], [])
        self.assertEqual(profile["known_decisions"], [])
        self.assertEqual(profile["suspected_gaps"], [])
        self.assertEqual(profile["domain_context"]["key_challenges"], [])
        self.assertEqual(profile["domain_context"]["common_pitfalls"], [])
        self.assertEqual(profile["domain_context"]["methodology_clashes"], [])

    def test_domain_context_defaults_merged_with_provided(self):
        profile = build_expert_profile(name="王五", domain_context={"key_challenges": ["scalability"]})
        self.assertEqual(profile["domain_context"]["key_challenges"], ["scalability"])
        self.assertEqual(profile["domain_context"]["common_pitfalls"], [])


# ---------------------------------------------------------------------------
# Test: build_latent_variable
# ---------------------------------------------------------------------------

class TestBuildLatentVariable(unittest.TestCase):
    def test_builds_correctly(self):
        var = _make_latent_variable()
        self.assertEqual(var["id"], "lv_001")
        self.assertEqual(var["label"], "Risk tolerance threshold")
        self.assertEqual(var["source_type"], "comparison_gap")
        self.assertIn("name", var["hypothesized_variable"])
        self.assertIn("why_latent", var["hypothesized_variable"])
        self.assertEqual(var["testability"], "high")
        self.assertEqual(var["priority"], 5)

    def test_default_priority_zero(self):
        var = build_latent_variable(
            id="lv_002", label="L", source_type="silent_topic",
            evidence_from_profile="evidence",
            hypothesized_variable={"name": "n", "description": "d", "why_latent": "w"},
            testability="medium",
        )
        self.assertEqual(var["priority"], 0)


# ---------------------------------------------------------------------------
# Test: build_triplet_group
# ---------------------------------------------------------------------------

class TestBuildTripletGroup(unittest.TestCase):
    def test_builds_correctly(self):
        triplet = build_triplet_group(
            target_variable="lv_001",
            domain_context="大规模分布式系统设计",
            question_a=_make_question("A"),
            question_b=_make_question("B", include_variable_changed=True),
            question_c=_make_question("C", include_variable_changed=True, include_conflict=True),
            control_notes="B changes only consistency model",
        )
        self.assertEqual(triplet["target_variable"], "lv_001")
        self.assertEqual(triplet["domain_context"], "大规模分布式系统设计")
        self.assertIn("question_A", triplet)
        self.assertIn("question_B", triplet)
        self.assertIn("question_C", triplet)
        self.assertEqual(triplet["control_notes"], "B changes only consistency model")
        self.assertIn("variable_changed", triplet["question_B"])
        self.assertIn("conflict_added", triplet["question_C"])

    def test_default_control_notes_empty(self):
        triplet = build_triplet_group(
            target_variable="lv_001",
            domain_context="ctx",
            question_a=_make_question("A"),
            question_b=_make_question("B"),
            question_c=_make_question("C"),
        )
        self.assertEqual(triplet["control_notes"], "")


# ---------------------------------------------------------------------------
# Test: validate_expert_profile
# ---------------------------------------------------------------------------

class TestValidateExpertProfile(unittest.TestCase):
    def test_valid_profile_no_errors(self):
        profile = build_expert_profile(name="张三")
        errors = validate_expert_profile(profile)
        self.assertEqual(errors, [])

    def test_missing_name_reports_error(self):
        profile = build_expert_profile(name="")
        errors = validate_expert_profile(profile)
        self.assertTrue(any("name" in e for e in errors))

    def test_missing_visible_knowledge_reports_error(self):
        profile = build_expert_profile(name="张三")
        del profile["visible_knowledge"]
        errors = validate_expert_profile(profile)
        self.assertTrue(any("visible_knowledge" in e for e in errors))

    def test_missing_domain_context_key_reports_error(self):
        profile = build_expert_profile(name="张三")
        del profile["domain_context"]["key_challenges"]
        errors = validate_expert_profile(profile)
        self.assertTrue(any("key_challenges" in e for e in errors))

    def test_missing_suspected_gaps_reports_error(self):
        profile = build_expert_profile(name="张三")
        del profile["suspected_gaps"]
        errors = validate_expert_profile(profile)
        self.assertTrue(any("suspected_gaps" in e for e in errors))


# ---------------------------------------------------------------------------
# Test: validate_latent_variables_pool
# ---------------------------------------------------------------------------

class TestValidateLatentVariablesPool(unittest.TestCase):
    def test_valid_pool_no_errors(self):
        pool = _make_pool(count=6, high_medium_count=4)
        errors = validate_latent_variables_pool(pool)
        self.assertEqual(errors, [])

    def test_too_few_variables(self):
        pool = _make_pool(count=3, high_medium_count=3)
        errors = validate_latent_variables_pool(pool)
        self.assertTrue(any("at least 5" in e for e in errors))

    def test_too_many_variables(self):
        pool = _make_pool(count=13, high_medium_count=5)
        errors = validate_latent_variables_pool(pool)
        self.assertTrue(any("at most 12" in e for e in errors))

    def test_insufficient_high_medium_testability(self):
        pool = _make_pool(count=6, high_medium_count=2)
        errors = validate_latent_variables_pool(pool)
        self.assertTrue(any("high or medium" in e for e in errors))

    def test_exactly_five_with_three_high_medium(self):
        pool = _make_pool(count=5, high_medium_count=3)
        errors = validate_latent_variables_pool(pool)
        self.assertEqual(errors, [])

    def test_exactly_twelve(self):
        pool = _make_pool(count=12, high_medium_count=5)
        errors = validate_latent_variables_pool(pool)
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# Test: validate_triplet_group
# ---------------------------------------------------------------------------

class TestValidateTripletGroup(unittest.TestCase):
    def _make_valid_triplet(self):
        return build_triplet_group(
            target_variable="lv_001",
            domain_context="分布式系统设计",
            question_a=_make_question("A"),
            question_b=_make_question("B"),
            question_c=_make_question("C"),
        )

    def test_valid_triplet_no_errors(self):
        triplet = self._make_valid_triplet()
        errors = validate_triplet_group(triplet)
        self.assertEqual(errors, [])

    def test_missing_target_variable(self):
        triplet = self._make_valid_triplet()
        triplet["target_variable"] = ""
        errors = validate_triplet_group(triplet)
        self.assertTrue(any("target_variable" in e for e in errors))

    def test_missing_question_text(self):
        triplet = self._make_valid_triplet()
        triplet["question_A"]["text"] = ""
        errors = validate_triplet_group(triplet)
        self.assertTrue(any("question_A.text" in e for e in errors))

    def test_missing_probes_primary(self):
        triplet = self._make_valid_triplet()
        triplet["question_B"]["probes"]["primary"] = ""
        errors = validate_triplet_group(triplet)
        self.assertTrue(any("question_B.probes.primary" in e for e in errors))

    def test_missing_expected_reveals_field(self):
        triplet = self._make_valid_triplet()
        del triplet["question_C"]["expected_reveals"]["latent_variable"]
        errors = validate_triplet_group(triplet)
        self.assertTrue(any("latent_variable" in e for e in errors))

    def test_missing_probes_key(self):
        triplet = self._make_valid_triplet()
        del triplet["question_A"]["probes"]
        errors = validate_triplet_group(triplet)
        self.assertTrue(any("question_A.probes" in e for e in errors))

    def test_missing_expected_reveals_key(self):
        triplet = self._make_valid_triplet()
        del triplet["question_B"]["expected_reveals"]
        errors = validate_triplet_group(triplet)
        self.assertTrue(any("question_B.expected_reveals" in e for e in errors))


# ---------------------------------------------------------------------------
# Test: enrich_expert_meta backward compatibility
# ---------------------------------------------------------------------------

class TestEnrichExpertMetaBackwardCompat(unittest.TestCase):
    def test_discovery_block_added_with_defaults(self):
        meta = {"name": "Test Expert", "expertise_type": "troubleshooter"}
        enriched = enrich_expert_meta(meta, slug="test_expert")
        discovery = enriched.get("discovery")
        self.assertIsNotNone(discovery)
        self.assertFalse(discovery["enabled"])
        self.assertEqual(discovery["status"], "not_started")
        self.assertEqual(discovery["interview_count"], 0)
        self.assertEqual(discovery["latent_variable_count"], 0)
        self.assertEqual(discovery["confidence_summary"], {})

    def test_existing_discovery_values_preserved(self):
        meta = {
            "name": "Test Expert",
            "expertise_type": "architect",
            "discovery": {"enabled": True, "status": "profile_ready", "interview_count": 2},
        }
        enriched = enrich_expert_meta(meta, slug="test_expert")
        self.assertTrue(enriched["discovery"]["enabled"])
        self.assertEqual(enriched["discovery"]["status"], "profile_ready")
        self.assertEqual(enriched["discovery"]["interview_count"], 2)

    def test_non_discovery_fields_unchanged(self):
        meta = {"name": "Test Expert", "expertise_type": "troubleshooter"}
        enriched = enrich_expert_meta(meta, slug="test_expert")
        self.assertEqual(enriched["slug"], "test_expert")
        self.assertEqual(enriched["expertise_type"], "troubleshooter")


# ---------------------------------------------------------------------------
# Test: build_manifest discovery artifact inclusion
# ---------------------------------------------------------------------------

class TestBuildManifestDiscovery(unittest.TestCase):
    def _make_enriched_meta(self, discovery_enabled: bool):
        meta = {
            "name": "Test Expert",
            "expertise_type": "troubleshooter",
            "discovery": {"enabled": discovery_enabled},
        }
        return enrich_expert_meta(meta, slug="test_expert")

    def test_discovery_disabled_no_discovery_artifacts(self):
        meta = self._make_enriched_meta(discovery_enabled=False)
        manifest = build_manifest(meta)
        self.assertNotIn("latent_report.md", manifest["artifacts"])
        self.assertNotIn("interview_transcript.md", manifest["artifacts"])
        self.assertNotIn("discovery", manifest["capabilities"])

    def test_discovery_enabled_includes_discovery_capability(self):
        # enabled=True → "discovery" capability, but artifacts only added when
        # report_generated / transcript_generated flags are also set.
        meta = self._make_enriched_meta(discovery_enabled=True)
        manifest = build_manifest(meta)
        self.assertIn("discovery", manifest["capabilities"])
        self.assertNotIn("latent_report.md", manifest["artifacts"])
        self.assertNotIn("interview_transcript.md", manifest["artifacts"])

    def test_discovery_enabled_with_flags_includes_artifacts(self):
        meta = self._make_enriched_meta(discovery_enabled=True)
        meta["discovery"]["report_generated"] = True
        meta["discovery"]["transcript_generated"] = True
        manifest = build_manifest(meta)
        self.assertIn("latent_report.md", manifest["artifacts"])
        self.assertIn("interview_transcript.md", manifest["artifacts"])
        self.assertIn("discovery", manifest["capabilities"])

    def test_discovery_disabled_base_artifacts_present(self):
        meta = self._make_enriched_meta(discovery_enabled=False)
        manifest = build_manifest(meta)
        self.assertIn("SKILL.md", manifest["artifacts"])
        self.assertIn("expertise.md", manifest["artifacts"])
        self.assertIn("expertise", manifest["capabilities"])


if __name__ == "__main__":
    unittest.main()
