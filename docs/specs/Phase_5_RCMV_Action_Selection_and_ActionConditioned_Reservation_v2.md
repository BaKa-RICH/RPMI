# Phase 5 v2: RCMV Action Selection and Action-Conditioned Reservation

## 1. 本阶段目标

实现 near-miss based boundary-speed slot production、action-conditioned rollout、RCMV 计算、action selection、reservation lifecycle 与 ramp merge execution。

本阶段是 proposed RPMI-CMV 的 V0 核心闭环，但 v2 明确拆分为：

```text
Phase 5A: boundary-speed production only
Phase 5B: optional lane-change production
```

## 2. 本阶段为什么必要

slot production 不能只看某个 gap 变宽。action 会改变：

- future boundary sequence；
- ramp reachability；
- RD；
- matching；
- reservation validity。

因此必须在每个 action rollout 后重新生成 slots/edges/matching，再计算 RCMV。

## 3. 对应机制

near-miss：

```math
E_{prod}^0=\{e:I_{reach}=1,\ e\notin E_{res}^0,\ \Delta W_{req}\le W_{prod}\}
```

objective：

```math
J(a)=\bar Z_H^{R,a}+\lambda_D\bar D_H^{R,a}+\lambda_C\bar C_{prod}(a)
```

RCMV：

```math
RCMV(a)=J(a_0)-J(a)
```

selection：

```math
a^*=\arg\max_a RCMV(a),\quad execute\ if\ RCMV(a^*)>\theta
```

## 4. 输入与输出

| 类型 | 内容 |
|---|---|
| 输入 | current state、baseline edges/matching、near-miss labels、action config |
| 输出 | near-miss logs、actions、action evaluations、selected action、reservations、outcome events |
| 不输出 | stochastic estimator、action bundle、rolling horizon default |

## 5. Phase 5A Action Set

第一轮只实现：

```text
none
front_acc
rear_dec
front_rear
```

不实现：

```text
lane_change
multi-action bundle
multi-CAV optimization
```

Phase 5B 才实现 upstream lane-change production。

## 6. 数据结构设计

```python
@dataclass(frozen=True)
class NearMissEdge:
    edge_id: str
    near_miss_type: str
    delta_W_req: float
    available_modes: tuple[str, ...]
    screen_score: float
    selected_for_rollout: bool

@dataclass(frozen=True)
class Action:
    action_id: str
    action_type: Literal["none", "front_acc", "rear_dec", "front_rear", "lane_change"]
    nominal_edge_id: str | None
    controlled_cavs: tuple[int, ...]
    target_gap_id: tuple[int, int] | None
    control_profile: dict
    estimated_cost: float

@dataclass(frozen=True)
class ActionEvaluation:
    action_id: str
    J: float
    Z_bar: float
    D_bar: float
    C_bar: float
    RCMV: float
    S_R: float
    Z_R: float
    matched_edge_ids: list[str]
    selected: bool
    rejected_by_theta: bool
```

Reservation:

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

@dataclass
class Reservation:
    reservation_id: str
    decision_context_id: str
    ramp_id: int
    edge_id: str
    slot_id: str
    action_id: str
    planned_tau: float
    planned_merge_x: float
    planned_interval_lower: float
    planned_interval_upper: float
    status: ReservationStatus = "planned"
    failure_reason: str = ""
```

## 7. Candidate actions 不跨候选去重

必须生成所有 single-action candidates。  
允许两个 alternative candidate actions 共享同一个 CAV，因为最终只执行一个。

只检查 action 内部有效性：

- 不控制 HDV；
- 一个 action 内部不重复控制同一 CAV；
- front/rear 控制对象符合 boundary type。

## 8. Boundary speed profile

设：

```text
delta_W_req = max(W_min_buffer - W, 0)
delta_W_target = delta_W_req + production_width_buffer
T_prod = min(config.T_prod, tau - current_time)
```

### front_acc

```text
u_front = 2 * delta_W_target / T_prod^2
u_front = clip(u_front, 0, u_max_comfort)
```

### rear_dec

```text
u_rear = -2 * delta_W_target / T_prod^2
u_rear = clip(u_rear, u_min_comfort, 0)
```

### front_rear

```text
for alpha in {0.25, 0.5, 0.75}:
  front_dx = alpha * delta_W_target
  rear_dx = (1-alpha) * delta_W_target
  compute u_front, u_rear
