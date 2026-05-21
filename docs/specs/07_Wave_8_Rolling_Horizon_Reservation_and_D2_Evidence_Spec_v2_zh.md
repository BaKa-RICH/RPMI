# Wave 8: Rolling Horizon Reservation and D2 Evidence Spec v2 中文版

## 0. 执行前必读资料

任何 Codex 执行 Wave 8 前，必须先读取：

```text
docs/specs/00_ACTIVE_SPECS_README_v2.1_zh.md
docs/specs/01_Codex_Implementation_Wave_Guide_Paper_Experiment_Closed_Loop_v2.1_zh.md
docs/specs/06_Gate_D1_Lane_Change_Production_Claim_Decision_v2_zh.md
docs/specs/07_Wave_8_Rolling_Horizon_Reservation_and_D2_Evidence_Spec_v2_zh.md
docs/specs/08_Gate_D2_Rolling_Reservation_Claim_Decision_v2_zh.md
docs/specs/12_Paper_Claim_Evidence_Decision_Matrix_v2.1_zh.md
docs/specs/13_Claim_Staging_and_Gate_Interpretation_Guardrail_v2.1_zh.md
docs/paper/第3.1版论文稿.md
```

不得只读本文件就实现 rolling。Wave 8 直接对应论文中的：

```text
recoverable perishable merge-slot inventory
matching-limited supply
slot-consumption conflict
action-conditioned rolling reservation
expiration and reassignment
reuse or recompute reservation under selected action
no hidden fallback / no unsafe repair
measure / produce / reserve / consume / reassign
```

若代码选择、日志字段或实验设计与这些机制冲突，必须先报告，不得自行弱化为普通 rolling log。

## 1. 论文对照依据

| 论文机制点 | Wave 8 必须落地的 spec 约束 | Gate D2 evidence |
|---|---|---|
| matching-limited inventory | demand denominator + one demand one active/planned reservation | merge_success_rate_over_demand / unserved demand |
| slot-consumption conflict | physical_gap_id / slot_group_id / duplicate consumption check | duplicate_gap_consumption_count = 0 |
| action-conditioned rolling reservation | 每个 context 有 baseline/action-conditioned/stale matching trace | per_context_recompute_checked = true |
| expiration and reassignment | expired/cancelled demand 回流下一 context | expired_returned_demand_count / returned_demand_reassigned_count |
| reuse or recompute reservation under selected action | plan commitment + conditional replan | reservation_churn_rate / plan_lock_violation_count |
| no hidden fallback | unsafe/invalid outcome 记录为 failure | hidden_fallback_detected = false |

特别注意：

```text
Reuse or recompute reservation under selected a*
```

不等于每轮无条件推翻旧计划。rolling 的默认语义是有效计划延续，只有 replan trigger 成立才 refresh/cancel/supersede。

```text
When expiration occurs, the affected ramp vehicle is returned to the demand set in the next rolling cycle.
```

表示失效或过期后的 demand 必须回流并重新参与 matching；不能让失败 demand 从系统中消失。

## 2. 本阶段定位

Wave 8 实现 rolling horizon reservation。它替代旧 Phase 6B 命名。

本阶段不是从：

```text
single_t0_micro_episode
```

简单扩展到：

```text
rolling_horizon_episode
```

而是从：

```text
single-t0 action/reservation audit
```

扩展到：

```text
multi-context rolling control audit:
  plan commitment
  conditional replan
  action-conditioned recomputation
  demand lifecycle
  reservation lifecycle
  slot consumption lifecycle
  action lifecycle
  realized event feedback
  baseline/ablation benefit comparison
  full failure trace join
```

Wave 8 的最小成功标准不是 `rolling_decision_count > 1`。每个 `decision_context` 都必须能解释：

```text
旧计划为什么保留
旧计划为什么取消
旧计划为什么刷新
旧计划为什么替换
这些选择如何影响 demand service
这些选择如何影响 realized failure
```

Gate D2 是 RPMI-CMV 从“单时刻机制诊断”升级到“可运行滚动控制机制”的关键门槛。Wave 9 只验证 stochastic IDM V1 鲁棒性，不负责补救 rolling 的首次有效性证明。

## 3. Codex 执行合约

本阶段只允许实现：

