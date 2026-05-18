---
id: "agent/references/team-roles"
version: "1.0.0"
purpose: >
  Specifies the 5 AgentTeam roles (Research, Design, Implement, Test, Review)
  with their responsibilities, standard workflows, input/output contracts,
  quality criteria, tools/skills, team participation matrix by workflow type,
  and handoff protocol with deliverable format.
triggers:
  - "configuring task agents"
  - "understanding team capabilities"
  - "setting up handoff protocols"
tier: 2
token_estimate: 4200
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-04-23"
---

# Team Roles Reference

## 1. Team Relationship to Layers
From §4.0:

```
Layer 0 (Project)  ── workflow-type-agnostic orchestrator
Layer 1 (Stage)    ── stage-type-agnostic orchestrator
Layer 2 (Wave)     ── parallel-dispatch coordinator
Layer 3 (Task)     ── AgentTeam member (one of 5 roles)
                       ├── Research Agent
                       ├── Design Agent
                       ├── Implement Agent
                       ├── Test Agent
                       └── Review Agent
```

Teams are role classifications for Layer 3 Task Agents. The task's `type`
field in TaskDispatch determines which team role template configures the agent.

## 2. Research Team
From §4.1:

**Role:** Gather, analyze, and synthesize information. Establishes the
knowledge foundation that downstream teams build upon.

### Standard Workflow

```
1. SCOPE      — Parse research question; identify evaluation criteria
2. GATHER     — Search web, read docs, scan codebases, fetch references
3. ANALYZE    — Compare findings against criteria; build comparison matrices
4. SYNTHESIZE — Produce structured report with recommendations + confidence
5. SELF-CHECK — Verify all criteria addressed; flag gaps
```

### Input Contract

```yaml
research_task_input:
  research_question: "string"
  scope_boundaries:
    include: ["string"]
    exclude: ["string"]
  evaluation_criteria: ["string"]
  prior_findings: "string | null"
  output_format: "report | matrix | brief"
  max_sources: "integer"
```

### Output Contract

```yaml
research_task_output:
  report_path: "string"
  summary: "string"                    # 3-5 sentence executive summary
  findings_count: "integer"
  sources_consulted: "integer"
  confidence: "high | medium | low"
  gaps_identified: ["string"]
  recommendation: "string | null"
```

### Quality Criteria

| Criterion | Requirement |
|-----------|-------------|
| Criteria coverage | All evaluation criteria addressed (100%) |
| Source diversity | ≥ 3 distinct sources per major finding |
| Comparison matrix | Included when comparing 2+ alternatives |
| Confidence | Self-assessed and justified |
| Gap transparency | Gaps explicitly identified |

### Tools/Skills

`WebSearch`, `WebFetch`, `Read`, `Glob`, `Grep`, `SemanticSearch`, `Write`,
explore subagent type

## 3. Design Team
From §4.2:

**Role:** Synthesize requirements and research into concrete design
artifacts — architectures, API specs, data models, interface contracts, ADRs.

### Standard Workflow

```
1. REQUIREMENTS — Extract and formalize from predecessor artifacts
2. CONSTRAINTS  — Identify technical constraints (lang, platform, deps, perf)
3. STRUCTURE    — Design high-level architecture (modules, layers, interfaces)
4. DETAIL       — Specify interfaces, data models, error handling
5. DOCUMENT     — Write design doc with diagrams, schemas, ADRs
6. SELF-CHECK   — Verify requirements traceability, consistency, completeness
```

### Input Contract

```yaml
design_task_input:
  requirements: "string"
  constraints:
    language: "string | null"
    platform: "string | null"
    dependencies: ["string"]
    performance_targets: "string | null"
  research_findings: "string | null"
  existing_architecture: "string | null"
  design_scope: "full | incremental"
```

### Output Contract

```yaml
design_task_output:
  document_path: "string"
  summary: "string"                    # 3-5 sentence overview
  components_defined: "integer"
  interfaces_defined: "integer"
  diagrams_included: "integer"
  decisions_recorded: "integer"        # ADR count
  requirements_coverage_pct: "number"
  open_questions: ["string"]
```

