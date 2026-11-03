"""Tests for the Fresh Solutions-backed optimizer."""

from __future__ import annotations

from pathlib import Path

from fresh_urban_forest.optimize import OptimizationResult, build_problem, run_optimization
from tests.fixtures import make_dataset


def _run(tmp_path: Path, *, workers: int, seed: int = 5) -> OptimizationResult:
    """Run a small deterministic optimization."""
    problem = build_problem(
        make_dataset(tmp_path),
        site_count=8,
        species=("Acer rubrum", "Thuja plicata", "Quercus rubra"),
        horizon=5,
        seed=seed,
    )
    return run_optimization(
        problem,
        population_size=8,
        generations=2,
        scalarizations=6,
        local_iterations=20,
        workers=workers,
        seed=seed,
    )


def test_solver_returns_archive_and_history(tmp_path: Path) -> None:
    """A small run returns a bounded archive, history, and evidence."""
    result = _run(tmp_path / "one", workers=1)
    assert result.evaluations > 0
    assert result.scalarizations >= 6
    assert result.archive.solutions
    assert 0.0 <= result.archive.hypervolume <= 1.0
    assert len(result.history) == result.scalarizations
    payload = result.to_dict()
    assert "archive" in payload
    assert payload["scalarizations"] == result.scalarizations


def test_solver_is_deterministic_across_workers(tmp_path: Path) -> None:
    """The same seed and scalarizations produce the same archive across worker counts."""
    sequential = _run(tmp_path / "a", workers=1)
    parallel = _run(tmp_path / "b", workers=2)
    assert [solution.solution_id for solution in sequential.archive.solutions] == [
        solution.solution_id for solution in parallel.archive.solutions
    ]


def test_checkpoint_is_written(tmp_path: Path) -> None:
    """A completed scalarization writes a checkpoint."""
    problem = build_problem(
        make_dataset(tmp_path / "checkpoint"),
        site_count=6,
        species=("Acer rubrum", "Thuja plicata"),
        horizon=5,
    )
    path = tmp_path / "checkpoint.json"
    run_optimization(
        problem,
        population_size=6,
        generations=1,
        scalarizations=4,
        local_iterations=10,
        workers=1,
        checkpoint_path=path,
    )
    assert path.exists()
    assert "scalarization" in path.read_text(encoding="utf-8")
