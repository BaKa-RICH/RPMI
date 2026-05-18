# Codex Implementation Wave Guide for RPMI-CMV Python V0

## 0. How To Use This Guide

Use this document as the startup script for each new Codex window. Each wave
should feed Codex only the specs, current code state, previous gate result, and
acceptance criteria needed for that wave.

Do not ask Codex to implement multiple future waves at once. The project should
advance by phase gate:

```text
Wave 0 -> Wave 1 -> Wave 2 -> Wave 3A -> Wave 4 -> Wave 3B -> Wave 5A -> Wave 6A
```

Always restate the global V0 boundary at the start of each wave:

```text
V0 = deterministic Python mechanism validation.
No SUMO, no MOBIL, no RL, no action bundle, no hidden fallback.
Default decision_mode = single_t0_micro_episode.
```

## 1. Required Context Pack For Every New Window

For every new Codex task, provide:

```text
1. docs/specs/Implementation_README_v2.md
2. docs/specs/Phase_RPMI_V0_Code_Agent_Patch_Addendum_v2.md
3. The current wave's Phase_X_v2.md
4. docs/Codex_Implementation_Wave_Guide.md
5. docs/development_notes.md
6. Previous wave summary or gate report, if available
7. Current tests or failure logs, if any
8. Allowed write scope for this wave
9. Gate acceptance checklist for this wave
```

When the wave depends on earlier APIs, also include the relevant previous phase
specs and current implementation files.

## 2. Current Status

Wave 0 / Phase 0 v2 is complete.

Implemented:

```text
pyproject / package skeleton
uv + Python 3.12 environment
config dataclasses
global_conventions.json
config hash
run_id
seed management
state_hash helper placeholder
output directory creation
empty CSV log schemas
Phase 0 pytest
```

Verified commands:

```powershell
uv sync --extra dev
uv run pytest tests
```

Windows note: avoid `pytest tests/test_phase0_*.py` as a gate command in
PowerShell. It may be passed as a literal path. Use `uv run pytest tests` or
explicitly list the test files.

## 3. DevolaFlow Usage Policy

Use DevolaFlow for structure: detect task type, plan, implement, review, test,
refine, and report. For this repository, do not use background subtasks just to
create activity. Use them only when they reduce risk.

Preferred pattern:

```text
1. Main agent reads specs and defines shared interfaces first.
2. Main agent summarizes affected files before broad or risky edits.
3. Delegate only narrow, independently verifiable work.
4. Give each subtask explicit owned files, read-only files, acceptance criteria,
   and a short timeout.
5. Keep shared API design and final integration in the main workflow.
6. If a subtask stalls, close it, reconcile partial files, and continue.
7. Main workflow always runs final gate tests.
```

Good subtask candidates:

```text
review-only checks
documentation polish
independent tests for already-stable APIs
one isolated module with no shared-write conflict
```

Poor subtask candidates:

```text
initial shared API design
two tasks that must guess the same new names or return types
environment setup while the parent needs the same command resources
large cross-module edits with overlapping imports
```

## 4. Required Final Report From Codex

Every wave final answer must include:

```text
1. Files changed
2. Public APIs added or changed
3. Tests added
4. Commands used to verify
5. Gate pass/fail checklist
6. Known limitations
7. Forbidden scope check
8. Whether docs/development_notes.md was updated, and why
```

If Codex returns only code without a gate report, do not accept the wave.

## 5. Development Notes Policy

At the end of each wave, update `docs/development_notes.md` only when there is a
reusable lesson. Do not record every one-off typo or transient failed command.

Record items that are likely to affect later work:

```text
Windows shell behavior
uv/environment behavior
test command differences
spec interpretation decisions
DevolaFlow orchestration lessons
reproducibility or logging pitfalls
```

Do not record:

```text
ordinary syntax mistakes fixed immediately
temporary print/debug commands
one-off local timing hiccups with no workaround
```

## 6. Wave 0: Project Skeleton And Reproducibility

Status: complete.

### Feed Codex

```text
docs/specs/Implementation_README_v2.md
docs/specs/Phase_RPMI_V0_Code_Agent_Patch_Addendum_v2.md
docs/specs/Phase_0_Project_Skeleton_and_Reproducibility_v2.md
```

### Task Template

```text
Implement RPMI-CMV Python V0 Wave 0.

Only do Phase 0 v2:
- pyproject / package skeleton
- config dataclasses
- global_conventions.json
- config hash
- run_id
- seed management
- state_hash helper placeholder
- output directory creation
- empty CSV log schemas

Do not implement traffic dynamics, slot, edge, matching, or RCMV.

Add pytest:
- same config+seed reproducibility
- feature flag lock
- output schema exists
- ID convention helper tests

Return files changed, test commands, and gate checklist.
```

