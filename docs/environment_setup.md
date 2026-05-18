# RPMI-CMV V0 Environment Setup

This project uses `uv` with Python 3.12 for the Phase 0 implementation.

## Why `uv`

Phase 0 is a light Python package: the runtime needs only `numpy` and `PyYAML`,
and tests use `pytest`. `uv` keeps the project environment local in `.venv`,
starts quickly on Windows, and avoids coupling this repository to the global
Anaconda installation. Conda remains useful later if the project adds heavy
compiled traffic-simulation dependencies, but it is unnecessary for Wave 0.

## Python Version

Use Python 3.12. The repository includes:

```text
.python-version
pyproject.toml
```

The current Windows machine has Python 3.12.12 available, and `uv` can manage
that interpreter for this project.

## Create Or Refresh The Environment

From `D:\PycharmProjects\rpmi_v0`:

```powershell
uv venv --python 3.12
uv sync --extra dev
```

To run commands without manually activating the environment:

```powershell
uv run pytest tests
```

On Windows PowerShell, `tests/test_phase0_*.py` may be passed to `pytest` as a
literal path instead of being expanded into matching files. For Phase 0-only
verification, either run the whole `tests` directory or list the files
explicitly:

```powershell
uv run pytest tests\test_phase0_feature_flags.py tests\test_phase0_id_conventions.py tests\test_phase0_output_schema.py tests\test_phase0_reproducibility.py
```

Optional activation for an interactive shell:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Dependency Policy

Keep Phase 0 dependencies minimal:

```text
runtime: numpy, pyyaml
test: pytest
```

Do not add SUMO, MOBIL, RL, action-bundle, GUI, or traffic-simulation
dependencies during Phase 0. Those are explicitly locked out by feature flags.

## Reproducibility Notes

Every initialized run writes:

```text
run_config.json
config_canonical.json
config_hash.txt
seed.txt
code_version.txt
global_conventions.json
empty CSV logs with shared join keys
```

The config hash is generated from stable canonical JSON. The state hash helper
also uses canonical JSON, but Phase 0 does not generate real traffic states.
Later phases should reuse this contract rather than introducing a second hash
format.
