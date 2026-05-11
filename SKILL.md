---
name: expert-skill
description: "企业专家知识蒸馏引擎——将领域专家的隐性知识（诊断直觉、设计启发、判断框架）凝练为可复用的 Expert Skill"
argument-hint: "[expert-name-or-slug]"
version: "1.0.0"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash
---

> **Language**: 本 Skill 支持中文和英文。根据用户第一条消息的语言全程使用同一语言回复。

> **Execution Root**: 所有 `Bash` 命令都在当前 `SKILL.md` 所在目录执行。`tools/...` 和 `prompts/...` 均为相对于 skill 根目录的相对路径。

---

# 企业专家 Skill 创建器

## 触发条件

当用户说以下内容时启动：
- `/expert-skill`
- "帮我创建一个专家 skill"
- "我想蒸馏一个专家的知识"
- "把 XX 的专业知识做成 skill"
- "做一个 XX 专家的 skill"

## 核心理念

本 Skill 不做人格模拟，只蒸馏**专业知识**。

蒸馏的是一个专家的：
- 判断框架：他遇到问题时怎么想、怎么看、怎么查
- 决策模式：他做技术决策时优先考虑什么、红线在哪里
- 经验规则：他踩过的坑、验证过的结论、可复用的启发式
- 知识结构：按专长类型组织的方法论和操作流程

不蒸馏的是：
- 他的性格、MBTI、星座、脾气
- 他的沟通风格、话术习惯
- 他的人际行为

**产出的 Skill 会说："基于 XX 专家的方法论，你应该先检查 Y"，而不是模仿某个人的语气说话。**

---

## 专长类型

企业专家的专业能力分为 5 种类型：

| 类型 | 标识 | 知识形态 | 典型产出 |
|------|------|---------|---------|
| 诊断专家 | `troubleshooter` | 决策树 | 故障模式库、诊断路径、嗅觉检查项 |
| 架构专家 | `architect` | 设计原则 | 设计哲学、技术选型矩阵、反模式清单 |
| 审核专家 | `reviewer` | 检查清单 | 缺陷模式库、Review 检查项、风险等级 |
| 决策专家 | `decision_maker` | 决策框架 | 评估维度、风险评估、优先级方法 |
| 运维专家 | `operator` | Runbook | 监控指标、SOP、升级规则 |

---

## 主流程

### Step 1: 基础信息录入

使用 `prompts/intake.md` 引导用户录入：

1. **专家称呼**（必填）
2. **基本信息**：公司、职级、职位、专业领域（一句话，可跳过）
3. **专长类型**：5 选 1（可跳过，默认"诊断专家"）
4. **专业描述**：他擅长什么、判断框架是什么、什么时候别人会想到他（2-3 句话，可选但推荐）

收集完后汇总确认。

### Step 2: 原材料导入

```
原材料怎么提供？

  [A] 飞书自动采集（推荐）
  [B] 钉钉自动采集
  [C] 飞书链接
  [D] 上传文件（PDF / 图片 / 飞书导出 JSON / 邮件 .eml）
  [E] 直接粘贴内容

可以混用，也可以跳过（仅凭手动信息生成）。
```

具体操作方式与 dot-skill 兼容：飞书采集、钉钉采集、文件解析等工具均可用。

#### 方式 A：飞书自动采集

```bash
# 首次配置
python3 tools/feishu_auto_collector.py --setup

# 群聊采集
python3 tools/feishu_auto_collector.py \
  --name "{name}" \
  --output-dir ./knowledge/{slug} \
  --msg-limit 1000 \
  --doc-limit 20

# 私聊采集（需 user_access_token + chat_id）
python3 tools/feishu_auto_collector.py \
  --open-id {open_id} \
  --p2p-chat-id {chat_id} \
  --user-token {user_access_token} \
  --name "{name}" \
  --output-dir ./knowledge/{slug} \
  --msg-limit 1000
```

#### 方式 B：钉钉自动采集

```bash
python3 tools/dingtalk_auto_collector.py \
  --name "{name}" \
  --output-dir ./knowledge/{slug} \
  --msg-limit 500 \
  --doc-limit 20
```

#### 方式 C：飞书链接

```bash
# 浏览器方案
python3 tools/feishu_browser.py --url "{url}" --target "{name}" --output /tmp/feishu_doc.txt

# MCP 方案
python3 tools/feishu_mcp_client.py --url "{url}" --output /tmp/feishu_doc.txt
```

#### 方式 D：上传文件

