---
id: "agent/references/shell-proxy"
version: "1.0.0"
purpose: >
  Defines the v8.4.0 RTK + memory-router stack: the `rtk` runtime plugin
  (`workflow-system/agent/knowledge/runtime-plugins.yaml`), the `shell_proxy/`
  package (`src/devolaflow/shell_proxy/{registry,proxy,commands}.py`), the
  `pre_shell_call` lifecycle hook (`src/devolaflow/lifecycle/pre_shell_call.py`),
  the `memory_router/` planning fast-path (`src/devolaflow/memory_router/`),
  and the RTK-pattern command-output mapping layer
  (`schemas/command-mapping.yaml` + `.local/memory/commands/`). All 4 surfaces
  are runtime-opt-in via `DEVOLAFLOW_RTK_PROXY=1` (commands, proxy) and
  `DEVOLAFLOW_MEMORY_ROUTER=1` (memory router); all are R5 strict default-off
  (zero IO, zero subprocess, zero behavior change when env-flags unset).
triggers:
  - "configuring rtk plugin install"
  - "enabling shell-proxy compression"
  - "authoring a memory-router case recipe"
  - "authoring a command-mapping recipe"
  - "debugging pre_shell_call hook violations"
  - "extending the WHITELIST tier table"
  - "diagnosing rtk vs rtk-type-kit collision"
tier: 2
token_estimate: 5800
dependencies:
  - "agent/SKILL.md"
  - "agent/references/agent-hierarchy.md"
  - "agent/references/execution-protocol.md"
  - "agent/references/decomposition-gate.md"
  - "agent/references/message-schemas.md"
last_updated: "2026-04-23"
---

# Shell-Proxy + Memory-Router Reference

The v8.4.0 cycle ships a 4-layer **RTK + memory-router stack** that
opportunistically compresses Shell-tool dispatch output and short-circuits
L0/L1 planning when prior cycles have already shaped the workflow:

1. **RTK plugin entry** (`v8.3.1` PV-01) — registers the [`rtk`](https://github.com/rtk-ai/rtk)
   binary as the third runtime plugin alongside `nines` + `ui-pro`.
2. **Shell-proxy + lifecycle hook** (`v8.3.2` PV-02) — adds the
   `src/devolaflow/shell_proxy/` package + the new `pre_shell_call` lifecycle
   event that wraps Shell-tool calls in `rtk rewrite` for whitelisted commands.
3. **Memory-router fast-path** (`v8.3.3` PV-03) — adds
   `src/devolaflow/memory_router/` consulted at L0/L1 dispatch time BEFORE
   re-deriving from SKILL.md; cache-hit short-circuits ~3K tokens of planning
   context per matched route.
4. **RTK-pattern command mapping** (`v8.3.4` PV-04) — adds
   `src/devolaflow/shell_proxy/commands.py` + the
   `.local/memory/commands/<repo>/<cmd>.yaml` recipe layer that extends RTK's
   built-in 100+ rewrites with repo-specific compression filters.

All 4 surfaces are **runtime-opt-in** and **R5 strict default-off** (zero IO,
zero subprocess, zero behavior change when the env-flags are unset). Existing
3110 v8.3.0 baseline tests pass byte-identical when nothing is enabled — the
stack can NEVER break dispatch, only optionally accelerate or compress it.

---

## 1. When to Load This Reference

Load when the task involves any of:

| Trigger | What you'll be doing |
|---------|----------------------|
| Adding a new entry to `runtime-plugins.yaml` | Need the v2 schema layout + `curl_install_script` backend contract |
| Extending the `shell_proxy/registry.py` WHITELIST | Need Tier 1 / Tier 2 tier semantics + anchored-regex invariant |
| Authoring a `pre_shell_call` hook caller | Need the `{cmd, cwd?}` payload contract + PSC001..PSC004 codes |
| Authoring a memory-router case recipe | Need `schemas/memory-case.yaml` + multi-level routing keys |
| Authoring a command-mapping recipe | Need `schemas/command-mapping.yaml` + RTK `[filters.<name>]` reuse |
| Debugging the rtk-vs-rtk-type-kit collision | Need the `verify_distinguish_cmd: rtk gain` mandatory probe |
| Diagnosing why R5 strict tests changed | Need the env-flag activation contract per PV |

If the task is a generic feature/bugfix that does NOT touch
`runtime-plugins.yaml`, `shell_proxy/`, `memory_router/`, the
`pre_shell_call` hook, or `.local/memory/{cases,commands}/`, this reference
is OPTIONAL — load only when the dispatch chain explicitly opts into the
RTK + memory-router surface area.

---

## 2. Activation Surface (env flags)

| Flag | Source PV | Default | Activates |
|------|-----------|---------|-----------|
| `DEVOLAFLOW_AUTO_INSTALL` | v8.3.0 PV-01 (carried fwd) | `0` | Pre-existing — set to `1` to allow `installer.py::ensure_plugin('rtk')` to attempt curl/cargo install. |
| `DEVOLAFLOW_RTK_PROXY` | v8.3.2 PV-02 | unset | When `"1"`: `pre_shell_call` rewrites whitelisted commands via `rtk rewrite`; PV-04 command-mapping layer also activates (REUSES this flag — no new env var). |
| `DEVOLAFLOW_RTK_PROXY_TIER2` | v8.3.2 PV-02 | unset | Secondary opt-in. Adds the Tier 2 commands (`git add`, `git commit`, `git show`, `cargo test`, `npm test`, `make`) to the proxy whitelist. Has no effect unless `DEVOLAFLOW_RTK_PROXY=1`. |
| `DEVOLAFLOW_MEMORY_ROUTER` | v8.3.3 PV-03 | unset | When `"1"`: `lookup_case()` consults `.local/memory/cases/index.yaml` BEFORE the L0/L1 dispatcher re-derives from SKILL.md. Cache-miss falls through to the existing planner. |

**Strict equality** — only the literal string `"1"` enables. `"01"`, `"true"`,
`"yes"`, etc. all leave the flag DISABLED. This defends against typos that
would otherwise silently activate the surface.

---

## 3. Layer 1 — RTK Plugin Entry (v8.3.1 PV-01, closes R-001)

### 3.1 Registry row

`workflow-system/agent/knowledge/runtime-plugins.yaml` carries the canonical
plugin definitions. v8.3.1 grew the registry from 2 plugins (`nines` + `ui-pro`)
to 3 by appending RTK and bumped `schema_version` 1 → 2 to introduce the new
optional `verify_distinguish_cmd` field + the `curl_install_script` backend.

```yaml
schema_version: 2

plugins:
  - name: rtk
    backend: curl_install_script
    canonical_url: "https://github.com/rtk-ai/rtk"
    install_cmd: "curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/main/install.sh | sh"
    version_check_cmd: "rtk --version"
    verify_distinguish_cmd: "rtk gain"   # NEW field; mandatory for RTK
    min_version: "0.37.2"
    expected_sha256: null
    local_fallback_path: null
    invoked_by_workflows: [shell-proxy]
```

### 3.2 Backward compatibility (R5 strict)

The `nines` and `ui-pro` entries are byte-identical pre/post v8.3.1. Their
`verify_distinguish_cmd` is unset (`None` after parse) so `_verify_distinguish()`
is a no-op for them. `_SUPPORTED_SCHEMA_VERSIONS = frozenset({1, 2})` accepts
both v1 and v2 fixtures so existing test fixtures continue to load without
modification.

### 3.3 The `curl_install_script` backend

`src/devolaflow/plugins/installer.py` gained `_install_via_curl_script(spec, *, timeout)`
implementing the new backend. The flow:

1. `subprocess.run(install_cmd, shell=True, ...)` runs the canonical RTK install
   script (ships `rtk` binary into `~/.local/bin/`).
2. `subprocess.run(version_check_cmd, ...)` probes `rtk --version`.
3. If `verify_distinguish_cmd` is set, runs `rtk gain` — for RTK this is **MANDATORY**
   per the upstream `INSTALL.md` collision warning vs the unrelated `rtk-type-kit`
   project (`reachingforthejack/rtk` on crates.io).
4. On primary failure (curl unavailable, network down, distinguish fails), falls
   back to `cargo install --git https://github.com/rtk-ai/rtk` — **NEVER** bare
   `cargo install rtk` (would risk pulling rtk-type-kit per R-2 collision risk).
5. Both backends fail → `PluginInstallError` per S-5 with actionable text
   aggregating both failure reasons + INSTALL.md collision-warning text.

### 3.4 Distinguish-from-collision discipline

`rtk gain` is the canonical Rust Token Killer "Get Tokens" subcommand. The
unrelated `rtk-type-kit` does NOT implement `gain`; if `rtk gain` returns
non-zero, the wrong package is installed. The check runs at BOTH preinstall
(skip-install branch when `rtk` is already on PATH) AND post-install
(verify the curl/cargo result). Failure raises `PluginInstallError` per S-5.

---

## 4. Layer 2 — Shell-Proxy + `pre_shell_call` Hook (v8.3.2 PV-02, closes R-002)

### 4.1 Module layout

```
src/devolaflow/shell_proxy/
├── __init__.py     # 49 lines — re-exports public API
├── proxy.py        # 320 lines — ShellProxy + ShellProxyConfig + proxy_command
├── registry.py     # 126 lines — single-source-of-truth WHITELIST + match_command
└── commands.py     # 612 lines (added in PV-04, see §6)

src/devolaflow/lifecycle/
└── pre_shell_call.py   # 148 lines — thin-delegator hook (5th lifecycle event)
```

The split mirrors RTK's own `src/discover/{registry,rules}.rs` pattern per
`.local/research/v8.4.0_rtk_nines_analysis.md` §4.1: `registry.py` owns the
whitelist + the rewrite metadata; `proxy.py` owns the runtime orchestration
(activation snapshot + per-call dispatch).

### 4.2 WHITELIST contract (registry.py single-source-of-truth)

```python
# Tier 1 — default-on under DEVOLAFLOW_RTK_PROXY=1
WHITELIST: dict[str, Tier] = {
    "pytest":     1,   # SI-10 step 1 + step 5
    "ruff check": 1,   # SI-10 step 2
    "git diff":   1,   # used by every PV
    "git log":    1,   # used by every PV
    "git status": 1,   # used by every PV
    # Tier 2 — opt-in via DEVOLAFLOW_RTK_PROXY_TIER2=1
    "git add":    2,
    "git commit": 2,
    "git show":   2,
    "cargo test": 2,
    "npm test":   2,
    "make":       2,
}
```

**Invariants:**

- The `WHITELIST` dict is the ONLY place that knows which commands to rewrite.
  The proxy reads from it; the hook reads from it via the proxy; tests read
  from it directly. Adding an entry is a 1-line change in this file.
- Pattern matching uses an **anchored** regex `^{prefix}($|\s)` so
  `pytest-style-runner` does NOT match `pytest`. Verified by
  `tests/test_shell_proxy.py::test_anchored_regex_rejects_hyphen_continuation`.
- Patterns are precompiled at import time into `_COMPILED_PATTERNS` (hot-path
  discipline — no per-call compile). If a maintainer adds a new entry without
  reimporting the module, the in-process cache will not pick it up; this
  invariant is documented in the `WHITELIST` docstring.

### 4.3 Activation snapshot (proxy.py)

`ShellProxyConfig` is captured **once** per `ShellProxy` instantiation:

```python
@dataclass(frozen=True, slots=True)
class ShellProxyConfig:
    enabled: bool          # DEVOLAFLOW_RTK_PROXY == "1"
    tier2_enabled: bool    # DEVOLAFLOW_RTK_PROXY_TIER2 == "1"
    rtk_on_path: bool      # shutil.which("rtk") is not None (only probed when enabled)
    distinguish_ok: bool   # `rtk gain` returncode == 0 (only probed when on PATH)
```

When `enabled=False` the snapshot is the trivial defaults path (no
`shutil.which`, no subprocess) per R5 strict zero-overhead. When all 4 fields
are `True`, the proxy is active and will rewrite whitelisted commands.

### 4.4 The 5th lifecycle event

`src/devolaflow/lifecycle/__init__.py::DEFAULT_EVENTS` grows from 4 → 5:

| Event | Purpose | Strict-mode raises |
|-------|---------|--------------------|
| `pre_dispatch` | Validate dispatch payload before send | `HookViolation` |
| `file_write` | Enforce file ownership per S-8 | `HookViolation` (PV-08 surface) |
| `task_stop` | Run `consolidate_session()` learnings | `HookViolation` |
| `format_on_edit` | Auto-format edited files | `HookViolation` |
| **`pre_shell_call`** (NEW) | Wrap Shell-tool calls via `ShellProxy` | `HookViolation` (PSC001..PSC004) |

Hook payload contract: `{cmd: str, cwd?: str}`. The hook validates the
payload, calls `ShellProxy().wrap_command(cmd)`, and stuffs three diagnostics
into `HookResult.metadata`:

| Key | Type | Meaning |
|-----|------|---------|
| `wrapped_cmd` | `str` | The (possibly rewritten) command |
| `proxy_enabled` | `bool` | Whether the env-flag was set + rtk was on PATH + distinguish passed |
| `was_rewritten` | `bool` | Strict equality: `wrapped_cmd != original_cmd` |

### 4.5 Schema violation codes

| Code | Cause |
|------|-------|
| `PSC001` | Payload is not a dict |
| `PSC002` | Payload missing `cmd` key |
| `PSC003` | `cmd` value is not a string |
| `PSC004` | `cwd` value present but not a string |

In permissive mode (default) these log a WARNING and the hook returns
`HookResult(severity="warning")`. In strict mode (`run_hooks(..., strict=True)`)
they raise `HookViolation` per the lifecycle dispatcher contract.

### 4.6 Graceful degradation

When `DEVOLAFLOW_RTK_PROXY=1` is set but `rtk` is missing OR `rtk gain`
returns non-zero, the proxy logs a WARNING via the lifecycle logger with
actionable text (collision-warning text from RTK INSTALL.md when distinguish
fails) AND gracefully passthroughs — it does NOT raise. This matches RTK's
own Claude Code hook behavior in `hooks/claude/rtk-rewrite.sh` lines 21-24.

---

## 5. Layer 3 — Fast-Path Memory Router (v8.3.3 PV-03, closes M-001)

### 5.1 Module layout

```
src/devolaflow/memory_router/
├── __init__.py     #  72 lines — public surface re-export
├── cache.py        # 329 lines — MemoryCase + invalidation predicates
└── router.py       # 471 lines — MemoryRouter + lookup_case + lookup_case_strict

schemas/memory-case.yaml   # 259 lines — canonical source-of-truth schema
.local/memory/cases/       # operator-local seeds (gitignored under .local/*)
├── README.md
├── index.yaml
└── <case-id>.md           # one markdown per recipe
```

### 5.2 The activation contract

```python
from devolaflow.memory_router import lookup_case

case = lookup_case(
    workflow_type="full-pipeline",
    task_type="implement",
    repo_signal=None,                # optional namespace narrowing
)
if case is not None:
    # Hit — short-circuit the planning re-derivation. Operators load the
    # verbatim recipe body from case.recipe_path; the summary + version
    # stamp are the L0 audit trail for which recipe routed which dispatch.
    summary = case.summary
    recipe_path = case.recipe_path
    version_stamp = case.version_stamp
else:
    # Miss — fall through to existing planner (R5 strict safe path)
    dispatch_template = derive_from_skill_md(...)
```

`lookup_case()` is the safe variant: NEVER raises, always degrades to `None`
on schema break / IO error / missing file. CI verification scripts and
operator inspection paths use `lookup_case_strict()` which raises
`MemoryRouterError` — but the L0/L1 dispatcher hot path uses the safe
variant so a corrupt index can NEVER block production work.

### 5.3 `MemoryCase` value type (cache.py)

```python
@dataclass(frozen=True)
class MemoryCase:
    case_id: str
    workflow_type: str
    task_type: str
    summary: str             # one-sentence verbatim summary, <= 160 chars
    recipe_path: str         # MUST start with .local/memory/cases/
    version_stamp: str       # MUST equal devolaflow.__version__
    ttl_days: int = DEFAULT_TTL_DAYS
    last_accessed: str = ""  # ISO-8601 yyyy-mm-dd
    last_updated: str = ""   # ISO-8601 yyyy-mm-dd
    repo_signal: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
```

### 5.4 Invalidation predicates (per cycle plan §6 R3)

Two predicates run for every match BEFORE returning a hit:

1. `is_version_stale(case, current_version)` — exact string equality with
   `devolaflow.__version__`. Pre-release tags like `8.3.4-rc.1` DO trigger
   invalidation (the safe behavior — recipes invalidate automatically when
   `__version__` bumps).
2. `is_ttl_expired(case, today=...)` — anchor priority is `last_accessed`
   first, then `last_updated`; both empty → fresh-but-undated (returns False
   to avoid spurious expiry).

Both predicates degrade to **cache-miss** if they detect drift; the caller
falls through to the existing planner unchanged.

### 5.5 Lazy load + cache reuse

`MemoryRouter()` construction is a no-op (no IO). The index loads on the
first `lookup_case()` call into an immutable `_IndexLoadResult` snapshot.
Subsequent calls reuse the snapshot without re-reading the file. Tests can
inject `cases=[...]` to skip IO entirely (e.g. for hot-path performance
benchmarks).

### 5.6 Index file format

```yaml
# .local/memory/cases/index.yaml
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: "rtk-plugin-entry"
    workflow_type: "feature-enhancement"
    task_type: "implement"
    summary: "RTK runtime auto-install via curl_install_script with cargo fallback."
    recipe_path: ".local/memory/cases/rtk-plugin-entry.md"
    version_stamp: "8.3.3"
    ttl_days: 30
    last_updated: "2026-04-23"
    tags: ["rtk", "plugin", "v8.4.0-cycle"]
```

The recipe markdown carries free-form playbook content (Trigger / Dispatch
shape / Predecessor refs / Owned files / Gate hints / Notes). The schema
permits any markdown body; only the index.yaml row is validated. Required
fields per `schemas/memory-case.yaml` `item_required_fields`: `case_id`,
`workflow_type`, `task_type`, `summary`, `recipe_path`, `version_stamp`.

### 5.7 Operator-local seed kit

The `.local/memory/cases/` tree is **gitignored** under `.local/*` per the
v8.3.0 PV-04 Q-5 policy. The 3 seeded recipes that ship with v8.4.0 are
extracted from the cycle's own PVs (`rtk-plugin-entry.md`,
`shell-proxy-registry.md`, `evobench-doc-coupling.md`) but are not part of
the committed source — operators populate their own library lazily via
`consolidate_session()` learnings substrate.

