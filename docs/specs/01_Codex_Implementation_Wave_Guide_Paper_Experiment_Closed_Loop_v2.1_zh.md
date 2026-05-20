# Codex Implementation Wave Guide: Paper--Experiment Closed Loop v2.1 中文版

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

## 0. 本文档定位

本文档是 Codex 的总指挥文档。  
它不替代各阶段 spec，而是规定：

1. Codex 每次如何读取阶段文档；
2. 阶段之间如何衔接；
3. 实验数据如何反哺论文主张；
4. 什么时候继续实现，什么时候停止改论文；
5. Gate D0--D3 如何控制论文声称边界。

## 1. 当前实现基线

当前代码已经完成到：

```text
Wave 6A runner/baseline/analysis
```

已实现机制：

```text
single_t0_micro_episode
deterministic scenario + seed
no-action diagnostic inventory
readiness hard gate
near-miss classification
boundary-speed actions: none/front_acc/rear_dec/front_rear
action-conditioned rollout
regenerate slots/edges/qualities/matching per action
J = Z_bar + lambda_D * D_bar + lambda_C * C_bar
RCMV = baseline_J - action_J
selected evaluation -> reservation
execute selected action + reservation guidance
metrics_episode + batch aggregate
```

未实现机制：

```text
lane-change production
rolling horizon
stochastic IDM V1
action bundle
multi-CAV optimization
fallback repair
SUMO/MOBIL/RL
```

## 2. 总路线

```text
Wave 6A 已实现
↓
Wave 6A.0 Patch
↓
Wave 6A+ Patch
↓
Gate D0
↓
Wave 7
↓
Gate D1
↓
Wave 8
↓
Gate D2
↓
Wave 9
↓
Gate D3
↓
论文实验章定稿
```

## 3. Codex 执行合约

每次执行时，Codex 必须遵守：

```text
只执行本次指定文档。
不得提前实现后续 Wave。
不得把 Gate 当成功能开发阶段。
不得把未通过 Gate 的机制写成论文已验证主张。
不得为了让指标变好而隐藏 failure。
不得添加 fallback repair。
不得让 baseline 使用 proposed 信息。
不得在 readiness_failed 上做 comparison。
不得用 failed_reservation_rate 单独代表 merge success。
不得把“没有生成失败 reservation”写成“demand 已被服务”。
```

每次提交必须包含：

```text
代码改动摘要
新增或修改的文件列表
新增指标/日志 schema
toy test 结果
small batch 结果
failure trace 样例
是否影响论文主张
下一步建议
```

## 4. 阶段依赖

| 当前阶段 | 必须先完成 | 允许做 | 禁止做 |
|---|---|---|---|
| Wave 6A.0 | Wave 6A | 证据包卫生、指标补丁 | lane-change/rolling/stochastic |
| Wave 6A+ | Wave 6A.0 | S2/S5/S6/S7/S8 deterministic evidence | lane-change/rolling/stochastic |
| Gate D0 | Wave 6A+ | evidence decision/report | 新功能 |
| Wave 7 | Gate D0 pass 或 conditional pass | lane-change production | rolling/stochastic |
| Gate D1 | Wave 7 | lane-change claim decision | 新功能 |
| Wave 8 | Gate D1 pass 或 paper decision allows | rolling reservation | stochastic |
| Gate D2 | Wave 8 | rolling claim decision | 新功能 |
| Wave 9 | Gate D2 pass 或 paper decision allows | stochastic IDM V1 | SUMO/MOBIL/RL |
| Gate D3 | Wave 9 | robustness claim decision | 新功能 |

## 5. 论文--实验闭环

每一轮结束后必须回答四个问题：

```text
Q1. 代码现在实际实现了什么？
Q2. 实验数据支持什么论文主张？
Q3. 哪些论文主张必须降级、删除或改为未来工作？
Q4. 下一阶段是补证据、改代码，还是改论文？
```

## 6. 实验证据层级

### Level 0: Toy correctness

目的：证明函数/日志/状态机没有明显错误。

### Level 1: Single scenario trace

目的：证明一个完整 trace 能从 vehicle -> edge -> action -> reservation -> event 回溯。

### Level 2: Deterministic batch evidence

