#!/usr/bin/env python3
"""
Expert skill artifact writer.

Writes expert knowledge artifacts for the enterprise-expert-skill engine.
Produces: SKILL.md, expertise.md, knowledge_graph.md, heuristics.json, manifest.json, meta.json
"""

from __future__ import annotations

import argparse
import json
import os
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
) -> str:
    """Write all artifacts for an expert skill. Returns the output directory path."""
    if meta is None:
        meta = create_meta(slug, name, expertise_type, profile, knowledge_sources)

    meta = enrich_expert_meta(meta, slug, expertise_type)
    preset = get_expertise_preset(expertise_type)
    artifacts = meta["artifacts"]

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

    # knowledge_graph.md (placeholder for structured knowledge graph)
    kg_header = f"# {name} — 知识图谱\n\n## 专长类型: {preset['display_name']}\n\n"
    (skill_dir / "knowledge_graph.md").write_text(kg_header, encoding="utf-8")

    # heuristics.json (structured heuristics for programmatic use)
    heuristics = {
        "expert": name,
        "expertise_type": expertise_type,
        "knowledge_format": preset["knowledge_format"],
        "execution_model": preset["execution_model"],
        "sections": preset["knowledge_sections"],
        "rules": [],
    }
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

    return str(skill_dir)


def update_expert_skill(
    base_dir: str,
    slug: str,
    expertise_content: str | None = None,
    domain_summary: str | None = None,
    knowledge_sources: list | None = None,
) -> str:
    """Update an existing expert skill. Returns the output directory path."""
    skill_dir = Path(base_dir) / slug
    if not skill_dir.is_dir():
        raise FileNotFoundError(f"Skill directory not found: {skill_dir}")

    meta_path = skill_dir / "meta.json"
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
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if expertise_content is not None:
        (skill_dir / "expertise.md").write_text(expertise_content, encoding="utf-8")
        # Rebuild SKILL.md
        name = meta.get("display_name", slug)
        identity = build_identity_string(meta)
        artifacts = meta["artifacts"]
        description = meta.get("summary", name)
        skill_md = SKILL_MD_TEMPLATE_ZH.format(
            combined_name=artifacts["combined_name"],
            description=description,
            display_name=name,
            identity=f"你是 {name}，{identity}。",
            domain_summary=domain_summary or "（待补充）",
            expertise_content=expertise_content,
        )
        (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

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

    if args.action == "create":
        out_dir = write_expert_skill(
            base_dir=args.base_dir,
            slug=args.slug,
            name=args.name or args.slug,
            expertise_type=args.expertise_type,
            expertise_content=expertise_content,
            domain_summary=args.domain_summary,
            meta=meta,
        )
        print(f"Expert skill created at: {out_dir}")

    elif args.action == "update":
        out_dir = update_expert_skill(
            base_dir=args.base_dir,
            slug=args.slug,
            expertise_content=expertise_content or None,
            domain_summary=args.domain_summary or None,
        )
        print(f"Expert skill updated at: {out_dir}")


if __name__ == "__main__":
    main()
