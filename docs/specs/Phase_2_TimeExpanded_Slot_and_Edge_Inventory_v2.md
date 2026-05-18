# Phase 2 v2: Time-Expanded Slot and Edge Inventory

## 1. 本阶段目标

实现 time-expanded candidate slot `s=(i,j,k)`、ramp-aware pair-edge `e=(r,i,j,k)`、deterministic edge validity cascade、V0 RD proxy、以及 inventory metric 接口。

本阶段不做 production action、RCMV、final reservation。

## 2. 本阶段为什么必要

论文核心不是“有几个 raw gap”，而是“某个 ramp vehicle 在某个 candidate time 能否使用某个 boundary pair”。因此必须显式生成：

```text
slot = (front, rear, k, action_context)
edge = (ramp, front, rear, k, action_context)
```

## 3. 对应公式与 v2 澄清

候选时间：

```math
T_H=\{\tau_k=t+k\Delta t_m,\ k=1,\ldots,K_H,\ \tau_k\le t+H\}
```

slot：

```math
s=(i,j,k)
```

edge：

```math
e=(r,i,j,k)
```

feasible interval：

```math
I_{r,i,j,k}=[x_j+L_r+d_{rear},\ x_i-L_i-d_{front}]
```

width：

```math
W_e = upper - lower
```

v2 必须区分：

```text
V_phys_theory = 1{W_e >= 0}
V_phys_buffer = 1{W_e >= W_min_buffer}
delta_W_req = max(W_min_buffer - W_e, 0)
```

不能把 `W>=W_min_buffer` 静默替代为论文中的 physical validity。

Deterministic V0 cascade：

```math
P_e^R = I_reach I_surv I_safe I_rec
```

若 slot 从 predicted state at `tau_k` 生成，则：

```text
I_surv = 1
surv_mode = "deterministic_tau_generated"
```

## 4. 输入与输出

| 类型 | 内容 |
|---|---|
| 输入 | current state、no-action/action rollout、ramp vehicles、target lane、config |
| 输出 | `slots.csv`、`edges.csv`、edge qualities、inventory draft |
| 不输出 | production actions、RCMV、baseline comparison |

## 5. 数据结构设计

```python
@dataclass(frozen=True)
class Slot:
    slot_id: str
    front_id: int
    rear_id: int
    k: int
    tau: float
    physical_gap_id: tuple[int, int]
    eval_context: Literal["baseline", "action"]
    action_id: str | None

@dataclass(frozen=True)
class Edge:
    edge_id: str
    ramp_id: int
    front_id: int
    rear_id: int
    k: int
    tau: float
    slot_id: str
    physical_gap_id: tuple[int, int]
    eval_context: str
    action_id: str | None

@dataclass(frozen=True)
class IntervalResult:
    lower: float
    upper: float
    width: float
    d_front: float
    d_rear: float
    V_phys_theory: int
    V_phys_buffer: int
    delta_W_req: float

@dataclass(frozen=True)
class EdgeQuality:
    edge_id: str
    I_reach: int
    I_surv: int
    I_safe: int
    I_rec: int
    P_R: float
    RD: float
    W: float
    V_phys_theory: int
    V_phys_buffer: int
    delta_W_req: float
    is_reservable: bool
    reason_not_reservable: str
    fail_reason_priority: str
    surv_mode: str
    validity_mode: str
    rd_components: dict
```

## 6. Reason codes

```text
OK
UNREACHABLE
PHYS_WIDTH_NEGATIVE
BUFFER_WIDTH_INSUFFICIENT
SAFETY_MARGIN_NEGATIVE
HIGH_RECOVERY_DEBT
RAMP_END_INFEASIBLE
SPEED_INCOMPATIBLE
SURV_DISABLED_BY_MODE
UNKNOWN_INVALID
```

优先级建议：

```text
UNREACHABLE > PHYS_WIDTH_NEGATIVE > SAFETY_MARGIN_NEGATIVE > HIGH_RECOVERY_DEBT > BUFFER_WIDTH_INSUFFICIENT > OK
```

## 7. 核心函数清单