---

## 6. Layer 4 — RTK-Pattern Command Mapping (v8.3.4 PV-04, closes M-002)

### 6.1 Module + schema layout

```
src/devolaflow/shell_proxy/
└── commands.py     # 612 lines — CommandMapping + apply_local_recipe + load_command_mappings

schemas/command-mapping.yaml   # 282 lines — canonical schema mirrors RTK [filters.<name>]
.local/memory/commands/        # operator-local seeds (gitignored)
├── README.md
└── <repo>/<cmd>.yaml          # one YAML per command (basename glob)
```

### 6.2 Precedence chain (verbatim user ask)

```
local recipe (.local/memory/commands/<repo>/<cmd>.yaml)
    └── falls back to ──> RTK rewrite (rtk rewrite <cmd>)
                                  └── falls back to ──> passthrough
```

The local recipe layer extends RTK's built-in 100+ command rewrites with
**repo-specific compression filters** (DeprecationWarning blocks specific to
the v8.3.3 PV-03 test output, `[*] N fixable` ruff lines, version-bump
pattern diffs, etc.).

### 6.3 Recipe YAML format (mirrors RTK `[filters.<name>]`)

```yaml
# .local/memory/commands/devolaflow/pytest.yaml
schema_version: 1
command: "pytest"
version_stamp: "8.4.0"          # MUST equal devolaflow.__version__
description: "DevolaFlow-specific pytest output compression"
repo_signal: "devolaflow"
last_updated: "2026-04-23"
ttl_days: 30
strip_ansi: true
pre_filters:
  - pattern: "^DeprecationWarning:.*$"
    replacement: ""    # drop matched lines outright (verbatim re.sub semantics)
post_filters:
  - pattern: "^.*\\[\\*\\] [0-9]+ fixable.*$"
    replacement: ""    # drop ruff "[*] N fixable" hints from final output
truncate_lines: 200
max_lines: 200                  # alias for truncate_lines (precedence: explicit truncate_lines wins)
on_empty: "(no relevant output)"
tags: ["pytest", "devolaflow"]
```

