# D2.5 Codex All-In-One Closure Pack

> 使用建议：如果只能给 Codex 一个文件，就给这个；如果可以分阶段执行，优先使用 `docs/D2.5-spec/` 中的分文件。

---

# File: 00_README_HUMAN_FIRST.md

# D2.5 论文-实验闭环包：先读这一页

## 0. 这包文件要解决什么

本包不是“投降式降级”。它的目标是把 RPMI-CMV 从现在的：

> rolling lifecycle / conflict blocking / failure trace 可审计

推进到：

> 在 target deterministic regimes 中，RPMI-CMV 能以可追踪、可解释的方式展示 low-disturbance recoverable slot selection 优势。

核心路线：

```text
RD / C_bar / RCMV
  -> selected action / selected gap
  -> reservation
  -> realized event
  -> hard brake / max decel / speed variance / wave / disturbance / TTC
```

如果这条链闭合，论文可以升级为 target-regime deterministic evidence。  
如果闭合失败，也能诚实判断：问题在 objective、RD/C_bar 定义、scenario、baseline、simulator，还是理论 claim。

---

## 1. 人怎么读

只想抓主线，读：

```text
00_README_HUMAN_FIRST.md
01_PROBLEM_GRADING_AND_MAIN_STORY.md
06_PAPER_CLAIM_DECISION_TREE.md
```

要指挥 Codex 执行，读：

```text
02_CODEX_MASTER_EXECUTION_SPEC.md
03_OBJECTIVE_METRIC_BASELINE_SPEC.md
04_TARGET_SCENARIO_CARDS.md
05_DECISIVE_EXPERIMENT_PROTOCOL.md
07_CODEX_PROMPT_SET_v2_闭环版.md
```

最推荐做法：

```text
1. 把 02_CODEX_MASTER_EXECUTION_SPEC.md 整份丢给 Codex。
2. 再把 07_CODEX_PROMPT_SET_v2_闭环版.md 的 Prompt 0 丢给 Codex。
3. 让 Codex 按 Prompt 1 -> Prompt 6 顺序执行。
4. 如果 Codex 卡住，只让它返回 stop condition 和缺失字段，不要让它自己编造成功。
```

---

## 2. Codex 先做什么

不要先大规模跑实验。先按这个顺序：

```text
A. Theory-to-metric audit
B. Missing metric register
C. Trace join schema
D. Principled Diagnostic Scenario Construction
E. Objective–Diagnostic Scenario Co-Design Loop
F. Evaluation Lock + Baseline Fairness Freeze
G. Locked Decisive Experiment
H. Paper Claim Decision
I. paper claim boundary
```

一句话：

```text
先用 diagnostic scenarios 调 objective；
再用 locked evaluation scenarios 做证据；
不要把调试场和最终考场混在一起。
```

---

## 3. 当前问题一眼分级

```text
P0：论文故事闭环没完成
    RD / C_bar / RCMV 还没连接到 realized low-disturbance outcome。

P1：目标函数需要重构
    权重、尺度、C_bar 定义、RD 定义、churn penalty 都可能要改。

P2：场景没有打中理论优势
    必须做 raw-gap trap、forced-accommodation、bad-action suppression。

P3：baseline 要围绕故事设计
    raw_largest_gap、forced_accommodation、without_RD、without_Cbar、without_theta 是核心。

P4：conflict-aware 先别抢主线
    它是机制补充，不是当前 low-disturbance story 的胜负点。
```

---

## 4. 论文主故事固定成一句话

英文建议：

> In deterministic target merging regimes, RPMI-CMV improves merge-slot quality by selecting recoverability-aware and disturbance-aware actions, reducing recovery debt and mainline disturbance compared with raw-gap and forced-accommodation baselines.

中文理解：

> 在确定性靶场合流场景中，RPMI-CMV 通过 recoverability-aware 和 disturbance-aware 的 action/gap 选择，相比 raw-gap 与 forced-accommodation baseline 降低恢复债与主线扰动。

先不要主张：

```text
universal optimality
stochastic robustness
multi-seed generalization
full conflict-aware rolling integer assignment 已验证
所有密度 / 所有 CAV penetration 都有效
```

---

## 5. 这次最重要的决定性实验

```text
D25-DECISIVE-RAW-GAP-FORCED-TRAP
```

要同时制造三件事：

```text
1. raw_largest_gap 会选几何最大但 recovery debt / disturbance 高的 Gap A。
2. forced_accommodation 可以强行服务需求，但 hard brake / max decel / wave / disturbance 高。
3. RPMI-CMV 应选几何较小但 recoverable、stable、low-disturbance 的 Gap B，或选择低成本 action-conditioned variant。
```

支持理论的结果：

```text
RPMI-CMV demand service 不差或 trade-off 可解释；
并且 RD_realized / hard_brake_count / max_deceleration / speed_variance_delta / wave_amplitude / mainline_disturbance_cost 更低；
同时 selected_action -> selected_edge/gap -> reservation -> realized_event -> metric change 可 join。
```

反驳或暂停理论强化的结果：

```text
RPMI-CMV 也选 Gap A；
RPMI-CMV 选 Gap B 但 realized disturbance 不低；
without_RD / without_Cbar / without_theta 和 full 选同一动作；
positive RCMV 不能 join 到 realized outcome；
forced baseline 无论怎样都不产生更高扰动，说明 simulator / metric sensitivity 先有问题。
```

---

## 6. 不要被信息淹没：当前只盯 4 个判断

```text
1. Full RPMI 是否和 raw_largest_gap 选了不同 gap / action？
2. Full RPMI 是否比 forced_accommodation 扰动低？
3. without_RD / without_Cbar / without_theta 是否改变选择或损害结果？
4. selected_action 是否能一路 join 到 realized disturbance / safety / demand outcome？
```

只要这 4 个问题回答清楚，论文-实验闭环就开始成立。


---

# File: 01_PROBLEM_GRADING_AND_MAIN_STORY.md

# 01 问题分级与论文主故事

## 1. 当前总判断

这篇论文现在不应被理解成“失败”或“只能降级”。更准确的判断是：

> 理论主线有价值，但实验、指标、baseline 和 objective 还没有闭合到论文真正想证明的低扰动性能机制。

Gate D2 已经证明的主要是：

```text
rolling lifecycle 可审计；
reservation / demand / slot / failure trace 可追；
conservative physical-gap conflict blocking 存在；
negative control 没有 hidden fallback。
```

Gate D2 没有充分证明的是：

```text
recoverability-aware / cost-aware / action-conditioned selection
是否真的降低 realized recovery debt、hard brake、wave、mainline disturbance。
```

因此 D2.5 的本质不是“补日志”，而是：

> 把理论量、动作选择、预约、实际结果、扰动指标闭合起来。

---

## 2. P0：论文故事闭环没完成

### 问题

当前主链条还没有闭合：

```text
J / RD / C_bar / RCMV
  -> selected action
  -> selected edge / gap
  -> reservation
  -> realized event
  -> realized low-disturbance outcome
```

### 为什么这是最高优先级

论文真正要赢的不是“系统能记录 reservation”，而是：

```text
RPMI-CMV 选择的 recoverable / low-debt / low-disturbance slot
比 raw gap 或 forced accommodation 更好。
```

### Codex 要做

必须生成并验证：

```text
trace_join_schema_plan.md
action_to_outcome_join.csv
disturbance_metrics.csv
recovery_metrics.csv
safety_metrics.csv
baseline_comparison.csv
ablation_comparison.csv
```

### Stop condition

如果 `selected_action_id` 无法 join 到：

```text
selected_edge_id
physical_gap_id / slot_group_id
reservation_id
realized_event_id
demand outcome
disturbance / recovery / safety metric
```

不要写 D2.5 support。先修 trace schema。

---

## 3. P1：目标函数需要重构

### 当前风险

旧目标函数可能存在几个问题：

```text
1. lambda_C 太小，或者 C_bar 只是 action effort proxy。
2. RD 只是 simplified proxy，未必对应 hard brake / wave / realized disturbance。
3. theta 太低，导致很小 RCMV 也触发 action。
4. 没有 churn / switching / commitment penalty。
5. Z_R 项可能压倒 cost，导致为了服务一个 demand 制造高扰动。
```

### 升级式修正

建议目标函数改成：

```text
J(a) =
  lambda_Z * Z_R_norm(a)
+ lambda_D * RD_pred_norm(a)
+ lambda_C * C_dist_norm(a)
+ lambda_S * S_safety_penalty(a)
+ lambda_Q * Q_churn_penalty(a)
```

RCMV 仍然保持：

```text
RCMV(a) = J(a0_none) - J(a)
```

选择规则：

```text
if max_a RCMV(a) > theta:
    select argmax RCMV(a)
else:
    select a0_none
```

### Codex 要做

```text
1. 审计现有 J / RD / C_bar / RCMV 是否参与 selected_action。
2. 将 C_bar 升级为 C_dist，不再只代表 action effort。
3. 将 RD 拆成 predicted_RD 与 realized_RD。
4. 加入 safety penalty 与 churn penalty。
5. 做 lambda_D / lambda_C / lambda_S / lambda_Q / theta 的校准网格。
6. 所有尝试写入 objective_calibration_log.csv，不允许只保留成功参数。
```

---

## 4. P2：场景没有打中理论优势

### 当前问题

泛泛 rolling 场景不能证明论文主故事。D2.5 必须设计“让 baseline 犯论文理论所预言错误”的场景。

### 三个最重要场景

```text
1. Raw-Large-Gap Trap
2. Forced-Accommodation
3. Bad-Action Suppression
```

### 每个场景必须明确

```text
baseline 为什么看起来合理；
baseline 为什么按论文理论会错；
RPMI-CMV 理论上为什么应该赢；
需要哪些 realized metrics 证明赢了；
失败时如何区分理论错、实现错、指标错、场景错。
```

---

## 5. P3：baseline 要围绕故事设计

### 核心 baseline / ablation

```text
raw_largest_gap
fifo_feasible_gap
forced_accommodation
no_action_natural
reservation_before_action / stale_reservation
without_RD
without_Cbar / without_cost
without_theta
without_conflict_blocking
```

### 重点不是数量，而是用途

| baseline | 用途 |
|---|---|
| raw_largest_gap | 证明 raw geometric gap 会被骗 |
| forced_accommodation | 证明强行合流不等于低扰动合流 |
| no_action_natural | 证明自然库存是否已经足够 |
| without_RD | 证明 RD 真的改变选择 |
| without_Cbar | 证明 disturbance cost 真的压制坏动作 |
| without_theta | 证明 threshold 真的避免微小收益触发 action |
| stale_reservation | 证明 action-conditioned / rolling 的必要性 |
| without_conflict_blocking | 证明不靠重复消费 physical gap 虚高成功率 |

---

## 6. P4：conflict-aware 先别抢主线

### 正确定位

conflict-aware 是论文机制完整性的一部分，但不是 D2.5 的主战场。当前可说：

> prototype implements conservative physical-gap conflict blocking.

暂时不要说：

> full conflict-aware rolling integer assignment has been validated.

### Codex 要做

只需要保留 conflict blocking 的 honest denominator 作用：

```text
physical_gap_id / slot_group_id
duplicate_consumption_attempt_count
duplicate_gap_consumption_count
blocked_by_conflict_count
unserved_due_to_conflict_count
```

它作为补充机制，不要抢走 low-disturbance story 的主线。

---

## 7. 当前行动主线