choose feasible profile with minimum normalized effort
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

被 clip 后预计无法补足 near-miss 也可以评估，但必须标记 `action_profile_feasible=False`。

## 9. RD / matching / cost 分工

```text
I_rec:
  RD <= RD_max hard gate

Matching:
  maximize supply
  RD only epsilon tie-break

RCMV:
  D_bar = demand-normalized matched RD

Production cost:
  action effort + action-induced disturbance only
```

避免把同一 RD component 在 `I_rec`、matching、`D_bar`、`C_bar` 中重复惩罚。

## 10. 核心函数清单

| 函数名 | 输入 | 输出 | 作用 | 必须记录 |
|---|---|---|---|---|
| `find_near_miss_edges(edges,params)` | edges | near-miss | 读 shared classifier | near_miss_edges |
| `available_production_modes(edge,state)` | edge,state | modes | boundary type | modes |
| `build_boundary_speed_profile(mode,nm,edge,state,params)` | near-miss | profile | 可复现控制 | profile fields |
| `generate_candidate_actions(near_misses,state,params)` | near-miss | actions | all single actions | actions |
| `validate_single_action(action,state)` | action | pass/reason | 内部冲突 | reject reason |
| `apply_action_rollout(action,state,config)` | action | rollout | action-conditioned rollout | snapshots |
| `evaluate_action(action,state,config)` | action | evaluation | regenerate slots/edges/matching | action_evals |
| `compute_production_cost(action,rollout,params)` | action | cost | `C_bar` | components |
| `compute_matched_recovery_debt(matching,edges,demand)` | matching | `D_bar` | RD soft term | matched RD |
| `select_action(evaluations,theta)` | evals | eval | max RCMV | selected |
| `create_reservations(selected_eval,edge_map)` | eval | reservations | final reservations | reservations |
| `execute_reservation_guidance(state,reservations,t)` | state | commands/status | ramp guidance | reservation status |
| `update_reservation_at_tau(...)` | state | status | merge/fail/expire | margins |
| `ablation_without_action_conditioned_reservation(...)` | baseline/action | stale report | 消融 | stale flag |

## 11. 关键流程

```text
At t0:
1. baseline no-action rollout
2. slots/edges/P_R/RD
3. diagnostic matching -> J(a0)
4. classify near-miss
5. generate all candidate boundary-speed actions + a0
6. for each action:
     rollout from same current state
     regenerate slots/edges/P_R/RD
     solve conflict-aware matching
     compute Z_bar, D_bar, C_bar, J
     RCMV = J0 - J
7. select max RCMV; if <= theta, select a0
8. create action-conditioned reservations
9. execute selected action and ramp guidance until evaluation horizon
10. update reservation statuses and realized events
```

## 12. 示例代码

```python
def generate_candidate_actions(near_misses, edge_map, state, params):
    actions = [Action("a0_none", "none", None, tuple(), None, {}, 0.0)]
    idx = 0
    for nm in near_misses:
        edge = edge_map[nm.edge_id]
        for mode in nm.available_modes:
            if mode == "lane_change" and not params.enable_lane_change_production:
                continue
            cavs = controlled_cavs_for_mode(mode, edge, state)
            action = build_action_for_mode(mode, nm, edge, cavs, params, idx)
            ok, reason = validate_single_action(action, state)
            if ok:
                actions.append(action)
                idx += 1
            else:
                log_rejected_action(action, reason)
    return actions
```

```python
def build_front_acc_profile(delta_W_target, T_prod, limits):
    u = 2.0 * delta_W_target / max(T_prod * T_prod, 1e-9)
    u_clip = min(max(u, 0.0), limits.u_max_comfort)
    estimated = 0.5 * u_clip * T_prod * T_prod
    return {
        "u_front": u_clip,
        "u_rear": 0.0,
        "T_prod": T_prod,
        "profile_clip_flag": abs(u_clip - u) > 1e-9,
        "estimated_delta_W_after_clip": estimated,
        "action_profile_feasible": estimated + 1e-9 >= delta_W_target,
    }
```