### Gate

Use the Windows-safe command:

```powershell
uv run pytest tests
```

Pass criteria:

```text
tests pass
empty run can be created
all CSV headers exist
feature flags block SUMO/MOBIL/RL/action_bundle
no traffic algorithms implemented
```

## 7. Wave 1: State, Dynamics, No-Fallback

### Feed Codex

```text
docs/specs/Implementation_README_v2.md
docs/specs/Phase_RPMI_V0_Code_Agent_Patch_Addendum_v2.md
docs/specs/Phase_0_Project_Skeleton_and_Reproducibility_v2.md
docs/specs/Phase_1_State_Dynamics_and_NoFallback_Simulator_v2.md
docs/development_notes.md
Wave 0 gate result
Current src/rpmi/config.py
Current src/rpmi/logging_schema.py
Current src/rpmi/run.py
Current tests/test_phase0_*.py
```

### Task Template

```text
Implement Wave 1: state, dynamics, and no-fallback simulator.

Must implement:
- VehicleState, RoadConfig, TrafficState
- occupied_interval
- lane sorting
- leader finding
- compute_gap_margin
- deterministic IDM / nominal CAV car-following
- combine nominal and action command
- effective acceleration speed-floor clipping
- step_traffic
- detect_overlap / negative_margin / hard_brake
- vehicles_step.csv and realized_events.csv writing hooks

Important:
no-fallback = nominal behavior + production command overlay + no post-hoc safety repair.
It does not mean no nominal following.

Do not add:
- hidden emergency controller
- SUMO
- MOBIL
- RL
- action bundle
- slots/edges/matching/RCMV

Add Phase 1 toy tests.
Return files changed, public APIs, tests, commands, gate checklist, and forbidden-scope check.
```

### Gate

Pass criteria:

```text
single-vehicle analytic test passes
speed floor uses a_eff for both x and v updates
overlap is recorded but not repaired
CAV without action still uses nominal following
hard braking / negative margin events are logged
Phase 0 tests still pass
```

Recommended command:

```powershell
uv run pytest tests
```

## 8. Wave 2: Time-Expanded Slots And Edges

### Feed Codex

```text
docs/specs/Implementation_README_v2.md
docs/specs/Phase_RPMI_V0_Code_Agent_Patch_Addendum_v2.md
docs/specs/Phase_1_State_Dynamics_and_NoFallback_Simulator_v2.md
docs/specs/Phase_2_TimeExpanded_Slot_and_Edge_Inventory_v2.md
Wave 1 gate result
Current dynamics/state/logging APIs
```

### Task Template

```text
Implement Wave 2: time-expanded slot and edge inventory.

Must implement:
- generate_time_grid
- target lane adjacent pair extraction
- Slot / Edge / IntervalResult / EdgeQuality
- action-context-aware slot_id and edge_id
- feasible interval
- separate V_phys_theory and V_phys_buffer
- reachability
- deterministic I_surv=1 with surv_mode
- safety screen
- V0 RD proxy
- P_R cascade
- reason codes
- inventory metrics interface with matching_hook

Do not:
- directly test S_H_R <= raw_gap_count
- implement action production
- implement RCMV
- implement matching beyond a hook/interface

Add Phase 2 toy tests.
```

### Gate

Pass criteria:

```text
raw gap but unreachable gives I_reach=0
W>=0 theory validity is separate from buffer validity
I_surv deterministic mode is correct
inventory sanity uses 0 <= S <= D style checks
Phase 0 and Phase 1 tests still pass
```

## 9. Wave 3A: Diagnostic Matching And Toy S0

### Feed Codex

```text
docs/specs/Implementation_README_v2.md
docs/specs/Phase_RPMI_V0_Code_Agent_Patch_Addendum_v2.md
docs/specs/Phase_2_TimeExpanded_Slot_and_Edge_Inventory_v2.md
docs/specs/Phase_3_Diagnostic_Matching_and_Mechanism_Experiment_S0_v2.md
Wave 2 gate result
Current slot/edge APIs
```

### Task Template

