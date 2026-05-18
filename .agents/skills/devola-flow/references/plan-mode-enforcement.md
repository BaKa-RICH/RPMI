---
id: plan-mode-enforcement
version: "11.0.0"
purpose: >
  Plan-mode L0 operating contract: when a dispatcher detects plan mode, this
  reference defines the canonical plan output template, plan-mode rules,
  reinforcement-loop mechanics, and stagnation-escalation behavior. Pairs
  with the W-8 / SI-9 convergence-round reinforcement primitive in
  src/devolaflow/gate/reinforcement.py and the round-aware dispatch
  escalation in src/devolaflow/task_adaptive_selector.py.
tier: 2
token_estimate: 3400
last_updated: "2026-05-08"
---

# Plan-Mode Enforcement & Reinforcement Loop Contract

> **Tier-2 reference** — load when the dispatcher enters Plan Mode (Cursor
> SwitchMode `plan`, system_reminder "Plan mode is active", explicit user
> "build a plan" / "design first" / "/plan", or env
> `DEVOLAFLOW_PLAN_MODE=1` / filesystem marker `.devolaflow_plan_mode`),
> AND when L1/L2 build a round-N+1 dispatch carrying
> `applicable_rules.reinforcement` payload after a gate FAIL. SKILL.md
> §"Mode Awareness" + §"Reinforcement Rules" carry the 1-paragraph
> summaries; this file carries the full operating contract.

## 1. When to Load

This reference is loaded by L0/L1 dispatchers under any of the following
trigger conditions:

| Trigger                                                          | Source                                                                  | Effect                                                                |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `<system_reminder>` contains "Plan mode is active"               | host runtime (Cursor / Claude Code system message channel)              | force-loads §3 plan template + §4 constraints + §5 rules              |
| `SwitchMode` tool available + current mode is `plan`             | Cursor mode-switch event                                                | same as above                                                         |
| User says "build a plan" / "plan this" / "design first" / "/plan" | NL trigger phrase from prompt                                           | escalates `plan_mode_template` section to `critical` priority         |
| `DEVOLAFLOW_PLAN_MODE` in `{"1","true","yes","on"}`              | env var (per `task_adaptive_selector._detect_plan_mode`)                | applies `_PLAN_MODE_OVERRIDES` block (see §2)                         |
| `.devolaflow_plan_mode` file in cwd                              | filesystem marker (per `task_adaptive_selector._PLAN_MODE_MARKER`)      | same as env var                                                       |
| L1 / L2 building round-N+1 dispatch after gate FAIL              | `ProposalGenerator.generate_round_dispatch()` in `src/devolaflow/feedback.py` | force-loads §6 reinforcement mechanics + §7 convergence loop |

The reference is also discoverable via SKILL.md §"Reference Navigation
Guide" Tier-2 sub-table. L1/L2 agents that detect a mode-handoff arrival
(plan→agent, plan→hotfix) should load this reference to confirm rules
inheritance.

## 2. Plan Mode Detection (priority order)

When multiple signals are present, evaluate in this priority order:

1. `<system_reminder>` contains "Plan mode is active" → **PLAN MODE**
2. `SwitchMode` tool available and current mode is `plan` → **PLAN MODE**
3. User explicitly says "build a plan" / "plan this" / "design first" /
   "/plan" → **PLAN MODE**
4. Otherwise → **AGENT MODE** (default; full orchestration). **v6.1.5+
   runtime hook:** `select_context(plan_mode=True)` (or env
   `DEVOLAFLOW_PLAN_MODE=1`) escalates plan-relevant sections
   (`agent_hierarchy`, `decomposition_gate`, `rationalization_prevention`)
   to `critical` priority and upgrades `model_hint` to `quality`.

### 2.1 `_PLAN_MODE_OVERRIDES` block

Defined in `src/devolaflow/task_adaptive_selector.py` (lines 67-77):

```python
_PLAN_MODE_OVERRIDES: dict[str, Any] = {
    "section_priority_overrides": {
        "agent_hierarchy": "critical",
        "decomposition_gate": "critical",
        "rationalization_prevention": "critical",
        "convergence_loop": "important",
        "execution_protocol": "supplementary",
    },
    "compression_intensity": "minimal",
    "model_hint_override": "quality",
}
```

Effects on the dispatch payload:

- **section_priority_overrides** — the listed sections are bumped to the
  declared priority before budget allocation runs; this guarantees
  agent-hierarchy + decomposition-gate + rationalization-prevention always
  fit even when the budget is tight.
- **compression_intensity: minimal** — disables verbatim → bullet
  contraction in `compressor.py` so plan output retains structural
  fidelity.
- **model_hint_override: quality** — forces the L0 model selector to pick
  the highest-quality tier regardless of profile defaults (plans must not
  cut model corners on the most consequential dispatch — the one humans
  read).

### 2.2 R5 backward-compat for AGENT MODE

When neither plan-mode signal is present, AGENT MODE is active and ALL
sections render under their profile defaults (no overrides applied). The
`_PLAN_MODE_OVERRIDES` payload only injects when `apply_plan_mode_overrides()`
is called explicitly, so the AGENT MODE byte-output is identical to v6.0.x
pre-plan-mode behavior — verified by
`tests/test_task_adaptive_selector_plan_mode.py`.

## 3. Plan Output Template (verbatim contract)

When PLAN MODE is active, the L0 agent writes its plan into the canonical
output target (Cursor: `create_plan` tool; Claude Code: `plan.md`; raw:
markdown stdout) using the following template VERBATIM. The template is the
delegation contract that downstream L1/L2/L3 agents inherit; section
ordering, header levels, and field names must match exactly.

