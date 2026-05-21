# Claim Staging and Gate Interpretation Guardrail v2.1 中文版

## 0. 用途

本文档用于防止把论文目标、实现计划和阶段性证据混在一起。

```text
3.1 论文稿 = 完整研究目标草稿
Wave specs = 把论文稿拆成可复现实验计划
Gate decision = 当前阶段 evidence package 对当前阶段 claim 的裁决
```

Codex 不得因为当前阶段尚未实现后续 Wave，就要求删除论文目标中的后续模块。

## 1. 论文稿、Wave、Gate 的关系

论文稿可以提出完整 RPMI-CMV 框架。Wave 逐步实现并生成 evidence package。Gate 只判断截至当前阶段，哪些 claim 可以写成已验证结论。

当前 Gate 未验证某一 claim，只表示该 claim 尚不能写成当前已验证结论；若该 claim 属于后续 Wave/Gate，则应标记为 `pending_later_wave_validation`。

## 2. 四类 claim status

```text
framework_proposal
  完整论文稿中的方法框架组成部分；可以保留为研究目标。

current_evidence_supported
  当前阶段 evidence package 已支持；可以写成当前阶段实验结论。

pending_later_wave_validation
  后续 Wave/Gate 的验证目标；可以写成计划、方法组成或待验证项。

unsupported_or_contradicted
  当前 evidence 不支持或反驳；必须修正实现、证据或当前阶段 claim。
```

## 3. 禁止误读

禁止把：

```text
当前 Gate 未验证
```

误读成：

```text
后续实验无效
论文稿必须删除该模块
```

也禁止把：

```text
后续 Wave planned validation
```

写成：

```text
当前 evidence 已验证
```

## 4. Gate D0 当前口径示例

Gate D0 只裁决 boundary-speed deterministic single-t0 V0 的 mechanism-level evidence。

D0 可以支持：

```text
raw-gap illusion diagnosis
recoverability-aware slot inventory
matching-consistent shortage
RCMV trace audit
single-t0 action/reservation/failure audit
```

D0 不能单独支持：

```text
lane-change production 已验证
rolling reservation 已验证
stochastic robustness 已验证
完整 RPMI-CMV 已验证
```

这些后续目标应标记为 `pending_later_wave_validation`。

## 5. 后续 Gate 升级规则

```text
Wave 7 / Gate D1
  验证 lane-change production 是否可升级为 current_evidence_supported 或 qualified_supported。

Wave 8 / Gate D2
  验证 rolling horizon reservation 是否可升级为 current_evidence_supported 或 qualified_supported。

Wave 9 / Gate D3
  验证 stochastic IDM robustness 是否可升级为 current_evidence_supported 或 qualified_supported。
```

若 D1/D2/D3 未能升级对应 claim，只表示当前 evidence version 不能把该 claim 写成已验证结果；它仍可作为 framework proposal、pending_later_wave_validation、limitation 或 future work 被记录。

最终论文实验章只写已经被对应 Gate 支持的 claim；未到对应 Gate 的内容只能写成 framework proposal、planned validation 或 limitation。
