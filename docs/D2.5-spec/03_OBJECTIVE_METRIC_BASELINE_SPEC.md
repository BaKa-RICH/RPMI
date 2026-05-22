# 03 Objective / Metrics / Baseline 规格

## 1. Objective 重构

### 1.1 新目标函数

D2.5 推荐将 objective 升级为：

```text
J(a) =
  lambda_Z * Z_R_norm(a)
+ lambda_D * RD_pred_norm(a)
+ lambda_C * C_dist_norm(a)
+ lambda_S * S_safety_penalty(a)
+ lambda_Q * Q_churn_penalty(a)
```

其中：

```text
RCMV(a) = J(a0_none) - J(a)
```

选择规则：

```text
if max_a RCMV(a) > theta:
    selected_action = argmax_a RCMV(a)
else:
    selected_action = a0_none
```

### 1.2 为什么要改

旧版本风险：

```text
C_bar 可能只是 action effort proxy；
RD 可能只是 simplified proxy；
positive RCMV 可能很小但仍触发 action；
高 churn / supersede 没有被惩罚；
safety margin 可能没有作为连续 penalty 进入 selection。
```

这不是“投降式改理论”，而是让 objective 服务论文主故事：

```text
recoverability-aware + disturbance-aware + action-conditioned slot selection。
```

---

## 2. 各项定义

### 2.1 Z_R_norm

含义：

```text
recoverable inventory deficit normalized by demand.
```

建议：

```text
Z_R_norm = max(D_H - S_R, 0) / max(D_H, epsilon)
```

注意：

```text
Z_R 不能压倒所有项；否则算法会为了服务一个 demand 执行高扰动动作。
```

### 2.2 RD_pred_norm

RD 应从抽象 proxy 升级为 predicted recovery burden。

建议组成：

```text
required_rear_deceleration_pred
recovery_time_estimate_pred
affected_vehicle_count_pred
post_merge_speed_drop_pred
wave_amplitude_proxy_pred
outflow_loss_proxy_pred
```

推荐形式：

```text
RD_pred_norm =
  beta_B * norm(required_rear_deceleration_pred)
+ beta_T * norm(recovery_time_estimate_pred)
+ beta_N * norm(affected_vehicle_count_pred)
+ beta_V * norm(post_merge_speed_drop_pred)
+ beta_A * norm(wave_amplitude_proxy_pred)
+ beta_Q * norm(outflow_loss_proxy_pred)
```

必须同时输出 realized 对照：

```text
RD_realized
RD_delta = RD_after - RD_before
RD_prediction_error = RD_realized - RD_pred
```

### 2.3 C_dist_norm

将旧 `C_bar` 升级为 disturbance-aware cost。

建议组成：

```text
action_effort
induced_mainline_deceleration
mean_abs_acceleration
acceleration_variance
speed_variance_delta
wave_amplitude_proxy
affected_vehicle_count
```

推荐形式：

```text
C_dist_norm =
  gamma_U * norm(action_effort)
+ gamma_B * norm(induced_mainline_deceleration)
+ gamma_A * norm(mean_abs_acceleration)
+ gamma_VAR * norm(speed_variance_delta)
+ gamma_W * norm(wave_amplitude_proxy)
+ gamma_N * norm(affected_vehicle_count)
```

必须记录：

```text
C_bar_legacy
C_dist_new
C_dist_components_json
```

如果 `C_bar` 被确认只是 action effort，不要在论文里叫 mainline disturbance cost。

### 2.4 S_safety_penalty

建议组成：

```text
min_TTC penalty
DRAC penalty
min_gap penalty
unsafe_margin penalty
predicted_overlap penalty
realized_invalid_event penalty
```

推荐：

```text
S_safety_penalty =
  penalty(min_TTC < TTC_min)
+ penalty(DRAC > DRAC_max)
+ penalty(min_gap < gap_min)
+ penalty(predicted_overlap)
```

这里 safety penalty 不是 hidden fallback。它只影响选择和报告；不允许事后自动修复 unsafe trajectory。

### 2.5 Q_churn_penalty

D2-ACTION-CONDITIONED-RECOMPUTE 的高 churn/unserved 风险说明，需要显式惩罚：

```text
reservation_supersede_count
action_switch_count
active_guidance_change
plan_lock_violation
stale_risk
new_plan_improvement_below_hysteresis
```

推荐：

```text
Q_churn_penalty =
  q1 * supersede_risk
+ q2 * switching_risk
+ q3 * active_guidance_change_risk
+ q4 * stale_risk
```

---

## 3. Calibration 规则

Calibration 不是 blind parameter sweep。D2.5 的 objective 更新必须是 failure-driven co-design：

```text
Objective update must be failure-driven.
Do not tune objective blindly.
Each change must be tied to one diagnostic failure mode.
```

