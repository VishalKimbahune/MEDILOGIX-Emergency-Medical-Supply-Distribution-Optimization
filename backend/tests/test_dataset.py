"""Tests for the MEDILOGIX synthetic dataset generator and validator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


def _load_module(name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(name, file_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dataset_generation_and_validation(tmp_path: Path) -> None:
    gen_mod = _load_module("generate_dataset", DATA_DIR / "generate_dataset.py")
    val_mod = _load_module("validate_dataset", DATA_DIR / "validate_dataset.py")

    counts = gen_mod.generate_all(output_dir=tmp_path, seed=42)
    assert counts["warehouses.csv"] == 3
    assert counts["hospitals.csv"] == 8
    assert counts["products.csv"] == 4
    assert counts["inventory.csv"] == 12
    assert counts["demands.csv"] == 32
    assert counts["routes.csv"] == 24

    is_valid, errors, summary = val_mod.validate_dataset(data_dir=tmp_path)
    assert is_valid, f"Dataset validation failed: {errors}"
    assert any(stats["net_balance"] < 0 for stats in summary.values())
