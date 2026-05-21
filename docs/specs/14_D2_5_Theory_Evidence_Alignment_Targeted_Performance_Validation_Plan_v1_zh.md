# D2.5 Theory--Evidence Alignment and Targeted Performance Validation Plan v1 中文版

## 0. 本计划定位

本文档是 Gate D2 之后、Wave 9 之前的中间研究计划。它不是 Wave 9，不执行 stochastic IDM，不推进 Gate D3，也不直接修改论文稿。它的目标是先回到论文核心理论和确定性实验设计，回答一个比鲁棒性更基础的问题：

```text
RPMI-CMV 的核心理论在 deterministic target scenarios 中，是否真的产生可观测、可追踪、可解释的指标优势？
```

Gate D2 的结论是 `downgrade / qualified_supported`，这说明 Wave 8 已经提供了可审计 rolling lifecycle、保守 slot conflict blocking、no-hidden-fallback 等证据，但还不足以支撑 retain 级别的 rolling reservation 强主张。这个结果不意味着论文理论错误，也不意味着应该马上进入 Wave 9。相反，它提示我们：在做 stochastic robustness 之前，应先把 deterministic 靶场中的理论优势做实。

本计划建议新增一个研究阶段：

```text
D2.5: Theory--Evidence Alignment and Targeted Performance Validation
```

也可以简称：

```text
D2.5 论文理论-实验对齐补强
```

本阶段的核心任务不是继续堆 rolling 日志，也不是扩大随机扰动，而是把论文里的理论主张拆成可检验 claim，设计专门命中这些 claim 的 deterministic target scenarios，补齐 disturbance / recovery / wave / safety / demand 指标，并建立从理论公式到 CSV 字段再到实验结果的闭环。

## 1. 为什么不应立刻进入 Wave 9

Wave 9 的定位是 stochastic IDM V1 和 Gate D3 robustness。它回答的问题是：

```text
在 HDV 随机扰动、驾驶异质性、有限噪声和不确定性下，RPMI-CMV 是否仍然稳健？
```

但当前更紧迫的问题是：

```text
在 deterministic、可控、最能表达理论机制的场景里，RPMI-CMV 是否真的比 raw-gap、FIFO、forced-accommodation、stale reservation 等 baseline 更好？
```

如果第二个问题还没有回答清楚，直接进入 Wave 9 会带来三个风险。

第一，结果解释会混乱。若 stochastic 结果不好，我们无法判断问题来自理论本身、场景设计、指标体系、实现路径，还是随机扰动过强。若 stochastic 结果偶然变好，也无法说明 deterministic 机制链条已经成立。

第二，论文叙事会断。审稿人首先会要求看到：在论文定义的 target regime 中，算法为什么应该赢、赢在哪里、以什么指标赢、失败时如何解释。如果 deterministic target evidence 不强，直接谈 robustness 会显得基础证据不足。

第三，随机实验可能掩盖真正问题。随机性会引入方差、偶然成功和偶然失败，使我们更难判断 RCMV、RD、disturbance cost、action-conditioned reservation 是否真的按论文理论发挥作用。

因此，本计划建议：

```text
先做 D2.5，暂缓 Wave 9。
```

只有当 D2.5 证明 deterministic target scenarios 中核心理论优势成立，或者明确指出论文理论/实验设计需要修正后，才决定是否进入 Wave 9。

## 2. D2.5 的研究问题

D2.5 不问“rolling 有没有跑起来”，也不问“stochastic 下是否鲁棒”。它问四个更基础的问题：

```text
Q1. 论文理论中的 recoverability-aware gap selection 是否真的优于 raw geometric gap selection？
Q2. RCMV action selection 是否真的能避免不必要主线扰动？
Q3. high-quality / low-recovery-debt gap 是否真的降低 hard braking、speed wave、mainline disturbance 或 recovery debt？
Q4. action-conditioned reservation、slot conflict blocking、rolling lifecycle 是否能在性能证据中发挥可解释作用，而不只是日志状态机？
```

这四个问题对应论文实验章最需要补强的地方。Wave 8 已经证明了 lifecycle 机制可审计，但还没有充分证明“算法选择更好的 gap/action 后，交通流代价真的更小”。D2.5 就是为这个缺口设计。

## 3. 本阶段不做什么

D2.5 必须守住边界，避免变成另一个无限扩张的实现阶段。

本阶段不做：

