"""Spatio-temporal planting optimization and exact objective evaluation.

The problem is deliberately small and auditable: candidate sites come from the planting
advisor, each site can grow one species or stay empty, and the evaluator sums precomputed
shade, carbon, water, cost, and habitat values. The archive itself comes from an
NSGA-II-style solver; the surrogate is a screening aid and is never the archive evaluator.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import multiprocessing
import random
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from fresh_solutions import (
    Change,
    Evaluation,
    HybridResult,
    PopulationConfig,
    SearchConfig,
    run_hybrid_search,
)

from fresh_urban_forest.allometry import (
    carbon_kg,
    estimate_crown_width_m,
    estimate_height_m,
    species_group,
)
from fresh_urban_forest.dss import PlantingCandidate, recommend_planting
from fresh_urban_forest.evidence import Evidence, evidence
from fresh_urban_forest.models import ScenarioEdit, UrbanForestDataset
from fresh_urban_forest.shade import shade_period
from fresh_urban_forest.solar import time_grid
from fresh_urban_forest.species import profile_for_species
from fresh_urban_forest.vigor import growth_response, project_species_growth
from fresh_urban_forest.water import simulate_water_balance

if TYPE_CHECKING:
    from fresh_urban_forest.pareto import ParetoArchive

ObjectiveDirection = Literal["max", "min"]
PROBLEM_EVIDENCE = evidence(
    "scenario",
    "precomputed-objective-evaluator",
    uncertainty=(
        "Fast shade, water, carbon, and habitat proxies use precomputed P7 values; the "
        "archive is a finite approximation, not a proof of global optimality."
    ),
    source="P7 shade/species/water engine plus a transparent NSGA-II-style search",
)


@dataclass(frozen=True, slots=True)
class CandidateSite:
    """One candidate planting site.

    Attributes
    ----------
    site_id : str
        Stable site identifier.
    lon : float
        Longitude.
    lat : float
        Latitude.
    x_m : float
        Projected easting.
    y_m : float
        Projected northing.
    sun_fraction : float
        Fraction of sampled daylight the site is directly sunlit.
    heat_weight : float
        Relative value of shade at this site.
    soil_volume_m3 : float
        Assumed available soil volume.
    base_score : float
        Existing planting-advisor score.
    """

    site_id: str
    lon: float
    lat: float
    x_m: float
    y_m: float
    sun_fraction: float
    heat_weight: float
    soil_volume_m3: float
    base_score: float

    def to_dict(self) -> dict[str, object]:
        """Convert the site to JSON-safe values.

        Returns
        -------
        dict
            Site coordinates and weights.
        """
        return {
            "site_id": self.site_id,
            "lon": round(self.lon, 6),
            "lat": round(self.lat, 6),
            "x_m": round(self.x_m, 2),
            "y_m": round(self.y_m, 2),
            "sun_fraction": round(self.sun_fraction, 3),
            "heat_weight": round(self.heat_weight, 3),
            "soil_volume_m3": round(self.soil_volume_m3, 2),
            "base_score": round(self.base_score, 3),
        }


@dataclass(frozen=True, slots=True)
class SpeciesOption:
    """Precomputed species performance at maturity.

    Attributes
    ----------
    name : str
        Scientific name.
    common_name : str
        Common name.
    group : str
        Species group.
    native : bool
        Native flag.
    mature_height_m : float
        Height at the horizon.
    mature_crown_width_m : float
        Crown width at the horizon.
    shade_m2h : float
        Full-sun shade area-hours at the horizon.
    carbon_kg : float
        Above-ground carbon at the horizon.
    water_l : float
        Annual irrigation litres under the default policy.
    cost_cad : float
        Planting, maintenance, and water cost over the horizon.
    habitat_value : float
        Transparent crown-volume/native habitat proxy.
    """

    name: str
    common_name: str
    group: str
    native: bool
    mature_height_m: float
    mature_crown_width_m: float
    shade_m2h: float
    carbon_kg: float
    water_l: float
    cost_cad: float
    habitat_value: float

    def to_dict(self) -> dict[str, object]:
        """Convert the option to JSON-safe values.

        Returns
        -------
        dict
            Species performance values.
        """
        return {
            "name": self.name,
            "common_name": self.common_name,
            "group": self.group,
            "native": self.native,
            "mature_height_m": round(self.mature_height_m, 2),
            "mature_crown_width_m": round(self.mature_crown_width_m, 2),
            "shade_m2h": round(self.shade_m2h, 1),
            "carbon_kg": round(self.carbon_kg, 2),
            "water_l": round(self.water_l, 1),
            "cost_cad": round(self.cost_cad, 2),
            "habitat_value": round(self.habitat_value, 4),
        }


@dataclass(frozen=True, slots=True)
class Objective:
    """One optimization objective.

    Attributes
    ----------
    name : str
        Machine name.
    label : str
        Human label.
    direction : str
        ``max`` or ``min``.
    """

    name: str
    label: str
    direction: ObjectiveDirection

    def to_dict(self) -> dict[str, str]:
        """Convert the objective to JSON-safe values.

        Returns
        -------
        dict
            Name, label, and direction.
        """
        return {"name": self.name, "label": self.label, "direction": self.direction}


@dataclass(frozen=True, slots=True)
class OptimizationProblem:
    """A complete planting optimization problem.

    Attributes
    ----------
    problem_id : str
        Stable problem identifier.
    dataset_id : str
        Base dataset identifier.
    sites : tuple of CandidateSite
        Candidate planting sites.
    species : tuple of SpeciesOption
        Species options. Index zero in a decision is always "no plant".
    objectives : tuple of Objective
        Objective definitions.
    horizon : int
        Projection horizon in years.
    budget_cad : float
        Budget constraint.
    max_sites : int
        Maximum planted sites.
    max_species_share : float
        Maximum share of one species.
    seed : int
        Default search seed.
    evidence : Evidence
        Method and tier.
    """

    problem_id: str
    dataset_id: str
    sites: tuple[CandidateSite, ...]
    species: tuple[SpeciesOption, ...]
    objectives: tuple[Objective, ...]
    horizon: int
    budget_cad: float
    max_sites: int
    max_species_share: float
    seed: int
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the problem to a JSON-safe dictionary.

        Returns
        -------
        dict
            Problem schema.
        """
        return {
            "problem_id": self.problem_id,
            "dataset_id": self.dataset_id,
            "sites": [site.to_dict() for site in self.sites],
            "species": [option.to_dict() for option in self.species],
            "objectives": [objective.to_dict() for objective in self.objectives],
            "horizon": self.horizon,
            "budget_cad": self.budget_cad,
            "max_sites": self.max_sites,
            "max_species_share": self.max_species_share,
            "seed": self.seed,
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class Solution:
    """One evaluated decision vector.

    Attributes
    ----------
    solution_id : str
        Content hash of the decision vector.
    decisions : tuple of int
        Species index per site; zero means no plant.
    objectives : tuple of float
        Objective values in problem order.
    metrics : mapping of str to float
        Raw metrics behind the objectives.
    constraint_violation : float
        Normalised constraint violation. Zero is feasible.
    planted : tuple of tuple of str
        ``(site_id, species_name)`` pairs for planted sites.
    """

    solution_id: str
    decisions: tuple[int, ...]
    objectives: tuple[float, ...]
    metrics: Mapping[str, float]
    constraint_violation: float
    planted: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, object]:
        """Convert the solution to JSON-safe values.

        Returns
        -------
        dict
            Decisions, objectives, metrics, and planted assignments.
        """
        return {
            "solution_id": self.solution_id,
            "decisions": list(self.decisions),
            "objectives": [round(value, 6) for value in self.objectives],
            "metrics": {key: round(value, 6) for key, value in self.metrics.items()},
            "constraint_violation": round(self.constraint_violation, 6),
            "planted": [[site, species] for site, species in self.planted],
        }


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """The solver result and its archive.

    Attributes
    ----------
    problem : OptimizationProblem
        Problem that was solved.
    archive : ParetoArchive
        Pareto archive from :mod:`fresh_urban_forest.pareto`.
    generations : int
        Generations requested.
    population_size : int
        Population size.
    evaluations : int
        Unique decision vectors evaluated.
    runtime_s : float
        Runtime in seconds.
    history : tuple of mapping of str to float
        Per-scalarisation summary.
    seed : int
        Search seed.
    scalarizations : int
        Number of weighted scalarizations solved through Fresh Solutions.
    surrogate : mapping of str to object or None
        Optional surrogate report.
    convergence : tuple of tuple of float
        Optional best-objective history for each scalarization.
    evidence : Evidence
        Method and tier.
    """

    problem: OptimizationProblem
    archive: ParetoArchive
    generations: int
    population_size: int
    evaluations: int
    runtime_s: float
    history: tuple[dict[str, float], ...]
    seed: int
    scalarizations: int
    surrogate: Mapping[str, object] | None
    convergence: tuple[tuple[float, ...], ...]
    evidence: Evidence

    def to_dict(self) -> dict[str, object]:
        """Convert the result to a JSON-safe dictionary.

        Returns
        -------
        dict
            Problem, archive, history, and evidence.
        """
        return {
            "problem": self.problem.to_dict(),
            "archive": self.archive.to_dict(),
            "generations": self.generations,
            "population_size": self.population_size,
            "evaluations": self.evaluations,
            "runtime_s": round(self.runtime_s, 3),
            "history": [dict(row) for row in self.history],
            "seed": self.seed,
            "scalarizations": self.scalarizations,
            "surrogate": dict(self.surrogate) if self.surrogate is not None else None,
            "convergence": [list(row) for row in self.convergence],
            "evidence": self.evidence.to_dict(),
        }


