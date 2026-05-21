# Gate D2: Rolling Reservation Claim Decision v2 中文版

## 0. 执行前必读资料

任何 Codex 执行 Gate D2 前，必须先读取：

```text
docs/specs/00_ACTIVE_SPECS_README_v2.1_zh.md
docs/specs/01_Codex_Implementation_Wave_Guide_Paper_Experiment_Closed_Loop_v2.1_zh.md
docs/specs/06_Gate_D1_Lane_Change_Production_Claim_Decision_v2_zh.md
docs/specs/07_Wave_8_Rolling_Horizon_Reservation_and_D2_Evidence_Spec_v2_zh.md
docs/specs/08_Gate_D2_Rolling_Reservation_Claim_Decision_v2_zh.md
docs/specs/12_Paper_Claim_Evidence_Decision_Matrix_v2.1_zh.md
docs/specs/13_Claim_Staging_and_Gate_Interpretation_Guardrail_v2.1_zh.md
docs/paper/第3.1版论文稿.md
```

Gate D2 不实现新功能，只裁决 Wave 8 evidence package 对 rolling horizon reservation claim 的支持强度。

## 1. Gate 定位

Gate D2 不判断“rolling 有没有跑起来”。Gate D2 判断 rolling reservation 是否足以支撑“可运行控制机制”主张：

```text
在多 decision_context 下，系统能稳定维护 plan / demand / slot / reservation / action 生命周期，
并在 stale、expiration、slot conflict、partial action、plan churn 等情况下保持可审计闭环和可解释收益。
```

核心判定问题：

```text
rolling reservation 是否既闭环、又有收益、还稳定？
```

Gate D2 不否定 `docs/paper/第3.1版论文稿.md` 作为完整研究目标草稿，也不裁决 Wave 9 stochastic robustness 的最终有效性。

若 D2 结果是 `remove/future_work`，只表示当前 evidence version 不能把 rolling horizon reservation 写成已验证结论；若该目标仍属于后续研究计划，应标记为 `pending_later_wave_validation` 或 `future_work`，不是永久删稿令。

Wave 9 / Gate D3 不补 rolling 的首次有效性证明；Wave 9 只检验 stochastic IDM V1 鲁棒性。

## 2. 输入

```text
gate_D2_input/
decision_contexts.csv
reservation_replans.csv
action_lifecycle.csv
rolling_reservations.csv
rolling_demand_lifecycle.csv
rolling_slot_consumption.csv
rolling_matching_trace.csv
rolling_plan_commitment.csv
rolling_failure_trace.csv
rolling_vs_single_demand_metrics.csv
rolling_vs_stale_ablation_metrics.csv
rolling_vs_no_commitment_metrics.csv
aggregate_metrics.csv
failure_summary.csv
rolling_trace_samples/
```

缺任一核心文件，则 D2 fail。

## 3. 完整性检查

任一失败则 D2 fail：

```text
decision_context_id 不唯一
demand_id / reservation_id / action_id / edge_id / physical_gap_id 无法 join
expired/cancelled demand 未回流且未解释
merged demand 未从后续 demand set 移除
同一 ramp_vehicle 在同一 context 有多个 active/planned reservation
physical_gap_id 或 slot_group_id 缺失
duplicate physical gap consumption 未检测
slot_consumption_conflict 未参与 matching 或 conservative blocking
每个 context 缺 baseline/action-conditioned/stale matching trace
planned reservation 无 persist/refresh/cancel/supersede 记录
active_guidance reservation 无 lock 语义
active_guidance 被取消但没有 safety/reachability/conflict reason
supersede 没有 improvement_margin / switching_cost 记录
rolling 与 single/stale/no_commitment baseline 的 initial state、demand arrival、horizon、threshold、action set 不公平
failure trace 无法 join 到 context/action/edge/reservation/demand/realized_event
hidden fallback 或 unsafe repair 存在
```

## 4. RETAIN 条件

