# RPMI-CMV Python V0 Mandatory Patch Addendum v2

本文档是代码实现 agent 的最高优先级补丁。  
所有 Phase v2 已吸收本补丁，但实现时仍必须把本文档作为硬约束清单。

## 0. 范围限定

V0 第一轮只做：

```text
deterministic Python mechanism validation
single_t0_micro_episode
boundary-speed production first
trace-first no-fallback simulation
```

不做：

```text
SUMO
MOBIL
RL
action bundle
rolling horizon by default
stochastic IDM by default
industrial simulation platform
```

## 1. 全局 data dictionary 必须实现

必须在 Phase 0 中建立并写入 `global_conventions.json` 或等价 config snapshot。

| 名称 | 约定 |
|---|---|
| units | meter, second, m/s, m/s^2 |
| `x` | front bumper position |
| occupied interval | `[x - length, x]` |
| target lane | config 显式指定，建议 outer target lane = 0 |
| ramp lane | 建议 `lane=-1` |
| time | absolute simulation time |
| step | integer simulation step |
| `decision_context_id` | 每次 t0/rolling decision 唯一 ID |
| `state_hash` | scenario/baseline/proposed fairness check |
| `slot_id` | must include `front_id,rear_id,k,action_context` |
| `edge_id` | must include `ramp_id,front_id,rear_id,k,action_context` |
| `action_id` | must include action type + index |
| `reservation_id` | binds selected action and selected edge |
| `code_version` | git commit or local package version |
| `units_version` | convention version, e.g. `rpmi_units_v1` |

## 2. No-fallback 的正确定义

```text
no-fallback = nominal behavior + production command overlay + no post-hoc safety repair
```

V0 中：

- HDV：deterministic IDM；
- 未受 production 控制的 CAV：nominal ACC/IDM-like car-following；
- 被 action 控制的 CAV：production command overlay 或短窗口 override；
- 若仍产生 overlap、negative margin、hard braking：只记录，不修复。

推荐接口：

```python
def compute_nominal_accel(vehicle, leader, config) -> float:
    if vehicle.veh_type == "HDV":
        return compute_idm_accel(vehicle, leader, config.hdv_idm)
    if vehicle.veh_type == "CAV":
        return compute_idm_accel(vehicle, leader, config.cav_nominal_cf)
    raise ValueError(vehicle.veh_type)

def combine_nominal_and_action(a_nominal: float, a_action: float | None, mode: str) -> float:
    if a_action is None:
        return a_nominal
    if mode == "override":
        return a_action
    if mode == "additive_clip":
        return a_nominal + a_action
    raise ValueError(mode)
```

## 3. Kinematics 速度下限必须用 effective acceleration

禁止：

```text
x_new = x + v*dt + 0.5*a_cmd*dt^2
v_new = clip(v + a_cmd*dt)
```

必须：

```python
def clip_accel_for_kinematics(v, a_cmd, dt, u_min, u_max):
    a_eff = max(u_min, min(u_max, a_cmd))
    speed_floor_clip = False
    if v + a_eff * dt < 0.0:
        a_eff = -v / dt
        speed_floor_clip = True
    return a_eff, speed_floor_clip
```

然后用 `a_eff` 同时更新位置和速度。  
这不是 safety fallback，只是速度不能为负的物理约束。

## 4. 不再直接测试 `S_H_R <= raw_gap_count`

必须替换为：

```text
0 <= S_H_R <= D_H
Z_H_R = max(D_H - S_H_R, 0)
matched_edge_count <= min(ramp_count, reservable_slot_count)
reservable_edge_count <= total_edge_count
```

若 `omega_r=1` 且 raw count 被明确定义为 time-expanded candidate slots，才可额外测试：

```text
matched_edge_count <= raw_time_expanded_slot_count
```

raw gap 与 `Z_H^R` 的核心比较应是预测能力比较，而不是直接数值大小比较。

## 5. Physical validity 与 buffer 分离