def build_problem(
    dataset: UrbanForestDataset,
    *,
    site_count: int = 32,
    species: Sequence[str] | None = None,
    horizon: int = 20,
    budget_cad: float = 60_000.0,
    max_sites: int | None = None,
    max_species_share: float = 0.6,
    seed: int = 42,
    grid_m: float = 12.0,
    center_lonlat: tuple[float, float] | None = None,
    radius_m: float | None = None,
) -> OptimizationProblem:
    """Build a planting optimization problem from a dataset.

    Parameters
    ----------
    dataset : UrbanForestDataset
        Dataset to search.
    site_count : int
        Number of candidate sites.
    species : sequence of str or None
        Species names. Defaults to a native/non-native mix.
    horizon : int
        Projection horizon.
    budget_cad : float
        Budget constraint.
    max_sites : int or None
        Maximum planted sites.
    max_species_share : float
        Maximum share of one species.
    seed : int
        Default search seed.
    grid_m : float
        Candidate grid spacing.
    center_lonlat : tuple of float or None
        Optional candidate-search centre.
    radius_m : float or None
        Optional candidate-search radius.

    Returns
    -------
    OptimizationProblem
        The problem.

    Raises
    ------
    ValueError
        When no candidate sites are available.
    """
    names = tuple(species or _default_species())
    candidates = recommend_planting(
        dataset,
        count=max(site_count * 2, site_count),
        species=names[0],
        grid_m=grid_m,
        center_lonlat=center_lonlat,
        radius_m=radius_m,
    )
    if not candidates:
        raise ValueError("no planting candidates are available in this dataset")
    selected = candidates[:site_count]
    whens = time_grid(dt.date(2026, 6, 21), times=("09:00", "12:00", "15:00", "18:00"))
    period = shade_period(dataset, whens, include_terrain=True)
    sites = tuple(
        _site_from_candidate(
            dataset,
            candidate,
            index=index,
            period=period,
            soil_volume_m3=4.0,
        )
        for index, candidate in enumerate(selected)
    )
    options = tuple(_species_option(name, horizon=horizon, sun_fraction=0.6) for name in names)
    objectives = _default_objectives()
    problem_id = _slug(f"{dataset.manifest.dataset_id}-{site_count}-{horizon}-{seed}")
    return OptimizationProblem(
        problem_id=problem_id,
        dataset_id=dataset.manifest.dataset_id,
        sites=sites,
        species=options,
        objectives=objectives,
        horizon=horizon,
        budget_cad=budget_cad,
        max_sites=max_sites or min(len(sites), 40),
        max_species_share=max_species_share,
        seed=seed,
        evidence=PROBLEM_EVIDENCE,
    )