```text
1. 固定论文主故事：
   target deterministic regimes 中，RPMI-CMV 降低 recovery debt 和 mainline disturbance。

2. 重构 objective：
   J = lambda_Z Z_R + lambda_D RD + lambda_C C_dist + lambda_S safety + lambda_Q churn。

3. 重定义 C_bar：
   从 action effort 升级为 disturbance-aware cost。

4. 重定义 RD：
   从抽象 proxy 升级为 predicted recovery burden，并与 realized RD 对照。

5. 做目标函数校准：
   调 lambda_D、lambda_C、lambda_S、lambda_Q、theta，记录所有尝试。

6. 做 ablation：
   full vs without_RD vs without_Cbar vs without_theta。

7. 做决定性场景：
   Raw-Large-Gap Trap + Forced-Accommodation。

8. 用 realized metrics 闭环：
   hard brake、max decel、speed variance、wave amplitude、disturbance cost、min TTC。

9. 论文写法：
   不说 universal optimality；
   说 target-regime deterministic evidence supports low-disturbance recoverable slot selection。
```


---

# File: 02_CODEX_MASTER_EXECUTION_SPEC.md

# 02 Codex Master Execution Spec：D2.5 自主执行总规格

## 0. 给 Codex 的角色设定

你是 RPMI-CMV 项目的科研工程执行 agent。你的任务不是泛泛重构代码，而是完成 D2.5：

> Theory-Evidence Alignment and Targeted Performance Validation.

目标是判断并尽量闭合：

```text
RPMI-CMV 在 deterministic target scenarios 中，
是否能通过 recoverability-aware / disturbance-aware / action-conditioned selection，
相比 raw-gap 和 forced-accommodation baselines，
降低 recovery debt、mainline disturbance、hard brake、speed wave，同时保持 demand service 不差或 trade-off 可解释。
```

你必须主动执行，不要停在口头建议。  
但遇到 stop condition 时，必须停止 claim 强化，输出原因和修复建议。

---

## 1. 禁止事项

```text
1. 不要先做 Wave 9 stochastic IDM。
2. 不要把 conservative conflict blocking 写成 full rolling integer assignment validated。
3. 不要把 failed_reservation_rate=0.0 写成 demand success。
4. 不要靠 hidden fallback / emergency repair 让实验成功。
5. 不要只保留成功参数；调参尝试必须全部记录。
6. 不要在 selected_action 无法 join 到 realized metrics 时写 support。
7. 不要修改论文正文作为第一步；先生成 evidence package 和 claim boundary。
8. 不要使用 RPMI-only future information 让 baseline 变得不公平。
```

---

## 2. 你应先检查的输入

在 repo 中定位并阅读这些文件。如果路径不同，搜索文件名或关键词。

```text
docs/paper/第3.1版论文稿.md
outputs/d2_5_theory_alignment/external_review_digest.md
outputs/d2_5_theory_alignment/d2_5_execution_charter.md
docs/specs/14_D2_5_Theory_Evidence_Alignment_Targeted_Performance_Validation_Plan_v1_zh.md
outputs/wave8_rolling_validation/wave8_d2_input_v2/gate_D2_input/
```

如果这些文件有缺失，不要编造。创建：

```text
outputs/d2_5_theory_alignment/missing_input_register.md
```

列出缺失项、影响、替代路径。

---

## 3. 总输出目录

所有 D2.5 新产物放在：

```text
outputs/d2_5_theory_alignment/
```

不要覆盖 Wave 8 / Gate D2 原始结果。  
所有新实验结果放在：

```text
outputs/d2_5_theory_alignment/gate_D2_5_input/
```

所有人类可读审阅结果放在：

```text
outputs/d2_5_theory_alignment/human_review/
```

---

## 4. 必须生成的文档产物

```text
outputs/d2_5_theory_alignment/theory_metric_audit.md
outputs/d2_5_theory_alignment/missing_metric_register.md
outputs/d2_5_theory_alignment/metric_schema_plan.md
outputs/d2_5_theory_alignment/trace_join_schema_plan.md
outputs/d2_5_theory_alignment/target_scenario_cards.md
outputs/d2_5_theory_alignment/baseline_fairness_audit.md
outputs/d2_5_theory_alignment/objective_reconstruction_plan.md
outputs/d2_5_theory_alignment/objective_calibration_protocol.md
outputs/d2_5_theory_alignment/objective_scenario_codesign_plan.md
outputs/d2_5_theory_alignment/objective_scenario_design_register.csv
outputs/d2_5_theory_alignment/co_design_iteration_log.csv
outputs/d2_5_theory_alignment/mechanism_activation_report.md
outputs/d2_5_theory_alignment/LOCKED_OBJECTIVE.md
outputs/d2_5_theory_alignment/LOCKED_SCENARIOS.md
outputs/d2_5_theory_alignment/LOCKED_BASELINES.md
outputs/d2_5_theory_alignment/LOCKED_METRICS.md
outputs/d2_5_theory_alignment/LOCKED_PASS_FAIL_CRITERIA.md
outputs/d2_5_theory_alignment/d2_5_decision_report.md
outputs/d2_5_theory_alignment/paper_claim_boundary.md
```

---

## 5. 必须生成的数据产物

在 `gate_D2_5_input/` 下至少生成：

```text
scenario_summary.csv
candidate_gap_table.csv
action_value_decomposition.csv
trace_join_table.csv
demand_outcome_metrics.csv
reservation_lifecycle_metrics.csv
disturbance_metrics.csv
recovery_metrics.csv
safety_metrics.csv
baseline_comparison.csv
ablation_comparison.csv
objective_calibration_log.csv
objective_scenario_design_register.csv
co_design_iteration_log.csv
failure_trace.csv
run_manifest.json
```

### 5.1 scenario_summary.csv 最低字段

```text
scenario_id
scenario_design_id
scenario_family
deterministic_case_id
random_seed_optional
deterministic_mode
algorithm_variant
baseline_id
D_H
merge_success_count
merge_success_rate_over_demand
realized_unserved_demand_count
realized_unserved_demand_rate
generated_reservation_count
failed_reservation_count
failed_reservation_rate
invalid_or_unsafe_event_count
hidden_fallback_count
mainline_disturbance_cost
mean_RD_pred
mean_RD_realized
hard_brake_count
max_deceleration
speed_variance_delta
max_wave_amplitude
min_TTC
min_realized_gap
pass_flag
fail_reason
```

### 5.2 candidate_gap_table.csv 最低字段

```text
scenario_id
context_id
candidate_edge_id
ramp_vehicle_id
front_vehicle_id
rear_vehicle_id
physical_gap_id
slot_group_id
tau
raw_gap_size
closing_rate
reachability_flag
predicted_physical_validity
P_R
RD_pred
C_dist_pred
safety_penalty_pred
is_near_miss
is_selected_by_full_rpmi
is_selected_by_raw_largest_gap
is_selected_by_forced_accommodation
```

### 5.3 action_value_decomposition.csv 最低字段

```text
scenario_id
context_id
action_id
action_type
candidate_edge_id
selected_edge_id
selected_physical_gap_id
Z_R
RD_pred_norm
C_dist_norm
S_safety_penalty
Q_churn_penalty
J
J_none
RCMV
RCMV_margin_to_second_best
theta
lambda_Z
lambda_D
lambda_C
lambda_S
lambda_Q
selected_flag
selection_reason
```

### 5.4 trace_join_table.csv 最低字段

```text
scenario_id
context_id
selected_action_id
selected_edge_id
physical_gap_id
slot_group_id
reservation_id
demand_id
realized_event_id
demand_outcome
merge_time_pred
merge_time_realized
selected_gap_raw_size
selected_gap_RD_pred
selected_gap_RD_realized
hard_brake_count_after
max_deceleration_after
speed_variance_delta_after
max_wave_amplitude_after
mainline_disturbance_cost_after
min_TTC_after
min_realized_gap_after
can_join_full_chain
join_failure_reason
```

---

## 6. 执行阶段

### Phase A：Repo inspection

任务：

```text
1. 找到当前 simulator / scenario / metric / baseline / gate scripts。
2. 列出相关文件。
3. 不改代码，先输出 repo_inspection_summary.md。
```

输出：

```text
outputs/d2_5_theory_alignment/repo_inspection_summary.md
```

### Phase B：Theory-to-metric audit

任务：

```text
1. 审计 Z_R / S_R / P_R / RD / C_bar / J / RCMV / theta。
2. 标明每个理论量对应哪个函数、哪个字段、哪个 CSV。
3. 标明它是否参与 selected_action。
4. 标明它是否能 join realized outcome。
5. 标明缺项。
```

输出：

```text
theory_metric_audit.md
missing_metric_register.md
```

Stop condition：

```text
如果 J / RD / C_bar / RCMV 无法定位到代码或 CSV，停止实验跑批，先修映射。
```

### Phase C：Metric and trace schema implementation

任务：

```text
1. 实现或补齐 disturbance / recovery / safety metrics。
2. 实现 selected_action -> realized_event -> metrics 的 join。
3. 确保 no-hidden-fallback 规则对 RPMI 和 baseline 都相同。
```

输出：

```text
metric_schema_plan.md
trace_join_schema_plan.md
trace_join_table.csv
```

Stop condition：

```text
如果 selected_action 无法 join 到 realized_event 和 metric change，不进入 D2.5 decision report。
```

### Phase D：Principled Diagnostic Scenario + Minimal Baseline Instrumentation

任务：

```text
1. 原则化构造 diagnostic scenarios，而不是随机 seed 搜索。
2. 每个场景必须声明 scenario_design_id、construction_principle、mechanism_target、diagnostic_contrast、parameter_ladder_id。
3. 至少准备 P0 raw-gap / forced-accommodation trap，以及两个 P1：bad-action suppression、near-miss production。
4. 为 full / raw_largest_gap / forced_accommodation / without_RD / without_Cbar / without_theta 准备最小可运行 instrumentation。
5. 如果 baseline 尚未实现，先补最小公平 baseline；不要跳过 forced_accommodation 或 exact raw_largest_gap。
```

输出：

```text
target_scenario_cards.md
baseline_fairness_audit.md
objective_scenario_design_register.csv
```

禁止写法：

```text
Seed diagnostic scenarios
```

应写成：

```text
Principled Diagnostic Scenario Construction
```

这里的 seed 只能表示 reproducibility seed / deterministic case id，不是场景来源。

### Phase E：Objective–Diagnostic Scenario Co-Design Loop

核心原则：

```text
Objective reconstruction and diagnostic scenario construction must not be executed as independent linear steps.
They must be co-designed.
```

执行闭环：

```text
原则化构造诊断场景
-> 用当前 objective 跑 full / baseline / ablation
-> 看失败模式
-> 判断失败来自 objective、scenario、metric、baseline、implementation 还是 simulator
-> 只根据具体失败模式修改 RD / C_bar / theta / lambda / churn 或诊断场景参数
-> 再跑诊断场景
-> 确认机制是否真的被激活
-> 当 objective 和 diagnostic scenarios 已经互相校准后
-> 才允许进入 Evaluation Lock
```

最低自主迭代要求：

```text
minimum_wall_clock_target: 2 hours if runtime permits
minimum_meaningful_iterations: 6 unless an earlier stop condition is hit
maximum_iterations: 20
minimum_scenario_families: P0 + two P1
minimum_variants_per_iteration:
  - full_RPMI_reconstructed_objective
  - raw_largest_gap
  - forced_accommodation
  - without_RD
  - without_Cbar
  - without_theta
```

每轮必须记录：

