#!/usr/bin/env python3
"""
Expert skill artifact writer.

Writes expert knowledge artifacts for the enterprise-expert-skill engine.
Produces: SKILL.md, expertise.md, knowledge_graph.md, heuristics.json, manifest.json, meta.json

P7 additions: --latent-report, --interview-transcript, --discovery-meta support.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from expertise_presets import get_expertise_preset, normalize_expertise_type, list_expertise_types
from skill_schema import (
    PRIMARY_ARTIFACTS,
    SCHEMA_VERSION,
    build_artifact_names,
    build_identity_string,
    build_manifest,
    enrich_expert_meta,
    now_iso,
)


SKILL_MD_TEMPLATE_ZH = """\
---
name: {combined_name}
description: {description}
user-invocable: true
---

# {display_name}

{identity}

---

## 专长领域

{domain_summary}

---

## 专业知识

{expertise_content}

---

## 执行规则

当收到相关领域的问题或任务时：

1. **识别问题类型**：判断问题属于诊断/设计/审查/决策/操作的哪一类
2. **应用专家框架**：按照 {display_name} 的专业方法论进行分析
3. **给出可执行输出**：提供具体的诊断步骤、设计方案、审查意见或决策建议
4. **诚实边界**：如果问题超出专业范围，明确说明"这不在我的专业领域内"