def evaluate_solution(problem: OptimizationProblem, decisions: Sequence[int]) -> Solution:
    """Evaluate one decision vector exactly.

    Parameters
    ----------
    problem : OptimizationProblem
        Problem definition.
    decisions : sequence of int
        Species index per site; zero means no plant.

    Returns
    -------
    Solution
        Objectives, metrics, and constraint violation.
    """
    vector = tuple(int(value) for value in decisions[: len(problem.sites)])
    if len(vector) < len(problem.sites):
        vector = vector + (0,) * (len(problem.sites) - len(vector))
    shade = 0.0
    equity = 0.0
    carbon = 0.0
    cost = 0.0
    water = 0.0
    habitat = 0.0
    native_count = 0
    counts: dict[str, int] = {}
    planted: list[tuple[str, str]] = []
    for site, index in zip(problem.sites, vector, strict=True):
        if index <= 0 or index > len(problem.species):
            continue
        option = problem.species[index - 1]
        site_shade = option.shade_m2h * site.sun_fraction
        shade += site_shade
        equity += site_shade * site.heat_weight
        carbon += option.carbon_kg
        cost += option.cost_cad
        water += option.water_l
        habitat += option.habitat_value
        if option.native:
            native_count += 1
        counts[option.name] = counts.get(option.name, 0) + 1
        planted.append((site.site_id, option.name))
    selected_count = len(planted)
    native_fraction = native_count / selected_count if selected_count else 0.0
    diversity = _shannon(counts)
    violation = _constraint_violation(
        problem,
        selected_count=selected_count,
        cost=cost,
        counts=counts,
    )
    metrics = {
        "shade_m2h": shade,
        "equity_m2h": equity,
        "native_fraction": native_fraction,
        "shannon_index": diversity,
        "carbon_kg": carbon,
        "cost_cad": cost,
        "water_l": water,
        "habitat_index": habitat,
        "selected_count": float(selected_count),
        "species_count": float(len(counts)),
    }
    objective_values = (
        shade,
        equity,
        native_fraction,
        diversity,
        carbon,
        cost,
        water,
    )
    return Solution(
        solution_id=_solution_id(vector),
        decisions=vector,
        objectives=objective_values,
        metrics=metrics,
        constraint_violation=violation,
        planted=tuple(planted),
    )


def evaluate_population(
    problem: OptimizationProblem,
    population: Sequence[Sequence[int]],
    *,
    workers: int = 1,
) -> list[Solution]:
    """Evaluate a population, optionally in a process pool.

    Parameters
    ----------
    problem : OptimizationProblem
        Problem definition.
    population : sequence of sequence of int
        Decision vectors.
    workers : int
        Worker count. Values above one use a process pool.

    Returns
    -------
    list of Solution
        Solutions in input order.
    """
    if workers <= 1 or len(population) <= 1:
        return [evaluate_solution(problem, vector) for vector in population]
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
    ) as executor:
        return list(executor.map(_evaluate_pair, [(problem, vector) for vector in population]))