```text
Implement Wave 3A: diagnostic matching and toy S0.

Must implement:
- DemandRecord / MatchingEdge / MatchingResult
- demand weights with default omega=1
- edges_conflict with time_window_default
- greedy conflict solver as default
- optional Hungarian only under slot_only_debug
- compute S_H_R and Z_H_R from matching
- predictor/outcome table helpers
- minimal hand-crafted S0 micro samples

Do not:
- implement production action
- implement RCMV
- use Hungarian as the default conflict-aware solver

Add Phase 3 toy tests.
```

### Gate

Pass criteria:

```text
one ramp one edge works
two ramps one slot conflict is handled
time-window conflict is handled
same gap far apart mode works
no edge gives Z=D
raw-gap illusion row can be generated
previous tests still pass
```

## 10. Wave 4: Scenario Generators And Readiness

### Feed Codex

```text
docs/specs/Implementation_README_v2.md
docs/specs/Phase_RPMI_V0_Code_Agent_Patch_Addendum_v2.md
docs/specs/Phase_3_Diagnostic_Matching_and_Mechanism_Experiment_S0_v2.md
docs/specs/Phase_4_Scenario_Generators_and_Readiness_Tests_v2.md
Wave 3A gate result
Current matching APIs
```

### Task Template

```text
Implement Wave 4: formal scenario generators and readiness tests.

Must implement:
- ScenarioConfig / ReadinessReport
- S0/S2/S5/S6 controlled templates
- deterministic seed perturbation
- shared read-only near_miss classifier
- compute_readiness_metrics using no-action diagnostics
- readiness_check
- parameter_sweep_for_readiness
- scenario_manifest.json and readiness_summary.csv

Do not:
- use proposed selected action outcome for readiness
- run RCMV comparison
- generate production action

Add Phase 4 toy tests.
```

### Gate

Pass criteria:

```text
S0/S2/S5/S6 each have at least one seed readiness pass
readiness fail blocks comparison
readiness does not call proposed action rollout
sweep records failed attempts
previous tests still pass
```

## 11. Wave 3B: Formal S0 Batch Rerun

### Feed Codex

```text
docs/specs/Phase_3_Diagnostic_Matching_and_Mechanism_Experiment_S0_v2.md
docs/specs/Phase_4_Scenario_Generators_and_Readiness_Tests_v2.md
Wave 4 generator APIs
```

### Task Template

```text
Connect the Phase 3A S0 toy pipeline to the Phase 4 formal scenario generator.

Must implement:
- batch S0 sample generation
- fixed label_policy = FIFO_no_production
- predictor/outcome joined table
- correlation/rank/regression summary
- raw-gap illusion subset export

Do not implement predictor-specific label policy.
```

### Gate

Pass criteria:

```text
s0_predictor_outcome_joined.csv is generated
joined table includes raw high/Z high and raw high/Z low strata
label_policy field is fixed
previous tests still pass
```

## 12. Wave 5A: Boundary-Speed RCMV And Reservation Lifecycle

### Feed Codex

```text
docs/specs/Implementation_README_v2.md
docs/specs/Phase_RPMI_V0_Code_Agent_Patch_Addendum_v2.md
docs/specs/Phase_2_TimeExpanded_Slot_and_Edge_Inventory_v2.md
docs/specs/Phase_3_Diagnostic_Matching_and_Mechanism_Experiment_S0_v2.md
docs/specs/Phase_5_RCMV_Action_Selection_and_ActionConditioned_Reservation_v2.md
Wave 4 scenario/readiness APIs
```

### Task Template

```text
Implement Wave 5A: boundary-speed RCMV and action-conditioned reservation.

Must implement:
- NearMissEdge / Action / ActionEvaluation / Reservation
- find_near_miss_edges using shared classifier
- generate all single-action candidates
- no cross-candidate CAV de-duplication
- front_acc / rear_dec / front_rear profiles
- action-conditioned rollout
- regenerate slots/edges/matching per action
- compute J, Z_bar, D_bar, C_bar, RCMV
- select_action with theta
- create reservations
- reservation lifecycle and ramp guidance
- ablation_without_action_conditioned_reservation

Do not:
- implement lane-change unless Phase 5B is explicitly requested
- implement action bundle
- implement rolling horizon
- add hidden fallback

Add Phase 5 toy tests.
```

### Gate

Pass criteria:

```text
front_acc toy RCMV positive
high cost action rejected
alternative actions sharing the same CAV are generated
action-conditioned reservation differs from stale ablation
failed unsafe merge is recorded but not repaired
previous tests still pass
```

## 13. Wave 6A: Runner, Baselines, Analysis

### Feed Codex