### 6.4 Activation reuses PV-02 surface (NO new env-flag)

`is_command_mapping_active(env)` is a thin wrapper over `is_proxy_enabled(env)`
with identical semantics — same dict lookup, same accepted value (`"1"`),
same R5 zero-overhead when unset. Operators only have to remember ONE flag
(`DEVOLAFLOW_RTK_PROXY=1`), not three.

### 6.5 Loud failures (S-5)

Every error path emits a `WARNING` via the `devolaflow.shell_proxy.commands`
logger and gracefully degrades to dropping the malformed recipe. The
remaining recipes are still loaded.

| Failure mode | Action |
|--------------|--------|
| Malformed YAML | WARNING → recipe skipped; loader continues |
| Empty file | WARNING → recipe skipped |
| Non-mapping top-level | WARNING → recipe skipped |
| Missing required field | WARNING → recipe skipped |
| Type error (str vs int, bool vs int) | WARNING → recipe skipped |
| Invalid regex pattern | WARNING → recipe skipped |
| Malformed date string | `CommandMappingError` raised by `build_mapping_from_dict` |
| TTL expired | INFO → recipe skipped (normal lifecycle) |
| Version stamp mismatch | INFO → recipe skipped (normal lifecycle) |

`CommandMappingError` is raised ONLY by `build_mapping_from_dict` — this
gives operator-driven inspection paths an explicit raise; the dispatch hot
path catches it inside `load_command_mappings` and degrades to recipe-skip.

