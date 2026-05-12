# 隐性知识挖掘引擎 Todo Plan

本文档基于 `docs/design.md`、`docs/design-thinking.md` 以及当前 `expert-skill` 代码结构整理。整体策略是：**不重写现有 expert-skill，而是在现有“材料分析 -> Skill 生成”链路中增加一条可选的隐性知识挖掘路径**。

## 0. 目标定义与边界确认

- [x] 明确 V1 目标：支持通过“前置研究 -> 隐性变量候选 -> 三联体问题 -> 实时访谈 -> 访谈分析 -> 融合生成”增强专家 Skill。
- [x] 明确 V1 非目标：
  - 不做多专家交叉验证。
  - 不做完整问卷系统。
  - 不替代现有原材料蒸馏流程。
  - 不做人格、语气、沟通风格模拟。
- [x] 保留现有快速路径：用户仍可跳过访谈，直接基于材料生成专家 Skill。
- [x] 新增增强路径：用户可选择进入“隐性知识挖掘模式”。

## 1. 数据模型与产物 Schema

- [x] 扩展 `tools/skill_schema.py` 的 artifact 定义，加入：
  - `latent_report.md`
  - `interview_transcript.md`
- [x] 在 `meta.json` 中增加 discovery 相关字段：
  - `discovery.enabled`
  - `discovery.status`
  - `discovery.interview_count`
  - `discovery.latent_variable_count`
  - `discovery.confidence_summary`
- [x] 定义《先验知识画像》结构：
  - `identity`
  - `visible_knowledge`
  - `known_decisions`
  - `domain_context`
    - `key_challenges`：领域核心挑战
    - `common_pitfalls`：常见陷阱
    - `methodology_clashes`：方法论分歧
  - `suspected_gaps`
- [x] 定义《隐性变量候选池》结构：
  - `id`
  - `label`
  - `source_type`
  - `evidence_from_profile`
  - `hypothesized_variable`
  - `why_latent`
  - `testability`
  - `priority`
- [x] 定义三联体问题结构：
  - `target_variable`
  - `domain_context`
  - `question_A`: `{ text, probes, expected_reveals }`
  - `question_B`: `{ text, variable_changed, probes, expected_reveals }`
  - `question_C`: `{ text, variable_changed, conflict_added, probes, expected_reveals }`
  - `control_notes`
- [x] 定义三联体中每个 question 的追问结构：
  - `probes.primary`
  - `probes.followups`
  - `probes.signal_triggers`
  - `expected_reveals.visible_rule`
  - `expected_reveals.latent_variable`
  - `expected_reveals.priority_signal`
- [x] 定义访谈分析结构：
  - `baseline_rule`
  - `awareness_state`
  - `priority_topology`
  - `latent_findings`
  - `confidence`
  - `invalidated_candidates`
- [x] 定义 discovery 中间文件存储位置：
  - 推荐使用 `skills/expert/{slug}/discovery/` 保存持久中间产物。
  - `/tmp` 仅用于临时 prompt 输入和未确认草稿。
  - 中间产物包括 `expert_profile.json`、`latent_variables.json`、`triplet_groups.json`、`interview_transcript.json`、`interview_analysis.json`。
- [x] 定义 discovery 状态枚举：
  - `not_started`
  - `profile_ready`
  - `variables_ready`
  - `triplets_ready`
  - `interview_in_progress`
  - `interview_completed`
  - `analysis_ready`
  - `merged`
  - `aborted`
  - 预留：V2 可从 `merged` 状态重新进入 `profile_ready`，发起迭代访谈（针对首轮新发现的隐性变量做更深层探测）。V1 暂不实现，但状态枚举设计时不应阻断此路径。

## 2. Prompt 体系建设

新增目录：

```text
prompts/discovery/
```

