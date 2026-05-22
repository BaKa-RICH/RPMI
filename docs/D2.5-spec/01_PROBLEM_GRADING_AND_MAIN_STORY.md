# 01 问题分级与论文主故事

## 1. 当前总判断

这篇论文现在不应被理解成“失败”或“只能降级”。更准确的判断是：

> 理论主线有价值，但实验、指标、baseline 和 objective 还没有闭合到论文真正想证明的低扰动性能机制。

Gate D2 已经证明的主要是：

```text
rolling lifecycle 可审计；
reservation / demand / slot / failure trace 可追；
conservative physical-gap conflict blocking 存在；
negative control 没有 hidden fallback。
```

Gate D2 没有充分证明的是：

```text
recoverability-aware / cost-aware / action-conditioned selection
是否真的降低 realized recovery debt、hard brake、wave、mainline disturbance。
```

因此 D2.5 的本质不是“补日志”，而是：

> 把理论量、动作选择、预约、实际结果、扰动指标闭合起来。

---

## 2. P0：论文故事闭环没完成

### 问题

当前主链条还没有闭合：

```text
J / RD / C_bar / RCMV
  -> selected action
  -> selected edge / gap
  -> reservation
  -> realized event
  -> realized low-disturbance outcome
```

### 为什么这是最高优先级

论文真正要赢的不是“系统能记录 reservation”，而是：

```text
RPMI-CMV 选择的 recoverable / low-debt / low-disturbance slot
比 raw gap 或 forced accommodation 更好。
```

### Codex 要做

必须生成并验证：

```text
trace_join_schema_plan.md
action_to_outcome_join.csv
disturbance_metrics.csv
recovery_metrics.csv
safety_metrics.csv
baseline_comparison.csv
ablation_comparison.csv
```

### Stop condition

如果 `selected_action_id` 无法 join 到：

```text
selected_edge_id
physical_gap_id / slot_group_id
reservation_id
realized_event_id
demand outcome
disturbance / recovery / safety metric
```

不要写 D2.5 support。先修 trace schema。

---

## 3. P1：目标函数需要重构

### 当前风险

旧目标函数可能存在几个问题：

```text
1. lambda_C 太小，或者 C_bar 只是 action effort proxy。
2. RD 只是 simplified proxy，未必对应 hard brake / wave / realized disturbance。
3. theta 太低，导致很小 RCMV 也触发 action。
4. 没有 churn / switching / commitment penalty。
5. Z_R 项可能压倒 cost，导致为了服务一个 demand 制造高扰动。
```

### 升级式修正

建议目标函数改成：

```text
J(a) =
  lambda_Z * Z_R_norm(a)
+ lambda_D * RD_pred_norm(a)
+ lambda_C * C_dist_norm(a)
+ lambda_S * S_safety_penalty(a)
+ lambda_Q * Q_churn_penalty(a)
```

RCMV 仍然保持：

```text
RCMV(a) = J(a0_none) - J(a)
```

选择规则：

```text
if max_a RCMV(a) > theta:
    select argmax RCMV(a)
else:
    select a0_none
```

### Codex 要做

```text
1. 审计现有 J / RD / C_bar / RCMV 是否参与 selected_action。
2. 将 C_bar 升级为 C_dist，不再只代表 action effort。
3. 将 RD 拆成 predicted_RD 与 realized_RD。
4. 加入 safety penalty 与 churn penalty。
5. 做 lambda_D / lambda_C / lambda_S / lambda_Q / theta 的校准网格。
6. 所有尝试写入 objective_calibration_log.csv，不允许只保留成功参数。
```

---

## 4. P2：场景没有打中理论优势

### 当前问题

泛泛 rolling 场景不能证明论文主故事。D2.5 必须设计“让 baseline 犯论文理论所预言错误”的场景。

### 三个最重要场景

```text
1. Raw-Large-Gap Trap
2. Forced-Accommodation
3. Bad-Action Suppression
```

### 每个场景必须明确

```text
baseline 为什么看起来合理；
baseline 为什么按论文理论会错；
RPMI-CMV 理论上为什么应该赢；
需要哪些 realized metrics 证明赢了；
失败时如何区分理论错、实现错、指标错、场景错。
```

---

## 5. P3：baseline 要围绕故事设计

### 核心 baseline / ablation

```text
raw_largest_gap
fifo_feasible_gap
forced_accommodation
no_action_natural
reservation_before_action / stale_reservation
without_RD
without_Cbar / without_cost
without_theta
without_conflict_blocking
```

### 重点不是数量，而是用途

| baseline | 用途 |
|---|---|
| raw_largest_gap | 证明 raw geometric gap 会被骗 |
| forced_accommodation | 证明强行合流不等于低扰动合流 |
| no_action_natural | 证明自然库存是否已经足够 |
| without_RD | 证明 RD 真的改变选择 |
| without_Cbar | 证明 disturbance cost 真的压制坏动作 |
| without_theta | 证明 threshold 真的避免微小收益触发 action |
| stale_reservation | 证明 action-conditioned / rolling 的必要性 |
| without_conflict_blocking | 证明不靠重复消费 physical gap 虚高成功率 |

---

## 6. P4：conflict-aware 先别抢主线

### 正确定位

conflict-aware 是论文机制完整性的一部分，但不是 D2.5 的主战场。当前可说：

> prototype implements conservative physical-gap conflict blocking.

暂时不要说：

> full conflict-aware rolling integer assignment has been validated.

### Codex 要做

只需要保留 conflict blocking 的 honest denominator 作用：

```text
physical_gap_id / slot_group_id
duplicate_consumption_attempt_count
duplicate_gap_consumption_count
blocked_by_conflict_count
unserved_due_to_conflict_count
```

它作为补充机制，不要抢走 low-disturbance story 的主线。

---

## 7. 当前行动主线

```text
1. 固定论文主故事：
   target deterministic regimes 中，RPMI-CMV 降低 recovery debt 和 mainline disturbance。

2. 重构 objective：
   J = lambda_Z Z_R + lambda_D RD + lambda_C C_dist + lambda_S safety + lambda_Q churn。

3. 重定义 C_bar：
   从 action effort 升级为 disturbance-aware cost。

4. 重定义 RD：
   从抽象 proxy 升级为 predicted recovery burden，并与 realized RD 对照。

5. 做目标函数校准：
   调 lambda_D、lambda_C、lambda_S、lambda_Q、theta，记录所有尝试。

6. 做 ablation：
   full vs without_RD vs without_Cbar vs without_theta。

7. 做决定性场景：
   Raw-Large-Gap Trap + Forced-Accommodation。

8. 用 realized metrics 闭环：
   hard brake、max decel、speed variance、wave amplitude、disturbance cost、min TTC。

9. 论文写法：
   不说 universal optimality；
   说 target-regime deterministic evidence supports low-disturbance recoverable slot selection。
```