### Quality Criteria

| Criterion | Requirement |
|-----------|-------------|
| Requirements traceability | 100% — every requirement maps to a design element |
| Interface specification | All interfaces have types, error cases, constraints |
| Diagrams | ≥ 1 architecture diagram (Mermaid) |
| Decision records | Documented with rationale + alternatives |
| Dependency direction | No circular dependencies |
| Internal consistency | No contradictory specifications |

### Tools/Skills

`Read`, `SemanticSearch`, `Write`, `WebSearch`

## 4. Implement Team
From §4.3:

**Role:** Write production-quality code, create configs, build infrastructure.
The ONLY team that modifies source code.

### Standard Workflow

```
1. ORIENT      — Read task spec, design reference, owned file list
2. LOAD_RULES  — Load applicable code-rules (core + language + task + quality)
3. SCAFFOLD    — Create file structure, module boilerplate, type definitions
4. IMPLEMENT   — Write code following loaded rules
5. UNIT_TEST   — Write unit tests for implemented code
6. VERIFY      — Run build and lint check
7. SELF-CHECK  — Review own code against MUST rules; fix violations
```

### Input Contract

```yaml
implement_task_input:
  specification: "string"
  owned_files:
    create: ["string"]
    modify: ["string"]
    read_only: ["string"]
  design_reference: "string"
  interface_contracts:
    - name: "string"
      signature: "string"
      constraints: "string"
  code_rules:
    loading_strategy: "minimal | standard | full"
    language: "string"
    task_type: "new_feature | bug_fix | refactoring"
    quality_focus: ["string"]
  predecessor_code: "string | null"
```

### Output Contract

```yaml
implement_task_output:
  files_created: ["string"]
  files_modified: ["string"]
  lines_added: "integer"
  lines_removed: "integer"
  tests_written: "integer"
  build_status: "pass | fail"
  lint_status: "clean | warnings | errors"
  self_review_findings:
    must_violations: "integer"         # should be 0
    should_deviations: "integer"
    deviation_justifications: ["string"]
```

### Quality Criteria

| Criterion | Requirement |
|-----------|-------------|
| MUST-rule violations | Zero |
| Build | Passes with zero errors |
| Lint | Clean (zero errors) |
| Unit tests | Written for all public interfaces |
| Interface contracts | All satisfied (signature + constraint) |
| SHOULD deviations | Justified in code comments |

### Tools/Skills

`Read`, `Write`, `StrReplace`, `Shell`, `Grep`, `Glob`, `SemanticSearch`,
`ReadLints`, code-rules loading protocol

## 5. Test Team
From §4.4:

**Role:** Execute test suites, measure quality metrics, validate correctness
and performance. Does NOT modify implementation (except test code).

### Standard Workflow

```
1. ORIENT       — Read task spec, identify test scope, review acceptance criteria
2. SETUP        — Verify test infrastructure, install deps, prepare test data
3. EXECUTE      — Run suites: unit → integration → E2E (increasing scope)
4. VERIFY       — Run user-facing checks: visual regression, acceptance verification, interaction flows, accessibility
5. MEASURE      — Collect metrics: coverage, performance, visual fidelity, interaction quality, accessibility compliance
6. GAP_ANALYSIS — Identify uncovered paths, missing edge cases, visual regressions, accessibility violations
7. WRITE_TESTS  — Write additional tests to close gaps (if part of task)
8. REPORT       — Produce structured test report including user-facing verification results
```

### Input Contract

```yaml
test_task_input:
  test_scope: "unit | integration | e2e | visual | acceptance | interaction | accessibility | full | benchmark | security"
  target_files: ["string"]
  test_files: ["string"]
  acceptance_criteria: ["string"]
  coverage_threshold: "number"
  performance_baselines:
    - metric: "string"
      threshold: "string"
  write_new_tests: "boolean"
  regression_baseline: "string | null"
  visual_baselines: "string | null"          # path to visual baseline screenshots
  acceptance_criteria_specs: ["string"]      # Gherkin/BDD specs for acceptance verification
  user_flow_definitions: ["string"]          # E2E user flow scenario definitions
  accessibility_standard: "WCAG2.1-AA | WCAG2.1-AAA | null"
```