- [x] 新建 `prompts/discovery/pre_research.md`
  - 目标：从用户材料、专家简介、领域背景中生成《先验知识画像》。
  - 重点：不仅提取“说了什么”，还要识别“没说什么”“边界在哪里模糊”。
  - 预留“开放搜索结果”输入段，即使 V1 暂不自动联网搜索，也允许用户或后续工具填入行业背景、技术路线争议、基准案例。
  - 明确 prompt 质量指导：每个 `suspected_gaps` 必须说明“为什么按领域常识这里应该出现但材料中缺席”。
- [x] 新建 `prompts/discovery/latent_variable.md`
  - 目标：从先验画像生成 5-12 个隐性变量候选。
  - 强制要求：每个候选必须有证据、`why_latent`、可测试性判断。
  - 明确 prompt 质量指导：候选必须来自“对比缺失、领域分歧、沉默话题、规则边界模糊”四类来源之一。
  - 要求输出候选优先级排序理由，避免只生成宽泛概念。
- [x] 新建 `prompts/discovery/triplet_builder.md`
  - 目标：为高优先级候选生成 A/B/C 三联体问题。
  - 强制约束：
    - B 与 A 表面重叠率 >= 70%。
    - B 只改变 1 个隐性变量。
    - C 只叠加 1 个冲突变量。
    - 场景必须来自专家真实工作领域。
    - 不可预测性：专家不能从措辞中猜出被测试的隐性变量。
    - 决策差异应有性：A 和 B 的理论正确答案或合理选择应不同。
  - 每个 `question_A/B/C` 必须包含 `text`、`probes`、`expected_reveals`。
- [x] 新建 `prompts/discovery/interview_guide.md`
  - 目标：指导实时访谈。
  - 包含信号检测规则：察觉、迟疑、边界发明、矛盾、反驳。
  - 必须包含完整会话协议：
    - 提问 A -> 记录回答 -> 追问 1 轮思考过程。
    - 提问 B -> 比对 A/B -> 追问是否察觉差异及原因。
    - 提问 C -> 呈现冲突 -> 追问最大犹豫点和反转条件。
  - 必须包含 5 条 IF -> THEN 追问规则：
    - IF 察觉信号 AND 未说清变量 -> 追问“你看出来什么不同让你改判断？”
    - IF 迟疑信号 -> 追问“你在衡量什么？”
    - IF 边界发明 -> 追问“你怎么知道这个边界在哪的？”
    - IF 矛盾信号 -> 直接指出矛盾，请专家解释。
    - IF 模糊词（“经验”“感觉”“大概”）-> 追问“你感觉的线索是什么？”
- [x] 新建 `prompts/discovery/interview_analyzer.md`
  - 目标：分析访谈记录，输出隐性知识发现报告。
  - 支持单三联体分析和跨三联体分析。
  - 必须汇总所有“边界发明”，形成全局边界地图：适用域、失效域、反转条件。
  - 必须区分“候选被验证”“候选被证伪”“候选仍不确定”三种结论。
- [x] 更新现有 `prompts/expertise_builder.md`
  - 增加“融合隐性知识”的输入段。
  - 将隐性变量、优先级拓扑、边界条件写入最终专家知识。

## 3. 工具层实现

### 3.1 前置研究工具

- [x] 新建 `tools/pre_researcher.py`
  - 输入：专家基础信息、原材料路径、可选领域背景文本。
  - 输出：`expert_profile.json` 或 Markdown/YAML。
- [x] 复用现有采集工具：
  - `feishu_auto_collector.py`
  - `dingtalk_auto_collector.py`
  - `email_parser.py`
  - `slack_auto_collector.py`
- [x] V1 建议先不做自动网络搜索，先支持用户提供材料 + 手动补充领域背景。
- [x] 后续再加入可选开放搜索能力，避免第一版被网络权限和搜索质量拖慢。
- [x] 即使 V1 不做自动搜索，`pre_researcher.py` 也应支持读取可选的 `--open-research` 文件，作为开放搜索结果输入槽。

### 3.2 隐性变量生成工具

- [x] 新建 `tools/latent_variable_builder.py`
  - 输入：`expert_profile`
  - 输出：`latent_variables.json`
