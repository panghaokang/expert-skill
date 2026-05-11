# Enterprise Expert Skill (企业专家 Skill)

将企业领域专家的隐性知识（诊断直觉、设计启发、判断框架）凝练为可复用的 LLM Skill。

## 与 dot-skill 的区别

| 维度 | dot-skill | expert-skill |
|------|-----------|-------------|
| 蒸馏目标 | Persona（人格）+ Work Skill（工作能力） | 纯专业知识 |
| 关注点 | "这个人会怎么说话、怎么做事" | "这个领域应该怎么做判断" |
| 角色类型 | colleague / relationship / celebrity | troubleshooter / architect / reviewer / decision_maker / operator |
| 是否模拟人格 | 是，模仿语气和沟通风格 | 否，只提取专业方法论 |
| 产出 | SKILL.md（含 work + persona 两部分） | SKILL.md（纯专业知识，无 persona） |

## 专长类型

| 类型 | 典型产出 | 适用场景 |
|------|---------|---------|
| 诊断专家 (troubleshooter) | 故障模式库、诊断路径、嗅觉检查 | 故障排查、性能诊断 |
| 架构专家 (architect) | 设计原则、技术选型矩阵、反模式 | 系统设计、技术评审 |
| 审核专家 (reviewer) | 缺陷模式库、检查清单、风险等级 | Code Review、方案审查 |
| 决策专家 (decision_maker) | 决策框架、风险评估、优先级方法 | 技术决策、资源分配 |
| 运维专家 (operator) | 监控指标、SOP、升级规则 | 运维保障、应急响应 |

## 快速开始

### 创建一个专家 Skill

```
/expert-skill
```

然后按提示回答 3-4 个问题，提供原材料（消息记录/文档/邮件），系统自动生成。

### 命令行使用

```bash
# 列出所有已生成的专家
python3 tools/skill_writer.py --action list --base-dir ./skills/expert

# 列出所有专长类型
python3 tools/skill_writer.py --list-types

# 版本管理
python3 tools/version_manager.py --action backup --slug {slug}
python3 tools/version_manager.py --action rollback --slug {slug} --version v2
```

## 项目结构

```
expert-skill/
├── SKILL.md                          # 主入口
├── README.md
├── prompts/
│   ├── intake.md                     # 基础信息录入
│   ├── expertise_analyzer.md         # 通用专业知识分析
│   ├── expertise_builder.md          # 通用专业知识构建
│   └── expertise/                    # 专长类型专属 prompt
│       ├── troubleshooter/
│       ├── architect/
│       ├── reviewer/
│       ├── decision_maker/
│       └── operator/
├── tools/
│   ├── expertise_presets.py          # 专长类型注册表
│   ├── skill_schema.py               # 元数据 schema
│   ├── skill_writer.py               # 产物写入器
│   ├── version_manager.py            # 版本管理
│   ├── feishu_auto_collector.py      # 飞书自动采集
│   ├── feishu_parser.py              # 飞书消息解析
│   ├── feishu_browser.py             # 飞书浏览器方案
│   ├── feishu_mcp_client.py          # 飞书 MCP 方案
│   ├── dingtalk_auto_collector.py    # 钉钉自动采集
│   ├── email_parser.py               # 邮件解析
│   └── slack_auto_collector.py       # Slack 采集
└── skills/
    └── expert/                       # 生成的专家 Skill
        └── {slug}/
            ├── SKILL.md
            ├── expertise.md
            ├── knowledge_graph.md
            ├── heuristics.json
            ├── meta.json
            └── manifest.json
```
