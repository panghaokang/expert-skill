#!/usr/bin/env python3
"""
Discovery schema helpers for the latent knowledge mining pipeline.

Defines data structures and validation for all discovery pipeline intermediates:
expert profiles, latent variable candidates, triplet question groups, and analysis outputs.
"""

from __future__ import annotations

from pathlib import Path


DISCOVERY_STATUSES = (
    "not_started",
    "profile_ready",
    "variables_ready",
    "triplets_ready",
    "interview_in_progress",
    "interview_completed",
    "analysis_ready",
    "merged",
    "aborted",
)

_VALID_SOURCE_TYPES = {"comparison_gap", "domain_disagreement", "silent_topic", "rule_boundary"}
_VALID_TESTABILITY = {"high", "medium", "low"}
_VALID_AWARENESS_STATES = {"explicit", "semi_latent", "deep_latent"}
_VALID_CONFIDENCE = {"high", "medium", "low"}


def build_expert_profile(
    name: str,
    title: str = "",
    domain: str = "",
    years_in_field: int | None = None,
    visible_knowledge: list[dict] | None = None,
    known_decisions: list[dict] | None = None,
    domain_context: dict | None = None,
    suspected_gaps: list[dict] | None = None,
) -> dict:
    """Build a prior knowledge profile for an expert.

    visible_knowledge items: {"rule": "...", "source": "..."}
    known_decisions items:   {"case": "...", "context": "...", "decision": "...", "source": "..."}
    suspected_gaps items:    {"gap": "...", "reason": "..."}
    """
    default_ctx: dict = {
        "key_challenges": [],
        "common_pitfalls": [],
        "methodology_clashes": [],
    }
    merged_ctx = {**default_ctx, **(domain_context or {})}
    return {
        "identity": {
            "name": name,
            "title": title,
            "domain": domain,
            "years_in_field": years_in_field,
        },
        "visible_knowledge": visible_knowledge or [],
        "known_decisions": known_decisions or [],
        "domain_context": merged_ctx,
        "suspected_gaps": suspected_gaps or [],
    }


def build_latent_variable(
    id: str,
    label: str,
    source_type: str,  # "comparison_gap" | "domain_disagreement" | "silent_topic" | "rule_boundary"
    evidence_from_profile: str,
    hypothesized_variable: dict,  # {"name": "...", "description": "...", "why_latent": "..."}
    testability: str,  # "high" | "medium" | "low"
    priority: int = 0,
) -> dict:
    """Build a latent variable candidate entry."""
    return {
        "id": id,
        "label": label,
        "source_type": source_type,
        "evidence_from_profile": evidence_from_profile,
        "hypothesized_variable": hypothesized_variable,
        "testability": testability,
        "priority": priority,
    }


def build_triplet_group(
    target_variable: str,
    domain_context: str,
    question_a: dict,
    question_b: dict,
    question_c: dict,
    control_notes: str = "",
) -> dict:
    """Build a triplet question group targeting a latent variable.

    Each question dict follows the structure:
      {
        "text": "...",
        "variable_changed": "...",   # question_b/c only
        "conflict_added": "...",     # question_c only
        "probes": {
          "primary": "...",
          "followups": ["..."],
          "signal_triggers": {
            "noticed": "...", "hesitated": "...", "boundary_invented": "...",
            "contradiction": "...", "pushback": "...",
          },
        },
        "expected_reveals": {
          "visible_rule": "...",
          "latent_variable": "...",
          "priority_signal": "...",
        },
      }
    """
    return {
        "target_variable": target_variable,
        "domain_context": domain_context,
        "question_A": question_a,
        "question_B": question_b,
        "question_C": question_c,
        "control_notes": control_notes,
    }


def build_triplet_analysis(
    triplet_id: str,
    baseline_rule: str,
    awareness_state: str,  # "explicit" | "semi_latent" | "deep_latent"
    priority_topology: dict,
    latent_findings: list[dict],
    confidence: str,  # "high" | "medium" | "low"
    invalidated_candidates: list[str] | None = None,
    evidence: dict | None = None,  # {"triplet_id", "layer", "expert_quote", "confidence_reason"}
) -> dict:
    """Build a triplet analysis result."""
    return {
        "triplet_id": triplet_id,
        "baseline_rule": baseline_rule,
        "awareness_state": awareness_state,
        "priority_topology": priority_topology,
        "latent_findings": latent_findings,
        "confidence": confidence,
        "invalidated_candidates": invalidated_candidates or [],
        "evidence": evidence or {},
    }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_expert_profile(profile: dict) -> list[str]:
    """Validate an expert profile dict. Returns a list of error strings (empty = valid)."""
    errors: list[str] = []
    identity = profile.get("identity", {})
    if not isinstance(identity, dict) or not identity.get("name"):
        errors.append("identity.name is required")
    for field in ("visible_knowledge", "known_decisions", "suspected_gaps"):
        if field not in profile:
            errors.append(f"{field} is required")
        elif not isinstance(profile[field], list):
            errors.append(f"{field} must be a list")
    if "domain_context" not in profile:
        errors.append("domain_context is required")
    else:
        ctx = profile["domain_context"]
        if not isinstance(ctx, dict):
            errors.append("domain_context must be a dict")
        else:
            for key in ("key_challenges", "common_pitfalls", "methodology_clashes"):
                if key not in ctx:
                    errors.append(f"domain_context.{key} is required")
    return errors