### 6.6 Command-head anchor (longest-prefix-wins)

`_match_recipe(cmd, mappings)` iterates the loaded mappings in
**length-descending** order so `git commit --amend` matches `git commit`
before falling through to `git`. Anchored at start-of-line so trailing
arguments like `pytest tests/test_benchmarks.py -v` correctly match the
`pytest` recipe.

### 6.7 Integration with `ShellProxy.apply_recipe_to_output`

```python
proxy = ShellProxy()
wrapped_cmd = proxy.wrap_command("pytest tests/ -q")  # PV-02 surface
# ... operator runs wrapped_cmd, captures `output` ...
filtered_output, was_filtered = proxy.apply_recipe_to_output(
    cmd="pytest tests/ -q",
    output=output,
    repo_signal="devolaflow",
)
```

`wrap_command(cmd)` is **byte-identical** pre/post v8.3.4 (R5 strict — verified
by `tests/test_shell_proxy_commands.py::TestShellProxyIntegration::test_wrap_command_byte_identical_post_pv04`).
The new `apply_recipe_to_output(cmd, output)` method is purely additive; callers
that don't invoke it see no behavior change.

---

## 7. Token Budgets & Performance

### 7.1 Steady-state cost when env-flags off (R5 strict)

| Surface | Cost when disabled |
|---------|--------------------|
| `installer.py::ensure_plugin('rtk')` | Not called unless workflow precondition declares `rtk` |
| `is_proxy_enabled(env)` | Single dict lookup (`os.environ.get(...) == "1"`) — sub-microsecond |
| `is_router_enabled(env)` | Single dict lookup — sub-microsecond |
| `is_command_mapping_active(env)` | Single dict lookup (REUSES PV-02 surface) — sub-microsecond |
| `pre_shell_call` hook | Function call + payload-validation pass (matches the 4 existing default hooks) |
| `lookup_case()` flat-call | Short-circuit to `None` BEFORE constructing a `MemoryRouter` |
| `apply_local_recipe()` flat-call | Short-circuit to `(output, False)` BEFORE constructing any `CommandMapping` |