```text
multiple decision contexts
rolling closed-loop state update
reservation commitment / plan lock
conditional replan
reservation persistence / refresh / cancellation / supersede
demand lifecycle return and removal
slot consumption conflict tracking
partial action execution
overlapping action rule
per-context baseline/action-conditioned/stale matching trace
rolling benefit baselines and ablations
D2 evidence package
```

禁止：

```text
stochastic IDM
SUMO/MOBIL/RL
复杂 multi-agent planner
用 fallback 修复 unsafe merge
使用未来真实 outcome 做当前决策
每轮无条件推翻旧 reservation
用 cancelled/expired 掩盖 unserved demand
用 reservation 指标替代 demand 指标
```

## 4. 进入条件

必须满足：

```text
Gate D0 pass 或 conditional pass 且修复项完成
Gate D1 decision recorded 且 paper decision allows
single-t0 reservation lifecycle 稳定
failure trace 可回溯
baseline suite 可复现
reservation denominator 与 demand denominator 已按 v2.1 口径报告
```

D1 可以是 retain/downgrade/remove，但论文必须已确定 lane-change 在当前 evidence version 的主张边界。

## 5. 核心术语

```text
decision_context:
  rolling 控制周期中的一次决策快照，必须有 context_time 和 state_hash。

committed reservation:
  已被系统选择并计划执行的 reservation，默认延续，除非 replan trigger 成立。

active_guidance:
  已进入实际引导/动作执行窗口的 reservation/action，默认 locked。

stale reservation:
  未按最新 state/action recompute 的旧 reservation，用作 ablation，不作为 proposed 结果。

supersede:
  用新 reservation 替换旧 reservation，必须保留 lineage 和 switching justification。

refresh:
  同一 demand/reservation lineage 在新 context 下更新 tau/edge/quality，但不删除 demand。

cancel:
  reservation 被取消，对应 demand 必须回流或进入 unserved，不能消失。

consume:
  ramp vehicle 成功使用 physical gap 合流，相关 gap copy 必须标记 consumed/blocked。
```

## 6. rolling 语义

新 decision_mode：

```text
rolling_horizon_episode
```

每隔：

```text
decision_interval
```

重新构造 decision context：

```text
t0, t1, t2, ...
```

每个 context 有唯一：

```text
decision_context_id
```

rolling 不是每轮贪心重算并频繁换计划。rolling 是：

```text
有效计划默认延续
失效、冲突、安全风险或显著收益触发 replan
每轮重新验证旧计划
每轮为 proposed 与 ablation 生成可审计 trace
```

## 7. Reservation Commitment and Conditional Replan

### 7.1 commitment 状态

```text
uncommitted_candidate
planned_committed
active_guidance_locked
released_by_merge
released_by_expire
released_by_cancel
released_by_safety
```

### 7.2 默认规则

```text
planned_committed 默认 persist
active_guidance_locked 默认不可取消
merged / failed / expired 为终态，不可改写
replan 不是每轮默认动作，而是条件触发动作
```

### 7.3 允许 replan 的触发条件

```text
reachability_lost
predicted_physical_validity_failed
P_R_below_p_min
RD_above_RD_max
slot_conflict_detected
physical_gap_consumed_or_blocked
reservation_tau_expired
controlled_CAV_overlap
new_plan_improvement_exceeds_switching_threshold
```

### 7.4 supersede 条件

只有：

```text
improvement_margin > switching_cost
```

或超过 configured hysteresis threshold 时，才允许用新 reservation 替换仍有效的 committed reservation。

不得因为轻微目标函数收益更高就频繁替换计划。

### 7.5 active guidance 取消条件

`active_guidance_locked` 只能因以下原因取消：

```text
safety
reachability
physical conflict
controlled_CAV_overlap
```

不得因为下一轮目标函数略优而取消已经进入 active guidance 的计划。

### 7.6 必须记录的配置/日志字段

不要求本 spec 固定数值，但必须记录：

```text
switching_cost
improvement_margin
hysteresis_threshold
lock_break_reason
replan_trigger
```

## 8. Rolling State Machines

### 8.1 Demand lifecycle

状态：

```text
active
reserved
merged
returned_after_expire
returned_after_cancel
unserved
```

强制规则：

```text
merged demand 从后续 demand set 移除
expired/cancelled demand 回流下一 context
unserved demand 计入 demand denominator
同一 ramp_vehicle 同一 context 最多一个 active/planned reservation
demand lifecycle 不得由 reservation lifecycle 代替
```

