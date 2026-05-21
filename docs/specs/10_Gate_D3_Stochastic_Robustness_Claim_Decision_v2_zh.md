# Gate D3: Stochastic Robustness Claim Decision v2 中文版

## 0. Gate 定位

Gate D3 判断：

```text
截至 Wave 9/Gate D3，stochastic robustness 是否可写成当前已验证或有限支持主张？
```

Gate D3 只裁决 Wave 9 evidence package 对 stochastic robustness claim 的支持强度。它不否定 `docs/paper/第3.1版论文稿.md` 作为完整研究目标草稿，也不要求删除未被当前 evidence version 验证的框架组成部分。

若 D3 结果是 `remove/future_work`，只表示当前 evidence version 不能把 stochastic robustness 写成已验证结论；若该目标仍属于后续研究计划，应标记为 `pending_later_wave_validation` 或 `future_work`，不是永久删稿令。

它不实现新功能。

## 1. 输入

```text
gate_D3_input/
edge_frequency_estimates.csv
edge_samples.csv
stochastic_reproducibility_report.csv
p_min_sensitivity.csv
noise_sensitivity.csv
stochastic_vs_deterministic_summary.csv
failure_summary.csv
```

## 2. 完整性检查

任一失败则 D3 fail：

```text
zero-noise 不等于 V0
same-seed 不可复现
sample seed prefix 不稳定
conditional denominator=0 被填 0 或 1
edge_samples 缺 sample flags
stochastic 结果无法 join deterministic action/edge/reservation trace
```

## 3. 支持 robustness 主张的条件

```text
P_R_hat/RD_mean/RD_p95 随 noise 合理变化
p_min sensitivity 单调或可解释
RPMI-CMV 在合理 noise range 内优势不崩塌
failure 增加时能解释来自 reach/surv/safe/rec 哪一环
stochastic 不与 deterministic 主链条矛盾
```

## 4. 判定

以下判定只约束当前 evidence version 的论文写法。

### RETAIN

论文可写：

```text
RPMI-CMV remains robust under bounded HDV heterogeneity and stochastic IDM perturbations.
```

### DOWNGRADE

论文写为：

```text
Stochastic tests are provided as preliminary robustness checks.
```

### REMOVE / FUTURE WORK

当前 evidence version 写为：

```text
Stochastic robustness is not validated in this evidence version and remains pending_later_wave_validation/future work.
```

## 5. 输出

```text
gate_D3_report.md
gate_D3_decision.json
gate_D3_claim_revision_plan.md
```

JSON:

```json
{
  "gate": "D3",
  "decision": "retain|downgrade|remove",
  "claim_status": "current_evidence_supported|qualified_supported|pending_later_wave_validation|unsupported_or_contradicted",
  "allowed_next_stage": "paper finalization|Wave 9 fix|paper revision only",
  "supported_claims": [],
  "downgraded_claims": [],
  "required_fixes": []
}
```
