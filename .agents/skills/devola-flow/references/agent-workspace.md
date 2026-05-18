---
id: "agent/references/agent-workspace"
version: "1.0.0"
purpose: >
  Defines the `.local/.agent/` change-driven workspace tree (active changes,
  handoff envelopes, archived changes, source-of-truth specs) introduced in
  DevolaFlow v8.3.0. Covers per-artifact token budgets, lifecycle FSM, the
  Python API surface (`devolaflow.agent_workspace`), append-only handoff
  semantics (Rule S-9), file-ownership constraint (Rule S-8), the OpenSpec-
  inspired delta-spec format, and the auto-generated REPORT.md surface.
  Use this when authoring `change-driven` workflows, debugging handoffs,
  archiving completed changes, or proposing source-of-truth spec mutations.
triggers:
  - "change-driven workflow execution"
  - "scaffolding a new active change folder"
  - "writing a handoff envelope"
  - "archiving a completed change"
  - "debugging file-ownership violations"
  - "merging delta specs into source-of-truth"
  - "auto-generating REPORT.md surface"
tier: 2
token_estimate: 6500
dependencies:
  - "agent/SKILL.md"
  - "agent/references/agent-hierarchy.md"
  - "agent/references/message-schemas.md"
  - "agent/references/decomposition-gate.md"
last_updated: "2026-04-23"
---

# Agent Workspace Reference

The agent workspace is DevolaFlow's machine-parseable, lightweight,
change-scoped substrate for OpenSpec-inspired in-flight work. Every
in-flight change owns a folder under `.local/.agent/active/<change-id>/`
with strict per-artifact token budgets, escalates via append-only
handoff envelopes under `.local/.agent/handoff/`, and is preserved
verbatim in `.local/.agent/archive/<YYYY-MM-DD>-<change-id>/` after the
gate passes.

## 1. When to Load This Reference

Load when the task involves any of:

| Trigger | What you'll be doing |
|---------|----------------------|
| Authoring a `change-driven` workflow dispatch | Need scaffold layout + STATUS.yaml schema |
| Writing or replying to a handoff envelope | Need append-only seq rules + envelope_kind variants |
| Archiving a completed change | Need archive directory layout + REPORT.md template |
| Lint-checking artifact token budgets | Need Rule C-9 budget table + `lint_change` API |
| Proposing a delta merge into source-of-truth | Need ADDED/MODIFIED/REMOVED format + A-4 ADR |
| Hydrating L3 context from an active change | Need `hydrate_change_context()` API |
| Wiring shell-proxy / memory-router into a change | Cross-link to `references/shell-proxy.md` + `references/execution-protocol.md` §10/§11 |
| Composing change-driven with the convergence loop | Cross-link to `references/decomposition-gate.md` §6 + `references/execution-protocol.md` §12 |

If the task is a generic feature/bugfix that does NOT touch
`.local/.agent/`, this reference is OPTIONAL — load only when the
delegation chain explicitly opts into the `change-driven` workflow
template (registered in `templates/registry.yaml` since v8.2.6).

### When to Engage (v9.1.1+)

The SKILL.md §"Workspace Engagement (Read at Session Start)" section is
the canonical entry point: every L0 dispatcher MUST call
`devolaflow.workspace_context.scan_workspace(repo_root)` at session
start to obtain a frozen `WorkspaceContext` snapshot, then route per
the activation matrix below. The scan itself is read-only (S-2 / S-7
relative-paths-only) and ALWAYS performed; auto-write side effects are
gated by `DEVOLAFLOW_AGENT_WORKSPACE=1` per W-20 (REUSED env-flag —
no new variable per the cycle plan §"Two-axis activation").

| Workspace surface (snapshot field) | Complexity ≤ Simple | Standard | Complex |
|---|---|---|---|
| `has_local=False` AND `has_rules=False` | proceed without engagement | scaffold via `devola-init local` then re-scan | scaffold + `--with-examples` (v9.2.0+) |
| `recent_feedbacks` non-empty | optional read | READ latest 3, surface themes in plan | READ latest 3 + cite verbatim in design ADR |
| `source_of_truth_specs` non-empty | inherit as ground truth | TREAT each as A-4 contract; per-change `spec.md` writes deltas | same + `propose_merge` at archive time |
| `active_changes` non-empty | inspect `STATUS.yaml.state` | RESUME the change unless user explicitly opts out (`--no-change`) | MUST resume; opening a parallel change is a S-8 violation |
| `rules_layer_set` non-empty + `compiled_corpora` complete | trust the compiled corpus | same + opt-in `agents_md_slice` for L3 task slices | same + cite layer headings in dispatch context |

**Default-OFF auto-write contract** (R5 strict): even when
`scan_workspace` reports `has_agent_dir=True`, NO handoff envelope is
written automatically until `DEVOLAFLOW_AGENT_WORKSPACE=1`. The
v9.1.3 `pre_handoff` hook (PV-03 of this cycle) is the production
caller that flips on under the env-flag; v9.1.1 PV-01 ships the
discovery API as the prerequisite.

**Envelope policy clarification (S-9 reminder)**: every envelope under
`.local/.agent/handoff/<from>__<to>__<change-id>__<seq>.yaml` is
append-only. To convey new information, author a NEW envelope at
`seq+1`. NEVER edit or delete an existing envelope. The append-only
ledger is the contract that prevents silent overwrites between agents
operating in parallel; mirrors P5 (Artifacts as Contracts). CI enforces
immutability via `tests/test_handoff_envelope_immutable.py` (lands with
the v8.2.4 schema package).

## 2. The `.local/.agent/` Tree Layout

Verbatim from `.local/research/v8.3.0_design.md` §1.1:

