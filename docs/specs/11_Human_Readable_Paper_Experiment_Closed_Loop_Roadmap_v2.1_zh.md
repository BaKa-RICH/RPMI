# Human-Readable Paper--Experiment Closed Loop Roadmap v2.1 中文版

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

## 0. 给研究者的总判断

你现在不是在堆功能，而是在做论文闭环：

```text
代码实现
→ 产生证据
→ 证据检验理论
→ 理论反过来修改代码和论文
```

不要问“功能是不是都做完了”。  
要问：

```text
当前 evidence package 支持哪些论文主张？
哪些主张必须降级？
下一步是补证据、修代码，还是改论文？
```

## 1. 为什么不再保留旧 Phase specs

旧 Phase 5/6/7 的思想仍有价值，但编号和当前路线不一致：

```text
旧 Phase 5A ≈ 当前 boundary-speed V0 已实现部分
旧 Phase 5B ≈ 新 Wave 7
旧 Phase 6B ≈ 新 Wave 8
旧 Phase 7 ≈ 新 Wave 9
```

如果把旧 Phase 和新 Wave 并列给 Codex，它会混用概念。  
所以 active specs 只能保留新路线。

## 2. 当前最重要的事

现在最重要的不是 Wave 7，而是：

```text
Wave 6A.0
→ Wave 6A+
→ Gate D0
```

原因：

```text
D0 决定 boundary-speed V0 的主机制是否站得住。
```

如果 D0 不清楚，直接做 lane-change 会让失败来源更难判断。

## 3. 每阶段人类要看什么

本节里的“保留 / 降级 / future work”都只表示当前 evidence version 的论文写法边界，不等于删除 `docs/paper/第3.1版论文稿.md` 中的完整研究目标。

### Wave 6A.0

你要看：

```text
文件有没有覆盖？
failure_summary_main_batch / readiness_fail / positive_rcmv 是否被分开保存？
failed reservation rate 和 demand service rate 是否同时报告？
state_hash fairness 是否通过？
failure 是否能 join action/edge/reservation？
RCMV trace 是否完整？
stale/RD/raw-gap-illusion 指标是否落表？
```

判断：

```text
这是证据可信度阶段，不看胜率，看证据能不能被信任。
```

### Wave 6A+

你要看：

```text
S2 是否证明 raw-gap illusion？
S5 是否证明 boundary-speed production？
S6 是否证明 RD？
S7 是否证明 action-conditioned reservation？
S8 是否证明 near-miss screening？
```

判断：

```text
这是机制说服力阶段，看每个场景是否对应一个论文机制点。
```

### Gate D0

你要决定：

```text
boundary-speed deterministic V0 是否足以作为会议论文主实验？
```

如果 D0 pass：

```text
可以写 mechanism-level V0 paper。
```

如果 D0 conditional：

```text
可以写更谨慎版本，或先修 fixlist。
```

如果 D0 fail：

```text
不要做 Wave 7，先修 V0 或改论文主张。
```

### Wave 7 / Gate D1

你要看：

```text
lane-change 是否真的带来 boundary-speed 不能带来的收益？
```

如果没有：

```text
不要把 lane-change 写成当前已验证主张；可写成 framework proposal、pending validation 或 limitation。
```

### Wave 8 / Gate D2

你要看：

```text
rolling 是否解决 stale/expiration/multi-period consistency？
```

如果只是复杂但无收益：

```text
在当前 evidence version 写成 pending validation / future work。
```

### Wave 9 / Gate D3

你要看：

```text
stochastic 是否证明鲁棒性，而不是掩盖 deterministic 问题？
```

如果 deterministic V0 不稳：

```text
不要进入 stochastic。
```

## 4. 最现实的发文策略

### 安全版本

```text
主文：deterministic boundary-speed RPMI-CMV mechanism validation
限制：no lane-change, no rolling, no stochastic full validation
未来工作：lane-change/rolling/stochastic
```

优点：

```text
可控、诚实、容易解释。
```

### 强版本

```text
D0 + D1 + D2 + D3 全过
```

才写完整 RPMI-CMV。

风险：

```text
周期长，功能复杂，失败来源更多。
```

## 5. 人类判断红线

出现以下情况不要继续加功能：

```text
RCMV 经常选错且解释不了
failure trace join 不上
readiness 依赖 proposed outcome
baseline 初始状态不公平
ablation flag 没有真实影响
论文主张超过实现能力
```

## 6. 你现在应该怎么做

1. 替换 `docs/specs/` 为 active specs v2。
2. 让 Codex 只执行 Wave 6A.0。
3. 看 evidence hygiene 是否过关。
4. 再执行 Wave 6A+。
5. 跑 Gate D0。
6. 根据 D0 决定是否做 Wave 7。

## 7. 一句话

你现在乱，是因为旧 Phase、当前代码、论文理想系统、未来扩展混在一起。  
从今天开始只看：

```text
当前 Wave
当前 evidence
当前 Gate
当前论文可写主张
```

## 8. v2.1 人类如何读 failed reservation 与 unserved demand

你以后看实验结果时，先不要问：

```text
failed_reservation_rate 是不是 0？
```

而要同时问：

```text
D_H 是多少？
reservation_count 是多少？
failed_reservation_count 是多少？
merge_success_count 是多少？
realized_unserved_demand_count 是多少？
```

四种常见解释：

| 现象 | 正确解释 | 不能写成 |
|---|---|---|
| failed_reservation_rate=0，merge_success_count=D_H | reservation 没失败且 demand 被服务 | 无问题 |
| failed_reservation_rate=0，merge_success_count=0，realized_unserved_demand_count>0 | 没有做坏 reservation，但 demand 没服务 | merge success 高 |
| failed_reservation_rate>0，merge_success_count>0 | 部分服务，部分 reservation/execution 失败 | proposed 完全失败或完全成功 |
| selected_action_type=none，selected_Z_R=0 | 利用已有 inventory，不是不必要生产 | production action 有效 |

人类 Gate 判断时必须把这两句话分开：

```text
No bad reservation was generated.
Demand was successfully served.
```

前者看 reservation denominator，后者看 demand denominator。