class PlantingAdapter:
    """Fresh Solutions adapter for one weighted scalarisation.

    Parameters
    ----------
    problem : OptimizationProblem
        Planting problem.
    weights : sequence of float
        Objective weights.
    scales : sequence of float
        Objective scales used to normalise the weighted sum.
    penalty : float
        Penalty multiplier for constraint violation.
    """

    name = "urban-forest-planting-v1"

    def __init__(
        self,
        problem: OptimizationProblem,
        weights: Sequence[float],
        scales: Sequence[float],
        penalty: float = 5.0,
    ) -> None:
        self.problem = problem
        self.weights = tuple(float(value) for value in weights)
        self.scales = tuple(max(float(value), 1e-9) for value in scales)
        self.penalty = penalty

    @property
    def variable_count(self) -> int:
        """Return the number of candidate sites.

        Returns
        -------
        int
            Site count.
        """
        return len(self.problem.sites)

    def option_count(self, variable: int) -> int:
        """Return the number of options at one site.

        Parameters
        ----------
        variable : int
            Site index.

        Returns
        -------
        int
            Number of species options plus the empty option.
        """
        if variable < 0 or variable >= self.variable_count:
            raise IndexError(variable)
        return len(self.problem.species) + 1

    def option_at(self, variable: int, option: int) -> object:
        """Return the species name or an empty string.

        Parameters
        ----------
        variable : int
            Site index.
        option : int
            Option index.

        Returns
        -------
        object
            Species name, or an empty string for no plant.
        """
        self._check_option(variable, option)
        return "" if option == 0 else self.problem.species[option - 1].name

    def initial_assignment(self) -> dict[int, int]:
        """Return the empty planting plan.

        Returns
        -------
        dict of int to int
            Every site assigned to no plant.
        """
        return dict.fromkeys(range(self.variable_count), 0)

    def random_assignment(self, rng: random.Random) -> dict[int, int]:
        """Return a random planting plan.

        Parameters
        ----------
        rng : random.Random
            Random source.

        Returns
        -------
        dict of int to int
            Random assignment.
        """
        return {
            variable: 0 if rng.random() > 0.35 else rng.randint(1, len(self.problem.species))
            for variable in range(self.variable_count)
        }

    def mutate(
        self,
        assignment: Mapping[int, int],
        rate: float,
        rng: random.Random,
    ) -> dict[int, int]:
        """Mutate a planting plan.

        Parameters
        ----------
        assignment : mapping of int to int
            Parent assignment.
        rate : float
            Per-site mutation probability.
        rng : random.Random
            Random source.

        Returns
        -------
        dict of int to int
            Mutated assignment.
        """
        values = self._assignment(assignment)
        for variable in range(self.variable_count):
            if rng.random() < rate:
                values[variable] = rng.randint(0, len(self.problem.species))
        return values

    def crossover(
        self,
        left: Mapping[int, int],
        right: Mapping[int, int],
        rng: random.Random,
    ) -> dict[int, int]:
        """Return a uniform crossover.

        Parameters
        ----------
        left : mapping of int to int
            First parent.
        right : mapping of int to int
            Second parent.
        rng : random.Random
            Random source.

        Returns
        -------
        dict of int to int
            Child assignment.
        """
        left_values = self._assignment(left)
        right_values = self._assignment(right)
        return {
            variable: left_values[variable] if rng.random() < 0.5 else right_values[variable]
            for variable in range(self.variable_count)
        }

    def evaluate(self, assignment: Mapping[int, int]) -> Evaluation:
        """Evaluate the weighted scalar objective exactly.

        Parameters
        ----------
        assignment : mapping of int to int
            Complete assignment.

        Returns
        -------
        Evaluation
            Scalar objective, feasibility, and diagnostics.
        """
        values = self._assignment(assignment)
        solution = evaluate_solution(
            self.problem, tuple(values[index] for index in range(self.variable_count))
        )
        scalar = 0.0
        for index, objective in enumerate(self.problem.objectives):
            value = solution.objectives[index] / self.scales[index]
            scalar += self.weights[index] * (-value if objective.direction == "max" else value)
        scalar += self.penalty * solution.constraint_violation
        details = dict(solution.metrics)
        details["constraint_violation"] = solution.constraint_violation
        return Evaluation(
            objective=float(scalar),
            feasible=solution.constraint_violation <= 1e-9,
            details=details,
        )

    def evaluate_batch(self, assignments: Sequence[Mapping[int, int]]) -> list[Evaluation]:
        """Evaluate a batch exactly.

        Parameters
        ----------
        assignments : sequence of mapping of int to int
            Complete assignments.

        Returns
        -------
        list of Evaluation
            Evaluations in input order.
        """
        return [self.evaluate(assignment) for assignment in assignments]

    def propose(self, assignment: Mapping[int, int], rng: random.Random) -> Change | None:
        """Propose one site/species change.

        Parameters
        ----------
        assignment : mapping of int to int
            Current assignment.
        rng : random.Random
            Random source.

        Returns
        -------
        Change or None
            The proposed change.
        """
        values = self._assignment(assignment)
        if self.variable_count == 0 or len(self.problem.species) == 0:
            return None
        variable = rng.randrange(self.variable_count)
        before = values[variable]
        choices = [option for option in range(len(self.problem.species) + 1) if option != before]
        return Change(variable=variable, before=before, after=rng.choice(choices))

    def apply(self, assignment: Mapping[int, int], change: Change) -> dict[int, int]:
        """Apply a site/species change.

        Parameters
        ----------
        assignment : mapping of int to int
            Current assignment.
        change : Change
            Change to apply.

        Returns
        -------
        dict of int to int
            Updated assignment.
        """
        values = self._assignment(assignment)
        if values[change.variable] != change.before:
            raise ValueError("change.before does not match the assignment")
        values[change.variable] = change.after
        return values

    def undo(self, assignment: Mapping[int, int], change: Change) -> dict[int, int]:
        """Reverse a site/species change.

        Parameters
        ----------
        assignment : mapping of int to int
            Current assignment.
        change : Change
            Change to reverse.

        Returns
        -------
        dict of int to int
            Restored assignment.
        """
        values = self._assignment(assignment)
        if values[change.variable] != change.after:
            raise ValueError("change.after does not match the assignment")
        values[change.variable] = change.before
        return values

    def _assignment(self, assignment: Mapping[int, int]) -> dict[int, int]:
        if set(assignment) != set(range(self.variable_count)):
            raise ValueError("assignment must cover every site")
        values = {int(key): int(value) for key, value in assignment.items()}
        for variable, option in values.items():
            self._check_option(variable, option)
        return values

    def _check_option(self, variable: int, option: int) -> None:
        if variable < 0 or variable >= self.variable_count:
            raise IndexError(variable)
        if option < 0 or option > len(self.problem.species):
            raise ValueError(f"site {variable} has an invalid option {option}")


