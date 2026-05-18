---
id: "agent/references/context-isolation"
version: "1.0.0"
purpose: >
  Defines the context isolation strategy including the 3 failure modes it
  prevents, how subagents get isolated context windows, the full context
  injection template (YAML), what must NOT leak between agents (6 categories),
  what IS shared, and context budget management by layer with max files/tokens.
triggers:
  - "setting up context injection"
  - "debugging context leaks"
  - "configuring agent budgets"
tier: 2
token_estimate: 3400
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-04-23"
---

# Context Isolation Reference

## 1. Isolation Principles
From §6.1:

Context isolation prevents three failure modes:

| # | Failure Mode | Description | Consequence If Not Prevented |
|---|-------------|-------------|------------------------------|
| 1 | **Context pollution** | Task Agent's working memory fills with irrelevant information from other tasks | Degraded output quality; agent reasoning contaminated |
| 2 | **Cross-task interference** | Parallel tasks inadvertently share or conflict on information | Inconsistent results; hidden dependencies |
| 3 | **Budget exhaustion** | Accumulated context from multiple phases exceeds effective context window | Degraded reasoning; important details lost from attention |

These failure modes are observed across agent frameworks (MetaGPT pub-sub
pollution, OpenHands context overflow). The isolation strategy prevents
all three through enforcement at spawn time.

## 2. Isolation Mechanisms
From §6.2:

### Mechanism 1 — Fresh Context Per Spawn

Every Task Agent (Layer 3) starts with an empty context window. It receives
ONLY the TaskDispatch message and the files listed in `owned_files`. No
conversation history from prior tasks leaks in.

### Mechanism 2 — File Ownership Boundaries

Each Task Agent is authorized to read/modify ONLY files listed in its
`TaskDispatch.context.owned_files`. File ownership is partitioned at the
Wave level — no two tasks in the same wave share a writable file.

### Mechanism 3 — Artifact-Mediated Communication

Tasks never directly communicate. When Task B depends on Task A's output:

```
Task A writes to file
  → Wave Agent collects result
    → Task B receives a SUMMARY REFERENCE in context injection
      (NOT the full content)
```

## 3. Context Injection Template
From §6.3:

Every Task Agent receives this structured context at spawn time. This is
the ONLY information the Task Agent has access to (beyond its own tool outputs).

```yaml
context_injection:

  # Section 1: Identity and role (~100 tokens)
  identity:
    role: "string"                     # research | design | implement | test | review
    task_id: "string"                  # e.g., S03_W02_T01
    team: "string"                     # AgentTeam role template to follow

  # Section 2: Task specification (500-1500 tokens)
  task:
    title: "string"                    # short descriptive title
    description: "string"             # detailed what-to-do
    acceptance_criteria: ["string"]    # testable done-when conditions
    constraints: ["string"]           # non-negotiable boundaries

  # Section 3: Scoped context (1000-3000 tokens)
  context:
    predecessor_summary: "string"      # 3-5 sentence summary (NOT full artifacts)
    design_reference_excerpt: "string | null"  # relevant section ONLY (NOT full doc)
    relevant_interfaces: ["string"]    # interface signatures to respect

  # Section 4: File scope (200-500 tokens)
  files:
    owned:                             # files agent can create/modify
      - path: "string"
        purpose: "string"             # why this file is relevant
    read_only:                         # files agent can read but NOT modify
      - path: "string"
        purpose: "string"

  # Section 5: Rules (loaded per guide.md protocol) (2000-5000 tokens)
  rules:
    loading_strategy: "minimal | standard | full"
    language: "string | null"
    task_type: "string | null"
    quality_focus: ["string"]

  # Section 6: Behavioral constraints (~200 tokens)
  behavioral:
    timeout_seconds: "integer"
    max_files_to_read: "integer"       # prevent context blow-up
    output_format: "string"            # expected output structure
    escalation_contact: "wave_agent"   # who to escalate to
```

### Section Token Budgets

