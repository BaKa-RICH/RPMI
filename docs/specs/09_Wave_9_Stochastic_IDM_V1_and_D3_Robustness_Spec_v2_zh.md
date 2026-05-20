# Wave 9: Stochastic IDM V1 and D3 Robustness Spec v2 中文版

## 0. 本阶段定位

Wave 9 实现 stochastic IDM V1。  
它替代旧 Phase 7 命名。

V1 是鲁棒性增强，不是修复 V0 失败的手段。

## 1. Codex 执行合约

只允许实现：

```text
HDV heterogeneity
bounded/truncated zero-mean acceleration noise
scenario-frequency estimator P_R_hat
conditional probability denominator logs
sample seed/repeat design
stochastic sensitivity evidence
```

禁止：

```text
SUMO
MOBIL
RL
action bundle
用 stochastic 掩盖 deterministic 失败
无 deterministic trace 的 stochastic 解释
```

## 2. 进入条件

必须满足：

```text
D0 pass 或 conditional pass 且修复项完成
deterministic S2/S5/S6/S7/S8 结果可解释
RCMV 不经常明显选错
action-conditioned reservation 与 ablation 有差异
logs 能从 failure 回溯
RD/cost/near-miss thresholds 已做基本 sensitivity
```

若 deterministic V0 主链条不成立，不得进入 Wave 9。

## 3. 核心公式

V0:

```math
P_e^R=I_e^{reach}I_e^{surv}I_e^{safe}I_e^{rec}
```

V1:

```math
\hat P_e^R=\frac{1}{N}\sum_{n=1}^N I_{e,n}^{reach}I_{e,n}^{surv}I_{e,n}^{safe}I_{e,n}^{rec}
```

Stochastic IDM:

```math
u_h=f_{IDM}(X;\theta_h)+\eta_h(t)
```

其中 `eta` 是 bounded/truncated zero-mean acceleration noise。

## 4. 数据结构

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

## 5. 条件概率 denominator = 0

规则：

```text
conditional_probability = NaN
conditional_probability_is_nan = True
conditional_denominator = 0
```

禁止填 0 或 1。

## 6. sample seed 规则

```text
global seed 控制 scenario
sample seed = hash(global_seed, edge_id, action_id, sample_id)
同 config/seed/N 必须复现 sample flags
N 增大时前 N_old samples 保持一致
```

## 7. 核心函数

```text
sample_idm_params(driver_class,rng)
sample_bounded_noise(rng,sigma,bound)
derive_sample_seed(global_seed,edge_id,action_id,n)
rollout_stochastic_sample(state,action,config,n)
estimate_edge_frequency(edge,state,action,config,N)
compute_stochastic_edge_quality(edges,N)
stochastic_reproducibility_check(config)
sensitivity_pmin(config_grid)
sensitivity_noise(config_grid)
```

## 8. 日志补丁

### edges.csv 新增

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

### edge_samples.csv 新增

```text
run_id
decision_context_id
edge_id
action_id
sample_id
sample_seed
I_reach
I_surv
I_safe
I_rec
P_R_sample
RD
min_margin
hard_brake_count
noise_sigma
noise_bound
driver_class_summary
```

## 9. Toy tests

| Test | 构造 | 预期 |
|---|---|---|
| W9.1 zero noise | sigma=0 固定参数 | P_R_hat == P_R |
| W9.2 same seed | 同 config 重跑 | sample flags 一致 |
| W9.3 N prefix | N=10/50 | 前 10 samples 一致 |
| W9.4 p_min monotonic | p_min 升高 | reservable count 非增 |
| W9.5 denominator zero | no survival samples | NaN + denom=0 |
| W9.6 uncertainty trace | S8 | 可解释 survival/safety/rec 来源 |

## 10. 实验设计

至少输出：

```text
stochastic_reproducibility_report.csv
p_min_sensitivity.csv
noise_sensitivity.csv
stochastic_vs_deterministic_summary.csv
edge_frequency_estimates.csv
edge_samples.csv
gate_D3_input/
```

## 11. 进入 Gate D3 条件

```text
zero-noise 与 V0 一致
same-seed 可复现
conditional denominator 规则正确
sensitivity 表可读
stochastic 结果能回溯到 deterministic trace
```