```text
1. 不执行 Wave 9。
2. 不实现 stochastic IDM。
3. 不执行 Gate D3。
4. 不引入 SUMO / MOBIL / RL / 大规模交通仿真。
5. 不用随机扰动掩盖 deterministic 机制问题。
6. 不为了追求指标好看而隐藏 failure。
7. 不把 failed_reservation_rate 单独解释为 merge success。
8. 不把 conservative conflict blocking 写成 full conflict-aware rolling integer assignment。
9. 不直接修改论文稿，除非另开 paper revision 阶段。
```

本阶段可以做：

```text
1. 只读审计论文理论 claim 与现有指标字段。
2. 设计 deterministic target scenarios。
3. 增加或补齐 deterministic disturbance / wave / recovery / safety 指标。
4. 增加针对 target scenarios 的 baseline 和 ablation。
5. 重新生成 D2.5 evidence package。
6. 生成 D2.5 human_review 和 D2.5 gate-style decision report。
```

## 4. 核心思想：不是只问“合没合上”，而是问“以什么代价合上”

论文理论的关键不是简单提高 merge success。很多粗糙 baseline 也能通过强迫主线车加速/减速让 ramp 车合上。但这种成功可能伴随更高的主线扰动、更大速度波、更高 recovery debt、更差安全裕度，甚至把代价转嫁给下游 traffic stability。

RPMI-CMV 的理论价值应体现在：

```text
在 demand service 不差的前提下，选择 recoverability 更高、恢复代价更低、主线扰动更小、slot conflict 更少的 gap/action。
```

因此 D2.5 的指标体系必须同时看：

```text
demand service
reservation validity
mainline disturbance
recovery debt
speed wave
safety margin
action cost
failure trace
```

如果一个 baseline 的 merge success 和 RPMI-CMV 相同，但 hard_brake_count、max_deceleration、speed_variance_delta、mainline_disturbance_cost 明显更高，那么这恰恰支持论文理论：RPMI-CMV 不是为了服务 demand 而不计代价地扰动主线，而是在可恢复库存和低扰动动作之间做有约束选择。

## 5. 理论 claim 拆解

D2.5 的第一步是把论文理论拆成可检验 claim。建议至少形成以下 claim matrix。

| Claim ID | Claim | 通俗解释 | 必须验证的内容 |
|---|---|---|---|
| C-A | recoverability-aware gap selection 优于 raw geometric gap selection | 不是最大 gap 最好，而是最适合 ramp 车、恢复债最低、时机最合适的 gap 最好 | RPMI-CMV 选择的 gap 在 RD、validity、disturbance 或 safety 上优于 raw-gap baseline |
| C-B | action-conditioned reservation 优于 reservation-before-action / stale reservation | 先选 action 后重新算 reservation，比拿旧 reservation 硬套新状态更可靠 | selected action 后 matching / edge quality / reservation 发生合理变化，stale baseline 失败或代价更高 |
| C-C | RCMV action selection 能避免不必要主线扰动 | 有些 action 虽然能制造 gap，但代价太大，不该执行 | RPMI-CMV 在 bad-action case 中选择 none 或低扰动 action，naive action baseline 指标更差 |
| C-D | high-quality gap selection 会降低 recovery debt 和 wave/hard-brake | 好 gap 不只让 ramp 合上，还应让主线恢复更平稳 | 在 merge success 相近时，RPMI-CMV 的 RD、hard brake、wave、disturbance 更低 |
| C-E | conflict-aware slot consumption 避免重复使用同一 physical gap | time-expanded copies 不能被当成独立物理资源无限使用 | naive matching 出现 duplicate risk，RPMI-CMV 阻断并保留 unserved demand |
| C-F | rolling lifecycle 能处理 expiration / stale / demand return | 旧计划失效后 demand 不消失，能回流或被诚实标记 unserved | demand lifecycle 和 reservation lifecycle 能追到 cancel/expire/reassign/unserved |
| C-G | no-hidden-fallback 是机制可信度前提 | 算法不能靠隐形安全控制器修复失败 | unsafe/invalid/failure 必须显式记录，不能把失败改写成成功 |

D2.5 的优先级应放在 C-A、C-C、C-D。因为它们最直接支撑论文的核心理论：RPMI-CMV 的价值不是“能不能强行合流”，而是“能不能以更低扰动和更高 recoverability 完成或拒绝合流”。

## 6. Theory-to-Metric Consistency Audit

