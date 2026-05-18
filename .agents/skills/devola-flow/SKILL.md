---
id: "agent/SKILL"
version: "12.4.0"
purpose: >
  Entry point for the DevolaFlow workflow orchestration skill.
  Orchestrate multi-stage software workflows using a 4-layer agent hierarchy
  with gate mechanisms, convergence loops, and context-isolated task delegation.
triggers:
  - "implement feature"
  - "build from scratch"
  - "fix bug"
  - "refactor code"
  - "migrate system"
  - "full pipeline"
  - "hotfix"
  - "workflow orchestration"
  - "run workflow"
  - "update devola"
  - "update_devola"
  - "/update-devola"
tier: 1
token_estimate: 2800
last_updated: "2026-05-09"
name: devola-flow
description: >
  Use when orchestrating multi-file software tasks, implementing features,
  fixing bugs, refactoring, or running any multi-step development workflow
  that benefits from structured dispatch, quality gates, and context-isolated
  subagents.
---

> **Now Using DevolaFlow v12.4.0**

# DevolaFlow

## Version & Update
**Current version:** 12.4.0 — Check: `curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/src/devolaflow/__init__.py | grep '__version__'`
If newer: `pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git`. Only check on explicit user request ("update devola" / "update_devola" / "/update-devola").

### Session Banner Contract (v12.3.0+)