```text
iteration_id
scenario_design_id
mechanism_target
failure_observed
failure_type
hypothesis
changed_component
old_value
new_value
selected_gap_before
selected_gap_after
selected_action_before
selected_action_after
RD_pred_direction_match
C_dist_direction_match
realized_disturbance_change
ablation_sensitivity_change
keep_or_revert
reason
```

允许在 co-design 阶段升级 objective 为：

```text
J(a) =
  lambda_Z * Z_R_norm(a)
+ lambda_D * RD_pred_norm(a)
+ lambda_C * C_dist_norm(a)
+ lambda_S * S_safety_penalty(a)
+ lambda_Q * Q_churn_penalty(a)
```

必须保留 variants：

```text
legacy_objective
full_reconstructed_objective
without_RD
without_Cbar
without_theta
without_churn
```

输出：

```text
objective_reconstruction_plan.md
objective_calibration_protocol.md
objective_scenario_codesign_plan.md
objective_scenario_design_register.csv
co_design_iteration_log.csv
mechanism_activation_report.md
objective_calibration_log.csv
ablation_comparison.csv
```

Stop condition：

```text
如果 raw_largest_gap 不能稳定触发 raw-gap trap、forced_accommodation 不能产生可测 disturbance、without_RD / without_Cbar / without_theta 与 full 完全无差异，不能进入 Evaluation Lock；先分类为 revise_objective / revise_scenario / revise_metric / revise_baseline / revise_implementation / simulator_sensitivity_insufficient。
```

### Phase F：Evaluation Lock

任务：

```text
1. 锁定 objective formula、RD_pred definition、C_dist definition、normalization rules、lambda、theta、churn rule。
2. 锁定 evaluation scenarios、baselines、ablations、metrics、fairness rules、pass/fail criteria。
3. 明确区分 diagnostic scenarios 与 held-out evaluation scenarios。
4. 生成 lock package。锁定后除 implementation bug invalidation 外，不允许继续调参。
```

输出：

```text
LOCKED_OBJECTIVE.md
LOCKED_SCENARIOS.md
LOCKED_BASELINES.md
LOCKED_METRICS.md
LOCKED_PASS_FAIL_CRITERIA.md
run_manifest.json
```

所有 locked baseline 必须满足：

```text
same initial state
same demand
same horizon
same candidate time grid
same physical validity rule
same no-hidden-fallback rule
same denominator policy
no RPMI-only future information
```

Stop condition：

```text
如果 baseline fairness 不成立，不进入 locked decisive experiment。
如果 Evaluation Lock 后还需要改 lambda / theta / scenario 才能通过，必须回到 co-design 阶段，且该 run 不得作为 final evidence。
```

### Phase G：Locked Decisive Experiment

优先运行：

```text
P0: D25-DECISIVE-RAW-GAP-FORCED-TRAP
P1: D25-BAD-ACTION-SUPPRESSION
P1: D25-NEAR-MISS-PRODUCTION
P2: D25-PHYSICAL-GAP-CONFLICT
P2: D25-ROLLING-STALE-PERFORMANCE
```

如果时间有限，先只做 P0 + 两个 P1。

运行顺序：

```text
Step 0: Verify lock package
Step 1: Sanity check locked scenario
Step 2: Run no_action_natural
Step 3: Run raw_largest_gap
Step 4: Run forced_accommodation
Step 5: Run full RPMI with locked objective
Step 6: Run locked ablations
Step 7: Build final evidence table
Step 8: Failure classification without tuning
```

禁止：

```text
1. 看 final result 后继续调 lambda。
2. 看 final result 后继续改 theta。
3. 看 final result 后继续改 scenario。
4. 把 calibration / co-design run 当成 final evidence。
5. 只展示成功 run。
```

允许：

```text
只允许做 secondary sensitivity reporting，不允许改变 locked objective、scenarios、baselines、metrics、pass/fail criteria。
```

输出：

```text
scenario_summary.csv
candidate_gap_table.csv
action_value_decomposition.csv
trace_join_table.csv
demand_outcome_metrics.csv
reservation_lifecycle_metrics.csv
disturbance_metrics.csv
recovery_metrics.csv
safety_metrics.csv
baseline_comparison.csv
ablation_comparison.csv
failure_trace.csv
run_manifest.json
```

### Phase H：Paper Claim Decision

输出：

```text
d2_5_decision_report.md
paper_claim_boundary.md
```

报告必须回答：

```text
1. P0 决定性实验是否支持主故事？
2. RD / C_bar / RCMV 是否参与 selection？
3. positive RCMV 是否对应 realized improvement？
4. RPMI 是否优于 raw-gap / forced baseline？
5. without_RD / without_Cbar / without_theta 是否破坏结果？
6. 失败是 theory、objective、metric、scenario、baseline、implementation、simulator 哪一类？
7. 论文 claim 应该 strong / qualified / revise / hold？
```

---

## 7. D2.5 硬通过标准

至少满足：

```text
1. 至少一个 raw-gap trap 中，RPMI-CMV 在 demand service 不差或 trade-off 可解释的情况下，RD 或 disturbance 明显更低。
2. 至少一个 forced-accommodation case 中，baseline merge success 相近但 hard brake / wave / disturbance 更差。
3. 至少一个 bad-action suppression case 中，RPMI-CMV 选择 none 或低成本 action，避免不必要扰动。
4. 至少一个 near-miss production case 中，RPMI-CMV 通过低扰动 action 把不可用 slot 变成可用 slot。
5. 每个 positive case 都能 join selected_action -> selected_edge/gap -> reservation -> realized_event -> metric change。
6. 所有场景同时报告 demand denominator 和 disturbance metrics。
7. failure 必须诚实记录，不能 hidden fallback。
```

---

## 8. D2.5 判定标签

使用以下标签，不要自行创造模糊结论：

```text
support_target_regime_theory
qualified_support_mixed
revise_objective
revise_metric
revise_scenario
revise_baseline
revise_implementation
simulator_sensitivity_insufficient
insufficient_trace_join
do_not_claim_performance
```

---

## 9. 最后输出给人看的摘要格式

在 `human_review/d2_5_one_page_summary.md` 中用 1 页写：

```text
1. 主结论
2. P0 决定性实验结果
3. 最强支持证据
4. 最强反证或边界
5. 论文现在能写什么
6. 论文不能写什么
7. Wave 9 是否可以进入
8. 下一步唯一最重要任务
```


---

# File: 03_OBJECTIVE_METRIC_BASELINE_SPEC.md

# 03 Objective / Metrics / Baseline 规格

## 1. Objective 重构

### 1.1 新目标函数

D2.5 推荐将 objective 升级为：

```text
J(a) =
  lambda_Z * Z_R_norm(a)
+ lambda_D * RD_pred_norm(a)
+ lambda_C * C_dist_norm(a)
+ lambda_S * S_safety_penalty(a)
+ lambda_Q * Q_churn_penalty(a)
```

其中：

```text
RCMV(a) = J(a0_none) - J(a)
```

选择规则：

```text
if max_a RCMV(a) > theta:
    selected_action = argmax_a RCMV(a)
else:
    selected_action = a0_none
```

### 1.2 为什么要改

旧版本风险：

```text
C_bar 可能只是 action effort proxy；
RD 可能只是 simplified proxy；
positive RCMV 可能很小但仍触发 action；
高 churn / supersede 没有被惩罚；
safety margin 可能没有作为连续 penalty 进入 selection。
```

这不是“投降式改理论”，而是让 objective 服务论文主故事：

```text
recoverability-aware + disturbance-aware + action-conditioned slot selection。
```

---

## 2. 各项定义

### 2.1 Z_R_norm

含义：

```text
recoverable inventory deficit normalized by demand.
```

建议：

```text
Z_R_norm = max(D_H - S_R, 0) / max(D_H, epsilon)
```

注意：

```text
Z_R 不能压倒所有项；否则算法会为了服务一个 demand 执行高扰动动作。
```

### 2.2 RD_pred_norm

RD 应从抽象 proxy 升级为 predicted recovery burden。

建议组成：

```text
required_rear_deceleration_pred
recovery_time_estimate_pred
affected_vehicle_count_pred
post_merge_speed_drop_pred
wave_amplitude_proxy_pred
outflow_loss_proxy_pred
```

推荐形式：

```text
RD_pred_norm =
  beta_B * norm(required_rear_deceleration_pred)
+ beta_T * norm(recovery_time_estimate_pred)
+ beta_N * norm(affected_vehicle_count_pred)
+ beta_V * norm(post_merge_speed_drop_pred)
+ beta_A * norm(wave_amplitude_proxy_pred)
+ beta_Q * norm(outflow_loss_proxy_pred)
```

必须同时输出 realized 对照：

```text
RD_realized
RD_delta = RD_after - RD_before
RD_prediction_error = RD_realized - RD_pred
```

### 2.3 C_dist_norm

将旧 `C_bar` 升级为 disturbance-aware cost。

建议组成：

```text
action_effort
induced_mainline_deceleration
mean_abs_acceleration
acceleration_variance
speed_variance_delta
wave_amplitude_proxy
affected_vehicle_count
```

推荐形式：

```text
C_dist_norm =
  gamma_U * norm(action_effort)
+ gamma_B * norm(induced_mainline_deceleration)
+ gamma_A * norm(mean_abs_acceleration)
+ gamma_VAR * norm(speed_variance_delta)
+ gamma_W * norm(wave_amplitude_proxy)
+ gamma_N * norm(affected_vehicle_count)
```

必须记录：

```text
C_bar_legacy
C_dist_new
C_dist_components_json
```

如果 `C_bar` 被确认只是 action effort，不要在论文里叫 mainline disturbance cost。

### 2.4 S_safety_penalty

建议组成：

```text
min_TTC penalty
DRAC penalty
min_gap penalty
unsafe_margin penalty
predicted_overlap penalty
realized_invalid_event penalty
```

推荐：

```text
S_safety_penalty =
  penalty(min_TTC < TTC_min)
+ penalty(DRAC > DRAC_max)
+ penalty(min_gap < gap_min)
+ penalty(predicted_overlap)
```

这里 safety penalty 不是 hidden fallback。它只影响选择和报告；不允许事后自动修复 unsafe trajectory。

### 2.5 Q_churn_penalty

D2-ACTION-CONDITIONED-RECOMPUTE 的高 churn/unserved 风险说明，需要显式惩罚：

```text
reservation_supersede_count
action_switch_count
active_guidance_change
plan_lock_violation
stale_risk
new_plan_improvement_below_hysteresis
```

推荐：

```text
Q_churn_penalty =
  q1 * supersede_risk
+ q2 * switching_risk
+ q3 * active_guidance_change_risk
+ q4 * stale_risk
```

---

## 3. Calibration 规则

Calibration 不是 blind parameter sweep。D2.5 的 objective 更新必须是 failure-driven co-design：

```text
Objective update must be failure-driven.
Do not tune objective blindly.
Each change must be tied to one diagnostic failure mode.
```

参数网格只能服务诊断闭环，不能服务最终实验现场调参。所有 calibration / co-design 结果必须在 Evaluation Lock 前完成；锁定后只能做 secondary sensitivity reporting，不能改变 locked objective、scenarios、baselines、metrics 或 pass/fail criteria。

### 3.1 可调参数

```text
lambda_Z
lambda_D
lambda_C
lambda_S
lambda_Q
theta
RD component weights beta_*
C_dist component weights gamma_*
hard_brake_threshold
wave_window
TTC_min
DRAC_max
churn_hysteresis
```

### 3.2 允许调参，但必须可辩护

