# D2.5 论文-实验闭环包：先读这一页

## 0. 这包文件要解决什么

本包不是“投降式降级”。它的目标是把 RPMI-CMV 从现在的：

> rolling lifecycle / conflict blocking / failure trace 可审计

推进到：

> 在 target deterministic regimes 中，RPMI-CMV 能以可追踪、可解释的方式展示 low-disturbance recoverable slot selection 优势。

核心路线：

```text
RD / C_bar / RCMV
  -> selected action / selected gap
  -> reservation
  -> realized event
  -> hard brake / max decel / speed variance / wave / disturbance / TTC
```

如果这条链闭合，论文可以升级为 target-regime deterministic evidence。  
如果闭合失败，也能诚实判断：问题在 objective、RD/C_bar 定义、scenario、baseline、simulator，还是理论 claim。

---

## 1. 人怎么读

只想抓主线，读：

```text
00_README_HUMAN_FIRST.md
01_PROBLEM_GRADING_AND_MAIN_STORY.md
06_PAPER_CLAIM_DECISION_TREE.md
```

要指挥 Codex 执行，读：

```text
02_CODEX_MASTER_EXECUTION_SPEC.md
03_OBJECTIVE_METRIC_BASELINE_SPEC.md
04_TARGET_SCENARIO_CARDS.md
05_DECISIVE_EXPERIMENT_PROTOCOL.md
07_CODEX_PROMPT_SET_v2_闭环版.md
```

最推荐做法：

```text
1. 把 02_CODEX_MASTER_EXECUTION_SPEC.md 整份丢给 Codex。
2. 再把 07_CODEX_PROMPT_SET_v2_闭环版.md 的 Prompt 0 丢给 Codex。
3. 让 Codex 按 Prompt 1 -> Prompt 6 顺序执行。
4. 如果 Codex 卡住，只让它返回 stop condition 和缺失字段，不要让它自己编造成功。
```

---

## 2. Codex 先做什么

不要先大规模跑实验。先按这个顺序：

```text
A. Theory-to-metric audit
B. Missing metric register
C. Trace join schema
D. Principled Diagnostic Scenario Construction
E. Objective–Diagnostic Scenario Co-Design Loop
F. Evaluation Lock + Baseline Fairness Freeze
G. Locked Decisive Experiment
H. Paper Claim Decision
I. paper claim boundary
```

一句话：

```text
先用 diagnostic scenarios 调 objective；
再用 locked evaluation scenarios 做证据；
不要把调试场和最终考场混在一起。
```

---

## 3. 当前问题一眼分级

```text
P0：论文故事闭环没完成
    RD / C_bar / RCMV 还没连接到 realized low-disturbance outcome。

P1：目标函数需要重构
    权重、尺度、C_bar 定义、RD 定义、churn penalty 都可能要改。

P2：场景没有打中理论优势
    必须做 raw-gap trap、forced-accommodation、bad-action suppression。

P3：baseline 要围绕故事设计
    raw_largest_gap、forced_accommodation、without_RD、without_Cbar、without_theta 是核心。

P4：conflict-aware 先别抢主线
    它是机制补充，不是当前 low-disturbance story 的胜负点。
```

---

## 4. 论文主故事固定成一句话

英文建议：

> In deterministic target merging regimes, RPMI-CMV improves merge-slot quality by selecting recoverability-aware and disturbance-aware actions, reducing recovery debt and mainline disturbance compared with raw-gap and forced-accommodation baselines.

中文理解：

> 在确定性靶场合流场景中，RPMI-CMV 通过 recoverability-aware 和 disturbance-aware 的 action/gap 选择，相比 raw-gap 与 forced-accommodation baseline 降低恢复债与主线扰动。

先不要主张：

```text
universal optimality
stochastic robustness
multi-seed generalization
full conflict-aware rolling integer assignment 已验证
所有密度 / 所有 CAV penetration 都有效
```

---

## 5. 这次最重要的决定性实验

```text
D25-DECISIVE-RAW-GAP-FORCED-TRAP
```

要同时制造三件事：

```text
1. raw_largest_gap 会选几何最大但 recovery debt / disturbance 高的 Gap A。
2. forced_accommodation 可以强行服务需求，但 hard brake / max decel / wave / disturbance 高。
3. RPMI-CMV 应选几何较小但 recoverable、stable、low-disturbance 的 Gap B，或选择低成本 action-conditioned variant。
```

支持理论的结果：

```text
RPMI-CMV demand service 不差或 trade-off 可解释；
并且 RD_realized / hard_brake_count / max_deceleration / speed_variance_delta / wave_amplitude / mainline_disturbance_cost 更低；
同时 selected_action -> selected_edge/gap -> reservation -> realized_event -> metric change 可 join。
```

反驳或暂停理论强化的结果：

```text
RPMI-CMV 也选 Gap A；
RPMI-CMV 选 Gap B 但 realized disturbance 不低；
without_RD / without_Cbar / without_theta 和 full 选同一动作；
positive RCMV 不能 join 到 realized outcome；
forced baseline 无论怎样都不产生更高扰动，说明 simulator / metric sensitivity 先有问题。
```

---

## 6. 不要被信息淹没：当前只盯 4 个判断

```text
1. Full RPMI 是否和 raw_largest_gap 选了不同 gap / action？
2. Full RPMI 是否比 forced_accommodation 扰动低？
3. without_RD / without_Cbar / without_theta 是否改变选择或损害结果？
4. selected_action 是否能一路 join 到 realized disturbance / safety / demand outcome？
```

只要这 4 个问题回答清楚，论文-实验闭环就开始成立。