| 函数名 | 输入 | 输出 | 作用 | 必须记录 |
|---|---|---|---|---|
| `generate_time_grid(t,H,dt_merge)` | floats | `(k,tau)` | 候选时间 | k,tau |
| `get_target_lane_pairs(state_tau,lane)` | state | pairs | 相邻 boundary | gap |
| `make_slot_id(front,rear,k,action_context)` | values | str | 统一 slot id | slot_id |
| `generate_slots(rollout,...)` | rollout | slots | time-expanded slots | slots.csv |
| `make_edge_id(ramp,slot,action_context)` | values | str | 统一 edge id | edge_id |
| `build_edges(ramps,slots)` | lists | edges | ramp-slot 笛卡尔候选 | edges |
| `compute_safety_distances(edge,state_tau,params)` | edge,state | distances | dynamic buffer | d_front,d_rear |
| `compute_feasible_interval(edge,state_tau,params)` | edge,state | interval | interval/W | W,V flags |
| `evaluate_reachability(ramp,interval,delta_T,params)` | ramp | result | ramp 能否到达 | x_min,x_max,a_req |
| `evaluate_survival(edge,mode)` | edge | result | V0 默认 1 | surv_mode |
| `evaluate_safety(edge,rollout,interval)` | edge | result | min margin | margin |
| `compute_recovery_debt(edge,merge_rollout,params)` | edge | result | V0 RD proxy | components |
| `compute_edge_validity(...)` | edge | quality | cascade | edges.csv |
| `compute_inventory_metrics(...,matching_hook)` | qualities | metrics | 调 Phase3 solver | S/Z |

## 8. 关键流程

```text
1. Generate T_H
2. For each tau:
     get predicted state at tau
     get adjacent target-lane boundary pairs
     create slots
3. Cross ramp vehicles with slots -> edges
4. For each edge:
     interval <- compute feasible interval
     reach <- evaluate reachability
     surv <- 1 in deterministic tau-generated mode
     safe <- evaluate safety/margin
     RD <- compute V0 RD proxy
     I_rec <- 1{RD <= RD_max}
     P_R <- product flags
     reservable <- required flags true
     log reason code
5. Pass reservable edge list to Phase3 matching hook
```

## 9. 示例代码

```python
def generate_time_grid(t: float, H: float, dt_merge: float) -> list[tuple[int, float]]:
    out = []
    k = 1
    while t + k * dt_merge <= t + H + 1e-9:
        out.append((k, round(t + k * dt_merge, 10)))
        k += 1
    return out

def make_slot_id(front_id: int, rear_id: int, k: int, action_context: str) -> str:
    return f"slot_{action_context}_f{front_id}_r{rear_id}_k{k}"

def make_edge_id(ramp_id: int, front_id: int, rear_id: int, k: int, action_context: str) -> str:
    return f"edge_{action_context}_r{ramp_id}_f{front_id}_b{rear_id}_k{k}"
```

```python
def compute_feasible_interval(edge, state_tau, ramp_length: float, params) -> IntervalResult:
    front = state_tau.vehicles[edge.front_id]
    rear = state_tau.vehicles[edge.rear_id]
    ramp_pred = state_tau.vehicles[edge.ramp_id]

    d_front = params.d0 + params.T_safe * ramp_pred.v
    d_rear = params.d0 + params.T_safe * rear.v

    lower = rear.x + ramp_length + d_rear
    upper = front.x - front.length - d_front
    width = upper - lower
    return IntervalResult(
        lower=lower,
        upper=upper,
        width=width,
        d_front=d_front,
        d_rear=d_rear,
        V_phys_theory=int(width >= 0.0),
        V_phys_buffer=int(width >= params.W_min_buffer),
        delta_W_req=max(params.W_min_buffer - width, 0.0),
    )
```

```python
def evaluate_survival_deterministic_tau_generated(edge) -> dict:
    return {
        "I_surv": 1,
        "surv_mode": "deterministic_tau_generated",
        "surv_reason": "slot_generated_from_state_at_tau",
    }
```

