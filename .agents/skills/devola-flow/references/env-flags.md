---
id: "agent/references/env-flags"
version: "9.1.5"
purpose: >
  Canonical inventory of every `DEVOLAFLOW_*` environment variable consumed
  by the runtime, the test fixtures, and the gate primitives. Pairs with
  Workflow Rule W-20 (env-flag reuse vs new-flag policy) — every L3 Task
  Agent that proposes a new env-flag MUST consult this reference FIRST
  and prefer reuse of an existing flag whenever the data shape allows.
  v9.0.0 PV-06 (v8.5.1) moved the 5 v8.0.0 gate-primitive flags from §4
  (forward-declared) to §2 (active runtime flags) as Theme T5 default-on
  flip closure; the 6th forward-declared flag (`LEGIBILITY_CHECK`) and the
  `CYCLE_DETECTOR` flag remain pre-documented for a future cycle.
  v9.1.5 PV-05 wired `DEVOLAFLOW_AGENTS_MD_SLICE` (telegraphed v9.0.0
  PV-07; runtime read added v9.1.5 PV-05 alongside the YAML default flip)
  as the operator-visible escape hatch for the per-task-type AGENTS.md
  slicing default-ON.
triggers:
  - "introducing a new feature flag"
  - "adding a runtime env-var"
  - "auditing default-off / R5 strict surfaces"
  - "wiring a v8.0.0 gate primitive (PV-06 closed)"
  - "debugging a feature that should be off-by-default"
  - "investigating a `lookup_case is None` cache miss"
  - "opting OUT of a default-on gate primitive on STRICT/AUDIT"
tier: 2
token_estimate: 4500
dependencies:
  - "agent/SKILL.md"
  - "agent/references/shell-proxy.md"
  - "agent/references/decomposition-gate.md"
  - "agent/references/plan-mode-enforcement.md"
last_updated: "2026-04-24"
---

# Environment Flag Reference

> **Tier-2 reference** — load when the dispatcher is about to author a
> new env-flag, audit an existing default-off surface, debug a feature
> that operators expect to be inactive, or prepare the v9.0.0 PV-06 flip
> of the 5 v8.0.0 gate primitives. Pairs with **Workflow Rule W-20**
> (env-flag reuse vs new-flag policy): every NEW env-flag proposal MUST
> first consult §1 to confirm no existing flag covers the same surface.

## 1. Why this reference exists

Two distinct hygiene gaps motivate this reference (the **13th SF-4
canonical**, added in v8.5.0 PV-05):