def run_optimization(
    problem: OptimizationProblem,
    *,
    population_size: int = 24,
    generations: int = 6,
    scalarizations: int = 24,
    local_iterations: int = 200,
    workers: int = 1,
    seed: int | None = None,
    checkpoint_path: Path | None = None,
    progress: Callable[[int, int, int], None] | None = None,
    surrogate_samples: int = 0,
    trace: bool = False,
) -> OptimizationResult:
    """Solve many weighted scalarizations with Fresh Solutions and build an archive.

    Parameters
    ----------
    problem : OptimizationProblem
        Problem definition.
    population_size : int
        Fresh Solutions population size per scalarization.
    generations : int
        Fresh Solutions generations per scalarization.
    scalarizations : int
        Number of weighted scalarizations to solve.
    local_iterations : int
        Exact local-search iterations after each population search.
    workers : int
        Number of scalarizations evaluated in parallel.
    seed : int or None
        Base search seed. Defaults to the problem seed.
    checkpoint_path : Path or None
        Optional JSON checkpoint written after each completed scalarization.
    progress : callable or None
        Callback ``(scalarization, scalarizations, archive_size)``.
    surrogate_samples : int
        When positive, fit and report a screening surrogate.
    trace : bool
        Keep each scalarization's best-objective history for convergence analysis.

    Returns
    -------
    OptimizationResult
        Archive, history, and evidence.
    """
    from fresh_urban_forest.pareto import build_archive

    base_seed = problem.seed if seed is None else seed
    started = time.perf_counter()
    weights = _weight_vectors(len(problem.objectives), scalarizations, base_seed)
    scales = _objective_scales(problem)
    jobs = [
        (
            problem,
            weight,
            scales,
            population_size,
            generations,
            local_iterations,
            base_seed + index * 7919,
        )
        for index, weight in enumerate(weights)
    ]
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=multiprocessing.get_context("spawn"),
        ) as executor:
            raw_results = list(executor.map(_solve_scalarization, jobs))
    else:
        raw_results = [_solve_scalarization(job) for job in jobs]
    solutions: list[Solution] = []
    evaluations = 0
    history: list[dict[str, float]] = []
    convergence: list[tuple[float, ...]] = []
    for index, (result, assignment) in enumerate(raw_results):
        solution = evaluate_solution(problem, assignment)
        solutions.append(solution)
        evaluations += result.evaluations
        if trace:
            convergence.append(tuple(float(value) for value in result.history))
        archive = build_archive(problem, solutions)
        history.append(
            {
                "scalarization": float(index + 1),
                "archive_size": float(len(archive.solutions)),
                "hypervolume": float(archive.hypervolume),
                "evaluations": float(evaluations),
                "objective": float(result.objective),
            }
        )
        if checkpoint_path is not None:
            _write_checkpoint(checkpoint_path, problem, index + 1, assignment, result.objective)
        if progress is not None:
            progress(index + 1, len(weights), len(archive.solutions))
    archive = build_archive(problem, solutions)
    surrogate: Mapping[str, object] | None = None
    if surrogate_samples > 0:
        from fresh_urban_forest.surrogate import fit_surrogate

        surrogate = fit_surrogate(problem, samples=surrogate_samples, seed=base_seed).to_dict()
    return OptimizationResult(
        problem=problem,
        archive=archive,
        generations=generations,
        population_size=population_size,
        evaluations=evaluations,
        runtime_s=time.perf_counter() - started,
        history=tuple(history),
        seed=base_seed,
        scalarizations=len(weights),
        surrogate=surrogate,
        convergence=tuple(convergence),
        evidence=PROBLEM_EVIDENCE,
    )


