# Phase 7 v2: Stochastic IDM V1 and Do-Not-Proceed Rules

## 1. 本阶段目标

说明何时允许进入 stochastic IDM V1，以及如何添加 HDV heterogeneity、bounded noise、scenario-frequency estimator、conditional probability logs 和 seed/repeat 设计。

V1 是鲁棒性增强，不是修复 V0 失败的手段。

## 2. 进入 V1 的前置条件

必须全部满足：

- Phase 0--6A gates 通过；
- deterministic S0 能显示 `Z_H^R` 比 raw gap 更好解释 future difficulty；
- S2/S5/S6 至少有稳定、可解释结果；
- RCMV 不经常选择明显错误 action；
- action-conditioned reservation 与 ablation 有差异；
- logs 能从 failure 回溯到 vehicle/edge/action/reservation；
- scenario readiness 机制稳定；
- RD / production cost / near-miss thresholds 已做 sensitivity。

未满足时不得通过 stochastic 掩盖问题。

## 3. 对应公式

V0 deterministic：

```math
P_e^R=I_e^{reach}I_e^{surv}I_e^{safe}I_e^{rec}
```

V1 scenario-frequency estimator：

```math
\hat P_e^R=\frac{1}{N}\sum_{n=1}^N I_{e,n}^{reach}I_{e,n}^{surv}I_{e,n}^{safe}I_{e,n}^{rec}
```

Stochastic IDM：

```math
u_h=f_{IDM}(X;\theta_h)+\eta_h(t)
```

`eta` 为 bounded/truncated zero-mean acceleration noise。

## 4. 输入与输出

| 类型 | 内容 |
|---|---|
| 输入 | passed deterministic config、stochastic config、sample count、noise seed |
| 输出 | `P_R_hat`、RD mean/p95、edge samples、sensitivity tables |
| 不输出 | SUMO/MOBIL/RL/action bundle |

## 5. 数据结构设计

```python
@dataclass(frozen=True)
class StochasticIDMConfig:
    enabled: bool
    sample_count: int
    noise_sigma: float
    noise_bound: float
    driver_class_probs: dict[str, float]
    sample_seed: int
    p_min: float = 0.8

@dataclass(frozen=True)
class EdgeFrequencyEstimate:
    edge_id: str
    sample_count: int
    P_R_hat: float
    P_reach_hat: float
    P_surv_hat: float
    P_safe_given_surv_hat: float | None
    P_rec_given_safe_surv_hat: float | None
    denom_safe_given_surv: int
    denom_rec_given_safe_surv: int
    RD_mean: float
    RD_p95: float
```

## 6. 条件概率分母为 0 的规则

如果 denominator=0：

```text
conditional_probability = NaN
conditional_probability_is_nan = True
conditional_denominator = 0
```

禁止填 0 或 1。

示例：

```python
def conditional_mean(numerators, mask):
    denom = int(sum(mask))
    if denom == 0:
        return float("nan"), 0, True
    return float(sum(n for n, m in zip(numerators, mask) if m) / denom), denom, False
```

## 7. 核心函数清单

| 函数名 | 输入 | 输出 | 作用 | 必须记录 |
|---|---|---|---|---|
| `sample_idm_params(driver_class,rng)` | class,rng | params | HDV heterogeneity | class |
| `sample_bounded_noise(rng,sigma,bound)` | rng | noise | acceleration noise | value |
| `derive_sample_seed(global_seed,edge_id,action_id,n)` | values | seed | 可复现 sample | seed |
| `rollout_stochastic_sample(state,action,config,n)` | state | rollout | single sample | sample summary |
| `estimate_edge_frequency(edge,state,action,config,N)` | edge | estimate | `P_R_hat` | per-sample flags |
| `compute_stochastic_edge_quality(edges,N)` | edges | qualities | 替代 V0 cascade | probability columns |
| `stochastic_reproducibility_check(config)` | config | report | seed repeat | report |
| `sensitivity_pmin(config_grid)` | grid | table | `p_min` sensitivity | csv |
| `sensitivity_noise(config_grid)` | grid | table | noise sensitivity | csv |

## 8. 关键流程

```text
For each action context:
  For each edge:
    For sample n=1..N:
      seed_n <- deterministic function(global_seed, edge_id, action_id, n)
      sample HDV params/noise
      rollout under same action context
      evaluate I_reach/I_surv/I_safe/I_rec/RD
    P_R_hat <- mean(product flags)
    conditional probabilities <- with denominator logging
    RD_mean/RD_p95 <- aggregate
Use:
  edge is reservable if P_R_hat >= p_min and RD statistic passes config rule
```

## 9. 示例代码