| Section | Tokens | Content |
|---------|--------|---------|
| Identity | ~100 | role, task_id, team |
| Task spec | 500–1500 | title, description, acceptance_criteria, constraints |
| Scoped context | 1000–3000 | predecessor_summary, design_excerpt, interfaces |
| File scope | 200–500 | owned files (create/modify), read_only files |
| Rules | 2000–5000 | Loaded per code-rules protocol |
| Behavioral | ~200 | timeout, max_files, output_format, escalation |
| **Total** | **~3800–10300** | Leaves 150K–490K for reasoning + tool outputs |

### Example Context Injection

```yaml
context_injection:
  identity:
    role: "implement"
    task_id: "S04_W02_T01"
    team: "Implement"

  task:
    title: "Implement ConfigManager module"
    description: >
      Implement the ConfigManager module that reads, validates, and merges
      configuration from TOML files, environment variables, and CLI
      arguments, following the design in design_document.md §3.2.
    acceptance_criteria:
      - "cargo build succeeds with zero warnings"
      - "cargo test config:: passes with >= 80% line coverage"
      - "ConfigManager satisfies all 4 interface methods from design §3.2"
    constraints:
      - "Must use the ConfigSource trait from config_types.rs"
      - "No unwrap() calls; all errors must use the project error type"
      - "Environment variables take precedence over TOML values"

  context:
    predecessor_summary: >
      S04_W01 created the project scaffold: Cargo.toml, src/main.rs,
      src/lib.rs, src/error.rs with the AppError type. The config_types
      module defines ConfigSource trait and Config struct.
    design_reference_excerpt: >
      §3.2 ConfigManager: 4 methods — new(sources: Vec<Box<dyn ConfigSource>>),
      load() -> Result<Config>, get(key) -> Option<Value>,
      validate() -> Result<()>. Merge order: defaults < TOML < env < CLI.
    relevant_interfaces:
      - "trait ConfigSource { fn load(&self) -> Result<Config, AppError>; }"
      - "struct Config { settings: HashMap<String, Value> }"

  files:
    owned:
      - path: "src/config/manager.rs"
        purpose: "ConfigManager implementation"
      - path: "src/config/mod.rs"
        purpose: "Module declaration"
      - path: "tests/config/manager_test.rs"
        purpose: "Unit tests"
    read_only:
      - path: "src/config/types.rs"
        purpose: "ConfigSource trait definition"
      - path: "src/error.rs"
        purpose: "AppError type"

  rules:
    loading_strategy: "standard"
    language: "rust"
    task_type: "new_feature"
    quality_focus: ["maintainability", "error_handling"]

  behavioral:
    timeout_seconds: 1800
    max_files_to_read: 10
    output_format: "TaskReport"
    escalation_contact: "wave_agent"
```

## 4. What MUST NOT Leak Between SubAgents
From §6.4:

| # | Category | What Must Not Leak | Why |
|---|----------|-------------------|-----|
| 1 | **Conversation history** | Prior task's internal reasoning, tool calls, intermediate outputs | Pollutes new task's reasoning with irrelevant context |
| 2 | **File contents from other tasks** | Source code files owned by other parallel tasks | Prevents false dependencies and conflicting assumptions |
| 3 | **Full predecessor artifacts** | Complete research reports, design documents, review reports | Context budget exhaustion; summaries are sufficient |
| 4 | **Error details from siblings** | Stack traces, failure logs from sibling tasks | Irrelevant to current task; may confuse the agent |
| 5 | **Quality scores from other tasks** | Review scores, coverage metrics from unrelated modules | Could create false pressure to match or exceed |
| 6 | **Deferred items from other stages** | Items explicitly pushed to later stages | Not actionable for the current task |

## 5. What IS Shared (Via Artifact Summaries)
From §6.4:

| Category | How Shared | Example |
|----------|-----------|---------|
| Interface contracts | Function signatures, type definitions from predecessor stages | `trait ConfigSource { fn load(&self) -> Result<Config>; }` |
| Design decisions | ADR summaries that constrain the current task | "Decision: use TOML over YAML for config (rationale: ...)" |
| Naming conventions | Project-wide patterns from code-rules | `snake_case` for Rust, module naming patterns |
| Quality thresholds | Acceptance criteria from project configuration | "coverage >= 80%, zero blockers" |
| Acceptance criteria | From the task's own TaskDispatch | Binary testable conditions |

