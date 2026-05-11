#!/usr/bin/env python3
"""
Expertise preset registry for the enterprise-expert-skill engine.

Defines expertise types as the primary abstraction dimension.
Each expertise type has its own intake questions, knowledge format,
and execution model — orthogonal to who the expert is.
"""

from __future__ import annotations


EXPERTISE_PRESETS = {
    "troubleshooter": {
        "name": "troubleshooter",
        "display_name": "Troubleshooter",
        "identity_label": "诊断专家",
        "description": "擅长故障诊断与排查，能从现象快速定位根因",
        "knowledge_format": "decision_tree",
        "execution_model": "diagnostic",
        "prompt_bundle": {
            "preset": "expert.troubleshooter.v1",
            "intake": "prompts/expertise/troubleshooter/intake.md",
            "analyzer": "prompts/expertise/troubleshooter/analyzer.md",
            "builder": "prompts/expertise/troubleshooter/builder.md",
        },
        "intake_questions": [
            "你主要负责排查哪些类型的系统/问题？",
            "遇到陌生故障时，你的第一步通常是什么？",
            "你有哪些'一上来就查'的固定检查项？",
        ],
        "knowledge_sections": [
            "常见故障模式",
            "诊断决策链",
            "嗅觉检查项 (smell tests)",
            "工具与命令",
            "经验教训",
        ],
        "storage_root": "skills/expert",
        "skill_name_prefix": "expert",
    },
    "architect": {
        "name": "architect",
        "display_name": "Architect",
        "identity_label": "架构专家",
        "description": "擅长系统设计与技术选型，能从全局视角做出架构决策",
        "knowledge_format": "design_principles",
        "execution_model": "evaluative",
        "prompt_bundle": {
            "preset": "expert.architect.v1",
            "intake": "prompts/expertise/architect/intake.md",
            "analyzer": "prompts/expertise/architect/analyzer.md",
            "builder": "prompts/expertise/architect/builder.md",
        },
        "intake_questions": [
            "你主要设计哪些类型的系统？",
            "做技术选型时你最优先考虑什么？",
            "你有哪些'绝对不能这样设计'的红线？",
        ],
        "knowledge_sections": [
            "设计原则",
            "技术选型矩阵",
            "反模式与红线",
            "架构决策记录 (ADR)",
            "经验教训",
        ],
        "storage_root": "skills/expert",
        "skill_name_prefix": "expert",
    },
    "reviewer": {
        "name": "reviewer",
        "display_name": "Reviewer",
        "identity_label": "审核专家",
        "description": "擅长代码/方案审查，能快速发现缺陷与风险点",
        "knowledge_format": "checklist",
        "execution_model": "evaluative",
        "prompt_bundle": {
            "preset": "expert.reviewer.v1",
            "intake": "prompts/expertise/reviewer/intake.md",
            "analyzer": "prompts/expertise/reviewer/analyzer.md",
            "builder": "prompts/expertise/reviewer/builder.md",
        },
        "intake_questions": [
            "你主要 Review 哪些类型的内容（代码/方案/架构）？",
            "Review 时你最关注什么？",
            "你有哪些'一看到就会 block'的模式？",
        ],
        "knowledge_sections": [
            "缺陷模式库",
            "Review 检查清单",
            "风险等级判定",
            "常见争议与处理方式",
            "经验教训",
        ],
        "storage_root": "skills/expert",
        "skill_name_prefix": "expert",
    },
    "decision_maker": {
        "name": "decision_maker",
        "display_name": "Decision Maker",
        "identity_label": "决策专家",
        "description": "擅长在不确定条件下做权衡与优先级判断",
        "knowledge_format": "decision_framework",
        "execution_model": "evaluative",
        "prompt_bundle": {
            "preset": "expert.decision_maker.v1",
            "intake": "prompts/expertise/decision_maker/intake.md",
            "analyzer": "prompts/expertise/decision_maker/analyzer.md",
            "builder": "prompts/expertise/decision_maker/builder.md",
        },
        "intake_questions": [
            "你主要做哪些类型的决策？",
            "做决策时你的核心判断框架是什么？",
            "什么情况下你会推迟决策或向上求助？",
        ],
        "knowledge_sections": [
            "决策框架",
            "风险评估矩阵",
            "优先级排序方法",
            "历史决策与复盘",
            "经验教训",
        ],
        "storage_root": "skills/expert",
        "skill_name_prefix": "expert",
    },
    "operator": {
        "name": "operator",
        "display_name": "Operator",
        "identity_label": "运维专家",
        "description": "擅长系统运维与稳定性保障，掌握大量操作经验与监控阈值",
        "knowledge_format": "runbook",
        "execution_model": "procedural",
        "prompt_bundle": {
            "preset": "expert.operator.v1",
            "intake": "prompts/expertise/operator/intake.md",
            "analyzer": "prompts/expertise/operator/analyzer.md",
            "builder": "prompts/expertise/operator/builder.md",
        },
        "intake_questions": [
            "你负责运维哪些系统？",
            "日常巡检你最关注什么指标？",
            "紧急情况下你的标准操作流程是什么？",
        ],
        "knowledge_sections": [
            "监控指标与阈值",
            "标准操作流程 (SOP)",
            "升级规则",
            "常见事故处理",
            "经验教训",
        ],
        "storage_root": "skills/expert",
        "skill_name_prefix": "expert",
    },
}


def get_expertise_preset(name: str) -> dict:
    """Return the preset dict for a given expertise type."""
    key = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key in EXPERTISE_PRESETS:
        return dict(EXPERTISE_PRESETS[key])
    # Fuzzy match
    for preset_key, preset in EXPERTISE_PRESETS.items():
        if preset_key in key or key in preset_key:
            return dict(preset)
        if preset["display_name"].lower() == key:
            return dict(preset)
    raise KeyError(
        f"Unknown expertise type '{name}'. "
        f"Available: {list(EXPERTISE_PRESETS.keys())}"
    )


def normalize_expertise_type(raw: str | None) -> str:
    """Normalize an expertise type string to a canonical preset key."""
    if not raw:
        return "troubleshooter"
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    if key in EXPERTISE_PRESETS:
        return key
    for preset_key, preset in EXPERTISE_PRESETS.items():
        if preset_key in key or key in preset_key:
            return preset_key
        if preset["display_name"].lower() == key:
            return preset_key
    return "troubleshooter"


def list_expertise_types() -> list[dict]:
    """Return a summary list of all available expertise types."""
    return [
        {
            "name": p["name"],
            "display_name": p["display_name"],
            "description": p["description"],
            "knowledge_format": p["knowledge_format"],
        }
        for p in EXPERTISE_PRESETS.values()
    ]