### Output Contract

```yaml
test_task_output:
  report_path: "string"
  summary: "string"                    # 2-3 sentence summary
  suites_run: "integer"
  tests_total: "integer"
  tests_passed: "integer"
  tests_failed: "integer"
  tests_skipped: "integer"
  coverage_pct: "number"
  coverage_delta: "number | null"
  new_tests_written: "integer"
  performance_results:
    - metric: "string"
      value: "string"
      meets_threshold: "boolean"
  regressions_detected: ["string"]
  uncovered_paths: ["string"]
  acceptance_criteria_met:
    - criterion: "string"
      met: "boolean"
      evidence: "string"
  visual_fidelity_score: "number | null"
  visual_diffs: ["string"]                  # paths to diff images
  interaction_quality_score: "number | null"
  accessibility_score: "number | null"
  accessibility_violations:
    critical: "integer"
    serious: "integer"
    moderate: "integer"
    minor: "integer"
  acceptance_verification_score: "number | null"
  acceptance_criteria_results:
    - criterion: "string"
      status: "pass | fail | skip"
      evidence: "string"
```

### Quality Criteria

| Criterion | Requirement |
|-----------|-------------|
| Regressions | Zero (all existing tests pass) |
| Coverage | Meets or exceeds threshold |
| Acceptance criteria | All evaluated with evidence |
| Performance | Within specified thresholds |
| Gap analysis | Actionable (not just pass/fail) |
| Test conventions | New tests follow project conventions |

### Tools/Skills

`Shell`, `Read`, `Grep`, `Write`, `ReadLints`

## 6. Review Team
From §4.5:

**Role:** Evaluate artifacts against quality standards. NEVER modifies
artifacts — produces findings that other teams act on.

### Standard Workflow

```
1. ORIENT      — Read task spec, identify review scope, load checklist
2. LOAD_RULES  — Load code-rules for target language and quality dimensions
3. STRUCTURAL  — Review architecture: modules, dependencies, interfaces
4. BEHAVIORAL  — Review logic: correctness, error handling, edge cases, security
5. STYLISTIC   — Review conventions: naming, formatting, documentation, idioms
6. SCORE       — Calculate quality score using severity-weighted formula
7. REPORT      — Produce structured review report with classified findings
```

### Input Contract

```yaml
review_task_input:
  review_type: "code | design | security | architecture | documentation"
  target_files: ["string"]
  design_reference: "string | null"
  code_rules:
    loading_strategy: "standard | full"
    language: "string"
    quality_focus: ["string"]
  review_checklist: ["string"]
  prior_review: "string | null"
  severity_weights:
    blocker: 25
    critical: 15
    major: 5
    minor: 1
    info: 0
```

### Output Contract

```yaml
review_task_output:
  report_path: "string"
  summary: "string"                    # 2-3 sentence summary
  findings:
    - finding_id: "string"            # e.g., "F001"
      severity: "blocker | critical | major | minor | info"
      category: "correctness | security | performance | style
                | design_compliance | maintainability"
      location: "string"              # file:line or section
      description: "string"
      suggestion: "string | null"
      rule_id: "string | null"
  quality_score: "number (0-100)"
  findings_by_severity:
    blocker: "integer"
    critical: "integer"
    major: "integer"
    minor: "integer"
    info: "integer"
  verdict: "PASS | REVISE | REJECT"
  verdict_rationale: "string"
  checklist_coverage:
    items_checked: "integer"
    items_total: "integer"
```

### Quality Score Formula

```
quality_score = max(0, 100 - Σ(severity_weight × finding_count))

Severity weights: blocker=25, critical=15, major=5, minor=1, info=0
```

### Quality Criteria