**Key rule:** Share summaries and contracts, never full content.
Predecessor artifacts are summarized to 3-5 sentences max.

## 6. Context Budget Management by Layer
From §6.5:

| Layer | Strategy | Budget | What's Loaded | Max Files | Max Tokens |
|-------|----------|--------|---------------|-----------|------------|
| L0 Project | Minimal | ~3K | Workflow template, project config, stage status dashboard | 3 | 3000 |
| L1 Stage | Standard | ~5K | Stage definition, predecessor artifact summaries, wave plan | 5 | 5000 |
| L2 Wave | Minimal | ~4K | Wave task list, task status tracking | 3 | 4000 |
| L3 Task | Standard–Full | ~8K | Task spec, owned files, code-rules, design excerpt | 15 (read) + 6 (write) | 8000 |

### Loading Strategy Reference

| Strategy | Description | Used By |
|----------|-------------|---------|
| **Minimal** | Only essential context; no file contents, no deep references | L0 Project, L2 Wave |
| **Standard** | Essential context + key excerpts from predecessor artifacts | L1 Stage, L3 Task (typical) |
| **Full** | Standard + complete code-rules + detailed design references | L3 Task (complex tasks) |

### Budget Enforcement Rules

1. **Hard caps:** No layer may exceed its token budget for context injection
2. **Summarization:** Artifacts exceeding budget are auto-summarized before injection
3. **Prioritization:** Identity > Task spec > Rules > Context > Files (in priority order)
4. **Overflow handling:** If budget exceeded after prioritization, truncate lowest-priority
   sections and add `[TRUNCATED — load full content via Read tool if needed]` marker

### File Limits by Layer

| Layer | Max Writable Files | Max Readable Files | File Content in Context? |
|-------|-------------------|-------------------|-------------------------|
| L0 Project | 2 (dashboard, config) | 3 | NO (paths only) |
| L1 Stage | 2 (README, report) | 5 | Summaries only |
| L2 Wave | 0 (in-memory only) | 3 | NO (paths only) |
| L3 Task | 6 | 15 | YES (owned files loaded) |

## 7. Context Injection Checklist

Use this checklist when building context injection for a Task Agent:

```
CONTEXT INJECTION CHECKLIST
════════════════════════════

□ Identity section populated (role, task_id, team)
□ Task description is self-contained (not referencing external docs by name only)
□ Acceptance criteria are binary-testable
□ Predecessor summary is ≤ 5 sentences (not full artifact)
□ Design excerpt is the relevant section ONLY (not full doc)
□ Interface signatures are complete (types, return types, constraints)
□ Owned files listed with purpose annotations
□ Read-only files listed (dependencies the task needs to reference)
□ No file appears in both owned AND another parallel task's owned
□ Rules loading strategy matches task complexity
□ Timeout is set (default: estimated_minutes × 120 seconds)
□ max_files_to_read is set (prevents context explosion)
□ Total token estimate is within layer budget (~8K for L3)

LEAK PREVENTION CHECKS:
□ No conversation history from prior tasks included
□ No file contents from other parallel tasks included
□ No full predecessor artifacts (summaries only)
□ No error details from sibling tasks
□ No quality scores from unrelated tasks
□ No deferred items from other stages
```

## 8. Information Density Optimization (v2.2.0)

Context injection now supports density-aware loading:

**Task-Adaptive Profiles**: Six profiles (hotfix, research, design, refactor, review, feature) control which SKILL.md sections load per task type. Defined in `context_profiles.yaml`.

**Lean Message Format**: Inter-layer messages (TaskDispatch, StatusReport) use structured compact format. Key changes:
- `key_facts` lists replace paragraph summaries (verbatim extraction, zero hallucination)
- Cause→effect notation for acceptance criteria (e.g., "expired → 401")
- Abbreviated severity codes (B/C/M/m/i)

**Acceptance Readiness Gate**: Pre-workflow validation of acceptance criteria quality. Prevents budget exhaustion from rework caused by vague criteria.

## 9. Debugging Context Issues

