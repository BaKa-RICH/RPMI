# Patch Wave 6A+: Deterministic Evidence Hardening v2.1 中文版

## v2.1 更新说明：denominator 与论文解释红线

本次 v2.1 的全局补丁来自 A1/A2/A3 与 B/C 类判定。

所有 evidence package、Gate 输入、论文图表和实验表格必须同时报告两类 denominator：

```text
reservation denominator:
  failed_reservation_rate = failed_reservation_count / generated_reservation_count
  generated_reservation_count = reservation_count 或 planned_reservation_count，必须显式标注

demand denominator:
  merge_success_rate_over_demand = merge_success_count / D_H
  predicted_unserved_demand_rate = predicted_unserved_demand_count / D_H
  realized_unserved_demand_rate = realized_unserved_demand_count / D_H
```

禁止把：

```text
failed_reservation_rate = 0
```

单独解释为：

```text
merge success 高
proposed 成功服务 demand
RPMI-CMV 显著提高合流成功率
```

正确解释必须区分：

```text
没有生成坏 reservation
≠ ramp demand 已被服务
≠ merge success over demand 提高
```

## 0. 本阶段定位

Wave 6A+ 不是新算法阶段。  
它是在 Wave 6A.0 的证据包卫生基础上，加强 deterministic evidence，使 Gate D0 能判断 boundary-speed V0 是否足以支撑论文主机制。

## 1. Codex 执行合约

本阶段只允许做：

```text
S2/S5/S6/S7/S8 deterministic scenario/readiness/evidence hardening
scenario manifest 补充
Gate D0 input package
summary tables
mechanism trace summaries
threshold/sensitivity 小范围补证
S5 no-action inventory 与 production claim 判别
S6_productive 子场景补证
positive RCMV hardening 与 predicted-vs-realized 审计
```

本阶段禁止：

```text
lane-change production
rolling horizon
stochastic IDM
action bundle
major algorithm redesign
为追求胜率修改 baseline 公平性
```

## 2. 本阶段核心问题

Wave 6A+ 必须回答：

```text
S2 是否证明 raw-gap illusion？
S5 是否证明 boundary-speed production 有效？
S6 是否证明 RD/recoverability 有用？
S7 是否证明 action-conditioned reservation 有用？
S8 是否证明 near-miss screening 有用？
```

如果回答不清楚，不进入 Wave 7。

## 3. 场景组定义

### S2: raw-gap illusion

目标：

```text
几何 raw gap 看似存在，但 ramp-specific reachability / safety / recoverability / matching 后不可用。
```

应观察：

```text
raw_gap_reservation 可能选中 W 大但 P_R=0 或 RD 差的 edge
RPMI-CMV 通过 P_R/RD/RCMV 避免或修复
raw_gap_illusion_count > 0
```

### S5: boundary-speed production

目标：

```text
near-miss edge 可由 front_acc/rear_dec/front_rear 轻微动作转为 reservable。
```

应观察：

```text
near_miss_edge_count > 0
candidate_action_count > 1
positive_RCMV_candidate_count > 0
selected_action_type 非 none 的比例可解释
selected_Z_R 下降或 S_R 上升
production cost 不过度

v2.1 判别：
如果 selected_action_type = none 且 selected_S_R > 0，
则该证据只能支持 inventory reservation / matching success，
不能支持 production action effectiveness。

若要支持 production action effectiveness，必须观察到：
selected_action_type != none
selected_RCMV > 0
action-conditioned inventory 相比 no-action inventory 改善
selected_Z_R 下降或 selected_S_R 上升
realized merge_success_rate_over_demand 不下降

```

### S6: RD/recoverability

目标：

```text
几何和 reachability 相似的 edge，因为 RD 不同导致不同决策质量。
```

应观察：

```text
without_rd 与 full 在 selected action/edge 或 outcome 上有差异
mean_RD_matched 变化可解释
failure 或 hard braking/wave 指标支持 RD 的必要性

v2.1 判别：
若 S6 中 RPMI-CMV selected_Z_R > 0 且 merge_success_count = 0，
则 S6 只能证明 diagnostic avoidance / invalid reservation avoidance，
不能证明 demand service improvement。

```


### S6_productive: recoverable raw-gap illusion / productive RD contrast

新增子场景目标：

```text
raw-gap baseline 会误选 invalid 或 low-recoverability slot；
no-action 下 demand 仍未服务；
boundary-speed action 能把 near-miss edge 转成 recoverable slot；
RCMV 选择非 none action；
selected_RCMV > 0；
selected_Z_R 下降；
realized merge_success_rate_over_demand 上升或至少不低于 baseline。
```

必须输出：

```text
S6_productive_manifest.json
S6_productive_aggregate_metrics.csv
S6_productive_rcmv_trace.csv
S6_productive_failure_summary.csv
```

如果 S6_productive 无法构造或结果 inconclusive，D0 不得写“boundary-speed production improves merge success”，只能写“raw-gap illusion diagnosis”。

### S7: action-conditioned reservation

目标：

```text
action 后必须重新生成 reservation； stale reservation 会产生失败、过期或收益下降。
```

应观察：

```text
rpmi_cmv 优于 without_action_conditioned_reservation
stale_reservation_count 或 stale_reservation_harm 可见
action_conditioned_gain > 0 或 failure trace 清楚解释差异
```

### S8: near-miss screening

目标：

```text
near-miss screening 降低无意义候选动作，同时保留有效 production opportunity。
```

应观察：

```text
without_near_miss 候选动作更多
计算量/invalid/rejected action 增加
full near-miss screening 不丢失主要 positive RCMV candidate
```