```
.local/
├── feedbacks/                     # (existing) Per-version user feedback
│   ├── TRACKER.md                 # feedback resolution status
│   └── feedback_for_vX.Y.Z.md
├── memory/                        # (existing → newly populated)
│   ├── MEMORY.md                  # index loaded at session start
│   ├── REPORT.md                  # human-readable knowledge state
│   ├── prefs.md                   # personal preferences
│   ├── operational.jsonl          # operational learnings
│   ├── session_state.json         # unified session state
│   └── specs/                     # (M-004) source-of-truth specs
│       └── <domain>/spec.md       # per-domain behavior contract
├── tasks/                         # (existing) Task overviews + YAML specs
├── research/                      # (existing) Free-form research artifacts
├── .agent/                        # NEW — agent-facing workspace
│   ├── config.yaml                # per-project DevolaFlow config
│   ├── REPORT.md                  # running dashboard of active + recent archives
│   ├── active/                    # In-flight changes
│   │   └── <change-id>/
│   │       ├── goal.md            # (≤ 200 tokens) intent statement
│   │       ├── acceptance.md      # (≤ 400 tokens) testable AC checklist
│   │       ├── spec.md            # (≤ 1500 tokens) operation spec — ADDED/MODIFIED/REMOVED
│   │       ├── tasks.md           # (≤ 800 tokens) impl checklist with [ ] checkboxes
│   │       ├── STATUS.yaml        # (≤ 100 tokens) machine-readable status block
│   │       ├── owned_files.txt    # (≤ 50 tokens) file ownership manifest
│   │       └── learnings.jsonl    # (capped 50 KB) per-change learnings
│   ├── handoff/                   # Cross-agent handoff envelopes
│   │   └── <from>__<to>__<change-id>__<seq>.yaml
│   └── archive/                   # Completed/merged changes
│       └── <YYYY-MM-DD>-<change-id>/
│           ├── goal.md            # frozen at archive time
│           ├── acceptance.md
│           ├── spec.md
│           ├── tasks.md           # all checkboxes ticked
│           ├── STATUS.yaml        # state: archived
│           ├── owned_files.txt
│           ├── learnings.jsonl    # final per-change learnings (consolidated)
│           ├── REPORT.md          # auto-generated human-readable change report
│           └── handoff_chain.yaml # frozen handoff history
└── index.md                       # auto-regenerated listing
```

### Path conventions

- All paths are relative to repo root (Rule S-2 / Soul invariant). Never absolute.
- **change-id** = lowercase-kebab-case (`add-dark-mode`, `fix-auth-bug`,
  `v8.3.0-pv09-skill-references-bench`). For DevolaFlow's own iteration cycles,
  use `<version>-pv<NN>-<topic>` for traceability.
- **Date prefix** for archives uses ISO-8601 `YYYY-MM-DD` (sorts chronologically).
- **Sequence numbers** for handoff envelopes are monotonic integers starting at 1,
  zero-padded to 4 digits (`0001`, `0002`, ...) for sort-correct directory listing.

## 3. Lifecycle FSM

Verbatim from `.local/research/v8.3.0_design.md` §1.3:

```
[NEW IDEA / FEEDBACK]
        │
        │  /devola:propose <topic>           (deferred to v8.4.0+; today: manual scaffold)
        ▼
[active/<id>/ created]
  ├─ goal.md         ← scaffolded
  ├─ acceptance.md   ← scaffolded
  ├─ spec.md         ← scaffolded
  ├─ tasks.md        ← scaffolded (empty checklist)
  ├─ STATUS.yaml     ← state: PROPOSED
  └─ owned_files.txt ← scaffolded
        │
        │  L0 dispatches L3 task agents per W-9 SI-10
        ▼
        │  /devola:apply        (loop until tasks.md all ticked)
        ▼
[active/<id>/ in progress]
  ├─ STATUS.yaml     ← state: IN_PROGRESS, percent_complete: ...
  ├─ tasks.md        ← checkboxes ticked as work completes
  └─ learnings.jsonl ← per-task reflections appended
        │
        │  /devola:verify       (optional gate)
        ▼
[STATUS.yaml state: VERIFYING]
  └─ verification report appended to STATUS.yaml
        │
        │  /devola:archive      (REQUIRES gate composite ≥ threshold per W-3 SI-3)
        ▼
[active/<id>/ → archive/<YYYY-MM-DD>-<id>/]
  ├─ All artifacts frozen
  ├─ REPORT.md auto-generated
  ├─ Delta merge to .local/memory/specs/<domain>/spec.md PROPOSED (NOT auto-applied)
  └─ STATUS.yaml     ← state: ARCHIVED
        │
        ▼
[Aggregate REPORTs auto-regenerated]
  ├─ .local/.agent/REPORT.md          ← active-vs-archived dashboard
  ├─ .local/memory/REPORT.md          ← knowledge state report
  └─ .rules/REPORT.md                 ← rules-coverage report
```

### State transitions

Machine-enforced via `STATUS.yaml` `state` field:

| From | To | Trigger |
|------|----|---------|
| `PROPOSED` | `IN_PROGRESS` | First L3 dispatch starts |
| `IN_PROGRESS` | `VERIFYING` | `/devola:verify` invoked (or manual STATUS.yaml edit) |
| `VERIFYING` | `IN_PROGRESS` | Verify FAIL → bounded retry (P4) |
| `VERIFYING` | `ARCHIVED` | Verify PASS + `/devola:archive` invoked + gate PASS |
| `IN_PROGRESS` | `ESCALATED` | P4 bounded retry exhausted; human intervention required |
| `ARCHIVED` | (terminal) | No further transitions |
| `ESCALATED` | (terminal) | Human resolves out-of-band |

