# Gate D1: Lane-Change Production Claim Decision v2 中文版

## 0. Gate 定位

Gate D1 判断：

```text
论文是否保留 lane-change production 作为主张？
```

它不实现新功能。

## 1. 输入

```text
gate_D1_input/
wave_7_s5_full_action_summary.csv
rcmv_trace.csv
actions.csv
realized_events.csv
failure_summary.csv
lane_change_trace_samples/
```

## 2. 完整性检查

任一失败则 D1 fail：

```text
lane_change candidate/action/evaluation/log 不完整
LC failure 无法 join action/edge/reservation
full/boundary/lane_change_only 对比缺失
state_hash fairness 不通过
```

## 3. 支持 lane-change 主张的条件

```text
lane_change_feasible_count > 0
lane_change_selected_count > 0 或 lane_change_only 在目标场景中有明确作用
full_action_set 相比 boundary_speed_only 在 S5 有收益
收益不能完全来自不公平 baseline 或 hidden fallback
LC cost/induced failure 不抵消全部收益
trace 能解释 LC 如何改变 boundary sequence 或 receiving slot
```

## 4. 判定

### RETAIN

论文可写：

```text
lane-change production expands the action space beyond boundary-speed production and contributes to recoverable slot production in LC-targeted scenarios.
```

### DOWNGRADE

论文写为：

```text
lane-change production is implemented and observed in selected cases, but main evidence focuses on boundary-speed V0.
```

### REMOVE / FUTURE WORK

论文写为：

```text
lane-change production remains future work.
```

## 5. 输出

```text
gate_D1_report.md
gate_D1_decision.json
gate_D1_claim_revision_plan.md
```

JSON:

```json
{
  "gate": "D1",
  "decision": "retain|downgrade|remove",
  "allowed_next_stage": "Wave 8|Wave 7 fix|paper revision only",
  "supported_claims": [],
  "downgraded_claims": [],
  "required_fixes": []
}
```

## 6. 进入 Wave 8 的条件

允许进入 Wave 8 不要求 D1 一定 retain。  
但必须满足：

```text
reservation lifecycle 在 single-t0 下稳定
failure trace 可回溯
论文已明确 lane-change 主张边界
```