### Symptom → Cause → Fix

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Task produces output inconsistent with design | Design excerpt missing or truncated | Expand design_reference_excerpt to cover relevant section |
| Task modifies files it shouldn't | owned_files misconfigured | Audit owned_files list; ensure disjoint within wave |
| Task reasoning seems confused | Context pollution from prior task | Verify fresh context spawn; check no history leakage |
| Task runs out of context mid-reasoning | Budget exhaustion; too much injected | Reduce context injection; use Minimal loading strategy |
| Parallel tasks produce conflicting code | Shared file ownership | Re-partition files; ensure disjoint ownership in wave |
| Task ignores interface contracts | relevant_interfaces not populated | Add interface signatures to context.relevant_interfaces |
| Task quality low despite good design | Rules not loaded or wrong strategy | Check rules.loading_strategy matches task complexity |

## 10. Cache Layout Invariant (v7.0.0+)

Long agent sessions hit a cost wall when the prompt-cache hit rate falls below
~90 %. The single largest operational lever is **structural stability of the
dispatch prefix across convergence rounds** — when round-N restructures the
cached prefix, the host KV-cache rebuilds from scratch (5–10× cost delta on
long sessions).

DevolaFlow declares a single canonical top-level key order for every lean
dispatch. The order is **additive**: each key may be absent, none may be
reordered. Positions 1-12 form the **FROZEN PREFIX** — reordering any of
the v7.0.0 baseline slots invalidates the LLM cache prefix and is a release
blocker per `v9-ADR-002` (and Soul Rule S-2 / Architecture Rule A-2
nest-vs-append clause). Positions 13-16 are **append-only** — new top-level
keys land at position N+1 where N is the current `len(canonical_order)`,
never inserted into a lower slot. Authors choosing between adding a new
top-level key vs. nesting under an existing one apply the nest-vs-append
decision rule (`v9-ADR-002` D3) — the bias is toward NEST whenever the
data shape allows.

**Canonical order (17 keys, `version: 6`):** `hdr` → `task` → `goal` →
`assumptions` → `pred` → `files` → `rules` → `shared` → `accept` →
`reinforce` (round 2+ only) → `verify_cfg` → `gate` → `repos` (v7.2.6 P-06)
→ `behavioral_guidelines` (v8.0.0 P-08) → `acceptance_criteria_v2` (v8.0.0
P-10) → `change_context` (v8.3.0 PV-05) → `predecessor_dedup_ledger`
(v9.7.0 PV-02). Source of truth:
`schemas/lean-dispatch.yaml#layout_invariant.canonical_order`.

**Validator:** `devolaflow.compressor.assert_dispatch_layout(payload)` raises
`DispatchLayoutError` on any out-of-order or pre-spec-end unknown key.
`compute_dispatch_lcp_pct(a, b)` returns the round-over-round prefix
stability fraction. **SLO:** LCP ≥ 80 % round 1→2 and ≥ 70 % round 1→3,
enforced by `tests/test_compressor.py::test_dispatch_prefix_is_stable_across_rounds`.
**Rationale:** `.local/research/adr/v7-ADR-001-cache-layout-invariant.md`.

## 11. Tool-Output Truncation (v7.0.1+)

In multi-round convergence, prior-round `tool_use` outputs (Read/Grep/Shell
returns) accumulate inside the predecessor context the L2 wave agent feeds
to the next round's L3 task agents. Anthropic's cookbook (`[ref-6]`) calls
this the "lightest-touch" lever: keep the `tool_use` record (so the model
knows the call happened) but elide the bulky `tool_result` payload once it
falls below a recency threshold. DevolaFlow ships the deterministic
prompt-side equivalent in `devolaflow.compressor` per ADR-002.

**When the runtime applies truncation.** The L3 task agent emits its
`StatusReport` with the full tool_use list. Before the L2 wave agent splices
that report into the next round's predecessor context, it calls
`clear_old_tool_uses(tool_uses, keep=3, exclude_tool_names=("Read",))`.
The default behaviour preserves the most recent 3 tool calls verbatim and
truncates the middle of older outputs (head 500 + placeholder + tail 500
chars). `Read` outputs are exempt from truncation by default because they
represent authoritative file content frequently cited verbatim during code
review. Triggering happens at round ≥ 2 only — round 1 has no
prior-round payloads to clear.

