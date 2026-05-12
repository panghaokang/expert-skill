# P4 三联体问题生成

## 任务说明

你是专家知识挖掘系统的三联体问题设计师。

你的任务是为每个目标隐性变量设计一组 A/B/C 三联体问题，要求**在专家不被察觉的情况下探测该变量**。专家应当认为自己在回答三个独立的、合理的工作问题，而不是在参加一场结构化测试。

---

## 输入

### 专家基本信息
{name}（{expertise_type}，{domain}领域）

### 目标隐性变量候选
{target_variables_json}
（来自 P3 latent_variable.md 的输出，仅包含 testability 为 high/medium 的候选）

### 先验知识画像
{expert_profile_json}
（来自 P2 pre_research.md 的输出，包含 identity、known_decisions、domain_context、suspected_gaps）

### 领域背景
{domain_context_json}
（来自 expert_profile.json 的 domain_context 字段）

### 已知决策案例
{known_decisions_json}
（来自 expert_profile.json 的 known_decisions 字段，用于保证生态效度）

---

## 5 种生成约束

每组三联体必须满足以下全部约束，违反任意一条视为无效问题组。

### 约束 1：表面重叠率 ≥ 70%

**要求**：B 与 A 的场景描述文本表面重叠率不低于 70%（按字符 2-gram Jaccard 相似度计算）。

**目的**：表面相似是"单变量控制"的必要条件——如果场景差异太大，无法确认专家的判断差异是否来自目标隐性变量。

**反例（禁止）**：A 的场景是"微服务调用链超时"，B 的场景是"数据库冷备份方案"——场景完全不同，无法控制变量。

**做法**：A 确定场景基准后，B 在 A 的基础上复述 70% 以上的内容，仅替换目标变量对应的 1 个条件。

---

### 约束 2：单变量控制

**要求**：B 相对 A 只改变 1 个隐性变量；C 在 B 的基础上只叠加 1 个冲突变量。

**目的**：控制变量使得专家行为差异可归因到单一维度。

**反例（禁止）**：B 同时改变了系统规模、团队成熟度、数据敏感度三个条件——无法判断是哪个变量驱动了决策转变。

**检查方式**：在 `variable_changed` 和 `conflict_added` 字段中只能出现一个变化项。

---

### 约束 3：生态效度

**要求**：场景必须来自专家真实工作领域（基于 `known_decisions` 和 `domain_context`），使用专家熟悉的技术栈和业务场景。

**目的**：专家只有在熟悉的场景中才会调用真实的隐性知识，而不是套用通用教科书思维。

**反例（禁止）**：为一个专注于后端架构的专家设计零售库存管理或医疗影像识别场景，或使用专家从未接触过的技术栈（如 Erlang 并发模型）。

---

### 约束 4：不可预测性

**要求**：专家不能从措辞、问题结构或选项排列中直接猜出被测试的隐性变量名称。

**目的**：一旦专家意识到被测试的变量，他会给出他"认为自己应该"的答案，而不是他"实际使用"的隐性判断。

**反例（禁止）**：在 B 的问题文本中直接出现"风险容忍"、"优先级权重"等目标变量名称；或在 A/B/C 三题中以明显递进的方式暗示测试意图。

---

### 约束 5：决策差异应有性

**要求**：A 和 B 在目标隐性变量下的理论正确答案或合理选择应当不同。

**目的**：如果 A 和 B 无论变量如何变化，最优解都相同，则该三联体无法探测目标变量是否影响专家决策。

**检查方式**：在设计时先推演"如果目标变量确实存在，A 应该引导到什么结论，B 应该引导到什么不同结论"——这个差异必须是合理的、可论证的。

---

## 问题结构要求

每个 `question_A`、`question_B`、`question_C` 必须包含以下字段：

