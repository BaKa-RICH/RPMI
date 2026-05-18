# Phase 6 v2: Baselines, Ablations, Experiment Runner, and Analysis

## 1. 本阶段目标

实现最小 baseline、ablation、single-decision experiment runner 和 analysis pipeline，使 S0/S2/S5/S6 的 deterministic V0 实验可自动运行、聚合、复现和检查 failure trace。

## 2. v2 重要修改

第一轮默认：

```text
decision_mode = "single_t0_micro_episode"
```

不默认 rolling horizon。rolling horizon 属于 Phase 6B，只有 0--6A gates 通过后才启用。

## 3. 对应机制

- diagnostic inventory：`S_H^R`, `Z_H^R`;
- RCMV：`J(a)`, `RCMV(a)`;
- baseline comparison：FIFO、raw-gap、density、speed、RPMI-CMV；
- ablations：without RD、without RCMV、without action-conditioned reservation、boundary-only、no near-miss；
- metrics：delay、merge success、slot expiration、hard braking、RD、wave、failure rate、production cost。

## 4. 输入与输出

| 类型 | 内容 |
|---|---|
| 输入 | scenario configs、seeds、baseline configs、readiness filter |
| 输出 | run dirs、batch manifest、aggregate metrics、failure summary、RCMV trace、tables |
| 不输出 | SUMO/MOBIL/RL baseline |

## 5. 数据结构设计

```python
@dataclass(frozen=True)
class BaselineConfig:
    baseline_id: str
    uses_inventory: bool
    uses_rd: bool
    uses_near_miss: bool
    production_mode: Literal["none", "raw_gap", "density", "speed", "rpmi"]
    action_conditioned_reservation: bool

@dataclass(frozen=True)
class ExperimentRunSpec:
    scenario_config_path: str
    algorithm_id: str
    seed: int
    output_root: str
    mode: Literal["mechanism", "comparison"] = "comparison"

@dataclass(frozen=True)
class BatchResult:
    batch_id: str
    run_ids: list[str]
    aggregate_metrics_path: str
    failure_summary_path: str
```

## 6. Baseline 可执行定义

| Baseline | 行为 | 禁止 |
|---|---|---|
| FIFO/no production | 不主动生产；ramp 按 arrival order 尝试自然机会 | RD、RCMV、near-miss |
| raw-gap reservation | 按 geometric width 选 gap；执行失败就记录 | ramp-specific RD/reachability 用于决策 |
| density-triggered | 只看 lane density imbalance 触发 production | `Z_R`、near-miss、RCMV |
| speed-benefit | 只看 CAV 自身 expected speed gain | ramp inventory |
| RPMI-CMV | near-miss + RCMV + action-conditioned reservation | realized future labels |

Baseline 失败后不得 fallback 到 RPMI edge。

## 7. Ablations

| Ablation | 改动 | 目的 |
|---|---|---|
| without RD | `I_rec` 或 `D_bar` 关闭，按 config 明确 | 验证 recoverability |
| without RCMV | 用 density/speed trigger 选 action | 验证 objective |
| without action-conditioned reservation | action 后保持 baseline reservation | 暴露 stale |
| boundary-speed-only | Phase 5A 主方法 | V0 default |
| lane-change-only | Phase 5B 后才允许 | LC contribution |
| no near-miss screening | brute force more candidates | 验证 screening |
| slot-only matching | Hungarian debug only | 不用于主实验 |

## 8. 核心函数清单

| 函数名 | 输入 | 输出 | 作用 | 必须记录 |
|---|---|---|---|---|
| `run_experiment(run_spec)` | spec | run_dir | 单 run | all logs |
| `run_single_t0_episode(config,state)` | config,state | metrics | V0 default | metrics |
| `apply_baseline_policy(policy_id,state,context)` | id | decision | baseline action/reservation | actions |
| `apply_rpmi_policy(state,context)` | state | decision | proposed | action eval |
| `readiness_filter(config,state)` | config | pass/fail | comparison gate | readiness |
| `run_baseline_suite(scenarios,seeds,baselines)` | lists | run dirs | fair suite | manifest |
| `aggregate_metrics(run_dirs)` | paths | csv | metrics | aggregate |
| `aggregate_failures(run_dirs)` | paths | csv | failure events | failure summary |
| `collect_rcmv_trace(run_dirs)` | paths | csv | RCMV | trace |
| `generate_summary_tables(batch)` | batch | tables | paper-ready data | csv |
| `replay_trace_summary(run_dir)` | path | md/json | failure inspection | trace |

## 9. Single-decision run flow

```text
1. Phase0 initialize run
2. Generate scenario state
3. Compute state_hash
4. Run readiness using no-action diagnostics
5. If comparison mode and readiness fails:
     write status=readiness_failed
     stop comparison
6. At t0:
     build decision context
     apply baseline or RPMI policy
     create reservations
7. Execute selected action/guidance until evaluation horizon
8. Log vehicles/events/reservations/metrics
9. Write metrics_episode.json
```

## 10. Baseline suite fairness

同一 `scenario_id + seed` 下：