**Policy knobs.** Per-profile in
`workflow-system/agent/context_profiles.yaml`:

```yaml
tool_output_truncation:
  enabled: false                 # default at v7.0.1 cut
  keep: 3                        # most-recent-N preserved verbatim
  exclude_tool_names: ["Read"]   # never-truncated tool names
  head_chars: 500
  tail_chars: 500
```

The six decomposition-enabled profiles (`feature`, `refactor`,
`skill-optimization`, `migration`, `security-audit`, `perf-optimization`)
ship the knob disabled in v7.0.1. Operators opt in per profile after
H.1 retention data confirms safety; v7.1.0 will flip the default to
`enabled: true` cycle-wide.

**Placeholder format.** `truncate_tool_output()` substitutes `{removed}`
in `placeholder_template` (default `"[truncated {removed} chars]"`) with
the count of elided characters. The placeholder is intended for the
*model's* re-ingestion and human scan, not for programmatic JSON parsing —
truncation always lands on character boundaries, not structural ones.

**Reading the `tool_results.summary` block.** `clear_old_tool_uses()`
returns a `ToolUseTruncation` summary that the producing agent records in
`schemas/lean-report.yaml#tool_results.summary` (`kept_count`,
`cleared_count`, `cleared_at_round`). The L2 wave agent inspects the
summary to decide whether to refresh the L1 dispatch tool list:
`cleared_count > 0` is the canonical signal that round-N reused fewer
verbatim tool outputs than round-(N−1) and the cached prefix is starting
to drift. Together with the cache-layout invariant (§10), this is the
prompt-side mechanism for keeping convergence-round dispatches inside
their token budget without sacrificing recent-call fidelity.

**Rationale:** `.local/research/adr/v7-ADR-002-tool-output-truncation.md`.
**Sub-agent budget bump (K.8 resolution):** the same six profiles raise
`decomposition.sub_agent_context_budget` from 3000 → 5000 tokens at the
v7.0.1 cut so a sub-agent can absorb the verbatim recent-N records without
spillover.

## 12. Hierarchical Predecessor Summariser (v7.0.2+)

Predecessor artifacts from the prior stage enter a consuming layer's
dispatch under `pred[*]`. When a single artifact exceeds ~25 % of the
consuming layer's token budget (L3 8000 → 2000 tokens; L2 4000 → 1000
tokens; L1 5000 → 1250 tokens; L0 3000 → 750 tokens), embedding the body
verbatim starves every other dispatch section. DevolaFlow ships
`devolaflow.compressor.summarise_predecessor(artifact_path, *,
max_tokens=500, mode="extractive", schema_hint=None)` as the
deterministic collapse primitive. The extractive pipeline is a
fixed three-stage descent: (1) **schema-priority heading selection** —
`design` favours *Decision* > *Consequences* > *Alternatives*, `research`
favours *Recommendations* > *Open Questions* > *Synthesis*, `adr` favours
*Decision* > *Consequences* > *Test plan*, `gate_report` favours *Verdict* >
*Findings* > *Metrics*, with document-order H2 fallback; (2) **verbatim
preserve-list extraction** via `extract_named_entities()`, which surfaces
all 8 structured classes (file_paths, task_ids, version_strings,
commit_hashes, metric_values, error_messages, acceptance_criterion_bullets,
interface_signatures) as a `key_facts:` YAML prefix; (3) **sentence-level
bounded truncation** — selected sections fill the remaining `max_tokens`
budget in priority order; when a section would overflow, the renderer
inserts `[TRUNCATED]` at the token boundary and emits `was_bounded=True`.
No paraphrase ever occurs on the default path, honouring CO-2 by
construction.