- PDF / 图片 → `Read` 工具直接读取
- 飞书消息 JSON 导出 → `python3 tools/feishu_parser.py --file {path} --target "{name}"`
- 邮件 .eml → `python3 tools/email_parser.py --file {path} --target "{name}"`

#### 方式 E：直接粘贴

用户粘贴的内容直接作为原材料。

如果用户跳过原材料，仅凭 Step 1 的手动信息生成。

### Step 3: 分析原材料

根据专长类型加载对应 prompt：

| 专长类型 | Intake | Analyzer | Builder |
|---------|--------|----------|---------|
| troubleshooter | `prompts/expertise/troubleshooter/intake.md` | `prompts/expertise/troubleshooter/analyzer.md` | `prompts/expertise/troubleshooter/builder.md` |
| architect | `prompts/expertise/architect/intake.md` | `prompts/expertise/architect/analyzer.md` | `prompts/expertise/architect/builder.md` |
| reviewer | `prompts/expertise/reviewer/intake.md` | `prompts/expertise/reviewer/analyzer.md` | `prompts/expertise/reviewer/builder.md` |
| decision_maker | `prompts/expertise/decision_maker/intake.md` | `prompts/expertise/decision_maker/analyzer.md` | `prompts/expertise/decision_maker/builder.md` |
| operator | `prompts/expertise/operator/intake.md` | `prompts/expertise/operator/analyzer.md` | `prompts/expertise/operator/builder.md` |

**分析流程：**

1. 读取专长类型对应的 intake.md，追问专业方法论、核心工具、经典案例
2. 使用通用的 `prompts/expertise_analyzer.md` 做初步提取
3. 使用专长类型对应的 analyzer.md 做类型专项提取
4. 整合两份分析结果，生成结构化的专业知识摘要

**分析摘要包含：**
- 专业领域与职责边界
- 判断框架与核心启发式
- 决策模式与技术红线
- 按专长类型组织的方法论结构
- 经验知识库

### Step 4: 生成并预览

使用 `prompts/expertise_builder.md` + 专长类型的 builder.md 生成专业知识内容。

向用户展示摘要（5-8 行）：

```
专家知识摘要：
  - 专长类型：{type}
  - 专业领域：{domain}
  - 核心判断框架：{key heuristics}
  - 技术红线：{red lines}
  - 经验规则数：{N} 条
  ...

确认生成？还是需要调整？
```

### Step 5: 写入文件

用户确认后：

1. 将专业知识内容写入 `/tmp/expert_{slug}_expertise.md`
2. 准备 meta.json 写入 `/tmp/expert_{slug}_meta.json`
3. 调用 writer：

```bash
python3 tools/skill_writer.py \
  --action create \
  --slug {slug} \
  --name "{name}" \
  --expertise-type {type} \
  --expertise-content /tmp/expert_{slug}_expertise.md \
  --meta /tmp/expert_{slug}_meta.json \
  --domain-summary "{domain_summary}" \
  --base-dir ./skills/expert
```

生成的文件结构：

```
skills/expert/{slug}/
  ├── SKILL.md             # 完整 Skill（可直接运行）
  ├── expertise.md          # 专业知识文档
  ├── knowledge_graph.md    # 知识图谱（结构化的知识关联）
  ├── heuristics.json       # 启发式规则（程序化使用）
  ├── meta.json             # 元数据
  ├── manifest.json         # 安装/分发清单
  └── versions/             # 历史版本
```

如需安装到 Claude Code：
```bash
python3 tools/skill_writer.py ... --install-claude-skill
```

---

## 进化模式：追加材料

用户提供新文件时：

1. 按 Step 2 方法读取新内容
2. 用 `Read` 读取现有 `skills/expert/{slug}/expertise.md`
3. 归档当前版本：
   ```bash
   python3 tools/version_manager.py --action backup --slug {slug} --base-dir ./skills/expert
   ```
4. 分析增量内容，合并到专业知识中
5. 写入更新后的 expertise.md 并重建 SKILL.md：
   ```bash
   python3 tools/skill_writer.py \
     --action update \
     --slug {slug} \
     --expertise-content /tmp/expert_{slug}_expertise_updated.md \
     --base-dir ./skills/expert
   ```

---

## 管理操作

列出所有专家 Skill：
```bash
python3 tools/skill_writer.py --action list --base-dir ./skills/expert
```

列出可用专长类型：
```bash
python3 tools/skill_writer.py --list-types
```

回滚版本：
```bash
python3 tools/version_manager.py --action rollback --slug {slug} --version v2 --base-dir ./skills/expert
```

删除专家 Skill：
```bash
rm -rf skills/expert/{slug}
```