在写新代码或跑新 batch 前，必须先做只读审计。审计目标是确认论文公式、实现字段、CSV 指标、实验表格之间没有断裂。

### 6.1 必须审计的理论对象

论文中至少需要审计这些对象：

```text
Z_R / Z_bar
RD / D_bar
C_bar
J(a)
RCMV(a)
P_R
near-miss producible edge
action-conditioned rollout
reservation matching
slot consumption conflict
```

### 6.2 必须回答的问题

审计必须逐项回答：

```text
1. 论文中的 J = Z_bar + lambda_D * D_bar + lambda_C * C_bar 对应代码里的哪些字段？
2. selected_J、baseline_J、selected_RCMV 是否来自同一套 normalized components？
3. RD 是否真的参与 action ranking，而不只是事后记录？
4. C_bar 是否真的惩罚主线扰动，而不只是一个展示字段？
5. positive RCMV 是否对应最终 realized outcome 改善？
6. selected_action_type=none 时，是否能解释为 action cost 大于收益？
7. selected action 后，slots、edges、qualities、matching 是否真的 recompute？
8. hard_brake_count / max_wave_amplitude / disturbance metrics 是否与 C_bar 或 RD 同向？
9. baseline 是否使用了 proposed 才知道的信息？
10. 是否存在指标字段命名正确但没有进入实际决策的情况？
```

### 6.3 审计输出

建议新增：

```text
outputs/d2_5_theory_alignment/theory_metric_audit.md
```

内容包括：

```text
claim_id
paper_formula_or_claim
implementation_function_or_field
CSV_field
does_it_affect_selection
does_it_affect_reported_metric
known_gap
required_fix_or_experiment
```

如果审计发现某个理论量没有参与 action selection，则不能用它支撑论文主张。它最多只能写成 diagnostic metric。

## 7. Target Scenario Suite

D2.5 的第二步是设计 deterministic target scenarios。它们不是普通随机场景，而是为了打中特定理论 claim 的靶场。每个 scenario 都必须有明确的“理论预期”和“失败解释路径”。

### 7.1 S-D25-A: Raw-Large-Gap Trap

构造：

```text
几何上存在一个较大的 mainline gap。
raw-gap baseline 会倾向选择这个大 gap。
但 ramp vehicle 的到达时机、速度或加速度约束使这个 gap 的 recoverability 差。
另一个 gap 几何尺寸较小，但 ramp-specific timing 更好、RD 更低、主线扰动更小。
```

预期：

```text
raw-gap baseline 选择几何大 gap，但 P_R 较低或 RD / disturbance 较高。
RPMI-CMV 选择 recoverability 更好的 gap。
merge success 不低于 raw-gap baseline。
RD、mainline_disturbance_cost、hard_brake_count 或 max_wave_amplitude 更低。
```

必须输出：

```text
selected_gap_raw
selected_gap_rpmi
gap_size_raw
gap_size_rpmi
P_R_raw / P_R_rpmi
RD_raw / RD_rpmi
mainline_disturbance_cost_raw / rpmi
merge_success_rate_over_demand
realized_unserved_demand_rate
failure trace if failed
```

通过标准：

```text
RPMI-CMV 在 demand service 不差的前提下，至少一个核心代价指标明显更低。
```

### 7.2 S-D25-B: Forced-Accommodation Baseline

构造：

```text
baseline 为了服务 ramp demand，强行让 front CAV 加速或 rear CAV 减速。
该动作可以制造一个可用 gap，但会带来明显主线扰动。
RPMI-CMV 有机会选择更低扰动 gap/action，或拒绝代价过高的 action。
```

预期：

```text
forced baseline 的 merge success 可能不差。
但 hard_brake_count、max_deceleration、speed_variance_delta、wave amplitude 或 action cost 更高。
RPMI-CMV 的 service 相近或更好，同时主线扰动更低。
```

必须输出：

```text
forced_action_type
rpmi_selected_action_type
forced_action_cost
rpmi_action_cost
max_deceleration
hard_brake_count
max_wave_amplitude
speed_variance_delta
merge_success_rate_over_demand
```

通过标准：

```text
在 merge success 相同或可解释差异不大的情况下，RPMI-CMV 的 disturbance / wave / hard-brake 指标优于 forced baseline。
```

### 7.3 S-D25-C: Near-Miss Production Case

构造：

```text
当前没有自然 valid slot。
存在一个 near-miss edge，经过小幅 front_acc、rear_dec 或 front_rear 微调后可以变成 recoverable slot。
naive production 可以使用更大动作制造 gap，但代价更高。
```

