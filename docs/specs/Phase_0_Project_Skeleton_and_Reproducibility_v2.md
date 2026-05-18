# Phase 0 v2: Project Skeleton, Reproducibility, and Global Dictionary

## 1. 本阶段目标

建立最小项目结构、配置系统、随机种子、run directory、config snapshot、空日志 schema，以及全局数据字典。

本阶段不实现任何交通算法。

## 2. 本阶段为什么必要

RPMI-CMV V0 的结论依赖跨 scenario、baseline、seed 的可复现比较。若没有统一 ID、单位、state hash、decision context、config hash，后续无法追溯：

```text
vehicle -> slot -> edge -> matching -> action -> reservation -> realized event
```

Gate 0 不通过，后续所有实验无效。

## 3. 对应论文机制/公式

本阶段不实现公式，但必须为以下量提供统一配置：

- `dt`, `H`, `dt_merge`;
- `RD_max`, `lambda_D`, `lambda_C`, `theta`;
- `W_min_buffer`, `production_width_buffer`, `T_prod`;
- demand weight 参数 `chi_w`, `chi_d`, `d_crit`, `epsilon_D`;
- conflict mode；
- decision mode；
- V0/V1 feature flags。

## 4. 输入与输出

| 类型 | 内容 |
|---|---|
| 输入 | YAML/JSON config、scenario id、algorithm id、seed、output root |
| 输出 | run directory、config snapshot、global conventions、empty log headers、state hash placeholder |
| 不输出 | traffic dynamics、slots、edges、matching、RCMV |

## 5. 全局约定与数据字典

必须保存为 `global_conventions.json` 或写入 `run_config.json`。

| 字段 | 约定 |
|---|---|
| `units_version` | `rpmi_units_v1` |
| distance | meter |
| time | second |
| speed | m/s |
| acceleration | m/s^2 |
| `x` | front bumper position |
| occupied interval | `[x - length, x]` |
| lane ordering | same lane 中 `x` 越大越靠前 |
| ramp lane | `lane=-1` |
| target lane | config 显式指定 |
| `time` | absolute simulation time |
| `step` | integer step |
| `decision_context_id` | `dc_{run_id}_{step}` 或 single episode 的 `dc_t0` |
| `slot_id` | 包含 `front_id,rear_id,k,action_context` |
| `edge_id` | 包含 `ramp_id,front_id,rear_id,k,action_context` |
| `action_id` | 包含 `action_type,index` |
| `reservation_id` | 绑定 selected `action_id` 和 `edge_id` |
| `state_hash` | 初始 state canonical JSON hash |
| `code_version` | git commit；无 git 时用 `local_dirty` |

## 6. 推荐目录结构

```text
rpmi_v0/
  pyproject.toml
  configs/
    scenarios/
    baselines/
  src/rpmi/
    config.py
    logging_schema.py
    reproducibility.py
    state.py
    dynamics.py
    slots.py
    matching.py
    scenarios.py
    actions.py
    reservations.py
    runner.py
    analysis.py
  tests/
    test_phase0_reproducibility.py
    test_phase1_dynamics.py
    ...
  outputs/
```

不要在 Phase 0 做 plugin system、distributed runner、GUI。

## 7. 数据结构设计

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class SimConfig:
    dt: float = 0.1
    H: float = 12.0
    dt_merge: float = 0.5
    total_time: float = 30.0
    decision_mode: Literal["single_t0_micro_episode", "rolling"] = "single_t0_micro_episode"

@dataclass(frozen=True)
class AlgorithmConfig:
    RD_max: float = 1.0
    W_min_buffer: float = 0.0
    production_width_buffer: float = 0.5
    W_prod_bar: float = 6.0
    lambda_D: float = 1.0
    lambda_C: float = 1.0
    theta: float = 0.05
    top_k_actions: int = 8
    conflict_mode: Literal["time_window_default", "whole_horizon_debug", "slot_only_debug"] = "time_window_default"

@dataclass(frozen=True)
class DemandWeightConfig:
    chi_w: float = 0.0
    chi_d: float = 0.0
    d_crit: float = 120.0
    epsilon_D: float = 1e-9
    default_omega: float = 1.0

@dataclass(frozen=True)
class FeatureFlags:
    stochastic_idm: bool = False
    sumo: bool = False
    mobil: bool = False
    action_bundle: bool = False
    learning: bool = False
    lane_change_production: bool = False
    rolling_reservation: bool = False