### 7.2 Cost when env-flags on

| Surface | First call | Subsequent calls |
|---------|-----------|------------------|
| `MemoryRouter.__init__` | No IO (lazy) | No IO |
| `MemoryRouter.lookup_case` | YAML parse + validate (~5-50 cases) | Dict iteration over frozen snapshot |
| `ShellProxy.__init__` | No IO (lazy snapshot) | No IO |
| `ShellProxy.wrap_command` | `shutil.which("rtk")` + `subprocess.run("rtk gain", timeout=5)` then dict + regex | Dict + regex (snapshot reused) |
| `load_command_mappings` | `Path.rglob("*.yaml")` + parse 5-15 recipes | (caller passes pre-loaded mappings) |
| `apply_local_recipe` | Dict + sorted-prefix iter + `re.sub` | Same |

### 7.3 Token savings (structural)

- **Memory-router hit** — replaces a full SKILL.md re-derivation
  (~498 lines + workflow selection table ≈ 3200 tokens) with a single
  dict probe (~200 tokens) ≈ **93% reduction** of the planning-context block.
  Well above the gap analysis §2.1 M-001 ≥30% target.
- **Shell-proxy rewrite (RTK)** — RTK reports **80-90% token reduction**
  on `pytest` / `ruff` / `git diff` / `git log` per the upstream README's
  savings table.
- **Command-mapping incremental** — local recipes layered on top of RTK
  rewrites add ~10pp incremental savings on the 3 seeded DevolaFlow recipes
  (DeprecationWarning suppression, fixable-hint suppression, version-bump
  pattern compression).

---

## 8. Verification Surface

### 8.1 Unit tests (per PV)

| Test file | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_plugins.py` | +14 in v8.3.1 | RTK detect / install / distinguish / uninstall + 5 schema-v2 + helper guards |
| `tests/test_shell_proxy.py` | +22 in v8.3.2 | All 5 Tier 1 + 6 Tier 2 entries + `_resolve_config` decision tree + `_probe_distinguish` 3 failure modes |
| `tests/test_shell_proxy_disabled_is_noop.py` | +4 in v8.3.2 | R5 strict baseline (dedicated file with intentionally-verbose name) |
| `tests/test_lifecycle_pre_shell_call.py` | +6 in v8.3.2 | PSC001..PSC004 schema violations in permissive + strict modes |
| `tests/test_memory_router.py` | +40 in v8.3.3 | R5 zero-IO contract via `monkeypatch.setattr(Path, "read_text", watcher)` |
| `tests/test_shell_proxy_commands.py` | +36 in v8.3.4 | R5 zero-IO contract + 11 schema-validation breaks (loop-asserts) |

**Cycle-wide test count:** 3110 (v8.3.0) → 3215 (v8.3.4) = +105 net new
tests across 4 PVs (slight +5 over the +100 cycle cap, documented in
`.local/research/v8.4.0_evaluation.md`).

### 8.2 EvoBench scenarios

| Scenario | PV | Composite | Floor | Asserts |
|----------|----|----------:|------:|---------|
| `shell_proxy_disabled.yaml` | v8.3.2 PV-02 | 91.21 | 90 | R5 strict zero-overhead in dispatch path |
| `memory_router_fastpath.yaml` | v8.3.3 PV-03 | 99.73 | 90 | Router lifecycle integration adds zero overhead |
| `command_mapping_density.yaml` | v8.3.4 PV-04 | 99.73 | 90 | Recipe layer lifecycle integration adds zero overhead |

EvoBench grew 45 → 48 baseline scenarios across the cycle; **0 regressions
> 5pp** vs `v8.3.0_baseline.json` per W-4 / SI-4. The v8.4.0 rollup
regenerates `v8.4.0_baseline.json` for the post-cycle baseline.

### 8.3 R5 strict triple codification

The R5 strict default-off contract is codified at THREE layers per PV:

1. **Unit test** — dedicated `*_disabled_is_noop.py` or `TestR5StrictOff`
   class with `monkeypatch.setattr(Path, "read_text", watcher)` watcher
   asserting no `Path.read_text()` call is reached when the env-flag is off.
2. **Integration test** — full `pytest tests/` PASS with all baseline tests
   byte-identical when env-flag off.
3. **EvoBench scenario** — `*_disabled.yaml` or `*_fastpath.yaml` proves
   dispatch-surface composite is byte-identical (within scenario tolerance).

---

## 9. Operator Cookbook

### 9.1 Enabling the full v8.4.0 stack

```bash
# Install RTK runtime plugin (one-time; respects DEVOLAFLOW_AUTO_INSTALL=0 opt-out)
export DEVOLAFLOW_AUTO_INSTALL=1
python -c "from devolaflow.plugins import ensure_plugin; ensure_plugin('rtk')"

