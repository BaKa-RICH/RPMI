---
id: "agent/references/agent-hierarchy"
version: "1.0.0"
purpose: >
  Defines the 4-layer agent hierarchy (Project → Stage → Wave → Task) with full
  specifications per layer, delegation rules, prohibited actions, context budgets,
  and message flow. Use this when setting up agents, debugging delegation failures,
  or understanding layer responsibilities.
triggers:
  - "setting up agent hierarchy"
  - "debugging delegation"
  - "understanding layer roles"
tier: 2
token_estimate: 3200
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-04-23"
---

# Agent Hierarchy Reference

## 1. Architecture Overview
From §2.1:

```
  Human
    │
    ▼
  [L0 Project Agent]  ──dispatch──►  [L1 Stage Agent]
                                          │
                                     dispatch
                                          ▼
                                     [L2 Wave Agent]
                                          │
                                     dispatch (parallel)
                                     ┌────┼────┐
                                     ▼    ▼    ▼
                                   [L3] [L3] [L3]   ◄── Task Agents (do work)
                                     │    │    │
                                     report report
                                     └────┼────┘
                                          ▼
                               [L2] ──report──► [L1] ──report──► [L0]
```

**Invariant P1 — Dispatcher-Not-Implementer:** Layers 0–2 dispatch, monitor,
and report. Only Layer 3 Task Agents execute actual work.

## 2. Layer Specification Table
From §2.2–2.5:

| Aspect | L0 Project | L1 Stage | L2 Wave | L3 Task |
|--------|-----------|----------|---------|---------|
| **Role** | Top-level orchestrator | Single-stage owner | Parallel task coordinator | Leaf worker |
| **Count** | 1 per project | 3–8 per project | 1–7 per stage | 1–5 per wave |
| **Lifespan** | Entire run | Per stage | Per wave | Per task |
| **Does work?** | NO | NO | NO | **YES** |
| **Context budget** | ~3K tokens | ~5K tokens | ~4K tokens | ~8K tokens |
| **Receives** | User request, workflow type | StageDispatch | WaveDispatch | TaskDispatch |
| **Produces** | Final project report | StageReport (PASS/FAIL) | WaveReport | TaskReport |
| **Reports to** | Human user | Project Agent | Stage Agent | Wave Agent |
| **Delegates to** | Stage Agents | Wave Agents | Task Agents | Nothing (leaf) |
| **State owned** | `project_status.yaml` | `stage_{id}/README.md` | In-memory only | Task-scoped files |
| **Tools** | TodoWrite, file R/W | TodoWrite, file R/W | TodoWrite, Task tool | ALL tools |

## 3. Per-Layer Behavioral Contracts
From §2.2–2.5:

### L0 — Project Agent

1. Determine workflow type from user request (heuristics from SKILL.md §Quick Start)
2. Instantiate workflow template — resolve stage list, gate conditions, loop-back rules
3. Dispatch stages sequentially (or parallel where template allows)
4. After each stage: evaluate gate. PASS → advance. FAIL → loop-back per template
5. On completion: produce final report
6. On unrecoverable failure: halt + divergence report for human

### L1 — Stage Agent

1. Receive StageDispatch; analyze scope; decompose into waves
2. For each wave: determine parallel tasks (file ownership + dependency constraints)
3. Dispatch waves sequentially — Wave N+1 starts only after Wave N completes
4. After all waves: aggregate results; evaluate stage gate
5. If convergence loop applies: run review→fix→test→fix cycle as waves
6. Report StageReport upward

**Wave decomposition rules:**
- Tasks within a wave MUST be independent (no shared writable files, no data deps)
- Maximum 5 tasks per wave
- Each task MUST own a disjoint set of files

### L2 — Wave Agent

1. Validate all task specifications (task_id, description, owned_files, acceptance_criteria)
2. Dispatch all tasks in parallel using Task tool
3. Monitor completion; record status and artifacts per task
4. On recoverable task failure: retry once; on second failure: mark failed, continue
5. After all tasks: aggregate results; check cross-task conflicts
6. Report WaveReport upward

### L3 — Task Agent

1. Receive TaskDispatch with context injection
2. Execute the assigned work using ALL available tools
3. Produce TaskReport even on failure (with error details)
4. Follow applicable code-rules loaded per context injection

**Task Agent type specializations:**

| Task Type | Primary Tools | Typical Output |
|-----------|--------------|----------------|
| `code` | Read, Write, StrReplace, Shell | Modified/new source files |
| `test` | Shell, Read, Write | Test results, coverage report |
| `review` | Read, Grep, SemanticSearch | Severity-classified findings |
| `research` | WebSearch, WebFetch, Read | Research report, comparison matrix |
| `design` | Read, Write, SemanticSearch | Design document section |
| `benchmark` | Shell, Read | Benchmark results, baseline comparison |

## 4. MUST / MUST NOT Rules
From §1 (P1), §2.2–2.5:

| Layer | MUST | MUST NOT |
|-------|------|----------|
| **L0 Project** | Dispatch stages, track status, enforce gates, report to human | Write code, run tests/shell, read source files, author designs, skip gates, reorder stages |
| **L1 Stage** | Dispatch waves, aggregate wave results, run gate evaluations | Write code, run tests, perform reviews, author content, dispatch >5 tasks/wave |
| **L2 Wave** | Dispatch tasks in parallel, collect results, report to Stage | Do any task's work, modify task outputs, retry >1 time, wait indefinitely |
| **L3 Task** | Execute assigned work, produce TaskReport, follow code-rules | Spawn sub-agents, delegate work, modify files outside owned set, exceed timeout |