允许围绕 target regime 调参。论文不需要证明 universal optimality。  
但必须遵守：

```text
1. 先定义 target regime，再调参。
2. 一组 default parameters 适用于所有 D2.5 target scenarios。
3. 所有尝试写入 objective_calibration_log.csv。
4. 失败 run 保留。
5. 不允许只展示成功 seed / 成功参数。
6. 不允许为了让 baseline 输而给 baseline 更差物理规则。
```

### 3.3 推荐调参顺序

```text
Step 1: 固定 lambda_Z = 1.0。
Step 2: 扫 lambda_C，确保 bad-action suppression 能选 none / low-cost action。
Step 3: 扫 lambda_D，确保 raw-gap trap 中高 RD gap 被压制。
Step 4: 加 lambda_S，确保 unsafe 或低 TTC candidate 被压制。
Step 5: 加 lambda_Q，降低 recompute churn / supersede。
Step 6: 扫 theta，避免 tiny positive RCMV 触发无意义 action。
```

### 3.4 推荐网格

先小网格：

```text
lambda_D in {0.5, 1.0, 2.0, 4.0}
lambda_C in {0.5, 1.0, 2.0, 4.0}
lambda_S in {0.0, 1.0, 2.0}
lambda_Q in {0.0, 0.5, 1.0}
theta in {0.0, 0.001, 0.005, 0.01}
```

若数值尺度不同，Codex 应先输出 observed component ranges，再自适应调整网格。不要盲目使用这些数字。

### 3.5 Failure-driven co-design calibration

每次 objective 或 diagnostic scenario 修改都必须绑定一个已观测 failure。要求循环：

```text
1. Run full / baseline / ablation on a diagnostic scenario.
2. Record selected gap/action and all J components.
3. Compare predicted RD / C_dist with realized RD / disturbance.
4. Classify failure:
   - objective_scale_failure
   - RD_definition_failure
   - C_dist_definition_failure
   - theta_failure
   - churn_failure
   - scenario_not_diagnostic
   - metric_insensitive
   - baseline_unfair
   - implementation_bug
   - simulator_sensitivity_insufficient
5. Modify only the relevant component.
6. Re-run the minimal diagnostic case.
7. Keep or revert the change.
8. Log the decision.
```

不允许：

```text
1. 为每个 scenario 单独 cherry-pick lambda / theta。
2. 只保留成功 run。
3. 因 final evaluation 结果不好而现场改 objective。
4. 用更差的物理规则让 baseline 输。
5. 在 trace join 不完整时把 positive RCMV 写成 performance support。
```

### 3.6 co_design_iteration_log.csv 最低字段

```text
iteration_id
scenario_design_id
scenario_family
mechanism_target
failure_observed
failure_type
hypothesis
changed_component
old_value
new_value
selected_gap_before
selected_gap_after
selected_action_before
selected_action_after
RD_pred_direction_match
C_dist_direction_match
realized_disturbance_change
ablation_sensitivity_change
keep_or_revert
reason
```

### 3.7 objective_scenario_design_register.csv 最低字段

```text
scenario_design_id
scenario_family
construction_principle
mechanism_target
diagnostic_contrast
controlled_knobs
parameter_ladder_id
random_seed_optional
expected_baseline_failure
expected_full_behavior
minimum_activation_gate
anti_cherry_picking_rule
held_out_variant_rule
lock_status
```

### 3.8 mechanism_activation_report.md 必答问题

进入 Evaluation Lock 前，必须回答：

```text
1. raw_largest_gap 是否稳定选择机制设计中的 Gap A？
2. forced_accommodation 是否能服务但带来更高 disturbance？
3. full RPMI-CMV 是否选择 Gap B / low-cost action / none？
4. without_RD 是否更容易选高 RD gap？
5. without_Cbar 是否更容易选高 disturbance action？
6. without_theta 是否更容易触发 tiny-RCMV action 或 churn？
7. RD_pred / C_dist_pred 是否与 realized metrics 同向？
8. selected_action 是否能 join 到 realized_event 和 metric change？
```

如果这些问题没有答案，不得进入 Evaluation Lock。

---

## 4. 必补 Metrics

### 4.1 Demand denominator

必须保留：

```text
D_H
generated_reservation_count
failed_reservation_count
failed_reservation_rate
failed_reservation_denominator
merge_success_count
merge_success_rate_over_demand
predicted_unserved_demand_count
predicted_unserved_demand_rate
realized_unserved_demand_count
realized_unserved_demand_rate
```

红线：

```text
failed_reservation_rate = 0.0
不等于
merge_success_rate_over_demand = 1.0
```

### 4.2 Disturbance metrics

必须新增或强化：

```text
hard_brake_count
max_deceleration
mean_abs_acceleration
acceleration_variance
speed_variance_before
speed_variance_after
speed_variance_delta
max_wave_amplitude
mainline_disturbance_cost
mainline_disturbance_cost_normalized
action_cost_sum
action_cost_per_served_demand
affected_vehicle_count
```

### 4.3 Recovery metrics

```text
mean_RD_candidate
mean_RD_selected
mean_RD_pred
mean_RD_realized
RD_before_action
RD_after_action
RD_delta
max_RD
RD_per_served_demand
recovery_time_estimate
post_merge_speed_drop
outflow_loss_proxy
required_rear_deceleration
```

### 4.4 Safety metrics

```text
min_realized_gap
min_predicted_gap
min_TTC
DRAC
min_surrogate_safety_margin
physical_validity_failed_count
realized_invalid_event_count
unsafe_overlap_count
no_fallback_invalid_event_count
```

### 4.5 Selection explanation metrics

```text
candidate_action_count
positive_RCMV_candidate_count
selected_action_rank
selected_action_type
selected_action_id
selected_edge_id
selected_physical_gap_id
selected_P_R
selected_RD_pred
selected_C_dist
selected_Z_R
J_none
selected_J
selected_RCMV
RCMV_margin_to_second_best
theta
lambda_Z
lambda_D
lambda_C
lambda_S
lambda_Q
```

---

## 5. Baseline / Ablation 设计

### 5.1 raw_largest_gap

用途：

```text
证明 raw geometric gap 会被误导。
```

允许知道：

```text
candidate physical gaps
raw gap size
basic physical validity screen
same candidate time grid
```

不允许知道：

```text
RD
RCMV
C_dist
future realized disturbance
RPMI selected gap
```

选择规则：

```text
select candidate with largest raw_gap_size among physically feasible candidates.
```

### 5.2 fifo_feasible_gap

用途：

```text
检验简单先到先服务。
```

允许知道：

```text
demand order
physical validity
reachability
```

不允许知道：

```text
RD ranking
disturbance cost ranking
future outcomes
```

### 5.3 forced_accommodation

用途：

```text
证明强行合流成功不等于低扰动合流。
```

允许：

```text
为了服务 demand，使用上限内的 CAV acceleration / deceleration / micro-adjustment。
```

不允许：

```text
违反 physical validity；
使用 hidden fallback；
使用 RPMI 的 objective 排名；
未来知道哪条 trajectory disturbance 最低。
```

必须输出：

```text
forced action type
forced action magnitude
hard_brake_count
max_deceleration
speed_variance_delta
wave_amplitude
mainline_disturbance_cost
```

### 5.4 no_action_natural

用途：

```text
检验自然可恢复库存是否已经足够。
```

规则：

```text
只做自然 rollout 和 reservation，不做 active production action。
```

### 5.5 reservation_before_action / stale_reservation

用途：

```text
检验 action-conditioned recompute 的必要性。
```

规则：

```text
先基于 no-action state 生成 reservation，再执行 action 或滚动，不重新生成 action-conditioned reservation。
```

### 5.6 without_RD

用途：

```text
检验 RD 是否真实影响选择。
```

规则：

```text
lambda_D = 0
其他项不变。
```

期望：

```text
若 without_RD 和 full 选择相同且结果相同，RD 对主故事贡献不足。
```

### 5.7 without_Cbar / without_cost

用途：

```text
检验 C_dist 是否压制高扰动动作。
```

规则：

```text
lambda_C = 0
其他项不变。
```

期望：

```text
without_Cbar 更容易选择 forced / high-disturbance action。
```

### 5.8 without_theta

用途：

```text
检验 threshold 是否避免 tiny positive RCMV 触发无意义 action。
```

规则：

```text
theta = 0
其他项不变。
```

期望：

```text
without_theta 更容易产生 churn / low-value action。
```

### 5.9 without_conflict_blocking

用途：

```text
只作为 denominator honesty 补充，不作为低扰动主线。
```

规则：

```text
关闭 physical_gap_id / slot_group_id conflict blocking。
```

警告：

```text
该 baseline 可能虚高 service rate，必须明确标注 duplicate physical gap consumption。
```

---

## 6. Baseline fairness audit 模板

每个 baseline 必须记录：

```text
baseline_id:
same_initial_state: true/false
same_demand: true/false
same_horizon: true/false
same_candidate_time_grid: true/false
same_physical_validity_rule: true/false
same_no_hidden_fallback_rule: true/false
same_denominator_policy: true/false
uses_future_realized_outcome: true/false
uses_RPMI_only_information: true/false
allowed_information:
forbidden_information:
known_advantage:
known_limitation:
fairness_pass:
fairness_failure_reason:
```

任何 baseline 如果 `uses_future_realized_outcome=true` 或 `uses_RPMI_only_information=true`，不得用于论文性能主结论。


---

# File: 04_TARGET_SCENARIO_CARDS.md

# 04 D2.5 Target Scenario Cards

## 总原则

D2.5 不是跑更多普通 rolling 场景，而是设计 deterministic target scenarios，让 baseline 犯论文理论预言的错误，让 RPMI-CMV 有机会展示机制优势。

每个 scenario 必须包含：

```text
scenario_id
scenario_design_id
deterministic_case_id
random_seed_optional
theory_target
construction_principle
mechanism_target
diagnostic_contrast
controlled_knobs
parameter_ladder_id
initial_state_pattern
baseline_expected_behavior
RPMI_expected_behavior
required_metrics
minimum_activation_gate
pass_pattern
fail_pattern
failure_interpretation
anti_cherry_picking_rule
held_out_variant_rule
trace_join_requirements
```

## 原则化诊断场景构造语法

D2.5 diagnostic scenarios must be constructed from mechanism principles, not random seeds.

不要写：

```text
Seed diagnostic scenarios
```

应写：

```text
Principled Diagnostic Scenario Construction
```

这里的 `random_seed_optional` 只用于复现，不用于生成理论靶场。场景是机制触发器；每个场景必须说明它要激活什么理论机制、让哪个 baseline 犯什么预期错误、让 full RPMI-CMV 通过什么低扰动 / 可恢复 / action-conditioned 选择体现差异。

每个 scenario card 必须至少声明：

```text
scenario_design_id
construction_principle
mechanism_target
diagnostic_contrast
controlled_knobs
expected_baseline_failure
expected_full_behavior
minimum_activation_gate
anti_cherry_picking_rule
held_out_variant_rule
```

推荐 controlled knobs：

```text
raw_gap_contrast:
  Gap A raw size > Gap B raw size

closing_rate_contrast:
  Gap A rear vehicle closing rate > Gap B rear vehicle closing rate

ramp_timing_mismatch:
  Gap A ramp timing mismatch > Gap B ramp timing mismatch

forced_action_magnitude:
  forced baseline requires rear braking / front acceleration

natural_slot_availability:
  no_action has valid Gap B or has no valid slot depending on scenario family

near_miss_margin:
  candidate edge is slightly below physical validity threshold

follower_response_sensitivity:
  disturbance metrics must cover affected following vehicles

churn_pressure:
  rolling recompute can create supersede / switch / stale risk
```

