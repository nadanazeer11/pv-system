"""Monte Carlo uncertainty engine for PV financial outcomes.

This module is the kernel behind Contribution C of the thesis. It draws
``n_simulations`` independent samples for each uncertain parameter,
evaluates the same year-by-year cash-flow chain as the deterministic
:mod:`financial_basic` service, and returns the *distribution* of the
headline metrics (payback, NPV, LCOE, lifetime savings) rather than a
single point estimate.

Methodological notes
--------------------
* **Why parametric distributions, not bootstrap?** A homeowner deciding
  on PV at *t = 0* has no historical sample of *their own* future
  panel performance — only published priors on degradation, on tariff
  policy, on weather. The right uncertainty model is therefore
  parametric, with priors anchored in the literature (PLAN.md
  references EgyptERA, NREL, IRENA, IEA-PVPS).

* **Why one inverter replacement event, not zero or two?** Modern
  string inverters in Egypt's climate carry 10–12 year warranties and
  see a typical 12–15 year service life (IEA-PVPS T13). A 25-year
  analysis horizon therefore captures one replacement; modelling two
  would over-attribute uncertainty to the inverter alone and is left
  for sensitivity analysis (Day 18).

* **Why per-year, per-simulation yield noise?** Annual irradiance in
  Egypt varies ~±5 % around the TMY mean (Egyptian PV field studies),
  and that variability *does not* average out over the analysis
  horizon for the *payback* metric — early bad years push payback
  later in nonlinear ways. The kernel therefore samples a fresh yield
  factor for each (simulation, year) pair, giving a (N, T) matrix.

* **Why vectorised numpy and not a Python loop?** 1 000 simulations
  × 25 years × 7 distributions is ~175 k samples; vectorising the cash
  flow algebra collapses the run-time below 100 ms on a laptop, which
  matters because the Day 14 dashboard re-runs the engine on every
  user input change.

* **Reproducibility.** Every call accepts a ``random_seed`` that is
  threaded into a NumPy ``Generator``. The test suite relies on this
  for byte-identical re-runs; the API exposes it so a thesis reviewer
  can reproduce any reported figure.

References
----------
* Jordan & Kurtz, NREL (2013): photovoltaic degradation rates — an
  analytical review. ``Prog. Photovolt.``
* IRENA (2023): Renewable Power Generation Costs.
* IEA-PVPS Task 13 (2021): Service Life of PV Inverters.
* EgyptERA published residential schedule (2023).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.config import settings
from app.schemas.monte_carlo import (
    CumulativeCashFlowTrajectory,
    Distribution,
    HistogramBins,
    MonteCarloPercentiles,
    MonteCarloRequest,
    MonteCarloResult,
)


class MonteCarloError(ValueError):
    """Raised when Monte Carlo inputs are invalid for the kernel itself.

    Most validation happens at the Pydantic layer; this error is
    reserved for invariants the schema cannot express, such as a
    triangular ``low > high`` introduced via a settings reload that
    bypassed schema validation.
    """


_PERCENTILES = np.array([5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0])


# ──────────────────────────── Defaults ──────────────────────────────


def _default_distribution(
    kind: str,
    *,
    triangular: tuple[float, float, float] | None = None,
    normal: tuple[float, float] | None = None,
    clip: tuple[float | None, float | None] = (None, None),
) -> Distribution:
    """Construct a ``Distribution`` from a config 3-tuple or 2-tuple.

    Centralised here so every default flows through the same Pydantic
    validation as user-supplied overrides, and so a config typo (e.g.
    ``low > high``) is surfaced loudly at engine import time rather
    than silently corrupting a simulation.
    """
    if kind == "triangular":
        assert triangular is not None
        low, mode, high = triangular
        return Distribution(
            kind="triangular",
            low=low,
            mode=mode,
            high=high,
            clip_min=clip[0],
            clip_max=clip[1],
        )
    if kind == "normal":
        assert normal is not None
        mean, std = normal
        return Distribution(
            kind="normal",
            mean=mean,
            std=std,
            clip_min=clip[0],
            clip_max=clip[1],
        )
    raise MonteCarloError(f"unsupported default distribution kind: {kind}")


def _resolve_distribution(
    override: Distribution | None, default: Distribution
) -> Distribution:
    """Caller override beats the configured default."""
    return override if override is not None else default


def _default_distributions() -> dict[str, Distribution]:
    """Build the Egypt-tuned default distribution set from settings.

    Materialised on each call so a settings reload (for example, an
    environment-variable flip in tests) is honoured immediately, the
    same way :func:`tiered_tariff._resolve_tiers` re-reads its tier
    schedule.
    """
    return {
        "degradation_rate": _default_distribution(
            "triangular",
            triangular=settings.monte_carlo_degradation_triangular,
            clip=(0.0, None),
        ),
        "tariff_inflation_rate": _default_distribution(
            "normal",
            normal=settings.monte_carlo_tariff_inflation_normal,
            clip=(0.0, None),
        ),
        "om_cost_fraction": _default_distribution(
            "triangular",
            triangular=settings.monte_carlo_om_fraction_triangular,
            clip=(0.0, None),
        ),
        "cost_egp_per_kw": _default_distribution(
            "triangular",
            triangular=settings.monte_carlo_cost_per_kw_triangular,
            clip=(0.0, None),
        ),
        "annual_yield_factor": _default_distribution(
            "normal",
            normal=settings.monte_carlo_yield_factor_normal,
            clip=settings.monte_carlo_yield_factor_clip,
        ),
        "inverter_replacement_year": _default_distribution(
            "triangular",
            triangular=settings.monte_carlo_inverter_year_triangular,
            clip=(1.0, None),
        ),
        "inverter_replacement_cost_fraction": _default_distribution(
            "triangular",
            triangular=settings.monte_carlo_inverter_cost_fraction_triangular,
            clip=(0.0, None),
        ),
    }


# ──────────────────────────── Sampling ──────────────────────────────


def _sample(
    dist: Distribution, rng: np.random.Generator, shape: int | tuple[int, ...]
) -> np.ndarray:
    """Draw ``shape`` samples from ``dist`` using ``rng``.

    Clipping is applied as a last step; for the normal family, this is
    the *truncation by clipping* approach (a draw outside the bounds is
    mapped to the bound, not re-drawn). That biases the tails toward
    the bounds, but for the small fraction of out-of-bound draws we
    expect (≪ 1 % at the configured σ) the bias is negligible compared
    with the underlying parameter uncertainty.
    """
    if dist.kind == "normal":
        if dist.mean is None or dist.std is None:
            raise MonteCarloError("normal distribution missing mean or std")
        if dist.std == 0:
            samples = np.full(shape, float(dist.mean))
        else:
            samples = rng.normal(loc=dist.mean, scale=dist.std, size=shape)
    elif dist.kind == "triangular":
        if dist.low is None or dist.mode is None or dist.high is None:
            raise MonteCarloError("triangular distribution missing low/mode/high")
        if dist.low == dist.high:
            samples = np.full(shape, float(dist.mode))
        else:
            samples = rng.triangular(
                left=dist.low, mode=dist.mode, right=dist.high, size=shape
            )
    else:  # pragma: no cover - schema rejects unknown kinds upstream
        raise MonteCarloError(f"unsupported distribution kind: {dist.kind}")

    if dist.clip_min is not None or dist.clip_max is not None:
        lo = -np.inf if dist.clip_min is None else dist.clip_min
        hi = np.inf if dist.clip_max is None else dist.clip_max
        samples = np.clip(samples, lo, hi)
    return samples


# ───────────────────────── Core simulation ─────────────────────────


@dataclass(frozen=True)
class _SimulationArrays:
    """Vectorised simulation outputs.

    Internal dataclass exposed only to the test suite for white-box
    assertions (e.g. monotonicity of cumulative cash flow inside a
    single simulation).
    """

    payback_years: np.ndarray  # (N,) — np.inf when project never recovers
    npv_egp: np.ndarray  # (N,)
    lcoe_egp_per_kwh: np.ndarray  # (N,)
    lifetime_savings_egp: np.ndarray  # (N,)
    paid_back_mask: np.ndarray  # (N,) bool
    capex_samples: np.ndarray  # (N,) — for diagnostics
    cumulative_discounted: np.ndarray  # (N, T+1) — fan-chart input


def _simulate(
    request: MonteCarloRequest,
    analysis_years: int,
    discount_rate: float,
    rng: np.random.Generator,
) -> _SimulationArrays:
    """Run the vectorised cash-flow simulation for all draws at once.

    The matrix algebra exactly mirrors the year-by-year loop in
    :func:`financial_basic.compute_financials`, so the deterministic
    test ``Monte Carlo with σ = 0 ≡ flat-tariff financial_basic`` holds
    by construction. Vectorising along the simulation axis is what
    makes 1 000 draws feasible inside an interactive request.
    """
    n = request.n_simulations
    t = analysis_years
    years = np.arange(1, t + 1)
    sim_idx = np.arange(n)
    defaults = _default_distributions()

    deg_dist = _resolve_distribution(
        request.degradation_rate_dist, defaults["degradation_rate"]
    )
    infl_dist = _resolve_distribution(
        request.tariff_inflation_rate_dist, defaults["tariff_inflation_rate"]
    )
    om_dist = _resolve_distribution(
        request.om_cost_fraction_dist, defaults["om_cost_fraction"]
    )
    cost_dist = _resolve_distribution(
        request.cost_egp_per_kw_dist, defaults["cost_egp_per_kw"]
    )
    yield_dist = _resolve_distribution(
        request.annual_yield_factor_dist, defaults["annual_yield_factor"]
    )
    inv_year_dist = _resolve_distribution(
        request.inverter_replacement_year_dist, defaults["inverter_replacement_year"]
    )
    inv_cost_dist = _resolve_distribution(
        request.inverter_replacement_cost_fraction_dist,
        defaults["inverter_replacement_cost_fraction"],
    )

    # Per-simulation scalar draws (N,)
    degradation = _sample(deg_dist, rng, n)
    tariff_inflation = _sample(infl_dist, rng, n)
    om_fraction = _sample(om_dist, rng, n)
    cost_per_kw = _sample(cost_dist, rng, n)
    inv_year_raw = _sample(inv_year_dist, rng, n)
    inv_cost_fraction = _sample(inv_cost_dist, rng, n)

    # Per-(simulation, year) yield draws (N, T)
    yield_factors = _sample(yield_dist, rng, (n, t))

    # Capex and constant annual O&M per simulation (N,)
    capex = request.system_kw * cost_per_kw
    annual_om = capex * om_fraction

    # Year-by-year matrices (N, T).
    deg_mat = (1.0 - degradation[:, None]) ** (years[None, :] - 1)
    infl_mat = (1.0 + tariff_inflation[:, None]) ** (years[None, :] - 1)
    gen_mat = request.annual_kwh * deg_mat * yield_factors
    tariff_mat = request.tariff_egp_per_kwh * infl_mat
    savings_mat = gen_mat * tariff_mat
    net_mat = savings_mat - annual_om[:, None]

    # Inverter replacement: round to nearest integer year, clip into
    # [1, T], then subtract the cost from that year's net cash flow for
    # each simulation.
    inv_year_int = np.clip(np.rint(inv_year_raw).astype(int), 1, t)
    inv_cost = capex * inv_cost_fraction
    net_mat[sim_idx, inv_year_int - 1] -= inv_cost

    # Discount factors (T,) and discounted net cash flow (N, T)
    discount_factors = (1.0 + discount_rate) ** years
    discounted_net = net_mat / discount_factors[None, :]
    npv = -capex + np.sum(discounted_net, axis=1)

    # LCOE: capex (year-0) + discounted O&M + discounted inverter cost
    # divided by discounted lifetime generation.
    discounted_gen = np.sum(gen_mat / discount_factors[None, :], axis=1)
    discounted_om = np.sum(
        annual_om[:, None] / discount_factors[None, :], axis=1
    )
    discounted_inv_cost = inv_cost / (1.0 + discount_rate) ** inv_year_int
    # Guard against the degenerate zero-generation case (yield clip 0
    # plus full degradation) so the array stays float-clean.
    safe_gen = np.where(discounted_gen > 0, discounted_gen, np.nan)
    lcoe = (capex + discounted_om + discounted_inv_cost) / safe_gen

    lifetime_savings = np.sum(savings_mat, axis=1)

    payback_years, paid_back_mask, cumulative_discounted = (
        _vectorised_discounted_payback(
            capex=capex,
            discounted_net=discounted_net,
            analysis_years=t,
        )
    )

    return _SimulationArrays(
        payback_years=payback_years,
        npv_egp=npv,
        lcoe_egp_per_kwh=lcoe,
        lifetime_savings_egp=lifetime_savings,
        paid_back_mask=paid_back_mask,
        capex_samples=capex,
        cumulative_discounted=cumulative_discounted,
    )


def _vectorised_discounted_payback(
    *, capex: np.ndarray, discounted_net: np.ndarray, analysis_years: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised linear-interpolated discounted payback.

    Builds the ``(N, T+1)`` discounted cumulative cash-flow matrix
    starting at ``-capex`` in year 0, finds the first non-negative
    column for each row, and linearly interpolates across the year of
    the sign flip — exactly the same convention as
    :func:`financial_basic._interpolated_payback`. Simulations that
    never reach break-even within the horizon are flagged in
    ``paid_back_mask`` and emit ``np.inf`` so downstream percentile
    aggregation can filter them out cleanly. The cumulative matrix is
    returned alongside so the Day-16 fan chart can derive percentile
    bands without re-running the algebra.
    """
    n = discounted_net.shape[0]
    cum = np.empty((n, analysis_years + 1))
    cum[:, 0] = -capex
    cum[:, 1:] = -capex[:, None] + np.cumsum(discounted_net, axis=1)

    positive = cum[:, 1:] >= 0  # (N, T)
    paid_back = positive.any(axis=1)
    # ``argmax`` on a boolean row returns the first ``True``; rows with
    # no ``True`` return 0, which is meaningless — masked out below.
    first_pos_idx = positive.argmax(axis=1)  # (N,)
    year_of_first_pos = first_pos_idx + 1  # 1..T

    sim_idx = np.arange(n)
    prev_year_cum = cum[sim_idx, year_of_first_pos - 1]
    this_year_cum = cum[sim_idx, year_of_first_pos]
    denom = this_year_cum - prev_year_cum
    safe_denom = np.where(denom != 0, denom, 1.0)
    fraction = np.where(denom != 0, -prev_year_cum / safe_denom, 0.0)
    payback = (year_of_first_pos - 1) + fraction
    payback = np.where(paid_back, payback, np.inf)
    return payback, paid_back, cum