```python
def compute_objective(Z_R, D_H, matched_rd_sum, C_bar, lambda_D, lambda_C, eps=1e-9):
    Z_bar = Z_R / (D_H + eps)
    D_bar = matched_rd_sum / (D_H + eps)
    J = Z_bar + lambda_D * D_bar + lambda_C * C_bar
    return {"J": J, "Z_bar": Z_bar, "D_bar": D_bar, "C_bar": C_bar}
```

## 13. Reservation lifecycle

创建时：

```text
planned_merge_x = (interval.lower + interval.upper) / 2
status = planned
```

执行中：

```text
t < tau: ramp guidance attempts planned_merge_x
abs(t-tau)<=tol: recompute actual margins
valid: lane <- target_lane, status=merged
invalid: status=failed_invalid_slot or failed_unsafe_margin
time > tau + tol and not merged: status=expired
```

不得修复 invalid merge，只记录。

## 14. 日志字段

### `actions.csv`

```text
action_id, action_type, nominal_edge_id, controlled_cavs,
target_gap_id, boundary_type, control_start, control_end,
requested_delta_W, delta_W_target, T_prod,
u_front, u_rear, profile_clip_flag,
estimated_delta_W_after_clip, action_profile_feasible,
estimated_cost, rejected_before_rollout, reject_reason
```

### `action_evaluations.csv`

```text
action_id, J, Z_bar, D_bar, C_bar, RCMV,
S_R, Z_R, matched_count, matched_edge_ids,
invalid_count, selected, rank, rejected_by_theta,
cost_components_json, matched_rd_sum
```

### `reservations.csv`

```text
reservation_id, decision_context_id, ramp_id, edge_id, slot_id, action_id,
planned_tau, planned_merge_x,
planned_interval_lower, planned_interval_upper,
actual_x_at_tau, actual_margin_front, actual_margin_rear,
status, failure_reason, stale_flag
```

## 15. Toy Cases

| Toy | 构造 | 预期 |
|---|---|---|
| 5.1 only a0 | 无 action | `RCMV(a0)=0`, selected a0 |
| 5.2 front_acc works | front CAV 轻加速补足 W | `RCMV>0`, selected front_acc |
| 5.3 cost rejection | high cost | selected a0 or rejected by theta |
| 5.4 shared CAV alternatives | 两候选共享同 CAV | 两者都生成，后续 RCMV 排名 |
| 5.5 global rematching | action 后 e2 比 nominal e1 好 | final matching 可选 e2 |
| 5.6 reservation success | ramp 到 tau margin valid | status merged |
| 5.7 reservation fail | tau actual margin invalid | failed_unsafe_margin，无修复 |
| 5.8 stale ablation | 不重生成 reservation | stale flag true |

## 16. 阶段验收条件

- near-miss 来自 shared classifier；
- 不控制 HDV；
- 不跨候选去重 CAV；
- boundary speed profile 可复现；
- action rollout 后重新生成 slots/edges/matching；
- RCMV 分项全部记录；
- selected action 使用 action-conditioned reservation；
- reservation lifecycle 可计算 success/fail/expire；
- no-fallback failure 可追溯到 action/edge/reservation。

## 17. Phase 5B lane-change 进入条件

只有满足以下条件才可做 5B：

- Phase 5A toy gates 全过；
- S2/S5/S6 至少一个 deterministic scenario 可解释；
- action-conditioned reservation 与 ablation 有差异；
- logs 能解释 failure；
- boundary-speed baselines 已可跑。

5B 需要新增 receiving gap、lane-change duration、target lane insertion、LC cost、LC safety gate。未完成 5B 不得声称完整 action set。

## 18. 本阶段不做

- Phase 5A 不做 lane-change；
- 不做 action bundle；
- 不做 rolling horizon；
- 不做 stochastic IDM；
- 不用 future realized outcome 修正 action。