反 cherry-picking 规则：

```text
1. 先声明 parameter ladder，再运行；不能只保留成功参数。
2. 每个 ladder step 的失败也要写入 co_design_iteration_log.csv。
3. 如果所有 variant 都选同一个 gap，场景诊断力不足，不能进入 locked evaluation。
4. 如果 forced_accommodation 不产生可测 disturbance，先分类为 metric / simulator / scenario 问题。
5. 如果 final evaluation 失败，不允许现场改 scenario；只能输出 failure classification。
```

---

# P0 Scenario：D25-DECISIVE-RAW-GAP-FORCED-TRAP

## 1. 理论目标

同时验证三件事：

```text
raw geometric largest gap may be misleading；
forced accommodation may merge successfully but at high disturbance；
RPMI-CMV should prefer a recoverable lower-disturbance gap/action。
```

也就是论文主线：

```text
raw geometric gap != useful merge slot；
successful merge != low-disturbance merge；
RCMV / RD / C_dist should select low-disturbance recoverable slot。
```

## 2. 初始状态设计

### 2.1 结构要求

在目标外侧车道制造两个候选 gap：

```text
Gap A:
  geometrically large
  high closing rate
  poor ramp timing
  requires rear CAV forced deceleration to keep safe
  predicted RD high
  realized disturbance high if selected

Gap B:
  geometrically smaller
  stable relative speed
  better ramp timing
  lower predicted RD
  lower realized disturbance
```

### 2.2 可作为第一版尝试的参数模板

坐标方向按项目 simulator 实际定义调整。这里给的是相对关系，不是必须固定数值。

```yaml
target_lane: outer
horizon_s: 12
candidate_merge_times_s: [3, 4, 5, 6, 7, 8]
vehicle_length_m: 5

mainline_vehicles:
  # Gap A between A_front and A_rear
  - id: A_front
    lane: outer
    x_m: 115
    v_mps: 20
    type: HDV_or_CAV
  - id: A_rear
    lane: outer
    x_m: 45
    v_mps: 30
    type: CAV
    note: "fast rear vehicle, high closing rate; forced baseline may brake this vehicle"

  # Gap B between B_front and B_rear
  - id: B_front
    lane: outer
    x_m: 20
    v_mps: 22
    type: HDV_or_CAV
  - id: B_rear
    lane: outer
    x_m: -18
    v_mps: 21.5
    type: CAV_or_HDV
    note: "stable smaller gap"

ramp_vehicles:
  - id: r0
    x_m: -70
    v_mps: 18
    target_merge_window_s: [4.0, 6.0]
    type: CAV_or_guided_ramp_vehicle
```

### 2.3 调整规则

如果 raw baseline 不选 Gap A：

```text
增大 Gap A raw size；
减小 Gap B raw size；
保持 Gap A closing rate 高。
```

如果 forced baseline 不产生明显扰动：

```text
提高 A_rear speed；
缩短安全裕度；
增加 forced braking magnitude；
扩大 follower propagation window。
```

如果 RPMI-CMV 不选 Gap B：

```text
检查 RD_pred / C_dist 是否参与 selection；
提高 lambda_D / lambda_C；
检查 Gap B reachability / validity；
检查 Gap A RD_pred 是否真的高。
```

## 3. Baseline 行为

### raw_largest_gap

应选择 Gap A，因为几何 gap 最大。

### forced_accommodation

应尝试通过强制 rear CAV deceleration 或 front acceleration 让 Gap A 可服务。

### no_action_natural

用于判断自然库存是否足够。

### without_RD

可能仍选择 Gap A，因为没有 recovery debt 惩罚。

### without_Cbar

可能选择高扰动 action，因为 cost 惩罚不足。

### without_theta

可能为了 tiny RCMV 触发 action，增加 churn 或扰动。

## 4. RPMI-CMV 预期行为

```text
选择 Gap B；
或选择与 Gap B 相关的低扰动 action-conditioned variant；
或选择 none，如果所有 active action 的 RCMV <= theta 且自然 Gap B 可服务。
```

## 5. 必需输出字段

```text
raw_selected_gap_id
forced_selected_gap_id
rpmi_selected_gap_id
raw_gap_size_A
raw_gap_size_B
closing_rate_A
closing_rate_B
RD_pred_A
RD_pred_B
C_dist_pred_A
C_dist_pred_B
selected_action_id
selected_edge_id
reservation_id
realized_event_id
merge_success_rate_over_demand
realized_unserved_demand_rate
hard_brake_count
max_deceleration
mean_abs_acceleration
speed_variance_delta
max_wave_amplitude
mainline_disturbance_cost
RD_realized
min_TTC
min_realized_gap
can_join_full_chain
```

## 6. Pass pattern

强支持：

```text
RPMI-CMV demand service >= raw_largest_gap demand service - small_tolerance；
RPMI-CMV demand service >= forced_accommodation demand service - small_tolerance；
RPMI-CMV RD_realized < raw / forced；
RPMI-CMV mainline_disturbance_cost < forced；
RPMI-CMV hard_brake_count <= forced；
RPMI-CMV max_deceleration magnitude < forced；
RPMI-CMV min_TTC >= forced；
selected_action chain can join realized metrics。
```

中等支持：

```text
RPMI-CMV service 相同，至少 2 个 disturbance / recovery / safety 指标明显更好；
或 RPMI-CMV service 略低，但避免 unsafe / duplicate / high-disturbance outcome，且论文按 trade-off 写。
```

## 7. Fail pattern

```text
F1: RPMI-CMV 也选 Gap A。
F2: RPMI-CMV 选 Gap B，但 realized disturbance 不低。
F3: raw / forced 和 RPMI 结果几乎相同。
F4: without_RD / without_Cbar / without_theta 和 full 完全相同。
F5: selected_action 无法 join realized_event。
F6: forced baseline 不管怎样都不产生扰动差异。
```

## 8. 失败解释

| Fail | 可能原因 | 下一步 |
|---|---|---|
| F1 | RD / C_dist 没参与 selection；lambda 不合理；Gap A trap 不够强 | theory-to-metric audit + objective calibration |
| F2 | RD 定义与 realized outcome 脱节 | 重定义 RD，分 predicted_RD / realized_RD |
| F3 | scenario 没打中理论 | 重设 closing rate / timing / safety margin |
| F4 | RD / Cbar / theta 没有边际贡献 | objective 或实现有问题 |
| F5 | trace schema 不足 | 先修 join，不做 claim |
| F6 | simulator / metric sensitivity 不足 | 先补 follower response / acceleration trace / wave metrics |

---

# P1 Scenario：D25-BAD-ACTION-SUPPRESSION

## 1. 理论目标

验证：

```text
RCMV / C_dist / theta 不是为了盲目创造 gap；
当 action 只带来很小 inventory / RD 改善，却造成高主线扰动时，
RPMI-CMV 应选择 none 或更低成本 action。
```

## 2. 初始状态

构造一个已经有可用自然 slot 的场景：

```text
no_action 下已有一个可服务 Gap B；
另一个 action 可以把 Gap A 变得更大或更早，但需要显著 braking / acceleration；
Z_R 改善很小或为 0；
C_dist 很高。
```

## 3. Baseline

```text
forced_accommodation 或 naive_gap_creation 执行高扰动 action。
without_Cbar 更可能执行高扰动 action。
without_theta 更可能执行 tiny positive RCMV action。
```

## 4. RPMI-CMV 预期

```text
selected_action = a0_none
或 selected_action = low_cost_action
```

## 5. Pass pattern

```text
full RPMI 选择 none / low-cost；
without_Cbar 或 without_theta 选择 high-cost；
full 的 disturbance metrics 明显更低；
demand service 不差。
```

## 6. Fail pattern

```text
full 仍选择 high-cost action；
full 选择 none 但 demand service 明显更差且无 safety/disturbance trade-off；
C_dist 与 realized disturbance 不同向。
```

---

# P1 Scenario：D25-NEAR-MISS-PRODUCTION

## 1. 理论目标

验证：

```text
RPMI-CMV 能用低扰动 action 把 currently invalid / low-quality near-miss edge 转成 useful recoverable slot。
```

## 2. 初始状态

构造：

```text
no_action 下没有 valid recoverable reservation，Z_R > 0；
某个 edge reachability 通过，但 physical width / safety margin 差少量；
front or rear boundary 是 CAV；
low-disturbance micro action 可以让该 edge valid；
forced action 也能成功但扰动更大。
```

## 3. RPMI-CMV 预期

```text
选择 positive RCMV 的 low-cost action；
baseline_validity = 0；
action_conditioned_validity = 1；
Z_R 降低；
demand merged；
disturbance 可接受。
```

## 4. 必需字段

```text
near_miss_edge_id
baseline_validity
action_conditioned_validity
baseline_Z_R
selected_Z_R
selected_RCMV
selected_C_dist
RD_pred_before
RD_pred_after
selected_action_id
reservation_id
realized_event_id
merge_success_rate_over_demand
mainline_disturbance_cost
```

## 5. Pass pattern

```text
no_action 无法服务；
RPMI low-cost action 服务成功；
forced baseline 成功但扰动更高；
trace join 完整。
```

---

# P2 Scenario：D25-PHYSICAL-GAP-CONFLICT

## 1. 理论目标

验证：

```text
系统不会通过重复消费同一个 physical gap 来虚高 demand service。
```

## 2. 初始状态

```text
两个 ramp demands；
一个 physical gap 有多个 time-expanded copies；
如果不做 conflict blocking，两个 demand 看似都能预约；
真实物理上只能服务一个。
```

## 3. RPMI-CMV 预期

```text
服务一个 demand；
另一个 demand unserved 或等待；
duplicate_gap_consumption_count = 0；
blocked_by_conflict_count > 0。
```

## 4. 论文定位

这是机制补充，不是 low-disturbance 主线。  
不要把它写成 full integer assignment validation。

---

# P2 Scenario：D25-ROLLING-STALE-PERFORMANCE

## 1. 理论目标

验证 rolling 不只是 lifecycle hygiene，也能改善性能指标。

## 2. 初始状态

```text
t0 reservation 在 t1 因 gap compression / timing mismatch 变 stale；
stale_reservation baseline 继续执行，产生 failure 或 high disturbance；
rolling action-conditioned recompute 取消并重新分配，demand outcome 或 disturbance 更好。
```

## 3. Pass pattern

```text
rolling 能暴露 stale；
demand return / reassign 可追；
rolling 相比 stale_reservation 有更低 unserved / lower disturbance / higher safety margin；
不是 hidden fallback。
```

## 4. Fail pattern

```text
rolling 只产生 churn，没有性能收益；
recompute high churn/unserved 重现；
需要审 theta / hysteresis / Q_churn。
```


---

# File: 05_DECISIVE_EXPERIMENT_PROTOCOL.md

# 05 决定性实验协议：D25-DECISIVE-RAW-GAP-FORCED-TRAP

## 0. 为什么它是最关键实验

这个实验一次性打中论文主故事：

```text
raw geometric gap 不等于 useful merge slot；
forced accommodation 成功率高不等于低扰动；
RPMI-CMV 的 RD / C_dist / RCMV 应该把选择推向 recoverable low-disturbance slot。
```

如果这个实验都打不出来，先不要进入 Wave 9。  
如果它能打出来，论文就有了 target-regime deterministic evidence 的核心图表。

---

