# Phase 4 v2: Scenario Generators and Algorithm-Independent Readiness Tests

## 1. 本阶段目标

把 S0、S2、S5、S6 等场景做成可调试、可复现、可参数扫描的 scenario generator，并在算法比较前执行 algorithm-independent readiness test。

## 2. 本阶段为什么必要

场景不是 one-shot。若没有 near-miss、没有 deficit、没有 boundary CAV、没有 raw-gap illusion，算法没效果不代表理论错。反过来，如果 readiness 直接筛选 proposed 胜利样本，也会破坏实验可信度。

## 3. v2 核心原则

Readiness 可以使用：

```text
initial state
no-action rollout
diagnostic slots/edges/matching
cheap near-miss availability
```

Readiness 禁止使用：

```text
selected RPMI action outcome
proposed advantage
future realized comparison result
```

## 4. 对应机制

- `G_H` 与 `S_H^R/Z_H^R` 分离；
- near-critical outer-lane；
- near-miss producible edge；
- boundary type 到 production mode 的可用性；
- raw-gap illusion；
- density trap；
- speed-benefit trap；
- action-conditioned reservation 的 stale risk。

## 5. 输入与输出

| 类型 | 内容 |
|---|---|
| 输入 | scenario config、seed、parameter grid、road geometry、mechanism target |
| 输出 | initial `TrafficState`、scenario manifest、readiness report、sweep report |
| 不输出 | final RCMV comparison result |

## 6. 数据结构设计

```python
@dataclass(frozen=True)
class ScenarioConfig:
    scenario_id: str
    seed: int
    road: dict
    simulation: dict
    vehicles: dict
    ramp: dict
    mechanism_targets: dict
    readiness_targets: dict

@dataclass(frozen=True)
class ReadinessReport:
    scenario_id: str
    seed: int
    readiness_pass: bool
    fail_reason: str
    metrics: dict
    recommended_adjustments: list[str]
    algorithm_independent: bool = True
```

## 7. Shared near-miss classifier

Phase 4 不生成 action，但要用 Phase 5 也会用的同一个 classifier 统计 near-miss availability：

```python
@dataclass(frozen=True)
class NearMissLabel:
    is_near_miss: bool
    near_miss_type: str
    delta_W_req: float
    available_modes: tuple[str, ...]
    screen_score: float
    reason: str
```

```python
def classify_near_miss(edge_quality, boundary_type, params) -> NearMissLabel:
    ...
```

Phase 4 只读取 `NearMissLabel`，不得调用 action rollout。

## 8. 核心函数清单

| 函数名 | 输入 | 输出 | 作用 | 必须记录 |
|---|---|---|---|---|
| `load_scenario_config(path)` | path | config | 读取配置 | manifest |
| `generate_initial_vehicles(config,rng)` | config | vehicles | 构造 micro-state | initial state |
| `apply_template_perturbation(vehicles,rng,config)` | vehicles | vehicles | seed 控制扰动 | perturbation |
| `generate_s0_samples(config,N)` | config | states | 分层 S0 | sample manifest |
| `generate_s2_near_critical(config)` | config | state | near-critical outer lane | manifest |
| `generate_s5_boundary_templates(config)` | config | states | boundary type coverage | coverage |
| `generate_s6_raw_gap_illusion(config)` | config | state | raw gap illusion | illusion type |
| `compute_readiness_metrics(state,config)` | state | metrics | no-action diagnostics | metrics |
| `readiness_check(metrics,config)` | metrics | report | gate | readiness |
| `parameter_sweep_for_readiness(config,grid)` | config | accepted configs | 找合格场景 | sweep report |

## 9. 场景机制卡片

### S0 Mechanism Sampling

| 项 | 内容 |
|---|---|
| 目标 | 验证 inventory metrics 的解释力 |
| 旋钮 | raw gap、ramp demand、ramp speed、arrival timing、outer density、speed difference |
| readiness | raw gap high/low 与 `Z_H_R` high/low 均有样本 |
| 禁止 | 用 proposed outcome 选择样本 |

### S2 Near-Critical Outer-Lane

| 项 | 内容 |
|---|---|
| 目标 | boundary-speed RCMV 在 near-critical 外侧车道中优于 raw/density/speed baseline |
| 旋钮 | outer spacing、ramp demand、CAV penetration、near-miss deficit、inner lane spare capacity |
| readiness | `Z_R_0>0`, near_miss>0, boundary CAV 可用 |
| 失败调整 | 调 outer spacing、ramp arrival、CAV boundary、demand |

### S5 Boundary-Control