预期：

```text
no-action baseline 留下 unserved demand。
naive production 可以服务 demand 但扰动更高。
RPMI-CMV 选择低扰动 positive RCMV action，降低 Z_R 或 RD，并服务 demand。
```

必须输出：

```text
near_miss_edge_id
baseline_validity
action_conditioned_validity
baseline_Z_R
selected_Z_R
baseline_RD
selected_RD
selected_RCMV
selected_action_type
production_cost_sum
merge_success_rate_over_demand
```

通过标准：

```text
RPMI-CMV 通过小动作将 near-miss edge 转化为可用 reservation，并且 C_bar / disturbance 没有过高。
```

### 7.4 S-D25-D: Bad-Action Suppression Case

构造：

```text
存在一个 technically feasible action。
该 action 可以稍微改善 reservation 指标，但主线扰动成本很高。
当前 natural inventory 或等待策略已经足够，或者 action 净收益低于 theta。
```

预期：

```text
RPMI-CMV 选择 none。
naive action baseline 执行动作后 hard brake / wave / cost 变差。
RPMI-CMV 证明自己不会为了微小 Z_R 改善而不必要扰动主线。
```

必须输出：

```text
best_positive_action_before_cost
selected_action_type
selected_RCMV
theta
baseline_J
selected_J
lambda_C * C_bar contribution
hard_brake_count
max_wave_amplitude
mainline_disturbance_cost
```

通过标准：

```text
RPMI-CMV 的 no-action 选择能由 J / RCMV / cost 分解解释，并且 naive action 的扰动更差。
```

### 7.5 S-D25-E: Multi-Demand Physical-Gap Conflict

构造：

```text
多个 ramp vehicles 在 time-expanded matching 中都看似可以使用同一 physical gap 的不同时间 copy。
naive matching 不考虑 physical gap consumption conflict。
RPMI-CMV 或 conservative conflict blocking 阻断重复使用。
```

预期：

```text
naive matching 的 apparent served demand 更高。
但它依赖重复消费同一 physical gap 或造成 unsafe overlap。
RPMI-CMV 保守服务较少 demand，但 duplicate_gap_consumption_count=0，failure trace 可解释。
```

必须输出：

```text
physical_gap_id
slot_group_id
naive_assigned_demand_count
rpmi_assigned_demand_count
slot_consumption_conflict_detected_count
duplicate_gap_consumption_count
realized_unserved_demand_rate
failure_reason
```

通过标准：

```text
RPMI-CMV 不用虚假的重复消费换取表面 merge success。
```

### 7.6 S-D25-F: Rolling Stale Benefit With Performance Metric

构造：

```text
旧 reservation 在后续 context 中变 stale。
stale baseline 继续使用旧计划。
rolling 检测到 stale 后 cancel / expire / reassign。
```

预期：

```text
rolling 不只是日志更干净，还应在 realized invalidity、waiting、RD、unserved 或 disturbance 上体现优势。
```

通过标准：

```text
rolling 在至少一个 demand-level 或 disturbance-level 指标上优于 stale baseline，且 failure trace 能说明 stale 为什么失败。
```

## 8. 指标体系补强

D2.5 必须把指标从 reservation/demand lifecycle 扩展到 performance mechanism。

### 8.1 必须保留的 denominator 指标

所有场景必须继续报告：

```text
D_H
generated_reservation_count
failed_reservation_count
failed_reservation_rate
failed_reservation_denominator
merge_success_count
merge_success_rate_over_demand
predicted_unserved_demand_count
predicted_unserved_demand_rate
realized_unserved_demand_count
realized_unserved_demand_rate
```

解释红线仍然有效：

```text
failed_reservation_rate=0 不等于 demand served。
没有 reservation failure 不等于 merge success。
negative control 中 unserved demand 是诚实证据，不是性能成功。
```

### 8.2 必须新增或强化的 disturbance 指标

建议新增：

```text
hard_brake_count
max_deceleration
mean_abs_acceleration
acceleration_variance
max_wave_amplitude
speed_variance_before
speed_variance_after
speed_variance_delta
mainline_disturbance_cost
mainline_disturbance_cost_normalized
action_cost_sum
action_cost_per_served_demand
```

解释要求：