论文物理 interval：

```text
W_e = upper - lower
V_phys_theory = 1{W_e >= 0}
```

V0 可引入 buffer，但必须显式命名：

```text
V_phys_buffer = 1{W_e >= W_min_buffer}
delta_W_req = max(W_min_buffer - W_e, 0)
```

不能把 `W>=W_min` 静默替代为论文中的 physical validity。

## 6. Deterministic V0 的 `I_surv`

如果 slot 从 predicted state at `tau_k` 生成：

```text
I_surv = 1
surv_mode = "deterministic_tau_generated"
```

除非显式启用 observation-window survival rule。  
V1 stochastic 再估计 survival probability。

## 7. Matching solver 默认规则

不允许在 physical-gap/time-window conflict 存在时直接使用 Hungarian 并声称 conflict-aware。

默认：

```text
Phase 3 gates: greedy conflict solver
Phase 6 paper-ready small scale: MILP or enumeration optional
Hungarian: only conflict_mode="slot_only_debug"
```

Conflict rule：

```text
same ramp_id => conflict
same slot_id => conflict
same physical_gap_id and abs(tau1 - tau2) < T_merge + T_buffer => conflict
```

主实验默认：

```text
conflict_mode = "time_window_default"
```

`whole_horizon_debug` 只用于 toy/debug。

## 8. Phase 3 / Phase 4 依赖修正

```text
Phase 3A: diagnostic matching + hand-crafted toy states + minimal S0 micro sampler
Phase 4: formal scenario generator + readiness
Phase 3B/6: formal S0 batch rerun with Phase 4 generator
```

不得在 Phase 3 写一套临时 sampler 后在 Phase 4 重写另一套口径不一致的 generator。

## 9. Near-miss classifier 共享

Phase 4 readiness 与 Phase 5 action generation 必须调用同一个只读 classifier：

```python
def classify_near_miss(edge_quality, params) -> NearMissLabel:
    ...
```

Phase 4 只能使用它统计 availability，不能生成 action 或读取 proposed outcome。

## 10. Candidate actions 不跨候选去重 CAV

允许两个不同 candidate actions 控制同一 CAV，因为 V0 最终只执行一个 action。

不允许：

- 一个 action 内部重复/冲突控制同一 CAV；
- 任何 action 控制 HDV；
- future action bundle 逻辑进入 Phase 5A。

必须删除旧示例中的 `used_primary_cavs` 跨候选过滤。

## 11. Phase 5A 只实现 boundary-speed production

第一轮 action set：

```text
none
front_acc
rear_dec
front_rear
```

lane-change production 进入 Phase 5B，只有 Phase 5A gates 通过后才实现。

## 12. Boundary speed action profile 固定

设：

```text
delta_W_req = max(W_min_buffer - W, 0)
buffer = production_width_buffer
T_prod = min(config.T_prod, tau - current_time)
delta_W_target = delta_W_req + buffer
```

front acceleration：

```text
desired_front_dx = delta_W_target
u_front = 2 * desired_front_dx / T_prod^2
u_front = clip(u_front, 0, u_max_comfort)
```

rear deceleration：

```text
desired_rear_dx_reduction = delta_W_target
u_rear = -2 * desired_rear_dx_reduction / T_prod^2
u_rear = clip(u_rear, u_min_comfort, 0)
```

front-rear joint：

```text
try alpha in {0.25, 0.5, 0.75}
front share = alpha * delta_W_target
rear share = (1-alpha) * delta_W_target
choose minimum normalized effort among feasible profiles
```

必须记录：

```text
requested_delta_W
delta_W_target
T_prod
u_front
u_rear
profile_clip_flag
estimated_delta_W_after_clip
action_profile_feasible
```

## 13. RD 的软硬分工

V0 分工：

```text
I_rec:
  RD <= RD_max as hard feasibility gate

Matching:
  maximize demand-weighted P_R supply
  RD only epsilon tie-break

RCMV:
  D_bar = demand-normalized matched RD soft penalty

Production cost:
  action effort and action-induced disturbance only
```