参数网格只能服务诊断闭环，不能服务最终实验现场调参。所有 calibration / co-design 结果必须在 Evaluation Lock 前完成；锁定后只能做 secondary sensitivity reporting，不能改变 locked objective、scenarios、baselines、metrics 或 pass/fail criteria。

### 3.1 可调参数

```text
lambda_Z
lambda_D
lambda_C
lambda_S
lambda_Q
theta
RD component weights beta_*
C_dist component weights gamma_*
hard_brake_threshold
wave_window
TTC_min
DRAC_max
churn_hysteresis
```

### 3.2 允许调参，但必须可辩护

允许围绕 target regime 调参。论文不需要证明 universal optimality。  
但必须遵守：

```text
1. 先定义 target regime，再调参。
2. 一组 default parameters 适用于所有 D2.5 target scenarios。
3. 所有尝试写入 objective_calibration_log.csv。
4. 失败 run 保留。
5. 不允许只展示成功 seed / 成功参数。
6. 不允许为了让 baseline 输而给 baseline 更差物理规则。
```

### 3.3 推荐调参顺序

```text
Step 1: 固定 lambda_Z = 1.0。
Step 2: 扫 lambda_C，确保 bad-action suppression 能选 none / low-cost action。
Step 3: 扫 lambda_D，确保 raw-gap trap 中高 RD gap 被压制。
Step 4: 加 lambda_S，确保 unsafe 或低 TTC candidate 被压制。
Step 5: 加 lambda_Q，降低 recompute churn / supersede。
Step 6: 扫 theta，避免 tiny positive RCMV 触发无意义 action。
```

### 3.4 推荐网格

先小网格：

```text
lambda_D in {0.5, 1.0, 2.0, 4.0}
lambda_C in {0.5, 1.0, 2.0, 4.0}
lambda_S in {0.0, 1.0, 2.0}
lambda_Q in {0.0, 0.5, 1.0}
theta in {0.0, 0.001, 0.005, 0.01}
```

若数值尺度不同，Codex 应先输出 observed component ranges，再自适应调整网格。不要盲目使用这些数字。

### 3.5 Failure-driven co-design calibration

每次 objective 或 diagnostic scenario 修改都必须绑定一个已观测 failure。要求循环：

```text
1. Run full / baseline / ablation on a diagnostic scenario.
2. Record selected gap/action and all J components.
3. Compare predicted RD / C_dist with realized RD / disturbance.
4. Classify failure:
   - objective_scale_failure
   - RD_definition_failure
   - C_dist_definition_failure
   - theta_failure
   - churn_failure
   - scenario_not_diagnostic
   - metric_insensitive
   - baseline_unfair
   - implementation_bug
   - simulator_sensitivity_insufficient
5. Modify only the relevant component.
6. Re-run the minimal diagnostic case.
7. Keep or revert the change.
8. Log the decision.
```

不允许：

```text
1. 为每个 scenario 单独 cherry-pick lambda / theta。
2. 只保留成功 run。
3. 因 final evaluation 结果不好而现场改 objective。
4. 用更差的物理规则让 baseline 输。
5. 在 trace join 不完整时把 positive RCMV 写成 performance support。
```

### 3.6 co_design_iteration_log.csv 最低字段

```text
iteration_id
scenario_design_id
scenario_family
mechanism_target
failure_observed
failure_type
hypothesis
changed_component
old_value
new_value
selected_gap_before
selected_gap_after
selected_action_before
selected_action_after
RD_pred_direction_match
C_dist_direction_match
realized_disturbance_change
ablation_sensitivity_change
keep_or_revert
reason
```

### 3.7 objective_scenario_design_register.csv 最低字段

```text
scenario_design_id
scenario_family
construction_principle
mechanism_target
diagnostic_contrast
controlled_knobs
parameter_ladder_id
random_seed_optional
expected_baseline_failure
expected_full_behavior
minimum_activation_gate
anti_cherry_picking_rule
held_out_variant_rule
lock_status
```

### 3.8 mechanism_activation_report.md 必答问题

进入 Evaluation Lock 前，必须回答：

```text
1. raw_largest_gap 是否稳定选择机制设计中的 Gap A？
2. forced_accommodation 是否能服务但带来更高 disturbance？
3. full RPMI-CMV 是否选择 Gap B / low-cost action / none？
4. without_RD 是否更容易选高 RD gap？
5. without_Cbar 是否更容易选高 disturbance action？
6. without_theta 是否更容易触发 tiny-RCMV action 或 churn？
7. RD_pred / C_dist_pred 是否与 realized metrics 同向？
8. selected_action 是否能 join 到 realized_event 和 metric change？
```

如果这些问题没有答案，不得进入 Evaluation Lock。

---

## 4. 必补 Metrics

### 4.1 Demand denominator

必须保留：

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

红线：

```text
failed_reservation_rate = 0.0
不等于
merge_success_rate_over_demand = 1.0
```

### 4.2 Disturbance metrics

必须新增或强化：