| Criterion | Requirement |
|-----------|-------------|
| Checklist coverage | 100% items evaluated |
| Severity classification | Correctly classified (no inflation/deflation) |
| Score calculation | Uses agreed formula |
| Finding specificity | Each has specific location + actionable description |
| Verdict consistency | Consistent with score and threshold |
| Suggestions | Provided for critical and blocker findings |

### Simplicity Check

Every Review agent MUST evaluate against these scope-creep and over-engineering criteria:

| Check | FAIL if |
|-------|---------|
| Speculative features | Code adds capability not required by task objective |
| Unnecessary abstraction | Indirection/generalization without current use case |
| Line traceability | Any changed line cannot be traced to a task acceptance criterion |
| Premature optimization | Performance work without measured bottleneck evidence |
| Gold-plating | Polish beyond acceptance criteria (extra formatting, unused config) |

A finding of severity `major` is raised for each violation. This prevents scope creep at the source.

### Two-stage review pattern (v9.6.0 — superpowers integration)

The canonical L2 Wave dispatch pattern for Review-team work follows the
two-stage protocol formalized by `superpowers/skills/subagent-driven-development`
(https://github.com/obra/superpowers): **spec compliance** first, then
**code quality**.

| Stage | Verifier role | Acceptance | On FAIL |
|---|---|---|---|
| 1. Spec compliance | "Does the code do what the spec said it should?" — verify outputs against `acceptance_criteria` from TaskDispatch. | All criteria met. | Implementer fixes spec gaps; spec reviewer re-checks. |
| 2. Code quality | "Is the code well-engineered?" — apply Quality Criteria + Simplicity Check above. | `quality_score ≥ threshold`, 0 blockers, simplicity-check passes. | Implementer fixes quality issues; quality reviewer re-checks. |

**Why two stages instead of one:** spec compliance and code quality are
independent failure modes. A reviewer evaluating both at once tends to
collapse the two — typically prioritizing code quality (visible in the
diff) over spec compliance (requires reading the spec). The two-stage
split forces the reviewer to discharge each concern explicitly. Per the
superpowers `subagent-driven-development` skill: *"Fresh subagent per
task + two-stage review (spec then quality) = high quality, fast
iteration"*.

DevolaFlow's L2 Wave Agent dispatches the two reviewers as sequential
sub-tasks inside a `generator_verifier` wave coordination mode (per
SKILL.md §"Wave Coordination Modes"). The Implement Agent receives both
verdicts before the Wave terminates.

**Typed status protocol** (from superpowers, lifted into
`schemas/lean-report.yaml::StatusReport.verdict`):

* `DONE` — both stages PASS
* `DONE_WITH_CONCERNS` — both PASS but the quality reviewer flagged
  non-blocking findings the Implementer chose to ship (with rationale)
* `NEEDS_CONTEXT` — reviewer cannot decide without more info from L1/L2
* `BLOCKED` — Implementer cannot fix without L1 escalation

### Tools/Skills

`Read`, `Grep`, `SemanticSearch`, `ReadLints`, `Write`, code-rules protocol

## 7. Team Participation Matrix
From §4.6:

The matrix below covers all 22 builtin templates (verbatim from
`workflow-system/agent/templates/builtin/*.yaml`). Workflow-type names
match the template `.yaml` basename so a Wave/Task agent loading a
specific template can route directly to the correct team boundary.

**`(legacy)` = REGISTERED but v9.0.0..v10.3.0 cycle did NOT invoke; preserved for backward compat; Phase B compose-not-define collapse deferred to v12.0+** per `.local/research/v11.0.0_patches/D-A-2.md` §1 audit (v10.5.0 PV-02).

| Workflow Type | Research | Design | Implement | Test | Review |
|---------------|----------|--------|-----------|------|--------|
| research-only (legacy) | **Primary** | — | — | — | — |
| design-only (legacy) | — | **Primary** | — | — | Active |
| hotfix (legacy) | — | — | **Primary** | Active | Minimal |
| refactoring (legacy) | — | — | **Primary** | **Primary** | Optional |
| migration | Active | — | **Primary** | Active | Optional |
| spike-poc (legacy) | Active | — | Active | — | — |
| documentation-only (legacy) | Active | — | — | — | Active |
| security-audit (legacy) | Active | — | Active | Active | Active |
| research-design-review-refine (legacy) | **Primary** | **Primary** | — | — | **Primary** |
| full-pipeline (legacy) | Active | **Primary** | **Primary** | **Primary** | **Primary** |
| product-verification (legacy) | — | Active | — | **Primary** | Active |
| feature-enhancement (legacy) | Active | Active | **Primary** | Active | Active |
| demo-showcase (legacy) | — | Active | **Primary** | Active | Active |
| performance-optimization (legacy) | Active | — | **Primary** | **Primary** | Active |
| dependency-setup (legacy) | Active | — | **Primary** | Active | — |
| onboarding (legacy) | Active | — | **Primary** | — | — |
| skill-optimization | — | Active | **Primary** | Active | Active |
| nines-assisted | **Primary** | — | Active | Active | **Primary** |
| self-update | — | — | **Primary** | Active | Active |
| repo-init | Active | — | **Primary** | Active | — |
| entropy-cleanup (legacy) | Active | — | **Primary** | Active | Active |
| change-driven | Active | Active | **Primary** | Active | Active |

**Primary** = drives the stage. **Active** = participates. **Minimal** =
participates with reduced ceremony (e.g., hotfix Review). **Optional** =
participates only when a wave-specific gate flag enables it (e.g.,
`refactoring` review). **—** = not involved.

## 8. Handoff Protocol
From §5:

### Handoff Deliverable Schema

```yaml
handoff_deliverable:
  metadata:
    deliverable_id: "string (UUID)"
    source_team: "research | design | implement | test | review"
    target_team: "research | design | implement | test | review"
    stage_id: "string"
    timestamp: "ISO8601"
    version: "integer"                 # increments on revision

  content:
    artifact_paths: ["string"]
    summary: "string"                  # 3-5 sentence summary
    key_decisions: ["string"]
    constraints_imposed: ["string"]
    open_items: ["string"]

  quality:
    self_assessed_score: "number"
    review_verdict: "PASS | REVISE | null"
    known_limitations: ["string"]
```

### Standard Handoff Chains

```
Research ──research_report──► Design
Design  ──design_document──► Implement
Implement ──source_code──► Review
Implement ──source_code──► Test
Review  ──review_findings──► Implement
Test    ──test_results──► Implement
Test (verify) ──verification_results──► Review
Test (verify) ──visual_diffs──► Implement
```

### Handoff Contracts by Team Pair

| Source → Target | Deliverable | Required Sections | Acceptance |
|----------------|------------|-------------------|------------|
| Research → Design | Research report | findings, matrix, recommendation, gaps | All criteria addressed, confidence ≥ medium |
| Design → Implement | Design document | architecture, interfaces, models, ADRs | 100% requirements coverage, zero blocking questions |
| Implement → Review | Source + test code | all changed files | Build passes, lint clean, self-review MUST=0 |
| Implement → Test | Source + test code | files + acceptance criteria | Build passes, test scaffolding present |
| Review → Implement | Review findings | severity findings, score, verdict | All findings have severity, location, description |
| Test → Implement | Test results | pass/fail, coverage, gaps, regressions | All suites executed, coverage measured |

### Handoff Acceptance Check

```yaml
handoff_acceptance:
  checks:
    - completeness: "All required sections present (no TBD/TODO)"
    - parsability: "Well-formed, readable, no broken references"
    - scope_alignment: "Summary matches receiving team's task"
    - blocker_free: "No unresolved blocking items"
  on_pass: "Begin work"
  on_fail: "Reject with feedback → return to source team"
```

### Rejection-Remediation Cycle

1. Receiving team sends ExceptionEscalation (blocking, quality_threshold)
2. Stage Agent packages rejection with reasons + suggested fixes
3. Stage Agent reports FAIL with loop_back_target to source stage
4. Project Agent re-dispatches source stage with rejection as context
5. Source runs targeted remediation wave (not full re-execution)
6. Maximum 2 rejection-remediation cycles before human escalation