| 项 | 内容 |
|---|---|
| 目标 | 比较 front_acc、rear_dec、front_rear、no action |
| 旋钮 | boundary type、gap deficit、CAV position、speed difference |
| readiness | CAV-HDV、HDV-CAV、CAV-CAV、HDV-HDV 分布可观测 |
| Phase 5A | 不要求 lane-change |

### S6 Raw-Gap Illusion

| 项 | 内容 |
|---|---|
| 目标 | raw gap 多但对具体 ramp 不可达/高 RD/易过期 |
| 旋钮 | ramp speed、gap timing、distance to ramp end、rear braking risk |
| readiness | `G_H` 高、`S_R_0` 低、`Z_R_0` 高，invalid reasons 可解释 |
| 失败调整 | 加大 timing mismatch 或 RD burden |

### Optional S7

| 项 | 内容 |
|---|---|
| 目标 | action-conditioned reservation vs stale reservation ablation |
| readiness | action 后 baseline selected edge 会失效或不再最优 |
| 进入条件 | Phase 5A reservation lifecycle 已通过 |

### Optional S8

| 项 | 内容 |
|---|---|
| 目标 | V1 stochastic high uncertainty |
| readiness | V0 deterministic 已稳定 |
| 进入条件 | Phase 7 |

## 10. Readiness metrics

```text
G_H
raw_time_expanded_slot_count
D_H
S_R_0
Z_R_0
reservable_edge_count
near_miss_edge_count
near_miss_by_type
boundary_CAV_HDV
boundary_HDV_CAV
boundary_CAV_CAV
boundary_HDV_HDV
inner_receiving_gap_count
raw_gap_illusion_count
dominant_invalid_reasons
readiness_pass
fail_reason
```

## 11. 示例代码

```python
def readiness_check(metrics: dict, config: ScenarioConfig) -> ReadinessReport:
    t = config.readiness_targets
    failures = []

    if metrics["G_H"] < t.get("raw_gap_count_min", 0):
        failures.append("raw_gap_count_too_low")
    if metrics["Z_R_0"] < t.get("baseline_ZR_min", 0.0):
        failures.append("baseline_deficit_too_low")
    if metrics["near_miss_edge_count"] < t.get("near_miss_count_min", 0):
        failures.append("near_miss_too_low")
    if metrics.get("boundary_cav_available_count", 0) < t.get("boundary_cav_min", 0):
        failures.append("boundary_cav_unavailable")

    return ReadinessReport(
        scenario_id=config.scenario_id,
        seed=config.seed,
        readiness_pass=len(failures) == 0,
        fail_reason=";".join(failures),
        metrics=metrics,
        recommended_adjustments=suggest_adjustments(failures),
        algorithm_independent=True,
    )
```

## 12. Parameter sweep 规则

允许：

- 为找到机制合格状态扫 outer spacing、ramp demand、arrival time、CAV penetration；
- 保存失败尝试；
- 报告 accepted/rejected 数量。

禁止：

- 根据 proposed 是否赢来筛选；
- 隐藏失败 sweep；
- 修改 baseline/proposed 物理配置。

## 13. Toy Cases

| Toy | 构造 | 预期 |
|---|---|---|
| 4.1 S0 coverage | 16+ stratified samples | raw high/low + Z high/low 均覆盖 |
| 4.2 S2 readiness | near-critical config | `Z_R_0>0`, near_miss>0 |
| 4.3 S5 boundary coverage | 四类 boundary | 每类计数可记录 |
| 4.4 S6 illusion | raw gap high, reach/RD fail | `G_H` 高、`S_R_0` 低 |
| 4.5 readiness blocks | near_miss=0 | comparison run stops |
| 4.6 no proposed leakage | readiness 不调用 action rollout | code/test 检查 |

## 14. 阶段验收条件

- 每个核心场景可输出 readiness report；
- readiness fail 阻止 comparison；
- S0/S2/S5/S6 各至少一个 seed 可通过；
- near-miss classifier 与 Phase 5 共用；
- sweep 记录失败尝试；
- readiness algorithm-independent。

## 15. 常见失败与回查

| 失败 | 优先调整 |
|---|---|
| `Z_R≈0` | 提高 demand、压缩 outer gap、错开 ramp timing |
| near-miss=0 | 放松 spacing、增加 CAV boundary、调整 W buffer |
| action mode 不可用 | 检查 boundary CAV 类型 |
| raw-gap baseline 太强 | 构造 reachability/RD illusion |
| density baseline 太强 | 构造 density trap |
| readiness 像 cherry-pick | 检查是否读取 proposed outcome |

## 16. 本阶段不做

- 不运行 final RCMV comparison；
- 不生成 production action；
- 不做 stochastic IDM；
- 不实现 MOBIL/HDV lane change；
- 不构建通用仿真平台。