L0 MUST echo the active devola version on session boundaries so operators see live confirmation of orchestrator + version (closes `.local/feedbacks/feedback_for_v12.1.1.md` #1):

* **Workflow start** (first message after skill activation OR first dispatch): emit one line — `🌸 DevolaFlow v12.3.0 active · workflow: <type> · mode: <agent|plan|grill>`. Use the literal version string from this §"Version & Update" header (kept in sync by `scripts/bump_version.py`).
* **Workflow end** (final report after the last stage completes): emit one line — `🌸 DevolaFlow v12.3.0 complete · <stages> stages · <waves> waves · <tasks> tasks` (omit counts for SIMPLE/TRIVIAL single-task shortcuts).
* **Task Quality Score footer** (per `references/task-quality-score.md`): footer line MUST include literal `DevolaFlow v12.3.0` so the score artifact is self-describing in chat logs.

Banner output is for the OPERATOR (chat output), NOT for inter-layer dispatch payloads — keep dispatch / handoff envelopes free of decorative banners per CO-2.
Subagent (L1/L2/L3) reports MUST NOT include banner lines — see PV-05 runtime hook `reject_subagent_banner_emission`. Banners are L0-only operator chat output.

**Note (v9.2.2+)**: `pip install` ships the package but the `devola-init` CLI's `cursor` / `claude` / `codex` / `copilot` targets need the `workflow-system/agent/` source tree (not bundled in the wheel). For most install scenarios `devola-init local --mode=core` works on a wheel-only install (v9.2.3+ — `--mode=core` is the shorthand for `--no-compile --no-with-examples`, the lean scaffolding-only install). For other targets, install from a clone: `git clone https://github.com/YoRHa-Agents/DevolaFlow && pip install -e ./DevolaFlow`. Tracked in I-001 (fixed v9.2.2) + I-004 (doc v9.2.2) + `--mode` shorthand (v9.2.3); full bundle deferred to v9.3.0.

## Workspace Engagement (Read at Session Start)

Before applying the Quick Action Decision table, **scan the consumer repo's workspace surfaces** so dispatch context reflects the project's accumulated state. Use `devolaflow.workspace_context.scan_workspace(repo_root)` (returns a frozen `WorkspaceContext` snapshot) — pure-function, zero side effects, safe to call repeatedly.

| Surface | When present | What L0 does |
|---|---|---|
| `.local/feedbacks/feedback_for_v*.md` | User has accumulated cross-version feedback | READ the latest 3 (`recent_feedbacks`) and surface themes in plan-mode reasoning |
| `.local/memory/specs/<domain>/spec.md` | Source-of-truth specs exist (A-4) | TREAT as ground truth; per-change `spec.md` files express deltas relative to these |
| `.local/memory/cases/*.md` | Prior decisions cached | When `DEVOLAFLOW_MEMORY_CONSULT=1`, surface relevant cases as dispatch hints |
| `.local/.agent/active/<id>/` | In-flight changes exist | RESUME the change rather than opening a new one (check `STATUS.yaml.state`) |
| `.rules/*.mdc` + compiled `AGENTS.md` | Layered governance corpus present | TRUST the compiled corpus as the rule contract; opt-in `agents_md_slice` slices per task type |

**Defaults**: Workspace scanning is read-only and ALWAYS performed. Auto-write side effects (handoff envelopes, change folder scaffolding) are R5-strict default-OFF; opt in via `DEVOLAFLOW_AGENT_WORKSPACE=1`. **Resume + override (v10.5.0):** when `active_changes` non-empty AND idle >24h, follow `agent-workspace.md` §3.6 (5-step checklist); pass `force_no_change=True` to `activation_verdict()` for ad-hoc dispatch bypass.

See `references/agent-workspace.md` §"When to Engage" for the full activation contract and `references/plan-mode-enforcement.md` §"Feedback Ingestion" for plan-mode consumption rules.

## Quick Action Decision

| Complexity | Signal | Action |
|-----------|--------|--------|
| **Trivial** | Single file, < 20 lines, obvious fix | Execute directly — P1 waived for minimal edits |
| **Simple** | 1-3 files, clear scope, < 1 hour | Dispatch **single Task Agent** via `Task` tool — no multi-stage workflow |
| **Standard** | 3-10 files, needs design or review | L0→L1→L2→L3 cascade (`examples/multi-stage-trace.md`) |
| **Complex** | 10+ files, cross-cutting, multi-day | L0→L1→L2→L3 cascade with strict gate profile |

**Rule**: Match ceremony to complexity. **P1**: For Simple+ tasks, always delegate work to Task Agents — never implement directly. **Cascade verdict** via `cascade_requirement(complexity)` returns `CASCADE_REQUIRED` for Standard/Complex, `CASCADE_OPTIONAL` for Simple/Trivial.

## Mode Awareness

**Detection (priority order):**
1. `<system_reminder>` contains "Plan mode is active" → **PLAN MODE**
2. `SwitchMode` tool available and current mode is `plan` → **PLAN MODE**
3. User explicitly says "build a plan" / "plan this" / "design first" → **PLAN MODE**
4. `classify_grill_intent(message)` returns `GRILL_REQUESTED` → **GRILL MODE** (concurrent with current mode; not exclusive)
5. Otherwise → **AGENT MODE** (default, full orchestration). **v6.1.5+ runtime hook:** `select_context(plan_mode=True)` (or env `DEVOLAFLOW_PLAN_MODE=1`) escalates plan-relevant sections (`agent_hierarchy`, `decomposition_gate`, `rationalization_prevention`) to `critical` and upgrades `model_hint` to `quality`.

### PLAN MODE — Design the Plan, Do NOT Execute

**You are L0 (Project Agent).** Design the execution plan as a delegation contract; L0 dispatches → L1 → L2 → L3 (only L3 implements). Plan output template (title → overview → execution model → stages → waves × ≤5 tasks → tasks × {writable, read-only, AC}), Constraints Checklist (9 items incl. P1 enforcement), Invariants P1–P5, and DO / DO NOT rules: see `references/plan-mode-enforcement.md`.

### AGENT MODE — Full Orchestration

**You are the L0 Project Agent.** You orchestrate — you NEVER implement.

**P1 Self-Check — Before using any tool, verify:**
- Am I about to write/modify a source file? → DELEGATE via `Task` tool
- Am I about to run tests or build commands? → DELEGATE via `Task` tool
- Am I about to author a design doc or review? → DELEGATE via `Task` tool
- Am I reading files to understand the codebase for planning? → ALLOWED

**L0 Tool Permissions:**
- **ALLOWED**: Read, Glob, Grep, SemanticSearch (understand codebase), TodoWrite (track progress)
- **DELEGATE**: Write, StrReplace, Shell (code/test/build), EditNotebook → spawn Task Agent
- **Trivial exception**: Single file, < 20 lines → P1 waived, execute directly

**Execution Protocol:**
1. **ASSESS** complexity → Quick Action Decision table
2. **SELECT** workflow type → Workflow Selection table below
3. **DECOMPOSE** into stages → waves → tasks (disjoint file ownership per wave)
4. **DISPATCH** each task → `Task` tool (subagent_type: `generalPurpose`); prompt includes role, task_id, description, owned_files, read_only, acceptance_criteria, predecessor summary (3-5 sentences max)
5. **VERIFY** task output against acceptance criteria
6. **GATE** stage → composite score ≥ threshold, 0 blockers → advance or converge
7. **REPORT** final results + Task Quality Score

**Simple task shortcut** (SIMPLE/TRIVIAL, < 1 hour):
Skip multi-stage hierarchy. Dispatch a **single Task Agent**. STANDARD+ MUST cascade per `cascade_requirement()`. Verify output and report.

### GRILL MODE — Interrogate the Plan, Sharpen the Domain (v11.3.0+)

**You are L0.** Grill Mode is the **parallel-orthogonal** sibling of PLAN MODE — both can be active simultaneously. When triggered (explicit "grill" / "interview me" / "stress-test plan" / "challenge the plan" / "interrogate" / "sharpen terminology" or `classify_grill_intent` returning `GRILL_REQUESTED`), L0 conducts a one-question-at-a-time interview, exploring the codebase before asking, sharpening fuzzy domain language, probing concrete scenarios, and offering ADRs only when the 3-condition gate (Hard to reverse + Surprising without context + Real trade-off) all pass. Inline updates to `CONTEXT.md` (vocabulary) and `docs/adr/` (architectural decisions) are R5 strict default-OFF — explicit operator consent required per session. NO new env flag (W-20 reuse-first); activation is purely natural-language. See `references/grill-mode.md` for the operating contract and `references/domain-awareness.md` for `CONTEXT.md` + ADR format.

## Quick Start — Workflow Selection
Match user intent to workflow type, then load the corresponding stage template.

| Intent Keywords | Workflow Type | Stages (abbreviated) |
|---|---|---|
| research, compare, survey, investigate | `research-only` | research |
| design, architect, API spec, schema | `design-only` | research → design → review |
| fix bug, broken, crash, hotfix, SEV1/SEV2 | `hotfix` | triage → fix → test → release |
| refactor, clean up, tech debt, simplify | `refactoring` | scope → plan → impl → test → review |
| migrate, upgrade, port, convert | `migration` | assess → plan → impl → validate → cutover |
| prototype, spike, experiment, PoC | `spike-poc` | research → prototype → evaluate |
| document, write docs, README, guide | `documentation-only` | survey → author → review |
| security, audit, CVE, vulnerability | `security-audit` | threat-model → scan → analyze → remediate → verify |
| add to existing, extend, enhance | `feature-enhancement` | design → plan → impl → review → test → release |
| build from scratch, new project, full | `full-pipeline` | design → plan → impl → review → test → testgate → release |
| design with research, ADR, iterate design | `research-design-review-refine` | research → design → review → refine (loop) |
| demo, showcase, presentation, pitch | `demo-showcase` | research → storyboard → build → review → polish → package |
| slow, optimize, profile, benchmark | `performance-optimization` | profile → design → optimize → benchmark → validate |
| setup env, install, configure tools | `dependency-setup` | research → plan → configure → verify |
| new to project, onboard, getting started | `onboarding` | analyze → document → setup → verify |
| optimize skill, benchmark context, density | `skill-optimization` | survey → profile → optimize → benchmark → iterate → document |
| update refs, self-update, check references | `self-update` | check-refs → research-updates → decompose → integrate → test → evaluate |
| verify, product verification, visual test, UAT, user-facing quality | `product-verification` | analyze → design → implement → test → verify → review → validate |
| nines-assisted self-eval, NineS analysis, evaluation pipeline | `nines-assisted` | research → design → plan → impl → review → test → validate → release |
| init repo, initialize, scaffold workspace, setup rules, 初始化仓库 | `repo-init` | analyze → scaffold(.local/ + .rules/) → compile → interview → verify (mode: core\|standard\|full) |
| change, propose, apply, archive, lifecycle, OpenSpec | `change-driven` | propose → apply → verify → archive (lite/full mode); Rule A-6 auto-activates when `DEVOLAFLOW_AGENT_WORKSPACE=1` AND complexity ≥ Standard (CLI: `/devola:{propose,apply,verify,archive}`; `--no-change` opt-out) |
| entropy cleanup, gc agent, stale docs, drift audit | `entropy-cleanup` | scan → propose → review → apply |
| shell-proxy, rtk rewrite, fast-path memory, command mapping | `shell-proxy` | RTK shell-proxy + memory_router fast-path lookup at dispatch time (env-flag opt-in: `DEVOLAFLOW_RTK_PROXY=1` + `DEVOLAFLOW_MEMORY_ROUTER=1`) |
| grill, challenge plan, interview me, stress-test plan, domain glossary, sharpen terminology | `grill-driven` | interrogate → resolve-fuzz → cross-ref → record (CONTEXT.md/ADR) |

### Repo-Init Pre-Dispatch Contract

**Canonical manifest — ALL modes (core/standard/full) MUST create all 8 paths:**

| # | Path | Source | Contents |
|---|------|--------|----------|
| 1 | `.local/feedbacks/` | `scaffold_local()` | TRACKER.md + dir README |
| 2 | `.local/tasks/` | `scaffold_local()` | dir README |
| 3 | `.local/memory/` | `scaffold_local()` | MEMORY.md + dir README |
| 4 | `.local/index.md` | `generate_index()` | auto-generated listing |
| 5 | `.rules/compile-config.yaml` | `install_local()` | from packaged template |
| 6 | `.local/.agent/active/` | `scaffold_local()` | dir README |
| 7 | `.local/.agent/handoff/` | `scaffold_local()` | dir README |
| 8 | `.local/.agent/archive/` | `scaffold_local()` | dir README |

**Mode selects stages, NOT files.** `core` skips compile/interview/verify but scaffold MUST create all 8 paths. `standard` adds compile. `full` adds all stages.

**Pre-dispatch self-check (REQUIRED for repo-init):** Before dispatching scaffold, L0 MUST verify `owned_files ⊇ canonical_manifest` (all 8 paths above). Any missing path = `VOF001` blocker. L0 MUST include this assertion in the dispatch: *"owned_files covers all 8 canonical paths per SKILL.md §Repo-Init Pre-Dispatch Contract."* Post-init verify: `devola-init doctor`.

**Working-tree sanity check (v12.3.0 PV-04 — `.local/research/v12.2.0_retrospective.md` §4.3 learning):** at cycle-entry PV-01 (before authoring the SI-1 gap analysis), L0 MUST run `git status` + `git diff --stat HEAD -- '*.md' '*.py'` to surface pre-existing working-tree corruption (e.g. truncated CHANGELOG.md / test_no_ghost_features.py from a prior interrupted session). Restore drifted files via `git restore <path>` BEFORE proceeding so the SI-1 entry gate operates on a clean baseline. The v12.2.0 cycle is the canonical example — PV-01 surfaced a pre-existing 4787-line CHANGELOG.md truncation + 1786-line test_no_ghost_features.py truncation that would have silently invalidated W-18 ghost-audit if not restored first.

**Selection heuristics:**

- Urgency signals (urgent, ASAP, production down) → boost `hotfix`
- "from scratch" / "new project" / "greenfield" → boost `full-pipeline`
- Question-form phrasing (what, how, which, should we) → boost `research-only`
- Explicit type mention → direct match (highest priority)
- Ambiguous or multi-concern → default to `full-pipeline`
- High confidence (≥0.8) → auto-select; Medium (0.5–0.79) → present top 2–3; Low (<0.5) → require explicit choice

## 4-Layer Agent Hierarchy

| Layer | Role | Context | Delegates To | MUST NOT |
|---|---|---|---|---|
| **L0 Project** | Selects workflow, sequences stages, evaluates gates, reports to human | ~3K tok | Stage Agents | Write code, run tests, read source, author docs |
| **L1 Stage** | Owns one stage; decomposes into waves, runs convergence, evaluates gate | ~5K tok | Wave Agents | Write code, run tests, review, author content |
| **L2 Wave** | Dispatches parallel tasks, collects results, checks cross-task conflicts | ~4K tok | Task Agents | Do any task's work, modify outputs, retry >1 |
| **L3 Task** | **Only layer that does work.** Executes single atomic task | ~8K tok | Nothing (leaf) | Spawn sub-agents, modify files outside owned set |

**Invariant P1 — Dispatcher-Not-Implementer:** Layers 0–2 dispatch, monitor, and report. Only Layer 3 executes.
**Wave constraints:** max 5 tasks/wave, max 7 waves/stage, disjoint file ownership within a wave.
**Task sizing:** max 30 min (impl) / 45 min (research), max 6 writable files, ~50–300 lines changed.
**Escalation chain:** Task → Wave → Stage → Project → Human. Always upward, never skip levels.
Every loop has `max_iterations`. Every failure is classified (retry / escalate / abort). No infinite loops.

**Cascade requirement (v11.1.0):** STANDARD+ MUST cascade L0→L1→L2→L3 per `cascade_requirement()`; SIMPLE/TRIVIAL MAY collapse (see `examples/multi-stage-trace.md`).

### Rationalization Prevention

| Rationalization | Reality |
|---|---|
| "It's just one small file" | P1 applies regardless of size. Dispatch via `Task` tool. |
| "I'll be faster doing it myself" | Speed is not the goal — isolation and auditability are. |
| "The task is too simple for a subagent" | Use the Quick Action Decision table. If Simple+, delegate. |
| "I need to see the result before dispatching" | Read files (ALLOWED), then dispatch. Never write. |
| "One more retry should fix it" | Check `max_iterations`. If at limit, escalate — do not increment. |
| "The gate score is close enough" | Close is FAIL. Run convergence round or escalate. |
| "I'll skip the gate for this stage" | Gates are mandatory. No stage advances without gate PASS. |
| "Tests can be added later" | `test_on_complete` hook checks (warns by default; strict mode blocks). Run with `strict=True` for hard enforcement. |

### Wave Coordination Modes

L2 Wave auto-selects mode via O(|V|+|E|) DAG analysis. L1 may override (`topology_override`).

| DAG Shape | Mode | Mechanism |
|-----------|------|-----------|
| No edges | `parallel` | Dispatch all, collect results (default) |
| Linear chain | `sequential` | Dispatch N+1 after N completes |
| Quality-critical + shared context | `generator_verifier` | Gen → Verify → Refine loop (below) |
| Low-risk doc/research/design | `inline_self_review` | In-process checklist (~30s vs ~25min subagent); see references/decomposition-gate.md §8 |
| Mixed | `hybrid` | Partition into named recipes: orchestrator-subagent ⊕ shared-state, message-bus ⊕ agent-teams (see references/execution-protocol.md §7) |

**Gen-Verify loop** (convergence stages: review+fix, test+fix, benchmark+optimize):
1. Wave dispatches **generator** + **verifier** (criteria from `acceptance_criteria`)
2. Verifier evaluates → `{PASS | FAIL + feedback}`. PASS → done. FAIL → generator refines (round N+1)
3. Terminates on: verifier PASS, `max_rounds` reached, or score stagnant 2 rounds → escalate L1

**Subagent pattern selection (v11.4.0+):** when decomposing a wave, consult `references/subagent-patterns.md` §3 (decision tree) — `INLINE` / `FAN_OUT` are native; `AGENT_POOL_FORWARD` is forward-compat-only; `TEAMS_FORBIDDEN` per P5. See `src/devolaflow/skills/subagent_pattern.py::select_pattern()` for the pure-function helper.

## Stage Primitives Index

14 universal primitives across 6 categories. Every workflow is a composition of these.

**Discover:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `research` | Gather info, survey prior art, benchmark alternatives | Research |
| `analyze` | Examine existing artifacts for structured assessment | Research |

**Shape:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `design` | Synthesize inputs into architecture, API spec, schema, ADRs | Design |
| `plan` | Decompose design into waves and tasks with dependencies | Design |

**Build:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `implement` | Write code, create tests, build configs per design spec | Implement |
| `refine` | Address review/test findings — fix bugs, resolve comments | Implement |

**Verify:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `review` | Evaluate artifacts against quality standards, produce findings | Review |
| `test` | Execute test suites, measure coverage and performance | Test |
| `validate` | Aggregate verification results into readiness verdict | Review |
| `verify` | User-facing validation: visual regression, acceptance verification, interaction flows, accessibility | Test |

**Deliver:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `release` | Package, tag, publish artifacts, update changelog | Implement |
| `deploy` | Deploy released artifacts to target environments | Implement |
| `monitor` | Post-deploy observation, anomaly detection, stability check | Test |

**Control:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `gate` | Quality checkpoint blocking progression unless criteria met | (orchestrator) |

**Composition operators:** `sequence` (→), `parallel` (||), `choice` (⊕), `loop` (↻), `gate` (⊣). Full alias table + per-workflow sequences: `references/meta-framework.md`

## Gate Mechanism

**Composite score:** `composite = Σ(dimension_score × weight)` — test_quality×0.30, code_review×0.30, architecture×0.20, benchmark×0.20.
**Per-dimension:** `max(0, 100 - Σ(severity_weight × count))` — blocker=25, critical=15, major=5, minor=1, info=0.

**Extended Composite (when user-facing verification is present):**
`composite = test_quality×0.20 + code_review×0.20 + architecture×0.15 + benchmark×0.15 + visual_fidelity×0.10 + interaction_quality×0.10 + acceptance_verification×0.10`
- `visual_fidelity`: Screenshot comparison pass rate (0-100); `interaction_quality`: E2E flow success (60%) + accessibility (40%); `acceptance_verification`: AC test pass rate (0-100). Standard 4-dimension formula is used when no user-facing inputs are present (backward compatible).

**Pass conditions (ALL required):**
1. `composite_score >= threshold` (default 85)
2. Zero blocker findings AND zero MUST-priority violations
3. `coverage >= coverage_threshold` (default 80%)

**On FAIL:** round < max_rounds → next convergence round. Stagnant 2+ rounds → escalate. round >= max_rounds → escalate.
**Gate profiles:** `relaxed` (≥70, ≥60% cov), `standard` (≥85, ≥80%), `strict` (≥90, ≥90%), `audit` (≥95, ≥90%).
Full gate specification: `references/decomposition-gate.md`

### Reinforcement Rules (v5.1+)
When a stage gate FAILS, next round's dispatch carries top-5 prior-round findings (severity ≥ major) as `applicable_rules.reinforcement` MUST-fix mandates; L3 MUST address all before any new work (failure = automatic blocker next gate). Mechanism + L3 obligation matrix + round-aware escalation table: `references/plan-mode-enforcement.md` §"Reinforcement Rules".

## AgentTeam Quick Reference

| Team | Responsibilities | Primary Tools | Output |
|---|---|---|---|
| **Research** | Survey prior art, benchmark, compare, identify gaps | WebSearch, WebFetch, Read, Glob, SemanticSearch | Research report, comparison matrix |
| **Design** | Architecture, API spec, data models, ADRs, schemas | Read, Write, SemanticSearch, WebSearch | Design document, interface definitions |
| **Implement** | Write code + unit tests, fix issues, configs | Read, Write, StrReplace, Shell, Grep, ReadLints | Source files, test files, build artifacts |
| **Test** | Run test suites, measure coverage, gap analysis | Shell, Read, Write, Grep | Test report, coverage metrics |
| **Review** | Code/design review, quality scoring, SOLID + simplicity checks | Read, Grep, SemanticSearch, ReadLints | Severity-classified findings, quality score |

Full team specifications + participation matrix: `references/team-roles.md`

## Context Isolation

Each Task Agent spawns with a fresh, isolated context:

```
context_injection:
  identity:    role, task_id, team                            (~100 tokens)
  task:        title, description, acceptance_criteria         (~500-1500 tokens)
  context:     predecessor_summary, design_excerpt, interfaces (~1000-3000 tokens)
  files:       owned (create/modify), read_only               (~200-500 tokens)
  rules:       loading_strategy, language, quality_focus       (~2000-5000 tokens)
  behavioral:  timeout, max_files, output_format, escalation   (~200 tokens)
```

**MUST NOT leak:** conversation history, file contents from other tasks, full predecessor artifacts, error details from siblings, quality scores from unrelated tasks.
**IS shared (via artifact summaries):** interface contracts, design decisions (ADRs), naming conventions, quality thresholds, acceptance criteria.
Full context injection spec: `references/context-isolation.md`
**Cache layout (v7.0.0+):** Key order fixed by `schemas/lean-dispatch.yaml#layout_invariant`; see `references/context-isolation.md` Cache-Layout Invariant subsection for the `assert_dispatch_layout` validator API.

## Subagent Hang Prevention

**L0 contract**: ALWAYS set `timeout_seconds` in TaskDispatch per task type — `research=2700` / `impl=1800` / `test=900` / `review=1200` / `hotfix=600`. Default 7200 is a fail-safe ceiling, not a target.

**L3 forbidden patterns** (every dispatched subagent MUST AVOID — these are the canonical hang vectors):
- `AskQuestion` — no human channel exists below L0; resolve via predecessor artifacts or escalate via StatusReport
- Recursive `Task` tool re-entry — L3 is the leaf (P5 invariant); only L0/L1/L2 dispatch
- Unbounded `Shell` calls — every invocation MUST set explicit `block_until_ms` (≤60000 ms for fast commands, ≤300000 ms for `pytest` runs)
- Unbounded `WebFetch` / `WebSearch` — verify upstream timeout coverage; abandon stalled requests rather than wait forever
- Internal loops without `max_iterations` — every loop has a ceiling, every failure is classified (retry / escalate / abort)

**L3 progress contract**: emit a heartbeat (`progress_pct` update in StatusReport) at least every 5 minutes for long-running tasks; if no progress is observed within the dispatched `timeout_seconds` budget → self-escalate via `StatusReport(escalation: HUMAN_INTERVENE, reason='suspected_hang')` rather than retry indefinitely.

**L0 hang detection**: if a dispatched task exceeds `timeout_seconds` OR shows no `progress_pct` change for 10 minutes → cancel + escalate per P4 (Task → Wave → Stage → Project → Human). Never wait past the ceiling.

## Dispatch & Report Protocol

All inter-layer communication uses typed YAML schemas. Free-form chat between layers is prohibited.

**Dispatching a task:**
- `task_id`, `type`, `title`, `description`
- `predecessor_artifacts`: list of `{path, summary}` (3-5 sentence summaries only)
- `owned_files`: disjoint from parallel tasks
- `acceptance_criteria`: concrete pass conditions
- `timeout_seconds`: max execution time (default 7200)
- `model_hint`: quality | balanced | budget | inherit (default: inherit) — model tier suggestion
- `decomposition_mode`: single | sub_agents (default: single) — L3 execution strategy
- `compression_intensity`: minimal | standard | aggressive (default: standard) — dispatch message compression
- `verification_config`: visual/acceptance/interaction/accessibility test settings (optional)

**Reporting completion:**
- `task_id`, `state` (completed/failed/escalated), `progress_pct`
- `artifacts`: list of `{path, type, summary}`
- `metrics`: `tests_passed`, `coverage_pct`, `findings_by_severity`
- Subagent reports DO NOT include `quality_score` (L0-only per §"Task Quality Score (L0 ONLY)")

**Escalation severity:**

| Severity | Action |
|----------|--------|
| `AUTO_RECOVER` | Retry up to 3x with exponential backoff |
| `PAUSE` | Pause task, queue question, continue parallel work |
| `HUMAN_INTERVENE` | Stop stage, present options to human |
| `FULL_ROLLBACK` | Rollback to checkpoint, halt all |

Full schemas: `references/message-schemas.md`

**Round-aware dispatch (v6.0.3+):** `select_context(task_type, round_num=N)` auto-applies escalation for N>1 (critical-section bump, +20% budget on round 3, `model_hint → quality`). `ProposalGenerator.generate_round_dispatch()` merges prior-round gate findings into `context.applicable_rules.reinforcement` as explicit MUST-fix mandates for L3.

## Lifecycle Hooks

Permissive default (warn + log); strict opt-in raises HookViolation.

| Hook | Event | Checks | On Violation (strict) |
|------|-------|--------|----------------------|
| `validate_dispatch` | Pre-dispatch | AC ≥1 testable condition | Block + escalate |
| `check_file_ownership` | File write | File ∈ `owned_files` | Reject + log (P1) |
| `test_on_complete` | Task stop | Tests pass, lint clean | Auto-retry ≤ P4 limit |

API: `run_hooks(event, payload, *, strict=False)` in `src/devolaflow/lifecycle/`. v8.4.4 adds `post_dispatch` (no-op default) wired by S-10 — see `references/plan-mode-enforcement.md` §10.

## Repo Mode Detection

| Mode | Detection Signal | Key Capabilities |
|---|---|---|
| **local** | No `.git` or no remote | Local build/test/lint only; no CI, no release, no PR flow |
| **github** | Remote matches `github.com` | GitHub Actions CI, cross-platform matrix, Pages, Releases, PR flow |
| **other-git** | Any other remote | Platform-native CI, MR/PR flow, variant-specific pipeline templates |

Detection: parse `git remote -v` → match URL → fallback to CI config files.
Override: `repo_mode` in `.workflow/config.yaml`. Full detection: `references/repo-modes.md`

## Reference Navigation Guide

**Tier 2 — Domain references** (load when topic arises):

| File | Load When |
|---|---|
| `references/agent-hierarchy.md` | Layer setup, delegation debugging, per-layer contracts |
| `references/agent-workspace.md` | Change folders, handoff envelopes, archive, source-of-truth specs |
| `references/behavioral-guidelines.md` | L3 think_first / simplicity_check / surgical_scope / goal_loop primitives |
| `references/compression-pipeline.md` | CompressionStage protocol, 6-transform unification, multi-pass filter chain |
| `references/context-isolation.md` | Context injection setup, debugging leaks |
| `references/decomposition-gate.md` | Gate evaluation, threshold config, convergence loops |
| `references/degraded-mode.md` | Per-plugin upstream-unreachable contract (NineS / Si-Chip / RTK / ui-pro); "Degraded ≠ Full" |
| `references/domain-awareness.md` | CONTEXT.md authoring, CONTEXT-MAP.md multi-context inference, ADR format, 3-condition ADR gate, vocabulary vs spec.md |
| `references/env-flags.md` | DEVOLAFLOW_* env-var inventory, R5 strict patterns, W-20 reuse policy |
| `references/evaluator-rosetta.md` | SI-3 × NineS × Si-Chip 6×9 cross-walk, C-04 split, per-cell authority citations |
| `references/execution-protocol.md` | Task execution lifecycle, tool usage patterns |
| `references/grill-mode.md` | Grill mode active, stress-test plan, sharpen terminology, interrogate operator, codebase cross-reference, ADR offer evaluation |
| `references/message-schemas.md` | Constructing/parsing dispatch/report/escalation |
| `references/meta-framework.md` | Workflow instantiation, stage ordering |
| `references/plan-mode-enforcement.md` | Plan-mode L0 contract, plan output template, reinforcement rules, convergence loop |
| `references/repo-modes.md` | Repo detection, mode-specific behavior |
| `references/shell-proxy.md` | RTK plugin + shell_proxy + pre_shell_call hook + memory_router + command mapping |
| `references/subagent-patterns.md` | Subagent pattern selection (4-pattern taxonomy: Inline Tool / Fan-Out / Agent Pool / Teams), v12.0.0 NEST schema roadmap, Pattern 3 forward-compat plan, Pattern 4 P5-Forbidden rationale |
| `references/task-quality-score.md` | LOAD AT WORKFLOW CLOSE ONLY — full Task Quality Score rubric (v12.3.0 PV-03 extraction; ~120 tokens kept out of execution-loop context) |
| `references/team-roles.md` | Task agent config, team capabilities |
| `references/troubleshooting.md` | Operator-friction lookup index + per-symptom diagnostics (load when a dispatch/gate/hook fails opaquely) |

**Tier 3 — On-demand** (load for specific tasks):

| File | Load When |
|---|---|
| `examples/full-pipeline-trace.md` | Full-pipeline walkthrough |
| `examples/hotfix-trace.md` | Hotfix delegation example |
| `examples/convergence-loop-trace.md` | Review-fix-test cycle walkthrough |
| `schemas/task-dispatch.schema.yaml` | Building TaskDispatch YAML |
| `schemas/status-report.schema.yaml` | Building StatusReport YAML |
| `schemas/handoff-deliverable.schema.yaml` | Inter-team handoff envelopes |
| `templates/project-status.yaml` | Project tracking dashboard |
| `templates/stage-readme.md` | Per-stage tracking documents |
| `templates/wave-plan.md` | Wave decomposition planning |
| `knowledge/index.md` | Knowledge page catalog, selective loading |
| `knowledge/code-rules-mapping.md` | Code-to-rule lineage (S/A/C/W/ST taxonomy) |
| `knowledge/principle-mapping.md` | P0–P6 principle ↔ rule trace |

## Template Quick-Reference

`(legacy)` = REGISTERED but v9.0.0..v10.3.0 cycle did NOT invoke; preserved for backward compat; Phase B compose-not-define collapse deferred to v12.0+ per `.local/research/v11.0.0_patches/D-A-2.md` §1 audit.

| Template | Stages | Gate Type |
|----------|--------|-----------|
| research-only (legacy) | 3 | standard |
| design-only (legacy) | 3 | standard |
| hotfix (legacy) | 4 | standard |
| refactoring (legacy) | 5 | convergence |
| migration | 5 | convergence |
| spike-poc (legacy) | 3 | standard |
| documentation-only (legacy) | 3 | standard |
| security-audit (legacy) | 5 | convergence |
| feature-enhancement (legacy) | 7 | convergence |
| full-pipeline (legacy) | 8 | convergence |
| research-design-review-refine (legacy) | 4-5 | convergence |
| demo-showcase (legacy) | 6 | standard |
| performance-optimization (legacy) | 5 | convergence |
| dependency-setup (legacy) | 4 | standard |
| onboarding (legacy) | 4 | standard |
| skill-optimization | 6 | convergence |
| product-verification (legacy) | 8 | convergence |
| nines-assisted | 9 | convergence |
| self-update | 7 | convergence |
| repo-init | 5 | standard |
| entropy-cleanup (legacy) | 4 | standard |
| change-driven | 4 | convergence |

## Task Quality Score (L0 ONLY)

**L0 ONLY** — Subagents MUST NOT score. L0 evaluates the user's original request at workflow close (L1/L2/L3 reports carry no `quality_score` field — see §"Reporting completion"). Full rubric (4 dimensions × per-tier criteria + 📊 output template) loads on-demand from `references/task-quality-score.md` AFTER the last stage gate PASSES — this keeps the ~120-token scoring rubric out of the per-dispatch execution-loop context (v12.3.0 PV-03 closure for `.local/feedbacks/feedback_for_v12.1.1.md` #2). Operator-facing footer line MUST include the literal version string `DevolaFlow vX.Y.Z` per the §"Session Banner Contract" above.

## Operational Learnings — Session Pinning & Decay (v7.0.3+)
Persisted learnings (`.../learnings/operational.jsonl`) carry a confidence half-life (default 30 days per `DEFAULT_DECAY_HALF_LIFE_DAYS`): `decay_confidence()` applies `new_conf = conf - 0.5 * min(1, days_since_last_access / half_life)`, prunes entries below `DECAY_FLOOR=0.1`; `consolidate_session(session_id, session_learnings, path)` bumps matched entries by +0.05 at session end and appends new ones with `promotion_count=1` — stale entries decay while validated insights stay fresh. For cross-round convergence loops that must keep a specific insight in context regardless of confidence, call `pin_learning_for_session(key, stage, task_type, session_id, path)` — `load_relevant_learnings(..., session_id=...)` then surfaces pinned entries first. Reserve pinning for blockers (ADR-005 §3); legacy v1 entries parse unchanged, `last_accessed` lazily backfilled from `timestamp` on first decay.