- [x] 实现质量门检查：
  - 候选数量必须为 5-12。
  - 每个候选必须有证据。
  - 每个候选必须有 `why_latent`。
  - 每个候选必须标记 `testability`。
- [x] 对候选排序：
  - 高证据强度。
  - 高业务价值。
  - 高可测试性。
  - 高“沉默话题”价值。
- [x] 输出 `latent_variables.json` 时保留被降级或暂不测试的候选，标记为 `testability: low`，不要静默丢弃。

### 3.3 三联体生成工具

- [x] 新建 `tools/triplet_generator.py`
  - 输入：`latent_variables.json`
  - 输出：`triplet_groups.json`
- [x] 加入三联体质量检查：
  - A/B 文本重叠率检查。
  - 单变量变更检查。
  - C 层冲突变量检查。
  - 场景真实性检查。
  - 不可预测性检查。
  - 决策差异应有性检查。
- [x] 定义 “A/B 表面重叠率 >= 70%” 的 V1 计算方法：
  - 先对中文文本按标点和空白切分为短句。
  - 再用字符 n-gram 或 token 集合计算 Jaccard 相似度。
  - 工具输出相似度分数和人工复核提示。
  - 对明显语义等价但字面分数不足的情况，允许标记 `manual_override_reason`。
- [x] 支持问题组装：
  - 开场 1 个。
  - 核心 3-8 个。
  - 深度 1-2 个。
  - 冷却 1 个。
- [x] 输出访谈脚本草稿，供实时访谈使用。

### 3.4 访谈记录工具

- [x] 新建 `tools/interview_session.py`
  - V1 可先做 CLI/文本会话记录，不必做复杂 UI。
  - 工具应按 A -> B -> C 的会话协议推进，避免操作者跳过必要追问。
  - 每轮记录：
    - 问题 ID。
    - A/B/C 原问题。
    - 专家回答。
    - 追问。
    - 观察信号。
    - 操作者备注。
- [x] 输出 `interview_transcript.md`。
- [x] 支持手动标注信号：
  - `noticed`
  - `hesitated`
  - `boundary_invented`
  - `contradiction`
  - `pushback`
- [x] 增加“辅助追问建议”功能：
  - 根据操作者标注的信号，输出对应推荐追问语。
  - 支持操作者接受、修改或跳过建议追问。
- [x] 记录访谈中断点：
  - 当前 triplet id。
  - 当前 question 层级。
  - 已完成追问。
  - 下一步建议动作。

### 3.5 访谈分析工具

- [x] 新建 `tools/interview_analyzer.py`
  - 输入：`triplet_groups.json` + `interview_transcript.md`
  - 输出：`latent_report.md` + 可选 `latent_findings.json`
- [x] 实现单三联体分析：
  - A 层基准规则。
  - B 层察觉状态：`explicit` / `semi_latent` / `deep_latent`。
  - C 层优先级拓扑。
- [x] 实现跨三联体分析：
  - 同变量一致性。
  - 优先级拓扑一致性。
  - 全局边界地图：汇总所有“边界发明”，标出适用域、失效域、反转条件。
  - 被证伪候选列表。
- [x] `latent_report.md` 输出结构必须包含以下段落：
  - 发现的隐性变量（按置信度排序）。
  - 隐性优先级拓扑。
  - 全局边界地图（适用域、失效域、反转条件）。
  - 疑似误判区：专家在特定条件下可能偏离最优判断的领域。
  - 未解问题：本轮访谈未能确认或证伪的候选，以及建议的后续探测方向。
- [x] 输出分析结论时必须附带证据引用：
  - 来源 triplet id。
  - A/B/C 层级。
  - 专家原始回答摘录。
  - 置信度理由。

## 4. `skill_writer.py` 增强

- [x] 修改 `tools/skill_writer.py`，支持写入新增产物：
  - `latent_report.md`
  - `interview_transcript.md`
- [x] 新增参数：
  - `--latent-report`
  - `--interview-transcript`
  - `--discovery-meta`
- [x] 更新 `write_expert_skill()`：
  - 如果传入隐性知识报告，则写入对应文件。
  - 如果没有传入，则保持现有行为不变。
