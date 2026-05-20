# Patch Wave 6A.0: Evidence Package Hygiene and Metric Patch v2.1 中文版

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

Wave 6A.0 不是新算法阶段。  
它是证据包卫生与指标可信度补丁。

目标是让已经实现的 Wave 6A 结果能够被论文可靠使用。

## 1. Codex 执行合约

本阶段只允许做：

```text
run/batch/evidence package 命名修复
CSV/JSON schema 稳定化
metric 补丁
failure trace join key
readiness_failed 与 completed 分层
RCMV trace 补全
stale/action-conditioned/RD/raw-gap-illusion 指标补丁
reservation denominator 与 demand denominator 双口径补丁
positive RCMV micro evidence package 纳入
failure_summary 分层命名与防覆盖
small batch reproducibility check
```

本阶段禁止做：

```text
lane-change production
rolling horizon
stochastic IDM
RCMV 公式大改
new simulator
baseline 偷用 proposed 信息
fallback repair
```

## 2. 为什么必须先做 Wave 6A.0

如果没有本补丁，后续论文会遇到这些问题：

```text
batch 文件可能覆盖
run_id 不唯一
state_hash fairness 只在局部可见
readiness_failed 与 completed 混在 aggregate 中
failed reservation 无法 join 到 action/edge
positive RCMV 是否真的存在说不清
without_rd 是否真的改变决策说不清
without_action_conditioned_reservation 的 stale harm 看不清
raw-gap illusion 只能讲故事不能落表
```

论文审稿人最容易攻击的是：

```text
你的机制到底有没有起作用？
你的指标是否来自同一初始状态？
你的 failure 是否被隐藏？
你的 ablation 是否真的消融了对应机制？
```

Wave 6A.0 就是为了堵住这些洞。

## 3. 必须新增或稳定的文件

每个 evidence package 必须采用分层目录，避免同名覆盖：

```text
evidence_package/
  main_batch/
    batch_manifest.csv
    aggregate_metrics_completed.csv
    failure_summary_main_batch.csv
    rcmv_trace.csv
    readiness_summary.csv
    state_hash_fairness.csv
    schema_manifest.json

  readiness_fail/
    aggregate_metrics_readiness_fail.csv
    failure_summary_readiness_fail.csv
    readiness_failures.csv

  positive_rcmv_micro/
    positive_rcmv_manifest.json
    positive_rcmv_aggregate_metrics.csv
    positive_rcmv_failure_summary.csv
    positive_rcmv_rcmv_trace.csv
    positive_rcmv_action_evaluations.csv
    positive_rcmv_reservations.csv

  gate_D0_input/
    gate_D0_manifest.json
    aggregate_metrics_completed.csv
    failure_summary_main_batch.csv
    failure_summary_readiness_fail.csv
    positive_rcmv_aggregate_metrics.csv
    positive_rcmv_failure_summary.csv
    positive_rcmv_rcmv_trace.csv
    state_hash_fairness.csv
    paper_claim_support_table.csv

  evidence_index.json
  schema_manifest.json
```

禁止不同层级都写成：

```text
failure_summary.csv
```

否则主 batch、readiness failure、positive RCMV micro-case 会相互覆盖，后续无法审计。

每个 run 必须输出或稳定：

```text
metrics_episode.json
state_hash.json
scenario_manifest.json
readiness_summary.json
actions.csv
action_evaluations.csv
reservations.csv
realized_events.csv
vehicles_step.csv
trace_replay_summary.md
```

## 4. 全局字段补丁

所有核心 CSV/JSON 必须带：

```text
batch_id
run_id
scenario_id
seed
algorithm_id
decision_mode
state_hash
config_hash
code_version
metrics_schema_version
evidence_package_version
```

`run_id` 建议：

```text
{batch_id}__{scenario_id}__seed{seed}__{algorithm_id}
```

禁止只用 timestamp 作为唯一 ID。

## 5. aggregate_metrics.csv 补丁

新增字段分为三类。

### 5.1 基础比较字段

```text
status
readiness_pass
readiness_fail_reason
D_H
baseline_J
selected_J
selected_RCMV
rcmv_positive_margin
positive_RCMV_candidate_count
candidate_action_count
selected_action_type
baseline_S_R
baseline_Z_R
selected_S_R
selected_Z_R
delta_S_R
delta_Z_R
mean_RD_matched
production_cost_sum
stale_reservation_count
stale_reservation_harm
action_conditioned_gain
rd_decision_changed_flag
raw_gap_illusion_flag
no_fallback_invalid_event_count
failure_joinable_rate
```

### 5.2 reservation denominator 字段

```text
reservation_count
generated_reservation_count
planned_reservation_count
failed_reservation_count
failed_reservation_rate
failed_reservation_denominator
```

定义：

```text
generated_reservation_count = reservation_count 或 planned_reservation_count，必须在 failed_reservation_denominator 中标注
failed_reservation_rate = failed_reservation_count / generated_reservation_count
```

### 5.3 demand denominator 字段