def _solve_scalarization(
    job: tuple[OptimizationProblem, Sequence[float], Sequence[float], int, int, int, int],
) -> tuple[HybridResult, tuple[int, ...]]:
    """Run one Fresh Solutions scalarization in a worker."""
    problem, weights, scales, population_size, generations, local_iterations, seed = job
    adapter = PlantingAdapter(problem, weights, scales)
    result = run_hybrid_search(
        adapter,
        PopulationConfig(
            population=population_size,
            generations=generations,
            seed=seed,
            mutation_rate=0.08,
            elite_fraction=0.15,
        ),
        SearchConfig(iterations=local_iterations, seed=seed, temperature=0.5, cooling=0.995),
    )
    assignment = tuple(int(result.assignment[index]) for index in range(len(problem.sites)))
    return (result, assignment)


def _weight_vectors(count: int, requested: int, seed: int) -> tuple[tuple[float, ...], ...]:
    """Build one-hot and Dirichlet weight vectors.

    Parameters
    ----------
    count : int
        Objective count.
    requested : int
        Requested total number of scalarizations.
    seed : int
        Random seed.

    Returns
    -------
    tuple of tuple of float
        Normalised weight vectors.
    """
    total = max(1, min(500, requested))
    rng = random.Random(seed)
    vectors: list[tuple[float, ...]] = []
    for index in range(min(count, total)):
        vector = [0.0] * count
        vector[index] = 1.0
        vectors.append(tuple(vector))
    if len(vectors) < total:
        balanced = tuple(1.0 / count for _ in range(count))
        vectors.append(balanced)
    while len(vectors) < total:
        raw = [-math.log(max(rng.random(), 1e-12)) for _ in range(count)]
        denominator = sum(raw)
        vectors.append(tuple(value / denominator for value in raw))
    return tuple(vectors[:total])


def _objective_scales(problem: OptimizationProblem) -> tuple[float, ...]:
    """Return per-objective scales for the weighted sum.

    Parameters
    ----------
    problem : OptimizationProblem
        Problem definition.

    Returns
    -------
    tuple of float
        Positive scales.
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


def solution_to_edits(problem: OptimizationProblem, solution: Solution) -> tuple[ScenarioEdit, ...]:
    """Convert a solution to scenario plant edits.

    Parameters
    ----------
    problem : OptimizationProblem
        Problem definition.
    solution : Solution
        Selected solution.

    Returns
    -------
    tuple of ScenarioEdit
        Plant edits for the planted sites.
    """
    edits: list[ScenarioEdit] = []
    for index, (site, species) in enumerate(solution.planted):
        candidate = next((item for item in problem.sites if item.site_id == site), None)
        if candidate is None:
            continue
        group = species_group(species)
        edits.append(
            ScenarioEdit(
                edit_id=f"opt-{solution.solution_id[:8]}-{index + 1}",
                kind="plant",
                tree_id=f"opt:{solution.solution_id[:8]}:{index + 1}",
                lon=candidate.lon,
                lat=candidate.lat,
                species=species,
                common_name=species,
                dbh_cm=6.0,
                height_m=estimate_height_m(6.0, group),
                crown_width_m=estimate_crown_width_m(6.0, group),
                note=f"Pareto solution {solution.solution_id[:8]} at {site}",
            )
        )
    return tuple(edits)


def write_result(result: OptimizationResult, path: Path) -> Path:
    """Write an optimization result as JSON.

    Parameters
    ----------
    result : OptimizationResult
        Result to write.
    path : Path
        Destination path.

    Returns
    -------
    Path
        The written path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def result_from_dict(payload: Mapping[str, object]) -> OptimizationResult:
    """Reconstruct an optimization result from a saved JSON payload.

    Parameters
    ----------
    payload : mapping
        Mapping produced by :meth:`OptimizationResult.to_dict`.

    Returns
    -------
    OptimizationResult
        Reconstructed result.

    Raises
    ------
    ValueError
        When the payload is missing a problem or archive.
    """
    from fresh_urban_forest.pareto import archive_from_dict

    problem_payload = payload.get("problem")
    archive_payload = payload.get("archive")
    if not isinstance(problem_payload, Mapping) or not isinstance(archive_payload, Mapping):
        raise ValueError("result needs a problem and an archive")
    problem = problem_from_dict(problem_payload)
    archive = archive_from_dict(archive_payload)
    history_raw = payload.get("history", [])
    history: list[dict[str, float]] = []
    if isinstance(history_raw, list):
        for row in history_raw:
            if isinstance(row, Mapping):
                history.append({str(key): _as_float(value, 0.0) for key, value in row.items()})
    convergence_raw = payload.get("convergence", [])
    convergence: list[tuple[float, ...]] = []
    if isinstance(convergence_raw, list):
        for row in convergence_raw:
            if isinstance(row, list):
                convergence.append(tuple(_as_float(value, 0.0) for value in row))
    surrogate_raw = payload.get("surrogate")
    surrogate = (
        {str(key): value for key, value in surrogate_raw.items()}
        if isinstance(surrogate_raw, Mapping)
        else None
    )
    return OptimizationResult(
        problem=problem,
        archive=archive,
        generations=_as_int(payload.get("generations"), 0),
        population_size=_as_int(payload.get("population_size"), 0),
        evaluations=_as_int(payload.get("evaluations"), 0),
        runtime_s=_as_float(payload.get("runtime_s"), 0.0),
        history=tuple(history),
        seed=_as_int(payload.get("seed"), problem.seed),
        scalarizations=_as_int(payload.get("scalarizations"), len(archive.solutions)),
        surrogate=surrogate,
        convergence=tuple(convergence),
        evidence=PROBLEM_EVIDENCE,
    )