```text
如果 RPMI-CMV 和 baseline 的 merge success 相同，优先比较 disturbance / hard-brake / wave。
如果 RPMI-CMV 的 merge success 较低，但避免 unsafe event 或 duplicate consumption，也必须诚实解释 trade-off。
```

### 8.3 必须新增或强化的 recovery 指标

建议新增：

```text
mean_RD_candidate
mean_RD_selected
mean_RD_realized
RD_before_action
RD_after_action
RD_delta
max_RD
RD_per_served_demand
recovery_time_estimate
```

这些指标要回答：

```text
算法选中的 gap/action 是否真的降低 recovery debt？
如果 RD 下降但 merge 没成功，是 prediction 问题还是 action/reservation 问题？
如果 merge 成功但 RD 高，是否说明算法用了高代价成功？
```

### 8.4 必须新增或强化的 safety 指标

建议新增：

```text
min_realized_gap
min_predicted_gap
min_TTC
min_surrogate_safety_margin
physical_validity_failed_count
realized_invalid_event_count
unsafe_overlap_count
no_fallback_invalid_event_count
```

这类指标是为了防止 baseline 通过 unsafe 或接近 unsafe 的动作获得表面成功。

### 8.5 必须新增或强化的 selection explanation 指标

建议新增：

```text
candidate_action_count
positive_RCMV_candidate_count
selected_action_rank
selected_action_type
selected_action_id
selected_edge_id
selected_physical_gap_id
selected_P_R
selected_RD
selected_C_bar
selected_Z_bar
baseline_J
selected_J
selected_RCMV
RCMV_margin_to_second_best
theta
lambda_D
lambda_C
```

这些字段要让人能解释：

```text
为什么选这个 action？
为什么不选 raw largest gap？
为什么不执行 forced action？
为什么 selected_action_type=none 是合理的？
```

## 9. Baseline 与 Ablation 设计

D2.5 不需要大量 baseline，但每个 baseline 必须对应一个理论问题。

| Baseline | 用途 | 必须防止的误读 |
|---|---|---|
| `raw_largest_gap` | 检验 raw geometric gap 是否误导 | 不允许使用 RPMI-CMV 的 future outcome |
| `fifo_feasible_gap` | 检验简单先到先服务 | 不允许隐式选择 recoverability 最优 gap |
| `forced_accommodation` | 检验强行主线配合的扰动代价 | 成功率高不代表更好，必须看 disturbance |
| `no_action_natural` | 检验自然库存是否足够 | selected none 不是失败，可能是避免不必要动作 |
| `reservation_before_action` | 检验 stale/action-conditioned 差异 | 必须使用同一初始状态和 demand |
| `without_RD` | 检验 RD 是否真正有贡献 | 如果结果一样，要查 RD 是否进入 selection |
| `without_Cost` | 检验 action cost 是否抑制高扰动动作 | 如果 cost 去掉后动作更激进，说明 cost 有作用 |
| `without_conflict_blocking` | 检验 physical gap conflict | 不允许把重复消费解释成真实服务 |

所有 baseline 必须满足 fairness：

```text
same initial state
same ramp demand
same horizon
same action availability, unless baseline definition explicitly removes actions
same physical validity checks
same no-hidden-fallback rule
same denominator policy
```

## 10. Evidence Package 设计

建议输出目录：

```text
outputs/d2_5_theory_alignment/
  d2_5_report.md
  theory_metric_audit.md
  evidence_package/
    raw_large_gap_trap/
    forced_accommodation/
    near_miss_production/
    bad_action_suppression/
    physical_gap_conflict/
    rolling_stale_performance/
  gate_D2_5_input/
    aggregate_metrics.csv
    scenario_summary.csv
    candidate_edges.csv
    candidate_actions.csv
    action_value_decomposition.csv
    selected_action_trace.csv
    reservation_trace.csv
    realized_events.csv
    disturbance_metrics.csv
    recovery_debt_metrics.csv
    safety_metrics.csv
    baseline_comparison.csv
    failure_trace.csv
    manifest.json
  human_review/
    README.md
    claim_cards.md
    scenario_cards.md
    theory_to_metric_mapping.md
    baseline_fairness_audit.md
    disturbance_audit.md
    failure_trace_drilldown.md
    paper_claim_boundary.md
```

D2.5 的 evidence package 必须能够回答：

```text
哪个 claim？
哪个 scenario？
哪个 baseline？
初始状态是否公平？
RPMI-CMV 选了哪个 gap/action？
baseline 选了哪个 gap/action？
为什么选？
服务了多少 demand？
代价是多少？
是否产生 hard brake / wave / unsafe event？
失败能否追链？
论文 claim 应该 strengthen、qualify 还是 revise？
```