### 8.2 Reservation lifecycle

状态：

```text
planned
active_guidance
merged
expired
failed_unreachable
failed_invalid_slot
failed_unsafe_margin
cancelled_by_replan
refreshed
superseded
```

强制规则：

```text
每个 reservation 必须绑定 decision_context_id / ramp_vehicle_id / edge_id / action_id
每个 refresh/supersede/cancel 必须保留 lineage
reservation status 变化必须同步 demand status
failed_reservation_rate 不能解释为 demand service
```

### 8.3 Slot lifecycle

状态：

```text
available
reserved
consumed
invalidated
blocked_by_conflict
```

必须字段：

```text
physical_gap_id
slot_group_id
slot_consumption_conflict_id
consumed_gap_id
```

强制规则：

```text
同一 physical gap 的 time-expanded copies 不能重复服务多个 demand
已 consumed 的 physical_gap 后续 context 必须 blocked 或进入 conflict set
若不做完整 rolling integer assignment，可用 conservative conflict-set V0，但必须记录为 approximation
```

### 8.4 Action lifecycle

状态：

```text
selected
started
partially_executed
completed
cancelled_future_part
rejected_overlap
```

强制规则：

```text
已执行部分不可回滚
未来未执行部分可 cancel/continue
同一 CAV overlap 必须 reject 或有明确 conflict handling
action lifecycle 必须 join reservation 和 realized_event
```

## 9. Per-Context Rolling Algorithm

每个 context 必须按顺序记录：

```text
1. freeze current state and state_hash
2. carry over committed reservations/actions/demands
3. ingest realized events since previous context
4. update demand/reservation/action/slot terminal states
5. evaluate plan locks and replan triggers
6. expire invalid reservations and return affected demand
7. mark consumed physical gaps and block conflicting slot copies
8. rebuild baseline/no-action inventory and matching
9. build stale/no-replan baseline from carried reservations
10. generate candidate actions from current state
11. run action-conditioned rollout for candidate actions
12. regenerate slots/edges/qualities under each candidate action
13. solve conflict-aware reservation or conservative conflict-set assignment
14. compute RCMV and select action
15. apply commitment rule: persist / refresh / cancel / supersede
16. form final reservations and ramp guidance
17. execute one decision interval without hidden fallback
18. update demand/reservation/action/slot states
19. write full trace rows
```

明确禁止：

```text
每轮无条件推翻旧 reservation
只复制上一轮 reservation 而不验证有效性
只记录 context 不记录 matching
使用未来真实 outcome 做当前决策
fallback repair unsafe merge
用 cancelled/expired 掩盖 unserved demand
用 reservation 指标替代 demand 指标
```

## 10. 日志 Schema

### 10.1 保留现有文件

```text
decision_contexts.csv
reservation_replans.csv
action_lifecycle.csv
```

### 10.2 新增必须文件

```text
rolling_reservations.csv
rolling_demand_lifecycle.csv
rolling_slot_consumption.csv
rolling_matching_trace.csv
rolling_plan_commitment.csv
rolling_failure_trace.csv
rolling_vs_single_demand_metrics.csv
rolling_vs_stale_ablation_metrics.csv
rolling_vs_no_commitment_metrics.csv
```

### 10.3 decision_contexts.csv

```text
decision_context_id
context_index
context_time
state_hash_at_context
previous_context_id
active_demand_count
reserved_demand_count
returned_demand_count
active_reservation_count
locked_reservation_count
active_action_count
consumed_gap_count
blocked_slot_count
readiness_pass
candidate_action_count
selected_action_id
selected_RCMV
baseline_matching_id
action_conditioned_matching_id
stale_matching_id
```

### 10.4 rolling_reservations.csv

```text
reservation_id
lineage_root_reservation_id
lineage_parent_reservation_id
decision_context_id
ramp_vehicle_id
edge_id
action_id
physical_gap_id
slot_group_id
planned_tau
commitment_status
is_locked
status_before
status_after
status_reason
demand_status_before
demand_status_after
realized_event_id
failure_join_key
```

### 10.5 rolling_demand_lifecycle.csv

```text
demand_id
ramp_vehicle_id
decision_context_id
status_before
status_after
reservation_id
event_reason
returned_to_context_id
merge_success
predicted_unserved
realized_unserved
```

### 10.6 rolling_slot_consumption.csv