def problem_from_dict(payload: Mapping[str, object]) -> OptimizationProblem:
    """Build a problem from a JSON mapping.

    Parameters
    ----------
    payload : mapping
        Problem dictionary.

    Returns
    -------
    OptimizationProblem
        Reconstructed problem.

    Raises
    ------
    ValueError
        When a required field is missing or invalid.
    """
    sites_payload = payload.get("sites", [])
    species_payload = payload.get("species", [])
    objectives_payload = payload.get("objectives", [])
    if (
        not isinstance(sites_payload, list)
        or not isinstance(species_payload, list)
        or not isinstance(objectives_payload, list)
    ):
        raise ValueError("problem sites, species, and objectives must be lists")
    sites = tuple(
        CandidateSite(
            site_id=str(_mapping(item).get("site_id", "")),
            lon=_as_float(_mapping(item).get("lon"), 0.0),
            lat=_as_float(_mapping(item).get("lat"), 0.0),
            x_m=_as_float(_mapping(item).get("x_m"), 0.0),
            y_m=_as_float(_mapping(item).get("y_m"), 0.0),
            sun_fraction=_as_float(_mapping(item).get("sun_fraction"), 0.0),
            heat_weight=_as_float(_mapping(item).get("heat_weight"), 0.0),
            soil_volume_m3=_as_float(_mapping(item).get("soil_volume_m3"), 4.0),
            base_score=_as_float(_mapping(item).get("base_score"), 0.0),
        )
        for item in sites_payload
        if isinstance(item, Mapping)
    )
    species = tuple(
        SpeciesOption(
            name=str(_mapping(item).get("name", "")),
            common_name=str(_mapping(item).get("common_name", "")),
            group=str(_mapping(item).get("group", "unknown")),
            native=bool(_mapping(item).get("native", False)),
            mature_height_m=_as_float(_mapping(item).get("mature_height_m"), 0.0),
            mature_crown_width_m=_as_float(_mapping(item).get("mature_crown_width_m"), 0.0),
            shade_m2h=_as_float(_mapping(item).get("shade_m2h"), 0.0),
            carbon_kg=_as_float(_mapping(item).get("carbon_kg"), 0.0),
            water_l=_as_float(_mapping(item).get("water_l"), 0.0),
            cost_cad=_as_float(_mapping(item).get("cost_cad"), 0.0),
            habitat_value=_as_float(_mapping(item).get("habitat_value"), 0.0),
        )
        for item in species_payload
        if isinstance(item, Mapping)
    )
    objectives = tuple(
        Objective(
            name=str(_mapping(item).get("name", "")),
            label=str(_mapping(item).get("label", "")),
            direction="min" if str(_mapping(item).get("direction", "max")) == "min" else "max",
        )
        for item in objectives_payload
        if isinstance(item, Mapping)
    )
    if not sites or not species or not objectives:
        raise ValueError("problem needs sites, species, and objectives")
    return OptimizationProblem(
        problem_id=str(payload.get("problem_id", "problem")),
        dataset_id=str(payload.get("dataset_id", "unknown")),
        sites=sites,
        species=species,
        objectives=objectives,
        horizon=_as_int(payload.get("horizon"), 20),
        budget_cad=_as_float(payload.get("budget_cad"), 60_000.0),
        max_sites=_as_int(payload.get("max_sites"), len(sites)),
        max_species_share=_as_float(payload.get("max_species_share"), 0.6),
        seed=_as_int(payload.get("seed"), 42),
        evidence=PROBLEM_EVIDENCE,
    )


def _site_from_candidate(
    dataset: UrbanForestDataset,
    candidate: PlantingCandidate,
    *,
    index: int,
    period: object,
    soil_volume_m3: float,
) -> CandidateSite:
    """Build a candidate site from the planting advisor."""
    from fresh_urban_forest.terrain import project_lonlat

    x, y = project_lonlat(candidate.lon, candidate.lat, dataset.terrain.crs)
    sun_fraction = _sample_sun_fraction(dataset, period, x, y)
    return CandidateSite(
        site_id=f"site-{index + 1}",
        lon=candidate.lon,
        lat=candidate.lat,
        x_m=x,
        y_m=y,
        sun_fraction=sun_fraction,
        heat_weight=0.25 + 0.75 * sun_fraction,
        soil_volume_m3=soil_volume_m3,
        base_score=candidate.score,
    )


def _sample_sun_fraction(dataset: UrbanForestDataset, period: object, x: float, y: float) -> float:
    """Sample the sunlit fraction from a shade period."""
    from fresh_urban_forest.shade import ShadePeriod

    if not isinstance(period, ShadePeriod):
        return 0.6
    grid = dataset.terrain
    left, bottom, right, top = grid.bounds
    col = min(max(int((x - left) / max(right - left, 1e-9) * grid.width), 0), grid.width - 1)
    row = min(max(int((top - y) / max(top - bottom, 1e-9) * grid.height), 0), grid.height - 1)
    daylight = max(period.daylight_sampled_hours, 1e-9)
    return max(0.0, min(1.0, float(period.sunlit_hours[row, col]) / daylight))


