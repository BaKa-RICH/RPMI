# Wave 7: Lane-Change Production and S5 Full Action Evidence v2.1 中文版

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

Wave 7 是在 Gate D0 允许后，扩展 action set：

```text
boundary-speed production
→ upstream CAV lane-change production
```

它替代旧的 Phase 5B / Optional lane-change 文档命名。

## 1. Codex 执行合约

本阶段只允许实现：

```text
lane_change production action
receiving gap detection
lane-change feasibility gate
lane-change duration and trajectory proxy
target lane insertion/update
lane-change production cost
lane-change logs
S5 full action-set evidence
reservation denominator 与 demand denominator 双口径继承
```

禁止：

```text
rolling horizon
stochastic IDM
MOBIL
SUMO
RL
HDV autonomous lane changing
multi-action bundle
large-scale planner
```

## 2. 进入条件

必须满足：

```text
Gate D0 = pass 或 conditional_pass 且 D0_fixlist 已完成
Wave 6A.0 evidence hygiene pass
boundary-speed action trace 可解释
reservation lifecycle 稳定
failure join 可追溯
```

若 D0 fail，不得进入 Wave 7。

## 3. 论文问题

Wave 7 只回答：

```text
lane-change production 是否为 RPMI-CMV 的必要/有效 action mode？
```

不回答：

```text
rolling 是否有效
stochastic 是否鲁棒
真实交通仿真是否可部署
```

## 4. action set 扩展

新增：

```text
lane_change
```

保留：

```text
none
front_acc
rear_dec
front_rear
```

`Action.action_type` 更新为：

```text
Literal["none", "front_acc", "rear_dec", "front_rear", "lane_change"]
```

## 5. lane-change production 语义

lane_change 的 V0 语义是：

```text
控制一个 upstream CAV 在 action window 内从 target lane 或 blocking lane 移出/移入，
改变 future boundary sequence，
从而生产或释放 ramp receiving slot。
```

V0 不要求真实 MOBIL。  
V0 只要求 deterministic、可复现、可解释的 lane-change proxy。

## 6. 必须新增的数据结构

```python
@dataclass(frozen=True)
class LaneChangeCandidate:
    candidate_id: str
    edge_id: str
    cav_id: int
    from_lane: int
    to_lane: int
    start_time: float
    end_time: float
    expected_gap_effect: str
    receiving_gap_front_id: int | None
    receiving_gap_rear_id: int | None
    feasibility_pass: bool
    reject_reason: str
```

action profile 增加：

```text
lc_from_lane
lc_to_lane
lc_start_time
lc_end_time
lc_duration
receiving_gap_id
lc_feasibility_margin_front
lc_feasibility_margin_rear
lc_cost
```

## 7. lane-change feasibility gate

必须检查：

```text
controlled vehicle is CAV
receiving lane exists
receiving gap exists at planned LC time
front/rear margins >= config thresholds
LC duration <= T_prod 或明确允许跨越 T_prod
no duplicate controlled CAV within the action
```

失败时：

```text
rejected_before_rollout = true
reject_reason = ...
```

## 8. rollout 规则

在 action-conditioned rollout 中：

```text
t < lc_start: normal
lc_start <= t <= lc_end: vehicle lane state marked changing or interpolated
t > lc_end: vehicle lane = lc_to_lane
```

V0 可采用离散 lane switch at `lc_end`，但必须记录：

```text
lc_mode = "discrete_switch_at_end"
```

不能假装为真实连续横向动力学。

## 9. cost 规则

lane_change cost 至少包含：

```text
lc_base_cost
lc_duration_penalty
lc_margin_risk_penalty
lc_disturbance_proxy
```

`C_bar` 更新为：

```text
production_speed_effort + lane_change_cost + disturbance
```

但必须避免把 RD 重复计入 cost。

## 10. near-miss 与 lane-change

near-miss classifier 可扩展 available_modes：

```text
CAV-HDV -> front_acc
HDV-CAV -> rear_dec
CAV-CAV -> front_acc, rear_dec, front_rear
LC-eligible upstream CAV -> lane_change
```

新增 lane-change near-miss reason：

```text
lc_upstream_blocking
lc_receiving_gap_available
lc_can_reorder_boundary
```

## 11. 日志补丁

### actions.csv 新增

```text
lc_from_lane
lc_to_lane
lc_start_time
lc_end_time
lc_duration
receiving_gap_id
lc_feasibility_pass
lc_reject_reason
lc_cost_components_json
lc_mode
```

### rcmv_trace.csv 新增

```text
lane_change_candidate_id
lc_cost
lc_feasibility_margin_front
lc_feasibility_margin_rear
lc_expected_gap_effect
```

### realized_events.csv 新增

```text
lane_change_started
lane_change_completed
lane_change_rejected
lane_change_induced_failure
```

## 12. S5 full action evidence

Wave 7 必须重跑或新增 S5：

```text
S5_boundary_only
S5_lane_change_only
S5_full_action_set
```

对比：

```text
rpmi_cmv_boundary_speed_only
rpmi_cmv_lane_change_only
rpmi_cmv_full_action_set
raw_gap_reservation
density_triggered
speed_benefit
```

## 13. 验收指标

必须输出：

```text
lane_change_candidate_count
lane_change_feasible_count
lane_change_selected_count
lane_change_success_count
lane_change_induced_failure_count
full_vs_boundary_delta_Z_R
full_vs_boundary_delta_S_R
full_vs_boundary_delta_J
full_vs_boundary_delta_failure_rate
full_vs_boundary_delta_cost
```

## 14. Toy tests

| Test | 构造 | 预期 |
|---|---|---|
| W7.1 no LC CAV | 无 upstream CAV | 无 lane_change candidate |
| W7.2 feasible LC | CAV 有 receiving gap | candidate pass |
| W7.3 unsafe receiving gap | margin 不足 | reject |
| W7.4 LC changes boundary | rollout 后 edge set 改变 | regenerated inventory 可见 |
| W7.5 LC selected by RCMV | LC 降低 J | selected lane_change |
| W7.6 LC high cost rejected | cost 大 | a0 或 boundary action |
| W7.7 full vs boundary | boundary 无法解决，LC 可解决 | full 优于 boundary |

## 15. 阶段输出

```text
wave_7_report.md
wave_7_lane_change_trace_samples/
wave_7_s5_full_action_summary.csv
gate_D1_input/
```

## 16. 进入 Gate D1 的条件

```text
lane-change toy tests pass
actions/rcmv/reservations/failure logs 完整
S5 full action evidence 产生
full/boundary/lane_change_only 对比可解释
没有大面积不可 join failure
```

## 17. v2.1 denominator 继承与 claim 边界

Wave 7 继承 Wave 6A.0/D0 的 denominator 规则。

所有 S5 full action-set evidence 必须同时报告：

```text
failed_reservation_rate
failed_reservation_denominator
merge_success_rate_over_demand
predicted_unserved_demand_rate
realized_unserved_demand_rate
```

若 lane_change 或 boundary-speed action 只是避免坏 reservation，但 demand 未服务，则只能写：

```text
the action avoids invalid reservations or unsafe attempts
```

不得写：

```text
the action improves merge success
```

若 selected_action_type = none，则该 run 不可计为 lane-change production 成功。

若要支持 lane-change production 主张，至少需要：

```text
selected_action_type = lane_change
selected_RCMV > theta
selected_Z_R 低于 no-action/boundary-only
realized merge_success_rate_over_demand 不低于 baseline
failure_summary_main_batch 可解释所有失败
```