@dataclass(frozen=True)
class RunConfig:
    scenario_id: str
    algorithm_id: str
    seed: int
    sim: SimConfig
    algorithm: AlgorithmConfig
    demand: DemandWeightConfig
    flags: FeatureFlags
    log_level: Literal["summary", "trace", "debug"] = "trace"
```

## 8. 核心函数清单

| 函数名 | 输入 | 输出 | 作用 | 必须记录 |
|---|---|---|---|---|
| `load_config(path)` | path | `RunConfig` | 读取配置 | source path |
| `validate_v0_flags(config)` | config | None/error | 禁用 SUMO/MOBIL/RL/action_bundle | feature flags |
| `config_to_canonical_dict(config)` | config | dict | 稳定排序 config | canonical json |
| `hash_config(config_dict)` | dict | str | 生成 hash | `config_hash` |
| `hash_state(state)` | state | str | 初始状态公平性 hash | `state_hash` |
| `make_run_id(config, config_hash)` | config | str | run id | run id |
| `set_global_seed(seed)` | int | rng | random/numpy seed | seed |
| `create_run_directory(root, run_id)` | path,str | path | 创建输出目录 | output paths |
| `init_empty_logs(run_dir)` | path | files | 写空表头 | schema version |

## 9. 关键流程

```text
1. load config
2. validate V0 flags
3. build global conventions
4. canonicalize config
5. hash config
6. set seed
7. create run directory
8. save run_config.json, config_hash.txt, seed.txt, global_conventions.json
9. init empty logs with shared join keys
```

## 10. 示例代码

```python
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone

def stable_json(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def short_hash(obj: dict, n: int = 12) -> str:
    return hashlib.sha256(stable_json(obj).encode("utf-8")).hexdigest()[:n]

def make_run_id(scenario_id: str, algorithm_id: str, seed: int, config_hash: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{stamp}_{scenario_id}_{algorithm_id}_seed{seed:04d}_{config_hash}"

def create_run_directory(output_root: str | Path, run_id: str) -> Path:
    run_dir = Path(output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    for name in ["figures", "debug_snapshots", "tables"]:
        (run_dir / name).mkdir()
    return run_dir
```

## 11. 必须初始化的日志表

```text
run_config.json
global_conventions.json
scenario_manifest.json
readiness_summary.csv
vehicles_step.csv
slots.csv
edges.csv
near_miss_edges.csv
actions.csv
action_evaluations.csv
matching.csv
reservations.csv
realized_events.csv
metrics_step.csv
metrics_episode.json
```

所有 CSV 至少包含：

```text
run_id, step, time, decision_context_id, state_hash, config_hash, code_version, units_version
```

若某阶段暂不使用字段，留空，不改表名。

## 12. 单元测试 / Toy Cases

| Toy | 测试 | 预期 |
|---|---|---|
| 0.1 same seed | 同 config + seed 生成 deterministic fake state | `state_hash` 一致 |
| 0.2 different seed | 同 config 不同 seed | config hash 可相同，state hash 可不同 |
| 0.3 feature lock | `sumo=true` 或 `action_bundle=true` | validator 抛错 |
| 0.4 schema exists | 初始化空 run | 所有日志表存在 |
| 0.5 ID convention | 构造 slot/edge/action/reservation id | 包含必要组成字段 |

## 13. 阶段验收条件

- 能创建空 run；
- 保存 config、seed、config hash、global conventions；
- 初始化全部日志表；
- 同 config + seed 可复现；
- 禁用 V0 不允许的 feature flags；
- 不涉及任何交通算法。

## 14. 常见失败模式与回查

| 失败 | 回查 |
|---|---|
| 同 seed 不可复现 | 是否使用未设 seed RNG；是否用当前时间生成 scenario |
| config hash 不稳定 | dict 是否排序；浮点是否 canonical |
| baseline/proposed state 不同 | scenario 是否每个 algorithm 重采样 |
| logs 无法 join | 是否缺 `decision_context_id/state_hash` |
| 误开 V1 功能 | `validate_v0_flags` 是否覆盖所有 flag |

## 15. 本阶段不做

- 不实现 dynamics；
- 不生成 scenario；
- 不实现 slot、edge、matching；
- 不引入 SUMO/MOBIL/RL；
- 不写 plugin platform。
