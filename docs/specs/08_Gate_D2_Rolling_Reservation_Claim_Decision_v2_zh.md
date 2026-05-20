# Gate D2: Rolling Reservation Claim Decision v2 中文版

## 0. Gate 定位

Gate D2 判断：

```text
论文是否保留 rolling horizon reservation 主张？
```

它不实现新功能。

## 1. 输入

```text
gate_D2_input/
decision_contexts.csv
reservation_replans.csv
action_lifecycle.csv
aggregate_metrics.csv
failure_summary.csv
rolling_trace_samples/
```

## 2. 完整性检查

任一失败则 D2 fail：

```text
decision_context_id 不唯一
reservation refresh/cancel/supersede 无日志
action partial execution 无日志
failure 无法 join 到 context/action/reservation
rolling 和 single 初始状态不公平
```

## 3. 支持 rolling 主张的条件

```text
rolling_decision_count > 1
rolling_consistency_violation_count 可控
rolling 相比 single_t0 在 stale/expiration/failure/delay 至少一类指标上有可解释收益
收益来自 replan/refresh/cancel，而不是 hidden fallback
trace 能显示 reservation lifecycle 的合理变化
```

## 4. 判定

### RETAIN

论文可写：

```text
rolling horizon reservation improves reservation consistency under evolving traffic states.
```

### DOWNGRADE

论文写为：

```text
rolling horizon is implemented as an extension; main evidence remains single-decision deterministic V0.
```

### REMOVE / FUTURE WORK

论文写为：

```text
rolling horizon reservation is future work.
```

## 5. 输出

```text
gate_D2_report.md
gate_D2_decision.json
gate_D2_claim_revision_plan.md
```

JSON:

```json
{
  "gate": "D2",
  "decision": "retain|downgrade|remove",
  "allowed_next_stage": "Wave 9|Wave 8 fix|paper revision only",
  "supported_claims": [],
  "downgraded_claims": [],
  "required_fixes": []
}
```