本 Skill 基于真实企业专家的知识蒸馏生成。
"""

_LATENT_SECTION_HEADER = "## 隐性知识增强"
_VARIABLE_TYPES = {"变量", "variable", "latent_variable"}


# ---------------------------------------------------------------------------
# P7 helper functions (independently testable)
# ---------------------------------------------------------------------------

def extract_latent_fields(discovery_meta: dict) -> dict:
    """Extract latent_variables, priority_rules, boundary_conditions from P6 analysis.

    latent_variables: de-duplicated by content; accepts type 变量/variable/latent_variable.
    priority_rules: from cross_analysis.priority_topology (raw list).
    boundary_conditions: from cross_analysis.boundary_map (raw list).
    """
    seen_contents: set[str] = set()
    latent_variables: list[dict] = []
    for a in discovery_meta.get("triplet_analyses", []):
        for f in a.get("latent_findings", []):
            if f.get("type", "").lower() in _VARIABLE_TYPES:
                content = f.get("content", "")
                if content and content not in seen_contents:
                    seen_contents.add(content)
                    latent_variables.append(f)
    cross = discovery_meta.get("cross_analysis", {})
    return {
        "latent_variables": latent_variables,
        "priority_rules": cross.get("priority_topology", []),
        "boundary_conditions": cross.get("boundary_map", []),
    }


def generate_knowledge_graph_md(
    name: str, preset: dict, discovery_meta: dict | None
) -> str:
    """Generate knowledge_graph.md content.

    With discovery_meta: includes latent variable nodes, rule conflict, boundary tables.
    Without discovery_meta: returns the existing header placeholder.
    """
    header = (
        f"# {name} — 知识图谱\n\n"
        f"## 专长类型: {preset['display_name']}\n\n"
    )
    if discovery_meta is None:
        return header

    fields = extract_latent_fields(discovery_meta)
    lines: list[str] = [header.rstrip()]

    # Latent variable nodes
    lines += [
        "",
        "## 隐性变量节点",
        "",
        "| 变量 | 置信度 | 来源三联体 |",
        "|------|--------|-----------|",
    ]
    for v in fields["latent_variables"]:
        content = v.get("content", "")
        conf = v.get("confidence", "")
        tid = v.get("evidence", {}).get("triplet_id", "")
        lines.append(f"| {content} | {conf} | {tid} |")

    # Rule conflict topology
    lines += [
        "",
        "## 规则冲突关系",
        "",
        "| 优先规则 | 从属规则 | 触发条件 |",
        "|---------|---------|---------|",
    ]
    for pt in fields["priority_rules"]:
        if isinstance(pt, dict):
            winner = pt.get("winner", "")
            loser = pt.get("loser", "")
            cond = pt.get("condition", "")
            lines.append(f"| {winner} | {loser} | {cond} |")
        elif isinstance(pt, str):
            lines.append(f"| {pt} | | |")

    # Boundary conditions
    lines += [
        "",
        "## 边界条件",
        "",
        "| 边界内容 | 适用域 | 失效域 |",
        "|---------|-------|-------|",
    ]
    for bc in fields["boundary_conditions"]:
        if isinstance(bc, dict):
            boundary = bc.get("boundary", bc.get("content", ""))
            applicable = bc.get("applicable_domain", "")
            failure = bc.get("failure_domain", "")
            lines.append(f"| {boundary} | {applicable} | {failure} |")
        elif isinstance(bc, str):
            lines.append(f"| {bc} | | |")

    lines.append("")
    return "\n".join(lines)


def generate_latent_expertise_section(discovery_meta: dict) -> str:
    """Generate the '## 隐性知识增强' section to append to expertise_content."""
    fields = extract_latent_fields(discovery_meta)
    lines: list[str] = ["", _LATENT_SECTION_HEADER, ""]

    if fields["latent_variables"]:
        lines.append("### 隐性变量")
        for v in fields["latent_variables"]:
            conf = v.get("confidence", "")
            content = v.get("content", "")
            lines.append(f"- **[{conf}]** {content}")
        lines.append("")

    if fields["priority_rules"]:
        lines.append("### 优先级规则")
        for pt in fields["priority_rules"]:
            if isinstance(pt, dict):
                winner = pt.get("winner", "")
                loser = pt.get("loser", "")
                cond = pt.get("condition", "")
                lines.append(f"- {winner} 优先于 {loser}（条件：{cond}）")
            elif isinstance(pt, str):
                lines.append(f"- {pt}")
        lines.append("")

    if fields["boundary_conditions"]:
        lines.append("### 边界条件")
        for bc in fields["boundary_conditions"]:
            if isinstance(bc, dict):
                boundary = bc.get("boundary", bc.get("content", ""))
                applicable = bc.get("applicable_domain", "")
                failure = bc.get("failure_domain", "")
                entry = f"- {boundary}"
                if applicable:
                    entry += f"  适用条件：{applicable}"
                if failure:
                    entry += f" / 失效条件：{failure}"
                lines.append(entry)
            elif isinstance(bc, str):
                lines.append(f"- {bc}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers shared by create and update paths
# ---------------------------------------------------------------------------

def _apply_latent_section(expertise_content: str, discovery_meta: dict | None) -> str:
    """Append the latent expertise section to expertise_content if not already present."""
    if discovery_meta is None:
        return expertise_content
    if _LATENT_SECTION_HEADER in expertise_content:
        return expertise_content
    return expertise_content + generate_latent_expertise_section(discovery_meta)


def _apply_discovery_meta_fields(
    meta: dict,
    latent_report: str | None,
    interview_transcript: str | None,
    discovery_meta: dict | None,
) -> None:
    """Update meta.discovery in-place based on provided discovery parameters."""
    if latent_report is None and interview_transcript is None and discovery_meta is None:
        return
    d = meta.setdefault("discovery", {})
    d["enabled"] = True
    if latent_report is not None:
        d["report_generated"] = True
    if interview_transcript is not None:
        d["transcript_generated"] = True
    if discovery_meta is not None:
        d["analysis_completed"] = True


def _write_latent_artifacts(
    skill_dir: Path,
    latent_report: str | None,
    interview_transcript: str | None,
) -> None:
    if latent_report is not None:
        (skill_dir / "latent_report.md").write_text(latent_report, encoding="utf-8")
    if interview_transcript is not None:
        (skill_dir / "interview_transcript.md").write_text(interview_transcript, encoding="utf-8")


def _update_heuristics_with_latent(skill_dir: Path, heuristics: dict, discovery_meta: dict) -> None:
    """Enrich heuristics dict with latent fields and write to disk."""
    fields = extract_latent_fields(discovery_meta)
    heuristics["latent_variables"] = fields["latent_variables"]
    heuristics["priority_rules"] = fields["priority_rules"]
    heuristics["boundary_conditions"] = fields["boundary_conditions"]
    (skill_dir / "heuristics.json").write_text(
        json.dumps(heuristics, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def create_meta(slug: str, name: str, expertise_type: str,
                profile: dict | None = None,
                knowledge_sources: list | None = None) -> dict:
    """Build a minimal meta.json payload for the expert skill."""
    return {
        "name": name,
        "slug": slug,
        "expertise_type": expertise_type,
        "profile": profile or {},
        "knowledge_sources": knowledge_sources or [],
    }


def write_expert_skill(
    base_dir: str,
    slug: str,
    name: str,
    expertise_type: str,
    expertise_content: str,
    domain_summary: str = "",
    meta: dict | None = None,
    profile: dict | None = None,
    knowledge_sources: list | None = None,
    latent_report: str | None = None,
    interview_transcript: str | None = None,
    discovery_meta: dict | None = None,
) -> str:
    """Write all artifacts for an expert skill. Returns the output directory path."""
    if meta is None:
        meta = create_meta(slug, name, expertise_type, profile, knowledge_sources)

    meta = enrich_expert_meta(meta, slug, expertise_type)
    preset = get_expertise_preset(expertise_type)
    artifacts = meta["artifacts"]

    # Apply latent section to expertise_content before writing any file
    expertise_content = _apply_latent_section(expertise_content, discovery_meta)

    # Update meta discovery fields
    _apply_discovery_meta_fields(meta, latent_report, interview_transcript, discovery_meta)

    skill_dir = Path(base_dir) / slug
    skill_dir.mkdir(parents=True, exist_ok=True)

    # SKILL.md
    description = meta.get("summary", f"{name} — {preset['identity_label']}")
    identity = build_identity_string(meta)
    skill_md = SKILL_MD_TEMPLATE_ZH.format(
        combined_name=artifacts["combined_name"],
        description=description,
        display_name=name,
        identity=f"你是 {name}，{identity}。",
        domain_summary=domain_summary or "（待补充）",
        expertise_content=expertise_content,
    )
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    # expertise.md (pure knowledge, no identity wrapper)
    (skill_dir / "expertise.md").write_text(expertise_content, encoding="utf-8")

    # knowledge_graph.md
    kg_content = generate_knowledge_graph_md(name, preset, discovery_meta)
    (skill_dir / "knowledge_graph.md").write_text(kg_content, encoding="utf-8")

    # heuristics.json
    heuristics: dict = {
        "expert": name,
        "expertise_type": expertise_type,
        "knowledge_format": preset["knowledge_format"],
        "execution_model": preset["execution_model"],
        "sections": preset["knowledge_sections"],
        "rules": [],
    }
    if discovery_meta is not None:
        _update_heuristics_with_latent(skill_dir, heuristics, discovery_meta)
    else:
        (skill_dir / "heuristics.json").write_text(
            json.dumps(heuristics, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # meta.json
    (skill_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # manifest.json
    manifest = build_manifest(meta)
    (skill_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Optional discovery artifacts
    _write_latent_artifacts(skill_dir, latent_report, interview_transcript)

    return str(skill_dir)


def update_expert_skill(
    base_dir: str,
    slug: str,
    expertise_content: str | None = None,
    domain_summary: str | None = None,
    knowledge_sources: list | None = None,
    latent_report: str | None = None,
    interview_transcript: str | None = None,
    discovery_meta: dict | None = None,
) -> str:
    """Update an existing expert skill. Returns the output directory path."""
    skill_dir = Path(base_dir) / slug
    if not skill_dir.is_dir():
        raise FileNotFoundError(f"Skill directory not found: {skill_dir}")

    meta_path = skill_dir / "meta.json"
    meta: dict = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        lifecycle = meta.setdefault("lifecycle", {})
        lifecycle["updated_at"] = now_iso()
        current_v = lifecycle.get("version", "v1")
        if current_v.startswith("v"):
            try:
                num = int(current_v[1:]) + 1
                lifecycle["version"] = f"v{num}"
            except ValueError:
                lifecycle["version"] = "v2"
        if knowledge_sources:
            existing = set(meta.get("knowledge_sources", []))
            existing.update(knowledge_sources)
            meta["knowledge_sources"] = list(existing)
            meta["generation"]["created_from"] = meta["knowledge_sources"]

    # Apply discovery meta fields to meta
    _apply_discovery_meta_fields(meta, latent_report, interview_transcript, discovery_meta)

    # Determine if we need to rewrite content files
    need_rewrite_content = (expertise_content is not None) or (discovery_meta is not None)

    if need_rewrite_content:
        effective_content = expertise_content
        if effective_content is None:
            existing_path = skill_dir / "expertise.md"
            effective_content = (
                existing_path.read_text(encoding="utf-8") if existing_path.exists() else ""
            )

        # Apply latent section (shared helper — same logic as create path)
        effective_content = _apply_latent_section(effective_content, discovery_meta)

        # Write expertise.md
        (skill_dir / "expertise.md").write_text(effective_content, encoding="utf-8")

        # Rebuild SKILL.md
        name = meta.get("display_name", slug)
        identity = build_identity_string(meta)
        artifacts = meta.get("artifacts", {})
        description = meta.get("summary", name)
        skill_md = SKILL_MD_TEMPLATE_ZH.format(
            combined_name=artifacts.get("combined_name", slug),
            description=description,
            display_name=name,
            identity=f"你是 {name}，{identity}。",
            domain_summary=domain_summary or "（待补充）",
            expertise_content=effective_content,
        )
        (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    # Write meta.json
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Optional discovery artifacts
    _write_latent_artifacts(skill_dir, latent_report, interview_transcript)

    # Update heuristics.json and knowledge_graph.md if discovery_meta provided
    if discovery_meta is not None:
        heuristics_path = skill_dir / "heuristics.json"
        try:
            heuristics = json.loads(heuristics_path.read_text(encoding="utf-8")) if heuristics_path.exists() else {}
        except (json.JSONDecodeError, OSError):
            heuristics = {}
        _update_heuristics_with_latent(skill_dir, heuristics, discovery_meta)

        name = meta.get("display_name", slug)
        expertise_type = meta.get("expertise_type", "troubleshooter")
        preset = get_expertise_preset(expertise_type)
        kg_content = generate_knowledge_graph_md(name, preset, discovery_meta)
        (skill_dir / "knowledge_graph.md").write_text(kg_content, encoding="utf-8")

    # Rebuild manifest if any discovery params were provided
    if latent_report is not None or interview_transcript is not None or discovery_meta is not None:
        if "artifacts" not in meta:
            meta["artifacts"] = build_artifact_names(meta)
        manifest = build_manifest(meta)
        (skill_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return str(skill_dir)


def list_experts(base_dir: str) -> list[dict]:
    """List all generated expert skills."""
    base = Path(base_dir)
    if not base.is_dir():
        return []
    result = []
    for skill_dir in sorted(base.iterdir()):
        if not skill_dir.is_dir():
            continue
        meta_path = skill_dir / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            result.append({
                "slug": skill_dir.name,
                "name": meta.get("display_name", skill_dir.name),
                "expertise_type": meta.get("expertise_type", ""),
                "created_at": meta.get("lifecycle", {}).get("created_at", ""),
                "updated_at": meta.get("lifecycle", {}).get("updated_at", ""),
                "version": meta.get("lifecycle", {}).get("version", "v1"),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return result


def main():
    parser = argparse.ArgumentParser(description="Enterprise Expert Skill Writer")
    parser.add_argument("--action", choices=["create", "update", "list"])
    parser.add_argument("--slug", help="Skill slug (e.g. zhang-san)")
    parser.add_argument("--name", help="Expert display name")
    parser.add_argument("--expertise-type", default="troubleshooter",
                        help="Expertise type preset")
    parser.add_argument("--expertise-content", help="Path to expertise.md content file")
    parser.add_argument("--domain-summary", default="", help="Domain summary text")
    parser.add_argument("--meta", help="Path to meta.json file")
    parser.add_argument("--base-dir", default="./skills/expert",
                        help="Output base directory")
    parser.add_argument("--list-types", action="store_true",
                        help="List available expertise types and exit")
    # P7 additions
    parser.add_argument("--latent-report", default="",
                        help="Path to latent_report.md to embed in skill directory")
    parser.add_argument("--interview-transcript", default="",
                        help="Path to interview_transcript.md to embed in skill directory")
    parser.add_argument("--discovery-meta", default="",
                        help="Path to interview_analysis.json for heuristics/knowledge_graph enrichment")
    args = parser.parse_args()

    if args.list_types:
        print(json.dumps(list_expertise_types(), ensure_ascii=False, indent=2))
        return

    if not args.action:
        parser.error("--action is required (create, update, list)")

    if args.action == "list":
        experts = list_experts(args.base_dir)
        if experts:
            for e in experts:
                print(f"  [{e['expertise_type']}] {e['name']} (slug: {e['slug']}, {e['version']})")
        else:
            print("  (no experts found)")
        return

    if not args.slug:
        parser.error("--slug is required")

    expertise_content = ""
    if args.expertise_content:
        expertise_content = Path(args.expertise_content).read_text(encoding="utf-8")

    meta = None
    if args.meta:
        meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))

    # Read P7 inputs
    latent_report: str | None = None
    if args.latent_report:
        latent_report = Path(args.latent_report).read_text(encoding="utf-8")

    interview_transcript: str | None = None
    if args.interview_transcript:
        interview_transcript = Path(args.interview_transcript).read_text(encoding="utf-8")

    discovery_meta: dict | None = None
    if args.discovery_meta:
        discovery_meta = json.loads(Path(args.discovery_meta).read_text(encoding="utf-8"))

    if args.action == "create":
        out_dir = write_expert_skill(
            base_dir=args.base_dir,
            slug=args.slug,
            name=args.name or args.slug,
            expertise_type=args.expertise_type,
            expertise_content=expertise_content,
            domain_summary=args.domain_summary,
            meta=meta,
            latent_report=latent_report,
            interview_transcript=interview_transcript,
            discovery_meta=discovery_meta,
        )
        print(f"Expert skill created at: {out_dir}")

    elif args.action == "update":
        out_dir = update_expert_skill(
            base_dir=args.base_dir,
            slug=args.slug,
            expertise_content=expertise_content or None,
            domain_summary=args.domain_summary or None,
            latent_report=latent_report,
            interview_transcript=interview_transcript,
            discovery_meta=discovery_meta,
        )
        print(f"Expert skill updated at: {out_dir}")


if __name__ == "__main__":
    main()