```text
# [Plan Title]

## Overview
[1-2 sentences] | Workflow: [type] | Gate: [standard/strict/relaxed]
Escalation: Task → Wave → Stage → Project → Human

## Execution Model
| Plan Element | Layer | Role |
|---|---|---|
| Stage dispatch | L0 Project | Selects workflow, sequences stages |
| Stage execution | L1 Stage | Decomposes into waves, runs gate |
| Wave dispatch | L2 Wave | Dispatches parallel tasks, checks conflicts |
| Task execution | L3 Task | **Only layer that does work** |

## Stages (gate-before-advance: no stage starts until predecessor gate PASS)

### S01: [primitive] — [name] [L0 dispatches → L1 executes]
- gate_type: [standard|convergence|passthrough] | threshold: [N] | coverage: [N]%
- max_rounds: [N] (convergence only) | on_stagnation: escalate
- context_profile: [type] | deliverables: [artifact paths → consumed by S02]
- L1_receives: stage definition, predecessor gate results, token budget ~5K

#### W01 (parallel | <=5 tasks | disjoint ownership) [L2 dispatches tasks]
| ID | Layer | Type | Task | Team | Writable (<=6) | Read-only | Est. | AC |
|----|-------|------|------|------|----------------|-----------|------|-----|
| T01 | L3 | impl | ... | Implement | ... | ... | ... | ... |

## Constraints Checklist
- [ ] Every task row is L3 (no L0-L2 performing work — P1 enforced)
- [ ] Stage headers specify L1 agent constraints (MUST NOT write code)
- [ ] Execution model section present with per-layer delegation rules
- [ ] Each wave: <=5 tasks, pairwise disjoint writable files
- [ ] Each stage: <=7 waves
- [ ] Task limits: impl <=30min, research <=45min, <=6 writable files
- [ ] Stage DAG: no cycles, gate-before-advance (D4)
- [ ] Convergence stages: max_rounds + stagnation rule specified
- [ ] Predecessors referenced by artifact path, not content copy

## Invariants (ALL enforced)
- P1: L0-L2 dispatch only; only L3 Tasks execute work
- P2: Token budgets — L0: ~3K, L1: ~5K, L2: ~4K, L3: ~8K
- P3: Inter-layer messages use typed YAML (TaskDispatch/StatusReport)
- P4: Every loop has max_iterations; failures: retry/escalate/abort
- P5: Layers communicate through artifact files, not conversation history
```

### 3.1 Field semantics (per-row contract)

- **Workflow type** — must match a registry entry (`workflow-system/agent/templates/registry.yaml`). Free-form names break `TemplateRegistry.load_template()` exact-match.
- **Gate** — `relaxed` (≥70 / ≥60% cov) | `standard` (≥85 / ≥80%) | `strict` (≥90 / ≥90%) | `audit` (≥95 / ≥90%) per `gate/profiles.py`.
- **Escalation** — always upward, never skip levels (per S-9 escalation invariant).
- **Layer** — L0 / L1 / L2 / L3 only; per the 4-layer hierarchy in SKILL.md §"4-Layer Agent Hierarchy". Mixed-layer task rows fail the constraints checklist.
- **gate_type** — `standard` (linear gate-before-advance), `convergence` (gen→verify loop with `max_rounds`), `passthrough` (no gate; rare; only for setup stages).
- **max_rounds** — defaults from gate profile: `relaxed=3`, `standard=5`, `strict=5`, `audit=7`. Required field on `convergence` stages.
- **on_stagnation** — `escalate` (default; emit ExceptionEscalation), `retry` (rare; only for transient I/O), `abort` (very rare).
- **context_profile** — string key into `workflow-system/agent/context_profiles.yaml::profiles`.
- **deliverables** — repo-relative artifact paths consumed by next stage (P5 contract — no shared memory).
- **Writable** — list of repo-relative paths the L3 may modify; pairwise disjoint within a wave (S-8 invariant).
- **Read-only** — list of repo-relative paths the L3 may read; intersect freely across wave tasks.

### 3.2 Multi-Step Plans (Multi-Horizon Reasoning)

