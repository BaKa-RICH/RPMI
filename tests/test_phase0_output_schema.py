import csv
import json

from rpmi.conventions import UNITS_VERSION
from rpmi.logging_schema import CSV_LOG_SCHEMAS, REQUIRED_JSON_LOGS, SHARED_COLUMNS
from rpmi.run import init_run
from rpmi.config import RunConfig


def test_init_run_creates_required_phase0_artifacts(tmp_path):
    artifacts = init_run(
        RunConfig(scenario_id="s0", algorithm_id="phase0", seed=11),
        tmp_path,
        run_id="run_fixed",
        code_version="test_version",
    )

    assert artifacts.run_dir == tmp_path / "run_fixed"
    for subdir in ["figures", "debug_snapshots", "tables"]:
        assert (artifacts.run_dir / subdir).is_dir()

    for filename in [
        "run_config.json",
        "config_canonical.json",
        "config_hash.txt",
        "seed.txt",
        "code_version.txt",
        "global_conventions.json",
        *REQUIRED_JSON_LOGS,
    ]:
        assert (artifacts.run_dir / filename).is_file()

    conventions = json.loads((artifacts.run_dir / "global_conventions.json").read_text())
    assert conventions["units_version"] == UNITS_VERSION
    assert conventions["lanes"]["target_lane"] == 0
    assert conventions["lanes"]["ramp_lane"] == -1


def test_all_csv_log_schemas_exist_and_share_join_keys(tmp_path):
    artifacts = init_run(RunConfig(seed=2), tmp_path, run_id="run_schema")

    for filename, expected_columns in CSV_LOG_SCHEMAS.items():
        path = artifacts.run_dir / filename
        assert path.is_file()
        with path.open(newline="", encoding="utf-8") as file:
            header = next(csv.reader(file))
        assert header == expected_columns
        for column in SHARED_COLUMNS:
            assert column in header