**Note**: Slash commands (`/devola:propose`, `/devola:apply`, `/devola:verify`,
`/devola:archive`) are deferred to v8.4.0+ per Q-3 in design.md §11.2. In v8.3.0,
the same lifecycle is driven by manual scaffolding plus `change-driven` workflow
template stages (`propose → apply → verify → archive`).

## 3.6 Resume After Pause (v10.5.0 PV-03)

Documentation only — no new code, no new schema, no new template.
This subsection answers: **what does L0 do when returning to an
active change folder ≥ 24 h later, in a new session, after the
operator has been off-task?** All machinery cited below already
exists at v10.4.0 (STATUS.yaml, append-only handoff envelopes,
change_context dispatch field). Cross-references: `STATUS.yaml`
schema §4 (this file), handoff envelope append-only S-9, W-19
cycle-archive boundary, `references/execution-protocol.md` §2
checkpoint mechanism.

### Pre-resume checklist (5 steps)

L0 MUST execute these steps in order BEFORE invoking any L1 / L2 /
L3 dispatch on a returning session:

1. **Scan workspace.** Call
   `devolaflow.workspace_context.scan_workspace(repo_root)` —
   returns frozen `WorkspaceContext` snapshot. If `active_changes`
   is empty, no resume protocol applies; proceed to fresh dispatch.
2. **Pick the candidate active change.** When `active_changes`
   contains > 1 entry, prefer the one whose `last_updated` is most
   recent. The append-only handoff store guarantees `last_updated`
   is monotonic per change, so "most recent" is unambiguous.
