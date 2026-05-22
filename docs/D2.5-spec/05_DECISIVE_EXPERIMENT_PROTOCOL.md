# 05 决定性实验协议：D25-DECISIVE-RAW-GAP-FORCED-TRAP

## 0. 为什么它是最关键实验

这个实验一次性打中论文主故事：

```text
raw geometric gap 不等于 useful merge slot；
forced accommodation 成功率高不等于低扰动；
RPMI-CMV 的 RD / C_dist / RCMV 应该把选择推向 recoverable low-disturbance slot。
```

如果这个实验都打不出来，先不要进入 Wave 9。  
如果它能打出来，论文就有了 target-regime deterministic evidence 的核心图表。

---

## 1. 实验对象

本协议只负责 Evaluation Lock 之后的 final evidence。Calibration sweep 必须已经在 Objective–Diagnostic Scenario Co-Design Loop 中完成。

红线：

```text
After Evaluation Lock, Codex may run sensitivity reporting only as secondary analysis.
It must not change the locked objective, scenarios, baselines, metrics, or pass/fail criteria.
If the locked decisive experiment fails, do failure classification without tuning.
```

比较：

```text
full_RPMI_reconstructed_objective
legacy_RPMI_objective
raw_largest_gap
forced_accommodation
no_action_natural
without_RD
without_Cbar
without_theta
reservation_before_action / stale_reservation
```

最小可运行集合：

```text
full_RPMI_reconstructed_objective
raw_largest_gap
forced_accommodation
without_RD
without_Cbar
without_theta
```

---

## 2. 实验流程

### Step 0：Verify lock package

先确认以下 lock 文件存在并一致：

```text
LOCKED_OBJECTIVE.md
LOCKED_SCENARIOS.md
LOCKED_BASELINES.md
LOCKED_METRICS.md
LOCKED_PASS_FAIL_CRITERIA.md
run_manifest.json
```

如果缺失任一 lock 文件，不进入 final experiment。

### Step 1：Sanity check locked scenario

确认：

```text
1. 场景中存在 Gap A 和 Gap B。
2. Gap A raw_gap_size > Gap B raw_gap_size。
3. Gap A closing_rate > Gap B closing_rate。
4. Gap A RD_pred > Gap B RD_pred。
5. Gap A forced action 会产生更高 disturbance。
6. Gap B reachable and physically valid 或可被 low-cost action-conditioned valid。
```

如果这些不满足，不要现场调 scenario；输出 failure classification，并回到 co-design 阶段。

### Step 2：Run no_action_natural

目的：

```text
判断自然可恢复库存是否已经足够。
```

输出：

```text
no_action_Z_R
no_action_merge_success
no_action_RD_realized
no_action_disturbance
```

解释：

```text
如果 no_action 已经和 RPMI 一样好，场景可能太容易。
```

### Step 3：Run raw_largest_gap

预期：

```text
raw 选择 Gap A。
```

如果 raw 不选 Gap A，场景没有形成 raw-gap trap。

### Step 4：Run forced_accommodation

预期：

```text
forced 能让 demand merge；
但 hard_brake / max_deceleration / speed_variance / wave / disturbance 高。
```

如果 forced 不产生扰动，先审 simulator / metric sensitivity。

### Step 5：Run full RPMI with locked objective

预期：

```text
full 选择 Gap B 或 low-cost action-conditioned Gap B variant；
service 不差；
disturbance / RD / safety 更好；
trace join 完整。
```

### Step 6：Run locked ablations

```text
without_RD:
  如果它选择 Gap A 或高 RD gap，说明 RD 有贡献。

without_Cbar:
  如果它选择 high-disturbance forced action，说明 C_dist 有贡献。

without_theta:
  如果它触发 tiny positive RCMV action 或 churn，说明 theta 有贡献。
```

### Step 7：Run locked sensitivity reporting

这一步只能报告 locked objective 附近的敏感性，不能改变最终证据使用的 objective / scenario / baseline / metric / pass-fail rule。

禁止把 sensitivity / calibration run 当成 final evidence。

```text
lambda_D
lambda_C
lambda_S
lambda_Q
theta
selected_gap
selected_action
RD_realized
mainline_disturbance_cost
hard_brake_count
max_deceleration
speed_variance_delta
max_wave_amplitude
min_TTC
pass_flag
fail_reason
locked_config_id
is_secondary_sensitivity
```

### Step 8：Build final evidence table

最小论文表格：

| variant | selected gap/action | service | RD_realized | hard brake | max decel | speed var delta | wave | disturbance cost | min TTC | join |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|

### Step 9：Failure classification without tuning

如果 final evidence 不支持主故事，不允许现场调参。只能输出：