Profile knobs live under each profile's `summary:` block in
`workflow-system/agent/context_profiles.yaml` (fields `mode`, `max_tokens`,
`trigger_pct`). Per-dispatch overrides travel on `pred[*].summary_mode`
and `pred[*].summary_max_tokens` — both declared in
`schemas/lean-dispatch.yaml#per_predecessor` and appended nested inside
each pred entry, *never* as new top-level keys, to preserve the §10
cache-layout invariant. Missing fields default to `extractive` / 500
tokens. Abstractive mode is reserved for narrative stage reports and
opts in per profile; it still runs the extractive pass first so the
preserve-list facts travel verbatim, and is guarded by the §13
persistence probe against named-entity drift. At the v7.1.0 cut the six
decomposition-enabled profiles (`feature`, `refactor`,
`skill-optimization`, `migration`, `security-audit`, `perf-optimization`)
default to `summary.mode: extractive` with `max_tokens: 1200` —
roomier than the schema default because these profiles consume 5000-
token sub-agent contexts.

**Rationale:** `.local/research/adr/v7-ADR-003-hierarchical-summary.md`.

## 13. Persistence Probe (v7.0.3+)

`summarise_predecessor()` is the only primitive that can silently
paraphrase a file path or a commit hash — losing a single such entity
between Stage A and Stage B breaks the P5 artifact contract and burns
a convergence round on search-instead-of-execute rabbit holes. The
persistence probe is the deterministic integration guard that catches
this failure. The harness lives in `tests/test_e2e_compression.py`
(with seed logic in `tests/_probe_fixtures.py`): it synthesises a
Stage A artifact seeded with a preserve-list panel, runs it through
`summarise_predecessor` + `render_dispatch` + `task_adaptive_selector.
select_context`, then calls `compute_entity_carrythrough_rate()` to
measure the fraction of Stage A entities that appear verbatim in the
rendered Stage B dispatch. Any paraphrase, case-fold on a
file-path/commit-hash, or outright omission fails the probe with a
diagnostic naming the lost entity.

Three scenarios ship at the v7.0.3 cut, matched to the H.1 retention
tiers: **easy** (500-token artifact, 5 seeded entities, rate ≥ 1.0,
0 misses), **medium** (5000-token artifact, 20 seeded entities, rate
≥ 0.9, ≤ 2 misses), **hard** (15000-token artifact, 50 seeded
entities, rate ≥ 0.9, ≤ 5 misses). Per-scenario elapsed time plus
the realised carry-through rate land in
`.local/research/v7.0.3_probe_telemetry.json` after each run, feeding
SI-3 evaluation. The probe is marked `@pytest.mark.persistence_probe`
and runs in the default pytest suite so SI-10 step 5 cannot merge a
summariser regression.

**Rationale:** `.local/research/adr/v7-ADR-004-persistence-probe.md`.

## 14. Operational Learnings v2 (v7.0.3+)

`src/devolaflow/learnings.py` gains four additive `Learning` fields —
`confidence_half_life_days` (default 30), `last_accessed` (ISO
timestamp), `pinned_for_session` (session id or empty), `promotion_count`
(monotonic) — plus three public helpers: `consolidate_session(session_id,
session_learnings, jsonl_path)` promotes learnings actually used during a
session (+0.05 confidence, `promotion_count++`, refreshed `last_accessed`)
or captures novel ones with `promotion_count=1`; `decay_confidence(
jsonl_path, half_life_days=None)` applies linear decay across the file;
`pin_learning_for_session(key, stage, task_type, session_id, jsonl_path)`
attaches a session pin. `load_relevant_learnings()` accepts the new
`session_id: str | None` parameter — when supplied, pinned entries for
that session are surfaced ahead of the confidence-sorted top-N and
bypass `min_confidence` (TTL + `task_type` still apply). The four new
fields default to safe zero-equivalents so legacy JSONL parses unchanged
via `Learning(**fields)` filtered through `Learning.__dataclass_fields__`.

Decay is a single linear sweep per call: for every entry,
`delta_days = (now - last_accessed)` in UTC days; `decay_factor =
min(1.0, delta_days / entry.confidence_half_life_days)`; `new_conf =
confidence - 0.5 * decay_factor`. The result is clamped to `[0.0, 1.0]`
and every entry whose new confidence falls strictly below `DECAY_FLOOR =
0.1` is pruned in-place. Pinned entries survive pruning regardless of
confidence. ADR-005 §2.4's migration shim is lazy and per-entry: on the
first `decay_confidence()` touch of a legacy v1 entry, `last_accessed`
is backfilled from the existing `timestamp` so the linear formula has a
stable anchor — no file-wide rewrite is forced and no writer ever
overwrites a non-empty `last_accessed`.

