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
