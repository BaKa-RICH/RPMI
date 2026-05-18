# Phase 1 v2: State, Dynamics, and No-Fallback Simulator

## 1. 本阶段目标

实现最小一维多车道车辆状态、front-bumper 几何、nominal car-following、production command placeholder、point-mass dynamics，以及 no-fallback event logging。

本阶段不实现 slots、edges、matching、RCMV。

## 2. 本阶段为什么必要

后续 `W_e`、reachability、safety margin、RD、matching 全部依赖：

- `x` 是否为 front bumper；
- occupied interval 是否为 `[x-L, x]`；
- 同车道排序是否正确；
- gap 是否为 `front.x - front.length - rear.x`；
- no-fallback 是否没有 hidden repair。

## 3. 对应论文机制/公式

车辆占据区间：

```math
[x_n(t)-L_n,\ x_n(t)]
```

同车道 front `i` 与 rear `j` 的净 gap：

```math
g_{ij}=x_i-L_i-x_j
```

point-mass dynamics：

```math
x_{t+dt}=x_t+v_tdt+0.5u_tdt^2
```

```math
v_{t+dt}=v_t+u_tdt
```

速度不能为负，必须通过 effective acceleration 裁剪实现。

## 4. 输入与输出

| 类型 | 内容 |
|---|---|
| 输入 | `TrafficState`、commands by vehicle、road config、sim config |
| 输出 | 下一步 `TrafficState`、`vehicles_step.csv`、`realized_events.csv` |
| 不输出 | slots、edges、inventory、matching、RCMV |

## 5. 数据结构设计

```python
@dataclass
class VehicleState:
    id: int
    role: Literal["mainline", "ramp"]
    veh_type: Literal["CAV", "HDV"]
    lane: int
    x: float
    v: float
    a: float
    length: float = 5.0
    active: bool = True
    idm_params: dict | None = None
    cav_limits: dict | None = None
    reservation_id: str | None = None

@dataclass(frozen=True)
class RoadConfig:
    lanes: int
    target_lane: int
    ramp_lane: int = -1
    merge_zone: tuple[float, float] = (300.0, 420.0)
    ramp_end_x: float = 420.0

@dataclass
class TrafficState:
    time: float
    step: int
    vehicles: dict[int, VehicleState]
```

## 6. No-fallback 定义

必须实现：

```text
no-fallback = nominal behavior + optional production command overlay + no post-hoc safety repair
```

允许：

- HDV 使用 deterministic IDM；
- 未受控 CAV 使用 nominal ACC/IDM-like following；
- 受控 CAV 在 action window 内使用 overlay/override；
- 加速度、速度物理边界裁剪；
- 记录 overlap/negative margin/hard braking。

禁止：

- 发现碰撞后自动移动或分开车辆；
- hidden emergency brake 覆盖算法输出；
- unsafe match 后偷偷换 slot；
- baseline 失败后 fallback 到 proposed edge。

## 7. 核心函数清单

| 函数名 | 输入 | 输出 | 作用 | 必须记录 |
|---|---|---|---|---|
| `occupied_interval(vehicle)` | vehicle | `(rear, front)` | `[x-L,x]` | none |
| `sort_lane_vehicles(state,lane)` | state,lane | list | `x` 降序 | optional |
| `find_leader(state,vehicle_id)` | state,id | vehicle/None | 同 lane 前车 | leader_id |
| `compute_gap_margin(front,rear)` | vehicles | float | 净 gap | gap |
| `compute_idm_accel(vehicle,leader,params)` | vehicle,leader | accel | deterministic IDM/ACC | raw accel |
| `compute_nominal_accel(vehicle,leader,config)` | vehicle | accel | HDV/CAV nominal | `a_nominal` |
| `combine_nominal_and_action(a_nominal,a_action,mode)` | accel | accel | action overlay | `a_action` |
| `clip_accel_for_kinematics(v,a_cmd,dt,limits)` | values | `(a_eff,flag)` | effective accel | `speed_floor_clip` |
| `step_vehicle_kinematic(vehicle,a_eff,dt)` | vehicle | vehicle | 更新状态 | `x,v,a_eff` |
| `step_traffic(state,commands,config)` | state,commands | state | 一步 rollout | vehicles_step |
| `detect_overlap(state)` | state | events | no-fallback event | realized_events |
| `detect_hard_brake(state)` | state | events | 强制动事件 | realized_events |

## 8. 关键流程

