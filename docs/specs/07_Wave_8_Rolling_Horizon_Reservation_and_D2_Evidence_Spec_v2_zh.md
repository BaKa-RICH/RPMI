# Wave 8: Rolling Horizon Reservation and D2 Evidence Spec v2 中文版

## 0. 本阶段定位

Wave 8 实现 rolling horizon reservation。  
它替代旧 Phase 6B 命名。

目标是从：

```text
single_t0_micro_episode
```

扩展到：

```text
rolling_horizon_episode
```

## 1. Codex 执行合约

只允许实现：

```text
multiple decision contexts
reservation persistence
reservation refresh
reservation cancellation
partial action execution
overlapping action rule
rolling logs
D2 evidence package
```

禁止：

```text
stochastic IDM
SUMO/MOBIL/RL
复杂 multi-agent planner
用 fallback 修复 unsafe merge
```

## 2. 进入条件

必须满足：

```text
Gate D0 pass 或 conditional pass 且修复项完成
single-t0 reservation lifecycle 稳定
failure trace 可回溯
baseline suite 可复现
```

D1 可以是 retain/downgrade/remove，但论文必须已确定 lane-change 主张边界。

## 3. rolling 语义

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

## 4. reservation persistence

reservation 状态扩展：

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

规则：

```text
未到 tau 的 planned reservation 可被 refresh/cancel
已经 active_guidance 的 reservation 只能按安全规则处理
merged/failed/expired 不可修改
```

## 5. overlapping action rule

必须定义：

```text
同一 CAV 是否可在上一 action 未结束时接受新 action
```

V0 推荐：

```text
no_overlap_same_cav
```

如果新 action 想控制正在 action window 内的 CAV：

```text
reject_reason = overlapping_action_same_cav
```

## 6. partial execution

如果 rolling replan 发生在 action 未执行完：

```text
已执行部分不可回滚
未来未执行部分可取消或继续
必须记录 action_executed_fraction
```

## 7. 新增日志

### decision_contexts.csv

```text
decision_context_id
context_index
context_time
state_hash_at_context
active_reservation_count
active_action_count
readiness_pass
candidate_action_count
selected_action_id
selected_RCMV
```

### reservation_replans.csv

```text
old_reservation_id
new_reservation_id
decision_context_id
operation
reason
old_action_id
new_action_id
old_edge_id
new_edge_id
tau
status_before
status_after
```

### action_lifecycle.csv

```text
action_id
decision_context_id
controlled_cavs
start_time
end_time
executed_start_time
executed_end_time
executed_fraction
cancelled
cancel_reason
overlap_reject_count
```

## 8. rolling evaluation

新增指标：

```text
rolling_decision_count
reservation_refresh_count
reservation_cancel_count
reservation_supersede_count
overlap_reject_count
mean_action_executed_fraction
rolling_vs_single_delta_failure_rate
rolling_vs_single_delta_delay
rolling_vs_single_delta_expiration_rate
rolling_consistency_violation_count
```

## 9. 实验设计

对比：

```text
single_t0_micro_episode
rolling_horizon_episode
rolling_without_refresh
rolling_without_cancellation
```

场景：

```text
D2/S7 rolling-stale scenario
S5 production scenario
S6 RD contrast scenario
```

## 10. Toy tests

| Test | 构造 | 预期 |
|---|---|---|
| W8.1 two contexts | decision_interval < H | 生成多个 context |
| W8.2 persist planned | 无 replan | reservation 延续 |
| W8.3 refresh reservation | 新 inventory 更优 | old refreshed/superseded |
| W8.4 cancel unsafe | stale slot invalid | cancelled_by_replan |
| W8.5 no overlap | 同 CAV action overlap | reject |
| W8.6 partial action | action 执行一半 replan | executed_fraction 记录 |
| W8.7 rolling improves stale | stale scenario | rolling 优于 single/stale |

## 11. 输出

```text
wave_8_report.md
rolling_trace_samples/
gate_D2_input/
```

## 12. 进入 Gate D2 条件

```text
rolling toy tests pass
decision_contexts/reservation_replans/action_lifecycle 完整
rolling vs single 对比可解释
无大面积 consistency violation
failure trace 可回溯
```
