# Paper Claim--Evidence Decision Matrix v2.1 中文版

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

## 0. 用途

本文档把论文主张、代码能力、实验证据和 Gate 决策绑定起来。  
论文实验章只能写本矩阵中状态为 `supported` 或 `qualified_supported` 的主张。

## 1. 主张状态

```text
supported：证据充分，可写为主结论
qualified_supported：有限条件下支持，必须写清边界
inconclusive：证据不清，不写主结论
contradicted：证据反驳，必须删改
future_work：未实现或未验证，只能写未来工作
```

## 2. 主张矩阵

| Claim ID | 论文主张 | 所需证据 | Gate | 通过后写法 | 未通过写法 |
|---|---|---|---|---|---|
| C0 | raw gap count 不等于 ramp-specific recoverable inventory | S2/S6 raw-gap illusion + P_R/RD/matching trace | D0 | raw gap is insufficient | limitation/example only |
| C1 | time-expanded edge inventory 可解释 merge difficulty | S0/S2/S6 predictor/outcome 或 diagnostic summary | D0 | inventory-based metrics explain difficulty | preliminary diagnostic |
| C2 | near-miss screening 能定位可生产机会 | S5/S8 near_miss + candidate/action trace | D0 | near-miss screening identifies actionable opportunities | future refinement |
| C3 | boundary-speed production 可改善 slot availability | S5/S6_productive positive non-none RCMV + delta_S/delta_Z + demand denominator | D0 | boundary-speed V0 supports production mechanism | not supported / inventory-only |
| C3a | RPMI-CMV 可利用已有 recoverable inventory 且抑制不必要动作 | selected_action_type=none + selected_Z_R下降/为0 + negative action RCMV | D0 | inventory reservation and no-unnecessary-action behavior supported | not supported |
| C4 | RCMV 能选择合理 action | RCMV trace top actions + selected J decrease + positive_rcmv_micro package | D0 | RCMV selects beneficial actions under audited conditions | objective/execution gap needs revision |
| C5 | RD/recoverability 有独立贡献 | without_rd ablation difference | D0 | RD improves action/reservation quality | RD proxy limitation |
| C6 | action-conditioned reservation 必要 | stale ablation harm | D0 | action-conditioned reservation avoids stale plans | future work/weak evidence |
| C7 | lane-change production 是有效 action mode | full vs boundary/lane_change evidence | D1 | LC expands action space | future work |
| C8 | rolling horizon reservation 改善多周期一致性 | rolling vs single evidence | D2 | rolling improves consistency | future work |
| C9 | stochastic IDM 下鲁棒 | P_R_hat/noise/p_min sensitivity | D3 | robust under bounded stochasticity | future work |
| C10 | 完整 RPMI-CMV 已复现 | D0+D1+D2+D3 全部 retain/pass | D3 | full mechanism implemented and validated | 不得声称 |

## 3. 写作规则

### D0 pass 但 D1/D2/D3 未做

论文标题和摘要应避免：

```text
full RPMI-CMV
complete action set
rolling reservation
stochastic robustness
```

推荐写：

```text
a deterministic boundary-speed V0 mechanism validation of RPMI-CMV
```

### D1 未通过

不要写：

```text
lane-change production is validated
```

可写：

```text
lane-change production is an extension left for future work
```

### D2 未通过

不要写：

```text
rolling reservation is validated
```

可写：

```text
the present experiments use single-t0 micro-episodes
```

### D3 未通过

不要写：

```text
robust under stochastic human driving
```

可写：

```text
stochastic robustness will be evaluated in V1
```

## 4. 证据不足时怎么处理

如果实验结果不好，不要直接调参追胜率。先判断：

| 现象 | 优先处理 |
|---|---|
| readiness 大量失败 | 改 scenario generator/readiness target |
| RCMV 全选 none | 查 near-miss、cost、theta、delta_W |
| RCMV 选错 | 查 J normalization、RD double counting、cost sign |
| raw-gap baseline 太强 | 查 S2 illusion 是否构造不足 |
| without_rd 与 full 一样 | 查 RD 是否真正参与 decision |
| stale ablation 与 full 一样 | 查 reservation 是否真的 action-conditioned |
| failure 无法解释 | 先修 logs，不写论文结论 |

## 5. 论文实验章生成顺序

```text
1. 只读取通过 Gate 的 evidence package
2. 先写 supported claims
3. 再写 qualified_supported claims
4. inconclusive 写 limitation
5. future_work 写未来工作
6. contradicted 必须删除或反向讨论
```

## 6. 最终定稿检查

提交论文前逐条确认：

```text
每个主张是否有对应 Gate？
每张表是否来自 evidence package？
每个 ablation 是否真的改变代码路径？
每个 failure 是否没有被隐藏？
是否诚实说明 deterministic/single-t0/boundary-speed 限制？
```

## 7. v2.1 指标误读风险表

| 风险 | 误读写法 | 正确写法 | 必须检查 |
|---|---|---|---|
| failed reservation denominator | failed_reservation_rate=0，所以合流成功 | 没有生成失败 reservation，但 demand 是否服务要看 demand denominator | merge_success_rate_over_demand, realized_unserved_demand_rate |
| S5 no-action success | selected_Z_R=0，所以 production 有效 | 若 selected_action_type=none，只能说明已有 inventory 可用 | selected_action_type, selected_RCMV |
| S6 raw-gap illusion | RPMI 没失败，所以提升成功率 | RPMI 避免 invalid reservation，但可能留下 unserved demand | selected_Z_R, merge_success_count |
| positive RCMV 聊天案例 | 口头案例可支撑论文主张 | 必须进入正式 evidence package | positive_rcmv_* 文件 |
| hard brake/wave | 诊断指标存在即可写降低 | 只有相对 baseline 有优势才可写降低 | hard_brake_count, max_wave_amplitude |

## 8. v2.1 论文禁止表述

除非 evidence package 明确支持，否则论文不得写：

```text
RPMI-CMV significantly improves merge success.
RPMI-CMV reduces hard braking and speed-wave amplitude.
Boundary-speed production creates new slots in S5.
RCMV reliably selects safe production actions.
failed_reservation_rate=0 demonstrates success.
The full RPMI-CMV mechanism is validated.
```

允许的保守写法：

```text
RPMI-CMV avoids invalid reservations in raw-gap illusion states, but may leave demand unserved when no recoverable slot exists.
The RCMV selector suppresses unnecessary production actions when action-conditioned cost exceeds predicted benefit.
The current deterministic V0 evidence supports mechanism-level inventory, reservation, and action-selection diagnostics under audited conditions.
Safety and wave metrics are reported diagnostically; current V0 evidence does not establish a clear advantage unless shown by Gate tables.
```