def _species_option(name: str, *, horizon: int, sun_fraction: float) -> SpeciesOption:
    """Precompute a species option at the horizon."""
    profile = profile_for_species(name)
    group = profile.group
    water = simulate_water_balance(
        profile,
        crown_area_m2=max(profile.mature_crown_width_m**2 * math.pi / 4.0, 2.0),
        soil_volume_m3=4.0,
        sun_fraction=sun_fraction,
        policy="moisture_trigger",
        age_years=0.0,
    )
    response = growth_response(
        profile,
        sun_fraction=sun_fraction,
        water=water,
        soil_volume_m3=4.0,
        heat_exposure=0.4,
    )
    projection = project_species_growth(profile, response, initial_dbh_cm=6.0, years=horizon)
    final = projection.points[-1]
    crown_area = math.pi * (final.crown_width_m / 2.0) ** 2
    shade_m2h = crown_area * 0.65 * 365.0 * 12.0
    return SpeciesOption(
        name=profile.name,
        common_name=profile.common_name,
        group=group,
        native=profile.native,
        mature_height_m=final.height_m,
        mature_crown_width_m=final.crown_width_m,
        shade_m2h=shade_m2h,
        carbon_kg=carbon_kg(final.dbh_cm, group),
        water_l=water.irrigation_l,
        cost_cad=750.0 + 18.0 * horizon + water.annual_cost_cad * horizon,
        habitat_value=crown_area * final.height_m / 1000.0 * (1.2 if profile.native else 1.0),
    )


def _default_species() -> tuple[str, ...]:
    """Return the default species mix."""
    return (
        "Acer macrophyllum",
        "Thuja plicata",
        "Pseudotsuga menziesii",
        "Quercus rubra",
        "Gleditsia triacanthos",
        "Tilia cordata",
    )


def _default_objectives() -> tuple[Objective, ...]:
    """Return the default objective set."""
    return (
        Objective("shade", "Effective shade", "max"),
        Objective("equity", "Shade equity", "max"),
        Objective("native", "Native share", "max"),
        Objective("diversity", "Species diversity", "max"),
        Objective("carbon", "Carbon", "max"),
        Objective("cost", "Cost", "min"),
        Objective("water", "Irrigation water", "min"),
    )


def _constraint_violation(
    problem: OptimizationProblem,
    *,
    selected_count: int,
    cost: float,
    counts: Mapping[str, int],
) -> float:
    """Calculate a normalised constraint violation."""
    violation = 0.0
    if selected_count > problem.max_sites:
        violation += (selected_count - problem.max_sites) / max(problem.max_sites, 1)
    if cost > problem.budget_cad:
        violation += (cost - problem.budget_cad) / max(problem.budget_cad, 1.0)
    if selected_count:
        share = max(counts.values()) / selected_count
        if share > problem.max_species_share:
            violation += (share - problem.max_species_share) / max(problem.max_species_share, 1e-9)
    return float(violation)


def _shannon(counts: Mapping[str, int] | Sequence[int]) -> float:
    """Calculate Shannon diversity from species counts."""
    values = (
        [float(value) for value in counts]
        if not isinstance(counts, Mapping)
        else [float(value) for value in counts.values()]
    )
    total = sum(values)
    if total <= 0.0:
        return 0.0
    return float(-sum((value / total) * math.log(value / total) for value in values if value > 0.0))


def _solution_id(decisions: Sequence[int]) -> str:
    """Build a content hash for a decision vector."""
    payload = ",".join(str(value) for value in decisions).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:12]


def _evaluate_pair(pair: tuple[OptimizationProblem, Sequence[int]]) -> Solution:
    """Process-pool helper for exact evaluations.

    Parameters
    ----------
    pair : tuple
        Problem and decision vector.

    Returns
    -------
    Solution
        Exact evaluation.
    """
    problem, decisions = pair
    return evaluate_solution(problem, decisions)


def _write_checkpoint(
    path: Path,
    problem: OptimizationProblem,
    scalarization: int,
    assignment: Sequence[int],
    objective: float,
) -> None:
    """Write a completed scalarization checkpoint.

    Parameters
    ----------
    path : Path
        Destination path.
    problem : OptimizationProblem
        Problem definition.
    scalarization : int
        Completed scalarization index.
    assignment : sequence of int
        Best assignment.
    objective : float
        Weighted scalar objective.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "problem_id": problem.problem_id,
        "scalarization": scalarization,
        "assignment": [int(value) for value in assignment],
        "objective": objective,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _mapping(value: object) -> Mapping[str, object]:
    """Return a string-keyed mapping or raise.

    Parameters
    ----------
    value : object
        Candidate value.

    Returns
    -------
    mapping of str to object
        The value.

    Raises
    ------
    ValueError
        When the value is not a mapping.
    """
    if not isinstance(value, Mapping):
        raise ValueError("expected a mapping")
    return {str(key): item for key, item in value.items()}


def _as_float(value: object, default: float) -> float:
    """Convert a value to float with a default."""
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    return default


def _as_int(value: object, default: int) -> int:
    """Convert a value to int with a default."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default
    return default


def _slug(value: str) -> str:
    """Return a short identifier-safe slug."""
    return "".join(character if character.isalnum() else "-" for character in value.lower()).strip(
        "-"
    )
