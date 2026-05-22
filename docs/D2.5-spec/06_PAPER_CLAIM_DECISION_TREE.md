# 06 D2.5 结果下论文如何处理

## 0. 论文策略原则

不要再把当前状态理解为“只能降级”。正确策略是：

```text
先通过 D2.5 把论文故事闭合；
闭合成功就升级成 target-regime deterministic evidence；
闭合部分成功就 qualified；
闭合失败就诚实重构 objective / metric / scenario / theory。
```

---

# 1. 如果 D2.5 强支持理论

## 1.1 满足条件

```text
Raw-Large-Gap Trap 中：
  raw_largest_gap 选择几何大但 high-RD / high-disturbance gap；
  RPMI-CMV 选择 lower-disturbance recoverable gap/action；
  demand service 不差或 trade-off 可解释；
  realized RD / hard brake / wave / disturbance 更低；
  trace join 完整。

Forced-Accommodation 中：
  forced baseline merge success 相近；
  但 hard brake / max decel / wave / disturbance 更差。

Ablation 中：
  without_RD / without_Cbar / without_theta 至少一个破坏选择或结果。

Near-Miss / Bad-Action 中：
  RPMI-CMV 能生产 low-disturbance slot；
  或拒绝高扰动低收益 action。
```

## 1.2 论文可以写

英文：

> In deterministic target scenarios, RPMI-CMV's recoverability-aware, action-conditioned, cost-aware reservation avoids misleading raw geometric gaps and reduces recovery debt or mainline disturbance compared with raw-gap and forced-accommodation baselines.

中文：

> 在确定性靶场中，RPMI-CMV 能避免 raw geometric gap 的误导，并在与粗暴主线配合 baseline 服务水平相近时降低恢复债或主线扰动。

## 1.3 可以加强的 claim

```text
recoverability-aware selection 优于 raw-gap selection；
RCMV / cost-aware action selection 可抑制不必要主线扰动；
near-miss production 在 target regime 中有效；
action-conditioned reservation 在 stale / near-miss 场景中优于 stale reservation；
conservative conflict blocking 避免 duplicate physical gap consumption。
```

## 1.4 仍不能写

```text
stochastic robustness；
multi-seed generalization；
full conflict-aware rolling integer assignment 已验证；
SUMO / high-fidelity generalization；
universal optimality；
所有交通密度 / 所有 CAV penetration 下有效。
```

## 1.5 Wave 9 何时进入

D2.5 strong support 后进入 Wave 9。  
此时 Wave 9 的问题变成：

```text
已成立的 deterministic low-disturbance mechanism
在 stochastic IDM noise 下是否稳健？
```

---

# 2. 如果 D2.5 部分支持 / mixed

## 2.1 典型情况

```text
RPMI 在 raw-gap trap 中赢，但 forced baseline 差异小；
或 bad-action suppression 通过，但 near-miss production 不稳定；
或 disturbance 指标方向对，但 effect size 小；
或 service 略低，需要 trade-off 解释；
或 ablation 只证明 Cbar 有用，RD 不明显。
```

## 2.2 论文写法

英文：

> Targeted deterministic evidence provides qualified support for the proposed mechanism, while performance gains remain scenario-dependent.

中文：

> 定向确定性证据为该机制提供了有限支持，但性能收益具有场景依赖性。

## 2.3 Claim 调整

| 原强 claim | 改成 |
|---|---|
| reduces speed waves / hard braking | can reduce in designed target scenarios |
| robustly improves merge success | improves traceability and may improve service in selected target regimes |
| RCMV reliably selects low-disturbance actions | RCMV provides an auditable action-value criterion; realized benefits are scenario-dependent |
| full conflict-aware assignment validated | conservative physical-gap conflict blocking observed |

## 2.4 正例和边界写法

把通过的 scenario 写成 positive mechanism cards：

```text
Raw-Large-Gap Trap
Bad-Action Suppression
Near-Miss Production
```

把失败或风险写成 boundary cards：

```text
D2-ACTION-CONDITIONED-RECOMPUTE high churn
negative control
all-lanes congested
low CAV penetration
simulator-insensitive forced baseline
```

---

# 3. 如果 D2.5 不支持理论

## 3.1 不要立即判论文完了

按顺序判断：