def _trajectory_from_cumulative(
    cumulative: np.ndarray,
) -> CumulativeCashFlowTrajectory:
    """Aggregate a ``(N, T+1)`` cumulative-cash-flow matrix into a
    percentile-band trajectory.

    Percentiles are taken column-wise — at each year independently —
    so the resulting bands are *envelope* percentiles, not the
    trajectory of any single simulation. This is the correct framing
    for an uncertainty fan chart: the user sees, at each year, where
    the middle 50 / 90 % of futures lie, regardless of which futures
    they are. Mixing simulation identity across years would imply a
    causal coupling the model does not posit.
    """
    n_years_plus_one = cumulative.shape[1]
    pcts = np.percentile(cumulative, [5.0, 25.0, 50.0, 75.0, 95.0], axis=0)
    mean_traj = np.mean(cumulative, axis=0)
    return CumulativeCashFlowTrajectory(
        year_index=list(range(n_years_plus_one)),
        p05=pcts[0].tolist(),
        p25=pcts[1].tolist(),
        p50=pcts[2].tolist(),
        p75=pcts[3].tolist(),
        p95=pcts[4].tolist(),
        mean=mean_traj.tolist(),
    )


# ───────────────────── Aggregation / output mapping ─────────────────


def _percentiles_from_array(
    values: np.ndarray, *, exclude_inf: bool = False
) -> MonteCarloPercentiles:
    """Build a percentile summary, optionally dropping ``np.inf`` rows.

    ``exclude_inf`` is set for the payback metric so that simulations
    that fail to break even within the horizon do not contaminate the
    percentile band. The fraction of such runs is reported separately
    via :pyattr:`MonteCarloResult.payback_probability`.
    """
    finite = values[np.isfinite(values)] if exclude_inf else values
    if finite.size == 0:
        return MonteCarloPercentiles(
            mean=float("nan"),
            std=0.0,
            p05=float("nan"),
            p10=float("nan"),
            p25=float("nan"),
            p50=float("nan"),
            p75=float("nan"),
            p90=float("nan"),
            p95=float("nan"),
            minimum=float("nan"),
            maximum=float("nan"),
        )
    pcts = np.percentile(finite, _PERCENTILES)
    return MonteCarloPercentiles(
        mean=float(np.mean(finite)),
        std=float(np.std(finite, ddof=0)),
        p05=float(pcts[0]),
        p10=float(pcts[1]),
        p25=float(pcts[2]),
        p50=float(pcts[3]),
        p75=float(pcts[4]),
        p90=float(pcts[5]),
        p95=float(pcts[6]),
        minimum=float(np.min(finite)),
        maximum=float(np.max(finite)),
    )


