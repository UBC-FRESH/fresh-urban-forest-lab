"""Non-dominated archives, fuzzy robustness, and approximate hypervolume.

The archive is the decision surface. It keeps only feasible, non-dominated solutions, adds
a bootstrap robustness score, and reports the ideal/nadir box used by the 3D explorer.
Hypervolume is Monte Carlo because the default problem has seven objectives.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.optimize import Objective, OptimizationProblem, Solution

ARCHIVE_EVIDENCE = evidence(
    "scenario",
    "pareto-archive",
    uncertainty=(
        "Finite archive from weighted scalarizations; hypervolume is Monte Carlo and "
        "robustness is a bootstrap diagnostic, not a dominance proof."
    ),
    source="Fresh Solutions scalarizations + non-dominated filtering",
)


@dataclass(frozen=True, slots=True)
class ParetoArchive:
    """A filtered Pareto archive and its summary.

    Attributes
    ----------
    problem_id : str
        Problem identifier.
    objectives : tuple of Objective
        Objective definitions.
    solutions : tuple of Solution
        Non-dominated feasible solutions.
    ideal : tuple of float
        Best value per objective.
    nadir : tuple of float
        Worst value per objective.
    hypervolume : float
        Approximate normalized hypervolume.
    robustness : tuple of float
        Bootstrap probability of remaining non-dominated.
    evidence : Evidence
        Method and tier.
    """

    problem_id: str
    objectives: tuple[Objective, ...]
    solutions: tuple[Solution, ...]
    ideal: tuple[float, ...]
    nadir: tuple[float, ...]
    hypervolume: float
    robustness: tuple[float, ...]
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the archive to a JSON-safe dictionary.

        Returns
        -------
        dict
            Objectives, ideal/nadir, hypervolume, and solutions with robustness.
        """
        return {
            "problem_id": self.problem_id,
            "objectives": [objective.to_dict() for objective in self.objectives],
            "ideal": [round(value, 6) for value in self.ideal],
            "nadir": [round(value, 6) for value in self.nadir],
            "hypervolume": round(self.hypervolume, 6),
            "solutions": [
                {**solution.to_dict(), "robustness": round(self.robustness[index], 4)}
                for index, solution in enumerate(self.solutions)
            ],
            "evidence": self.evidence.to_dict(),
        }


def dominates(
    first: Sequence[float],
    second: Sequence[float],
    objectives: Sequence[Objective],
) -> bool:
    """Return whether the first objective vector dominates the second.

    Parameters
    ----------
    first : tuple of float
        Candidate values.
    second : tuple of float
        Comparison values.
    objectives : sequence of Objective
        Objective directions.

    Returns
    -------
    bool
        ``True`` when first is no worse on every objective and better on one.
    """
    no_worse = True
    strictly_better = False
    for index, objective in enumerate(objectives):
        left = first[index]
        right = second[index]
        if objective.direction == "max":
            if left < right:
                no_worse = False
                break
            if left > right:
                strictly_better = True
        else:
            if left > right:
                no_worse = False
                break
            if left < right:
                strictly_better = True
    return no_worse and strictly_better


def non_dominated_indices(
    values: Sequence[Sequence[float]],
    objectives: Sequence[Objective],
) -> list[int]:
    """Return indices of non-dominated objective vectors.

    Parameters
    ----------
    values : sequence of tuple of float
        Objective vectors.
    objectives : sequence of Objective
        Objective directions.

    Returns
    -------
    list of int
        Non-dominated indices.
    """
    keep: list[int] = []
    for index, candidate in enumerate(values):
        if any(
            other != index and dominates(values[other], candidate, objectives)
            for other in range(len(values))
        ):
            continue
        keep.append(index)
    return keep


