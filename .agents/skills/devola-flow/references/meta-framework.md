---
id: "agent/references/meta-framework"
version: "1.0.0"
purpose: >
  Defines the 14 stage primitives with full interface contracts, the dependency
  lattice, alias mapping table, 5 composition operators with YAML examples,
  formal grammar, and key composition patterns. Use this when designing workflow
  compositions, understanding stage primitives, or authoring templates.
triggers:
  - "understanding stage primitives"
  - "designing workflow composition"
  - "template authoring"
tier: 2
token_estimate: 4500
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-04-23"
---

# Meta-Framework Reference

## 1. Stage Primitive Catalog
From §2.1:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     STAGE PRIMITIVE UNIVERSE                        │
├──────────┬───────────┬───────────┬───────────┬───────────┬─────────┤
│ DISCOVER │  SHAPE    │  BUILD    │  VERIFY   │  DELIVER  │ CONTROL │
├──────────┼───────────┼───────────┼───────────┼───────────┼─────────┤
│ research │ design    │ implement │ review    │ release   │ gate    │
│ analyze  │ plan      │ refine    │ test      │ deploy    │         │
│          │           │           │ validate  │ monitor   │         │
│          │           │           │ verify    │           │         │
└──────────┴───────────┴───────────┴───────────┴───────────┴─────────┘
```

## 2. Primitive Interface Contracts
From §2.1.1–2.1.14:

### 2.1 research (Discover)

| Property | Value |
|----------|-------|
| **Input** | `ResearchRequest { question, scope[], evaluation_criteria[], source_hints[] }` |
| **Output** | `ResearchReport { findings[], comparison_matrix?, risk_assessment[], knowledge_gaps[] }` |
| **Preconditions** | Research question defined; scope boundaries set |
| **Postconditions** | findings non-empty; knowledge_gaps identified |
| **Config** | `depth: shallow|standard|comprehensive`, `source_types[]`, `time_box_minutes` |
| **Team** | Research |
| **Duration** | Medium–Long (15–45+ min) |

### 2.2 analyze (Discover)

| Property | Value |
|----------|-------|
| **Input** | `AnalyzeRequest { targets[], analysis_type, baseline_metrics? }` |
| **Output** | `AnalysisReport { findings[], hotspots[], priority_ranking[], baseline_comparison? }` |
| **Preconditions** | Target artifacts exist and are accessible |
| **Postconditions** | findings non-empty; priority_ranking sorted by severity × impact |
| **Config** | `analysis_type: code|performance|security|dependency|documentation`, `severity_threshold` |
| **Team** | Research |
| **Duration** | Medium (15–45 min) |

#### 2.2.1 Multi-team codebase analysis pattern (v9.6.0 — understand-anything integration)

For codebases spanning multiple subsystems (frontend ⊕ backend ⊕ infra),
the `analyze` primitive supports **subdomain knowledge-graph merging**
inspired by `understand-anything/skills/understand` Phase 0 step 4
(https://github.com/Lum1104/Understand-Anything). The pattern:

1. Per subsystem, dispatch a Research-team L3 task that produces a
   `<subsystem>-knowledge-graph.json` artifact under
   `.local/.agent/active/<change-id>/`.
2. After all per-subsystem analyses complete, the L1/L2 dispatcher
   delegates a **merge** L3 task that combines the per-subsystem graphs
   into a single `knowledge-graph.json` with deduplicated nodes and
   edges (the upstream tool ships a 70-line `merge-subdomain-graphs.py`
   reference implementation).
3. Downstream Design / Implement stages consume the merged graph as a
   single artifact path (per P5 Artifacts as Contracts).

This pattern preserves DevolaFlow's L2 Wave parallelism (each subsystem
analyzes in parallel) while giving downstream stages a single
authoritative artifact path. Use when `len(targets) >= 3` AND the
targets are themselves logical subsystems with stable boundaries.

### 2.3 design (Shape)

| Property | Value |
|----------|-------|
| **Input** | `DesignRequest { inputs[], constraints[], quality_requirements[], design_type }` |
| **Output** | `DesignDocument { diagrams[], interfaces[], decisions[], trade_off_analysis[], specification }` |
| **Preconditions** | At least one input artifact exists |
| **Postconditions** | specification non-empty; every constraint addressed in decisions |
| **Config** | `design_type: architecture|api|schema|component|migration_plan`, `formality`, `diagram_types[]` |
| **Team** | Design |
| **Duration** | Medium–Long (15–45+ min) |

### 2.4 plan (Shape)

| Property | Value |
|----------|-------|
| **Input** | `PlanRequest { design, capacity_constraints?, priority_rules[] }` |
| **Output** | `ImplementationPlan { waves[], dependency_matrix, risk_register[], acceptance_criteria[] }` |
| **Preconditions** | design is reviewed and approved (gate-passed) |
| **Postconditions** | Every requirement maps to ≥1 task; no unresolvable cycles in dependency_matrix |
| **Config** | `granularity: coarse|standard|fine`, `max_parallel_waves`, `estimate_unit` |
| **Team** | Design |
| **Duration** | Medium (15–45 min) |

### 2.5 implement (Build)

| Property | Value |
|----------|-------|
| **Input** | `ImplRequest { tasks[], code_rules[], language_conventions[], existing_code_context[] }` |
| **Output** | `ImplResult { artifacts[], files_changed[], tests_written[], build_status }` |
| **Preconditions** | tasks non-empty; code_rules loaded |
| **Postconditions** | Every task has ≥1 artifact; build_status is success |
| **Config** | `test_strategy: tdd|test_after|no_test`, `code_style`, `target_coverage` |
| **Team** | Implement |
| **Duration** | Long (45+ min) |

### 2.6 review (Verify)

| Property | Value |
|----------|-------|
| **Input** | `ReviewRequest { artifacts[], checklist, acceptance_criteria[], review_type }` |
| **Output** | `ReviewVerdict { decision, score, findings[], blocking_count, suggestion_count }` |
| **Preconditions** | artifacts non-empty; checklist defined |
| **Postconditions** | decision set; every finding has severity classification |
| **Config** | `review_type: design|code|security|documentation`, `pass_threshold`, `require_zero_blocking` |
| **Team** | Review |
| **Duration** | Medium (15–45 min) |

### 2.7 test (Verify)

| Property | Value |
|----------|-------|
| **Input** | `TestRequest { code_refs[], test_suites[], coverage_threshold }` |
| **Output** | `TestResult { suite_results[], pass_rate, coverage, failures[], performance_metrics? }` |
| **Preconditions** | Code compiles/lints clean; test infrastructure available |
| **Postconditions** | Every requested suite has a result entry |
| **Config** | `suites[]`, `coverage_threshold`, `timeout_per_suite`, `fail_fast` |
| **Team** | Test |
| **Duration** | Medium (15–45 min) |

### 2.8 validate (Verify)

| Property | Value |
|----------|-------|
| **Input** | `ValidateRequest { review_verdict?, test_result?, acceptance_criteria[], quality_thresholds }` |
| **Output** | `ValidationReport { ready, unmet_criteria[], metric_summary, gap_analysis[] }` |
| **Preconditions** | At least one of review_verdict or test_result provided |
| **Postconditions** | ready is deterministic; every unmet criterion has gap_analysis entry |
| **Config** | `require_all_criteria`, `allow_waivers`, `waiver_authority` |
| **Team** | Review |
| **Duration** | Quick (<15 min) |

### 2.9 refine (Build)

| Property | Value |
|----------|-------|
| **Input** | `RefineRequest { findings[], original_artifacts[], refine_scope }` |
| **Output** | `RefineResult { updated_artifacts[], changelog[], unresolved[] }` |
| **Preconditions** | findings non-empty |
| **Postconditions** | Every finding resolved (in changelog) or listed in unresolved with reason |
| **Config** | `scope: targeted|broad`, `allow_new_features: false`, `max_file_changes` |
| **Team** | Implement (code) or Design (design) |
| **Duration** | Medium (15–45 min) |

### 2.10 release (Deliver)

| Property | Value |
|----------|-------|
| **Input** | `ReleaseRequest { artifacts[], version_strategy, changelog_template?, target_environments[] }` |
| **Output** | `ReleaseRecord { version, tag, changelog, artifacts_published[], deployment_status? }` |
| **Preconditions** | All quality gates passed; changelog drafted |
| **Postconditions** | version tag created; changelog non-empty |
| **Config** | `version_strategy: semver|calver|manual`, `require_human_approval`, `draft_mode` |
| **Team** | Implement |
| **Duration** | Quick–Medium |

### 2.11 deploy (Deliver)

| Property | Value |
|----------|-------|
| **Input** | `DeployRequest { release, environment, strategy, rollback_plan }` |
| **Output** | `DeployResult { environment, status, health_check, rollback_available }` |
| **Preconditions** | release exists; environment accessible |
| **Postconditions** | status set; health_check executed |
| **Config** | `strategy: rolling|blue_green|canary|immediate`, `auto_rollback_on_failure` |
| **Team** | Implement |
| **Duration** | Medium (15–45 min) |

### 2.12 monitor (Deliver)

| Property | Value |
|----------|-------|
| **Input** | `MonitorRequest { deployment, watch_metrics[], anomaly_thresholds[], duration_minutes }` |
| **Output** | `MonitorReport { status, anomalies[], metric_snapshots[], recommendation }` |
| **Preconditions** | deployment status is success |
| **Postconditions** | ≥1 metric_snapshot captured; recommendation set |
| **Config** | `duration_minutes`, `check_interval_seconds`, `alert_on_degraded` |
| **Team** | Test |
| **Duration** | Long (45+ min) |

### 2.13 verify (Verify)

| Property | Value |
|----------|-------|
| **Input** | `VerifyRequest { test_artifacts[], acceptance_criteria[], visual_baselines[], user_flow_definitions[], accessibility_config }` |
| **Output** | `VerifyResult { visual_fidelity_score, interaction_quality_score, acceptance_verification_score, accessibility_score, findings[], artifact_paths { screenshots[], diff_images[], flow_reports[] } }` |
| **Preconditions** | Implementation complete; developer-side tests passing |
| **Postconditions** | User-facing quality dimensions scored; findings classified by severity |
| **Config** | See `verify_config` below |
| **Team** | Test |
| **Duration** | Medium (15–30 min) |

**`verify_config` detail:**

```yaml
verify_config:
  visual_testing:
    enabled: boolean      # default: true for web projects
    tool: "playwright | backstopjs | percy"
    threshold: number     # screenshot pass rate threshold
    mask_dynamic: boolean # mask timestamps, animations
  acceptance_testing:
    enabled: boolean
    framework: "gherkin | robot | custom"
    criteria_source: "plan.acceptance_criteria"
  interaction_testing:
    enabled: boolean
    tool: "playwright | cypress"
    flows: ["string"]     # user flow definitions
  accessibility:
    enabled: boolean
    tool: "axe-core | pa11y | lighthouse"
    standard: "WCAG2.1-AA"
    threshold: number     # minimum score