```python
def sample_bounded_noise(rng, sigma: float, bound: float) -> float:
    raw = rng.normal(0.0, sigma)
    return float(max(-bound, min(bound, raw)))
```

```python
def derive_sample_seed(global_seed: int, edge_id: str, action_id: str, n: int) -> int:
    import hashlib
    key = f"{global_seed}|{edge_id}|{action_id}|{n}"
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
```

```python
def estimate_edge_frequency(edge, current_state, action, config, N):
    flags = []
    rds = []
    for n in range(N):
        seed_n = derive_sample_seed(config.seed, edge.edge_id, action.action_id, n)
        rollout = rollout_stochastic_sample(current_state, action, config, seed_n)
        q = compute_edge_validity(edge, rollout, config)
        flags.append((q.I_reach, q.I_surv, q.I_safe, q.I_rec))
        rds.append(q.RD)

    prod = [a*b*c*d for a, b, c, d in flags]
    surv = [b for _, b, _, _ in flags]
    safe_given_mask = [bool(b) for _, b, _, _ in flags]
    safe_values = [c for _, _, c, _ in flags]
    rec_mask = [bool(b and c) for _, b, c, _ in flags]
    rec_values = [d for _, _, _, d in flags]

    p_safe, denom_safe, nan_safe = conditional_mean(safe_values, safe_given_mask)
    p_rec, denom_rec, nan_rec = conditional_mean(rec_values, rec_mask)

    return {
        "P_R_hat": float(np.mean(prod)),
        "P_surv_hat": float(np.mean(surv)),
        "P_safe_given_surv_hat": p_safe,
        "P_rec_given_safe_surv_hat": p_rec,
        "denom_safe_given_surv": denom_safe,
        "denom_rec_given_safe_surv": denom_rec,
        "conditional_probability_nan_flags": {
            "safe_given_surv": nan_safe,
            "rec_given_safe_surv": nan_rec,
        },
        "RD_mean": float(np.mean(rds)),
        "RD_p95": float(np.percentile(rds, 95)),
    }
```

## 10. 日志字段

V1 在 V0 logs 上增加：

### `edges.csv`

```text
P_R_hat
P_reach_hat
P_surv_hat
P_safe_given_surv_hat
P_rec_given_safe_surv_hat
denom_safe_given_surv
denom_rec_given_safe_surv
conditional_probability_is_nan_json
RD_mean
RD_p95
sample_count
p_min
```

### `edge_samples.csv`

```text
run_id, step, decision_context_id,
edge_id, action_id, sample_id, sample_seed,
I_reach, I_surv, I_safe, I_rec, P_R_sample,
RD, min_margin, hard_brake_count,
noise_sigma, noise_bound, driver_class_summary
```

## 11. Seed 与 repeat 设计

- global seed 控制 scenario；
- sample seed 由 global seed + edge_id + action_id + sample_id 派生；
- 同 config/seed/N 必须完全复现 sample flags；
- 不同 N 的前 N_old samples 应保持一致，便于 convergence analysis。

## 12. Toy Cases

| Toy | 构造 | 预期 |
|---|---|---|
| 7.1 zero noise | sigma=0，固定 params | `P_R_hat == P_R` |
| 7.2 same seed | 同 config 重跑 | sample flags 一致 |
| 7.3 N stability | N=10/50/200 | variance 降低趋势 |
| 7.4 p_min | p_min 升高 | reservable count 非增 |
| 7.5 denominator zero | no survival samples | conditional prob NaN + denom=0 |
| 7.6 high uncertainty | S8 | logs 指出 survival/safety/rec 降低来源 |

## 13. Do-not-proceed rules

若以下任一未跑通，不要加 SUMO、MOBIL、learning、action bundle：

| 未跑通现象 | 回查 |
|---|---|
| `Z_H^R` 不比 raw gap 更好解释困难 | `P_R`、RD、reachability、sampling strata、label policy |
| S2 无法显露差异 | readiness、near-miss、cost、theta、scenario construction |
| RCMV 明显选错 | normalization、cost、RD double counting、sign |
| action-conditioned reservation 与 ablation 无差异 | S7、regeneration、stale matching |
| logs 无法解释 failure | join keys、reservation/action/edge linkage |
| readiness 未通过 | generator、parameter sweep、mechanism target |
| RD/cost/near-miss 不稳定 | components、normalization、thresholds |

## 14. 本阶段不做

- 不接 SUMO；
- 不做 MOBIL；
- 不做 HDV lane changing；
- 不做 RL；
- 不做 action bundle；
- 不用 stochastic 修复 deterministic 错误；
- 不在无 deterministic trace 的情况下解释 stochastic 结果。