D2 retain 必须同时满足：

```text
rolling_decision_count > 1
rolling_consistency_violation_count = 0 或低于 spec 明确阈值
duplicate_gap_consumption_count = 0
full_trace_join_rate = 1.0，或所有缺失 join 有人工解释
expired/cancelled demand 回流可审计
merged demand 移除可审计
每个 context 有 baseline/action-conditioned/stale matching trace
有效 planned reservation 默认 persist
active_guidance reservation 默认 locked
lock break 全部有 replan trigger 和 reason
rolling 相比 stale_no_replan baseline 在 stale/expiration/consistency 至少一类核心指标上改善
rolling 的 merge_success_rate_over_demand 不得无解释低于 single_t0/stale baseline
rolling 的 realized_unserved_demand_rate 不得无解释恶化
rolling_without_commitment 相比 committed rolling 有更高 churn 或更差稳定性，或报告解释为何 commitment 不是当前 claim
收益来自 refresh/cancel/reassignment/conflict-aware matching/commitment，而不是 hidden fallback
trace samples 展示成功闭环、失败闭环、plan-lock 延续闭环、replan 触发闭环
```

论文可写：

```text
rolling improves reservation consistency under evolving traffic states,
with audited demand lifecycle, conflict-aware slot consumption,
and plan-commitment stability.
```

## 5. DOWNGRADE 条件

D2 downgrade 用于：

```text
rolling lifecycle 已实现且 trace 可审计
但 demand denominator 改善不足
或 slot-consumption conflict 只完成 conservative approximation
或 plan commitment 只完成基础 persist/lock，缺少 no_commitment ablation
或 rolling 主要改善 stale/expiration 日志，不足以证明 realized service improvement
或收益存在但 plan churn 偏高，需要降级为 lifecycle/diagnostic evidence
```

论文写为：

```text
rolling horizon reservation is implemented as an auditable lifecycle extension;
current evidence supports plan persistence, stale/expiration diagnosis, and reservation hygiene,
but does not yet establish robust realized service improvement.
```

## 6. REMOVE / FUTURE WORK 条件

D2 remove/future_work 用于：

```text
rolling 只有 context/log，没有 demand lifecycle
无法证明 expired/cancelled demand 回流
无法防止 duplicate physical gap consumption
无法证明有效计划默认 persist
active guidance 被无理由频繁取消
trace 无法 join
rolling 改善 reservation 指标但无解释恶化 demand service
rolling 靠 fallback 修复 unsafe/invalid outcome
```

当前 evidence version 写为：

```text
rolling horizon reservation is not validated as a current evidence-supported control mechanism and remains pending_later_wave_validation/future work.
```

## 7. 输出

```text
gate_D2_report.md
gate_D2_decision.json
gate_D2_claim_revision_plan.md
```

JSON:

```json
{
  "gate": "D2",
  "decision": "retain|downgrade|remove",
  "claim_status": "current_evidence_supported|qualified_supported|pending_later_wave_validation|unsupported_or_contradicted",
  "allowed_next_stage": "Wave 9|Wave 8 fix|paper revision only",
  "demand_denominator_checked": true,
  "slot_consumption_conflict_checked": true,
  "per_context_recompute_checked": true,
  "plan_commitment_checked": true,
  "benefit_baseline_checked": true,
  "full_trace_join_checked": true,
  "hidden_fallback_detected": false,
  "rolling_vs_single_demand_delta": {},
  "rolling_vs_stale_ablation_delta": {},
  "rolling_vs_no_commitment_delta": {},
  "consistency_violation_count": 0,
  "duplicate_gap_consumption_count": 0,
  "plan_lock_violation_count": 0,
  "reservation_churn_rate": 0.0,
  "active_guidance_cancel_count": 0,
  "full_trace_join_rate": 1.0,
  "supported_claims": [],
  "downgraded_claims": [],
  "required_fixes": []
}
```