# Activate shell-proxy (Tier 1 commands: pytest, ruff check, git {diff,log,status})
export DEVOLAFLOW_RTK_PROXY=1

# Optional: opt into Tier 2 (git add/commit/show, cargo test, npm test, make)
export DEVOLAFLOW_RTK_PROXY_TIER2=1

# Activate planning-time fast-path memory router
export DEVOLAFLOW_MEMORY_ROUTER=1

# Optional: seed the local memory tree (gitignored)
mkdir -p .local/memory/{cases,commands/devolaflow}
# ... author index.yaml + <case-id>.md + <cmd>.yaml files ...
```

### 9.2 Adding a new whitelist entry

1. Edit `src/devolaflow/shell_proxy/registry.py::WHITELIST` — add a single
   `"<command>": <tier>,` row.
2. Restart the process (the `_COMPILED_PATTERNS` cache is import-time).
3. Add a unit test in `tests/test_shell_proxy.py` covering the new entry
   (mirror the existing parametrize/loop-asserts pattern).

### 9.3 Adding a memory-router case

1. Append a row to `.local/memory/cases/index.yaml` with a unique `case_id`,
   the matching `workflow_type` + `task_type`, and a `version_stamp` equal
   to the current `__version__`.
2. Author the recipe markdown at `.local/memory/cases/<case_id>.md` (free-form
   playbook content; the body is unvalidated).
3. The router will pick it up on the next `lookup_case()` call (or after
   the in-process cache is invalidated by a `__version__` bump).

### 9.4 Adding a command-mapping recipe

1. Author `<cmd>.yaml` at `.local/memory/commands/<repo>/<cmd>.yaml` with
   the canonical schema fields (see §6.3).
2. Set `version_stamp: "<current __version__>"` to opt into automatic
   invalidation on the next version bump.
3. Recipes are discovered via `Path.rglob("*.yaml")` so any nesting under
   `.local/memory/commands/` works.

### 9.5 Diagnosing R5 violations

If a test fails byte-equality after enabling any env flag, the most likely
causes are:

| Symptom | Likely cause |
|---------|--------------|
| `tests/test_shell_proxy_disabled_is_noop.py` fails | Someone added an unconditional code path in `proxy.py` that runs even when `enabled=False` |
| `tests/test_memory_router.py::TestLookupCaseR5StrictOff` fails | `lookup_case()` no longer short-circuits before constructing the router or reading the index |
| `tests/test_shell_proxy_commands.py::TestLoadR5StrictOff::test_env_off_does_not_touch_path_read_text` fails | `load_command_mappings()` no longer short-circuits before `Path.read_text()` |
| EvoBench `shell_proxy_disabled.yaml` composite drops > 5pp | Lifecycle hook now adds non-trivial cost in the dispatch path |

In all cases the fix is to reinstate the early-return at the top of the
function before any IO / subprocess / parse work. The R5 strict contract
is codified BOTH at the unit-test layer AND at the EvoBench layer — fixing
the unit test alone is insufficient.

---

## 10. Cross-References

- **SI-1 gap analysis:** `.local/research/v8.4.0_gap_analysis.md` (R-001 / R-002 / M-001 / M-002 in §2.1; D-001 split decision in §3; cycle invariants in §5)
- **SI-2 NineS analysis on RTK:** `.local/research/v8.4.0_rtk_nines_analysis.md` (§4.1 single-source-of-truth pattern; §4.3 RTK `[filters.<name>]` schema; §6.1 Tier 1/Tier 2 whitelist; §6.2 hook delegator; §5.2 collision-warning enforcement)
- **Per-PV evaluations (W-3 / SI-3):**
  - `.local/research/v8.3.1_evaluation.md` (PV-01 RTK plugin) — composite 9.10/10
  - `.local/research/v8.3.2_evaluation.md` (PV-02 shell-proxy) — composite 9.10/10
  - `.local/research/v8.3.3_evaluation.md` (PV-03 memory router) — composite 9.10/10
  - `.local/research/v8.3.4_evaluation.md` (PV-04 command mapping) — composite 9.10/10
- **Per-PV NineS:** `.local/research/v8.3.{1,2,3,4}_nines.{json,md}` (composite 0.9050 byte-stable across all 4 PVs)
- **Rollup evaluation:** `.local/research/v8.4.0_evaluation.md` (cycle composite ≥ 8.5)
- **Rollup NineS:** `.local/research/v8.4.0_nines.{json,md}`
- **EvoBench summary:** `.local/research/v8.4.0_evobench_summary.md` (per-scenario delta vs v8.3.0_baseline.json)
- **Source:**
  - `src/devolaflow/plugins/installer.py` (PV-01)
  - `src/devolaflow/shell_proxy/{__init__,proxy,registry,commands}.py` (PV-02 + PV-04)
  - `src/devolaflow/lifecycle/pre_shell_call.py` (PV-02)
  - `src/devolaflow/memory_router/{__init__,cache,router}.py` (PV-03)
- **Schemas:**
  - `workflow-system/agent/knowledge/runtime-plugins.yaml` (PV-01, schema_version 2)
  - `schemas/memory-case.yaml` (PV-03, schema_version 1)
  - `schemas/command-mapping.yaml` (PV-04, schema_version 1)
- **Operator-local seeds (gitignored, opt-in):**
  - `.local/memory/cases/{README.md,index.yaml,<case-id>.md}` (PV-03 seeds)
  - `.local/memory/commands/{README.md,<repo>/<cmd>.yaml}` (PV-04 seeds)
- **External (per S-7 — canonical URL only):**
  - RTK: https://github.com/rtk-ai/rtk
  - DevolaFlow: https://github.com/YoRHa-Agents/DevolaFlow
  - NineS: https://github.com/YoRHa-Agents/NineS

---

## 11. Registry SSOT (A-5)

Per Architecture Rule **A-5 — Single-Source-of-Truth Registry Pattern**
(`AGENTS.md` §"A-5"; `.cursor/rules/repo-governance.mdc` §A-5;
`.rules/architecture.mdc` §A-5), the shell-proxy + memory-router stack
ships **3 of the 5 domain-SSOT registries** in DevolaFlow. Each surface
has exactly one owner module — cross-cutting consumers import from the
owner; they never re-declare the registration data locally.

| # | Registry symbol | Owner module | In-repo consumers |
|---|---|---|---|
| 1 | `WHITELIST: dict[str, Tier]` | `src/devolaflow/shell_proxy/registry.py` | `src/devolaflow/shell_proxy/proxy.py::ShellProxy.wrap_command` (delegates via `match_command`); `src/devolaflow/lifecycle/pre_shell_call.py` (re-uses `match_command` for hook-level enforcement) |
| 2 | `MemoryCase` (frozen dataclass) | `src/devolaflow/memory_router/cache.py` | `src/devolaflow/memory_router/router.py::MemoryRouter.lookup_case` (constructs via `build_case_from_dict` + invalidates via `is_ttl_expired` / `is_version_stale`) |
| 3 | `CommandMapping` (frozen dataclass) | `src/devolaflow/shell_proxy/commands.py` | `src/devolaflow/shell_proxy/commands.py::apply_local_recipe` (sibling-module consumer; loads + matches recipes against `WHITELIST` heads via `_match_recipe`) |

The remaining 2 SSOT registries live outside this stack:
`workflow-system/agent/plugins.yaml` (loaded by `devolaflow.plugins.loader`)
and `workflow-system/agent/knowledge/runtime-plugins.yaml` (loaded by
`devolaflow.plugins.installer.load_registry`).

**A-5 enforcement (CI guards)**

- `tests/test_no_ghost_features.py::test_registry_single_owner` —
  AST-walks `src/devolaflow/` and fails when more than one module-level
  definition (`class`, `def`, `Assign`, `AnnAssign`) exists for any
  registry name above. Adding a NEW whitelist / recipe / cache surface
  MUST pick a single owner per A-5.1.
- `scripts/detect_dead_apis.py::_check_allowlist_domain_overlap` +
  `tests/test_dead_apis.py::test_default_allowlist_no_ssot_overlap` —
  reject any `DEFAULT_ALLOWLIST` entry that names a domain-SSOT symbol
  per A-5.2 (such symbols HAVE in-repo callers, so they are not eligible
  for the "no production caller" allowlist).
- ADR: `.local/research/adr/v9-ADR-003-a5-ssot-registry.md` (rationale,
  alternatives considered, staged rollout).
