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
