# RPMI-CMV Python V0 Implementation README v2

## 0. 硬限定：本组 specs 能支撑什么，不能声称什么

本组 v2 文档支撑的是：

> **第 3.1 版论文的 deterministic Python V0 机制验证实验。**

它可以支撑验证以下核心链条：

1. raw gap count 不等于具体 ramp vehicle 可用的 merge slot inventory；
2. time-expanded slot `s=(i,j,k)` 与 pair-edge `e=(r,i,j,k)` 是 V0 的核心代码对象；
3. `P_R`、`RD`、`S_H^R`、`Z_H^R` 比 raw gap、density、speed 更能解释 future merge difficulty；
4. near-miss screening 能定位可由轻微 CAV 动作生产的 slot；
5. boundary-speed production 下，RCMV 能选择比 raw-gap/density/speed baseline 更合理的 action；
6. action-conditioned reservation 能暴露 stale reservation 消融；
7. no-fallback simulation 能诚实记录 invalid slot、unsafe match、collision risk、negative margin。

它**不能直接声称完整复现论文中的 RPMI-CMV**。若要声称完整 RPMI-CMV，需要继续完成并通过：

- Phase 5B：upstream lane-change production；
- Phase 6B：rolling-horizon reservation lifecycle；
- Phase 7：stochastic IDM / scenario-frequency estimator；
- 对应的 logging、readiness、ablation 和 do-not-proceed gates。

## 1. 文档优先级

代码实现 agent 必须按以下优先级解释文档：

```text
1. Phase_RPMI_V0_Code_Agent_Patch_Addendum_v2.md
2. Implementation_README_v2.md
3. Phase_0--Phase_7 *_v2.md
4. Phase_RPMI_V0_Implementation_Plan_Audit_v2.md
5. 原始 Phase 0--7 / 原始 Patch / 原始 Audit，仅作为历史背景
```

如果旧 phase 文档与 v2 或 Patch Addendum v2 冲突，**以 v2 为准**。

## 2. 项目定位

本项目是轻量科研实验装置，不是通用交通仿真平台。

V0 的目标不是让仿真“看起来合理”，而是让每个实验结论都可以追溯到：

- initial state；
- vehicle trajectory；
- candidate slot；
- pair-edge validity；
- invalid reason；
- matching decision；
- near-miss；
- candidate action；
- RCMV 分项；
- reservation lifecycle；
- realized failure event；
- config、seed、state hash。

## 3. 第一轮推荐实现顺序

不要机械按 Phase 0→7 把所有内容一次做完。第一轮应按以下 gates 逐层推进：

| Wave | 目标 | 对应文档 | 通过后才进入 |
|---|---|---|---|
| 0 | skeleton、config、logs、global dictionary | Phase 0 v2 | Wave 1 |
| 1 | no-fallback dynamics + nominal car-following | Phase 1 v2 | Wave 2 |
| 2 | slot/edge/P_R/RD/inventory draft | Phase 2 v2 | Wave 3A |
| 3A | diagnostic matching + toy S0 | Phase 3 v2 | Wave 4 |
| 4 | scenario generator + readiness | Phase 4 v2 | Wave 3B/5A |
| 3B | formal S0 batch rerun | Phase 3 + Phase 4 v2 | Wave 5A |
| 5A | boundary-speed RCMV + reservation lifecycle | Phase 5 v2 | Wave 6A |
| 6A | baselines/ablations/runner/analysis | Phase 6 v2 | optional 5B/6B/7 |
| 5B | lane-change production | Phase 5 v2 | optional paper extension |
| 6B | rolling horizon | Phase 6 v2 | optional paper extension |
| 7 | stochastic IDM V1 | Phase 7 v2 | robustness extension |

## 4. 最小可行实验闭环

第一轮最小闭环是：

```text
single_t0_micro_episode
  -> generate deterministic scenario
  -> readiness_check
  -> baseline no-action rollout
  -> generate slots and edges
  -> evaluate P_R/RD
  -> conflict-aware diagnostic matching
  -> compute S_H_R/Z_H_R
  -> classify near-miss
  -> generate boundary-speed actions
  -> action-conditioned rollout
  -> regenerate slots/edges/matching
  -> compute RCMV
  -> select action
  -> create reservations
  -> execute until evaluation horizon
  -> log outcome metrics and failure events
```

默认不启用 rolling horizon。

## 5. 严禁事项

V0 第一轮严禁：

- 先接 SUMO；
- 先做 MOBIL；
- 先做 RL；
- 先做 action bundle；
- 先做复杂 GUI；
- 先做工业级 plugin system；
- 让 hidden fallback controller 修复 collision/unsafe match；
- 用 realized future label 修正当前 decision；
- 用 proposed 的信息污染 baseline；
- 在 readiness fail 的场景上做 baseline/proposed comparison；
- 用 Hungarian 声称解决了 physical-gap/time-window conflict；
- 直接测试 `S_H^R <= raw_gap_count`；
- 跨候选 action 提前去重 CAV；
- 在 Phase 5A 未通过前声称完整 RPMI-CMV。

## 6. 统一术语

| 术语 | V0 含义 |
|---|---|
| no-fallback | 不做 post-hoc safety repair；仍然有 nominal car-following |
| nominal behavior | HDV deterministic IDM；未受控 CAV 使用 nominal ACC/IDM-like following |
| production command overlay | 被 action 控制的 CAV 在 action window 内叠加或替代 nominal acceleration |
| slot | `(front_id, rear_id, k, action_context)` |
| edge | `(ramp_id, front_id, rear_id, k, action_context)` |
| `P_R` | V0 deterministic sequential validity cascade，0/1 |
| `RD` | V0 recovery debt proxy，必须标注 components |
| `S_H^R` | matching-limited demand-weighted recoverable supply |
| `Z_H^R` | `max(D_H - S_H^R, 0)` |
| readiness | algorithm-independent mechanism eligibility check |
| single-decision episode | t0 只决策一次，然后执行到 evaluation horizon |

## 7. 交付标准

每一波实现必须同时交付：

1. 代码变更；
2. toy tests；
3. gate report；
4. standard logs；
5. 一个最小 trace replay summary；
6. 失败时的回查建议。

没有日志的“通过”不算通过；不能从 `vehicles_step -> edges -> matching -> action -> reservation -> event` 追溯的实验结果不进入论文分析。