```text
hard_brake_count
max_deceleration
mean_abs_acceleration
acceleration_variance
speed_variance_before
speed_variance_after
speed_variance_delta
max_wave_amplitude
mainline_disturbance_cost
mainline_disturbance_cost_normalized
action_cost_sum
action_cost_per_served_demand
affected_vehicle_count
```

### 4.3 Recovery metrics

```text
mean_RD_candidate
mean_RD_selected
mean_RD_pred
mean_RD_realized
RD_before_action
RD_after_action
RD_delta
max_RD
RD_per_served_demand
recovery_time_estimate
post_merge_speed_drop
outflow_loss_proxy
required_rear_deceleration
```

### 4.4 Safety metrics

```text
min_realized_gap
min_predicted_gap
min_TTC
DRAC
min_surrogate_safety_margin
physical_validity_failed_count
realized_invalid_event_count
unsafe_overlap_count
no_fallback_invalid_event_count
```

### 4.5 Selection explanation metrics

```text
candidate_action_count
positive_RCMV_candidate_count
selected_action_rank
selected_action_type
selected_action_id
selected_edge_id
selected_physical_gap_id
selected_P_R
selected_RD_pred
selected_C_dist
selected_Z_R
J_none
selected_J
selected_RCMV
RCMV_margin_to_second_best
theta
lambda_Z
lambda_D
lambda_C
lambda_S
lambda_Q
```

---

## 5. Baseline / Ablation 设计

### 5.1 raw_largest_gap

用途：

```text
证明 raw geometric gap 会被误导。
```

允许知道：

```text
candidate physical gaps
raw gap size
basic physical validity screen
same candidate time grid
```

不允许知道：

```text
RD
RCMV
C_dist
future realized disturbance
RPMI selected gap
```

选择规则：

```text
select candidate with largest raw_gap_size among physically feasible candidates.
```

### 5.2 fifo_feasible_gap

用途：

```text
检验简单先到先服务。
```

允许知道：

```text
demand order
physical validity
reachability
```

不允许知道：

```text
RD ranking
disturbance cost ranking
future outcomes
```

### 5.3 forced_accommodation

用途：

```text
证明强行合流成功不等于低扰动合流。
```

允许：

```text
为了服务 demand，使用上限内的 CAV acceleration / deceleration / micro-adjustment。
```

不允许：

```text
违反 physical validity；
使用 hidden fallback；
使用 RPMI 的 objective 排名；
未来知道哪条 trajectory disturbance 最低。
```

必须输出：

```text
forced action type
forced action magnitude
hard_brake_count
max_deceleration
speed_variance_delta
wave_amplitude
mainline_disturbance_cost
```

### 5.4 no_action_natural

用途：

```text
检验自然可恢复库存是否已经足够。
```

规则：

```text
只做自然 rollout 和 reservation，不做 active production action。
```

### 5.5 reservation_before_action / stale_reservation

用途：

```text
检验 action-conditioned recompute 的必要性。
```

规则：

```text
先基于 no-action state 生成 reservation，再执行 action 或滚动，不重新生成 action-conditioned reservation。
```

### 5.6 without_RD

用途：

```text
检验 RD 是否真实影响选择。
```

规则：

```text
lambda_D = 0
其他项不变。
```

期望：

```text
若 without_RD 和 full 选择相同且结果相同，RD 对主故事贡献不足。
```

### 5.7 without_Cbar / without_cost

用途：

```text
检验 C_dist 是否压制高扰动动作。
```

规则：

```text
lambda_C = 0
其他项不变。
```

期望：

```text
without_Cbar 更容易选择 forced / high-disturbance action。
```

### 5.8 without_theta

用途：

```text
检验 threshold 是否避免 tiny positive RCMV 触发无意义 action。
```

规则：

```text
theta = 0
其他项不变。
```

期望：

```text
without_theta 更容易产生 churn / low-value action。
```

### 5.9 without_conflict_blocking

用途：

```text
只作为 denominator honesty 补充，不作为低扰动主线。
```

规则：

```text
关闭 physical_gap_id / slot_group_id conflict blocking。
```

警告：

```text
该 baseline 可能虚高 service rate，必须明确标注 duplicate physical gap consumption。
```

---

## 6. Baseline fairness audit 模板

每个 baseline 必须记录：

```text
baseline_id:
same_initial_state: true/false
same_demand: true/false
same_horizon: true/false
same_candidate_time_grid: true/false
same_physical_validity_rule: true/false
same_no_hidden_fallback_rule: true/false
same_denominator_policy: true/false
uses_future_realized_outcome: true/false
uses_RPMI_only_information: true/false
allowed_information:
forbidden_information:
known_advantage:
known_limitation:
fairness_pass:
fairness_failure_reason:
```

任何 baseline 如果 `uses_future_realized_outcome=true` 或 `uses_RPMI_only_information=true`，不得用于论文性能主结论。