不能在 `P_R`、matching 主目标、`D_bar`、`C_bar` 中重复惩罚同一 RD component。

## 14. Reservation lifecycle 必须实现

状态：

```python
ReservationStatus = Literal[
    "planned",
    "active_guidance",
    "merged",
    "expired",
    "failed_unreachable",
    "failed_invalid_slot",
    "failed_unsafe_margin",
]
```

必须字段：

```text
reservation_id
decision_context_id
ramp_id
edge_id
slot_id
action_id
planned_tau
planned_merge_x
planned_interval_lower
planned_interval_upper
actual_x_at_tau
actual_margin_front
actual_margin_rear
status
failure_reason
```

执行规则：

1. 创建 reservation 时，`planned_merge_x = interval center`；
2. `t < tau` 时，ramp guidance 用恒加速度或两段恒加速度到达 planned_merge_x；
3. `t = tau` 时，重新计算 actual interval/margins；
4. valid 则 lane 切到 target lane，status=`merged`；
5. invalid 则 status=`failed_invalid_slot` 或 `failed_unsafe_margin`，不修复；
6. `time > tau + tolerance` 仍未合流，则 status=`expired`。

## 15. V0 默认 single-decision micro-episode

默认：

```text
decision_mode = "single_t0_micro_episode"
```

流程：

```text
At t0:
  diagnostic inventory
  near-miss
  candidate actions
  action-conditioned rollout
  RCMV selection
  reservation creation

Then:
  execute selected action/guidance until evaluation horizon
  record outcomes
```

rolling horizon 放入 Phase 6B。

## 16. S0 future label policy 固定

主 S0 使用：

```text
label_policy = "FIFO_no_production"
```

所有 predictors 使用同一 label policy。  
可以做 raw-gap sensitivity，但不能混入主结果。

## 17. Baseline 不得偷用 proposed 信息

| Baseline | 允许 | 禁止 |
|---|---|---|
| FIFO/no production | arrival order natural opportunities | RD/RCMV/near-miss |
| raw-gap reservation | geometric gap width ranking | ramp-specific RD/reachability for decision |
| density-triggered | lane density imbalance only | `Z_R`、near-miss、RCMV |
| speed-benefit | CAV self speed gain | ramp inventory |
| RPMI-CMV | near-miss + RCMV + action-conditioned reservation | realized future labels |

## 18. Readiness 必须 algorithm-independent

Readiness 可用：

```text
initial state
no-action rollout
diagnostic edges/matching
cheap near-miss availability
```

Readiness 禁止使用：

```text
selected RPMI action outcome
RPMI advantage
future realized comparison result
```

## 19. 日志补丁

所有核心表增加：

```text
decision_context_id
state_hash
code_version
config_hash
units_version
```

`vehicles_step.csv` 增加：

```text
a_nominal
a_action
a_eff
speed_floor_clip
controlled_by_action_id
reservation_id
```

`edges.csv` 增加：

```text
V_phys_theory
V_phys_buffer
surv_mode
validity_mode
fail_reason_priority
```

`actions.csv` 增加：

```text
requested_delta_W
estimated_delta_W_after_clip
action_profile_feasible
profile_clip_flag
```

`realized_events.csv` 增加：

```text
linked_reservation_id
linked_action_id
linked_edge_id
```

## 20. V1 stochastic 条件概率分母为 0

V1 估计条件概率时必须记录：

```text
conditional_denominator
conditional_probability
conditional_probability_is_nan
```

若 denominator=0，probability 记为 NaN，不得填 0 或 1 伪装确定结论。

## 21. 声称边界

若只完成 Phase 0--6A：

```text
可以声称 deterministic Python V0 mechanism validation completed.
不可以声称 full RPMI-CMV reproduction completed.
```

只有 Phase 5B/6B/7 对应 gates 通过后，才能逐项扩展论文表述。