目的：证明 S2/S5/S6/S7/S8 机制可复现、可比较、可解释。

### Level 3: Gate decision

目的：判断是否保留论文主张。

### Level 4: Paper-ready figures/tables

目的：只从通过 Gate 的 evidence package 生成论文实验章。

## 7. 统一指标词典

必须稳定输出：

```text
scenario_id
seed
algorithm_id
state_hash
readiness_pass
readiness_fail_reason
baseline_J
selected_J
selected_RCMV
baseline_S_R
baseline_Z_R
selected_S_R
selected_Z_R
candidate_action_count
positive_RCMV_candidate_count
selected_action_type
reservation_count
planned_reservation_count
failed_reservation_count
stale_reservation_count
mean_RD_matched
production_cost_sum
mean_Z_R
throughput_outflow
hard_brake_count
max_wave_amplitude
no_fallback_invalid_event_count
```

Wave 6A.0 后还必须补：

```text
unique_run_id
batch_id
config_hash
code_version
metrics_schema_version
readiness_schema_version
evidence_package_version
unserved_demand_count
rcmv_positive_margin
rd_decision_changed_flag
action_conditioned_gain
stale_reservation_harm
raw_gap_illusion_flag
failure_join_key
```

## 8. Gate 总览

| Gate | 决策问题 | 可能结果 |
|---|---|---|
| D0 | boundary-speed V0 是否足以支撑论文主机制？ | pass / conditional pass / fail |
| D1 | lane-change production 是否可作为论文主张？ | retain / downgrade / remove |
| D2 | rolling reservation 是否可作为论文主张？ | retain / downgrade / remove |
| D3 | stochastic robustness 是否可作为论文主张？ | retain / downgrade / remove |

## 9. 论文主张边界

### D0 通过后可写

```text
在 deterministic single-t0 micro-episode 中，RPMI-CMV 的 near-miss screening、RCMV action selection 与 action-conditioned reservation 能改善 recoverable supply/deficit，并暴露 raw-gap/density/speed baseline 的局限。
```

### D1 通过后可新增

```text
完整 action set 中，lane-change production 可以扩展 boundary-speed 无法覆盖的 near-miss opportunity。
```

### D2 通过后可新增

```text
rolling horizon reservation 在多周期决策中保持 reservation consistency，并降低 stale/expired/failure 风险。
```

### D3 通过后可新增

```text
在 HDV heterogeneity 与 bounded stochastic IDM 扰动下，RPMI-CMV 的 recoverability-based decision 具有鲁棒性。
```

## 10. Do-not-proceed 总规则

任何阶段如果出现以下情况，不进入下一阶段：

```text
结果无法复现
state_hash fairness 不通过
baseline/proposed 初始状态不一致
failure trace 无法 join 到 action/edge/reservation
RCMV 符号或排名不可解释
readiness 筛选依赖 proposed outcome
ablation flag 没有实际影响
论文主张超过代码能力
```

## 11. 给 Codex 的最短执行命令模板

```text
请读取 docs/specs/00_ACTIVE_SPECS_README_v2_zh.md、
docs/specs/01_Codex_Implementation_Wave_Guide_Paper_Experiment_Closed_Loop_v2_zh.md、
以及 docs/specs/<本次阶段文档>.md。

本次只执行 <本次阶段文档>。
禁止实现后续 Wave。
完成后输出代码改动、测试、evidence package、失败回查和论文主张影响。
```

这不是额外 spec，而是让 Codex 不跑偏的一行保险。

## 12. v2.1 Codex 输出硬要求

Codex 每次完成 Wave 6A.0 及之后阶段时，输出报告必须显式回答：

```text
failed_reservation_rate 的 denominator 是什么？
merge_success_rate_over_demand 是多少？
predicted_unserved_demand_count/rate 是多少？
realized_unserved_demand_count/rate 是多少？
是否存在 failed_reservation_rate=0 但 merge_success_count=0 或 realized_unserved_demand_count>0？
positive RCMV case 是否进入正式 evidence package？
failure_summary 是否按 main/readiness/positive_rcmv 分文件保留？
```

若上述任一项缺失，不得说 evidence package paper-ready。
