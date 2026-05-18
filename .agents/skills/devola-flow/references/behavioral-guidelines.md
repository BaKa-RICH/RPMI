---
id: "agent/references/behavioral-guidelines"
version: "1.0.0"
purpose: >
  L3 Task Agent behavioral guidelines (think_first, simplicity_check,
  surgical_scope, goal_loop) — the 4 Karpathy-derived primitives that
  shape Agent execution discipline. Loaded selectively into the L3
  dispatch payload via the top-level ``behavioral_guidelines`` field
  declared in ``schemas/lean-dispatch.yaml`` (canonical position 14).
triggers:
  - "L3 Task Agent execution"
  - "behavioral guideline injection"
  - "Karpathy behavioral primitives"
  - "code quality discipline"
tier: 2
token_estimate: 1100
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-04-23"
---

# Behavioral Guidelines (L3 Task Agent)

L3 Task Agents inherit four behavioral primitives from the dispatch payload's
top-level ``behavioral_guidelines`` field. The four rules are derived from the
Karpathy nano-agent skill set (https://github.com/forrestchang/andrej-karpathy-skills)
and adapted to DevolaFlow's 4-layer hierarchy. Each rule is opt-in per profile
(see ``workflow-system/agent/context_profiles.yaml``), severity-classified, and
self-checkable so a Task Agent can verify compliance without invoking Review.

## Field Shape

```yaml
behavioral_guidelines:
  think_first: bool              # Plan-before-code discipline (Karpathy "Think First")
  simplicity_check: bool         # Reject over-engineering (Karpathy "Simplicity First")
  surgical_scope: str            # 'line' | 'function' | 'module' (Karpathy "Surgical Edits")
  goal_loop: bool                # Re-anchor to user intent each round (Karpathy "Goal-Driven")
  no_llm_for_deterministic: bool # v12.2.0 — deterministic decisions in code (Mnimiy Rule 5)
  surface_conflicts: bool        # v12.2.0 — surface pattern disagreement (Mnimiy Rule 7)
  convention_first: bool         # v12.2.0 — match existing pattern (Mnimiy Rule 11)
```

The field is OPTIONAL in the dispatch payload. When absent, L3 agents fall
back to the v7.x default (no behavioral injection — byte-identical to the
v7.x dispatch shape and preserves the v7.0.0 cache-layout golden baseline).
When present, the dispatcher's ``select_context()`` helper selectively loads
the matching rule sections from this file into the L3 task agent context.

## Rule Application Matrix

| Profile     | think_first | simplicity_check | surgical_scope | goal_loop | no_llm_for_deterministic | surface_conflicts | convention_first | Rationale |
|-------------|-------------|------------------|----------------|-----------|--------------------------|-------------------|------------------|-----------|
| trivial     | false       | false            | line           | false     | false                    | false             | false            | < 20 line edit; full ceremony unwarranted |
| simple      | true        | false            | function       | false     | false                    | false             | true             | 1-3 file scope; require plan-first + pattern hygiene |
| standard    | true        | true             | function       | false     | true                     | true              | true             | 3-10 file scope; add cross-file consistency audits |
| complex     | true        | true             | module         | true      | true                     | true              | true             | 10+ files; full audit + re-anchor goal each round |

Profile authors override per-profile defaults via
``context_profiles.yaml#profiles.<name>.behavioral_guidelines``. Missing
keys inherit the matrix above per complexity tier classification.

## Rule 1 — think_first

**id**: `BG-001` | **severity**: warn | **applies when**: `think_first=true`

Before producing any code edit, the L3 Task Agent MUST surface an explicit
plan to the dispatcher. The plan is captured in the StatusReport's
``plan_artifact`` field (≤ 5 bullets, each ≤ 20 words) and rendered before
the first ``Write`` / ``StrReplace`` / ``Shell`` tool call.

**Rendered guidance** (injected into L3 dispatch when active):

> Before any source modification, emit a numbered plan describing: target
> files, key abstractions you will introduce or change, the acceptance
> criteria your changes will satisfy, and any assumptions that block work.
> One-line rationale per bullet. Reject the temptation to "just start
> coding" — plan friction is plan correctness.

**Self-check questions**:

1. Did I list every file I intend to write before the first edit?
2. Did I name every new function / class / data type I am introducing?
3. Did I cite the acceptance criterion each change addresses?

**When to skip**: Single-file ≤ 20-line trivial fixes (P1 trivial exception).

## Rule 2 — simplicity_check

**id**: `BG-002` | **severity**: warn | **applies when**: `simplicity_check=true`

Before merging a candidate solution, the L3 Task Agent MUST run a 3-question
over-engineering audit. Each YES is a candidate WARNING in the StatusReport
findings list (severity=major if 2+ YES, blocker if all 3 YES).

**Rendered guidance** (injected into L3 dispatch when active):

> Audit your solution against three over-engineering smells before commit:
> (1) Did I introduce abstractions (classes, factories, registries) for a
> single use case? (2) Did I add configuration knobs nobody asked for?
> (3) Did I write code that exists "in case" rather than "because"? Each
> YES is a finding. The minimal solution that passes acceptance criteria
> wins; cleverness without justification loses.

**Self-check questions**:

1. Could I delete this abstraction and inline the call site without harm?
2. Is every new config field consumed by a passing test?
3. Did I write code paths that have no AC reference?

**When to skip**: Hotfix profile (urgency outweighs purity).

## Rule 3 — surgical_scope

**id**: `BG-003` | **severity**: blocker | **applies when**: `surgical_scope` set

Limits the file-system blast radius of a single L3 task. The value is one
of three tiers; violation classifies as blocker because it directly breaches
the wave-level disjoint-ownership invariant (P2).

| Value     | Constraint | When applied | Verifier |
|-----------|------------|--------------|----------|
| `line`    | Edits restricted to declared line ranges within owned files | Trivial-tier hotfix | Future v8.2.0 work — currently aliased to ``function`` |
| `function`| Edits restricted to declared function bodies in owned files | Standard impl / refactor | Walk diff hunks; reject hunks that cross declared function boundaries |
| `module`  | Edits restricted to ``owned_files`` set; no out-of-scope writes | Complex multi-wave impl | Compare diff filename set against ``owned_files`` |

**Rendered guidance** (injected into L3 dispatch when active):

> Your edits MUST stay within the declared ``surgical_scope`` tier. A
> diff hunk that escapes the tier is a blocker finding, not a stylistic
> choice. If you discover an out-of-scope edit is required, surface a
> ``ScopeEscalation`` exception to the wave agent rather than silently
> widening the diff.

**Self-check questions**:

1. Did every diff hunk stay inside an owned file?
2. Did every diff hunk stay inside the declared function (when applicable)?
3. Did I escalate any required scope expansion BEFORE editing?

**Note** (v8.2.0 PV-04): `line`-tier verification is implemented. When the
resolved `behavioral_guidelines` block carries `surgical_scope='line'`,
`_select_behavioral_sections` augments the dispatch context with the
verbatim list of criteria documented under
[Line-Level Behavioral Criteria](#line-level-behavioral-criteria). The
v8.0.0 P-08 deferred AC #2 closes here; `function` and `module` tier
behaviour stays byte-identical to v8.0.0-p08 (R5 discipline).

## Rule 4 — goal_loop

**id**: `BG-004` | **severity**: warn | **applies when**: `goal_loop=true`

In multi-round convergence work the L3 Task Agent MUST re-anchor each round
to the original user goal verbatim before consuming the prior round's
findings. This counters "goal drift" where successive rounds optimise for
findings instead of intent.

**Rendered guidance** (injected into L3 dispatch when active):

> At the head of each round (round_num >= 2), restate the original user
> request VERBATIM in your StatusReport's ``goal_anchor`` field. Then read
> the prior round's findings. If the findings would push your work AWAY
> from the goal anchor, surface a ``GoalDriftWarning`` finding rather
> than complying.

**Self-check questions**:

1. Did I quote the original user request word-for-word at round start?
2. Did I cross-check each new finding against the goal anchor?
3. Did I flag findings that conflict with the goal rather than silently
   complying?

**When to skip**: Single-round (round_num == 1) tasks; the goal is implicit
in the dispatch and re-anchoring adds no signal.

## Rule 5 — no_llm_for_deterministic

**id**: `BG-005` | **severity**: warn | **applies when**: `no_llm_for_deterministic=true`

Deterministic decisions — retry policies, routing thresholds, escalation
boundaries, validation rules, fixed constants — MUST live in deterministic
code, NOT in LLM-driven prompts. The model decides differently each run
because the prompt context shifts; coding the decision behind a pure
function gives the L3 Task Agent a stable contract to call.

Added in v12.2.0 PV-03 per the Mnimiy May-2026 X article §4 Rule 5
([article cross-walk](.local/research/v12.2.0_gap_analysis.md) §2 D-2).
The article's source moment: *"A 'decide whether to retry on 503' LLM
call worked for two weeks, then started flaking because the model began
reading the request body as context for the decision. The retry policy
went random because the prompt was effectively random."*

**Rendered guidance** (injected into L3 dispatch when active):

> Before adding any LLM call inside your implementation, audit whether
> the decision is DETERMINISTIC (same inputs → same outputs by spec) or
> GENERATIVE (requires natural-language reasoning). Deterministic
> decisions belong in a pure function — write the function, write a
> unit test, and call it from the agent path. Generative decisions
> may legitimately call the model. If unsure, default to deterministic
> code — model calls are 100-1000x slower AND non-reproducible.

**Self-check questions**:

1. Did I add an LLM call where a `dict.get()` / `if-elif` / regex / table
   lookup / pure function would give a stable answer?
2. Did I justify each LLM call by the need for natural-language inference
   (free-form text generation, semantic comparison, intent classification)?
3. Did I write tests that exercise the deterministic-decision code path
   directly, without invoking the model?

**When to skip**: Tasks that are intrinsically generative (research,
documentation authoring, code review prose, summary synthesis); the
behavioural primitive is about misplaced LLM calls inside otherwise
deterministic code, not about model usage in the generative core.

## Rule 6 — surface_conflicts

**id**: `BG-006` | **severity**: major | **applies when**: `surface_conflicts=true`

When two parts of the codebase disagree on a pattern (error handling,
async style, state management, naming convention), the L3 Task Agent
MUST surface the disagreement as a `ConflictFinding` in StatusReport
rather than producing code that combines both patterns. The "averaged"
solution is usually broken — it neither matches Pattern A's invariants
nor Pattern B's, so the resulting code works in neither regime.

Added in v12.2.0 PV-03 per the Mnimiy May-2026 X article §4 Rule 7
([article cross-walk](.local/research/v12.2.0_gap_analysis.md) §2 D-2).
The article's source moment: *"A codebase had two error-handling
patterns — async/await with try/catch and a global error boundary.
Claude wrote code that did both. Errors got swallowed twice. 30
minutes to figure out."*

**Rendered guidance** (injected into L3 dispatch when active):

> Before writing code that touches a pattern with multiple existing
> implementations in the codebase, run a 2-step audit: (1) Did I
> identify > 1 pre-existing pattern via `grep` / `SemanticSearch`?
> (2) If yes, which pattern does my acceptance criteria mandate?
> If the AC does NOT mandate one, surface a `ConflictFinding`
> (severity=major) with the verbatim pattern signatures and the
> file paths. Halt your task until the dispatcher chooses. Do NOT
> produce code that satisfies both — that path always degrades.

**Self-check questions**:

1. Did I scan `owned_files` for the canonical pattern BEFORE writing?
2. Did I scan ALL `read_only` files in the predecessor artifact summary?
3. If a conflict surfaced, did I escalate via `ConflictFinding` rather
   than picking the pattern that "felt natural"?

**When to skip**: Tasks where only one pattern exists in the codebase
(verified via `Grep` / `SemanticSearch`); the audit is no-op.

## Rule 7 — convention_first

**id**: `BG-007` | **severity**: major | **applies when**: `convention_first=true`

In an established codebase, the L3 Task Agent MUST match the existing
pattern even when a "better" pattern is available in the broader
ecosystem. The cost of introducing a second pattern (cognitive split,
testing harness duplication, onboarding tax) almost always exceeds
the marginal benefit of the "better" pattern. Novelty requires
explicit ADR / escalation.

Added in v12.2.0 PV-03 per the Mnimiy May-2026 X article §4 Rule 11
([article cross-walk](.local/research/v12.2.0_gap_analysis.md) §2 D-2).
The article's source moment: *"Claude introduced React hooks into a
class-component codebase. The hooks worked. They also broke the
codebase's testing patterns, which assumed `componentDidMount`. Half
a day to remove and rewrite."*

**Rendered guidance** (injected into L3 dispatch when active):

> Before introducing a new pattern (a library, an abstraction style,
> a state-management primitive, a test harness, a build tool), audit
> the codebase for the canonical existing pattern. If one exists,
> use it even if you believe a "better" pattern is available. To
> introduce novelty, surface an `ADRRequiredFinding` (severity=major)
> citing the existing pattern + your proposed alternative + the
> 3-condition ADR gate ([W-22.3](.cursor/rules/repo-governance.mdc)):
> (1) hard to reverse, (2) surprising without context, (3) real
> trade-off. If all 3 pass, the dispatcher MAY authorise the novelty
> via an explicit ADR. Otherwise, match the convention.

**Self-check questions**:

1. Did I scan the codebase for the existing pattern BEFORE proposing a new one?
2. If introducing novelty, did I author the ADR per W-22.3?
3. If the novelty fails the 3-condition gate, did I fall back to the convention?

**When to skip**: Greenfield code paths (no pre-existing pattern to
match); the audit is no-op. Also skippable when the existing pattern
is verifiably broken — but that conclusion requires a `ConflictFinding`
(BG-006) first.

## Token Cost

Each rule's rendered guidance is bounded at ≈ 30 lines / ≈ 120 tokens. All
seven rules together total ≈ 840 tokens — under 10 % of the L3 8 K budget,
sized so they never displace `critical` SKILL.md sections (verified by
``tests/test_behavioral_guidelines.py::test_behavioral_block_token_bounds``).
v12.2.0 PV-03 added BG-005..BG-007 as 1-line dispatch bullets (~ 20-30
tokens each) so the rendered cost grew only ~ 75 tokens despite the 3-rule
addition — the heavy prose lives in the references file (this document),
not in the dispatch payload.

## Backward Compatibility

When the dispatch payload omits ``behavioral_guidelines``,
``select_context()`` returns a result whose ``assembled_text`` is
byte-identical to the v7.x output. This preserves the v7.0.0 layout
golden baseline (``benchmarks/devolaflow_context/baselines/layout_invariant_v7.0.0.yaml``)
and the v7.3.0 baseline (``...v7.3.0.yaml``). The schema bump
``layout_invariant.version: 2 → 3`` is purely additive per ADR-001 §2.

## Line-Level Behavioral Criteria

Added in v8.2.0 PV-04. Loaded verbatim by
`_select_behavioral_sections` whenever the resolved behavioural block
sets `surgical_scope='line'`. Each criterion below is a self-checkable
rule that the L3 Task Agent MUST audit per touched line before commit;
violations classify as a finding (severity follows BG-003 = blocker).

- LL-001 per-line max length: every touched line stays at or below the
  project's configured ruff/black line-length (default 100 chars); a
  single touched line exceeding the ceiling is a blocker finding.
- LL-002 per-line complexity delta: radon cyclomatic-complexity delta
  per touched line MUST be `< +1`; a single touched line that bumps
  the enclosing function's cc by `+1` or more must be split or
  escalated via `ScopeEscalation`.
- LL-003 per-line cohesion: every touched line MUST belong to a
  single logical change (no piggyback edits — e.g. a line that both
  fixes the bug AND renames a local must be split into two diff
  hunks).
- LL-004 declared-range adherence: every touched line MUST fall inside
  a line range explicitly named in the task spec's
  `owned_files[*].line_ranges` field; lines outside the declared
  ranges are blocker findings, not stylistic choices.
- LL-005 verbatim-line preservation: lines NOT explicitly named in the
  task spec MUST remain byte-identical (no whitespace normalisation,
  no quote-style flips, no import reordering); preserves CO-2 / C-3
  verbatim-extraction discipline at the diff layer.

These criteria compose with BG-003 — a `line`-scope task inherits BG-003
(diff hunks stay within the tier) AND each of LL-001..LL-005. Failing
any criterion is a blocker finding per the BG-003 severity classification.

## S-8 Composition Rule

`surgical_scope` (BG-003) interacts directly with Soul Rule **S-8** ("No
Writes Outside Active Change Owned Files" per `AGENTS.md`). When the
dispatch payload carries BOTH a `change_context.owned_files_ref` AND a
`behavioral_guidelines.surgical_scope` value, the L3 Task Agent MUST
honour the **stricter** of the two:

| `surgical_scope` | `change_context.owned_files_ref` present | Effective constraint |
|------------------|------------------------------------------|----------------------|
| `line` | YES | Edits restricted to declared line ranges within owned_files (S-8 ∩ BG-003 line tier) |
| `function` | YES | Edits restricted to declared function bodies in owned_files (S-8 ∩ BG-003 function tier) |
| `module` | YES | Edits restricted to owned_files (S-8 ≡ BG-003 module tier) |
| (any) | NO (free-floating) | BG-003 alone applies; no S-8 enforcement |

Violations classify per BG-003 severity (= **blocker**). The
`lifecycle/check_file_ownership` hook (v8.2.6 forward-defined) enforces
S-8 at write time; in `mode: lite` it warns + logs, in `mode: full` (or
STRICT) it blocks + escalates per P4. Trivial-tier exception (single file
< 20 lines per S-1 / P1) applies symmetrically — both S-8 and BG-003 are
waived for trivial edits.

## Severity Matrix

| Rule ID | Field / Tier | Severity | On-violation behaviour |
|---------|--------------|----------|------------------------|
| BG-001 | `think_first=true` | warn | Append finding to StatusReport `findings`; no block |
| BG-002 | `simplicity_check=true` (1 YES) | minor | Append finding |
| BG-002 | `simplicity_check=true` (2 YES) | major | Append finding + reduce score |
| BG-002 | `simplicity_check=true` (3 YES) | blocker | Append finding + halt commit |
| BG-003 | `surgical_scope` (any tier) | blocker | Halt commit; require ScopeEscalation |
| BG-004 | `goal_loop=true` (round ≥ 2) | warn | Append `GoalDriftWarning` finding |
| BG-005 | `no_llm_for_deterministic=true` (LLM call replaces deterministic code) | warn | Append `MisplacedLLMCallWarning` finding |
| BG-006 | `surface_conflicts=true` (≥ 2 patterns disagree) | major | Append `ConflictFinding` + halt task until dispatcher resolves |
| BG-007 | `convention_first=true` (novelty without ADR) | major | Append `ADRRequiredFinding` + halt task until ADR clears W-22.3 |
| LL-001 | per-line max length | blocker | (line tier) Halt commit |
| LL-002 | per-line cyclomatic delta < +1 | blocker | (line tier) Halt commit |
| LL-003 | per-line cohesion (single logical change) | blocker | (line tier) Halt commit |
| LL-004 | declared-range adherence | blocker | (line tier) Halt commit |
| LL-005 | verbatim-line preservation | blocker | (line tier) Halt commit |
| S-8 | owned_files write | blocker (mode: full) / warn (mode: lite) | Block + escalate per P4 |

The matrix is the single-source-of-truth for L3 self-audit; agents MUST
classify findings using this exact severity wording (no inflation, no
deflation per CO-2 verbatim-extraction discipline).

## v8.2.x Primitive References

The behavioral primitives compose with the runtime primitives shipped in
the v8.x cycle. Each cross-link below identifies the runtime surface that
backs the prompt-side guidance:

| Primitive | Runtime surface | Cycle |
|-----------|-----------------|-------|
| `surgical_scope='line'` verifier | `src/devolaflow/task_adaptive_selector.py:_load_line_level_criteria` | v8.2.0 PV-04 |
| `select_context()` integration | `src/devolaflow/task_adaptive_selector.py:_select_behavioral_sections` | v8.0.0 P-08 |
| `change_context.owned_files_ref` honoring | `src/devolaflow/agent_workspace/change.py::ChangeStore` | v8.2.5 PV-05 |
| Append-only handoff envelope (S-9) | `src/devolaflow/agent_workspace/handoff.py` | v8.2.4+ |
| `lifecycle/check_file_ownership` hook | `src/devolaflow/lifecycle/` (forward-defined v8.2.6) | v8.2.6 |
| Plan-mode prompt-side embedding (S-10) | `references/plan-mode-enforcement.md` (forward-defined v8.4.4 PV-04) | v8.4.4 |
| Reinforcement injection | `src/devolaflow/gate/reinforcement.py::merge_reinforcement_into_dispatch` | v8.0.0 P-04 |
| Token-budget breaker | `src/devolaflow/gate/budget.py::TokenBudgetBreaker` | v8.0.0 P-03 |

Operators triaging behavioral-rule violations consult the runtime surface
for the canonical implementation; the prompt-side guidance documented
above is the L3 contract surface.

## See Also

- ``schemas/lean-dispatch.yaml#layout_invariant`` (canonical position 14)
- ``workflow-system/agent/context_profiles.yaml`` (per-profile defaults)
- ``src/devolaflow/task_adaptive_selector.py:_select_behavioral_sections``
- ``src/devolaflow/task_adaptive_selector.py:_load_line_level_criteria`` (PV-04)
- ``.local/research/v8.0.0_patch_plan.md`` §3 P-08
- ``.local/research/v8.2.0_patch_plan.md`` §3 PV-04
- ``https://github.com/forrestchang/andrej-karpathy-skills`` (upstream rules)