def validate_latent_variable(var: dict) -> list[str]:
    """Validate a latent variable candidate. Returns a list of error strings."""
    errors: list[str] = []
    for field in ("id", "label", "source_type", "evidence_from_profile", "hypothesized_variable", "testability"):
        if not var.get(field):
            errors.append(f"{field} is required")
    source_type = var.get("source_type", "")
    if source_type and source_type not in _VALID_SOURCE_TYPES:
        errors.append(f"source_type must be one of {sorted(_VALID_SOURCE_TYPES)}, got '{source_type}'")
    testability = var.get("testability", "")
    if testability and testability not in _VALID_TESTABILITY:
        errors.append(f"testability must be one of {sorted(_VALID_TESTABILITY)}, got '{testability}'")
    hyp = var.get("hypothesized_variable")
    if isinstance(hyp, dict):
        for key in ("name", "description", "why_latent"):
            if not hyp.get(key):
                errors.append(f"hypothesized_variable.{key} is required")
    elif hyp is not None:
        errors.append("hypothesized_variable must be a dict")
    return errors


def _validate_probes(probes: dict, question_label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(probes, dict):
        errors.append(f"{question_label}.probes must be a dict")
        return errors
    if not probes.get("primary"):
        errors.append(f"{question_label}.probes.primary is required")
    if "followups" not in probes:
        errors.append(f"{question_label}.probes.followups is required")
    triggers = probes.get("signal_triggers", {})
    if not isinstance(triggers, dict):
        errors.append(f"{question_label}.probes.signal_triggers must be a dict")
    return errors


def _validate_expected_reveals(reveals: dict, question_label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(reveals, dict):
        errors.append(f"{question_label}.expected_reveals must be a dict")
        return errors
    for key in ("visible_rule", "latent_variable", "priority_signal"):
        if key not in reveals:
            errors.append(f"{question_label}.expected_reveals.{key} is required")
    return errors


def validate_triplet_group(triplet: dict) -> list[str]:
    """Validate a triplet group. Returns a list of error strings."""
    errors: list[str] = []
    if not triplet.get("target_variable"):
        errors.append("target_variable is required")
    if not triplet.get("domain_context"):
        errors.append("domain_context is required")
    for q_key in ("question_A", "question_B", "question_C"):
        q = triplet.get(q_key, {})
        if not isinstance(q, dict):
            errors.append(f"{q_key} must be a dict")
            continue
        if not q.get("text"):
            errors.append(f"{q_key}.text is required")
        if "probes" not in q:
            errors.append(f"{q_key}.probes is required")
        else:
            errors.extend(_validate_probes(q["probes"], q_key))
        if "expected_reveals" not in q:
            errors.append(f"{q_key}.expected_reveals is required")
        else:
            errors.extend(_validate_expected_reveals(q["expected_reveals"], q_key))
    return errors


def validate_latent_variables_pool(variables: list[dict]) -> list[str]:
    """Validate the full pool of latent variable candidates.

    Checks: count 5-12, at least 3 with high or medium testability.
    """
    errors: list[str] = []
    count = len(variables)
    if count < 5:
        errors.append(f"Pool must have at least 5 variables, got {count}")
    elif count > 12:
        errors.append(f"Pool must have at most 12 variables, got {count}")
    high_medium = sum(1 for v in variables if v.get("testability") in ("high", "medium"))
    if high_medium < 3:
        errors.append(
            f"At least 3 variables must have high or medium testability, got {high_medium}"
        )
    return errors


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_discovery_dir(base_dir: str, slug: str) -> Path:
    """Return the discovery intermediates directory: {base_dir}/{slug}/discovery/"""
    return Path(base_dir) / slug / "discovery"


def get_discovery_file_path(base_dir: str, slug: str, filename: str) -> Path:
    """Return the full path to a specific discovery intermediate file."""
    return get_discovery_dir(base_dir, slug) / filename
