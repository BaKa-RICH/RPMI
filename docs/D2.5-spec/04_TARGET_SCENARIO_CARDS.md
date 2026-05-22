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