def solution_from_dict(payload: object) -> Solution:
    """Reconstruct one solution from an archive payload.

    Parameters
    ----------
    payload : object
        Mapping produced by :meth:`Solution.to_dict`.

    Returns
    -------
    Solution
        Reconstructed solution.

    Raises
    ------
    ValueError
        When the payload is malformed.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("solution payload must be a mapping")
    decisions_raw = payload.get("decisions", [])
    objectives_raw = payload.get("objectives", [])
    planted_raw = payload.get("planted", [])
    metrics_raw = payload.get("metrics", {})
    if not isinstance(decisions_raw, list) or not isinstance(objectives_raw, list):
        raise ValueError("solution decisions and objectives must be lists")
    decisions = tuple(int(value) for value in decisions_raw)
    objectives = tuple(float(value) for value in objectives_raw)
    metrics = (
        {str(key): float(value) for key, value in metrics_raw.items()}
        if isinstance(metrics_raw, Mapping)
        else {}
    )
    planted = (
        tuple(
            (str(item[0]), str(item[1]))
            for item in planted_raw
            if isinstance(item, (list, tuple)) and len(item) >= 2
        )
        if isinstance(planted_raw, list)
        else ()
    )
    return Solution(
        solution_id=str(payload.get("solution_id", "")),
        decisions=decisions,
        objectives=objectives,
        metrics=metrics,
        constraint_violation=float(payload.get("constraint_violation", 0.0)),
        planted=planted,
    )


def archive_from_dict(payload: object) -> ParetoArchive:
    """Reconstruct a Pareto archive from a JSON payload.

    Parameters
    ----------
    payload : object
        Mapping produced by :meth:`ParetoArchive.to_dict`.

    Returns
    -------
    ParetoArchive
        Reconstructed archive.

    Raises
    ------
    ValueError
        When the payload is malformed.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("archive payload must be a mapping")
    objectives_raw = payload.get("objectives", [])
    solutions_raw = payload.get("solutions", [])
    if not isinstance(objectives_raw, list) or not isinstance(solutions_raw, list):
        raise ValueError("archive objectives and solutions must be lists")
    objectives = tuple(
        Objective(
            name=str(item.get("name", "")),
            label=str(item.get("label", "")),
            direction="min" if str(item.get("direction", "max")) == "min" else "max",
        )
        for item in objectives_raw
        if isinstance(item, Mapping)
    )
    solutions = tuple(solution_from_dict(item) for item in solutions_raw)
    robustness = tuple(
        float(item.get("robustness", 0.0)) for item in solutions_raw if isinstance(item, Mapping)
    )
    ideal_raw = payload.get("ideal", [])
    nadir_raw = payload.get("nadir", [])
    ideal = tuple(float(value) for value in ideal_raw) if isinstance(ideal_raw, list) else ()
    nadir = tuple(float(value) for value in nadir_raw) if isinstance(nadir_raw, list) else ()
    return ParetoArchive(
        problem_id=str(payload.get("problem_id", "problem")),
        objectives=objectives,
        solutions=solutions,
        ideal=ideal,
        nadir=nadir,
        hypervolume=float(payload.get("hypervolume", 0.0)),
        robustness=robustness,
        evidence=ARCHIVE_EVIDENCE,
    )


def build_archive(problem: OptimizationProblem, solutions: list[Solution]) -> ParetoArchive:
    """Build a feasible, non-dominated, robust archive.

    Parameters
    ----------
    problem : OptimizationProblem
        Problem definition.
    solutions : list of Solution
        Candidate solutions.

    Returns
    -------
    ParetoArchive
        Filtered archive with hypervolume and robustness.
    """
    feasible: dict[str, Solution] = {}
    for solution in solutions:
        if solution.constraint_violation <= 1e-9:
            feasible.setdefault(solution.solution_id, solution)
    candidates = list(feasible.values())
    if not candidates:
        return ParetoArchive(
            problem_id=problem.problem_id,
            objectives=problem.objectives,
            solutions=(),
            ideal=(),
            nadir=(),
            hypervolume=0.0,
            robustness=(),
            evidence=ARCHIVE_EVIDENCE,
        )
    indices = non_dominated_indices(
        [solution.objectives for solution in candidates], problem.objectives
    )
    front = [candidates[index] for index in indices]
    ideal, nadir = _ideal_nadir(front, problem.objectives)
    robustness = _fuzzy_robustness(front, problem.objectives, ideal, nadir, seed=problem.seed)
    hypervolume = _hypervolume(front, problem.objectives, problem, seed=problem.seed)
    return ParetoArchive(
        problem_id=problem.problem_id,
        objectives=problem.objectives,
        solutions=tuple(front),
        ideal=ideal,
        nadir=nadir,
        hypervolume=hypervolume,
        robustness=robustness,
        evidence=ARCHIVE_EVIDENCE,
    )