```text
1. scenario 是否真的命中理论？
2. baseline 是否公平？
3. disturbance metrics 是否敏感？
4. RD / C_dist 是否进入 selection？
5. RCMV 是否 myopic？
6. simulator 是否表达不了速度波 / 急刹 / 扰动传播？
7. 理论定义是否需要重写？
```

## 3.2 最可能需要修的对象

### RD

如果：

```text
RD_pred 低，但 hard brake / wave / disturbance 高；
```

则：

```text
把 RD 拆成 predicted_RD 和 realized_RD；
重定义 RD components；
不要再把 RD 直接等同于 realized low disturbance。
```

### C_bar / C_dist

如果：

```text
C_bar 只是 action effort；
与 mainline disturbance 不同向；
```

则：

```text
改名为 action_effort_cost；
或升级为 C_dist，加入 induced braking / speed variance / wave / affected vehicles。
```

### J(a)

如果：

```text
Z_R 压倒一切，导致高扰动服务；
```

则：

```text
重新归一化；
提高 lambda_C / lambda_S；
加入 service-disturbance Pareto 或 hard safety constraints。
```

### RCMV / theta / hysteresis

如果：

```text
positive RCMV 导致 churn / unserved；
```

则：

```text
提高 theta；
加入 switching hysteresis；
加入 Q_churn；
区分 local RCMV 与 commitment-aware RCMV。
```

### conflict model

如果：

```text
conservative blocking 太保守；
```

则：

```text
论文明确 prototype limitation；
或实现 conflict window / small MILP；
但不要让它抢 low-disturbance 主线。
```

## 3.3 论文是否还值得继续

值得，但定位改成：

> A traceable recoverable perishable slot inventory framework with honest failure accounting and conservative conflict blocking.

这时不能主张 low-disturbance superiority，只能主张 framework / diagnostic mechanism。

---

# 4. 如果 D2.5 显示 simulator 太弱

## 4.1 判断标准

出现以下情况时，不要直接说理论失败：

```text
forced_accommodation 无法产生 hard brake / deceleration / wave 差异；
speed variance 对强 braking 不敏感；
follower response 没有传播；
mainline_disturbance_cost 近乎常数；
near-miss insertion 对 downstream metrics 无影响。
```

## 4.2 先加强 Python simulator

优先补：

```text
follower car-following response
acceleration / deceleration trace
jerk trace
speed variance before / after
local wave amplitude
downstream outflow proxy
min TTC / DRAC
multi-vehicle propagation window
```

## 4.3 何时进入 SUMO

只有在 Python simulator 已经能表达基本扰动，但 reviewer 仍可能质疑真实性时，再进入 SUMO / calibrated microscopic simulation。

不要用 SUMO 来替代 D2.5 的逻辑闭环。  
SUMO 是外部验证，不是理论-指标-实验闭环的第一步。

---

# 5. 论文表述红线

## 可以写

```text
The prototype supports auditable rolling reservation lifecycle.
Stale / expired reservations and demand return can be traced.
Conservative physical-gap conflict blocking is observed.
Failures are not hidden by fallback repair in the reviewed traces.
In deterministic target scenarios, RPMI-CMV can reduce recovery debt or mainline disturbance compared with raw-gap / forced baselines, if D2.5 supports it.
```

## 不要写

```text
RPMI-CMV universally reduces traffic waves.
RPMI-CMV robustly improves merge success.
Full conflict-aware rolling integer assignment is validated.
Multi-seed diversity is demonstrated.
Stochastic robustness is demonstrated.
failed_reservation_rate=0.0 means demand success.
```

---

# 6. 最终摘要句模板

## Strong support

> D2.5 closes the main theory-evidence loop in deterministic target regimes: RPMI-CMV selects recoverable, lower-disturbance slots/actions and reduces realized recovery/disturbance metrics compared with raw-gap and forced-accommodation baselines.

## Mixed

> D2.5 provides qualified deterministic support: the mechanism works in selected target scenarios, but performance benefits depend on scenario structure and metric sensitivity.

## No support

> D2.5 does not support the current low-disturbance superiority claim. The paper should be repositioned as a traceable recoverable slot inventory framework unless RD / C_dist / RCMV and scenario design are revised.

## Simulator weak

> D2.5 is inconclusive because the current simulator cannot express the disturbance mechanisms required to test the theory. The next step is simulator metric sensitivity hardening, not stochastic robustness.