```text
For each vehicle:
  leader <- find_leader
  a_nominal <- compute_nominal_accel
  a_action <- commands_by_vehicle.get(vehicle_id)
  a_cmd <- combine_nominal_and_action(a_nominal, a_action, config.action_mode)
  a_eff, speed_floor_clip <- clip_accel_for_kinematics
  integrate with a_eff

After all vehicles updated:
  sort lanes
  compute gap_to_leader
  detect overlap / negative margin / hard brake
  log without repair
```

## 9. 示例代码

```python
def compute_gap_margin(front: VehicleState, rear: VehicleState) -> float:
    assert front.lane == rear.lane
    assert front.x >= rear.x, "front/rear ordering is wrong"
    return front.x - front.length - rear.x

def clip_accel_for_kinematics(v: float, a_cmd: float, dt: float, u_min: float, u_max: float):
    a_eff = max(u_min, min(u_max, a_cmd))
    speed_floor_clip = False
    if v + a_eff * dt < 0.0:
        a_eff = -v / dt
        speed_floor_clip = True
    return a_eff, speed_floor_clip

def step_vehicle_kinematic(vehicle: VehicleState, a_eff: float, dt: float, v_max: float):
    x_new = vehicle.x + vehicle.v * dt + 0.5 * a_eff * dt * dt
    v_new = min(v_max, vehicle.v + a_eff * dt)
    return replace(vehicle, x=x_new, v=v_new, a=a_eff)
```

```python
def detect_overlap(state: TrafficState, min_gap: float = 0.0) -> list[dict]:
    events = []
    lanes = sorted({v.lane for v in state.vehicles.values() if v.active})
    for lane in lanes:
        vehicles = sorted(
            [v for v in state.vehicles.values() if v.active and v.lane == lane],
            key=lambda v: v.x,
            reverse=True,
        )
        for front, rear in zip(vehicles, vehicles[1:]):
            gap = compute_gap_margin(front, rear)
            if gap < min_gap:
                events.append({
                    "event_type": "overlap" if gap < 0 else "negative_margin",
                    "time": state.time,
                    "vehicle_ids": [front.id, rear.id],
                    "min_gap": gap,
                    "severity": abs(min(0.0, gap)),
                    "note": "no_fallback_record_only",
                })
    return events
```

## 10. 日志字段

### `vehicles_step.csv`

```text
run_id, step, time, decision_context_id, state_hash, vehicle_id,
role, veh_type, lane, x, v, a,
a_nominal, a_action, a_eff, speed_floor_clip,
leader_id, gap_to_leader,
controlled_by_action_id, reservation_id,
invalid_overlap_flag
```

### `realized_events.csv`

```text
event_id, run_id, step, time, decision_context_id,
event_type, vehicle_ids, min_gap, min_margin, severity,
linked_reservation_id, linked_action_id, linked_edge_id,
note
```

## 11. Toy Cases

| Toy | 输入 | 预期 |
|---|---|---|
| 1.1 single constant speed | `x0=0,v=10,a=0,T=2` | `x=20,v=10` |
| 1.2 single constant accel | `x0=0,v=10,a=1,T=2` | `x=22,v=12` |
| 1.3 speed floor | `v=1,a_cmd=-100,dt=0.1` | `v_new=0`, `speed_floor_clip=True` |
| 1.4 two-car gap | front `x=100,L=5`, rear `x=80` | gap=15 |
| 1.5 overlap no repair | front `x=100,L=5`, rear `x=97` | event logged, positions unchanged |
| 1.6 IDM direction | free road / close slow leader | free accel positive, close accel negative |
| 1.7 CAV nominal | no action command | CAV still follows nominal behavior, not arbitrary constant speed unless configured |

## 12. 阶段验收条件

- front-bumper gap tests 通过；
- effective acceleration kinematics 通过；
- HDV/CAV nominal behavior 可用；
- action overlay placeholder 可用；
- 故意 overlap 不被修复；
- event logs 可 join 到 `decision_context_id`。

## 13. 失败模式与回查

| 失败 | 回查 |
|---|---|
| 大量无关碰撞 | CAV/HDV nominal following 是否缺失 |
| overlap 被自动消除 | 是否写了 hidden emergency/fallback |
| gap 系统偏差 | `x` 是否误当 center |
| speed 变负 | 是否没用 effective acceleration |
| baseline/proposed dynamics 不同 | 是否按 algorithm 使用不同 physics |

## 14. 本阶段不做

- 不生成 slot/edge；
- 不做 reservation merge；
- 不做 lane-change production；
- 不做 stochastic IDM；
- 不写 collision repair。