3. **Read STATUS.yaml.** The fields needed are:
   - `state` ∈ {PROPOSED, IN_PROGRESS, VERIFYING} → resume-eligible.
     `state == PROPOSED` is stale-OK (work hasn't started).
     `state == ESCALATED` requires human review BEFORE resume.
     `state == ARCHIVED` is terminal — never resume.
   - `last_updated` (ISO-8601). Compute staleness:
     `now() - last_updated`. If `> 7 days`, emit a warning;
     if `> 30 days`, recommend operator review (see "Stale-change
     pruning" below).
   - `last_handoff_seq` (int). The append-only seq counter the
     resume dispatch must respect.
4. **Reconcile handoff envelopes.** Read `.local/.agent/handoff/`
   and compute `max_seq = max(seq for envelope where change-id
   matches)`. Cross-check vs `STATUS.yaml.last_handoff_seq`:
   - `max_seq == last_handoff_seq` → in sync; resume normally.
   - `max_seq == last_handoff_seq + 1` → an envelope was written
     but STATUS.yaml was not updated (e.g. crash between writes).
     Re-read the latest envelope; `STATUS.yaml.last_handoff_seq`
     is treated as authoritative and bumped to `max_seq`.
   - `max_seq > last_handoff_seq + 1` → multiple unrecorded
     envelopes. EMIT a `ReconciliationWarning` and treat the
     latest envelope as the resume entry point.
5. **Read goal.md + acceptance.md + spec.md + tasks.md.** Per
   C-9 token budgets, all 4 fit in ~2K tokens combined. Identify
   the first un-checked task in `tasks.md` as the resume entry
   point — that's the first L3 dispatch target.

### Resume dispatch contract — `change_context` field

The next dispatch payload MUST include the `change_context` field
at canonical position 16 (per A-2.2 append-only tail), populated
from STATUS.yaml + the active folder:

```yaml
change_context:
  change_id: <STATUS.yaml.change_id>
  active_folder: ".local/.agent/active/<change_id>"
  state: <STATUS.yaml.state>           # IN_PROGRESS | VERIFYING
  spec_delta_target: <spec.md frontmatter delta_target>
  owned_files_ref: ".local/.agent/active/<change_id>/owned_files.txt"
  acceptance_ref: ".local/.agent/active/<change_id>/acceptance.md"
  resume_from_seq: <STATUS.yaml.last_handoff_seq + 1>
  resume_rationale: "resume after pause; idle <duration>"
```

The `resume_from_seq` field is the dispatch's prescribed seq for
the L0->L? handoff envelope it authors. Convergence-round counters
in `STATUS.yaml.gate_score` / round metadata are preserved
across resume — the round number is keyed by `change_id`, not
session_id.

### Concurrency-safe resume — O_EXCL semantics

`HandoffStore.write_envelope()` opens with `O_EXCL` (per §6 envelope
schema and §5 Python API), so two parallel resume attempts in
different sessions cannot collide on the same seq. The losing
attempt raises `EnvelopeImmutableError` and the operator can either:

1. Retry with `seq+2` (the audit trail records both attempts), or
2. Abort and re-scan workspace to pick up the winning attempt's
   handoff envelope as the new `last_handoff_seq`.

Either path preserves S-9 append-only — never modifies an existing
envelope. Both paths are logged (S-5 — explicit error states).

### Stale-change pruning (operator-facing recommendation)

When staleness threshold > 30 days AND `state == IN_PROGRESS`, the
resume protocol's recommendation is:

| Operator decision | Action |
|--------|--------|
| Continue | Proceed with normal resume (the staleness is just informational) |
| Archive | Run `/devola:verify` then `/devola:archive` per §3 lifecycle FSM transitions; A-4 source-of-truth merge proposal flows from there |
| Escalate | Set `STATUS.yaml.state = ESCALATED` and document the rationale in a NEW handoff envelope (`seq+1`) — preserves the audit trail |

The threshold (30 days) is documentation-only; operators may
override based on project context. The 7-day softer threshold
("emit warning") is the cross-week interruption signal; the
30-day harder threshold suggests abandonment or re-prioritization.

### Cross-references

- `STATUS.yaml` schema (§4 above; v8.2.4 — fields `state`,
  `last_updated`, `last_handoff_seq` are the resume-protocol
  contract).
- Handoff envelope append-only — Soul rule S-9
  (`.cursor/rules/repo-governance.mdc`).
- `change_context` dispatch field at canonical position 16
  (§12 below; v9.7.0 PV-02; A-2.2 append-only-tail invariant).
- `references/execution-protocol.md` §2 Checkpoint/Resume
  Mechanism — covers stage-gate-level resume (different scope:
  cycle vs change vs session).
- W-19 cycle-archive boundary — resume protocol applies to
  ACTIVE changes; archived changes are TERMINAL and cannot be
  resumed (re-archival is a no-op per §1 lifecycle FSM).
- A-4 source-of-truth merge rule — stale-change pruning's
  archive path goes through the gate per A-4.
- `src/devolaflow/skills/change_activation.py::activation_verdict`
  with `force_no_change=True` (v10.5.0 PV-03 D-A-4) — operator
  override on resume when ad-hoc dispatch is preferred over the
  full scaffold.

## 4. Per-Artifact Schemas

Each artifact in `active/<id>/` and `archive/<date>-<id>/` is governed by a
schema in `schemas/agent-workspace/` (v8.2.4). Token budgets are enforced
by Rule C-9 + `python -m devolaflow.agent_workspace.lint <change-id>` (v8.2.5).

### `goal.md` (≤ 200 tokens)

```markdown
---
id: <change-id>
created: <YYYY-MM-DDTHH:MM:SSZ>
priority: P1|P2|P3|P4
intent_class: feature|bugfix|refactor|migration|spike|docs|ops
---

# Goal: <one-line title>

## Why
<1–2 sentences: problem being solved>

## In scope
- <bullet>

## Out of scope
- <bullet>
```

Schema: `schemas/agent-workspace/change-goal.yaml`

### `acceptance.md` (≤ 400 tokens)

```markdown
---
parent: <change-id>
ac_count: <int>
---

# Acceptance Criteria

## Functional
- [ ] AC-1: <verifiable condition with metric where applicable>
- [ ] AC-2: ...

## Quality
- [ ] AC-N: tests pass — `<exact pytest command>`
- [ ] AC-N+1: lint clean — `ruff check src/ tests/`
- [ ] AC-N+2: format clean — `ruff format --check src/ tests/`

## Backward-compat
- [ ] AC-N+M: <byte-identical preservation claim, if applicable>
```

Schema: `schemas/agent-workspace/change-acceptance.yaml`

### `spec.md` (≤ 1500 tokens) — OpenSpec delta format

```markdown
---
parent: <change-id>
delta_target: <domain>           # e.g., "agent_workspace", "plugins", "rules"
delta_kind: lite|full
---

# Operation Spec for <change-id>

## Purpose
<2–4 sentences: what this change does to the existing system>

## ADDED Requirements

### Requirement: <Stable heading>
The system MUST <RFC 2119 verb> <observable behavior>.

#### Scenario: <when this applies>
- GIVEN <precondition>
- WHEN <trigger>
- THEN <observable outcome>

## MODIFIED Requirements

### Requirement: <Existing heading from .local/memory/specs/<domain>/spec.md>
The system <new behavior>.
(Previously: <old behavior>)

## REMOVED Requirements

### Requirement: <Existing heading>
(Reason for removal.)
```

Schema: `schemas/agent-workspace/change-spec.yaml`

### `tasks.md` (≤ 800 tokens)

Hierarchical numbered checkboxes (1.1, 1.2, 2.1, ...). Each task < 30 min,
owned files ≤ 6 (per Wave constraints in `references/decomposition-gate.md`).

Schema: `schemas/agent-workspace/change-tasks.yaml`

### `STATUS.yaml` (≤ 100 tokens)

```yaml
schema_version: 1
change_id: <id>
state: PROPOSED|IN_PROGRESS|VERIFYING|ARCHIVED|ESCALATED
percent_complete: <0-100>
owner_layer: L0|L1|L2|L3
owner_session_id: <uuid>
last_updated: <ISO-8601>
last_handoff_seq: <int>
gate_score: <float|null>
verify_pass: <bool|null>
last_handoff_summary:           # v10.7.0 D-P-3 — OPTIONAL NEST demo
  from_layer: L0|L1|L2|L3|operator|human
  to_layer:   L0|L1|L2|L3|operator|human
  ts:         <ISO-8601>
  seq:        <int>              # MUST equal last_handoff_seq at write time
```

Schema: `schemas/agent-workspace/change-status.yaml`

**`last_handoff_summary` (v10.7.0 D-P-3 — OPTIONAL).** Demonstrates the
A-2.3 NEST-vs-APPEND decision rule on the agent-workspace surface. The
four diagnostic sub-attributes (`from_layer` / `to_layer` / `ts` / `seq`)
are NESTED inside ONE dict-shaped optional key rather than spawned as
four sibling top-level scalars. Absent in v8.3.0..v10.6.x STATUS.yaml
files (those continue to validate cleanly at schema_version 1). When
present, `last_handoff_summary.seq` MUST equal `last_handoff_seq` at
write time (both refresh atomically). The Python accessor is
`Change.last_handoff_summary` (returns `dict | None`).

### `owned_files.txt`

One path per line. Max 6 paths. All relative to repo root.

```
src/devolaflow/plugins/installer.py
src/devolaflow/plugins/__init__.py
tests/test_plugins.py
workflow-system/agent/knowledge/runtime-plugins.yaml
```

Schema: `schemas/agent-workspace/owned-files.yaml`

### `learnings.jsonl` (capped 50 KB file size)

Same JSONL schema as `.local/memory/operational.jsonl` (`Learning` dataclass,
v8.2.2 PV-03 SessionState shape). Per-change scoping prevents cross-change
pollution. Captured by `capture_session_reflection(..., change_id=<id>)`
(extended in v8.2.8 — H-006).

### Handoff envelope (≤ 600 tokens)

See §6 below for full schema.

Schema: `schemas/agent-workspace/handoff-envelope.yaml`

### `.local/.agent/config.yaml` (per-project DevolaFlow config)

OpenSpec `openspec.yaml` analog. Sets default workflow, mode, plugin runtime.

Schema: `schemas/agent-workspace/agent-config.yaml`

## 5. Python API Surface

`src/devolaflow/agent_workspace/` (v8.2.5 + v8.2.7 + v8.2.8) — public symbols
re-exported from `devolaflow.agent_workspace.__init__.__all__`.

### Change folders

| Symbol | Description |
|--------|-------------|
| `Change` | Dataclass representing one `active/<id>/` folder; carries change_id, state, paths |
| `ChangeStore` | Repository for `active/` + `archive/` — list/get/move semantics |
| `ChangeNotFoundError` | Raised when a referenced change-id has no folder |
| `ChangeStoreError` | Base exception for ChangeStore operations |

### Handoff envelopes (Rule S-9 enforcement)

| Symbol | Description |
|--------|-------------|
| `HandoffEnvelope` | Dataclass for one envelope file (envelope_kind discriminator + variant payload) |
| `HandoffStore` | Append-only ledger; `write_envelope()` raises if seq would overwrite |
| `EnvelopeImmutableError` | Raised by `HandoffStore.write_envelope()` on seq collision |
| `HandoffStoreError` | Base exception for HandoffStore operations |

### Archive operations

| Symbol | Description |
|--------|-------------|
| `ArchiveManager` | Moves `active/<id>/` → `archive/<date>-<id>/`, freezes artifacts, calls `consolidate_session()`, PROPOSES delta merge to source-of-truth |
| `ArchiveError` | Base exception for ArchiveManager operations |
| `MergeConflict` | Raised when proposed delta merge cannot be safely applied (e.g., ADDED requirement collides with existing source-of-truth heading) |

### Delta-spec parsing (M-003 closure)

| Symbol | Description |
|--------|-------------|
| `DeltaSpec` | Parsed `spec.md` with `added`, `modified`, `removed` requirement lists |
| `DeltaRequirement` | Single ADDED/MODIFIED/REMOVED requirement with heading, body, scenarios |
| `parse_delta_spec(text) -> DeltaSpec` | Extract OpenSpec-style sections from a `spec.md` body |
| `serialize_delta_spec(spec) -> str` | Round-trip serialize a DeltaSpec back to OpenSpec format |
| `DeltaSpecParseError` | Raised when `spec.md` body lacks the expected delta sections |

### Token-budget linting (Rule C-9 enforcement)

| Symbol | Description |
|--------|-------------|
| `lint_change(change_id) -> BudgetReport` | Estimate token counts per artifact, classify against soft/hard ceilings |
| `BudgetReport` | Per-artifact result with `actual_tokens`, `budget`, `verdict` (PASS/WARN/FAIL) |
| `BudgetViolation` | Single artifact's overage record |
| `estimate_tokens(text) -> int` | Heuristic token counter (~4 chars/token) shared with `_estimate_tokens` in `local/compiler.py` |

### Memory bridge (v8.2.8 — closes H-006)

| Symbol | Description |
|--------|-------------|
| `consolidate_change_on_archive(change_id, ...) -> dict` | At archive time, promote durable per-change learnings into global `.local/memory/operational.jsonl` |
| `hydrate_change_context(change_id) -> dict` | Load all artifacts for an active change (capped to hard ceilings) for L0/L1/L2/L3 context injection |
| `MemoryBridgeError` | Base exception for memory_bridge operations |

### REPORT.md surface (v8.2.7 — closes H-005, opt-in per I-PV07-A)

| Symbol | Description |
|--------|-------------|
| `render_change_report(change_id, ...) -> str` | Per-archive REPORT.md (what changed / why / how / verification / files / learnings / handoff chain) |
| `render_workspace_report(...) -> str` | `.local/.agent/REPORT.md` aggregate (active changes + recently archived) |
| `render_memory_report(...) -> str` | `.local/memory/REPORT.md` (learnings counts, top high-confidence, external source reviews) |
| `render_rules_report(...) -> str` | `.rules/REPORT.md` (per-layer rule counts, compile target status) |
| `regenerate_all(repo_root) -> dict[str, Path]` | Regenerate all 4 REPORT.md files; returns `{report_kind: path_written}` |

CLI: `python -m devolaflow.agent_workspace.reporter --all` (or
`--change <id>` / `--workspace` / `--memory` / `--rules`). Opt-in only —
no auto-trigger from existing workflows yet.

### Backward-compat invariants (R5)

- This package adds NO new public symbol to `devolaflow.__init__`.
- `learnings.py`'s 14 existing public functions stay byte-identical
  (verified by `tests/test_learnings.py` — invariant I-PV05-B).
- `compressor.py::assert_dispatch_layout` accepts BOTH v4 (15 keys) AND v5
  (16 keys, `change_context` appended at position 16) payloads — invariant
  I-PV05-C.

## 6. Handoff Protocol

The `.local/.agent/handoff/` directory is the ONLY supported channel for
inter-agent messaging in DevolaFlow's 4-layer hierarchy. Replaces the
previous in-memory dispatch path; persists across sessions; survives
restarts; auditable.

### File naming

```
.local/.agent/handoff/<from>__<to>__<change-id>__<seq>.yaml
```

- `<from>`, `<to>`: layer identifiers — `L0` / `L1` / `L2` / `L3`
- `<change-id>`: lowercase-kebab-case, identifies the active change
- `<seq>`: monotonic integer starting at 1, zero-padded to 4 digits

Example: `L0__L2__add-dark-mode__0001.yaml` (first dispatch from Project to Wave).

### Envelope schema

Discriminator: `envelope_kind` selects one of three variants:

| `envelope_kind` | Direction | Variant body |
|-----------------|-----------|--------------|
| `TaskDispatch` | parent → child | `dispatch:` block (task_id, type, acceptance_criteria_ref, owned_files_ref, predecessor_artifact_refs) |
| `StatusReport` | child → parent | `report:` block (task_id, state, artifacts, metrics with tests_passed / coverage_pct / findings_by_severity) |
| `EscalationEvent` | child → parent (or upward) | `escalation:` block (severity, trigger, proposed_action) |

Full YAML envelope schema: `schemas/agent-workspace/handoff-envelope.yaml`.

### Append-only invariant (Rule S-9, Soul P0)

Once a `<from>__<to>__<change-id>__<seq>.yaml` envelope exists, it MUST NOT
be modified or deleted by any agent. To convey new information, the agent
MUST author a new envelope with `seq+1`.

Rationale: append-only ledger prevents silent overwrites between agents
operating in parallel. Mirrors P5 (Artifacts as Contracts) and the message-
schemas P3 contract in `references/message-schemas.md`.

Enforcement:

- `tests/test_handoff_envelope_immutable.py` (v8.2.4) — CI lint
- `lifecycle/check_envelope_append_only` hook (v8.2.5) — write-time block in STRICT mode
- `HandoffStore.write_envelope()` raises `EnvelopeImmutableError` on seq collision

### Inbox/outbox semantics

For an agent operating at layer `Lk`:

- **Inbox** = envelopes where `<to> == Lk` AND `<change-id>` matches active change
- **Outbox** = envelopes where `<from> == Lk` AND `<change-id>` matches active change

`HandoffStore.list_inbox(layer, change_id)` and `list_outbox(layer, change_id)`
return envelopes sorted by ascending `seq`. To compute the next seq for
authoring an outgoing envelope: `next_seq = max(existing_seqs) + 1`, atomic
under file-write race conditions via `O_EXCL` open.

### Handoff Envelope L0-only Metadata Stripping (v12.4.0 PV-05)

The handoff envelope's `predecessor_summary` block is a verbatim
extraction from the upstream layer's output (per C-3). However, three
L0-only literal classes leak operator-facing chrome into subagent
contexts when copied wholesale; the writer MUST strip them at
envelope-author time so downstream L1/L2/L3 dispatchers see no
decorative banners:

| Direction | Literal class | Source | Strip rule |
|---|---|---|---|
| L0 → L1 / L0 → L2 | `🌸 DevolaFlow vX.Y.Z active · …` (Session Banner workflow-start) | SKILL.md §"Session Banner Contract" line 1 | Drop the whole line from `predecessor_summary` |
| L0 → L1 / L0 → L2 | `🌸 DevolaFlow vX.Y.Z complete · <stages> stages · <waves> waves · <tasks> tasks` (Session Banner workflow-end) | SKILL.md §"Session Banner Contract" line 2 | Drop the whole line |
| L0 → L1 / L0 → L2 | `📊 Task Quality Score: <composite>/100 · <dimensions>` (TQS 📊 footer) + the `🌸 DevolaFlow vX.Y.Z · scored at workflow close` tail | `references/task-quality-score.md` template | Drop both lines |
| L1 → L2 / L1 → L3 | `pin_learning_for_session(...)` / `consolidate_session(...)` / `decay_confidence()` literals from §"Operational Learnings" | SKILL.md lines 484-485 | L1 has no operational.jsonl contract — strip session-pinned references entirely |

Subagents that receive the bannerless `predecessor_summary` perform
identical work — banner content is decorative operator chat output,
NOT load-bearing context per CO-2 / Rule C-2 (Lean Message Format).

**Runtime enforcement** (PV-05 baseline): the `pre_dispatch` lifecycle
hook `reject_subagent_banner_emission` (registered as an opt-in extra
via `register_pre_dispatch_extra()` in
`src/devolaflow/lifecycle/reject_subagent_banner_emission.py`) flags
NEW emissions of the `🌸 DevolaFlow vX.Y.Z` literal in dispatch
payloads whose `target_layer ∈ {L1, L2, L3}`. Historical evidence
inside `predecessor_artifacts[*].summary` carried forward from prior
rounds is NOT flagged (top-level-only discipline mirrors the v12.2.0
`reject_subagent_quality_score` precedent). Permissive default per
S-5 (warn + log); strict mode raises `HookViolation` per the
lifecycle dispatcher's strict contract.

**Auto-strip runtime helper telegraphed to v12.5.0+**: the
`src/devolaflow/agent_workspace/handoff.py` writer will gain a
`strip_l0_only_metadata(envelope)` helper that performs the table
above's strip rules in-place before the `O_EXCL` write. At v12.4.0
PV-05 the rule is **normative-only** (this subsection + the runtime
hook); auto-strip lands once the v12.5.0+ SI-1 plans the
backward-compat windowing.

Source: `.local/research/v12.4.0_l0_only_audit.md` §§B.1-B.3 (banner +
TQS + operational_learnings literal enumeration) + cycle plan §3 PV-05
D-4 closure (L0-only surfaces leak cluster).

## 7. Source-of-Truth Specs (M-004 / Rule A-4)

`.local/memory/specs/<domain>/spec.md` is the source-of-truth for current
system behavior. Per-change `.local/.agent/active/<id>/spec.md` files contain
DELTAS (ADDED/MODIFIED/REMOVED Requirements) relative to source-of-truth.

### Why deltas, not full specs

- **Lifecycle separation**: in-flight proposals (active/) and agreed contracts
  (memory/specs/) have different governance windows. A proposal can be
  rejected without contaminating the contract.
- **Audit trail**: every change archive preserves the proposed delta, so the
  archive log answers "what did we add to spec X across all of v8.3.0?"
- **Token economy**: a delta is dramatically smaller than re-stating the
  whole spec, fitting comfortably in the 1500-token soft budget.

### Archive-time merge proposal (NOT auto-applied)

Source-of-truth is mutated ONLY at archive time, after the gate has PASSED
(W-3 / SI-3 composite ≥ 8.5 for minor changes, ≥ 9.0 for major). The gate
runs the explicit `mergeability_check` (v8.2.5 reporter module) before
allowing the merge.

`ArchiveManager.propose_merge(change_id) -> MergeProposal` returns a structured
proposal that a human (or downstream automation) explicitly applies — never
auto-merged. This preserves W-3 / SI-3 + W-4 / SI-4 invariants.

### ADDED / MODIFIED / REMOVED semantics

| Section | Effect on source-of-truth |
|---------|---------------------------|
| `## ADDED Requirements` | Append new headings to source-of-truth spec; collision with existing heading raises `MergeConflict` |
| `## MODIFIED Requirements` | Replace existing heading body in source-of-truth (heading must already exist) |
| `## REMOVED Requirements` | Delete heading from source-of-truth (heading must already exist) |

Each requirement uses RFC 2119 keywords (MUST / MUST NOT / SHOULD / MAY) and
optional Scenario blocks (GIVEN / WHEN / THEN). Format borrowed verbatim from
OpenSpec — adopted in v8.3.0 per `.local/research/v8.3.0_openspec_deep_analysis.md`.

## 8. REPORT.md Surface

Auto-generated, human-readable reports at four locations. Generator API in
`src/devolaflow/agent_workspace/reporter.py` (v8.2.7).

### `archive/<date>-<id>/REPORT.md` (per-change)

Auto-generated at `/devola:archive` time (or manual `render_change_report()`
call). Template:

```markdown
# Change Report: <change-id>
> Archived <YYYY-MM-DD> | Author: <session_id> | Duration: <hh:mm:ss>

## What changed
<Auto-extracted from spec.md ADDED/MODIFIED/REMOVED sections>

## Why
<Verbatim from goal.md `## Why` section>

## How
<Auto-extracted from spec.md `## Purpose` + tasks.md `## N. <group>` headings>

## Verification
- AC pass rate: <X/Y>
- Tests passed: <int>
- Coverage: <pct>%
- Lint: <pass|fail>
- Format: <pass|fail>
- Gate score: <float>/10

## Files touched
<owned_files.txt verbatim>

## Learnings extracted
- <insight 1> (confidence: 0.X)
- <insight 2> (confidence: 0.Y)

## Handoff chain summary
- L0 → L2 (T01 dispatch) → L3 (T01 work) → L2 (T01 report) → L0 (gate eval)
```

### `.local/.agent/REPORT.md` (workspace aggregate)

Active vs. archived dashboard. Tables: Active changes (id, state, %, owner,
last touch), Recently archived (last 7 days; id, archived date, duration,
gate score). Auto-regenerates on every state transition.

### `.local/memory/REPORT.md` (memory aggregate)

Learnings counts by task type, top 10 high-confidence learnings (last 30
days), recent external-source reviews from `reference-dependencies.yaml`.

### `.rules/REPORT.md` (rules-coverage aggregate)

Per-layer rule counts, always-apply flags, token estimates. Compile-target
status (cursor `repo-governance.mdc` last compile date + drift verdict;
agents_md `AGENTS.md` last compile date + drift verdict).

### CLI invocation

```bash
python -m devolaflow.agent_workspace.reporter --all                # all 4 reports
python -m devolaflow.agent_workspace.reporter --change add-dark-mode
python -m devolaflow.agent_workspace.reporter --workspace
python -m devolaflow.agent_workspace.reporter --memory
python -m devolaflow.agent_workspace.reporter --rules
```

Opt-in semantics (I-PV07-A): no existing workflow auto-triggers reporter;
explicit invocation only. Plays nicely with W-9 SI-10 — adding the reporter
to a developer's pre-commit hook is OPTIONAL.

## 9. Token Budgets (Rule C-9)

Verbatim from `.cursor/rules/repo-governance.mdc` C-9:

| File | Soft budget | Hard ceiling | Rationale |
|------|-------------|--------------|-----------|
| `goal.md` | 200 tokens | 400 | Single-paragraph intent; verbose prose forbidden |
| `acceptance.md` | 400 tokens | 800 | Checkbox list; one AC per line |
| `spec.md` | 1500 tokens | 3000 | ADDED/MODIFIED/REMOVED sections; OpenSpec-style |
| `tasks.md` | 800 tokens | 1500 | Hierarchical numbered checkboxes |
| `STATUS.yaml` | 100 tokens | 200 | YAML frontmatter only; no prose |
| `owned_files.txt` | 50 tokens | 100 | One path per line; max 6 writable per task |
| `learnings.jsonl` | (no token limit) | 50 KB file size | Bounded by JSONL line count + decay |
| `REPORT.md` (per archive) | 1500 tokens | 3000 | Auto-generated; templated |
| Handoff envelope | 600 tokens | 1200 | YAML envelope with `key_facts` (verbatim per CO-2) |

Verify with:

```bash
python -m devolaflow.agent_workspace.lint <change-id>
```

Soft budget over → warn (lite mode). Hard ceiling over → fail commit (full
mode and STRICT). Couples with W-9 SI-10 step 1 (pytest) when the change-id
is enrolled in the `change-driven` workflow's pre-commit gate.

## 10. File-Ownership Constraint (Rule S-8)

When an L3 Task Agent is operating inside a `change-driven` workflow with
an active change folder, it MUST NOT modify any file outside the union of:

1. paths listed in `.local/.agent/active/<change-id>/owned_files.txt`
2. the change folder itself (`active/<change-id>/`)
3. its own outbox in `.local/.agent/handoff/` (append-only — see §6)

Violations:

- Detected at file-write time via `lifecycle/check_file_ownership` hook
- In `mode: lite` — warn + log
- In `mode: full` (or STRICT) — block + escalate per P4

Exceptions:

- Trivial single-file edits < 20 lines (P1 trivial waiver also applies here)
- L0/L1/L2 dispatcher reads (Read/Glob/Grep/SemanticSearch) are unrestricted

Source: Rule S-8 in `.cursor/rules/repo-governance.mdc`.

## 11. Workflow Template Integration

The `change-driven` workflow template (`workflow-system/agent/templates/builtin/
change-driven.yaml`, v8.2.6) wires the lifecycle FSM (§3) into DevolaFlow's
stage primitives (`references/meta-framework.md`):

| Stage | Primitive | Description |
|-------|-----------|-------------|
| `propose` | `design` | Scaffold `active/<id>/` with goal+acceptance+spec+tasks+STATUS+owned_files |
| `apply` | `implement` | Loop L3 dispatches until tasks.md all checkboxes ticked |
| `verify` | `verify` | Run AC checklist; gate composite must PASS per W-3 |
| `archive` | `deploy` | Move active → archive; auto-generate REPORT.md; consolidate per-change learnings to global memory; PROPOSE delta merge to source-of-truth (NOT auto-apply) |

Composition: `sequence(propose → loop(apply, verify) → archive)`.
Loop terminates when `verify.pass_rate == 1.0 AND verify.gate_score >= verify.threshold`,
max 5 iterations, on-exhaustion = escalate.

The `archive_gate` runs BEFORE the `archive` stage with criteria
`verify.pass_rate == 1.0 AND verify.gate_score >= 8.5`; failure escalates
and requires human override.

Mode parameter:

| Mode | Pre-commit gate steps |
|------|----------------------|
| `lite` (default) | Steps 1–3 of W-9 SI-10 (tests, lint, format) — single-author, low-risk |
| `full` | All 6 steps of W-9 SI-10 — multi-author or high-risk |

Set in `.local/.agent/config.yaml` `mode:` field, or override per-dispatch
via the workflow's `parameters.mode` config.

## 12. Cache Layout v5 (M-006)

Dispatch payloads in change-driven mode optionally include a `change_context`
top-level field at canonical position 16 (schema v5):

```yaml
change_context:
  change_id: <id>
  active_folder: ".local/.agent/active/<id>"
  state: PROPOSED|IN_PROGRESS|VERIFYING
  spec_delta_target: <domain>
  owned_files_ref: ".local/.agent/active/<id>/owned_files.txt"
  acceptance_ref: ".local/.agent/active/<id>/acceptance.md"
```

Per Rule 6 (P6 Preserve Cached Prefix), positions 1–15 remain byte-identical
to v4 — `change_context` is appended at the end. `assert_dispatch_layout()`
accepts BOTH v4 (15 keys) AND v5 (16 keys) payloads (invariant I-PV05-C).
When `change_context` is absent, dispatch is a "free-floating" workflow
(current v4 behavior preserved).

## 13. References

### Internal

- `schemas/agent-workspace/change-goal.yaml` — goal.md schema
- `schemas/agent-workspace/change-acceptance.yaml` — acceptance.md schema
- `schemas/agent-workspace/change-spec.yaml` — spec.md schema (delta format)
- `schemas/agent-workspace/change-tasks.yaml` — tasks.md schema
- `schemas/agent-workspace/change-status.yaml` — STATUS.yaml schema
- `schemas/agent-workspace/owned-files.yaml` — owned_files.txt schema
- `schemas/agent-workspace/handoff-envelope.yaml` — handoff envelope schema
- `schemas/agent-workspace/agent-config.yaml` — `.local/.agent/config.yaml` schema
- `schemas/agent-workspace/source-of-truth-spec.yaml` — `.local/memory/specs/<domain>/spec.md` schema
- `schemas/lean-dispatch.yaml#layout_invariant` — cache layout v5 with `change_context` at position 16
- `workflow-system/agent/templates/builtin/change-driven.yaml` — workflow template binding
- `.local/research/v8.3.0_design.md` — full design (this reference is the SKILL-surface summary)
- `.local/research/v8.3.0_openspec_deep_analysis.md` — OpenSpec patterns adopted/adapted/rejected
- `.local/research/v8.3.0_gap_analysis.md` — gap inventory (C-002, C-003, H-002, H-003, H-004, H-005, H-006, M-003, M-004, M-005)
- `.cursor/rules/repo-governance.mdc` — S-8 (file ownership), S-9 (handoff append-only), C-9 (token budgets), A-4 (source-of-truth ADR)
- `references/agent-hierarchy.md` — 4-layer agent hierarchy this workspace serves
- `references/decomposition-gate.md` — wave/task constraints that determine `owned_files.txt` shape
- `references/message-schemas.md` — TaskDispatch / StatusReport / Escalation schemas wrapped by handoff envelope

### External

- OpenSpec source: `https://github.com/Fission-AI/OpenSpec` — origin of the
  ADDED/MODIFIED/REMOVED delta format and the propose → apply → verify →
  archive lifecycle. Adopted in v8.3.0 per the deep-analysis artifact.
- DevolaFlow source: `https://github.com/YoRHa-Agents/DevolaFlow` (per S-7).
