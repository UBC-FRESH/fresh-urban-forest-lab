"""Tests for the planting problem schema and exact evaluator."""

from __future__ import annotations

from pathlib import Path

import pytest

from fresh_urban_forest.optimize import (
    OptimizationProblem,
    build_problem,
    evaluate_population,
    evaluate_solution,
    problem_from_dict,
    solution_to_edits,
)
from tests.fixtures import make_dataset

SPECIES = ("Acer rubrum", "Thuja plicata", "Quercus rubra")


def _problem(tmp_path: Path, *, site_count: int = 8) -> OptimizationProblem:
    """Build a small synthetic problem."""
    dataset = make_dataset(tmp_path)
    return build_problem(
        dataset,
        site_count=site_count,
        species=SPECIES,
        horizon=10,
        budget_cad=50_000.0,
    )


def test_problem_round_trip_and_defaults(tmp_path: Path) -> None:
    """The problem schema round-trips and exposes the documented defaults."""
    problem = _problem(tmp_path)
    assert len(problem.sites) >= 4
    assert len(problem.species) == 3
    assert len(problem.objectives) == 7
    assert problem.max_sites >= 1
    payload = problem.to_dict()
    restored = problem_from_dict(payload)
    assert restored.problem_id == problem.problem_id
    assert len(restored.sites) == len(problem.sites)
    assert len(restored.objectives) == len(problem.objectives)
    assert restored.sites[0].site_id == problem.sites[0].site_id


def test_empty_plan_is_feasible_and_zero(tmp_path: Path) -> None:
    """The empty plan has zero objectives and no violation."""
    problem = _problem(tmp_path)
    solution = evaluate_solution(problem, (0,) * len(problem.sites))
    assert solution.constraint_violation == 0.0
    assert solution.objectives[0] == 0.0
    assert solution.planted == ()


def test_full_plan_can_violate_the_species_share(tmp_path: Path) -> None:
    """Planting one species everywhere violates the default species-share constraint."""
    problem = _problem(tmp_path)
    solution = evaluate_solution(problem, (1,) * len(problem.sites))
    assert solution.constraint_violation > 0.0
    assert solution.metrics["selected_count"] == float(len(problem.sites))


def test_parallel_and_sequential_evaluation_match(tmp_path: Path) -> None:
    """Batch evaluation is independent of worker count."""
    problem = _problem(tmp_path)
    population = ((0,) * len(problem.sites), (1,) + (0,) * (len(problem.sites) - 1))
    sequential = evaluate_population(problem, population, workers=1)
    parallel = evaluate_population(problem, population, workers=2)
    assert [item.objectives for item in sequential] == [item.objectives for item in parallel]


def test_solution_converts_to_plant_edits(tmp_path: Path) -> None:
    """A solution creates one plant edit per planted site."""
    problem = _problem(tmp_path)
    solution = evaluate_solution(problem, (1, 2, 0, 0, 0, 0, 0, 0))
    edits = solution_to_edits(problem, solution)
    assert len(edits) == len(solution.planted)
    assert all(edit.kind == "plant" for edit in edits)
    assert all(edit.species for edit in edits)


def test_problem_requires_sites_and_species(tmp_path: Path) -> None:
    """An empty synthetic dataset cannot produce a problem."""
    import numpy as np

    from fresh_urban_forest.dataset import build_dataset
    from tests.fixtures import make_raster

    dem = make_raster(tmp_path / "dem.tif", np.zeros((10, 10), dtype=np.float32))
    chm = make_raster(tmp_path / "chm.tif", np.full((10, 10), 20.0, dtype=np.float32))
    dataset = build_dataset(
        name="empty",
        trees=(),
        dem=dem,
        chm=chm,
        out_dir=tmp_path / "empty",
    )
    with pytest.raises(ValueError, match="no planting candidates"):
        build_problem(dataset, site_count=4, species=SPECIES)