## 5. Delegation Rules
From §2, §7:

### Delegation Direction

```
Dispatch flows DOWN:    L0 → L1 → L2 → L3
Reports flow UP:        L3 → L2 → L1 → L0
Escalation flows UP:    L3 → L2 → L1 → L0 → Human
```

### Constraints

| Rule | Value |
|------|-------|
| Max tasks per wave | 5 |
| Max waves per stage | 7 |
| Max files per task (writable) | 6 |
| Max files per task (readable) | 15 |
| Max lines changed per task | ~300 net |
| Max task duration (impl) | 30 min |
| Max task duration (research) | 45 min |
| File ownership within wave | Disjoint (strict) |
| Read-only file sharing within wave | Allowed |

### Fail-Forward Protocol
From §SKILL.md, Appendix:

```
1. Task fails → Wave retries once with error context
     → still fails → escalate to Stage

2. Wave fails → Stage retries failed tasks only
     → still fails → escalate to Project

3. Stage gate fails → Project evaluates:
     loop-back (max 2 retries per stage) or escalate to human

4. Project loop-back budget: 3 total across all stages
     → exceeded → halt with divergence report
```

**Escalation chain:** Task → Wave → Stage → Project → Human.
Always upward, never skip levels. Every loop has `max_iterations`.
Every failure is classified (retry / escalate / abort). No infinite loops.

## 6. Context Budget Details
From §1 (P2), §6.5:

| Layer | Strategy | Budget | Loaded Content |
|-------|----------|--------|----------------|
| L0 Project | Minimal | ~3K tokens | Workflow template, project config, stage status dashboard |
| L1 Stage | Standard | ~5K tokens | Stage definition, predecessor artifact summaries, wave plan |
| L2 Wave | Minimal | ~4K tokens | Wave task list, task status tracking |
| L3 Task | Standard–Full | ~8K tokens | Task spec, owned files, code-rules, design excerpt |

**Context injection breakdown for L3 Task Agents:**

| Section | Token Range | Content |
|---------|-------------|---------|
| Identity | ~100 | role, task_id, team |
| Task spec | 500–1500 | title, description, acceptance_criteria |
| Scoped context | 1000–3000 | predecessor_summary, design_excerpt, interfaces |
| File scope | 200–500 | owned files (create/modify), read_only files |
| Rules | 2000–5000 | loading_strategy, language, quality_focus |
| Behavioral | ~200 | timeout, max_files, output_format, escalation |

## 7. Layer Comparison Summary
From §2.6:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        DELEGATION DIRECTION (↓)                        │
│                        REPORTING DIRECTION (↑)                         │
├──────────┬────────────┬──────────────┬──────────────┬─────────────────┤
│  Layer   │   Count    │   Lifespan   │  Does Work?  │  Context Size   │
├──────────┼────────────┼──────────────┼──────────────┼─────────────────┤
│ Project  │     1      │ Entire run   │     NO       │   ~3K tokens    │
│ Stage    │   3–8      │ Per stage    │     NO       │   ~5K tokens    │
│ Wave     │   1–7/stg  │ Per wave     │     NO       │   ~4K tokens    │
│ Task     │  1–5/wave  │ Per task     │    YES       │   ~8K tokens    │
└──────────┴────────────┴──────────────┴──────────────┴─────────────────┘
```

## 8. File System Layout
From §Appendix B:

```
.local/
├── project_status.yaml                # L0: Project Agent dashboard
├── workflow_config.yaml               # Workflow template + config
├── stages/
│   ├── overview.md                    # Stage tracking summary
│   ├── S01_design/
│   │   ├── README.md                  # Stage scope, wave plan
│   │   ├── dispatch.yaml              # StageDispatch message
│   │   ├── report.yaml                # StageReport produced
│   │   ├── waves/
│   │   │   ├── W01/
│   │   │   │   ├── dispatch.yaml      # WaveDispatch
│   │   │   │   ├── report.yaml        # WaveReport
│   │   │   │   └── tasks/
│   │   │   │       ├── T01_dispatch.yaml
│   │   │   │       └── T01_report.yaml
│   │   │   └── W02/ ...
│   │   ├── gate_report.yaml           # Gate decision record
│   │   └── artifacts/                 # Stage deliverables
│   └── S02_plan/ ...
├── handoffs/                          # Handoff deliverable envelopes
│   ├── research_to_design.yaml
│   └── design_to_implement.yaml
└── escalations/
    └── ESC_001.yaml                   # Exception escalation records
```

## 9. Convergence Loop
From §Appendix C:

8-phase loop for implementation stages, each phase dispatched as a wave:

```
Round N:
  Phase 1: CODE REVIEW        (Review Agent)
  Phase 2: FIX review findings (Implement Agent)
  Phase 3: TEST               (Test Agent)
  Phase 4: FIX test failures   (Implement Agent)
  Phase 5: BENCHMARK           (Test Agent)
  Phase 6: FIX bench issues    (Implement Agent)
  Phase 7: FINAL REVIEW        (Review Agent)
  Phase 8: FIX final findings  (Implement Agent)

  Gate Decision:
    composite ≥ 85 AND round ≥ min AND 0 blockers → PASS
    composite < 85 AND round < max              → NEXT ROUND
    round ≥ max                                  → ESCALATE
```

Defaults: min_rounds=1, max_rounds=3 (configurable, range 1–6).
Stage Agent orchestrates the loop — never executes any phase directly.
