# Phase 3 v2: Diagnostic Matching and Mechanism Experiment S0

## 1. 本阶段目标

实现 conflict-aware diagnostic matching、matching-consistent `S_H^R/Z_H^R`、固定 label policy 的 S0 mechanism prediction pipeline。

本阶段仍不做 production action。

## 2. v2 阶段拆分

为避免 Phase 3 与 Phase 4 的依赖循环，本阶段分为：

```text
Phase 3A:
  diagnostic matching
  hand-crafted toy states
  minimal S0 micro sampler

Phase 4:
  formal scenario generator and readiness

Phase 3B:
  rerun S0 batch using Phase 4 formal generator
```

代码上应尽量让 Phase 3A 的 minimal sampler 复用 Phase 4 generator 的底层 state builder，不要形成两套口径。

## 3. 对应公式

matching variable：

```math
x_{r,i,j,k}\in\{0,1\}
```

每个 ramp 至多一个 edge：

```math
\sum_{i,j,k}x_{r,i,j,k}\le1
```

每个 time-expanded slot 至多一个 ramp：

```math
\sum_r x_{r,i,j,k}\le1
```

time-window physical-gap conflict：

```text
same physical_gap_id and abs(tau1 - tau2) < T_merge + T_buffer => conflict
```

inventory：

```math
S_H^R=\max_x\sum_e \omega_r P_e^R x_e
```

```math
Z_H^R=\max(D_H-S_H^R,0)
```

## 4. 输入与输出

| 类型 | 内容 |
|---|---|
| 输入 | edge qualities、demand weights、conflict rules、S0 samples、future label config |
| 输出 | `matching.csv`、`metrics_step.csv`、S0 predictor/outcome tables |
| 不输出 | production action、RCMV、action-conditioned reservation |

## 5. 数据结构设计

```python
@dataclass(frozen=True)
class DemandRecord:
    ramp_id: int
    omega: float
    wait_time: float
    distance_to_ramp_end: float
    in_R_H: bool

@dataclass(frozen=True)
class MatchingEdge:
    edge_id: str
    ramp_id: int
    slot_id: str
    physical_gap_id: tuple[int, int]
    tau: float
    P_R: float
    RD: float
    weight: float

@dataclass
class MatchingResult:
    matching_id: str
    selected_edges: list[MatchingEdge]
    selected_edge_ids: list[str]
    S_R: float
    Z_R: float
    D_H: float
    unmatched_ramps: list[int]
    conflict_mode: str
    solver_name: str
    objective_value: float
```

## 6. Demand weight 规则

默认：

```text
omega_r = 1.0
```

可选论文式：

```text
omega_r = 1 + chi_w * wait_time_r + chi_d * max(d_crit - distance_to_ramp_end, 0) / d_crit
```

必须记录：

```text
ramp_id, omega, wait_time, distance_to_ramp_end, chi_w, chi_d, d_crit
```

S0 主结果若使用非默认权重，必须在 analysis summary 中说明。

## 7. Matching solver 规则

禁止：

```text
用 Hungarian 处理 physical-gap/time-window conflict 并声称 conflict-aware
```

默认：

```text
solve_matching_v0_greedy_conflict()
```

可选：

```text
solve_matching_milp_conflict()
```

Hungarian 只允许：

```text
conflict_mode="slot_only_debug"
```

Conflict modes：

| mode | 用途 |
|---|---|
| `time_window_default` | 主实验默认 |
| `whole_horizon_debug` | toy/debug，偏保守 |
| `slot_only_debug` | Hungarian debug only |

## 8. 核心函数清单

| 函数名 | 输入 | 输出 | 作用 | 必须记录 |
|---|---|---|---|---|
| `compute_demand_weights(ramps,config)` | ramps | dict | 计算 `omega_r` | demand rows |
| `build_matching_edges(edge_qualities,demand)` | qualities | edges | 过滤 reservable | weights |
| `edges_conflict(e1,e2,mode,params)` | edges | bool | conflict rule | reason |
| `solve_matching_v0_greedy_conflict(edges,demand,mode)` | edges | result | default solver | matching |
| `solve_matching_milp_conflict(edges,demand,mode)` | edges | result | optional exact small-scale | solver status |
| `build_matching_cost_matrix(...)` | edges | matrix | Hungarian debug | debug only |
| `compute_inventory_from_matching(result)` | matching | metrics | `S/Z/D` | metrics |
| `compute_predictor_row(...)` | sample | row | S0 predictors | predictor table |
| `compute_future_outcome_row(...)` | rollout logs | row | S0 labels | outcome table |
| `analyze_predictor_outcome(...)` | tables | summary | correlation/regression | summary |

## 9. 关键流程

### Diagnostic matching