```python
def compute_inventory_metrics(edge_qualities, demand_weights, matching_hook):
    D_H = sum(demand_weights.values())
    matching = matching_hook(edge_qualities, demand_weights)
    S_R = sum(demand_weights[e.ramp_id] * e.P_R for e in matching.selected_edges)
    Z_R = max(D_H - S_R, 0.0)
    return {
        "D_H": D_H,
        "S_H_R": S_R,
        "Z_H_R": Z_R,
        "matched_edge_count": len(matching.selected_edges),
        "reservable_edge_count": sum(q.is_reservable for q in edge_qualities),
        "total_edge_count": len(edge_qualities),
    }
```

## 10. Demand weight 默认值

Phase 2 只定义接口，Phase 3 计算 demand。默认：

```text
omega_r = 1.0
D_H = number of ramp vehicles in horizon
```

可选论文式权重：

```text
omega_r = 1 + chi_w * wait_time_r + chi_d * max(d_crit - distance_to_ramp_end, 0) / d_crit
```

必须记录 `chi_w, chi_d, d_crit, omega_r`。若使用默认全 1，明确写入 config。

## 11. RD V0 proxy

V0 minimal RD proxy：

```text
RD = mean(normalized rear braking, normalized wave amplitude, normalized recovery time)
```

推荐 components：

```text
B: rear braking proxy
A: local wave amplitude proxy
T: recovery time proxy
N_aff: optional affected vehicle count
Q_loss: optional outflow loss
```

若未实现 `N_aff/Q_loss`，日志和论文结果必须标注 `RD_proxy_v0_minimal`。

## 12. 日志字段

### `slots.csv`

```text
slot_id, front_id, rear_id, k, tau, physical_gap_id,
eval_context, action_id, gap_at_tau, boundary_type
```

### `edges.csv`

```text
edge_id, ramp_id, slot_id, front_id, rear_id, k, tau,
eval_context, action_id, physical_gap_id,
I_reach, I_surv, I_safe, I_rec, P_R,
V_phys_theory, V_phys_buffer, W, delta_W_req,
RD, rd_components_json,
is_reservable, reason_not_reservable, fail_reason_priority,
surv_mode, validity_mode
```

## 13. Toy Cases

| Toy | 构造 | 预期 |
|---|---|---|
| 2.1 raw gap but unreachable | 宽 gap、tau 太早或 ramp 太慢 | `V_phys_theory=1`, `I_reach=0`, `P_R=0` |
| 2.2 width negative | upper < lower | `V_phys_theory=0`, reason `PHYS_WIDTH_NEGATIVE` |
| 2.3 buffer insufficient | `W>=0` 但 `<W_min_buffer` | theory valid，buffer invalid/near-miss |
| 2.4 high RD | gap/reach OK，但 RD 高 | `I_rec=0`, `P_R=0` |
| 2.5 deterministic survival | tau-generated slot | `I_surv=1`, `surv_mode=deterministic_tau_generated` |
| 2.6 inventory sanity | arbitrary edges | `0<=S_H_R<=D_H`, `Z=max(D-S,0)` |

## 14. 阶段验收条件

- time grid 不含当前时刻；
- slot_id/edge_id 包含 action context；
- physical validity 和 buffer validity 分离；
- deterministic `I_surv` 不重复过滤；
- 所有 invalid edge 有 reason code；
- 不再出现 `S_H_R <= raw_gap_count` gate；
- inventory metrics 可由 Phase3 matching 重算。

## 15. 常见失败与回查

| 失败 | 回查 |
|---|---|
| supply 异常大 | matching 是否一 ramp 多 edge；是否未限制 conflict |
| edge 全 invalid | reachability/safety buffer/RD 阈值是否过严 |
| raw gap 多但 Z 低 | scenario 是否没有 illusion；demand 是否太低 |
| near-miss 与 Phase4 不一致 | 是否没共享 classifier |
| V_phys 口径混乱 | 是否混淆 `W>=0` 与 `W>=W_min_buffer` |

## 16. 本阶段不做

- 不选择 action；
- 不做 final reservation；
- 不做 baseline comparison；
- 不做 stochastic estimator；
- 不做 lane-change production。