## 1. 实验对象

本协议只负责 Evaluation Lock 之后的 final evidence。Calibration sweep 必须已经在 Objective–Diagnostic Scenario Co-Design Loop 中完成。

红线：

```text
After Evaluation Lock, Codex may run sensitivity reporting only as secondary analysis.
It must not change the locked objective, scenarios, baselines, metrics, or pass/fail criteria.
If the locked decisive experiment fails, do failure classification without tuning.
```

比较：

```text
full_RPMI_reconstructed_objective
legacy_RPMI_objective
raw_largest_gap
forced_accommodation
no_action_natural
without_RD
without_Cbar
without_theta
reservation_before_action / stale_reservation
```

最小可运行集合：

```text
full_RPMI_reconstructed_objective
raw_largest_gap
forced_accommodation
without_RD
without_Cbar
without_theta
```

---

## 2. 实验流程

### Step 0：Verify lock package

先确认以下 lock 文件存在并一致：

```text
LOCKED_OBJECTIVE.md
LOCKED_SCENARIOS.md
LOCKED_BASELINES.md
LOCKED_METRICS.md
LOCKED_PASS_FAIL_CRITERIA.md
run_manifest.json
```

如果缺失任一 lock 文件，不进入 final experiment。

### Step 1：Sanity check locked scenario

确认：

```text
1. 场景中存在 Gap A 和 Gap B。
2. Gap A raw_gap_size > Gap B raw_gap_size。
3. Gap A closing_rate > Gap B closing_rate。
4. Gap A RD_pred > Gap B RD_pred。
5. Gap A forced action 会产生更高 disturbance。
6. Gap B reachable and physically valid 或可被 low-cost action-conditioned valid。
```

如果这些不满足，不要现场调 scenario；输出 failure classification，并回到 co-design 阶段。

### Step 2：Run no_action_natural

目的：

```text
判断自然可恢复库存是否已经足够。
```

输出：

```text
no_action_Z_R
no_action_merge_success
no_action_RD_realized
no_action_disturbance
```

解释：

```text
如果 no_action 已经和 RPMI 一样好，场景可能太容易。
```

### Step 3：Run raw_largest_gap

预期：

```text
raw 选择 Gap A。
```

如果 raw 不选 Gap A，场景没有形成 raw-gap trap。

### Step 4：Run forced_accommodation

预期：

```text
forced 能让 demand merge；
但 hard_brake / max_deceleration / speed_variance / wave / disturbance 高。
```

如果 forced 不产生扰动，先审 simulator / metric sensitivity。

### Step 5：Run full RPMI with locked objective

预期：

```text
full 选择 Gap B 或 low-cost action-conditioned Gap B variant；
service 不差；
disturbance / RD / safety 更好；
trace join 完整。
```

### Step 6：Run locked ablations

```text
without_RD:
  如果它选择 Gap A 或高 RD gap，说明 RD 有贡献。

without_Cbar:
  如果它选择 high-disturbance forced action，说明 C_dist 有贡献。

without_theta:
  如果它触发 tiny positive RCMV action 或 churn，说明 theta 有贡献。
```

### Step 7：Run locked sensitivity reporting

这一步只能报告 locked objective 附近的敏感性，不能改变最终证据使用的 objective / scenario / baseline / metric / pass-fail rule。

禁止把 sensitivity / calibration run 当成 final evidence。

```text
lambda_D
lambda_C
lambda_S
lambda_Q
theta
selected_gap
selected_action
RD_realized
mainline_disturbance_cost
hard_brake_count
max_deceleration
speed_variance_delta
max_wave_amplitude
min_TTC
pass_flag
fail_reason
locked_config_id
is_secondary_sensitivity
```

### Step 8：Build final evidence table

最小论文表格：

| variant | selected gap/action | service | RD_realized | hard brake | max decel | speed var delta | wave | disturbance cost | min TTC | join |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|

### Step 9：Failure classification without tuning

如果 final evidence 不支持主故事，不允许现场调参。只能输出：

```text
failure_type:
  - revise_objective
  - revise_metric
  - revise_scenario
  - revise_baseline
  - revise_implementation
  - simulator_sensitivity_insufficient
  - insufficient_trace_join
  - do_not_claim_performance

failed_locked_item:
evidence_file:
required_next_phase:
```

---

## 3. 通过标准

### Strong support

满足：

```text
1. raw_largest_gap 选择 Gap A。
2. forced_accommodation 服务成功或接近成功，但 disturbance 高。
3. full RPMI 选择 Gap B / low-cost variant。
4. full RPMI service 不差，或 service trade-off 可以用 safety / disturbance 解释。
5. full RPMI 至少两个 realized disturbance / recovery / safety 指标明显优于 raw/forced。
6. without_RD / without_Cbar / without_theta 至少一个 ablation 破坏选择或结果。
7. trace join 完整。
```

### Qualified support

满足：

```text
1. full RPMI 确实降低 disturbance / RD，但 service 略低；
2. 或 full RPMI 只在部分指标胜出；
3. 或 ablation 差异存在但 effect size 小；
4. 或 scenario 需要较强参数才能显现。
```

论文写法：

```text
targeted deterministic evidence provides qualified support；
performance gains are scenario-dependent。
```

### No support / hold

出现任一核心问题：

```text
1. full RPMI 与 raw/forced 选择和结果无差异。
2. RD_pred 低但 RD_realized / disturbance 不低。
3. C_dist 低但 realized disturbance 高。
4. positive RCMV 不能 join outcome。
5. ablation 与 full 完全一样。
6. baseline fairness 不成立。
7. forced baseline 无法产生可测扰动差异。
```

---

## 4. 指标阈值建议

如果 simulator 单位和尺度稳定，可以使用：

```text
relative_improvement >= 10%：可称为 visible reduction
relative_improvement >= 20%：可称为 clear reduction
relative_improvement < 10%：只写 directionally lower，不写 strong
```

应用指标：

```text
mainline_disturbance_cost
RD_realized
max_deceleration magnitude
speed_variance_delta
max_wave_amplitude
hard_brake_count
```

安全指标不能只看改善百分比：

```text
min_TTC 必须不低于 safety threshold；
min_realized_gap 必须非负并满足 margin；
invalid_or_unsafe_event_count 必须不高于 baseline，最好为 0。
```

如果 simulator 指标尺度不稳定，先不要使用固定阈值。用排序、方向、组件分解和原始 trace 解释。

---

## 5. 失败拆解树

### Case A：raw 和 full 都选 Gap A

检查顺序：

```text
1. Gap A 的 RD_pred 是否真的高？
2. C_dist 是否真的计入 action cost？
3. lambda_D / lambda_C 是否太低？
4. Gap B 是否 reachability / validity 失败？
5. RCMV selection 是否真的使用了 reconstructed objective？
```

### Case B：full 选 Gap B，但 disturbance 不低

检查顺序：

```text
1. RD_pred 与 RD_realized 是否不同向？
2. C_dist_pred 与 disturbance_realized 是否不同向？
3. simulator 是否记录 follower braking / speed wave？
4. merge execution 是否使用了 hidden fallback？
5. Gap B 是否其实造成 ramp acceleration / insertion disturbance？
```

### Case C：forced baseline 不高扰动

检查顺序：

```text
1. forced action magnitude 是否足够？
2. follower response 是否被模拟？
3. hard brake threshold 是否太宽？
4. speed variance / wave window 是否覆盖受影响车辆？
5. 当前 simulator 是否太简化，无法表达主线扰动？
```

### Case D：without_RD / without_Cbar / without_theta 和 full 一样

解释：

```text
objective 项没有边际贡献；
场景 trade-off 不够强；
或者实现中 ablation 没有真正关闭对应项。
```

下一步：

```text
增强场景 trade-off；
打印 action_value_decomposition；
检查 J components。
```

### Case E：positive RCMV 最终 unserved

解释：

```text
local objective myopic；
reservation churn / stale risk 未惩罚；
theta / hysteresis 不足；
action-conditioned rollout 与 realized rollout 脱节。
```

下一步：

```text
加入 Q_churn；
提高 theta；
加入 active guidance lock / switching hysteresis；
检查 reachability / survival uncertainty。
```

---

## 6. 论文图表建议

如果实验通过，建议生成：

```text
Figure 1: Raw gap size vs selected useful slot, Gap A / Gap B schematic.
Figure 2: Objective decomposition bar chart for candidates and baselines.
Figure 3: Realized disturbance metrics by variant.
Figure 4: Trace chain: action -> edge -> reservation -> realized event -> metrics.
Table 1: Baseline comparison.
Table 2: Ablation comparison.
Table 3: Failure / boundary cases.
```

不建议先画大而散的 multi-scenario average。先把决定性机制讲清楚。


---

# File: 06_PAPER_CLAIM_DECISION_TREE.md

# 06 D2.5 结果下论文如何处理

## 0. 论文策略原则

不要再把当前状态理解为“只能降级”。正确策略是：

```text
先通过 D2.5 把论文故事闭合；
闭合成功就升级成 target-regime deterministic evidence；
闭合部分成功就 qualified；
闭合失败就诚实重构 objective / metric / scenario / theory。
```

---

# 1. 如果 D2.5 强支持理论

## 1.1 满足条件

```text
Raw-Large-Gap Trap 中：
  raw_largest_gap 选择几何大但 high-RD / high-disturbance gap；
  RPMI-CMV 选择 lower-disturbance recoverable gap/action；
  demand service 不差或 trade-off 可解释；
  realized RD / hard brake / wave / disturbance 更低；
  trace join 完整。

Forced-Accommodation 中：
  forced baseline merge success 相近；
  但 hard brake / max decel / wave / disturbance 更差。

Ablation 中：
  without_RD / without_Cbar / without_theta 至少一个破坏选择或结果。

Near-Miss / Bad-Action 中：
  RPMI-CMV 能生产 low-disturbance slot；
  或拒绝高扰动低收益 action。
```

## 1.2 论文可以写

英文：

> In deterministic target scenarios, RPMI-CMV's recoverability-aware, action-conditioned, cost-aware reservation avoids misleading raw geometric gaps and reduces recovery debt or mainline disturbance compared with raw-gap and forced-accommodation baselines.

中文：

> 在确定性靶场中，RPMI-CMV 能避免 raw geometric gap 的误导，并在与粗暴主线配合 baseline 服务水平相近时降低恢复债或主线扰动。

## 1.3 可以加强的 claim

```text
recoverability-aware selection 优于 raw-gap selection；
RCMV / cost-aware action selection 可抑制不必要主线扰动；
near-miss production 在 target regime 中有效；
action-conditioned reservation 在 stale / near-miss 场景中优于 stale reservation；
conservative conflict blocking 避免 duplicate physical gap consumption。
```

## 1.4 仍不能写

```text
stochastic robustness；
multi-seed generalization；
full conflict-aware rolling integer assignment 已验证；
SUMO / high-fidelity generalization；
universal optimality；
所有交通密度 / 所有 CAV penetration 下有效。
```

## 1.5 Wave 9 何时进入

D2.5 strong support 后进入 Wave 9。  
此时 Wave 9 的问题变成：

```text
已成立的 deterministic low-disturbance mechanism
在 stochastic IDM noise 下是否稳健？
```

---

# 2. 如果 D2.5 部分支持 / mixed

## 2.1 典型情况

```text
RPMI 在 raw-gap trap 中赢，但 forced baseline 差异小；
或 bad-action suppression 通过，但 near-miss production 不稳定；
或 disturbance 指标方向对，但 effect size 小；
或 service 略低，需要 trade-off 解释；
或 ablation 只证明 Cbar 有用，RD 不明显。
```

