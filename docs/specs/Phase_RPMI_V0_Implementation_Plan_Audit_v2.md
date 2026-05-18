# RPMI-CMV Python V0 Implementation Plan Audit v2

## 0. 审阅结论

这组 v2 specs 的定位是正确的：

> 它们可以支撑第 3.1 版论文的 **deterministic Python V0 机制验证实验**；  
> 若要声称完整复现 RPMI-CMV，必须继续完成 lane-change production、stochastic IDM 鲁棒性和 rolling reservation 的后续 gates。

总体评分：

| 执行方式 | 判断 |
|---|---|
| 按 v2 + Patch Addendum v2 执行 | 8.2 / 10，可以开工实现 V0 |
| 直接按旧 Phase 0--7 执行 | 6.3 / 10，容易写出“能跑但验证错对象”的代码 |

v2 的主要任务不是推翻原计划，而是把旧文档中会导致理论偏离的示例和 gate 直接替换掉。

## 1. 主链条保持正确

v2 保留了原计划的核心优点：

1. Python V0 是 scientific apparatus，不是 traffic simulation platform；
2. 先 deterministic，再 stochastic；
3. 先 toy gates，再 scenario readiness，再 baseline comparison；
4. 以 time-expanded slot `s=(i,j,k)` 和 ramp-slot edge `e=(r,i,j,k)` 为核心对象；
5. `P_R` 使用 deterministic sequential validity cascade；
6. `S_H^R` 是 matching-limited demand-weighted supply，不是 raw gap count；
7. RCMV 必须通过 action-conditioned rollout 和 regenerated matching 计算；
8. no-fallback 记录 failure，不替算法修复错误。

## 2. v2 已修正的阻断问题

| 原问题 | v2 修正 |
|---|---|
| README 缺少硬限定 | README v2 明确只能声称 deterministic Python V0 机制验证 |
| 缺少全局 data dictionary | Phase 0 v2 新增 units、ID、state_hash、decision_context_id |
| no-fallback 容易被误解为没有 nominal following | Phase 1 v2 明确 no-fallback = no post-hoc safety repair |
| `step_vehicle` 先积分再 clip 速度 | Phase 1 v2 改为 effective acceleration |
| `S_H^R <= raw_gap_count` 量纲错误 | Phase 2/3 v2 改为 `0 <= S_H^R <= D_H` 等一致性 gate |
| deterministic `I_surv` 重复过滤 | Phase 2 v2 默认 `I_surv=1`，记录 `surv_mode` |
| Hungarian 被误当 conflict-aware | Phase 3 v2 默认 greedy conflict，MILP optional，Hungarian debug only |
| Phase 3 与 Phase 4 sampler 依赖循环 | Phase 3 v2 拆成 3A toy/minimal sampler 与 3B formal S0 |
| readiness 与 action generation 的 near-miss 逻辑可能分叉 | Phase 4/5 v2 共享 read-only near-miss classifier |
| Candidate action 跨候选 CAV 去重 | Phase 5 v2 删除 `used_primary_cavs` 逻辑 |
| boundary speed action profile 不可复现 | Phase 5 v2 固定 front/rear/front-rear profile 公式 |
| lane-change 与 boundary action 同阶段实现过重 | Phase 5 v2 拆为 5A boundary-speed、5B lane-change |
| RD 软硬惩罚重复计量 | Phase 5 v2 明确 `I_rec`、matching、`D_bar`、`C_bar` 分工 |
| reservation lifecycle 缺失 | Phase 5 v2 新增 planned/active/merged/expired/failed 状态 |
| rolling horizon 过早进入 | Phase 6 v2 默认 single-decision micro-episode |
| S0 future label policy 不固定 | Phase 3 v2 固定 `FIFO_no_production` 主 label policy |
| baseline 定义可执行性不足 | Phase 6 v2 给出 baseline 行为规则和禁用信息 |
| readiness 可能筛选 proposed 胜利样本 | Phase 4/6 v2 要求 algorithm-independent readiness |
| V1 conditional probability 分母为 0 未定义 | Phase 7 v2 要求记录 NaN 和 denominator count |

## 3. 仍需诚实标注的 V0 限制

v2 不是“完整论文系统”的最终实现。实现和论文写作中必须标注：

1. **V0 RD 是 proxy**  
   Phase 2 v2 默认 RD proxy 至少包含 braking、wave amplitude、recovery time。若未实现 affected vehicle count 和 outflow loss，论文图表应标注 `V0 RD proxy`。

2. **Phase 5A 只验证 boundary-speed production**  
   若 lane-change production 未进入 Phase 5B 并通过 gates，不能声称完整 RPMI-CMV action set 已复现。

3. **V0 默认 single-decision episode**  
   若 rolling reservation 未进入 Phase 6B，不能声称完成 rolling-horizon RPMI-CMV。

4. **V0 deterministic probability 不是 stochastic robustness**  
   若 Phase 7 未通过，不能声称完成 stochastic IDM 或 scenario-frequency robustness。

5. **scenario readiness 不是 cherry-picking**  
   readiness 只能使用 initial state、no-action rollout、diagnostic edges/matching、cheap near-miss availability，不能使用 proposed outcome。

## 4. 推荐开工结论

可以开工，但必须以以下顺序交给代码实现 agent：

```text
Patch Addendum v2 + README v2
  -> Phase 0 v2
  -> Phase 1 v2
  -> Phase 2 v2
  -> Phase 3 v2
  -> Phase 4 v2
  -> Phase 5 v2
  -> Phase 6 v2
  -> optional Phase 7 v2
```

最重要的工程原则是：

> 先让一个 single-decision deterministic micro-episode 在 trace 中完整闭环，再做复杂化。
