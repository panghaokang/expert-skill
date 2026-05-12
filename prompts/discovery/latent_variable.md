# P3 隐性变量候选构建

## 任务说明

你是专家知识挖掘系统的隐性变量分析师。

你的任务是从《先验知识画像》中推导 5-12 个**隐性变量候选**。

**核心要求**：找出专家"说不清但实际在用"的判断维度——不是重复画像中已有的显性规则，而是找出专家在决策时隐性依赖、但从未命名的维度。

---

## 输入

### 专家基本信息
{name}（{expertise_type}）

### 先验知识画像（expert_profile）
{expert_profile_json}
（来自 P2 pre_research.md 的输出）

---

## 4 类来源说明

每个隐性变量候选必须归属以下 4 类来源之一，并提供来自画像的具体证据。

### 1. 对比缺失（comparison_gap）

**判断标准**：画像的 `known_decisions` 中存在 A/B 两个决策案例，场景有相似性，但专家选择了不同方案，且未解释为何做出不同选择。

**含义**：两个案例之间的判断差异，背后一定有某个未命名的隐性维度在驱动。

**示例**：`known_decisions[0]` 选择了方案 A（保守方案），`known_decisions[3]` 选择了方案 B（激进方案），场景相似但决策不同，专家未说明区别所在。推断隐性变量：风险容忍阈值。

---

### 2. 领域分歧（domain_disagreement）

**判断标准**：专家的方法论选择明显偏向某一阵营（体现在 `visible_knowledge` 或 `known_decisions`），但从未解释为何不选另一阵营，也未提及该分歧的存在。

**含义**：专家有隐含的立场，但这个立场的依据未被说明，可能是一个判断变量。

**示例**：专家在多个案例中都选择同步写入，但 `domain_context.methodology_clashes` 中存在"同步 vs 异步写入"分歧，专家从未解释为何偏向同步。

---

### 3. 沉默话题（silent_topic）

**判断标准**：来自 `suspected_gaps` 中的条目——同行专家通常会讨论的话题，但此专家在所有材料中从未提及。

**含义**：沉默本身是信号。专家可能有一套未命名的隐性判断框架在覆盖这个话题，导致他"不需要显式讨论"，或者这恰恰是他的隐性弱点/盲区。

**这是 4 类来源中价值最高的**——它指向的是材料缺口，而不只是材料模糊。

**示例**：`suspected_gaps` 中存在"容灾等级判断"，但 `visible_knowledge` 和 `known_decisions` 中完全没有出现容灾相关内容。

---

### 4. 规则边界模糊（rule_boundary）

**判断标准**：`visible_knowledge` 中专家陈述了某个规则，但未说明该规则在什么条件下成立、在什么情况下失效、或有哪些例外。

**含义**：规则的边界条件本身是一个隐性变量——专家知道这个边界，但从未说清楚。

**示例**：`visible_knowledge[2]` 写道"先查连接池"，但未说明在什么情况下不需要查，或者查了没结果时的下一步判断依据是什么。

---

## 候选生成要求

> ⚠️ **每个候选必须完整包含以下字段，任何字段不完整或证据不具体的候选均不符合要求：**

| 字段 | 要求 |
|------|------|
| `id` | `lv_001`, `lv_002`, ... 自动顺序编号 |
| `label` | 隐性变量的简洁名称，5 字以内的判断维度名 |
| `source_type` | 4 类之一：`comparison_gap` / `domain_disagreement` / `silent_topic` / `rule_boundary` |
| `evidence_from_profile` | 画像中的**具体**证据引用，必须指向字段路径或原文内容，**禁止**只写"材料中提到" |
| `hypothesized_variable.name` | 变量的英文或中文技术名称 |
| `hypothesized_variable.description` | 这个变量是什么，专家如何使用它，影响哪类决策 |
| `hypothesized_variable.why_latent` | 为什么这是隐性的——专家为何没有明确表达这个变量（禁止只写"未明确说明"） |
| `testability` | `high` / `medium` / `low`（用三联体问题能否有效探测这个变量） |
| `priority` | 1-10 整数，数值越高优先级越高 |

**禁止输出**：
- 宽泛泛化的概念（如"经验丰富"、"综合判断"）
- 无具体证据的推测（来源必须可以追溯到 expert_profile 的字段）
- `visible_knowledge` 中已有的显性规则的简单重复

---

## 优先级打分参考

| 加分项 | 分值 |
|--------|------|
| 画像中有多处证据指向同一变量（evidence 强度高） | +3 |
| 来自 `suspected_gaps`（沉默话题，source_type: silent_topic） | +2 |
| `testability` 为 `high` | +2 |
| `testability` 为 `medium` | +1 |
| 业务影响范围广（跨越多个决策场景） | +2 |

基础分为 1，满分为 10。打分后按 priority 从高到低排列输出。

---

## 输出格式

严格按照以下 JSON 格式输出，字段名不得修改：

```json
{
  "latent_variables": [
    {
      "id": "lv_001",
      "label": "风险容忍阈值",
      "source_type": "comparison_gap",
      "evidence_from_profile": "known_decisions[0] 选了方案A，known_decisions[2] 选了方案B，场景相似决策不同，未见解释",
      "hypothesized_variable": {
        "name": "risk_tolerance_threshold",
        "description": "专家做技术决策时隐性使用的风险容忍边界，决定何时选保守方案、何时接受高风险换收益",
        "why_latent": "专家从未命名过这个阈值，但跨越多个决策的模式显示存在稳定的临界点；可能因为他认为这是'常识'而不值得说明"
      },
      "testability": "high",
      "priority": 8
    }
  ]
}
```

---

## 输出通过标准

以下是最低要求，不是上限：

- 候选总数 **5-12 个**（不足 5 个说明画像分析不充分；超过 12 个说明区分度不够，需合并）
- 每个候选有**具体的** evidence 引用（不得只写"材料中提到"，必须指向字段路径或引用原文）
- 每个候选的 `why_latent` 解释专家为何没有明确表达这个变量（不得只写"未明确说明"）
- 至少 **3 个**候选的 `testability` 为 `high` 或 `medium`
- 至少 **1 个**候选的 `source_type` 为 `silent_topic`（来自 suspected_gaps）
- `priority` 排序理由可追溯到上方打分表