**Rationale:** `.local/research/adr/v7-ADR-005-learnings-v2.md`.

## 15. Staged Compression — End-to-End Flow (v7.1.0+)

The v7.0.x primitives compose across a convergence run as a single
context-compression staircase. Each row below describes the primitive's
active scope; rows downstream of a row do not disturb rows upstream.

| Stage                   | Round | Primitive                              | Reference | Scope                                                                          |
|-------------------------|-------|----------------------------------------|-----------|--------------------------------------------------------------------------------|
| Dispatch render         | 1+    | Cache-layout invariant                 | §10       | Freezes the 16-key top-level order (positions 1-12 frozen, 13-16 append-only) so round-N reuses round-(N−1)'s KV prefix. |
| Predecessor embed       | 1+    | Hierarchical summariser                | §12       | Collapses pred artifact > 25 % of layer budget via `summarise_predecessor()`.  |
| Predecessor embed       | 1+    | Preserve-list extraction               | §12 / §13 | `extract_named_entities()` surfaces 8 structured classes verbatim.             |
| L3 status → L2 context  | ≥ 2   | Tool-output truncation                 | §11       | `clear_old_tool_uses(keep=3, exclude=["Read"])` elides prior-round payloads.   |
| L1 → L2 → L3 pipeline   | 1+    | Persistence probe                      | §13       | CI assertion that preserve-list entities carry through Stage A → Stage B.      |
| Session end             | n/a   | Learnings consolidation / decay        | §14       | `consolidate_session()` bumps used learnings; `decay_confidence()` prunes.     |
| Next session load       | n/a   | Pinned-session surfacing               | §14       | `load_relevant_learnings(session_id=...)` surfaces pinned entries first.       |

At v7.1.0 the six decomposition-enabled profiles default to
`tool_output_truncation.enabled: true` **and** `summary.mode: extractive`
(opt-out per profile in `workflow-system/agent/context_profiles.yaml`).
The other profiles remain opt-in. Dispatch renderers that predate the
new `summary:` block continue to work: absent fields fall through to the
schema defaults (`extractive` / 500 tokens).

**Rollback posture.** Each primitive is individually reversible without
destabilising the others: disabling truncation per profile leaves the
summariser and probe untouched; removing the `summary:` block falls
through to the schema default; the persistence probe is pure test code;
learnings v2 fields are additive with safe defaults. Removing any single
primitive does NOT require a version rollback — only the coupled bundle
(SKILL.md + context profiles + compressor) needs a coordinated revert,
which the `scripts/bump_version.py` harness and SI-5 coupling already
gate.

## 16. Abstractive summariser Stage A (P-12, v8.0.0)

`summarise_predecessor(..., mode='abstractive')` is now wired via a
deterministic Stage A heuristic (no LLM). It complements the extractive
default by routing each parsed section through `_compute_information_density`
(unique-token ratio × 0.6 + entity-density signal × 0.4, both bounded to
`[0.0, 1.0]`) and switching to a denser representation when the body is
dilute:

* **Low-density sections** (`< 0.30`) collapse to ≤ 2 lines via
  `_summarise_low_density_section` — heading + first key phrase.
* **High-density sections** (`≥ 0.30`) preserve up to 5 lines via
  `_summarise_high_density_section`; if the verbatim slice would drop
  any named entity reported by `extract_named_entities`, an
  `entities: [...]` line is appended (entity preservation always wins
  over verbatim tail per AC #4 of the P-12 patch plan).
* **Empty input** falls back to the extractive path (defensive — keeps
  the v7.x byte-stable behaviour for blank artifacts).

Opt-in via `context_profiles.yaml#complex_feature.summary_mode`
= `abstractive` (top-level section, sibling to `meta:`/`sections:`/
`profiles:`, NOT a new profile — keeps profile count stable). All
existing profiles remain `extractive` (CO-2 verbatim). Stage B
(LLM-assisted, v8.2.0 PV-01) design lives in
`.local/research/v8.0.0_p12_abstractive_stage_b_design.md`.