## 2.2 论文写法

英文：

> Targeted deterministic evidence provides qualified support for the proposed mechanism, while performance gains remain scenario-dependent.

中文：

> 定向确定性证据为该机制提供了有限支持，但性能收益具有场景依赖性。

## 2.3 Claim 调整

| 原强 claim | 改成 |
|---|---|
| reduces speed waves / hard braking | can reduce in designed target scenarios |
| robustly improves merge success | improves traceability and may improve service in selected target regimes |
| RCMV reliably selects low-disturbance actions | RCMV provides an auditable action-value criterion; realized benefits are scenario-dependent |
| full conflict-aware assignment validated | conservative physical-gap conflict blocking observed |

## 2.4 正例和边界写法

把通过的 scenario 写成 positive mechanism cards：

```text
Raw-Large-Gap Trap
Bad-Action Suppression
Near-Miss Production
```

把失败或风险写成 boundary cards：

```text
D2-ACTION-CONDITIONED-RECOMPUTE high churn
negative control
all-lanes congested
low CAV penetration
simulator-insensitive forced baseline
```

---

# 3. 如果 D2.5 不支持理论

## 3.1 不要立即判论文完了

按顺序判断：

```text
1. scenario 是否真的命中理论？
2. baseline 是否公平？
3. disturbance metrics 是否敏感？
4. RD / C_dist 是否进入 selection？
5. RCMV 是否 myopic？
6. simulator 是否表达不了速度波 / 急刹 / 扰动传播？
7. 理论定义是否需要重写？
```

## 3.2 最可能需要修的对象

### RD

如果：

```text
RD_pred 低，但 hard brake / wave / disturbance 高；
```

则：

```text
把 RD 拆成 predicted_RD 和 realized_RD；
重定义 RD components；
不要再把 RD 直接等同于 realized low disturbance。
```

### C_bar / C_dist

如果：

```text
C_bar 只是 action effort；
与 mainline disturbance 不同向；
```

则：

```text
改名为 action_effort_cost；
或升级为 C_dist，加入 induced braking / speed variance / wave / affected vehicles。
```

### J(a)

如果：

```text
Z_R 压倒一切，导致高扰动服务；
```

则：

```text
重新归一化；
提高 lambda_C / lambda_S；
加入 service-disturbance Pareto 或 hard safety constraints。
```

### RCMV / theta / hysteresis

如果：

```text
positive RCMV 导致 churn / unserved；
```

则：

```text
提高 theta；
加入 switching hysteresis；
加入 Q_churn；
区分 local RCMV 与 commitment-aware RCMV。
```

### conflict model

如果：

```text
conservative blocking 太保守；
```

则：

```text
论文明确 prototype limitation；
或实现 conflict window / small MILP；
但不要让它抢 low-disturbance 主线。
```

## 3.3 论文是否还值得继续

值得，但定位改成：

> A traceable recoverable perishable slot inventory framework with honest failure accounting and conservative conflict blocking.

这时不能主张 low-disturbance superiority，只能主张 framework / diagnostic mechanism。

---

# 4. 如果 D2.5 显示 simulator 太弱

## 4.1 判断标准

出现以下情况时，不要直接说理论失败：

```text
forced_accommodation 无法产生 hard brake / deceleration / wave 差异；
speed variance 对强 braking 不敏感；
follower response 没有传播；
mainline_disturbance_cost 近乎常数；
near-miss insertion 对 downstream metrics 无影响。
```

## 4.2 先加强 Python simulator

优先补：

```text
follower car-following response
acceleration / deceleration trace
jerk trace
speed variance before / after
local wave amplitude
downstream outflow proxy
min TTC / DRAC
multi-vehicle propagation window
```

## 4.3 何时进入 SUMO

只有在 Python simulator 已经能表达基本扰动，但 reviewer 仍可能质疑真实性时，再进入 SUMO / calibrated microscopic simulation。

不要用 SUMO 来替代 D2.5 的逻辑闭环。  
SUMO 是外部验证，不是理论-指标-实验闭环的第一步。

---

# 5. 论文表述红线

## 可以写

```text
The prototype supports auditable rolling reservation lifecycle.
Stale / expired reservations and demand return can be traced.
Conservative physical-gap conflict blocking is observed.
Failures are not hidden by fallback repair in the reviewed traces.
In deterministic target scenarios, RPMI-CMV can reduce recovery debt or mainline disturbance compared with raw-gap / forced baselines, if D2.5 supports it.
```

## 不要写

```text
RPMI-CMV universally reduces traffic waves.
RPMI-CMV robustly improves merge success.
Full conflict-aware rolling integer assignment is validated.
Multi-seed diversity is demonstrated.
Stochastic robustness is demonstrated.
failed_reservation_rate=0.0 means demand success.
```

---

# 6. 最终摘要句模板

## Strong support

> D2.5 closes the main theory-evidence loop in deterministic target regimes: RPMI-CMV selects recoverable, lower-disturbance slots/actions and reduces realized recovery/disturbance metrics compared with raw-gap and forced-accommodation baselines.

## Mixed

> D2.5 provides qualified deterministic support: the mechanism works in selected target scenarios, but performance benefits depend on scenario structure and metric sensitivity.

## No support

> D2.5 does not support the current low-disturbance superiority claim. The paper should be repositioned as a traceable recoverable slot inventory framework unless RD / C_dist / RCMV and scenario design are revised.

## Simulator weak

> D2.5 is inconclusive because the current simulator cannot express the disturbance mechanisms required to test the theory. The next step is simulator metric sensitivity hardening, not stochastic robustness.


---

# File: 07_CODEX_PROMPT_SET_v2_闭环版.md

# 07 Codex Prompt Set v2：闭环版，可逐条复制给 Codex

## 使用原则

这组 Prompt 不是一次性流水线，而是一个带 checkpoint 的科研闭环。

核心目标是完成 D2.5：

```text
Theory-Evidence Alignment and Targeted Performance Validation.
```

也就是判断并尽量闭合：

```text
RPMI-CMV 在 deterministic target regimes 中，
是否能通过 recoverability-aware / disturbance-aware / action-conditioned selection，
相比 raw-gap 和 forced-accommodation baselines，
降低 recovery debt、mainline disturbance、hard brake、speed wave，
同时保持 demand service 不差或 trade-off 可解释。
```

新版顺序：

```text
Prompt 0 -> Prompt 1 -> Prompt 2 -> Prompt 3 -> Prompt 4 -> Prompt 5 -> Prompt 6
```

但要注意：

```text
Prompt 3 是核心 co-design loop，不是单次 objective 修改。
Prompt 4 是 lock，不是继续调参。
Prompt 5 是 locked final evidence，不允许边看结果边改参数。
```

---

# Prompt 0：Repo Inspection / 先摸清代码，不允许幻觉式修改

请你作为 RPMI-CMV 项目的科研工程执行 agent，先完整检查 repo。

你必须定位：

```text
simulator
scenario generator
policy / objective
RD / C_bar / C_dist / RCMV / theta
metric computation
trace join
baseline implementation
experiment entry scripts
outputs / CSV / JSON / plots
```

要求：

```text
1. 不要修改代码。
2. 不要猜测不存在的模块。
3. 如果文件缺失，创建 missing_input_register.md。
4. 输出 repo_inspection_summary.md。
```

必须回答：

```text
1. RD 当前在哪里实现？
2. C_bar / C_dist 当前在哪里实现？
3. RCMV 当前在哪里影响 selected_action？
4. objective 当前公式是什么？
5. scenario 当前如何生成？
6. baselines 当前有哪些？
7. realized metrics 当前有哪些？
8. selected_action 是否能 join 到 realized_event？
9. 当前 D2.5 最大缺口是什么？
```

输出到：

```text
outputs/d2_5_theory_alignment/repo_inspection_summary.md
outputs/d2_5_theory_alignment/missing_input_register.md
```

执行完后停止，等待人工审查。

---

# Prompt 1：Theory-to-Code Audit / 理论对象到代码对象审计

请对照论文主故事审计以下对象：

```text
Z_R
S_R
P_R
RD
C_bar
C_dist
J
RCMV
theta
selected_action
selected_gap
reservation
realized_event
disturbance metrics
recovery metrics
safety metrics
```

每个对象必须标明：

```text
1. 理论含义是什么？
2. 当前代码函数或类在哪里？
3. 当前 CSV / JSON 字段在哪里？
4. 是否参与 selected_action？
5. 是否能 join 到 realized outcome？
6. 是否只是 proxy？
7. 是否需要重定义或补记录？
```

红线：

```text
如果 J / RD / C_bar / RCMV 无法定位到代码或 CSV，
不要跑实验，先修映射。
```

输出：

```text
outputs/d2_5_theory_alignment/theory_metric_audit.md
outputs/d2_5_theory_alignment/missing_metric_register.md
```

执行完后停止，等待人工审查。

---

# Prompt 2：Trace + Metric Schema / 建立 objective 到 realized outcome 的证据链

请实现或补齐 trace schema 和 metric schema，使每一次 decision 都能闭环。

必须能记录：

```text
candidate gaps
candidate actions
每个 candidate 的 Z_R / RD_pred / C_dist_pred / safety / churn / J / RCMV
selected_action
selected_gap
reservation
realized_event
realized disturbance / recovery / safety metrics
```

必须输出以下表：

```text
candidate_gap_table.csv
action_value_decomposition.csv
trace_join_table.csv
disturbance_metrics.csv
recovery_metrics.csv
safety_metrics.csv
demand_outcome_metrics.csv
reservation_lifecycle_metrics.csv
```

最低要求：

```text
1. selected_action 可以 join 到 selected_edge / selected_gap。
2. selected_gap 可以 join 到 reservation。
3. reservation 可以 join 到 demand。
4. demand 可以 join 到 realized_event。
5. realized_event 可以 join 到 hard_brake / max_deceleration / speed_wave / min_TTC / RD_realized。
```

红线：

```text
如果 selected_action 无法 join 到 realized_event 和 metric change，
不要进入决定性实验，也不要写 performance support。
```

输出：

```text
outputs/d2_5_theory_alignment/metric_schema_plan.md
outputs/d2_5_theory_alignment/trace_join_schema_plan.md
outputs/d2_5_theory_alignment/gate_D2_5_input/trace_join_table.csv
```

执行完后停止，等待人工审查。

---

# Prompt 3：Objective–Diagnostic Scenario Co-Design Loop / 目标函数—诊断场景共同设计闭环

这是 D2.5 最重要的阶段。

你不能把 objective reconstruction 和 scenario design 分开执行。你必须让它们互相校准：

```text
原则化构造诊断场景
↓
用当前 objective 跑 full / baseline / ablation
↓
看失败模式
↓
判断失败来自 objective、scenario、metric、baseline、implementation 还是 simulator
↓
只根据具体失败模式修改 RD / C_bar / θ / λ / churn 或诊断场景参数
↓
再跑诊断场景
↓
确认机制是否真的被激活
```

## 3.1 自主执行时间要求

你应该独立执行一个充分的 co-design loop。

要求：

```text
minimum_wall_clock_target: 如果运行环境允许，至少连续推进 2 小时以上
minimum_meaningful_iterations: 6
maximum_iterations: 20
minimum_scenario_families: P0 + two P1
minimum_variants_per_iteration:
  - full_RPMI_reconstructed_objective
  - raw_largest_gap
  - forced_accommodation
  - without_RD
  - without_Cbar
  - without_theta
optional_variants:
  - no_action_natural
  - legacy_objective
  - without_churn
  - stale_reservation
```

