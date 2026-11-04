"""Tests for Pareto dominance, archives, robustness, and slices."""

from __future__ import annotations

from pathlib import Path

from fresh_urban_forest.optimize import Objective, Solution, build_problem
from fresh_urban_forest.pareto import (
    build_archive,
    dominates,
    non_dominated_indices,
    slice_solutions,
)
from tests.fixtures import make_dataset

MAX = Objective("a", "A", "max")
MIN = Objective("b", "B", "min")


def test_dominance_respects_directions() -> None:
    """Maximization and minimization directions are respected."""
    assert dominates((2.0, 1.0), (1.0, 2.0), (MAX, MIN))
    assert not dominates((1.0, 2.0), (2.0, 1.0), (MAX, MIN))
    assert not dominates((2.0, 1.0), (2.0, 1.0), (MAX, MIN))


def test_non_dominated_indices_keep_the_tradeoff() -> None:
    """Two tradeoff points survive and a dominated point is removed."""
    values = [(2.0, 3.0), (1.0, 2.0), (0.5, 4.0)]
    assert non_dominated_indices(values, (MAX, MIN)) == [0, 1]


def test_archive_has_hypervolume_and_robustness(tmp_path: Path) -> None:
    """A two-point front produces a bounded hypervolume and robustness values."""
    problem = build_problem(
        make_dataset(tmp_path),
        site_count=6,
        species=("Acer rubrum", "Thuja plicata"),
        horizon=5,
    )
    first = Solution(
        solution_id="s1",
        decisions=(1,) + (0,) * (len(problem.sites) - 1),
        objectives=(10.0, 1.0, 0.5, 0.7, 5.0, 100.0, 20.0),
        metrics={"selected_count": 1.0},
        constraint_violation=0.0,
        planted=((problem.sites[0].site_id, problem.species[0].name),),
    )
    second = Solution(
        solution_id="s2",
        decisions=(0,) * (len(problem.sites) - 1) + (1,),
        objectives=(1.0, 10.0, 0.5, 0.7, 5.0, 100.0, 20.0),
        metrics={"selected_count": 1.0},
        constraint_violation=0.0,
        planted=((problem.sites[-1].site_id, problem.species[0].name),),
    )
    archive = build_archive(problem, [first, second])
    assert len(archive.solutions) == 2
    assert 0.0 <= archive.hypervolume <= 1.0
    assert len(archive.robustness) == 2
    assert all(0.0 <= value <= 1.0 for value in archive.robustness)


def test_slice_solutions_filters_an_objective(tmp_path: Path) -> None:
    """A slice keeps only solutions inside the selected interval."""
    problem = build_problem(
        make_dataset(tmp_path),
        site_count=6,
        species=("Acer rubrum",),
        horizon=5,
    )
    solution = Solution(
        solution_id="one",
        decisions=(1,) + (0,) * (len(problem.sites) - 1),
        objectives=(3.0, 3.0, 0.0, 0.0, 1.0, 10.0, 1.0),
        metrics={},
        constraint_violation=0.0,
        planted=((problem.sites[0].site_id, problem.species[0].name),),
    )
    archive = build_archive(problem, [solution])
    assert slice_solutions(archive, objective_index=0, lower=2.0, upper=4.0)
    assert not slice_solutions(archive, objective_index=0, lower=8.0, upper=9.0)
    assert slice_solutions(archive, objective_index=99, lower=0.0, upper=10.0) == ()