```

### 2.14 gate (Control)

| Property | Value |
|----------|-------|
| **Input** | `GateRequest { criteria[], inputs }` |
| **Output** | `GateResult { passed, criteria_results[], blocking_failures[] }` |
| **Preconditions** | All referenced inputs exist |
| **Postconditions** | Every criterion has a result; passed is deterministic |
| **Config** | `on_fail: loop_back|escalate|block`, `loop_back_target?`, `require_human_override` |
| **Team** | (orchestrator) |
| **Duration** | Quick (<15 min) |

## 3. Dependency Lattice
From §2.2:

Valid direct-successor relationships between primitives:

```
research ──► analyze
research ──► design
analyze  ──► design, plan, refine
design   ──► plan, review
plan     ──► implement
implement──► review, test
review   ──► refine, validate, verify
test     ──► refine, validate, verify
refine   ──► implement, design, review, test
validate ──► release, refine
verify   ──► gate, validate, release
release  ──► deploy
deploy   ──► monitor
monitor  ──► refine
gate     ──► (insertable between any two connected primitives)
```

Templates may override with explicit `allow_transition` annotations.

## 4. Alias Mapping Table
From §2.3:

The 22 builtin templates live in `workflow-system/agent/templates/builtin/*.yaml`.
The alias table below covers the workflow-specific names each template
exposes plus the mapping back to the canonical primitive surface from §2.

| Workflow-Specific Name | Maps To Primitive | Workflow Type |
|------------------------|-------------------|---------------|
| bug-triage | analyze | hotfix |
| fix | implement + refine | hotfix |
| compare | analyze | research-only |
| report | validate + release | research-only |
| requirements | analyze | design-only |
| document | release | design-only |
| refactor | implement | refactoring |
| verify | validate | refactoring, security-audit |
| assess | analyze | migration |
| migrate | implement | migration |
| cutover | deploy | migration |
| hypothesis | research | spike-poc |
| prototype | implement | spike-poc |
| evaluate | review + validate | spike-poc |
| decide | gate | spike-poc |
| audit | analyze | documentation-only |
| write | implement | documentation-only |
| publish | release + deploy | documentation-only |
| scan | analyze | security-audit |
| prioritize | plan | security-audit |
| profile | analyze | performance-optimization |
| optimize | implement | performance-optimization |
| benchmark | test | performance-optimization |
| scope | analyze | feature-enhancement |
| testgate | gate + validate | full-pipeline |
| user-verification | verify | feature-enhancement, full-pipeline |
| visual-test | verify | demo-showcase, full-pipeline |
| acceptance-check | verify | feature-enhancement, full-pipeline |
| propose | research + design | change-driven |
| apply | implement | change-driven |
| archive | release | change-driven |
| storyboard | design | demo-showcase |
| demo | release + deploy | demo-showcase |
| install | implement | dependency-setup |
| init-deps | analyze + implement | dependency-setup |
| sweep | analyze + refine | entropy-cleanup |
| consolidate | implement + release | entropy-cleanup |
| triage | analyze | feature-enhancement |
| enhance | implement | feature-enhancement |
| nines-analyze | analyze | nines-assisted |
| nines-eval | review + validate | nines-assisted |
| onboard | implement | onboarding |
| bootstrap-skill | release | onboarding |
| product-verify | verify | product-verification |
| acceptance-verify | verify | product-verification |
| upgrade-skill | refine | self-update |
| skill-bump | release | self-update |
| skill-extract | refine | skill-optimization |
| skill-compress | implement | skill-optimization |

### Per-Workflow Template Catalog

The 22 builtin templates and their canonical primitive sequence.
**`(legacy)` = REGISTERED but v9.0.0..v10.3.0 cycle did NOT invoke; preserved for backward compat; Phase B compose-not-define collapse deferred to v12.0+** per `.local/research/v11.0.0_patches/D-A-2.md` §1 audit (v10.5.0 PV-02).

| # | Template (`.yaml` basename) | Canonical primitive sequence | Notes |
|---|-----------------------------|------------------------------|-------|
| 1 | `change-driven` | propose → (apply ↔ verify) → archive | v8.3.0 PV-06; 4-stage with `apply ↔ verify` convergence loop (max_rounds=5 per W-8) |
| 2 | `demo-showcase` (legacy) | design → storyboard → implement → verify → demo | visual-test + acceptance-check flavours |
| 3 | `dependency-setup` (legacy) | analyze → install → verify | init-deps lifecycle |
| 4 | `design-only` (legacy) | requirements → design → review | gate-passed design doc |
| 5 | `documentation-only` (legacy) | audit → write → publish | terminal release primitive |
| 6 | `entropy-cleanup` (legacy) | sweep → consolidate → release | v8.0.0 P-11; refine + implement |
| 7 | `feature-enhancement` (legacy) | triage → scope → design → implement → test → review → verify | acceptance-check + user-verification flavours |
| 8 | `full-pipeline` (legacy) | research → design → plan → implement → review → test → testgate → release | gate-guarded; visual-test + user-verification + acceptance-check flavours |
| 9 | `hotfix` (legacy) | bug-triage → fix → test | trivial scope; minimal review |
| 10 | `migration` | assess → migrate → cutover → verify | analyze + implement + deploy + validate |
| 11 | `nines-assisted` | nines-analyze → nines-eval → review → validate | external NineS subprocess; analyze + review primitives |
| 12 | `onboarding` (legacy) | onboard → bootstrap-skill | implement + release |
| 13 | `performance-optimization` (legacy) | profile → optimize → benchmark | analyze + implement + test |
| 14 | `product-verification` (legacy) | design → product-verify → acceptance-verify | verify primitive (visual + acceptance + interaction + a11y) |
| 15 | `refactoring` (legacy) | refactor → verify | implement + validate; no new features |
| 16 | `repo-init` | analyze → scaffold → compile → verify | initial repo bootstrap |
| 17 | `research-design-review-refine` (RDRR) (legacy) | research → design → review → refine | knowledge-loop pattern |
| 18 | `research-only` (legacy) | research → compare → report | validate + release |
| 19 | `security-audit` (legacy) | scan → prioritize → fix → verify | analyze + plan + implement + validate |
| 20 | `self-update` | upgrade-skill → skill-bump | refine + release |
| 21 | `skill-optimization` | skill-extract → skill-compress | refine + implement |
| 22 | `spike-poc` (legacy) | hypothesis → prototype → evaluate → decide | research + implement + review + gate |

### repo-init

| Property | Value |
|----------|-------|
| **Stages** | `analyze → scaffold → compile → verify` |
| **Gate Type** | standard |
| **Threshold** | 85 |
| **Description** | Initialize repo workspace (.local/) and governance rules (.rules/), compile rules to all detected AI tools |
| **Teams** | Research (analyze), Implement (scaffold, compile), Test (verify) |

## 5. Composition Operators
From §3.1:

### 5.1 sequence (→)

```yaml
compose: sequence
stages: [A, B, C]
```

Semantics: `start(B)` requires `completed(A)`. State flows forward only.

### 5.2 parallel (||)

```yaml
compose: parallel
stages: [A, B, C]
join: all            # all | any | n_of(k)
```

Join strategies: `all` (wait for every branch), `any` (first completes),
`n_of(k)` (k branches complete).

### 5.3 choice (⊕)

```yaml
compose: choice
condition: "review.decision == 'pass'"
if_true:
  stage: release
if_false:
  stage: refine
```

Exactly one branch executes. Supports `and`, `or`, `not` compound predicates.

### 5.4 loop (↻)

```yaml
compose: loop
name: review_refine_cycle
body:
  compose: sequence
  stages: [review, refine]
until: "review.decision == 'pass'"
max_iterations: 3
on_exhaustion: escalate     # escalate | abort | continue
escalation_target: plan
```

### 5.5 gate (⊣)

```yaml
compose: gate
name: release_readiness
criteria:
  - field: test_result.pass_rate
    operator: ">="
    value: 1.0
  - field: review_verdict.blocking_count
    operator: "=="
    value: 0
on_pass: release
on_fail:
  compose: sequence
  stages: [refine, implement]
  loop_back_to: test
```

## 6. Formal Grammar (BNF)
From §3.3:

```
Workflow   ::= Template Stage+
Stage      ::= Primitive | Composed
Composed   ::= Sequence | Parallel | Choice | Loop | Gate
Sequence   ::= 'sequence' '[' Stage (',' Stage)+ ']'
Parallel   ::= 'parallel' '[' Stage (',' Stage)+ ']' JoinStrategy
Choice     ::= 'choice' Predicate Stage Stage
Loop       ::= 'loop' Name Stage Predicate MaxIter OnExhaustion
Gate       ::= 'gate' Name Criterion+ Stage Stage

Primitive  ::= 'research' | 'analyze' | 'design' | 'plan'
             | 'implement' | 'review' | 'test' | 'validate'
             | 'verify' | 'refine' | 'release' | 'deploy'
             | 'monitor' | 'gate'

Predicate  ::= FieldRef Operator Value
             | Predicate 'and' Predicate
             | Predicate 'or' Predicate
             | 'not' Predicate

JoinStrategy ::= 'all' | 'any' | 'n_of(' Int ')'
OnExhaustion ::= 'escalate' StageRef | 'abort' | 'continue'
```

Operators nest arbitrarily. A `sequence` can contain a `loop` whose body
contains a `parallel` block with a `choice` inside.

## 7. Key Composition Patterns
From §3.4:

### Pattern A: Quality Loop (Review-Refine)

```
Work Stage ──► Review ──pass──► Next Stage
                 │
                fail
                 │
                 ▼
              Refine ──► Work Stage
                 │
         max_iterations exceeded
                 ▼
             Escalate
```

### Pattern B: Correctness Loop (Test-Fix)

```
Work Stage ──► Test ──all pass──► Next Stage
                │
             failures
                │
                ▼
             Refine ──► Work Stage
                │
         max_iterations exceeded
                ▼
             Escalate
```

### Pattern C: Knowledge Loop (Evaluate-Investigate)

```
Analysis Stage ──► Evaluate ──complete──► Next Stage
                      │
                  gaps found
                      │
                      ▼
                   Research ──► Analysis Stage
                      │
               max_iterations exceeded
                      ▼
               Proceed Best-Effort
```

### Pattern D: Gate-Guarded Release

```
Validate/TestGate ──all met──► Release
        │
    criteria unmet
        │
        ▼
     Refine ──► Implement ──► Test ──► Validate
        │
  max retries exceeded
        ▼
  Human Escalation
```

## 8. Nested Composition Example
From §3.2: Full-pipeline review-test cycle:

```yaml
compose: sequence
stages:
  - design
  - plan
  - compose: loop
    name: impl_cycle
    body:
      compose: sequence
      stages:
        - implement
        - compose: loop
          name: review_refine
          body:
            compose: sequence
            stages:
              - review
              - compose: choice
                condition: "review.decision == 'pass'"
                if_true: { break: true }
                if_false: { stage: refine }
          until: "review.decision == 'pass'"
          max_iterations: 3
          on_exhaustion: escalate
          escalation_target: plan
        - compose: loop
          name: test_fix
          body:
            compose: sequence
            stages:
              - test
              - compose: choice
                condition: "test_result.pass_rate == 1.0"
                if_true: { break: true }
                if_false: { stage: refine }
          until: "test_result.pass_rate == 1.0"
          max_iterations: 5
          on_exhaustion: escalate
          escalation_target: plan
    until: "false"
    max_iterations: 2
  - compose: gate
    name: testgate
    criteria:
      - { field: test_result.pass_rate, operator: ">=", value: 1.0 }
      - { field: test_result.coverage, operator: ">=", value: 0.80 }
      - { field: review_verdict.blocking_count, operator: "==", value: 0 }
    on_pass: release
    on_fail:
      compose: sequence
      stages: [refine, implement]
      loop_back_to: test_fix
```