Added v11.0.0 PV-01 per D-P-4 — `.local/research/v11.0.0_patches/D-P-4.md`. The §3 base
template assumes a single-horizon plan (one goal, stage-by-stage execution). Real plans
sometimes branch across horizons (e.g., "Phase A: research; Phase B: depending on
research outcome, EITHER design path X OR design path Y"). The convergence-loop machinery
ALREADY supports this at the wave level (`gate_type: convergence` + `max_rounds` +
`on_stagnation` + the round-aware escalation from §6 and §7). What was MISSING until
v11.0.0 PV-01 is the operator-facing documentation of HOW to express such plans cleanly
within the EXISTING fields. This sub-section closes that gap WITHOUT introducing new
schema fields — multi-horizon plans use the existing `gate_type`, `max_rounds`,
`context_profile`, `deliverables`, and `name` / `description` fields with two opt-in
text-annotation conventions (`[EXPLORE]` and `[REVISABLE: <stage-id>]`).

#### 3.2.1 — When multi-step plans apply

Apply §3.2 conventions when ANY of these triggers are present in the plan request:

* **Research-then-design**: phase A is exploratory (literature review / spike / probe);
  phase B's shape depends on phase A's outcome (e.g., "if benchmark X says approach Z is
  faster, do Z; else do Y").
* **Benchmark-driven branch decisions**: a stage's outcome decides between 2+ candidate
  paths in subsequent stages — the candidates need to be enumerable in the plan body so
  reviewers can reason about both branches before committing.
* **Spec-first-then-impl-or-defer**: phase A authors a spec; phase B is impl IFF the spec
  reaches some quality bar (e.g., SI-3 § score) — otherwise defer to next cycle.
* **Revise-after-stage-N-feedback**: a `convergence` stage's round-2 transition may
  invalidate the assumption that downstream stages were planned around — those downstream
  stages need an explicit revision marker so reviewers know they're tentative.

Single-horizon plans (one goal; stages are linear; no branching) do NOT need §3.2 — they
go straight to the §3 base template. §3.2 is OPT-IN.

#### 3.2.2 — Template extension (uses existing fields ONLY)

Multi-horizon plans express their structure through the EXISTING `stages × waves × tasks`
template by leveraging the following field combinations:

* **Exploratory probe stage** — set `gate_type: convergence` with `max_rounds: 2` and
  `on_stagnation: escalate` for stages whose outcome decides the next stage's shape.
  The convergence loop's W-8 / SI-9 reinforcement mechanism naturally accommodates the
  "round-2 outcome decides" semantics.
* **Profile flip per phase** — use the `context_profile` field to switch profiles between
  phases. Example: phase A uses `research` profile (heavy on exploratory tooling +
  semantic search); phase B uses `convergence_heavy` profile (heavy on gate verification
  + reinforcement). Profile flips are zero-cost (no schema change; just different
  context_profiles.yaml selections per stage).
* **Fork semantics in `deliverables`** — document the branch decision in the
  `deliverables` field by annotating which artifact is the BRANCH-DECISION INPUT for the
  next stage. Example: `deliverables: [research-report.md] (consumed by S02 — branch
  decision input determines path X vs path Y)`.

Zero new schema fields. The `lean-dispatch.yaml#layout_invariant.canonical_order`
remains at length 17 with positions 1-12 frozen per A-2.1. Multi-baseline byte test
(10/10) stays green by construction.

#### 3.2.3 — Plan-internal uncertainty annotation: `[EXPLORE]`

Annotate exploratory stages by prefixing the stage `name` text with `[EXPLORE]`.

```text
### S01: research — [EXPLORE] feasibility study of approach Z
- gate_type: convergence | threshold: 8.0 | coverage: N/A
- max_rounds: 2 | on_stagnation: escalate
- context_profile: research | deliverables: [feasibility-report.md]
                      (consumed by S02 — branch decision input)
- L1_receives: stage definition, predecessor gate results, token budget ~5K
```

This convention is OPT-IN — absence is canonical and equally valid. The annotation lives
in plain text within the existing `name` field; older plan parsers see it as part of the
stage name and ignore it. Operators who never use the convention emit single-horizon
plans that look identical to v8.4.1-era plans.

#### 3.2.4 — Plan-revision markers: `[REVISABLE: <stage-id>]`

Annotate `convergence` stages whose round-2 outcome may revise downstream stages by
appending `[REVISABLE: <downstream-stage-id>]` to the stage description.

```text
### S02: design — [EXPLORE] choose between path X and path Y [REVISABLE: S03]
- gate_type: convergence | threshold: 8.5 | coverage: N/A
- max_rounds: 2 | on_stagnation: escalate
- context_profile: convergence_heavy
- deliverables: [design-decision.md, chosen-path.md]
                      (consumed by S03 — implementation target)
- L1_receives: stage definition, S01 feasibility report, token budget ~5K
```

The `[REVISABLE: S03]` marker telegraphs to reviewers that S03's stage spec is tentative
until S02's round-2 (or final round) outcome lands. Reviewers should treat S03 as a
sketch to be re-validated rather than a committed plan.

If multiple downstream stages are revisable, list them comma-separated:
`[REVISABLE: S03, S04]`. Wildcard-like markers (`[REVISABLE: ALL_AFTER]`) are NOT
supported — the convention requires explicit stage-IDs so reviewers can reason about
which downstream blocks are tentative.

#### 3.2.5 — Worked example (research-then-design plan)

A 3-stage multi-horizon plan demonstrating both conventions:

```text
# Plan: Optimize compressor pipeline for 25%+ throughput

## Overview
Multi-horizon optimization research-then-design-then-impl. | Workflow: research-impl |
Gate: standard
Escalation: Task → Wave → Stage → Project → Human

## Execution Model
[4-row table from §3 verbatim — omitted for brevity]

## Stages

### S01: research — [EXPLORE] benchmark candidates A/B/C
- gate_type: convergence | threshold: 8.0 | coverage: N/A
- max_rounds: 2 | on_stagnation: escalate
- context_profile: research
- deliverables: [benchmark-report.md] (consumed by S02 — branch decision input)
- L1_receives: stage definition, token budget ~5K

#### W01 (parallel | <=3 tasks | disjoint ownership)
| ID | Layer | Type | Task | Team | Writable | Read-only | Est. | AC |
|----|-------|------|------|------|----------|-----------|------|-----|
| T01 | L3 | research | Benchmark candidate A | research | benchmarks/cand_a/ | src/compressor/ | 30min | report-shape match |
| T02 | L3 | research | Benchmark candidate B | research | benchmarks/cand_b/ | src/compressor/ | 30min | report-shape match |
| T03 | L3 | research | Benchmark candidate C | research | benchmarks/cand_c/ | src/compressor/ | 30min | report-shape match |

### S02: design — [EXPLORE] choose winning candidate [REVISABLE: S03]
- gate_type: convergence | threshold: 8.5 | coverage: N/A
- max_rounds: 2 | on_stagnation: escalate
- context_profile: convergence_heavy
- deliverables: [design-decision.md, chosen-path.md] (consumed by S03)
- L1_receives: stage definition, S01 benchmark report, token budget ~5K

### S03: impl — implement chosen path [REVISABLE: pending S02 decision]
- gate_type: standard | threshold: 8.5 | coverage: 80%
- context_profile: impl_heavy
- deliverables: [src/compressor/<chosen>.py, tests/test_<chosen>.py]
- L1_receives: stage definition, S02 chosen-path.md, token budget ~5K

## Constraints Checklist
[9-item checklist from §4 verbatim — omitted for brevity]

## Invariants
[5-item P1..P5 list from §3 verbatim — omitted for brevity]
```

The `[EXPLORE]` annotations on S01 + S02 telegraph that those stages are exploratory.
The `[REVISABLE: S03]` annotation on S02 telegraphs that S03's spec is tentative until
S02's round-2 outcome lands. The S03 description carries a reciprocal `[REVISABLE:
pending S02 decision]` so reviewers reading S03 in isolation see the tentative status
without backtracking to S02.

#### 3.2.6 — Cross-references

* §3 (Plan Output Template) — the base template all plans inherit from.
* §6 (Reinforcement Rules) — the round-N>1 mechanics that operate on `[EXPLORE]` stages.
* §7 (Convergence Loop Mechanics) — the `max_rounds` + `on_stagnation` semantics that
  underpin `[EXPLORE]` + `[REVISABLE]` plans.
* `.local/research/v11.0.0_patches/D-P-4.md` — the PDS authoring this sub-section.

## 4. Constraints Checklist (verbatim — must verify before finalizing plan)

The 9-item checklist is the gate the plan must clear before it can be
handed to L1 for execution. Each item is binary; partial-pass is not
acceptable.

1. **Every task row is L3** — no L0-L2 performing work. P1 enforced. Trivial
   exception (`< 20 lines`, single file) MAY be inlined into L0 with
   explicit `[trivial waiver]` annotation.
2. **Stage headers specify L1 agent constraints** — explicit "MUST NOT write
   code" / "MUST NOT execute Shell" line in every stage header.
3. **Execution model section present** — the 4-row table from §3 must be
   verbatim in the plan output (P1 reminder for downstream readers).
4. **Each wave: ≤5 tasks, pairwise disjoint writable files** — wave
   coordinator (L2) verifies disjointness at dispatch; conflict detection
   is O(|tasks|²) per wave. The 5-task ceiling matches L2 budget (~4K
   tokens) — exceeding it forces the wave to split.
5. **Each stage: ≤7 waves** — stage dispatcher (L1) verifies. Exceeding the
   7-wave ceiling forces stage split (often resolved by introducing an
   intermediate `gate` primitive).
6. **Task limits: impl ≤30min, research ≤45min, ≤6 writable files** —
   approximate budget; not enforced at runtime but used as a planning
   sanity check. Tasks exceeding 30min are usually candidates for
   sub-decomposition.
7. **Stage DAG: no cycles, gate-before-advance (D4)** — the stage graph
   must be a DAG; a cycle (e.g. design → impl → design) must be modeled
   as a single `convergence` stage with `max_rounds`. D4 = "no stage
   advances until predecessor gate PASS" per `decomposition-gate.md`.
8. **Convergence stages: max_rounds + stagnation rule specified** — every
   `gate_type: convergence` stage MUST have both fields populated; missing
   either is a P4 violation (no infinite loops).
9. **Predecessors referenced by artifact path, not content copy** — P5
   invariant. Plans that embed predecessor content directly violate
   context isolation and break the cached-prefix invariant.
10. **Cascade depth (STANDARD+)** — every plan whose Execution Model
    targets STANDARD or COMPLEX complexity (per
    `change_activation.classify_complexity` →
    `change_activation.cascade_requirement` returning `CASCADE_REQUIRED`)
    MUST contain at least one L1 Stage row AND at least one L2 Wave row
    BEFORE any L3 Task row. SIMPLE / TRIVIAL plans inherit item #1's
    `[trivial waiver]` carve-out and MAY collapse to a single L3 row
    directly under L0. v11.1.0 PV-04 NEST sub-fields
    `gate.cascade_required: bool` + `gate.cascade_min_layers: int` carry
    the signal in the dispatch payload (per A-2.3 NEST decision rule);
    PV-05 Architecture rule A-7 promotes this from soft check to strict
    enforcement.

The L0 agent runs the checklist as a self-verify before emitting the plan.
Any fail blocks the plan emission and forces revision.

## 5. Plan Mode Rules — DO and DO NOT

### 5.1 DO

- Use **read-only tools** for plan research: Read, Glob, Grep,
  SemanticSearch (allowed under L0 in plan mode per `_PLAN_MODE_OVERRIDES`).
- Emit the plan via `create_plan` (Cursor) or write `plan.md` (Claude
  Code). Other clients: emit raw markdown to stdout under a `# Plan` H1.
- Embed stage→wave→task decomposition with file ownership and AC for every
  L3 row.
- Annotate each stage's `gate_type`, `context_profile`, and convergence
  parameters (`max_rounds` + `on_stagnation`).
- Annotate every plan element with its delegation layer (L0/L1/L2/L3) so
  downstream readers can audit P1 compliance.
- Verify the §4 Constraints Checklist (especially P1 enforcement items)
  before finalizing.
- **Use the cascade chain L0 → L1 → L2 → L3 for STANDARD+ plans**
  (per §4 item #10 + v11.1.0 PV-04 schema NEST `gate.cascade_required`);
  collapse to single-L3 only for TRIVIAL/SIMPLE per item #1's
  `[trivial waiver]` carve-out.
- Cite predecessor artifacts by repo-relative path (S-2). External
  references use the GitHub URL (S-7).

### 5.2 DO NOT

- Do **NOT** dispatch tasks, write code, run tests, or modify files —
  this violates P1 + the plan-mode operating contract.
- Do **NOT** start execution until the user explicitly approves the plan
  (per the v3.x plan-mode-enforcement contract; user approval is the
  hand-off signal from PLAN MODE → AGENT MODE).
- Do **NOT** over-decompose (the 30min impl / 45min research budget is a
  ceiling, not a target — many tasks are 10-15min). Over-decomposition
  inflates wave count and breaks the ≤7-waves-per-stage invariant.
- Do **NOT** embed tool calls in the plan body — the plan is a
  declarative contract, not an executable script.
- Do **NOT** select model tier without rationale — `model_hint` defaults to
  `inherit`; explicit overrides need a per-task justification annotation.
- Do **NOT** skip the §4 Constraints Checklist. Plans that elide the
  checklist break downstream gate evaluation.
- Do **NOT** copy predecessor content into the plan body. Cite by path
  per P5.

### 5.3 Cursor-specific notes

When running under Cursor, the `SwitchMode` tool is available. The L0 agent
SHOULD call `SwitchMode(target_mode_id="plan")` if the host signals plan
intent but the runtime mode is still `agent`. Conversely,
`SwitchMode(target_mode_id="agent")` is the explicit hand-off after user
approval (do not auto-call without user consent).

### 5.4 Claude Code-specific notes

When running under Claude Code, plan output goes to `plan.md` at the
working-directory root. The Claude Code TUI auto-renders the plan in a
side panel. The user-approval signal is a follow-up message containing
"approve" / "go ahead" / "execute" — at which point L0 transitions to
AGENT MODE and starts dispatch.

### 5.5 Feedback Ingestion (v9.1.1+)

L0 plan mode MUST consume `WorkspaceContext.recent_feedbacks`
automatically when scanning the consumer repo. The latest 3 feedbacks
(by mtime descending) are surfaced in plan-mode reasoning to anchor
proposals against the user's accumulated voice.

**Mechanism:**

1. At plan-mode entry, L0 calls
   `devolaflow.workspace_context.scan_workspace(repo_root)` (the
   read-only discovery API shipped in v9.1.1 PV-01 — see
   `references/agent-workspace.md` §"When to Engage").
2. The returned `WorkspaceContext.recent_feedbacks` tuple holds up to 3
   `Path` objects pointing at `.local/feedbacks/feedback_for_v*.md`,
   ordered by `os.stat().st_mtime` descending (newest first). The cap
   matches `_RECENT_FEEDBACKS_LIMIT = 3` in
   `src/devolaflow/workspace_context.py` — older feedback files
   remain on disk but are not auto-loaded into the dispatch context
   (token-budget reason: the 3 newest carry the highest signal-to-noise
   for the imminent plan).
3. L0 reads each path with the standard `Read` tool (allowed under
   plan mode per §5.1) and extracts the user's themes. The themes feed
   the plan's "Overview" + "Stages" sections so the plan output reflects
   the user's accumulated voice rather than a fresh interpretation of
   the latest prompt only.
4. Themes are NOT copied verbatim into the plan body (P5 / S-2 /
   no-content-copy invariant). Cite by repo-relative path
   (`.local/feedbacks/feedback_for_vX.Y.Z.md` §<heading>) instead.

**v9.1.1 PV-01 ships the discovery API only — automatic ingestion at
plan-mode entry is the v9.1.4 PV-04 deliverable** (per the v9.2.0
cycle plan). The S-5-compliant default — no auto-write side effects —
applies regardless of PV.

#### Automatic Ingestion at Plan-Mode Entry (v9.1.4+)

Starting in v9.1.4 (PV-04 of the v9.2.0 cycle), L0 plan mode MUST
automatically ingest the `WorkspaceContext.recent_feedbacks` summary
when entering plan mode AND surface ≤ 5 extracted themes (≤ 30 chars
each) in the dispatch payload's `change_context.prior_feedback_themes`
NEST sub-field (per A-2.3 — the canonical_order length stays at 16,
no new top-level dispatch key was added). The contract:

1. **Discovery call** — at plan-mode entry, L0 calls
   `devolaflow.workspace_context.scan_workspace(repo_root)` and reads
   `WorkspaceContext.recent_feedbacks` (the tuple is already capped at
   `MAX_FEEDBACKS_RETURNED == 3` per the v9.1.1 PV-01 design — older
   feedbacks remain on disk but are not auto-loaded).
2. **Read with the standard `Read` tool** — for each of the (≤ 3)
   feedback paths, L0 reads the file with the standard `Read` tool
   (allowed under plan mode per §5.1 — no new tool permission needed).
3. **Theme extraction (L0 LLM contract — normative)** — extract ≤ 5
   short noun/verb phrases (each ≤ 30 chars; lowercase
   `snake_case` preferred) from the H1/H2 headings, key bullet
   markers, and recurring concept terms across the feedback bodies.
   Examples: `handoff_auto_write`, `slash_commands_cli`,
   `workspace_discovery`, `memory_consultation`,
   `spec_bootstrap`. Themes that are NOT short noun/verb phrases
   (e.g., full sentences, prose paragraphs) violate the
   `prior_feedback_themes` schema cap.
4. **Surfacing** — populate the dispatch payload's
   `change_context.prior_feedback_themes` sub-field (NEST per A-2.3 —
   schema documented in
   `schemas/lean-dispatch.yaml#lean_format_spec.change_context.prior_feedback_themes`)
   with the extracted theme list. Cite each source by repo-relative
   POSIX path per S-2 (e.g.,
   `.local/feedbacks/feedback_for_v9.1.3.md` §"What's New"). NEVER
   embed absolute filesystem paths.

**Why a NEST extension and not an APPEND?** Per A-2.3 nest-vs-append
decision rule, the new sub-field rides the existing `change_context`
position 16 block — the sub-field is independently optional and
modifies how an existing block is interpreted (the L3 task agent
treats `change_context` as the binding for in-flight workspace state
PLUS, when present, the user-voice anchors). This preserves the I-8
invariant: `canonical_order` length STAYS AT 16 and `version` STAYS
AT 5. The v8.3.0 PV-05 + v8.4.0 + v9.2.0 multi-baseline byte tests
in `tests/test_layout_invariant_multi_baseline.py` continue to PASS
without modification.

**Activation gate (W-20 reuse)** — feedback ingestion auto-runs in
plan mode by default (no env-flag required for the read-only
discovery + theme extraction; the activity is a `Read` operation L0
already performs in plan mode). The companion memory-case
consultation (`change_context.memory_case_hits`) is gated by
`DEVOLAFLOW_MEMORY_ROUTER=1` (REUSED per W-20 — no new env-flag).
The third sub-field, `source_of_truth_excerpt`, is L0-discretion
(reads `.local/memory/specs/<domain>/spec.md` when `spec_delta_target`
is set on the change folder).

**Coverage anchor** — `tests/test_feedback_ingestion_plan_mode.py`
pins this contract: empty-feedbacks → empty list, S-2 repo-relative
paths via `WorkspaceContext.to_summary_dict()`, the 3-feedback cap
honored, AND the §5.5 sub-section content asserted verbatim (so a
future doc rewrite that drops the contract markers fails CI
immediately).

## 6. Reinforcement Rules (W-8 / SI-9) — Mechanism + L3 Obligation

When a stage gate FAILS (composite_score < threshold OR blocker count > 0
OR coverage < threshold), the next round's dispatch carries
`applicable_rules.reinforcement` — top-5 prior-round findings (severity ≥
major) injected as MUST-fix mandates.

### 6.1 `applicable_rules.reinforcement` payload shape

```yaml
applicable_rules:
  reinforcement:                          # max 5 entries; severity-filtered
    - id: "R-001"
      severity: blocker | critical | major
      finding: "verbatim from prior-round gate output"
      source_file: "repo/relative/path.py"     # optional; for L3 to locate
      source_line: 142                          # optional
      remediation_hint: "1-sentence delta"      # optional
    # ... up to 4 more entries ...
```

**Severity filter:** blocker > critical > major; ignore minor / info /
warn from reinforcement (those go to `informational` instead). **Selection
order:** by severity descending; within same severity, by gate
chronological order (earliest finding first). **Deduplication:** identical
`(severity, source_file, source_line)` tuples merge into one entry with
combined `finding` + `remediation_hint` text.

### 6.2 L3 obligation

L3 Task Agents that receive a dispatch with non-empty
`applicable_rules.reinforcement` MUST:

1. Address ALL listed reinforcement rules **before** any new work. Failure
   to address any rule = automatic blocker in the next gate (the gate
   evaluator parses the L3 status report for explicit closure of each
   reinforcement entry).
2. Emit per-rule closure markers in the StatusReport's `delta` block:
   `closes_reinforcement: ["R-001", "R-003"]`.
3. If a rule cannot be closed in this round (e.g. dependency on another
   wave's task), explicitly emit `defers_reinforcement: ["R-002 — blocked
   on TaskAgent T03 deliverable"]` so the L1 gate can evaluate
   stagnation correctly.

### 6.3 Python API surface

Two source-of-truth modules:

- `src/devolaflow/gate/reinforcement.py` — `findings_to_reinforcement(findings, max_entries=5)` filters, sorts, and deduplicates findings into the reinforcement payload. ~227 LOC at v8.4.x.
- `src/devolaflow/feedback.py` — `ProposalGenerator.generate_round_dispatch(round_n, prior_findings, base_dispatch)` merges prior-round findings into `base_dispatch.applicable_rules.reinforcement` and bumps the dispatch payload's round counter.

The two are always called together by L1 between gate evaluation and
round-N+1 wave dispatch. Verified end-to-end by
`tests/test_dispatch_emission_runs_hooks.py` and
`tests/test_no_ghost_features.py::test_round_aware_dispatch_escalation_exists`.

### 6.4 Round-aware escalation table

`task_adaptive_selector._ROUND_ESCALATION_DEFAULTS` defines the
per-round-number context budget bumps and `model_hint` upgrades:

| Round | Budget multiplier | `model_hint`     | Notes                                        |
| ----- | ----------------- | ---------------- | -------------------------------------------- |
| 1     | 1.0               | `inherit`        | base round (no reinforcement carried)        |
| 2     | 1.0               | `inherit`        | first reinforcement round; budget unchanged  |
| 3     | 1.2               | `quality`        | +20% budget; force-quality model             |
| 4+    | 1.2               | `quality`        | sustained at +20% / quality                  |

L1 applies the table when calling `generate_round_dispatch()`.

## 7. Convergence Loop Mechanics

The Gen-Verify loop is the convergence wave's runtime topology. It applies
to `gate_type: convergence` stages — typically `review+fix`, `test+fix`,
`benchmark+optimize`, `design+critique`, and `verify+remediate`.

### 7.1 Loop structure

1. L2 Wave dispatches **generator** task + **verifier** task in parallel.
   Generator produces an artifact; verifier evaluates it against
   `acceptance_criteria` (lifted from the wave dispatch payload).
2. Verifier emits `{PASS | FAIL + feedback}`. PASS → wave done; L1 marks
   stage gate PASS. FAIL → L1 calls `generate_round_dispatch()` (see §6.3)
   to build round N+1 dispatch carrying the verifier's findings as
   reinforcement payload.
3. Round N+1 generator addresses the reinforcement (see §6.2 L3
   obligation), produces refined artifact. Verifier re-evaluates.
4. Loop terminates on **any** of:
   - verifier emits PASS (success path; gate PASS),
   - `round_n >= max_rounds` (escalate per §8),
   - composite_score Δ < `stagnation_epsilon` over 2 rounds (stagnation;
     escalate per §8),
   - L1 receives ExceptionEscalation from any task (immediate halt).

### 7.2 `max_rounds` defaults per gate profile

| Profile    | `max_rounds` | Rationale                                                   |
| ---------- | ------------ | ----------------------------------------------------------- |
| `relaxed`  | 3            | low-stakes content; cheap to escalate after 3 attempts      |
| `standard` | 5            | balanced default; matches W-8 / SI-9 hard cap               |
| `strict`   | 5            | same hard cap; higher per-round bar (composite ≥ 90)        |
| `audit`    | 7            | release-blocking; willing to spend more rounds for ≥ 95     |

The `max_rounds` value MUST be specified on every `convergence` stage; the
profile default is a fallback only.

### 7.3 Stagnation detection

Stagnation = composite_score Δ < `stagnation_epsilon` (default 1.0) over
**2 consecutive rounds** with no new blocker introduced. The 2-round
window prevents single-round noise (e.g. a verifier flip-flop) from
falsely triggering escalation.

### 7.4 Verifier criteria sourcing

The verifier reads `acceptance_criteria` from the wave dispatch payload
(per `schemas/lean-dispatch.yaml#layout_invariant.canonical_order`
position `accept`). Acceptance criteria authoring guidance lives in
`references/decomposition-gate.md` §"Acceptance Criteria". For
`convergence` stages, AC SHOULD be expressed as testable assertions
(boolean predicate) rather than descriptive prose, so the verifier can
emit unambiguous PASS / FAIL.

## 8. Stagnation Escalation (P4 Bounded Retry)

When the convergence loop terminates due to `max_rounds` exceeded OR
stagnation, L1 emits an `ExceptionEscalation` upward to L0 per the P4
bounded retry contract.

### 8.1 P4 classification

Every loop has a `max_iterations` ceiling. Every failure triggers a
classified response:

| Classification | Trigger                                        | Action                                                        |
| -------------- | ---------------------------------------------- | ------------------------------------------------------------- |
| `retry`        | transient I/O fault; round_n < max_rounds      | re-dispatch same round payload (no reinforcement bump)        |
| `escalate`     | max_rounds reached OR stagnation OR blocker    | emit ExceptionEscalation upward (Task → Wave → Stage → Project → Human) |
| `abort`        | unrecoverable schema violation OR P1 violation | halt entire workflow; surface to human immediately            |

### 8.2 Escalation chain

The escalation chain is always upward, never skip levels:

```text
L3 Task → L2 Wave → L1 Stage → L0 Project → Human
```

L2 receives Task escalations and decides: address inline (e.g. retry with
adjusted dispatch) or propagate to L1. L1 receives Wave escalations and
decides: re-dispatch wave or propagate to L0. L0 receives Stage
escalations and decides: re-dispatch stage with relaxed profile, or
present options to human. Skipping levels (e.g. L3 → L0 direct) breaks
the audit trail and is a P4 violation.

### 8.3 ExceptionEscalation schema

```yaml
exception_escalation:
  source_id: "<task_id|wave_id|stage_id>"
  source_layer: "L1|L2|L3"
  reason: "max_rounds_exceeded|stagnation|p1_violation|p4_violation|unrecoverable_error"
  classification: "retry|escalate|abort"
  context:
    round_n: <int>                  # only for max_rounds_exceeded / stagnation
    composite_history: [<float>]    # last 5 rounds, oldest first
    blocker_findings: [<str>]       # list of blocker-severity findings
    last_dispatch_id: "<dispatch_id>"
  remediation_hint: "<1-sentence>"  # optional; L1's best-guess fix
```

The schema is canonical per `schemas/exception-escalation.schema.yaml`
(when present) and consumed by L0's `gate.scorer.evaluate_escalation()`.

### 8.4 Per-team escalation routing

Default routing (configurable per `context_profiles.yaml::profiles.<name>.escalation_routing`):

| Team       | Primary escalation target | Rationale                                      |
| ---------- | ------------------------- | ---------------------------------------------- |
| Research   | Stage Agent (L1)          | research blocks usually need scope re-decision |
| Design     | Project Agent (L0)        | design blocks usually need workflow re-routing |
| Implement  | Wave Agent (L2)           | impl blocks often resolve in adjacent wave     |
| Test       | Wave Agent (L2)           | test blocks usually mean code-side fix needed  |
| Review     | Stage Agent (L1)          | review blocks usually mean criteria revision   |

## 9. Cross-References

### 9.1 SKILL.md sections (1-paragraph summaries)

- `## Mode Awareness` — Plan-mode detection priority order + AGENT MODE
  default + `_PLAN_MODE_OVERRIDES` runtime hook.
- `### Reinforcement Rules (v5.1+)` — 1-paragraph summary of §6 above.
- `### Wave Coordination Modes` — Gen-Verify mode selection + topology
  override.
- `## Gate Mechanism` — composite_score formula + per-dimension scoring +
  pass conditions + gate profiles.

### 9.2 Source files (Python API)

- `src/devolaflow/gate/reinforcement.py` — `findings_to_reinforcement()` (W-8 module).
- `src/devolaflow/feedback.py` — `ProposalGenerator.generate_round_dispatch()`.
- `src/devolaflow/task_adaptive_selector.py` — `_PLAN_MODE_OVERRIDES`, `_ROUND_ESCALATION_DEFAULTS`, `apply_plan_mode_overrides()`.
- `src/devolaflow/lifecycle/dispatcher.py` — dispatch event emission +
  `pre_dispatch` / `post_dispatch` hook orchestration.
- `src/devolaflow/lifecycle/__init__.py` — `run_hooks(event, payload, *, strict=False)`.

### 9.3 Schemas

- `schemas/lean-dispatch.yaml` — canonical dispatch payload (lean format);
  `applicable_rules.reinforcement` field at canonical_order position
  `rules`.
- `schemas/lean-report.yaml` — StatusReport schema; `delta.closes_reinforcement`
  / `defers_reinforcement` field semantics.

### 9.4 AGENTS.md rules

- `AGENTS.md` §"P1 Dispatcher-Not-Implementer" — L0-L2 may NOT execute
  work.
- `AGENTS.md` §"P4 Bounded Retry" — every loop has a `max_iterations`
  ceiling.
- `AGENTS.md` §"W-8 — Convergence Round Reinforcement (SI-9)" —
  reinforcement-loop discipline + 2-round stagnation rule.
- `AGENTS.md` §"S-1 — Dispatcher-Not-Implementer Invariant" — Soul-rule
  invariant; trivial exception (single file, < 20 lines) does NOT apply
  to plan mode (plans are inherently dispatcher artifacts).

### 9.5 Testing surface

- `tests/test_no_ghost_features.py::test_round_aware_dispatch_escalation_exists` — pins the round-aware dispatch wiring.
- `tests/test_no_ghost_features.py::test_reinforcement_findings_function_exists` — pins `findings_to_reinforcement()` callable.
- `tests/test_dispatch_emission_runs_hooks.py` — end-to-end pre_dispatch / post_dispatch hook coverage; landed in v8.4.4 PV-04 per
  `.local/research/adr/v9-ADR-004-lifecycle-wiring-and-s10.md`.
- `tests/test_task_adaptive_selector_plan_mode.py` — `_detect_plan_mode()`
  + `_PLAN_MODE_OVERRIDES` application coverage.

### 9.6 External

- DevolaFlow repository: https://github.com/YoRHa-Agents/DevolaFlow
- NineS evaluator (used for SI-2 self-eval): https://github.com/YoRHa-Agents/NineS

## 10. Soul Rule S-10 — Prompt-Side Governance Contract Embedding (v8.4.4 PV-04)

Every dispatch payload returned by
`src/devolaflow/feedback.py::ProposalGenerator.generate_round_dispatch`
MUST be visible to the lifecycle hook chain
(`pre_dispatch` → `post_dispatch`) via
`devolaflow.lifecycle.run_hooks(event, payload, strict=False)`.

### 10.1 Why this rule

Prior to v8.4.4 the dispatcher ran the hook chain only at validation
checkpoints (manual invocations from tests + CLI ops). Round-N+1
dispatches emitted from `generate_round_dispatch` bypassed it entirely
— a dead-wire identified in v6.0.3's highest-ROI retro precedent and
escalated to BLOCKER C-03 in `.local/research/v9.0.0_gap_analysis.md`
§3.1. S-10 codifies the wired-up state and lifts it into the Soul-set
so future refactors cannot regress.

### 10.2 Hook chain semantics

| Slot | Default handler | Role |
|---|---|---|
| `pre_dispatch` | `validate_dispatch` (+ `validate_owned_files` extra) | validate dispatch CONTENT (acceptance criteria, owned files, schema compliance) |
| `post_dispatch` | `post_dispatch` permissive no-op | future-extensibility slot for governance contracts (Soul-set version embedding, rule-manifest URL, reinforcement state) — actual content lands in PV-07 with the rule-corpus selectivity slice |

### 10.3 R5 strict triple codification

1. **Hook**: `lifecycle/__init__.py::DEFAULT_EVENTS` includes both
   `pre_dispatch` and `post_dispatch`; both wired to permissive
   defaults that NEVER mutate the payload.
2. **Schema**: `feedback.py::generate_round_dispatch` calls the hook
   chain on every return path (round-1 pass-through, no-reinforcement,
   reinforcement-applied).
3. **Test**: `tests/test_dispatch_emission_runs_hooks.py` asserts the
   hook is invoked exactly once per dispatch in permissive mode AND
   that the returned dispatch is byte-identical to the control when no
   extras register.

### 10.4 L3 obligation

L3 Task Agents do NOT need to interact with the hook chain directly —
the wiring is an L0/L1/L2 dispatcher concern. L3 Task Agents may
register custom `post_dispatch` extras when they need to inject
observability or governance side-effects, but the registration is
runtime-ephemeral and MUST clean up after the task completes
(`lifecycle.clear_hooks(POST_DISPATCH_EVENT)`) so future dispatches
see the canonical no-op default.