```text
decision_context_id
physical_gap_id
slot_group_id
edge_id
reservation_id
slot_status_before
slot_status_after
consumed_by_demand_id
blocked_by_conflict_id
duplicate_consumption_flag
```

### 10.7 rolling_matching_trace.csv

```text
decision_context_id
matching_id
matching_type
action_id
edge_id
reservation_id
ramp_vehicle_id
physical_gap_id
slot_group_id
P_R
RD
selected
rejected_reason
```

`matching_type` 必须至少包括：

```text
baseline_no_action
action_conditioned_selected
stale_no_replan
```

### 10.8 rolling_plan_commitment.csv

```text
decision_context_id
reservation_id
action_id
commitment_status_before
commitment_status_after
is_locked
replan_trigger
lock_break_reason
switching_cost
improvement_margin
reservation_churn_flag
active_guidance_cancel_flag
```

### 10.9 rolling_failure_trace.csv

```text
failure_id
decision_context_id
action_id
edge_id
reservation_id
demand_id
physical_gap_id
realized_event_id
failure_stage
failure_reason
is_hidden_fallback
can_join_full_chain
```

### 10.10 action_lifecycle.csv

`action_lifecycle.csv` 是 Wave 8 的保留文件，但必须在 D2 中具备明确字段，避免 partial execution 被写成不可追踪的黑箱。

```text
action_id
decision_context_id
controlled_cavs
start_time
end_time
executed_start_time
executed_end_time
executed_fraction
lifecycle_status_before
lifecycle_status_after
cancelled_future_part
cancel_reason
overlap_reject_count
reservation_id
realized_event_id
```

## 11. Metrics：闭环、收益、稳定性三层

### 11.1 Demand service 指标

```text
merge_success_count
merge_success_rate_over_demand
predicted_unserved_demand_count
predicted_unserved_demand_rate
realized_unserved_demand_count
realized_unserved_demand_rate
mean_ramp_waiting_time
```

### 11.2 Closed-loop correctness 指标

```text
expired_returned_demand_count
cancelled_returned_demand_count
returned_demand_reassigned_count
returned_demand_unserved_count
expired_reservation_count
invalidated_reservation_count
stale_reservation_harm_count
duplicate_gap_consumption_count
full_trace_join_rate
```

### 11.3 Rolling lifecycle 指标

```text
rolling_decision_count
reservation_refresh_count
reservation_cancel_count
reservation_supersede_count
overlap_reject_count
mean_action_executed_fraction
rolling_consistency_violation_count
rolling_vs_single_delta_failure_rate
rolling_vs_single_delta_delay
rolling_vs_single_delta_expiration_rate
```

### 11.4 Plan stability 指标

```text
reservation_churn_rate
action_switch_count
active_guidance_cancel_count
plan_lock_violation_count
mean_committed_reservation_age
rolling_vs_no_commitment_delta_churn_rate
```

### 11.5 Benefit deltas

```text
rolling_vs_single_delta_merge_success_rate_over_demand
rolling_vs_single_delta_realized_unserved_demand_rate
rolling_vs_stale_delta_merge_success_rate_over_demand
rolling_vs_stale_delta_realized_unserved_demand_rate
rolling_vs_stale_delta_expired_reservation_count
rolling_vs_stale_delta_invalidated_reservation_count
rolling_vs_stale_delta_expiration_rate
rolling_vs_stale_delta_stale_harm_count
rolling_vs_no_commitment_delta_churn_rate
```

### 11.6 解释红线

```text
reservation failure 降低，不等于 demand service 改善
expiration 减少，不等于 merge_success_rate_over_demand 提高
频繁重规划带来的短期收益，不能直接写成稳定控制收益
D2 retain 必须同时看 demand denominator、reservation lifecycle 和 plan stability
```

## 12. 实验设计

### 12.1 保留原对比

```text
single_t0_micro_episode
rolling_horizon_episode
rolling_without_refresh
rolling_without_cancellation
```

### 12.2 新增必须 baseline

```text
stale_no_replan_reservation
rolling_without_reassignment
rolling_without_slot_consumption_conflict
rolling_without_commitment
```

### 12.3 可选继承已有 baseline

```text
FIFO merge reservation
raw-gap reservation
density_triggered
speed_benefit
```

### 12.4 D2-focused scenarios