- [x] 更新 `heuristics.json`：
  - 新增 `latent_variables`
  - 新增 `priority_rules`
  - 新增 `boundary_conditions`
- [x] 更新 `knowledge_graph.md`：
  - 新增隐性变量节点。
  - 新增规则冲突关系。
  - 新增边界条件关系。
- [x] 实现 `knowledge_graph.md` 的实际内容生成逻辑，不能只写 header 占位符。
- [x] 更新 `tools/skill_schema.py` 中的 `build_manifest()`：
  - 将 `latent_report.md` 加入 manifest artifacts。
  - 将 `interview_transcript.md` 加入 manifest artifacts。
  - 当 discovery 未启用时，可不生成文件，但 manifest 逻辑需要能识别可选产物。
- [x] 确保旧命令仍可运行：
  - `create`
  - `update`
  - `list`

## 5. 主流程整合

- [x] 更新 `SKILL.md` 主入口说明。
- [x] 增加两种生成模式：
  - `standard`：现有专家知识蒸馏。
  - `discovery`：隐性知识挖掘增强。
- [x] 标准模式流程：
  - Intake -> 原材料导入 -> 显性知识分析 -> Skill 生成。
- [x] Discovery 模式流程：
  - Intake -> 前置研究 -> 隐性变量候选 -> 三联体生成 -> 实时访谈 -> 访谈分析 -> 融合生成。
- [x] 支持用户跳过访谈：
  - 若跳过，则只生成 `expertise.md`、`knowledge_graph.md`、`heuristics.json` 等现有产物。
- [x] 支持访谈后增强已有专家 Skill：
  - 先备份版本。
  - 再写入增强后的 `expertise.md`。
  - 再新增 `latent_report.md` 和 `interview_transcript.md`。
- [x] 定义 discovery 中途中断后的恢复/清理策略：
  - 每个 Phase 完成后更新 `meta.json.discovery.status`。
  - 再次启动 discovery 时可从最近完成阶段继续。
  - 用户可选择丢弃未合并的 discovery 中间产物。
  - 已合并到正式 Skill 的产物必须通过 `version_manager.py` 回滚，而不是手动删除。

## 6. 质量门与验证标准

- [x] P2 前置研究质量门：
  - 至少 3 条 visible knowledge。
  - 至少 2 条 known decisions。
  - 至少 3 条 suspected gaps。
- [x] P3 隐性变量质量门：
  - 候选数 5-12。
  - 每个候选有证据。
  - 每个候选有 `why_latent`。
  - 至少 3 个候选为 high/medium testability。
- [x] P4 三联体质量门：
  - 每个核心候选至少 1 组三联体。
  - A/B 表面重叠率 >= 70%。
  - A/B/C 变量控制清晰。
  - 专家无法从措辞中直接猜出目标变量。
  - A/B 的合理决策结果应存在差异。
  - 每个 question 都包含 `probes` 和 `expected_reveals`。
- [x] P5 访谈质量门：
  - 每组三联体至少记录 A/B/C 回答。
  - 至少记录一轮追问。
  - 信号可为空，但不能缺失字段。
  - 访谈记录必须体现 A -> B -> C 的会话顺序。
  - 若出现信号标注，必须记录是否采用了推荐追问。
- [x] P6 分析质量门：
  - 每个三联体必须输出基准规则、察觉状态、优先级判断。
  - 每个隐性发现必须有置信度。
  - 被证伪候选必须记录，不直接删除痕迹。
  - 全局边界地图必须汇总所有 `boundary_invented` 信号。
- [x] P7 融合质量门：
  - 访谈中的实际选择优先于材料陈述。
  - 隐性知识必须进入 `expertise.md` 或 `heuristics.json`，不能只停留在报告里。
  - manifest 必须包含实际生成的 discovery 产物。

## 7. 测试计划

- [x] 为 schema helper 增加单元测试。
- [x] 为 `pre_researcher.py` 增加测试：
  - 原材料输入。
  - 可选 `--open-research` 输入。
  - `suspected_gaps` 最小数量校验。
