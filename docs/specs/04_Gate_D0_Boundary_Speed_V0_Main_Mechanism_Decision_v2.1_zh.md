# Gate D0: Boundary-Speed V0 Main Mechanism Decision v2.1 中文版

## v2.1 更新说明：denominator 与论文解释红线

本次 v2.1 的全局补丁来自 A1/A2/A3 与 B/C 类判定。

所有 evidence package、Gate 输入、论文图表和实验表格必须同时报告两类 denominator：

```text
reservation denominator:
  failed_reservation_rate = failed_reservation_count / generated_reservation_count
  generated_reservation_count = reservation_count 或 planned_reservation_count，必须显式标注

demand denominator:
  merge_success_rate_over_demand = merge_success_count / D_H
  predicted_unserved_demand_rate = predicted_unserved_demand_count / D_H
  realized_unserved_demand_rate = realized_unserved_demand_count / D_H
```

禁止把：

```text
failed_reservation_rate = 0
```

单独解释为：

```text
merge success 高
proposed 成功服务 demand
RPMI-CMV 显著提高合流成功率
```

正确解释必须区分：

```text
没有生成坏 reservation
≠ ramp demand 已被服务
≠ merge success over demand 提高
```

## 0. Gate 定位

Gate D0 是第一个论文主张决策门。

它不实现新功能。  
它只回答：

```text
截至 Wave 6A+/Gate D0，当前 boundary-speed deterministic single-t0 V0 是否足以支撑当前阶段 mechanism-level evidence claim？
```

Gate D0 不否定 `docs/paper/第3.1版论文稿.md` 作为完整研究目标草稿，也不裁决 Wave 7 lane-change、Wave 8 rolling reservation、Wave 9 stochastic robustness 的最终有效性。后续模块若尚未被 D0 验证，应标记为 `pending_later_wave_validation`，而不是从论文目标中删除。

## 1. Codex 执行合约

本 Gate 只允许：

```text
读取 Wave 6A.0 + Wave 6A+ evidence package
检查完整性和公平性
生成 Gate D0 report
生成论文主张建议
标出必须修改的代码/场景/论文
```

禁止：

```text
实现 lane-change
实现 rolling
实现 stochastic
调参掩盖失败
删除不利结果
把 inconclusive 写成 support
```

## 2. Gate 输入

必须存在：

```text
gate_D0_input/gate_D0_manifest.json
aggregate_metrics_completed.csv
aggregate_metrics_readiness_fail.csv
failure_summary_main_batch.csv
failure_summary_readiness_fail.csv
state_hash_fairness.csv
scenario_mechanism_summary.csv
baseline_comparison_summary.csv
ablation_comparison_summary.csv
rcmv_trace_top_actions.csv
positive_rcmv_micro/
  positive_rcmv_manifest.json
  positive_rcmv_aggregate_metrics.csv
  positive_rcmv_failure_summary.csv
  positive_rcmv_rcmv_trace.csv
  positive_rcmv_action_evaluations.csv
  positive_rcmv_reservations.csv
failure_trace_samples/
trace_replay_summaries/
paper_claim_support_table.csv
```

Gate D0 不接受只有单个 `failure_summary.csv` 的输入。

## 3. 硬性完整性检查

任一失败，则 D0 不通过：

```text
state_hash_fairness 有 fail
aggregate_metrics_completed 缺关键算法
rcmv_trace 缺 selected/candidate
failure_summary 无法 join action/edge/reservation
readiness_failed 与 completed 混算
scenario manifest 缺 mechanism_target
缺 failed_reservation_denominator 或 demand denominator 字段
positive RCMV micro package 缺失且论文仍试图声明 RCMV production effectiveness
failure_summary_main_batch/readiness_fail/positive_rcmv 文件被覆盖或缺失
```

## 4. D0 决策问题

### Q1. raw-gap illusion 是否被证明？

支持条件：

```text
S2 或 S6 中 raw_gap_illusion_rate > 0
raw_gap baseline 的失败/低 P_R/高 RD 可追溯
RPMI-CMV 没有依赖 raw W 单独决策
```

### Q2. near-miss -> production 是否成立？

支持条件：

```text
S5 中 near_miss_edge_count > 0
candidate_action_count > 1
positive_RCMV_candidate_count > 0
selected_non_none_rate 可解释
action 后 selected_S_R 上升或 selected_Z_R 下降
若 selected_action_type = none，则只能支持 inventory/matching success，不能支持 production action effectiveness
```

### Q3. RCMV 是否合理？

支持条件：

```text
best RCMV 与 selected action 一致
selected_RCMV > theta 时才执行非 none
positive RCMV micro package 中至少有一个 selected_RCMV>0 的可复核案例，若要声明 production effectiveness
J/Z/D/C 分项可解释
反例能通过 failure trace 定位原因
```

### Q4. RD 是否提供独立贡献？

支持条件：

```text
without_rd 与 full 有决策或结果差异
RD 差异与 failure/hard_brake/wave/invalid reason 有一致解释
RD 没有被重复惩罚造成不可解释选择
```

### Q5. action-conditioned reservation 是否必要？

支持条件：

```text
full 优于 without_action_conditioned_reservation
stale_reservation_harm 或 action_conditioned_gain 可见
stale failure trace 可回溯
```

### Q6. near-miss screening 是否必要？

支持条件：

```text
without_near_miss 候选更多或无效更多
full 保留主要 positive candidate
screening 没有明显漏掉关键 action
```