## 4. scenario manifest 补丁

每个 scenario manifest 必须写：

```text
scenario_id
mechanism_target
expected_failure_mode
readiness_targets
vehicle_mix
ramp_demand
seed_policy
jitter_policy
expected_boundary_types
expected_near_miss_types
expected_raw_gap_illusion
expected_rd_contrast
expected_stale_contrast
expected_screening_contrast
```

## 5. Gate D0 input package

Wave 6A+ 必须生成：

```text
gate_D0_input/
  gate_D0_manifest.json
  aggregate_metrics_completed.csv
  aggregate_metrics_readiness_fail.csv
  failure_summary_main_batch.csv
  failure_summary_readiness_fail.csv
  state_hash_fairness.csv
  scenario_mechanism_summary.csv
  baseline_comparison_summary.csv
  ablation_comparison_summary.csv
  rcmv_trace_top_actions.csv
  positive_rcmv_micro/
    positive_rcmv_manifest.json
    positive_rcmv_aggregate_metrics.csv
    positive_rcmv_failure_summary.csv
    positive_rcmv_rcmv_trace.csv
    positive_rcmv_action_evaluations.csv
    positive_rcmv_reservations.csv
  failure_trace_samples/
  trace_replay_summaries/
  paper_claim_support_table.csv
```

Gate D0 输入中必须能直接审计：

```text
failed_reservation_rate 是否与 demand 服务率分开
S5 成功是否来自 no-action inventory 还是 production action
S6 是 diagnostic avoidance 还是 demand service improvement
positive RCMV case 是否 prediction valid 且 realized valid
```

## 6. scenario_mechanism_summary.csv

字段：

```text
scenario_group
scenario_id
seed_count
completed_run_count
readiness_pass_rate
raw_gap_illusion_rate
near_miss_presence_rate
positive_rcmv_rate
selected_non_none_rate
delta_Z_R_mean
delta_S_R_mean
failed_reservation_rate
merge_success_rate_over_demand
predicted_unserved_demand_rate
realized_unserved_demand_rate
failure_rate_delta_vs_raw_gap
RD_ablation_decision_change_rate
stale_harm_rate
screening_candidate_reduction_rate
mechanism_interpretability_status
notes
```

`mechanism_interpretability_status` 枚举：

```text
clear_support
partial_support
inconclusive
contradicts_claim
```

## 7. rcmv_trace_top_actions.csv

每个 scenario/seed 至少输出：

```text
best_action
selected_action
a0_none
top_5_by_RCMV
```

用于人工检查：

```text
best RCMV 是否与 selected 一致
RCMV 正负号是否合理
J/Z/D/C 分项是否解释选择
theta 拒绝是否合理
```

## 8. sensitivity 最小要求

不做大规模 sweep，但至少对关键阈值做局部敏感性：

```text
theta
lambda_D
lambda_C
near_miss_delta_W_max
RD_max
production_width_buffer
```

输出：

```text
sensitivity_local_summary.csv
```

判断：

```text
主结论不应只在一个极窄参数点成立。
```

## 9. 小 batch 设计

建议最小：

```text
scenario groups: S2/S5/S6/S7/S8
seeds: 5 或 10
algorithms:
  fifo_no_production
  raw_gap_reservation
  density_triggered
  speed_benefit
  rpmi_cmv
  rpmi_cmv_without_rd
  rpmi_cmv_without_action_conditioned_reservation
  rpmi_cmv_without_near_miss
```

如果 runtime 太高：

```text
先每组 3 seeds 验证 trace，再扩到 5/10。
```

## 10. 本阶段验收条件

进入 Gate D0 前必须满足：

```text
Wave 6A.0 所有 evidence hygiene pass
S2/S5/S6/S7/S8 至少有 completed runs
每个 scenario group 的 mechanism_target 可由 summary 表解释
RCMV trace 对 selected action 可解释
至少 S2/S5/S6/S7/S8 中 3 个以上给出 clear_support 或 partial_support
contradicts_claim 的场景必须有 failure trace 和论文修改建议
```

## 11. 阶段输出报告模板

Codex 完成后输出：

```text
1. batch 配置
2. scenario group 覆盖
3. readiness 通过情况
4. 各 scenario group 的 mechanism evidence
5. baseline comparison
6. ablation comparison
7. sensitivity 结论
8. 失败与反例
9. 是否建议进入 Gate D0
10. 如果不建议，应该改代码、改场景还是改论文
```

## 12. v2.1 机制判别红线

### 12.1 S5 no-action inventory 判别

```text
selected_action_type = none
selected_S_R > 0
selected_Z_R = 0
```

只能支持：

```text
RPMI-CMV can exploit recoverable inventory without unnecessary production.
```

不能支持：

```text
RPMI-CMV production action creates new merge opportunities.
```

### 12.2 positive RCMV hardening

positive RCMV micro-case 必须回答：

```text
selected_RCMV > 0 是否存在？
selected_action_type != none 是否存在？
selected_Z_R 是否下降？
predicted valid 是否最终 realized valid？
若 selected_Z_R=0 但 failed_unsafe_margin，原因是 edge quality 模型偏弱，还是 execution/guidance 没接好？
```

### 12.3 hard braking / wave claim

若 hard_brake_count 与 max_wave_amplitude 没有 proposed 优势，论文不得写：

```text
RPMI-CMV reduces hard braking and speed-wave amplitude.
```

最多写：

```text
Safety and wave metrics are reported diagnostically; current deterministic V0 evidence does not establish a clear advantage.
```