```text
failure_type:
  - revise_objective
  - revise_metric
  - revise_scenario
  - revise_baseline
  - revise_implementation
  - simulator_sensitivity_insufficient
  - insufficient_trace_join
  - do_not_claim_performance

failed_locked_item:
evidence_file:
required_next_phase:
```

---

## 3. 通过标准

### Strong support

满足：

```text
1. raw_largest_gap 选择 Gap A。
2. forced_accommodation 服务成功或接近成功，但 disturbance 高。
3. full RPMI 选择 Gap B / low-cost variant。
4. full RPMI service 不差，或 service trade-off 可以用 safety / disturbance 解释。
5. full RPMI 至少两个 realized disturbance / recovery / safety 指标明显优于 raw/forced。
6. without_RD / without_Cbar / without_theta 至少一个 ablation 破坏选择或结果。
7. trace join 完整。
```

### Qualified support

满足：

```text
1. full RPMI 确实降低 disturbance / RD，但 service 略低；
2. 或 full RPMI 只在部分指标胜出；
3. 或 ablation 差异存在但 effect size 小；
4. 或 scenario 需要较强参数才能显现。
```

论文写法：

```text
targeted deterministic evidence provides qualified support；
performance gains are scenario-dependent。
```

### No support / hold

出现任一核心问题：

```text
1. full RPMI 与 raw/forced 选择和结果无差异。
2. RD_pred 低但 RD_realized / disturbance 不低。
3. C_dist 低但 realized disturbance 高。
4. positive RCMV 不能 join outcome。
5. ablation 与 full 完全一样。
6. baseline fairness 不成立。
7. forced baseline 无法产生可测扰动差异。
```

---

## 4. 指标阈值建议

如果 simulator 单位和尺度稳定，可以使用：

```text
relative_improvement >= 10%：可称为 visible reduction
relative_improvement >= 20%：可称为 clear reduction
relative_improvement < 10%：只写 directionally lower，不写 strong
```

应用指标：

```text
mainline_disturbance_cost
RD_realized
max_deceleration magnitude
speed_variance_delta
max_wave_amplitude
hard_brake_count
```

安全指标不能只看改善百分比：

```text
min_TTC 必须不低于 safety threshold；
min_realized_gap 必须非负并满足 margin；
invalid_or_unsafe_event_count 必须不高于 baseline，最好为 0。
```

如果 simulator 指标尺度不稳定，先不要使用固定阈值。用排序、方向、组件分解和原始 trace 解释。

---

## 5. 失败拆解树

### Case A：raw 和 full 都选 Gap A

检查顺序：

```text
1. Gap A 的 RD_pred 是否真的高？
2. C_dist 是否真的计入 action cost？
3. lambda_D / lambda_C 是否太低？
4. Gap B 是否 reachability / validity 失败？
5. RCMV selection 是否真的使用了 reconstructed objective？
```

### Case B：full 选 Gap B，但 disturbance 不低

检查顺序：

```text
1. RD_pred 与 RD_realized 是否不同向？
2. C_dist_pred 与 disturbance_realized 是否不同向？
3. simulator 是否记录 follower braking / speed wave？
4. merge execution 是否使用了 hidden fallback？
5. Gap B 是否其实造成 ramp acceleration / insertion disturbance？
```

### Case C：forced baseline 不高扰动

检查顺序：

```text
1. forced action magnitude 是否足够？
2. follower response 是否被模拟？
3. hard brake threshold 是否太宽？
4. speed variance / wave window 是否覆盖受影响车辆？
5. 当前 simulator 是否太简化，无法表达主线扰动？
```

### Case D：without_RD / without_Cbar / without_theta 和 full 一样

解释：

```text
objective 项没有边际贡献；
场景 trade-off 不够强；
或者实现中 ablation 没有真正关闭对应项。
```

下一步：

```text
增强场景 trade-off；
打印 action_value_decomposition；
检查 J components。
```

### Case E：positive RCMV 最终 unserved

解释：

```text
local objective myopic；
reservation churn / stale risk 未惩罚；
theta / hysteresis 不足；
action-conditioned rollout 与 realized rollout 脱节。
```

下一步：

```text
加入 Q_churn；
提高 theta；
加入 active guidance lock / switching hysteresis；
检查 reachability / survival uncertainty。
```

---

## 6. 论文图表建议

如果实验通过，建议生成：

```text
Figure 1: Raw gap size vs selected useful slot, Gap A / Gap B schematic.
Figure 2: Objective decomposition bar chart for candidates and baselines.
Figure 3: Realized disturbance metrics by variant.
Figure 4: Trace chain: action -> edge -> reservation -> realized event -> metrics.
Table 1: Baseline comparison.
Table 2: Ablation comparison.
Table 3: Failure / boundary cases.
```

不建议先画大而散的 multi-scenario average。先把决定性机制讲清楚。