def _ideal_nadir(
    solutions: list[Solution],
    objectives: tuple[Objective, ...],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Return best and worst values per objective."""
    ideal: list[float] = []
    nadir: list[float] = []
    for index, objective in enumerate(objectives):
        values = [solution.objectives[index] for solution in solutions]
        if objective.direction == "max":
            ideal.append(max(values))
            nadir.append(min(values))
        else:
            ideal.append(min(values))
            nadir.append(max(values))
    return (tuple(ideal), tuple(nadir))


def _problem_scales(problem: OptimizationProblem) -> tuple[float, ...]:
    """Return fixed objective scales for comparable hypervolume.

    Parameters
    ----------
    problem : OptimizationProblem
        Problem definition.

    Returns
    -------
    tuple of float
        Positive scales in objective order.
    """
    max_shade = sum(
        max((option.shade_m2h for option in problem.species), default=1.0) for _ in problem.sites
    )
    max_carbon = sum(
        max((option.carbon_kg for option in problem.species), default=1.0) for _ in problem.sites
    )
    max_cost = sum(
        max((option.cost_cad for option in problem.species), default=1.0) for _ in problem.sites
    )
    max_water = sum(
        max((option.water_l for option in problem.species), default=1.0) for _ in problem.sites
    )
    return (
        max(max_shade, 1.0),
        max(max_shade, 1.0),
        1.0,
        math.log(max(len(problem.species), 2)),
        max(max_carbon, 1.0),
        max(max_cost, 1.0),
        max(max_water, 1.0),
    )


def _fixed_normalise(
    solution: Solution,
    objectives: tuple[Objective, ...],
    scales: tuple[float, ...],
) -> tuple[float, ...]:
    """Normalise a solution against fixed problem scales, best = 0."""
    values: list[float] = []
    for index, objective in enumerate(objectives):
        scale = max(scales[index], 1e-9)
        raw = solution.objectives[index] / scale
        value = 1.0 - raw if objective.direction == "max" else raw
        values.append(max(0.0, min(1.0, value)))
    return tuple(values)


def _hypervolume(
    solutions: list[Solution],
    objectives: tuple[Objective, ...],
    problem: OptimizationProblem,
    *,
    seed: int,
    samples: int = 20_000,
) -> float:
    """Estimate fixed-reference hypervolume with Monte Carlo sampling."""
    if not solutions:
        return 0.0
    dimensions = len(objectives)
    rng = np.random.default_rng(seed)
    points = rng.random((samples, dimensions))
    scales = _problem_scales(problem)
    normalized = np.asarray(
        [_fixed_normalise(solution, objectives, scales) for solution in solutions],
        dtype=np.float64,
    )
    dominated = np.any(
        np.all(normalized[:, np.newaxis, :] <= points[np.newaxis, :, :], axis=2),
        axis=0,
    )
    return float(np.mean(dominated))


def _fuzzy_robustness(
    solutions: list[Solution],
    objectives: tuple[Objective, ...],
    ideal: tuple[float, ...],
    nadir: tuple[float, ...],
    *,
    seed: int,
    samples: int = 12,
    noise: float = 0.03,
) -> tuple[float, ...]:
    """Estimate how often each solution stays non-dominated under small noise."""
    if len(solutions) <= 1:
        return (1.0,) * len(solutions)
    rng = np.random.default_rng(seed)
    dimensions = len(objectives)
    spans = np.asarray([abs(nadir[index] - ideal[index]) for index in range(dimensions)])
    spans = np.where(spans <= 1e-12, 1.0, spans)
    base = np.asarray([solution.objectives for solution in solutions], dtype=np.float64)
    counts = np.zeros(len(solutions), dtype=np.float64)
    for _ in range(samples):
        perturbed = base + rng.normal(0.0, 1.0, base.shape) * spans * noise
        keep = non_dominated_indices(
            [tuple(row) for row in perturbed],
            objectives,
        )
        counts[keep] += 1.0
    return tuple(float(value / samples) for value in counts)


def slice_solutions(
    archive: ParetoArchive,
    *,
    objective_index: int,
    lower: float,
    upper: float,
) -> tuple[Solution, ...]:
    """Return solutions whose objective lies inside a slice interval.

    Parameters
    ----------
    archive : ParetoArchive
        Archive to filter.
    objective_index : int
        Objective position.
    lower : float
        Inclusive lower bound.
    upper : float
        Inclusive upper bound.

    Returns
    -------
    tuple of Solution
        Solutions in the slice.
    """
    if objective_index < 0 or objective_index >= len(archive.objectives):
        return ()
    return tuple(
        solution
        for solution in archive.solutions
        if lower <= solution.objectives[objective_index] <= upper
    )


def _finite(value: float, default: float = 0.0) -> float:
    """Return a finite value or the default."""
    return value if math.isfinite(value) else default