```text
1. demand <- compute_demand_weights
2. E_res <- edge qualities with is_reservable=True
3. matching_edges <- weight = omega_r * P_R - epsilon_RD * RD
4. solve conflict-aware matching
5. S_R <- sum omega_r * P_R over selected edges
6. Z_R <- max(D_H - S_R, 0)
7. log matching and metrics
```

RD 只能作为 epsilon tie-break，不作为 matching 主目标。

### S0 mechanism experiment

```text
For each sample:
  1. generate state
  2. no-action deterministic rollout
  3. compute raw gap, density imbalance, speed difference
  4. generate slots/edges
  5. diagnostic matching -> S_R/Z_R
  6. future label rollout under fixed FIFO_no_production
  7. write predictor/outcome rows
After samples:
  8. join by sample_id
  9. compute correlation, rank correlation, simple regression, AUC if labels binary
```

主 label policy 固定：

```text
label_policy = "FIFO_no_production"
```

## 10. 示例代码

```python
def edges_conflict(e1, e2, mode: str, T_merge: float, T_buffer: float) -> bool:
    if e1.ramp_id == e2.ramp_id:
        return True
    if e1.slot_id == e2.slot_id:
        return True
    if mode == "whole_horizon_debug":
        return e1.physical_gap_id == e2.physical_gap_id
    if mode == "time_window_default":
        return (
            e1.physical_gap_id == e2.physical_gap_id
            and abs(e1.tau - e2.tau) < T_merge + T_buffer
        )
    if mode == "slot_only_debug":
        return False
    raise ValueError(mode)
```

```python
def solve_matching_v0_greedy_conflict(edges, demand_weights, mode, params):
    selected = []
    for e in sorted(edges, key=lambda z: z.weight, reverse=True):
        if any(edges_conflict(e, s, mode, params.T_merge, params.T_buffer) for s in selected):
            continue
        selected.append(e)

    D_H = sum(demand_weights.values())
    S_R = sum(demand_weights[e.ramp_id] * e.P_R for e in selected)
    Z_R = max(D_H - S_R, 0.0)
    return MatchingResult(
        matching_id="m_greedy_conflict",
        selected_edges=selected,
        selected_edge_ids=[e.edge_id for e in selected],
        S_R=S_R,
        Z_R=Z_R,
        D_H=D_H,
        unmatched_ramps=sorted(set(demand_weights) - {e.ramp_id for e in selected}),
        conflict_mode=mode,
        solver_name="greedy_conflict",
        objective_value=S_R,
    )
```

## 11. S0 表 schema

### `s0_predictor_table.csv`

```text
sample_id, scenario_id, seed,
G_H, raw_time_expanded_slot_count,
density_imbalance, speed_difference,
D_H, S_H_R, Z_H_R,
reservable_edge_count, matched_edge_count,
mean_RD_all_edges, mean_RD_matched,
near_miss_count_baseline
```

### `s0_future_outcome_table.csv`

```text
sample_id, label_policy,
future_ramp_waiting,
failed_reservation_count,
slot_expiration_count,
hard_brake_count,
recovery_time,
speed_wave_amplitude,
invalid_event_count
```

## 12. Toy Cases

| Toy | 构造 | 预期 |
|---|---|---|
| 3.1 one ramp one edge | 1 reservable edge | selected, `S=omega`, `Z=0` |
| 3.2 two ramps one slot | same slot | only one selected |
| 3.3 one ramp two edges | same ramp | only one selected |
| 3.4 time-window conflict | same physical gap, close tau | cannot both select |
| 3.5 far time-window | same gap, tau far apart | may both select if no other conflict |
| 3.6 no edge | all invalid | `S=0`, `Z=D` |
| 3.7 raw-gap illusion | high raw gaps, low reach/RD | high `G_H`, high `Z_H_R`, bad future labels |

## 13. 阶段验收条件

- matching constraints 全部可测；
- default solver 是 conflict-aware greedy；
- Hungarian 只用于 debug；
- `S_H_R` 可从 matching.csv 复算；
- `0 <= S_H_R <= D_H`；
- `Z_H_R=max(D_H-S_H_R,0)`；
- S0 主 label policy 固定；
- 至少输出一个 raw-gap vs `Z_H_R` 不一致样例。

## 14. 常见失败与回查

| 失败 | 回查 |
|---|---|
| 同一 ramp 多匹配 | conflict rule 是否包含 same ramp |
| same physical gap 被过度限制 | 是否误用 whole horizon default |
| S0 解释力弱 | P_R/RD/reachability/sample strata/label policy |
| raw gap 与 Z 数值直接比较 | 测试是否仍含旧 gate |
| result 不可复现 | sampler 是否绕过 Phase0 seed/state hash |

## 15. 本阶段不做

- 不生成 production action；
- 不执行 reservation；
- 不做 RCMV；
- 不做 proposed/baseline comparison；
- 不做 stochastic estimator。
