# RPMI-CMV V0 Development Notes

This document records local execution issues that affected Wave 0 and the
workarounds that should be reused in later waves.

Only record reusable lessons here. Good entries are issues that may affect later
waves, future Codex windows, reproducibility, environment setup, test commands,
or DevolaFlow orchestration. Do not record ordinary typos, transient debug
prints, or one-off mistakes fixed immediately.

## Wave 0 Issues And Resolutions

### PowerShell Startup Latency

During Wave 0, login-style PowerShell invocations were slow enough that even
simple commands could time out. This was not caused by the RPMI code or tests.

Resolution:

```text
Use non-login shell execution for routine commands in this workspace.
```

For manual work, prefer direct project commands:

```powershell
uv run pytest tests
uv run python -c "from rpmi import RunConfig, init_run; print(init_run(RunConfig(), 'outputs').run_dir)"
```

### Windows Pytest Globbing

PowerShell may not expand `tests/test_phase0_*.py` before passing it to
`pytest`, which can produce:

```text
file or directory not found: tests/test_phase0_*.py
```

Resolution:

```powershell
uv run pytest tests
```

Or explicitly list Phase 0 files:

```powershell
uv run pytest tests\test_phase0_feature_flags.py tests\test_phase0_id_conventions.py tests\test_phase0_output_schema.py tests\test_phase0_reproducibility.py
```

### uv Package Index Warnings

`uv sync` may print many `Skipping file` warnings for old wheels from packages
such as `numpy`, `PyYAML`, or `pygments`. These warnings are not failures when
the command finishes successfully and installs the requested environment.

Resolution:

```text
Treat the final command status as authoritative. If `uv sync --extra dev`
finishes successfully, continue.
```

### code_version Without Git

This folder was not a git repository during Wave 0. The Phase 0 code therefore
falls back to:

```text
local_dirty
```

This matches the Phase 0 specification. If the project is later initialized as a
git repository, run initialization will use the git short commit hash.

### GitHub Push On This Windows Machine

The machine previously had global Git proxy settings pointing at a local proxy:

```text
http.proxy=http://127.0.0.1:15715
https.proxy=http://127.0.0.1:15715
```

When that local proxy is not running, GitHub HTTPS operations fail. The global
proxy settings were removed with:

```powershell
git config --global --unset http.proxy
git config --global --unset https.proxy
```

Direct HTTPS was still unstable, so GitHub push used SSH. The `id_rsa` key is
authenticated for the `BaKa-RICH` GitHub account. The local SSH config file has
strict-permission warnings under the Codex sandbox user, so push commands should
use an explicit key and an empty temporary SSH config when needed.

## DevolaFlow Subtask Notes

Wave 0 initially attempted to split work into two background subtasks:

```text
1. core package implementation
2. tests and environment documentation
```

Both subtasks were scoped with disjoint file ownership, but they did not return
within the expected window. They were shut down and the main workflow completed
the work directly. One partial artifact, `src/rpmi/runner.py`, used an obsolete
interface and was rewritten as a thin compatibility wrapper around
`rpmi.run.init_run`.

Recommended policy for later waves:

```text
Use DevolaFlow-style decomposition for planning and review, but only delegate
background implementation when the parent can keep working independently and
the task does not depend on uncommitted interfaces from another subtask.
```

For this repository, prefer the following pattern:

```text
1. Main agent defines or edits shared interfaces first.
2. Background subtasks get narrow, file-owned implementation or review work.
3. Each subtask receives explicit file ownership, acceptance criteria, and a
   short timeout.
4. If a subtask stalls, close it and reconcile partial files before testing.
5. Always run the gate tests from the main workflow after integration.
```

Good candidates for background subtasks:

```text
review-only checks
documentation polish
independent tests for already-stable APIs
one module with no shared-write conflict
```

Poor candidates for background subtasks:

```text
initial shared API design
two tasks that must agree on new names or return types
environment setup while the parent also needs the same shell resources
large multi-file changes with overlapping imports
```