1. **Operator surface bloat** — without a single source-of-truth, every
   PV that adds a new feature is tempted to author its own env-flag
   ("the PV-04 command-mapping layer reuses `DEVOLAFLOW_RTK_PROXY`
   precisely because the PV-04 design doc consulted PV-02's wording
   and chose REUSE"). Without this reference, the next PV will lack
   that lookup.
2. **W-20 enforceability** — Rule W-20 (added in v8.5.0 PV-05) states
   *"new behaviours should reuse existing env-flags rather than
   introduce new ones unless behaviorally orthogonal."* Enforcement
   requires the reviewer to **see** the inventory; without this
   reference, W-20 is normative-only, not actionable.

## 2. Active runtime flags (wired in `src/devolaflow/`)

These flags are read by production code paths. Tests in
`tests/test_shell_proxy*.py`, `tests/test_memory_router.py`, and
`tests/test_task_adaptive_selector.py` codify the parsing contract
(strict `"1"` matching; rejects `"true"`, `"yes"`, `"on"`, `"01"`, `""`).

### 2.1 `DEVOLAFLOW_PLAN_MODE` — plan-mode auto-detect

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/task_adaptive_selector.py::_PLAN_MODE_ENV` |
| **Introduced** | v6.1.5 |
| **Default** | unset (= disabled) |
| **Activation** | env value in `{"1", "true", "yes", "on"}` (loose match) OR `select_context(plan_mode=True)` keyword OR `.devolaflow_plan_mode` filesystem marker |
| **Effect** | `apply_plan_mode_overrides()` escalates `agent_hierarchy`, `decomposition_gate`, `rationalization_prevention` priorities to `critical`; upgrades `model_hint` to `quality`; sets `compression_intensity` to `minimal` |
| **Composition** | Plan-mode applies BEFORE round-escalation (v6.0.3 round-based escalation runs on top) |
| **R5 strict?** | NO — historical loose-parsing matches Cursor SwitchMode contract; tests in `tests/test_task_adaptive_selector.py::TestPlanModeDetect` codify the loose semantics (e.g. `"garbage"` → false, `"1"` / `"true"` / `"yes"` / `"on"` → true) |
| **Reference** | `references/plan-mode-enforcement.md` §1 (When to Load) + §2 (Detection table) |

### 2.2 `DEVOLAFLOW_RTK_PROXY` — RTK rewrite + command-mapping activation

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/shell_proxy/proxy.py::_ENV_FLAG` (also consumed by `src/devolaflow/shell_proxy/commands.py::is_command_mapping_active`) |
| **Introduced** | v8.3.2 PV-02; REUSED by v8.3.4 PV-04 (NO new flag added) |
| **Default** | unset (= disabled) |
| **Activation** | env value EXACTLY `"1"` (R5 strict — rejects `"true"`, `"yes"`, `"on"`, `"01"`, `""`) AND `rtk` binary on PATH AND `rtk gain` probe succeeds (collision-warning per RTK INSTALL.md) |
| **Effect (Tier 1)** | `pre_shell_call` rewrites `pytest`, `ruff check`, `git diff`, `git log`, `git status` via `rtk rewrite <cmd>`; per RTK README ~80% token reduction on captured stdout |
| **Effect (PV-04 layer)** | `apply_local_recipe` consults `.local/memory/commands/<repo>/<cmd>.yaml` BEFORE returning the proxied output; precedence: local recipe → RTK rewrite → passthrough |
| **R5 strict?** | YES — `is_proxy_enabled()` is a pure env-var read with NO `shutil.which` lookup, NO subprocess spawn, NO Path.read_text when unset. Codified in `tests/test_shell_proxy_disabled_is_noop.py` + `tests/test_shell_proxy_commands.py::TestLoadR5StrictOff` (`monkeypatch.setattr(Path, "read_text", watcher)` proves zero IO when off). |
| **Reference** | `references/shell-proxy.md` §3.1 (env-flag table) + §4 (R5 strict zero-overhead breakdown) |

### 2.3 `DEVOLAFLOW_RTK_PROXY_TIER2` — Tier 2 commands opt-in

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/shell_proxy/proxy.py::_TIER2_ENV_FLAG` |
| **Introduced** | v8.3.2 PV-02 |
| **Default** | unset (= Tier 1 only) |
| **Activation** | env value EXACTLY `"1"` AND #2.2 also active |
| **Effect** | Adds `git add`, `git commit`, `git show`, `cargo test`, `npm test`, `make` to the proxy whitelist (per `shell_proxy/registry.py::WHITELIST` Tier 2 block) |
| **R5 strict?** | YES — has no effect unless #2.2 is set; the Tier 2 enablement is captured in `ShellProxyConfig` snapshot at activation time |
| **Why secondary?** | Tier 1 commands are read-only / safe; Tier 2 commands have side-effects (git mutations, build invocations). Operators opt in to Tier 2 when they have separate audit logging in place. |

### 2.4 `DEVOLAFLOW_MEMORY_ROUTER` — planning fast-path

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/memory_router/router.py::ENV_FLAG` |
| **Introduced** | v8.3.3 PV-03 |
| **Default** | unset (= disabled) |
| **Activation** | env value EXACTLY `"1"` AND `.local/memory/cases/index.yaml` exists AND yields a matching case |
| **Effect** | `lookup_case(intent, env)` consults the cases index BEFORE the L0/L1 dispatcher re-derives workflow + stage decomposition from SKILL.md; cache-hit short-circuits ~3K tokens of planning context per matched route (~93% reduction per the v8.3.3 PV-03 retrospective) |
| **Cache-miss path** | Returns `None` in O(1); caller falls through to the existing planner per cycle plan §6 R3 "cache-miss is the safe path" |
| **R5 strict?** | YES — codified in `tests/test_memory_router.py::TestLookupCaseR5StrictOff` with `monkeypatch.setattr(Path, "read_text", watcher)` proving zero IO when off; the EvoBench scenario `memory_router_fastpath.yaml` codifies the dispatch-surface invariant (composite floor 90, actual 99.73 at v8.3.3 cut) |
| **Reference** | `references/shell-proxy.md` §5 (memory-router fast-path) + §7 (R5 strict zero-overhead breakdown) |

### 2.5 `DEVOLAFLOW_AUTO_INSTALL` — plugin auto-install opt-out

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/plugins/installer.py` |
| **Introduced** | v8.3.0 PV-01 (earlier baseline preserved) |
| **Default** | `1` (auto-install ACTIVE) |
| **Opt-out** | env value `"0"` (any truthy other-than-1 also disables) |
| **Effect when enabled** | `installer.py::ensure_plugin('rtk' \| 'nines' \| 'ui-pro')` may invoke `curl` / `cargo install` / `npm install` / `pip install -e` from the workflow's `precondition.config.ensure_plugins` stage |
| **Why default-on?** | The v8.3.0 PV-01 contract trades a one-time ~5-30s install latency for full workflow capability — operators who have offline / pinned-version requirements opt out by setting `0` |
| **R5 strict?** | N/A — this flag governs an explicit subprocess (the install itself); R5 zero-overhead does not apply |
| **Reference** | `CHANGELOG.md` §[v8.3.0-pv01] for the PV-01 contract; `runtime-plugins.yaml` for the plugin registry |

### 2.6 `DEVOLAFLOW_TOKEN_BUDGET_BREAKER` — Theme T5 #1 default-on (STRICT/AUDIT)

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/gate/budget.py::ENV_FLAG` (helper: `is_token_budget_breaker_active`) |
| **Introduced** | v8.0.0 P-03 (forward-declared); promoted v9.0.0 PV-06 (v8.5.1) — moved from §4 to §2 |
| **Default** | unset → respect profile flag (STRICT/AUDIT default ON, STANDARD/RELAXED default OFF) |
| **Activation** | env value EXACTLY `"1"` → force ON; env value EXACTLY `"0"` → force OFF; otherwise fall back to `profile.budget_breaker_enabled` |
| **Effect when active** | Downstream orchestrators auto-instantiate :class:`devolaflow.gate.budget.TokenBudgetBreaker` and pass it to :func:`devolaflow.gate.scorer.evaluate_gate` |
| **R5 strict?** | YES — pure env-var read with NO file IO, NO subprocess, NO `shutil.which` lookup; codified in `tests/test_pv06_primitive_flip.py::test_loose_env_values_fall_back_to_profile_flag` |
| **Opt-out path (post-flip)** | `export DEVOLAFLOW_TOKEN_BUDGET_BREAKER=0` — preserves v8.5.0 pre-flip behaviour byte-identically |
| **Reference** | `references/decomposition-gate.md` §11 row 1; `benchmarks/devolaflow_context/scenarios/token_budget_disabled.yaml` (composite ≥ 90 floor when opted out) |

### 2.7 `DEVOLAFLOW_VERIFICATION_LADDER` — Theme T5 #2 default-on (STRICT/AUDIT)

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/gate/scorer.py::VERIFICATION_LADDER_ENV_FLAG` (helper: `is_verification_ladder_active`) |
| **Introduced** | v8.0.0 P-05 as `profile.ladder_enabled`; flag added v9.0.0 PV-06 (v8.5.1) |
| **Default** | unset → respect `profile.ladder_enabled` (STRICT/AUDIT default ON; STANDARD/RELAXED default OFF) |
| **Activation** | env value EXACTLY `"1"` → force ON; EXACTLY `"0"` → force OFF; otherwise profile flag wins |
| **Effect when active** | `evaluate_ladder` runs the full 6-rung short-circuit ladder; opt-out short-circuits to `evaluate_gate` byte-identically |
| **R5 strict?** | YES — pure env-var read; no IO when opted out (the ladder simply delegates to the existing `evaluate_gate` codepath) |
| **Opt-out path (post-flip)** | `export DEVOLAFLOW_VERIFICATION_LADDER=0` |
| **Reference** | `benchmarks/devolaflow_context/scenarios/verification_ladder_disabled.yaml` |

### 2.8 `DEVOLAFLOW_GATE_RATCHET` — Theme T5 #3 default-on (STRICT/AUDIT)

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/gate/ratchet.py::ENV_FLAG` (helper: `is_gate_ratchet_active`) |
| **Introduced** | v8.0.0 P-07 (forward-declared); promoted v9.0.0 PV-06 (v8.5.1) — moved from §4 to §2 |
| **Default** | unset → respect `profile.ratchet_enabled` (STRICT/AUDIT default ON) |
| **Activation** | env value EXACTLY `"1"` → force ON; EXACTLY `"0"` → force OFF; otherwise profile flag wins |
| **Effect when active** | Downstream orchestrators instantiate :class:`devolaflow.gate.ratchet.MonotonicRatchet` and feed per-round scores to it (4-verdict ADVANCE/TOLERATE/ROLLBACK/ESCALATE machinery) |
| **R5 strict?** | YES |
| **Opt-out path (post-flip)** | `export DEVOLAFLOW_GATE_RATCHET=0` |
| **Reference** | `benchmarks/devolaflow_context/scenarios/ratchet_disabled.yaml` |

### 2.9 `DEVOLAFLOW_COMPLEXITY_DETECTOR` — Theme T5 #4 default-on (STRICT/AUDIT)

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/gate/complexity_detector.py::ENV_FLAG` (helper: `is_complexity_detector_active`) |
| **Introduced** | v8.0.0 P-09 (forward-declared); promoted v9.0.0 PV-06 (v8.5.1) — moved from §4 to §2 |
| **Default** | unset → respect `profile.complexity_detector_enabled` (STRICT/AUDIT default ON) |
| **Activation** | env value EXACTLY `"1"` → force ON; EXACTLY `"0"` → force OFF; otherwise profile flag wins |
| **Effect when active** | Downstream orchestrators instantiate :class:`devolaflow.gate.complexity_detector.ComplexityDetector` and pair it with `profile.complexity_weight=0.10` so the gate composite reflects an overcomplexity penalty |
| **R5 strict?** | YES — pure env-var read; the actual NineS subprocess + MOCK fallback only run when the gate scorer is invoked with `complexity_detector` set |
| **Opt-out path (post-flip)** | `export DEVOLAFLOW_COMPLEXITY_DETECTOR=0` |
| **Reference** | `benchmarks/devolaflow_context/scenarios/complexity_detector_disabled.yaml` |

### 2.10 `DEVOLAFLOW_AC_GEN` — Theme T5 #5 default-on (STRICT/AUDIT)

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/ac_generator.py::ENV_FLAG` (helper: `is_ac_generator_active`) |
| **Introduced** | v8.0.0 P-10 (forward-declared); promoted v9.0.0 PV-06 (v8.5.1) — moved from §4 to §2 |
| **Default** | unset → respect `profile.ac_generator_enabled` (STRICT/AUDIT default ON) |
| **Activation** | env value EXACTLY `"1"` → force ON; EXACTLY `"0"` → force OFF; otherwise profile flag wins |
| **Effect when active** | The :class:`devolaflow.ac_generator.ACGenerator` synthesises structured `acceptance_criteria_v2` from the dispatch task description (11 deterministic patterns + 3-dim quality scoring); the legacy `acceptance_criteria: list[str]` alias remains the contract path so opt-out preserves v7.x byte-stable dispatch shape per R5 |
| **R5 strict?** | YES |
| **Opt-out path (post-flip)** | `export DEVOLAFLOW_AC_GEN=0` |
| **Reference** | `benchmarks/devolaflow_context/scenarios/ac_generator_disabled.yaml` |

### 2.11 `DEVOLAFLOW_AGENTS_MD_SLICE` — v9.1.5 PV-05 default-on (per-task-type AGENTS.md slicing)

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/task_adaptive_selector.py::_AGENTS_MD_SLICE_ENV_FLAG` (helper: `_agents_md_slice_env_override`) |
| **Introduced** | telegraphed v9.0.0 PV-07 ADR-007 D3; runtime read landed v9.1.5 PV-05 alongside the YAML default flip |
| **Default** | unset → respect `meta.agents_md_slice.enabled` in `workflow-system/agent/context_profiles.yaml` (v9.1.5 canonical default: `true`) |
| **Activation** | env value EXACTLY `"1"` → force opt-IN; EXACTLY `"0"` → force opt-OUT; otherwise YAML default wins |
| **Effect when active** | `select_agents_md_slice(task_type)` filters the compiled AGENTS.md by per-task-type rule slice (Soul / Architecture / Conventions / Workflow / Style layer-prefix mapping in `meta.agents_md_slice.profiles`); typically reduces L3 dispatch cache prefix by 15-70% |
| **Effect when opted out** | Returns AGENTS.md byte-identical to the v9.1.4 unsliced surface — preserves the cache prefix every L3 dispatcher keys on |
| **R5 strict?** | YES — pure dict.get with no IO; `references/env-flags.md` §6 conjunction contract pins literal-only matching (`"true"` / `"yes"` / `"on"` / `" 1 "` / `"01"` / `"0.0"` all fall through to YAML default) |
| **Why default-on?** | The v9.0.0 MAJOR cycle telegraphed the slice in PV-07 ADR-007 D3 but kept it OFF until operators had time to adopt; v9.1.5 PV-05 flips the canonical default ON now that two cycles of ADR review + retrospective coverage have closed the migration gap. The opt-out env flag preserves byte-stable behaviour for operators who still need the v9.1.4 surface. |
| **Opt-out path** | `export DEVOLAFLOW_AGENTS_MD_SLICE=0` |
| **Reference** | `tests/test_pv07_agents_md_slice.py::test_agents_md_slice_env_flag_0_opts_out`; `workflow-system/agent/context_profiles.yaml#meta.agents_md_slice` |

> **Retirement note (v12.0.0 PV-03 D-2)**: the v9.3.0 PV-06 entry that
> formerly occupied §2.12 (the simple-task auto-shortcut env flag,
> companion to the retired `shortcut_verdict` / `shortcut_from_env`
> surface in `src/devolaflow/skills/change_activation.py`) was
> RETIRED ENTIRELY at v12.0.0 PV-03 per the v11.1.0 retrospective §3
> D-2 telegraph. Env-flag count goes 8 → 7 (W-20 reuse-first
> preserved; no new flag introduced). Operators who relied on the
> v11.x shortcut path migrate to `activation_verdict(complexity, ...,
> force_no_change=True)` per the v12.0.0 CHANGELOG `## [12.0.0]`
> migration table. Subsequent §2.13/§2.14/§2.15 sub-sections were
> renumbered to §2.12/§2.13/§2.14 to close the gap.

### 2.12 `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` — v9.4.0 PV-02 dispatcher pre-flight auto-install (SPLIT v10.8.0 D-C-3)

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/lifecycle/pre_plugin_invocation.py::ENV_FLAG` (alias helper: `is_auto_install_active`); the v10.8.0 D-C-3 split handlers `pre_plugin_invocation_install` (event slot #11) + `pre_plugin_invocation_upgrade` (event slot #12) REUSE the same env flag during the 1-cycle alias window |
| **Introduced** | v9.4.0 PV-02 (closes D-P-1 + D-P-3 from `.local/research/v9.4.0_gap_analysis.md` §3.1); **SPLIT in v10.8.0 D-C-3** (closes D-C-3 from `.local/research/v11.0.0_patches/D-C-3.md`) — 2 new events appended at `DEFAULT_EVENTS` positions 11 + 12 (A-2.2 append-only); alias at position 9 preserved BYTE-IDENTICALLY for 1 cycle |
| **Default** | unset (= disabled — dispatcher does NOT pre-flight install OR upgrade plugins) |
| **Activation** | env value EXACTLY `"1"` (R5 strict — rejects `"true"`, `"yes"`, `"on"`, `"01"`, `"1\n"`, `""`); pure env-var read with no IO + no `shutil.which` lookup + no Path.read_text |
| **Effect when active (v10.8.0+)** | Three lifecycle events fire on every dispatch with populated `plugin_ids` / `plugin_id` / `workflow` payload: (1) `pre_plugin_invocation` (event slot #9) — the v10.8.0 ALIAS, body delegates to the two new handlers in sequence; emits PPI001 + PPI003. (2) `pre_plugin_invocation_install` (event slot #11) — install-only; emits PPI001 for `ensure_plugin` failures. (3) `pre_plugin_invocation_upgrade` (event slot #12) — upgrade-only; emits PPI003 for `upgrade_plugin` failures on stale plugins. The alias path fires AFTER the v9.1.3 PV-03 `pre_handoff` slot in `feedback.py::_emit_dispatch`. The v10.2.1 PV-02 D-P-2 daily-upgrade integration now lives in the dedicated upgrade handler. |
| **Effect when opted out** | All 3 hooks are zero-IO no-ops (lazy-import the installer module ONLY when active); dispatch behaviour is byte-identical to v9.3.x AND to v10.7.x for every input (the AC-6 byte-stable invariant from `v9.4.0_gap_analysis.md` §6 + the v10.8.0 D-C-3 §2 G-7 backward-compat contract) |
| **Why a NEW flag (W-20 §3 justification)** | Behavioural orthogonality test: AUTO_INSTALL_PLUGINS activates a different runtime surface (the dispatcher's pre-flight plugin install hook) than every existing flag. `DEVOLAFLOW_AUTO_INSTALL` (§2.5, default-ON, opt-OUT) controls whether the install primitive performs the install at all — different surface (it controls `ensure_plugin`'s behaviour WHEN called, not WHETHER it gets called). `DEVOLAFLOW_AGENT_WORKSPACE` (workspace lifecycle) is conceptually orthogonal — an operator may want plugin pre-flight without workspace activation. The two flags compose meaningfully: `AUTO_INSTALL_PLUGINS=1 + AUTO_INSTALL=0` = audit-mode pre-flight where the hook fires + ensure_plugin reports the version mismatch loudly without auto-installing. No existing flag could be REUSED without conflating two distinct activation surfaces. **v10.8.0 D-C-3 SPLIT**: the install + upgrade handlers REUSE this flag during the 1-cycle alias window per W-20 reuse-first (same activation surface). A future `DEVOLAFLOW_AUTO_UPGRADE_PLUGINS` flag is TELEGRAPHED for v12.0.0+ SI-1 re-evaluation (per D-C-3 §2 step 4 + §9 R3 mitigation) when the split has 1+ cycle of operator-feedback and the orthogonality argument matures. |
| **R5 strict?** | YES — `is_auto_install_active` (alias + install handler) and `is_auto_upgrade_active` (upgrade handler) are pure ``os.environ.get`` comparisons with no IO + no subprocess. Every hook body lazy-imports `devolaflow.plugins.installer` ONLY when active; codified by `tests/test_pre_plugin_invocation.py::TestDisabledIsNoopByteIdentical::test_disabled_is_noop_byte_identical` + `tests/test_pre_plugin_invocation_split.py::TestAliasByteIdentical::test_alias_byte_identical_when_disabled`. |
| **Lifecycle telegraph** | The v9.4.0 cycle shipped the flag as opt-in with default-OFF; v10.8.0 D-C-3 preserved default-OFF across the split. A future cycle MAY consider promotion to default-ON after one cycle of operator-adoption observation, mirroring the v9.0.0 PV-06 → v9.1.5 PV-05 default-flip pattern. **Alias deprecation telegraph (v10.8.0 → v12.0.0+)**: the `pre_plugin_invocation` event at position 9 remains as a BYTE-IDENTICAL alias through v11.x; operators registering extra handlers on this event should migrate to `pre_plugin_invocation_install` / `pre_plugin_invocation_upgrade` before v12.0.0 SI-1 re-evaluation. The 1-cycle alias cadence mirrors the W-21 Soul-set governance telegraph pattern. |
| **Opt-out path (when default-ON in a future cycle)** | TELEGRAPHED — operators will set `export DEVOLAFLOW_AUTO_INSTALL_PLUGINS=0` to preserve v9.4.x dispatch behaviour byte-identically |
| **Reference** | `tests/test_pre_plugin_invocation.py` (alias path coverage); `tests/test_pre_plugin_invocation_split.py` (v10.8.0 D-C-3 split contract: install-only / upgrade-only / alias-byte-identical / disjoint-violations / deprecation-telegraph); `src/devolaflow/lifecycle/pre_plugin_invocation.py::pre_plugin_invocation` (alias entry point); `src/devolaflow/lifecycle/pre_plugin_invocation_install.py::pre_plugin_invocation_install` (install handler at event slot #11); `src/devolaflow/lifecycle/pre_plugin_invocation_upgrade.py::pre_plugin_invocation_upgrade` (upgrade handler at event slot #12); `.local/research/v9.4.0_gap_analysis.md` §3.1 D-P-3 + `.local/research/v11.0.0_patches/D-C-3.md` |

### 2.13 `DEVOLAFLOW_SI_CHIP_DEEP` — v9.5.0 PV-04 Si-Chip DEEP integration (post-skill-edit dogfood gate)

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/lifecycle/post_skill_edit.py::ENV_FLAG` (helper: `is_deep_integration_active`) |
| **Introduced** | v9.5.0 PV-04 (closes D-S-4 + D-S-5 from `.local/research/v9.5.0_gap_analysis.md` §3.1; user Q2=B DEEP integration signoff) |
| **Default** | unset (= disabled — `post_skill_edit` hook is a zero-IO no-op) |
| **Activation** | env value EXACTLY `"1"` (R5 strict — rejects `"true"`, `"yes"`, `"on"`, `"01"`, `"1\n"`, `""`); pure env-var read with no IO + no `shutil.which` lookup + no Path.read_text |
| **Effect when active** | `post_skill_edit` lifecycle hook (event slot #10 in `DEFAULT_EVENTS`, A-2.2 append-only at position 10) auto-runs the Si-Chip iteration_delta gate (`devolaflow.si_chip_bridge.run_dogfood_cycle`) after any commit touching `workflow-system/agent/**`. APPLY verdict → no-op (continue). DEFER verdict → write a deferred-changes feedback doc to `.local/feedbacks/sichip_deferred_<timestamp>.md` per the v9.5.0 user requirement ("if not, summarise into a feedback document"). The hook fires AFTER the v9.4.0 PV-02 `pre_plugin_invocation` slot at DEFAULT_EVENTS position 10. |
| **Effect when opted out** | The `post_skill_edit` hook is a zero-IO no-op (lazy-imports the `si_chip_bridge` package ONLY when active); dispatch behaviour is byte-identical to v9.4.x for every input (the AC-7 byte-stable invariant from `v9.5.0_gap_analysis.md` §6) |
| **Why a NEW flag (W-20 §3 justification)** | Behavioural orthogonality test: SI_CHIP_DEEP activates a different runtime surface (the post-skill-edit dogfood gate) than every existing flag. (1) `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` (§2.12, opt-IN) controls dispatcher PRE-flight plugin install — different surface (PRE vs POST). (2) `DEVOLAFLOW_AUTO_INSTALL` (§2.5, opt-OUT) controls the install primitive's WHEN-called behaviour — different surface (install primitive vs hook). (3) `DEVOLAFLOW_AGENT_WORKSPACE` (workspace lifecycle) is conceptually orthogonal — workspace folder management has nothing to do with skill self-evaluation cadence. The flags compose meaningfully: `SI_CHIP_DEEP=1 + AUTO_INSTALL_PLUGINS=1` = full pipeline (auto-install Si-Chip on dispatch + auto-evaluate skills on commit); `SI_CHIP_DEEP=1` alone = auto-evaluate only (operators who pre-install Si-Chip manually). No existing flag could be REUSED without conflating distinct activation surfaces. |
| **R5 strict?** | YES — `is_deep_integration_active` is a pure ``os.environ.get`` comparison with no IO + no subprocess. The hook body lazy-imports `devolaflow.si_chip_bridge` ONLY when active; codified by `tests/test_post_skill_edit_hook.py::TestDisabledIsNoop::test_disabled_is_noop_byte_identical`. |
| **Lifecycle telegraph** | The v9.5.0 cycle ships the flag as opt-in with default-OFF. A future cycle MAY consider promotion to default-ON after one cycle of operator-adoption observation, mirroring the v9.0.0 PV-06 → v9.1.5 PV-05 default-flip pattern. NOT yet committed — the v9.5.0 retrospective will assess the operator-feedback signal. |
| **Opt-out path (when default-ON in a future cycle)** | TELEGRAPHED — operators will set `export DEVOLAFLOW_SI_CHIP_DEEP=0` to preserve v9.5.x dispatch behaviour byte-identically |
| **Reference** | `tests/test_post_skill_edit_hook.py` (NEW tests pin the verdict matrix); `src/devolaflow/lifecycle/post_skill_edit.py::post_skill_edit` (the public entry point); `.local/research/v9.5.0_gap_analysis.md` §3.1 D-S-4 + §3.2 D-S-5; canonical Si-Chip URL: `https://github.com/YoRHa-Agents/Si-Chip` |

### 2.14 `DEVOLAFLOW_WARMUP` — v9.7.0 PV-04 selector LRU cache pre-warmup (opt-in)

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/task_adaptive_selector.py::WARMUP_ENV_FLAG` (helper: `warmup_selector_cache`) |
| **Introduced** | v9.7.0 PV-04 (closes D-N-2 from `.local/research/v9.7.0_gap_analysis.md` §1.3 — selector LRU cache cold on session start) |
| **Default** | unset (= disabled — `warmup_selector_cache()` is a strict no-op returning `0`) |
| **Activation** | env value EXACTLY `"1"` (R5 strict — rejects `"true"`, `"yes"`, `"on"`, `"01"`, `"1\n"`, `" 1 "`, `""`); pure env-var read against the literal `WARMUP_TRUTHY_VALUE` constant |
| **Effect when active** | A session-start call to `warmup_selector_cache()` pre-populates the v9.3.0 PV-03 LRU caches (`_load_profiles_cached` / `_load_skill_md_cached`) by iterating the cartesian product of `WARMUP_TASK_TYPES` (top-5: `implement`, `research`, `design`, `hotfix`, `review`) × `WARMUP_ROUND_NUMS` ((1, 2, 3)) — 15 cache entries total. Pre-warmup, the first session dispatch pays ~80 ms cold-cache miss for `load_profiles`; post-warmup, every dispatch hits the cache in O(1). Net: an N-dispatch session amortises the warmup over N calls; for N ≥ 4, warmup is a strict win (saves ~80 ms × (N-1) ≈ ~240 ms on a 4-dispatch session, costs ~80-300 ms upfront on the first run, ~5 ms on subsequent invocations within the same process). |
| **Effect when opted out** | `warmup_selector_cache()` returns `0` immediately without spending IO or CPU; dispatch behaviour is byte-identical to v9.6.x (the AC byte-stable invariant from `v9.7.0_gap_analysis.md` §4.5) |
| **Why a NEW flag (W-20 §3 justification)** | Behavioural orthogonality test: WARMUP activates a different runtime surface (selector LRU cache pre-population on session start) than every existing flag. (1) `DEVOLAFLOW_AGENT_WORKSPACE` (workspace folder lifecycle) is conceptually orthogonal — workspace activation has nothing to do with selector cache state. (2) `DEVOLAFLOW_RTK_PROXY` (shell proxy + command mapping) is a totally different subsystem. (3) `DEVOLAFLOW_SI_CHIP_DEEP` (post-skill-edit dogfood gate) fires AFTER commits, not at session start. (4) `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` (dispatcher pre-flight plugin install) is conceptually similar (both opt-in dispatcher session lifecycle hooks) BUT activates plugin-install code paths, not selector cache state — REUSING that flag would conflate the two surfaces. The two flags compose meaningfully: `AUTO_INSTALL_PLUGINS=1 + WARMUP=1` = full session-start prep (auto-install plugins + warm selector cache); `WARMUP=1` alone = cache pre-warm only (operators who pre-install plugins manually). No existing flag could be REUSED without conflating distinct activation surfaces. |
| **R5 strict?** | YES — `warmup_selector_cache` reads `os.environ.get(WARMUP_ENV_FLAG)` EXACTLY against the literal `WARMUP_TRUTHY_VALUE = "1"`. No IO, no subprocess, no Path.read_text when unset (codified by `tests/test_selector_warmup.py::test_warmup_skips_env_flag_at_module_import`). |
| **Idempotency** | Calling `warmup_selector_cache()` a second time is cheap (LRU cache absorbs repeats in O(1) per pair). Calling without the env flag is a strict no-op. Calling with the env flag in a stale Python process where the cache is already populated also a strict no-op (same hit path). |
| **S-5 graceful** | A single warmup call that raises (e.g. transient profiles.yaml read error) is logged at WARNING level and the helper continues with the next pair. The warmup is best-effort by contract — partial warmup is strictly better than a cold cache. |
| **Reference** | `tests/test_selector_warmup.py` (7 NEW tests pin the activation matrix + idempotency + R5 strict + time budget + import-time invariant); `src/devolaflow/task_adaptive_selector.py::warmup_selector_cache` (the public entry point); `.local/research/v9.7.0_gap_analysis.md` §1.3 D-N-2 + `.local/research/v9.7.0_perf_research.md` §4 |

## 3. Test-fixture flags (NOT runtime flags)

These flags are read ONLY by tests (`tests/`) and never by production
code. They appear in this reference because operators sometimes set
them in CI configs and need to know they have NO production effect.

### 3.1 `DEVOLAFLOW_NINES_EDITABLE_PATH` — local NineS editable install path

| Field | Value |
|---|---|
| **Owner** | `tests/test_plugins.py` (line 549, fixture only) |
| **Default** | `/home/agent/workspace/NineS` |
| **Effect** | When the plugin-install integration test runs, it uses this path as the local fallback for `pip install -e <path>` instead of fetching from PyPI |
| **Production effect** | NONE — production paths use `pip install nines==<min_version>` per `runtime-plugins.yaml` |
| **Per S-7** | This is a test-side override; the production reference file MUST NOT hardcode this path |

### 3.2 `DEVOLAFLOW_PROBE_SCENARIO` — compression probe scenario selector

| Field | Value |
|---|---|
| **Owner** | `tests/conftest.py::_compression_e2e_workspace` |
| **Default** | `easy` |
| **Effect** | Selects the scenario tier for `tests/test_e2e_compression.py` — `easy` (~500-token artifact, 5 entities), `medium` (~5K tokens, 20 entities), `hard` (~15K tokens, 50 entities) |
| **Production effect** | NONE — runtime never reads this |

### 3.3 `DEVOLAFLOW_MOCK_KEY` — mock LLM provider key

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/llm_client.py::_API_KEY_ENV_VARS["mock"]` |
| **Introduced** | v8.0.0 P-12 (Stage B abstractive client) |
| **Default** | unset |
| **Effect** | When the LLM Stage B client runs with `provider="mock"`, this env var is consulted as the API key; tests use any non-empty value, production uses provider-specific keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) |
| **Production effect** | Test-only path — production never selects `provider="mock"` |

## 4. Forward-declared gate-primitive flags (residual after PV-06)

The v9.0.0 PV-06 (v8.5.1) Theme T5 flip moved 5 of the 6 originally
forward-declared flags into §2 (active runtime flags) — see §2.6..§2.10.
The 2 rows below remain forward-declared for a future cycle:

| # | Flag | Owner module (target) | Per-profile default | Companion config key |
|---|------|------------------------------|---------------------|----------------------|
| 1 | `DEVOLAFLOW_CYCLE_DETECTOR`       | `src/devolaflow/gate/cycle_detector.py`               | OFF (opt-in)                                    | `gate.cycle_detection`         |
| 2 | `DEVOLAFLOW_LEGIBILITY_CHECK`     | `src/devolaflow/legibility/scorer.py`                 | OFF (opt-in)                                    | `decomposition.legibility_check` |

**Why these stayed forward-declared in PV-06**: cycle-detector overlaps
the legacy `accept` list semantically (the v7.x `accept` path already
catches most cycle conditions); legibility-check is an additive scorer
whose default-on impact requires its own EvoBench `_disabled.yaml`
scenario set before flip. Both are tracked for the v9.x cycle's TBD
"completion theme".

**Cross-reference**: the PV-06 flip plan + acceptance criteria + opt-out
path live in `.local/research/adr/v9-ADR-006-compression-pipeline-and-b3-flip.md`.
The 5 promoted flags' R5 strict opt-out contract is pinned by
`tests/test_pv06_primitive_flip.py` and verified end-to-end by the 5 new
`benchmarks/devolaflow_context/scenarios/*_disabled.yaml` EvoBench scenarios.

## 5. Karpathy 4-primitive defaults (default-ON, no flag)

The 4 Karpathy-derived behavioral primitives (BG-001..BG-004) ship
**default-ON** in v8.0.0 P-08 and have **NO env-flag override**.
Operators who want to disable them adjust the per-profile
`behavioral_guidelines` dispatch field (canonical_order position 14).

| BG | Primitive | Default | Override mechanism |
|----|-----------|---------|--------------------|
| BG-001 | `think_first`     | ON | dispatch field `behavioral_guidelines.think_first=false` |
| BG-002 | `simplicity_check`| ON | dispatch field `behavioral_guidelines.simplicity_check=false` |
| BG-003 | `surgical_scope`  | ON | dispatch field `behavioral_guidelines.surgical_scope=line\|chunk\|module\|file` |
| BG-004 | `goal_loop`       | ON | dispatch field `behavioral_guidelines.goal_loop=false` |

**Why no env-flag?** The behavioral primitives are part of the
**dispatch payload contract** — they ship at the per-task granularity,
not the per-process granularity. An env-flag would force every L3 Task
Agent in a process to share the same value; the dispatch field allows
per-task tuning. See `references/behavioral-guidelines.md` for the full
BG-001..BG-004 spec.

## 6. R5 strict pattern — the conjunction contract

For the R5 strict flags (#2.2 `DEVOLAFLOW_RTK_PROXY`, #2.3
`DEVOLAFLOW_RTK_PROXY_TIER2`, #2.4 `DEVOLAFLOW_MEMORY_ROUTER`, and the
5 v8.5.1 PV-06 promotions §2.6..§2.10) the "feature is active"
predicate is the **conjunction** of:

1. env-var read returns EXACTLY `"1"` (rejects `"true"`, `"yes"`, `"on"`, `"01"`, `""`)
2. The companion runtime probe succeeds (e.g. `shutil.which("rtk")` for #2.2, `Path.exists` for #2.4's index file)

When EITHER side is missing, the feature is a **zero-IO no-op**:

* NO `Path.read_text` (codified by `tests/test_*_r5_strict_off.py` watchers)
* NO `subprocess.run`
* NO `shutil.which` (for the strict-affected modules — the post-activation `ShellProxyConfig` caches the result)
* NO `import` of the heavy code path (the watcher tests prove the cold-path import is not triggered)

This is the **R5 strict contract** that lets the v8.x codebase ship
~3000 tests where the new opt-in surfaces add ZERO baseline cost when
unset. The contract is verified at FOUR layers:

| Layer | Test file | Mechanism |
|-------|-----------|-----------|
| Unit  | `tests/test_shell_proxy_disabled_is_noop.py` | `monkeypatch.setattr(subprocess, 'run', ...)` watcher |
| Unit  | `tests/test_memory_router.py::TestLookupCaseR5StrictOff` | `monkeypatch.setattr(Path, 'read_text', ...)` watcher |
| Unit  | `tests/test_shell_proxy_commands.py::TestLoadR5StrictOff` | same Path.read_text watcher |
| EvoBench | `benchmarks/devolaflow_context/scenarios/{shell_proxy_disabled,memory_router_fastpath,command_mapping_density}.yaml` | composite floor 90 vs `simple_implementation` baseline; actual ~99 |

## 7. Adding a NEW env-flag — W-20 enforcement checklist

Before authoring a NEW `DEVOLAFLOW_*` env-flag, an L3 Task Agent MUST
walk the W-20 checklist:

1. **Inventory check** — read this reference §2..§5 to confirm no
   existing flag covers the same surface.
2. **Behavioural orthogonality test** — would the new flag activate
   independently of every existing flag? If NO (e.g. it always
   piggybacks on an existing flag), REUSE the existing flag with a
   sub-condition (the v8.3.4 PV-04 command-mapping layer is the
   canonical example: it REUSES `DEVOLAFLOW_RTK_PROXY` rather than
   adding `DEVOLAFLOW_COMMAND_MAPPING`).
3. **R5 strict design** — if the new flag is a runtime activation flag
   (not a config tuning knob), the companion code path MUST be
   zero-IO when the flag is unset. Authors MUST author a watcher test
   in the same PV that proves zero IO.
4. **Reference update** — add the new flag to §2.1..§2.5 (active) or
   §4 (forward-declared) in this reference IN THE SAME PR as the
   handler implementation.
5. **CHANGELOG entry** — the PR's CHANGELOG entry MUST cite the new
   flag by name in the §"Operator-visible behavior change" section.

A NEW env-flag PR that fails any of the 5 checks is a **W-20
violation** — block at code review and either remove the flag (REUSE)
or document the orthogonality argument explicitly.

## 7.A Lifecycle event taxonomy (v11.0.0 PV-02 D-Q-3 PURE-ALIAS rename)

> **Cross-cuts §2.12 + §2.13**: the `pre_plugin_invocation` /
> `post_skill_edit` env-flag rows reference event slots in
> `src/devolaflow/lifecycle/__init__.py::DEFAULT_EVENTS`. v11.0.0 PV-02
> D-Q-3 introduces 4 NEW canonical event names per a 3-prefix taxonomy
> (`pre_*` / `post_*` / `check_*`) with PURE-ALIAS preservation of the
> 4 OLD names for 1 cycle.

Per `.local/research/v11.0.0_patches/D-Q-3.md` §2 the rename mapping is:

| OLD event name (PURE-ALIAS, v11.x) | NEW canonical name | Position in DEFAULT_EVENTS | Handler module |
|---|---|:---:|---|
| `file_write` | `check_file_write` | 3 (OLD) / 13 (NEW) | `lifecycle/check_file_ownership.py` (S-8 owned-files manifest enforcement) |
| `task_stop` | `post_task_complete` | 4 (OLD) / 14 (NEW) | `lifecycle/test_on_complete.py` (verifies tests-pass at task end) |
| `format_on_edit` | `post_file_edit` | 5 (OLD) / 15 (NEW) | `lifecycle/format_on_edit.py` (auto-format after edit) |
| `envelope_write` | `check_envelope_write` | 7 (OLD) / 16 (NEW) | `lifecycle/check_envelope_append_only.py` (S-9 append-only enforcement) |

**Resulting taxonomy** (after rename, before deprecation; 3-prefix
partition for 100% conformance):

| Prefix group | Events | Count |
|---|---|:---:|
| `pre_*` | `pre_dispatch`, `pre_shell_call`, `pre_handoff`, `pre_plugin_invocation`, `pre_plugin_invocation_install`, `pre_plugin_invocation_upgrade` | 6 |
| `post_*` | `post_dispatch`, `post_task_complete`, `post_file_edit`, `post_skill_edit` | 4 |
| `check_*` | `check_file_write`, `check_envelope_write` | 2 |

**Alias schedule**: OLD names are PURE-ALIAS for v11.0.0..v11.x. Both
names accept `register_hook(event, handler)` and dispatch via
`run_hooks(event, payload)` to the SAME underlying handler list (single
source of truth in `_DEFAULT_HOOKS` / `_EXTRA_REGISTRY` keyed by the
canonical name; alias resolution via `dispatcher._EVENT_ALIASES`).
**Removal target: v12.0.0+** SI-1 evaluates the actual operator usage
of OLD names; if zero in-cycle production usage, the OLD names retire
at v12.0.0 and any remaining test fixture references migrate to the
NEW canonical names.

**Migration guidance for operators**:

1. Audit any custom `register_hook(...)` calls in your skill / extras
   for the 4 OLD names; replace with the NEW canonical names.
2. Audit any string-literal references in test fixtures or config
   files; the constants `FILE_WRITE_EVENT`, `TASK_STOP_EVENT`,
   `FORMAT_ON_EDIT_EVENT`, `ENVELOPE_WRITE_EVENT` are preserved but
   point at the OLD strings; the v12.0.0 retire flips them OR they
   stay as alias re-exports.
3. The `registered_events()` introspection helper returns BOTH the
   canonical names AND the aliased names so operators can verify their
   registrations resolve cleanly during the migration runway.

**Cross-references**:

* `.local/research/v11.0.0_patches/D-Q-3.md` — full PDS authoring this rename.
* `tests/test_lifecycle_hooks.py::test_v11_0_0_pv02_dq3_*` — the 5 PURE-ALIAS regression tests.
* `src/devolaflow/lifecycle/dispatcher.py::_EVENT_ALIASES` — the alias map.
* `src/devolaflow/lifecycle/__init__.py::DEFAULT_EVENTS` — the 16-entry tuple after the v11.0.0 PV-02 D-Q-3 append.

## 8. Cross-references

* SKILL.md §"Reference Navigation Guide" Tier-2 row — discovery surface
* `references/shell-proxy.md` §3.1 — RTK + memory-router env-flag table (cross-link from §2.2..§2.4)
* `references/decomposition-gate.md` §11 — gate primitive table (cross-link from §4)
* `references/plan-mode-enforcement.md` §2 — plan-mode detection table (cross-link from §2.1)
* `references/behavioral-guidelines.md` — BG-001..BG-004 spec (cross-link from §5)
* `AGENTS.md` §"W-20" — env-flag reuse vs new-flag policy (the rule this reference enforces)
* `.local/research/v9.0.0_pv05_design.md` §1 — full PV-05 audit + decision rationale
* `.local/research/adr/v9-ADR-005-nines-hygiene-and-w-rules.md` D5 — ADR for AGENTS.md ceiling bump + W-rule batch

---

> Maintenance contract — this reference is the **single source of
> truth** for env-flag inventory. v9.0.0 PV-06 (v8.5.1) closed the §4 →
> §2 promotion for 5 of the 6 forward-declared gate-primitive flags
> (`TOKEN_BUDGET_BREAKER`, `VERIFICATION_LADDER`, `GATE_RATCHET`,
> `COMPLEXITY_DETECTOR`, `AC_GEN`) per Theme T5. Two flags
> (`CYCLE_DETECTOR`, `LEGIBILITY_CHECK`) remain in §4 for a future
> cycle. The W-20 checklist (§7) MUST stay current with the cycle-N
> inventory.