```text
merge_success_count
merge_success_rate_over_demand
predicted_unserved_demand_count
predicted_unserved_demand_rate
realized_unserved_demand_count
realized_unserved_demand_rate
no_reservation_due_to_invalid_supply_count
no_reservation_due_to_invalid_supply_rate
waiting_or_unserved_penalty
denominator_warning_flag
denominator_notes
```

定义：

```text
predicted_unserved_demand_count = selected_Z_R
predicted_unserved_demand_rate = selected_Z_R / D_H
realized_unserved_demand_count = max(D_H - merge_success_count, 0)
realized_unserved_demand_rate = realized_unserved_demand_count / D_H
merge_success_rate_over_demand = merge_success_count / D_H
no_reservation_due_to_invalid_supply_count = demand exists but no generated reservation because selected inventory is invalid/empty
waiting_or_unserved_penalty = 对 unserved demand 的显式惩罚项；若当前 J 未使用，也必须作为诊断字段输出
denominator_warning_flag = true 当 failed_reservation_rate=0 但 realized_unserved_demand_count>0 或 merge_success_rate_over_demand=0
```

必须在表格注释或 `denominator_notes` 中写明：

```text
failed_reservation_rate 只衡量已生成 reservation 的失败比例；
merge_success_rate_over_demand 才衡量 ramp demand 服务比例。
```

其他定义：

```text
delta_S_R = selected_S_R - baseline_S_R
delta_Z_R = baseline_Z_R - selected_Z_R
rcmv_positive_margin = max_candidate_RCMV - theta
action_conditioned_gain = J(stale/no-action reservation) - J(action-conditioned reservation)，若不可算则 NaN + reason
stale_reservation_harm = stale failure/delay/invalid 增量，若无 stale reservation 则 0 或 NaN，必须标注
rd_decision_changed_flag = without_rd 与 full selected_action/selected_edge 是否不同
raw_gap_illusion_flag = raw geometric gap promising 但 P_R/RD/matching failed
```

## 6. rcmv_trace.csv 补丁

每个 candidate action 一行，必须包含：

```text
batch_id, run_id, scenario_id, seed, algorithm_id
decision_context_id
action_id
action_type
nominal_edge_id
boundary_type
near_miss_type
requested_delta_W
delta_W_target
T_prod
u_front
u_rear
profile_clip_flag
action_profile_feasible
J
Z_bar
D_bar
C_bar
RCMV
rank
selected
rejected_by_theta
matched_edge_ids
matched_rd_sum
invalid_count
cost_components_json
```

如果 action 被 rollout 前拒绝：

```text
J = inf
RCMV = -inf
rejected_before_rollout = true
reject_reason = ...
```

## 7. failure_summary.csv 补丁

从 v2.1 起，`failure_summary.csv` 不是唯一标准文件名。必须分层输出：

```text
failure_summary_main_batch.csv
failure_summary_readiness_fail.csv
failure_summary_positive_rcmv.csv
failure_summary_all.csv
```

其中：

```text
failure_summary_main_batch.csv:
  只包含 completed comparison runs 中 reservation/execution/metric failure

failure_summary_readiness_fail.csv:
  只包含 readiness_failed runs 与 readiness_fail_reasons

failure_summary_positive_rcmv.csv:
  只包含 positive RCMV micro package 的 predicted/realized mismatch、unsafe margin、expiration、invalid reservation 等 failure

failure_summary_all.csv:
  合并索引，可用于全局审计，但不得覆盖前三个文件
```

failure 必须可回溯到：

```text
batch_id
run_id
decision_context_id
reservation_id
action_id
edge_id
slot_id
ramp_id
vehicle_id
event_type
failure_reason
failure_stage
planned_tau
actual_time
actual_margin_front
actual_margin_rear
denominator_scope
demand_id
```

`failure_stage` 枚举：

```text
readiness
edge_quality
action_validation
reservation_creation
guidance_execution
merge_at_tau
slot_expiration
post_episode_metric
predicted_valid_realized_invalid
positive_rcmv_micro
```

## 8. readiness 输出补丁

`readiness_summary.csv/json` 必须包含：

```text
G_H
raw_time_expanded_slot_count
D_H
S_R_0
Z_R_0
reservable_edge_count
matched_edge_count
total_edge_count
near_miss_edge_count
boundary_CAV_HDV
boundary_HDV_CAV
boundary_CAV_CAV
boundary_HDV_HDV
boundary_cav_available_count
inner_receiving_gap_count
raw_gap_illusion_count
dominant_invalid_reasons
readiness_pass
readiness_fail_reasons
```

readiness_failed 的 run 不进入 completed comparison summary，但必须进入 readiness_failures.csv。

## 9. state_hash_fairness.csv

按：

```text
scenario_id, seed
```

分组，输出：

```text
scenario_id
seed
algorithm_count
unique_state_hash_count
state_hashes_json
fairness_pass
failed_algorithm_ids
```

规则：

```text
unique_state_hash_count == 1 才通过
```

失败时整个 batch 不可作为论文证据。

## 10. evidence_index.json