```text
D2-S7 rolling-stale:
  stale reservation 在后续 context 失效，rolling 应 refresh/cancel/reassign。

D2-expiration-return:
  expired reservation 的 demand 必须回流并重新 matching。

D2-slot-consumption-conflict:
  同一 physical gap 的多个 time-expanded copies 不得重复服务 demand。

D2-action-conditioned-recompute:
  selected action 后 inventory/edges/matching 必须变化且可审计。

D2-plan-commitment:
  仍有效的 planned/active_guidance reservation 默认延续。

D2-no-commitment-ablation:
  rolling_without_commitment 应暴露更高 churn/action switching，或更差稳定性。

D2-negative-control:
  无有效 recoverable slot 时，rolling 必须诚实留下 unserved demand，不得 fallback 假服务。
```

## 13. Toy tests

| Test | 构造 | 预期 |
|---|---|---|
| W8.1 two contexts | decision_interval < H | 生成多个 context |
| W8.2 persist planned | 无 replan trigger | reservation 延续 |
| W8.3 refresh reservation | 新 inventory 明显更优且超过 switching threshold | old refreshed/superseded |
| W8.4 cancel unsafe | stale slot invalid | cancelled_by_replan + demand returned |
| W8.5 no overlap | 同 CAV action overlap | reject |
| W8.6 partial action | action 执行一半 replan | executed_fraction 记录 |
| W8.7 rolling improves stale | stale scenario | rolling 优于 single/stale |
| W8.8 expired demand returns | reservation expired | demand returns to next context |
| W8.9 cancelled demand returns | reservation cancelled | demand returns to next context |
| W8.10 merged demand removed | demand merged | removed from future demand set |
| W8.11 consumed gap blocked | same physical gap copy reused | blocked_by_conflict |
| W8.12 duplicate consumption detected | duplicate physical_gap_id served twice | duplicate flag/count |
| W8.13 lineage join | superseded reservation | lineage is joinable |
| W8.14 matching trace exists | each context | baseline/action-conditioned/stale trace |
| W8.15 no future leak | future state changes | current decision cannot use future outcome |
| W8.16 stale fails rolling recovers | stale baseline invalid | rolling cancels/reassigns without fallback |
| W8.17 demand denominator checked | reservation improves but demand worsens | test reports demand-denominator failure |
| W8.18 full failure trace join | induced failure | context/action/edge/reservation/demand/event join |
| W8.19 planned persists | valid committed reservation | persists when still valid |
| W8.20 active guidance locked | active plan with no safety issue | cannot cancel |
| W8.21 supersede threshold | small improvement only | no supersede |
| W8.22 no-commitment churn | plan-churn scenario | rolling_without_commitment has higher churn |

## 14. 输出目录

```text
wave_8_report.md
evidence_package/
  main_rolling_batch/
  rolling_stale/
  expiration_return/
  slot_consumption_conflict/
  action_conditioned_recompute/
  plan_commitment/
  no_commitment_ablation/
  negative_control/
  failure_traces/
gate_D2_input/
  aggregate_metrics.csv
  decision_contexts.csv
  reservation_replans.csv
  action_lifecycle.csv
  rolling_reservations.csv
  rolling_demand_lifecycle.csv
  rolling_slot_consumption.csv
  rolling_matching_trace.csv
  rolling_plan_commitment.csv
  rolling_failure_trace.csv
  rolling_vs_single_demand_metrics.csv
  rolling_vs_stale_ablation_metrics.csv
  rolling_vs_no_commitment_metrics.csv
  failure_summary.csv
  rolling_trace_samples/
```

规则：

```text
不同 scenario 的 failure_summary 不得互相覆盖
main batch、negative control、plan commitment ablation 必须分开
所有 aggregate metrics 必须能回到 source trace
trace samples 必须覆盖成功闭环、失败闭环、plan-lock 延续、replan 触发
```

## 15. 进入 Gate D2 条件

```text
rolling toy tests pass
decision_contexts/reservation_replans/action_lifecycle 完整
rolling_reservations / rolling_demand_lifecycle / rolling_slot_consumption 完整
rolling_matching_trace / rolling_plan_commitment / rolling_failure_trace 完整
rolling vs single/stale/no_commitment 对比可解释
demand denominator 与 reservation denominator 同时报告
无大面积 consistency violation
无无法解释的 plan churn
failure trace 可回溯
```