## 11. D2.5 Gate-style 判定

D2.5 完成后建议新增一个轻量 Gate-style decision，不叫 Gate D3，避免和 Wave 9 混淆。可以叫：

```text
Gate D2.5: Deterministic Theory-Evidence Alignment Decision
```

可能结果：

```text
support
qualified_support
revise_theory
revise_experiment
insufficient_trace
```

### 11.1 support 条件

满足：

```text
至少 1 个 raw-gap trap 场景中，RPMI-CMV demand service 不差且 RD/disturbance 更低。
至少 1 个 forced-accommodation 场景中，RPMI-CMV 在 merge success 相近时 hard brake/wave/action cost 更低。
至少 1 个 bad-action suppression 场景中，RPMI-CMV 选择 none 或低扰动 action，并能用 J/RCMV/cost 解释。
至少 1 个 near-miss production 场景中，RPMI-CMV 通过低扰动 action 改善 Z_R/RD 并服务 demand。
所有 target scenarios 同时报告 demand denominator 和 disturbance metrics。
所有 positive cases 能追 selected_action -> selected_edge/gap -> reservation -> realized_event -> metric change。
```

### 11.2 qualified_support 条件

满足：

```text
部分理论靶场成立，但不是所有 claim 都有强证据。
或者 demand service 有改善，但 disturbance 指标只在部分场景改善。
或者 disturbance 指标改善明显，但 merge success 不稳定，需要收窄表述。
```

论文可写：

```text
Deterministic target scenarios provide qualified evidence that recoverability-aware action-conditioned reservation can reduce disturbance or recovery cost in designed regimes, while broader performance gains remain scenario-dependent.
```

### 11.3 revise_theory 条件

出现：

```text
精心构造 target scenarios 中，RPMI-CMV 仍不能降低 RD/disturbance/wave。
RCMV 选择方向与论文理论长期不一致。
RD 或 C_bar 与 realized outcome 没有可解释关系。
baseline 持续以同等或更低代价获得相同服务效果。
```

处理：

```text
回到论文理论，修改 claim 强度或公式设计。
不要进入 Wave 9。
```

### 11.4 revise_experiment 条件

出现：

```text
理论上应出现差异，但 scenario 没有形成足够冲突或扰动。
baseline 太弱或太强，不能回答理论问题。
指标缺失，无法看出 disturbance / recovery / wave。
simulator 太简化，无法表达速度波或 hard brake。
```

处理：

```text
重设 scenario generator、baseline 或 metrics。
不要把 inconclusive 写成理论失败。
```

### 11.5 insufficient_trace 条件

出现：

```text
selected_action 无法 join selected_edge/gap。
reservation 无法 join realized_event。
disturbance metric 无法回到 action or vehicle。
failure 被 summary 覆盖，不能解释。
```

处理：

```text
先修 trace 和 evidence hygiene，再谈论文主张。
```

## 12. 分阶段执行计划

### Stage 1: 只读理论-指标审计

目标：

```text
确认论文理论 claim、实现字段、现有 CSV、实验表格是否对齐。
```

任务：

```text
1. 读取论文稿中与 recoverability、RCMV、RD、C_bar、reservation、slot conflict、rolling 有关的段落。
2. 读取现有 src/rpmi 实现，定位 J / RCMV / RD / cost 的计算路径。
3. 读取现有 evidence package，列出已有字段和缺失字段。
4. 生成 theory_metric_audit.md。
```

退出条件：

```text
每个核心 claim 都能映射到公式、代码字段、CSV 字段和实验指标。
无法映射的 claim 被标为 evidence gap。
```

### Stage 2: Target scenario 设计

目标：

```text
为 C-A、C-C、C-D 设计 deterministic 靶场。
```

任务：

```text
1. 定义每个 scenario 的车辆位置、速度、gap、ramp arrival、CAV 可控对象。
2. 为每个 scenario 写明 baseline 预期和 RPMI-CMV 预期。
3. 设置 fairness guardrail。
4. 定义 pass/fail 指标。
```

退出条件：

```text
每个 scenario 有清楚的 theory target、expected mechanism、required metrics、failure interpretation。
```

### Stage 3: 指标与日志补齐

目标：

```text
让实验能报告 disturbance、recovery、safety、selection explanation。
```

