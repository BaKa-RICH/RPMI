# RPMI-CMV Active Specs README v2.1 中文版

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

## 0. 本目录用途

本目录是 `rpmi_v0/docs/specs/` 的**唯一活跃 specs 集合**。

旧的 `Phase_0` 到 `Phase_7`、旧 README、旧 Patch、旧 Audit 不再作为活跃实现依据。  
如果仓库中仍然需要备份旧文档，应放在仓库外或非 Codex 默认读取路径中；不要与本目录并列，以免污染实现上下文。

## 1. 当前代码基线

当前基线被定义为：

```text
Wave 6A runner/baseline/analysis 已实现
```

当前实现能力边界：

```text
deterministic Python V0
single_t0_micro_episode
boundary-speed production
near-miss candidate action generation
action-conditioned rollout
RCMV action selection
record-only/action-conditioned reservation
baseline + ablation + batch aggregation
```

当前不能直接声称：

```text
完整 RPMI-CMV action set
lane-change production 已验证
rolling-horizon reservation 已验证
stochastic IDM robustness 已验证
SUMO/MOBIL/RL/large-scale traffic simulator
```

## 2. 替换规则

将 `rpmi_v0/docs/specs/` 替换为本目录内容：

```text
rpmi_v0/docs/specs/
  00_ACTIVE_SPECS_README_v2.1_zh.md
  01_Codex_Implementation_Wave_Guide_Paper_Experiment_Closed_Loop_v2.1_zh.md
  02_Patch_Wave_6A0_Evidence_Package_Hygiene_and_Metric_Patch_v2.1_zh.md
  03_Patch_Wave_6Aplus_Deterministic_Evidence_Hardening_v2.1_zh.md
  04_Gate_D0_Boundary_Speed_V0_Main_Mechanism_Decision_v2.1_zh.md
  05_Wave_7_Lane_Change_Production_and_S5_Evidence_Spec_v2.1_zh.md
  06_Gate_D1_Lane_Change_Production_Claim_Decision_v2.1_zh.md
  07_Wave_8_Rolling_Horizon_Reservation_and_D2_Evidence_Spec_v2.1_zh.md
  08_Gate_D2_Rolling_Reservation_Claim_Decision_v2.1_zh.md
  09_Wave_9_Stochastic_IDM_V1_and_D3_Robustness_Spec_v2.1_zh.md
  10_Gate_D3_Stochastic_Robustness_Claim_Decision_v2.1_zh.md
  11_Human_Readable_Paper_Experiment_Closed_Loop_Roadmap_v2.1_zh.md
  12_Paper_Claim_Evidence_Decision_Matrix_v2.1_zh.md
```

不要同时保留旧 Phase specs 作为活跃文件。

## 3. Codex 使用原则

Codex 每次只执行一个阶段或一个 Gate。

推荐调用方式：

```text
请读取 docs/specs/00_ACTIVE_SPECS_README_v2.1_zh.md、
docs/specs/01_Codex_Implementation_Wave_Guide_Paper_Experiment_Closed_Loop_v2.1_zh.md、
以及本次目标阶段文档。
本次只执行该阶段文档，禁止实现后续 Wave。
```

如果阶段文档是：

```text
02_Patch_Wave_6A0...
```

则 Codex 不得实现 Wave 6A+、Wave 7、Wave 8、Wave 9。

如果阶段文档是 Gate 文档，则 Codex 只做 evidence package 检查、报告和论文主张建议，不做新功能。

## 4. 总路线

```text
Wave 6A 已实现
↓
Wave 6A.0 Patch：证据包卫生与指标补丁
↓
Wave 6A+ Patch：确定性证据强化，覆盖 S2/S5/S6/S7/S8
↓
Gate D0：判断 boundary-speed V0 是否足以支撑论文主机制
↓
Wave 7：实现 lane-change production，并做 S5 完整动作集证据
↓
Gate D1：决定论文是否保留 lane-change production 主张
↓
Wave 8：实现 rolling horizon reservation，并做多周期证据
↓
Gate D2：决定论文是否保留 rolling reservation 主张
↓
Wave 9：实现 stochastic IDM V1，并做鲁棒性证据
↓
Gate D3：决定论文是否保留 stochastic robustness 主张
↓
论文实验章定稿：只写 evidence package 支持的主张
```

## 5. 论文写作硬约束

论文只能写已经被 evidence package 支持的主张。

如果某一 Gate 未通过，对应论文主张只能写成：

```text
limitation
future work
not evaluated in this version
```

而不能写成已验证贡献。

## 6. 文件责任划分

| 文件 | 用途 |
|---|---|
| 00 README | 定义 active specs 目录替换规则 |
| 01 总指挥 | 定义全局路线、上下文和 Codex 执行纪律 |
| 02 Wave 6A.0 | 修补证据包卫生与指标可信度 |
| 03 Wave 6A+ | 加强 deterministic scenario evidence |
| 04 Gate D0 | 决定 boundary-speed V0 主机制是否可写进论文 |
| 05 Wave 7 | 实现 lane-change production |
| 06 Gate D1 | 决定是否保留 lane-change 主张 |
| 07 Wave 8 | 实现 rolling horizon reservation |
| 08 Gate D2 | 决定是否保留 rolling 主张 |
| 09 Wave 9 | 实现 stochastic IDM V1 |
| 10 Gate D3 | 决定是否保留 stochastic robustness 主张 |
| 11 人类路线图 | 给研究者判断阶段合理性 |
| 12 主张矩阵 | 将论文 claims 与 evidence/gates 绑定 |

## 7. 最重要的一句话

不要再按旧 Phase 0--7 思考。  
从现在开始，唯一主线是：

```text
当前代码能力
→ 当前 evidence package
→ 当前论文可声明内容
→ 下一 Wave 是否值得做
```

## 8. v2.1 全局证据包口径

所有活跃 specs 从 v2.1 起必须继承以下约束：

```text
1. evidence package 不得只报告 failed_reservation_rate。
2. failed_reservation_rate 的 denominator 是 generated reservations，不是 ramp demand。
3. 所有核心结果必须同时报告 reservation denominator 与 demand denominator。
4. readiness_failed、completed、positive_rcmv_micro 的 failure summary 不得互相覆盖。
5. positive RCMV 微实验必须进入正式 evidence package，不能只保留在聊天或临时说明中。
```

推荐统一目录：

```text
evidence_package/
  main_batch/
  readiness_fail/
  positive_rcmv_micro/
  gate_D0_input/
```

如果 06--10 尚未更新到 v2.1，也必须至少继承本 denominator 口径；不得在后续 Gate 中重新引入单一 failed reservation rate 解释。