def _histogram(
    values: np.ndarray, *, bins: int = 30, exclude_inf: bool = False
) -> HistogramBins:
    """Build a frequency histogram in the format the dashboard expects."""
    finite = values[np.isfinite(values)] if exclude_inf else values
    if finite.size == 0:
        return HistogramBins(bin_edges=[0.0, 0.0], counts=[0])
    if np.allclose(finite, finite[0]):
        # All draws collapsed to a single value (e.g. zero variance).
        # ``np.histogram`` would create a zero-width bin and crash on
        # downstream chart libraries; emit a synthetic ε-wide bin.
        v = float(finite[0])
        eps = max(abs(v), 1.0) * 1e-6
        return HistogramBins(bin_edges=[v - eps, v + eps], counts=[int(finite.size)])
    counts, edges = np.histogram(finite, bins=bins)
    return HistogramBins(bin_edges=edges.tolist(), counts=counts.astype(int).tolist())


# ─────────────────────────── Public API ─────────────────────────────


def run_monte_carlo(request: MonteCarloRequest) -> MonteCarloResult:
    """Execute the Monte Carlo simulation and return the summary.

    Returns a :class:`MonteCarloResult` with percentile bands for each
    headline metric, the payback / positive-NPV probabilities, and
    histograms ready for the dashboard.

    Raises
    ------
    MonteCarloError
        Only for invariants the Pydantic layer cannot enforce — most
        misuse fails at request validation.
    """
    analysis_years = (
        request.analysis_period_years
        if request.analysis_period_years is not None
        else settings.analysis_period_years
    )
    discount_rate = (
        request.discount_rate
        if request.discount_rate is not None
        else settings.discount_rate
    )
    if analysis_years < 1:
        raise MonteCarloError("analysis_period_years must be at least 1")

    rng = np.random.default_rng(request.random_seed)
    sim = _simulate(
        request=request,
        analysis_years=analysis_years,
        discount_rate=discount_rate,
        rng=rng,
    )

    n = request.n_simulations
    payback_prob = float(np.mean(sim.paid_back_mask))
    npv_prob = float(np.mean(sim.npv_egp > 0))

    return MonteCarloResult(
        n_simulations=n,
        payback_years=_percentiles_from_array(
            sim.payback_years, exclude_inf=True
        ),
        npv_egp=_percentiles_from_array(sim.npv_egp),
        lcoe_egp_per_kwh=_percentiles_from_array(sim.lcoe_egp_per_kwh),
        lifetime_savings_egp=_percentiles_from_array(sim.lifetime_savings_egp),
        payback_probability=payback_prob,
        positive_npv_probability=npv_prob,
        payback_histogram=_histogram(sim.payback_years, exclude_inf=True),
        npv_histogram=_histogram(sim.npv_egp),
        cumulative_cash_flow_trajectory=_trajectory_from_cumulative(
            sim.cumulative_discounted
        ),
        system_kw=request.system_kw,
        annual_kwh=request.annual_kwh,
        tariff_egp_per_kwh=request.tariff_egp_per_kwh,
        analysis_period_years=analysis_years,
        discount_rate=discount_rate,
        random_seed=request.random_seed,
    )