任务：

```text
1. 增加 disturbance_metrics.csv。
2. 增加 recovery_debt_metrics.csv。
3. 增加 safety_metrics.csv。
4. 增加 action_value_decomposition.csv。
5. 确保 failure_trace 能 join action/gap/reservation/event/metric。
```

退出条件：

```text
每个 target scenario 都能同时报告 demand denominator 和 performance cost。
```

### Stage 4: Baseline 与 ablation 实现或整理

目标：

```text
让每个 claim 有对应对照。
```

任务：

```text
1. raw_largest_gap baseline。
2. forced_accommodation baseline。
3. no_action_natural baseline。
4. reservation_before_action / stale baseline。
5. without_RD / without_Cost ablation。
6. without_conflict_blocking diagnostic ablation。
```

退出条件：

```text
每个 baseline 的初始状态、公平性和限制条件被 manifest 记录。
```

### Stage 5: Targeted evidence 运行

目标：

```text
生成 D2.5 deterministic target evidence package。
```

任务：

```text
1. 运行每个 target scenario。
2. 导出 scenario-level 和 row-level CSV。
3. 生成 human_review。
4. 抽样检查至少 5 条 success/failure/cost trade-off trace。
```

退出条件：

```text
所有 target scenarios completed 或明确 failure reason。
所有关键指标可追链。
```

### Stage 6: D2.5 判定与论文边界建议

目标：

```text
判断 deterministic theory evidence 是否支持论文核心 claim。
```

任务：

```text
1. 对每个 claim 给出 support / qualified_support / revise_theory / revise_experiment / insufficient_trace。
2. 生成 D2.5 report。
3. 生成 paper_claim_boundary.md。
4. 决定是否进入 Wave 9。
```

退出条件：

```text
明确回答: Wave 9 是可以继续，还是必须先修理论/实验。
```

## 13. 最小成功标准

D2.5 的最小成功不是“所有指标都赢”。最小成功是：

```text
至少在论文理论命中的 deterministic target scenarios 中，能展示 RPMI-CMV 的优势机制。
```

建议最小标准：

```text
1. Raw-Large-Gap Trap 中，RPMI-CMV 不选择几何最大但高债务 gap，而选择 recoverability 更高 gap。
2. Forced-Accommodation 中，RPMI-CMV 在 demand service 相近时 disturbance 或 wave 更低。
3. Bad-Action Suppression 中，RPMI-CMV 能拒绝高成本动作。
4. Near-Miss Production 中，RPMI-CMV 能通过低扰动动作改善 near-miss edge。
5. 所有 positive case 都能解释 J / RCMV / RD / C_bar。
6. 所有场景都报告 demand denominator。
7. failure 不隐藏，negative/control 场景不包装成 success。
```

如果这些标准达成，论文就可以从“机制可审计”进一步升级为：

```text
deterministic target regimes 中，RPMI-CMV 的 recoverability-aware action-conditioned reservation 展示出低扰动服务优势。
```

如果只部分达成，则写 qualified support。

如果完全达不成，则优先修理论、指标或 scenario，而不是进入 Wave 9。

## 14. 论文写作影响

D2.5 完成前，论文不应写：

```text
RPMI-CMV significantly reduces traffic waves.
RPMI-CMV robustly improves merge success.
RCMV reliably selects low-disturbance production actions.
Conflict-aware rolling integer assignment is validated.
Stochastic robustness is demonstrated.
```

D2.5 若成功，论文可以写：

```text
In deterministic target scenarios, RPMI-CMV's recoverability-aware selection avoids misleading raw geometric gaps and reduces disturbance or recovery cost compared with raw-gap or forced-accommodation baselines.
```

中文含义：

```text
在确定性靶场中，RPMI-CMV 能避免 raw gap 的误导，并在与粗暴主线配合 baseline 相比时降低扰动或恢复代价。
```

D2.5 若只部分成功，论文应写：

```text
Targeted deterministic evidence provides qualified support for the mechanism, while performance gains remain scenario-dependent and require further validation.
```

D2.5 若失败，论文应写：

```text
Current evidence supports traceable reservation and failure accounting, but does not yet validate the proposed performance mechanism. Formula design, scenario construction, or disturbance metrics require revision.
```

## 15. 风险与应对