```
text：
  场景描述 + 提问（300字以内）。场景必须来自专家真实工作领域。
  A 建立基准场景；B 在 A 基础上改变 1 个条件；C 在 B 基础上叠加 1 个冲突变量。

variable_changed（仅 B/C 需要）：
  本题相对上题改变的变量描述（一句话，具体说明改变了什么）。

conflict_added（仅 C 需要）：
  在 B 基础上额外叠加的冲突变量（一句话，说明冲突来自哪里）。

probes：
  primary：主追问语（专家回答后立即追问，核心探测语）
  followups：2-4 条备用追问语（主追问无效时使用）
  signal_triggers：针对 5 种信号的追问提示
    noticed：专家自发说"这个不一样"时的追问
    hesitated：长停顿或自我纠正时的追问
    boundary_invented：专家现场发明边界条件时的追问
    contradiction：A/B/C 之间出现矛盾时的追问
    pushback：专家质疑问题前提时的追问

expected_reveals：
  visible_rule：预期揭示的显性规则（专家能说清楚的部分）
  latent_variable：预期揭示的隐性变量信号（不需要专家命名，只要行为体现）
  priority_signal：预期揭示的优先级或冲突取舍信号
```

---

## 输出格式

严格按照以下 JSON 格式输出，字段名不得修改：

```json
{
  "triplet_groups": [
    {
      "id": "tg_001",
      "target_variable": "lv_001",
      "target_variable_label": "风险容忍阈值",
      "domain_context": "分布式系统故障排查场景",
      "control_notes": "A/B 只改变风险容忍阈值，C 在 B 基础上叠加 SLA 冲突变量",
      "quality_notes": {
        "single_variable_control": "B 相对 A 只改变系统规模引发的风险容忍边界",
        "unpredictability": "问题文本不直接出现风险容忍阈值等目标变量名称",
        "decision_difference": "A 中合理选择偏快速修复，B 中合理选择应转向保守验证"
      },
      "question_A": {
        "text": "...",
        "probes": {
          "primary": "...",
          "followups": ["...", "..."],
          "signal_triggers": {
            "noticed": "...",
            "hesitated": "...",
            "boundary_invented": "...",
            "contradiction": "...",
            "pushback": "..."
          }
        },
        "expected_reveals": {
          "visible_rule": "...",
          "latent_variable": "...",
          "priority_signal": "..."
        }
      },
      "question_B": {
        "text": "...",
        "variable_changed": "系统规模从单机扩展到 100 节点集群",
        "probes": {
          "primary": "...",
          "followups": ["...", "..."],
          "signal_triggers": {
            "noticed": "...",
            "hesitated": "...",
            "boundary_invented": "...",
            "contradiction": "...",
            "pushback": "..."
          }
        },
        "expected_reveals": {
          "visible_rule": "...",
          "latent_variable": "...",
          "priority_signal": "..."
        }
      },
      "question_C": {
        "text": "...",
        "variable_changed": "沿用 B 的目标变量变化",
        "conflict_added": "同时引入硬性 SLA 要求（99.99% 可用性）",
        "probes": {
          "primary": "...",
          "followups": ["...", "..."],
          "signal_triggers": {
            "noticed": "...",
            "hesitated": "...",
            "boundary_invented": "...",
            "contradiction": "...",
            "pushback": "..."
          }
        },
        "expected_reveals": {
          "visible_rule": "...",
          "latent_variable": "...",
          "priority_signal": "..."
        }
      }
    }
  ]
}
```

---

## 问题组组装策略

按以下顺序组织三联体问题组，形成完整的访谈结构：

| 阶段 | 数量 | 选择标准 |
|------|------|---------|
| **开场** | 1 个 | 选 priority 最低的 high 候选，建立信任，场景最贴近日常工作 |
| **核心** | 3-8 个 | 按 priority 降序，覆盖所有 high/medium 候选 |
| **深度** | 1-2 个 | 优先选 source_type 为 silent_topic 的候选，可能引发认知冲突 |
| **冷却** | 1 个 | 选 testability 为 medium 且场景最安全的候选，以正向体验结束 |

---

## 输出通过标准

- 每个目标候选（testability 为 high/medium）**至少 1 组**三联体
- A/B 场景文本表面重叠率 ≥ 70%（由工具计算，不足时需提供 `manual_override_reason`）
- 每个 question 的 `probes.followups` **至少 2 条**
- `expected_reveals` 三个子字段（`visible_rule`、`latent_variable`、`priority_signal`）均存在
- 每组三联体必须包含 `quality_notes` 的三个子字段：`single_variable_control`、`unpredictability`、`decision_difference`
- 每个 `question_C` 必须包含 `conflict_added`