如果 repo 运行过慢，你可以先使用最小 deterministic case，但不能跳过 failure diagnosis。

## 3.2 不要使用随机 seed 设计场景

不要写 “seed diagnostic scenarios”。

请改为：

```text
Principled Diagnostic Scenario Construction
```

中文含义：

```text
原则化诊断场景构造。
```

这里的 seed 只能作为 reproducibility seed 或 deterministic case id，不是场景生成方法。

场景必须根据机制原则构造，而不是随机碰运气。

## 3.3 场景构造原则

每个 diagnostic scenario 必须明确：

```text
scenario_design_id
scenario_family
mechanism_target
construction_principle
diagnostic_contrast
parameter_ladder_id
expected_baseline_failure
expected_full_behavior
anti_cherry_picking_rule
trace_join_requirements
```

至少构造并迭代以下机制靶场：

### P0：Raw-Gap / Forced-Accommodation Trap

必须形成：

```text
Gap A:
  raw_gap_size larger
  closing_rate higher
  ramp timing worse
  predicted RD higher
  forced action disturbance higher

Gap B:
  raw_gap_size smaller
  relative speed stable
  ramp timing better
  predicted RD lower
  realized disturbance lower
```

诊断目标：

```text
raw_largest_gap 应选择 Gap A；
forced_accommodation 应能服务但扰动高；
full RPMI-CMV 应选择 Gap B / low-cost variant / none；
without_RD 或 without_Cbar 应出现退化。
```

### P1：Bad-Action Suppression

必须形成：

```text
no_action 下已有自然可服务 slot；
某个 active action 只带来很小 Z_R / RD 改善；
但造成明显 C_dist / hard brake / wave。
```

诊断目标：

```text
full 应选择 none 或 low-cost action；
without_Cbar / without_theta 更容易选择 high-cost action。
```

### P1：Near-Miss Production

必须形成：

```text
no_action 下 slot 差一点 invalid；
low-disturbance micro action 可以让它变成 valid recoverable slot；
forced action 也能服务但扰动更高。
```

诊断目标：

```text
full 应选择 positive RCMV 的 low-cost action；
no_action 无法服务；
forced 可服务但 disturbance 更高。
```

## 3.4 每轮迭代必须做的事

每一轮必须执行：

```text
1. 选择一个 diagnostic scenario family。
2. 说明本轮 mechanism target。
3. 运行 full / baseline / ablation。
4. 输出 selected_gap / selected_action。
5. 输出 action_value_decomposition。
6. 输出 realized metrics。
7. 判断机制是否激活。
8. 诊断失败类型。
9. 提出一个具体修改。
10. 执行修改。
11. 复跑最小验证。
12. 写 keep / revert 决策。
```

每一轮必须写入 `co_design_iteration_log.csv`，最低字段为：

```text
iteration_id
scenario_design_id
scenario_family
mechanism_target
failure_observed
failure_type
hypothesis
changed_component
old_value
new_value
selected_gap_before
selected_gap_after
selected_action_before
selected_action_after
RD_pred_direction_match
C_dist_direction_match
realized_disturbance_change
ablation_sensitivity_change
keep_or_revert
reason
```

## 3.5 失败类型分类

每个失败必须归入以下类型之一：

```text
revise_objective
revise_metric
revise_scenario
revise_baseline
revise_implementation
simulator_sensitivity_insufficient
insufficient_trace_join
do_not_claim_performance
```

不要只写“效果不好”。

## 3.6 允许修改什么

在 co-design 阶段可以修改：

```text
RD_pred definition
RD component weights beta_*
C_dist definition
C_dist component weights gamma_*
lambda_D
lambda_C
lambda_S
lambda_Q
theta
churn_hysteresis
diagnostic scenario parameters
metric windows
baseline instrumentation bugs
trace join bugs
```

但必须遵守：

```text
1. 每次只根据具体 failure 修改。
2. 不允许 blind sweep。
3. 不允许只保留成功参数。
4. 不允许为每个 scenario 单独 cherry-pick 参数。
5. 不允许让 baseline 使用更差物理规则。
6. 不允许在 final evaluation scenarios 上调参。
```

## 3.7 机制激活判据

进入 Prompt 4 前，至少要回答：

```text
1. raw_largest_gap 是否稳定选择 Gap A？
2. forced_accommodation 是否服务成功或接近成功但 disturbance 更高？
3. full 是否选择 Gap B / low-cost action / none？
4. without_RD 是否更容易选择高 RD gap？
5. without_Cbar 是否更容易选择高 disturbance action？
6. without_theta 是否更容易触发 tiny positive RCMV action 或 churn？
7. RD_pred 是否与 RD_realized / disturbance 同向？
8. C_dist_pred 是否与 realized disturbance 同向？
9. selected_action 是否能 join 到 realized_event 和 metric change？
```

如果答案是否定的，不允许进入 Prompt 4 lock。

## 3.8 必须输出

```text
outputs/d2_5_theory_alignment/objective_scenario_codesign_plan.md
outputs/d2_5_theory_alignment/objective_scenario_design_register.csv
outputs/d2_5_theory_alignment/co_design_iteration_log.csv
outputs/d2_5_theory_alignment/mechanism_activation_report.md
outputs/d2_5_theory_alignment/objective_calibration_log.csv
outputs/d2_5_theory_alignment/gate_D2_5_input/ablation_comparison.csv
outputs/d2_5_theory_alignment/gate_D2_5_input/baseline_comparison.csv
outputs/d2_5_theory_alignment/gate_D2_5_input/failure_trace.csv
```

执行完后停止，输出 review packet，等待人工审查。

---

# Prompt 4：Evaluation Lock + Baseline Fairness Freeze / 最终实验锁定

现在不要继续调 objective。

请基于 Prompt 3 的结果，生成最终实验 lock package。

必须冻结：

```text
objective formula
RD_pred definition
C_dist / C_bar definition
normalization rules
lambda_Z
lambda_D
lambda_C
lambda_S
lambda_Q
theta
churn penalty / hysteresis
diagnostic scenarios
held-out evaluation scenarios
baselines
ablations
fairness rules
metrics
pass / fail criteria
random_seed_or_case_id
run manifest
```

其中：

```text
scenario_design_id: 机制设计编号，不是随机 seed。
deterministic_case_id: 锁定后的确定性 case 标识。
random_seed_optional: 只用于复现，不允许作为场景生成来源。
```

明确写入：

```text
No further objective tuning is allowed after this lock,
unless a run is declared invalid due to implementation bug.
```

baseline fairness 必须审计：

```text
same_initial_state
same_demand
same_horizon
same_candidate_time_grid
same_physical_validity_rule
same_no_hidden_fallback_rule
same_denominator_policy
uses_future_realized_outcome
uses_RPMI_only_information
```

任何 baseline 如果：

```text
uses_future_realized_outcome = true
```

或：

```text
uses_RPMI_only_information = true
```

不得用于论文性能主结论。

输出：

```text
outputs/d2_5_theory_alignment/LOCKED_OBJECTIVE.md
outputs/d2_5_theory_alignment/LOCKED_SCENARIOS.md
outputs/d2_5_theory_alignment/LOCKED_BASELINES.md
outputs/d2_5_theory_alignment/LOCKED_METRICS.md
outputs/d2_5_theory_alignment/LOCKED_PASS_FAIL_CRITERIA.md
outputs/d2_5_theory_alignment/baseline_fairness_audit.md
outputs/d2_5_theory_alignment/run_manifest.json
```

执行完后停止，等待人工审查。

---

# Prompt 5：Locked Decisive Experiment / 锁定后的决定性实验

请只使用 Prompt 4 锁定的 objective、scenarios、baselines、ablations、metrics 和 fairness rules。

禁止：

```text
1. 看 final result 后继续调 lambda。
2. 看 final result 后继续改 theta。
3. 看 final result 后继续改 scenario。
4. 只展示成功 run。
5. 把 calibration run 当成 final evidence。
```

运行：

```text
D25-DECISIVE-RAW-GAP-FORCED-TRAP
D25-BAD-ACTION-SUPPRESSION
D25-NEAR-MISS-PRODUCTION
```

最小 variant：

```text
full_RPMI_reconstructed_objective
raw_largest_gap
forced_accommodation
without_RD
without_Cbar
without_theta
```

建议 variant：

```text
no_action_natural
legacy_objective
without_churn
stale_reservation
reservation_before_action
```

必须输出：

```text
scenario_summary.csv
baseline_comparison.csv
ablation_comparison.csv
candidate_gap_table.csv
action_value_decomposition.csv
trace_join_table.csv
disturbance_metrics.csv
recovery_metrics.csv
safety_metrics.csv
failure_trace.csv
```

必须回答：

```text
1. full 是否在 P0 中避免 raw-gap trap？
2. full 是否比 forced_accommodation 更低 disturbance？
3. full 是否 service 不差，或 trade-off 可解释？
4. without_RD 是否破坏选择或结果？
5. without_Cbar 是否破坏选择或结果？
6. without_theta 是否造成 tiny-RCMV action 或 churn？
7. RD_pred / C_dist_pred 是否与 realized metrics 同向？
8. trace join 是否完整？
```

如果失败，不要现场调参。输出 failure classification。

输出：

```text
outputs/d2_5_theory_alignment/gate_D2_5_input/
outputs/d2_5_theory_alignment/human_review/decisive_experiment_review_packet.md
```

执行完后停止，等待人工审查。

---

# Prompt 6：Paper Claim Decision / 根据证据决定论文 claim

请根据 locked decisive experiment 的结果，不要根据 calibration run，生成论文 claim decision。

必须使用以下标签之一或组合：

```text
support_target_regime_theory
qualified_support_mixed
revise_objective
revise_metric
revise_scenario
revise_baseline
revise_implementation
simulator_sensitivity_insufficient
insufficient_trace_join
do_not_claim_performance
```

必须区分：

```text
1. calibration evidence
2. locked evaluation evidence
3. diagnostic support
4. final claim support
```

不能写：

```text
universal superiority
general optimality
validated rolling integer assignment
demand success based only on failed_reservation_rate = 0.0
```

必须输出：

```text
outputs/d2_5_theory_alignment/d2_5_decision_report.md
outputs/d2_5_theory_alignment/paper_claim_boundary.md
outputs/d2_5_theory_alignment/human_review/d2_5_one_page_summary.md
```

一页摘要必须包括：

```text
1. 主结论
2. P0 决定性实验结果
3. 最强支持证据
4. 最强反证或边界
5. 论文现在能写什么
6. 论文不能写什么
7. Wave 9 是否可以进入
8. 下一步唯一最重要任务
```

---

# 最小 checkpoint 规则

不要一路跑到底。至少在以下位置停止并输出 review packet：

```text
Checkpoint 0: Repo + Theory Audit 后
Checkpoint 1: Trace Schema 后
Checkpoint 2: Co-Design Loop 后
Checkpoint 3: Evaluation Lock 前
Checkpoint 4: Locked Decisive Experiment 后
Checkpoint 5: Paper Claim Decision 后
```

其中最重要的是：

```text
Checkpoint 2: Co-Design Loop 后
Checkpoint 3: Evaluation Lock 前
```

这两个 checkpoint 决定最终证据是否干净。

---

# 核心原则

一句话：

```text
用 diagnostic scenarios 调 objective；
用 locked evaluation scenarios 做最终证据；
不要把调试场和最终考场混在一起。
```