## 5. D0 判定

### PASS

条件：

```text
完整性检查全 pass
reservation denominator 与 demand denominator 字段完整
failure_summary 分层文件完整且未覆盖
S2/S5/S6/S7/S8 至少 4 组 partial_support 以上
其中 S5 必须 partial_support 或 clear_support
RCMV trace 符号和选择逻辑可解释
没有无法解释的系统性反例
```

论文可写：

```text
deterministic single-t0 boundary-speed V0 支持 mechanism-level V0 evidence。
```

PASS 不允许提前声称 Wave 7/8/9 尚未验证的内容。若没有 realized-valid positive non-none RCMV production case，只能写 mechanism-level inventory/reservation/avoidance evidence，不得写 production action effectiveness。

可进入：

```text
Wave 7
```

### CONDITIONAL PASS

条件：

```text
完整性检查全 pass
S5 支持，但 S6/S7/S8 中有 1--2 组 inconclusive
反例可以定位为场景不足、指标不足或实现小 bug
```

论文可写：

```text
boundary-speed V0 provides preliminary/mechanism-level staged evidence。
```

CONDITIONAL PASS 表示当前 V0 evidence 可支撑谨慎阶段性 claim。D0_fixlist 是阶段性 claim hygiene / evidence hygiene，不是最终论文删稿令；完成后可继续 Wave 7 验证更强 claim。

### FAIL

条件之一：

```text
完整性检查失败
S5 不支持 production 主链条
RCMV 常选明显错误 action 且无法解释
action-conditioned reservation 无差异且无法解释
failure trace 无法回溯
baseline fairness 不通过
```

不得进入 Wave 7。  
必须先修 Wave 6A.0/6A+ 或修改当前阶段 claim。FAIL 不等于后续 Wave 永久无效，只表示 D0 阶段 evidence package 不足以支撑 D0 阶段机制 claim。

## 6. 输出文件

Gate D0 必须输出：

```text
gate_D0_report.md
gate_D0_decision.json
gate_D0_claim_revision_plan.md
gate_D0_fixlist.md
```

`gate_D0_decision.json`：

```json
{
  "gate": "D0",
  "decision": "pass|conditional_pass|fail",
  "supported_claims": [],
  "downgraded_claims": [],
  "removed_claims": [],
  "required_fixes_before_next_wave": [],
  "allowed_next_stage": "Wave 7|Wave 6A+ fix|paper revision only"
}
```

## 7. 论文主张处理

### 如果 PASS

可保留：

```text
recoverable inventory 比 raw gap 更有解释力
near-miss based boundary-speed production 有效
RCMV 可以选择有机制收益的动作
action-conditioned reservation 是必要模块
```

仍不能声称：

```text
lane-change production 已验证
rolling horizon 已验证
stochastic robustness 已验证
完整 RPMI-CMV 已复现
```

### 如果 CONDITIONAL PASS

主文降级为：

```text
mechanism-level deterministic evidence
```

把不稳定场景写入 limitation 或 appendix。

### 如果 FAIL

论文必须改为：

```text
当前 V0 apparatus 暂不能支持 proposed mechanism
```

并优先修证据/代码，不进入复杂功能。

## 8. v2.1 A/B/C 判定规则与 claim 边界

## A 类：必须修，否则 D0 不可通过或只能 conditional/fail

| 编号 | 问题 | Gate 判定 |
|---|---|---|
| A1 | 只报告 failed_reservation_rate，不报告 demand denominator | 完整性失败 |
| A1 | failed_reservation_rate=0 但 merge_success_count=0 或 realized_unserved_demand_count>0 | 不得写 merge success improvement |
| A2 | failure_summary 同名覆盖，无法区分 main/readiness/positive_rcmv | 完整性失败 |
| A3 | positive RCMV 只在聊天或临时文件中，没有正式 evidence package | 不得写 RCMV production effectiveness |

## B 类：证据不足，必须降级论文主张

| 编号 | 现象 | claim allowed | claim forbidden |
|---|---|---|---|
| B1 | S5 selected_action_type=none 但 selected_Z_R=0 | inventory reservation success；suppresses unnecessary production | production action creates new slots |
| B2 | S6 selected_Z_R>0 且 merge_success_count=0 | avoids invalid reservation；diagnoses raw-gap illusion | improves merge success / serves demand |
| B3 | hard_brake_count 或 max_wave_amplitude 无优势 | diagnostic safety/wave reporting | reduces hard braking / reduces wave amplitude |

## C 类：当前行为正确，但必须解释清楚

| 编号 | 行为 | 解释 |
|---|---|---|
| C1 | negative RCMV → select a0_none | production is not free；不是算法失败 |
| C2 | readiness_failed 阻断 comparison | readiness 是实验有效性门，不是性能失败 |

## D0 claim allowed / forbidden 最小表

| 证据条件 | 允许写 | 禁止写 |
|---|---|---|
| failed_reservation_rate=0，且 realized_unserved_demand_count>0 | avoids invalid reservations | improves merge success |
| selected_action_type=none，selected_Z_R=0 | exploits existing inventory | production action works |
| selected_RCMV>0，non-none action，selected_Z_R 下降，realized valid | boundary-speed production supports mechanism-level improvement | full RPMI-CMV validated |
| positive RCMV predicted valid 但 realized failed_unsafe_margin | prediction/execution gap exposed by no-fallback trace | reliable production success |
| hard brake/wave 无显著优势 | diagnostic constraints reported | reduces hard braking/waves |