| 风险 | 表现 | 应对 |
|---|---|---|
| baseline 不公平 | baseline 被故意设弱，RPMI-CMV 虚假胜利 | manifest 记录 same initial state / same demand / same horizon |
| 指标不敏感 | hard_brake 或 wave 几乎不变 | 增加 max_deceleration、speed variance、disturbance cost |
| scenario 不命中理论 | 所有方法结果差不多 | 重新构造 raw-gap trap 或 forced-accommodation stress |
| RCMV 与 outcome 脱节 | selected_RCMV positive 但 realized outcome 差 | 检查 rollout、RD、cost normalization 和 action execution |
| action cost 太弱 | 算法总是执行激进动作 | 调整或审计 lambda_C，不直接调参追胜率 |
| action cost 太强 | 算法总是 none | 检查 theta、candidate generation、near-miss 可达性 |
| rolling 干扰主 claim | lifecycle 复杂性掩盖 target performance | D2.5 可以先用 single/short rolling deterministic micro scenario |
| trace 不完整 | 指标无法回到 action/gap | 先修 logging，不写结论 |

## 16. 建议的执行顺序

最推荐的顺序是：

```text
1. D2.5 plan approval
2. theory_metric_audit.md
3. target scenario design doc
4. metric schema patch
5. baseline/ablation patch
6. targeted evidence run
7. human_review package
8. D2.5 decision report
9. paper claim revision
10. 决定是否进入 Wave 9
```

其中第 2 步非常关键。不要先写大量代码。先确认论文理论到底要证明什么、现有实验到底能测什么。如果理论 claim 和指标字段没有对齐，后面的 batch 越多越容易制造噪声。

## 17. 给后续 Codex Agent 的建议 Prompt

后续可用如下 prompt 启动 D2.5 的第一阶段：

```text
请读取：
docs/specs/00_ACTIVE_SPECS_README_v2.1_zh.md
docs/specs/01_Codex_Implementation_Wave_Guide_Paper_Experiment_Closed_Loop_v2.1_zh.md
docs/specs/12_Paper_Claim_Evidence_Decision_Matrix_v2.1_zh.md
docs/specs/13_Claim_Staging_and_Gate_Interpretation_Guardrail_v2.1_zh.md
docs/specs/14_D2_5_Theory_Evidence_Alignment_Targeted_Performance_Validation_Plan_v1_zh.md
docs/paper/第3.1版论文稿.md
outputs/wave8_rolling_validation/wave8_d2_input_v2/gate_D2_decision.json
outputs/wave8_rolling_validation/wave8_d2_input_v2/gate_D2_report.md
outputs/wave8_rolling_validation/wave8_d2_input_v2/gate_D2_claim_revision_plan.md

本次只执行 D2.5 Stage 1：Theory-to-Metric Consistency Audit。

禁止执行 Wave 9、禁止实现 stochastic IDM、禁止执行 Gate D3、禁止修改论文稿。

请只读审计论文理论 claim、代码实现字段、现有 evidence CSV 字段和指标表之间的对应关系，输出：
outputs/d2_5_theory_alignment/theory_metric_audit.md

必须回答：
1. J / RCMV / RD / C_bar 分别对应哪些代码字段和 CSV 字段？
2. 这些字段是否真的参与 selected_action 或 reservation selection？
3. 哪些论文 claim 当前有 evidence 字段支撑？
4. 哪些 claim 只是 framework proposal 或 pending validation？
5. 后续 target scenarios 必须补哪些指标？

本阶段不得写 retain/downgrade/remove 结论，只输出审计和下一步建议。
```

## 18. 最终建议

当前最稳的研究路线是：

```text
不要进入 Wave 9。
先执行 D2.5。
```

原因不是 Wave 9 不重要，而是 Wave 9 的前提尚未完全打牢。论文理论真正需要先证明的是：

```text
在 deterministic target regimes 中，recoverability-aware、action-conditioned、cost-aware 的 RPMI-CMV 是否真的能比 raw-gap 或 forced-accommodation baseline 以更低扰动服务 demand。
```

如果 D2.5 成功，论文会明显变强，因为它不再只是说“我有完整状态机和 trace”，而是能说“我的理论机制在该赢的场景里确实赢了，而且知道为什么赢”。

如果 D2.5 失败，论文也会变强，因为我们能诚实定位问题：是理论公式需要修改，还是实验靶场设计不对，还是指标体系不够表达交通波动，还是实现没有真正让 RD / C_bar 参与决策。

这一步是论文从“工程机制可审计”走向“理论机制可证明”的关键。