- [x] 为 `latent_variable_builder.py` 增加测试：
  - 候选数量校验。
  - `why_latent` 缺失校验。
  - `testability` 分类校验。
- [x] 为 `skill_writer.py` 增加回归测试：
  - 无 discovery 输入时行为不变。
  - 有 discovery 输入时新增文件正确生成。
  - manifest 正确包含可选 discovery artifacts。
- [x] 为三联体生成增加测试：
  - 检查输出结构。
  - 检查候选数。
  - 检查 A/B/C 字段完整性。
  - 检查 `probes` 和 `expected_reveals` 字段完整性。
  - 检查 A/B 重叠率计算结果。
  - 检查不可预测性和决策差异应有性标记。
- [x] 为 `interview_session.py` 增加测试：
  - A -> B -> C 流程推进。
  - 信号标注后输出推荐追问。
  - 中断点记录和恢复。
- [x] 为 `interview_analyzer.py` 增加测试：
  - 单三联体分析结构。
  - 跨三联体一致性分析。
  - 全局边界地图生成。
  - 被证伪候选保留。
- [x] 准备 1 个 mock 专家样例：
  - 类型：troubleshooter 或 architect。
  - 材料：短消息/文档片段。
  - 跑通完整 discovery 流程。
- [x] 对比生成结果：
  - 访谈前 Skill。
  - 访谈后 Skill。
  - 验证增量价值是否清晰。

## 8. 推荐实施顺序

建议按 Phase 纵向推进，让 prompt、工具、测试在同一阶段内对齐，避免接口返工。

1. 基础 Schema 和 discovery 状态模型：
   - 扩展中间数据结构。
   - 定义 discovery 目录和状态枚举。
   - 暂不急着完整增强 writer。
2. P2 前置研究闭环：
   - 编写 `pre_research.md`。
   - 实现 `pre_researcher.py`。
   - 增加 P2 测试。
3. P3 隐性变量闭环：
   - 编写 `latent_variable.md`。
   - 实现 `latent_variable_builder.py`。
   - 增加 P3 质量门测试。
4. P4 三联体闭环：
   - 编写 `triplet_builder.md`。
   - 实现 `triplet_generator.py`。
   - 实现重叠率计算和三联体质量检查。
5. P5 访谈闭环：
   - 编写 `interview_guide.md`。
   - 实现 `interview_session.py`。
   - 支持辅助追问、信号标注、中断恢复。
6. P6 分析闭环：
   - 编写 `interview_analyzer.md`。
   - 实现 `interview_analyzer.py`。
   - 产出 `latent_report.md` 和 `latent_findings.json`。
7. P7 融合与 writer 增强：
   - 基于 P6 的实际输出格式增强 `skill_writer.py`。
   - 更新 `heuristics.json`、`knowledge_graph.md`、manifest。
   - 支持增强已有 Skill。
8. 端到端 mock 验证：
   - 用一个 mock 专家跑通 P2-P7。
   - 对比访谈前/访谈后的 Skill 差异。
9. 后续增强：
   - 自动开放搜索。
   - 访谈 UI。
   - 多专家交叉验证。
   - 迭代访谈：支持从已合并的 Skill 中发起第二轮 discovery，针对首轮新发现的隐性变量做更深层探测。

## 9. 实施建议

第一版应优先把“结构化产物 + prompt/工具闭环 + 三联体质量控制”做扎实。隐性知识挖掘的核心价值不在工具复杂度，而在 P2/P3 的推理质量、P4 的问题控制质量，以及 P5 能否捕捉真实追问信号。只要这几段稳住，后续的 UI、自动搜索、多专家验证都可以自然接上。

特别注意：所有 discovery prompt 都必须完整体现 `design.md` 的核心约束，包括不可预测性、决策差异应有性、A/B/C 追问结构、IF -> THEN 追问规则，以及全局边界地图。否则工具实现再完整，隐性知识探测效果也会明显打折。