示例：

```json
{
  "batch_id": "batch_...",
  "evidence_package_version": "wave_6A0_v2.1",
  "created_at": "...",
  "code_version": "...",
  "metrics_schema_version": "metrics_v2.1",
  "included_scenarios": ["S2", "S5", "S6", "S7", "S8"],
  "included_algorithms": ["fifo_no_production", "raw_gap_reservation", "density_triggered", "speed_benefit", "rpmi_cmv"],
  "denominator_policy": {
    "failed_reservation_rate": "failed_reservation_count / generated_reservation_count",
    "merge_success_rate_over_demand": "merge_success_count / D_H",
    "predicted_unserved_demand_rate": "selected_Z_R / D_H",
    "realized_unserved_demand_rate": "(D_H - merge_success_count) / D_H"
  },
  "files": {
    "aggregate_metrics_completed": "main_batch/aggregate_metrics_completed.csv",
    "failure_summary_main_batch": "main_batch/failure_summary_main_batch.csv",
    "failure_summary_readiness_fail": "readiness_fail/failure_summary_readiness_fail.csv",
    "positive_rcmv_aggregate_metrics": "positive_rcmv_micro/positive_rcmv_aggregate_metrics.csv",
    "positive_rcmv_failure_summary": "positive_rcmv_micro/positive_rcmv_failure_summary.csv",
    "positive_rcmv_rcmv_trace": "positive_rcmv_micro/positive_rcmv_rcmv_trace.csv",
    "rcmv_trace": "main_batch/rcmv_trace.csv",
    "readiness_summary": "main_batch/readiness_summary.csv",
    "state_hash_fairness": "main_batch/state_hash_fairness.csv"
  }
}
```

`evidence_index.json` 必须能回答：

```text
哪个文件证明 reservation denominator？
哪个文件证明 demand denominator？
positive RCMV case 是否正式纳入？
readiness failure 是否被单独保存？
```

## 11. Toy tests

必须新增或更新：

| Test | 构造 | 预期 |
|---|---|---|
| 6A0.1 unique run id | 同 scenario/seed 多算法 | run_id 不覆盖 |
| 6A0.2 fairness | 同 scenario/seed | unique_state_hash_count=1 |
| 6A0.3 readiness split | readiness_failed + completed | 分层输出 |
| 6A0.4 rcmv trace completeness | 有 3 个 candidate | rcmv_trace 至少 3 行 |
| 6A0.5 failure join | failed reservation | 可 join action/edge/reservation |
| 6A0.6 stale metric | stale ablation | stale_flag 与 stale count 可见 |
| 6A0.7 rd decision flag | without_rd | decision_changed 可计算 |
| 6A0.8 raw-gap illusion | raw W 大但 P_R=0 | raw_gap_illusion_flag=true |
| 6A0.9 denominator split | failed_reservation_rate=0 但 D_H>merge_success_count | denominator_warning_flag=true |
| 6A0.10 failure naming | main/readiness/positive 三类 failure | 三类文件均存在且不覆盖 |
| 6A0.11 positive RCMV package | 至少一个 selected_RCMV>0 micro case | positive_rcmv_* 文件完整 |

## 12. 小 batch 验收

至少跑：

```text
scenarios: S2, S5, S6 或其 deterministic toy/minimal versions
seeds: 3 个
algorithms: fifo_no_production, raw_gap_reservation, density_triggered, speed_benefit, rpmi_cmv,
            rpmi_cmv_without_rd, rpmi_cmv_without_action_conditioned_reservation,
            rpmi_cmv_without_near_miss
```

验收：

```text
所有 completed run 有 metrics_episode.json
readiness_failed run 不污染 comparison
state_hash_fairness 全 pass
rcmv_trace 可从 selected action 回查所有候选
failure_summary_main_batch/readiness_fail/positive_rcmv 三类文件互不覆盖
failure_summary 可从 failure 回查 action/edge/reservation
aggregate_metrics 可复算关键指标
failed_reservation_rate 与 merge_success_rate_over_demand 同表出现
positive_rcmv_micro package 可复核 selected_RCMV>0 的预测与执行结果
```

## 13. 阶段输出报告模板

Codex 完成后输出：

```text
1. 修改了哪些文件
2. 新增了哪些 schema 字段
3. 哪些旧字段保持兼容
4. toy tests 结果
5. small batch 结果
6. evidence package 路径
7. 当前仍无法支撑哪些论文主张
8. 是否允许进入 Wave 6A+
```

## 14. 进入 Wave 6A+ 的条件

全部满足：

```text
state_hash_fairness pass
evidence_index.json 存在
aggregate_metrics/failure_summary/rcmv_trace/readiness_summary 可读
failure joinable rate 足够高，无法 join 的要有 reason
RCMV trace 不缺 selected/candidate
readiness_failed 与 completed 分离
reservation denominator 与 demand denominator 字段完整
positive_rcmv_micro package 已纳入 evidence_index
failure_summary_main_batch/readiness_fail/positive_rcmv 不互相覆盖
```