```text
docs/specs/Implementation_README_v2.md
docs/specs/Phase_RPMI_V0_Code_Agent_Patch_Addendum_v2.md
docs/specs/Phase_4_Scenario_Generators_and_Readiness_Tests_v2.md
docs/specs/Phase_5_RCMV_Action_Selection_and_ActionConditioned_Reservation_v2.md
docs/specs/Phase_6_Baselines_Ablations_Experiment_Runner_and_Analysis_v2.md
All previous APIs
```

### Task Template

```text
Implement Wave 6A: single-decision experiment runner, baselines, ablations, and analysis.

Must implement:
- run_experiment
- run_single_t0_episode
- FIFO/no production baseline
- raw-gap reservation baseline
- density-triggered baseline
- speed-benefit baseline
- RPMI-CMV proposed
- ablation flags
- readiness_filter
- state_hash fairness check
- run_baseline_suite
- aggregate_metrics
- aggregate_failures
- collect_rcmv_trace
- summary tables

Default decision_mode = single_t0_micro_episode.
Do not enable rolling horizon by default.
Do not add SUMO/MOBIL/RL.
```

### Gate

Pass criteria:

```text
one scenario plus multiple baselines runs automatically
same scenario/seed state_hash is identical across fair comparisons
readiness fail run is marked readiness_failed
aggregate_metrics, failure_summary, and rcmv_trace can be generated
baselines do not use proposed information
previous tests still pass
```

## 14. Optional Wave 5B: Lane-Change Production

Only feed this after Wave 5A and Wave 6A pass.

### Task Template

```text
Implement optional Phase 5B lane-change production.

Must first design and implement:
- upstream CAV selection
- receiving gap check
- lane-change duration
- target lane insertion
- lane-change cost
- lane-change safety gates
- lane-change-specific logs and tests

Do not break Phase 5A boundary-speed tests.
```

### Gate

Pass criteria:

```text
lane-change does not break boundary-speed tests
invalid receiving gap does not generate lane-change action
lane-change cost and logs are traceable
```

## 15. Optional Wave 6B: Rolling Horizon

Only feed this after single-decision experiments are stable.

### Task Template

```text
Implement optional Phase 6B rolling horizon.

Must add:
- rolling decision_context_id
- reservation persistence
- stale reservation refresh
- cancellation rules
- overlapping action rule
- partial execution logging

Do not change the default single_t0_micro_episode behavior.
```

## 16. Optional Wave 7: Stochastic IDM V1

### Feed Codex

```text
docs/specs/Phase_7_Stochastic_IDM_V1_and_DoNotProceed_Rules_v2.md
passed deterministic gate summaries
edge/action/reservation logs
```

### Task Template

```text
Implement stochastic IDM V1.

Must implement:
- StochasticIDMConfig
- sample seed derivation
- bounded noise
- driver class sampling
- scenario-frequency estimator
- conditional probability denominator logging
- zero-noise equality test
- p_min/noise/N sensitivity tables

Do not use stochastic behavior to repair deterministic failures.
```

### Gate

Pass criteria:

```text
zero noise equals V0
same seed is reproducible
denominator=0 yields NaN plus denominator log
p_min increasing makes reservable count non-increasing or has documented explanation
```

## 17. How To Send Failure Feedback To Codex

Do not say only:

```text
The result is wrong. Fix it.
```

Provide:

```text
1. failed test name
2. exact assertion
3. relevant config
4. relevant log rows
5. expected behavior from Phase v2
6. files likely involved
```

Example:

```text
Toy 5.4 failed.
Two alternative actions share the same CAV, but only one action was generated.
This violates Phase 5 v2 Section 7 and Patch Addendum v2 Section 10.
Please remove cross-candidate CAV de-duplication. Keep only intra-action validation.
Relevant files: src/rpmi/actions.py, tests/test_phase5_actions.py.
```

## 18. End-Of-Wave Context Compression

Ask Codex to produce a wave summary:

```text
- Implemented APIs
- Tests passing
- Known limitations
- Log schemas touched
- Config keys added
- Next wave dependencies
- Whether development_notes.md was updated
```

The next wave should only need:

```text
README v2
Patch v2
current Phase v2
previous wave summary
development_notes.md
failing tests/logs if any
```

## 19. Final Acceptable V0 Completion Claim

After Wave 0 through Wave 6A pass, this project may claim:

```text
Deterministic Python V0 mechanism validation apparatus implemented.
```

It must not claim:

```text
Full RPMI-CMV reproduction implemented.
```

Only after optional Wave 5B, Wave 6B, and Wave 7 gates pass may the claim scope
be expanded item by item.