```text
initial state_hash must be identical across algorithms
dynamics config must be identical
logging schema must be identical
readiness result must be identical or derived from the same no-action diagnostics
```

如果 state hash 不一致，batch invalid。

## 11. 示例代码

```python
def run_experiment(run_spec: ExperimentRunSpec) -> Path:
    config = load_config(run_spec.scenario_config_path, algorithm_id=run_spec.algorithm_id, seed=run_spec.seed)
    run_dir = initialize_run(config, run_spec.output_root)
    state = generate_initial_state(config)
    state_hash = hash_state(state)
    write_state_hash(run_dir, state_hash)

    readiness = compute_and_log_readiness(state, config, run_dir)
    if run_spec.mode == "comparison" and not readiness.readiness_pass:
        write_episode_status(run_dir, "readiness_failed", readiness.fail_reason)
        return run_dir

    if config.sim.decision_mode == "single_t0_micro_episode":
        metrics = run_single_t0_episode(config, state, run_dir)
    else:
        raise NotImplementedError("rolling is Phase 6B, not V0 default")

    write_episode_metrics(run_dir, metrics)
    return run_dir
```

```python
def run_baseline_suite(scenario_paths, seeds, baseline_ids, output_root):
    run_dirs = []
    for scenario_path in scenario_paths:
        for seed in seeds:
            # generator must be deterministic by scenario_path + seed
            for baseline_id in baseline_ids:
                spec = ExperimentRunSpec(scenario_path, baseline_id, seed, output_root)
                run_dirs.append(run_experiment(spec))
    verify_state_hash_fairness(run_dirs)
    return aggregate_metrics(run_dirs)
```

## 12. Batch outputs

```text
outputs_batch/<batch_id>/
  batch_manifest.csv
  aggregate_metrics.csv
  failure_summary.csv
  rcmv_trace.csv
  readiness_failures.csv
  baseline_comparison_summary.csv
  ablation_comparison_summary.csv
  s0_predictor_outcome_summary.csv
  figures/
  runs/<run_id>/...
```

## 13. Episode metrics

```text
mean_ramp_delay
merge_success_count
failed_reservation_count
failed_reservation_rate
slot_expiration_count
slot_expiration_rate
mean_RD_matched
hard_brake_count
max_wave_amplitude
no_fallback_invalid_event_count
throughput_outflow
mean_Z_R
production_cost_sum
selected_action_type
stale_reservation_count
```

## 14. Analysis plan

| Experiment | Analysis |
|---|---|
| S0 | predictor/outcome correlation, rank correlation, simple regression |
| S2 | baseline comparison on delay/failure/RD/wave/cost |
| S5 | boundary type vs selected action and outcome |
| S6 | raw-gap illusion trace inspection |
| S7 optional | action-conditioned reservation vs stale ablation |
| Phase 5B optional | LC vs boundary-speed contribution |
| Phase 7 optional | stochastic sensitivity |

CSV tables first, figures second。Notebook 只能读 CSV，不作为唯一数据入口。

## 15. Toy Cases

| Toy | 构造 | 预期 |
|---|---|---|
| 6.1 one scenario multi baseline | S5 toy + FIFO/raw/RPMI | 3 run dirs, aggregate 3 rows |
| 6.2 readiness filter | invalid S2 | status readiness_failed |
| 6.3 fairness | same scenario/seed | same state_hash |
| 6.4 ablation identity | without_RD | only RD usage changes |
| 6.5 no fallback equal logging | baseline/proposed | both log failures |
| 6.6 single-decision default | config default | no rolling artifacts |

## 16. 阶段验收条件

- 一个 scenario + 多 baseline 自动运行；
- readiness fail 不进入 comparison；
- state_hash fairness check 通过；
- aggregate metrics 可复算；
- failure summary 可追溯到 reservation/action/edge；
- RCMV trace 输出；
- summary tables 可用于论文图表；
- no SUMO/MOBIL/RL baseline。

## 17. Phase 6B rolling 进入条件

只有满足以下条件才进入：

- single-decision S2/S5/S6 可解释；
- reservation lifecycle 在 single episode 中稳定；
- stale ablation 有可解释差异；
- logs 能解释 action/reservation failure；
- baseline suite 可复现。

Phase 6B 需新增：

```text
reservation persistence
replanning cancellation
overlapping action rule
partial execution
stale reservation refresh
rolling decision_context_id
```

## 18. 常见失败与回查

| 失败 | 回查 |
|---|---|
| proposed/baseline initial 不同 | generator/state hash |
| raw-gap baseline 太强 | 是否偷偷用了 reachability/RD；scenario illusion |
| density baseline 太强 | density trap 是否成立 |
| ablation 与 full 一样 | flag 是否真正影响 decision |
| aggregate 不能复算 | episode metrics 与 step logs |
| failure events 丢失 | no-fallback logging 是否所有 algorithms 开启 |
| RCMV 全 no-action | near-miss/profile/cost/theta |

## 19. 本阶段不做

- 不接 SUMO；
- 不做 MOBIL/RL；
- 不完整复现 CoMC/DCoMA；
- 不默认 rolling；
- 不让 baseline 使用 proposed 信息；
- 不用 notebook 代替 pipeline。
