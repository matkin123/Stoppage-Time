"""Statistics helpers: exact Poisson rate intervals and small bootstrap utilities."""
from __future__ import annotations

import numpy as np
from scipy import stats


def poisson_rate_ci(
    count: float, exposure: float, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Exact (Garwood) Poisson rate CI.

    rate = count / exposure (e.g. goals per live-minute). Returns (rate, lo, hi).
    Uses the chi-square relationship for the Poisson mean; exact for integer counts.
    """
    if exposure <= 0:
        return (float("nan"), float("nan"), float("nan"))
    count = float(count)
    rate = count / exposure
    if count == 0:
        lo_mean = 0.0
    else:
        lo_mean = stats.chi2.ppf(alpha / 2, 2 * count) / 2
    hi_mean = stats.chi2.ppf(1 - alpha / 2, 2 * (count + 1)) / 2
    return (rate, lo_mean / exposure, hi_mean / exposure)


def poisson_draw(lam: float, rng: np.random.Generator, size: int | None = None):
    """Poisson draw with a non-negative, finite rate guard."""
    lam = max(0.0, float(lam)) if np.isfinite(lam) else 0.0
    return rng.poisson(lam, size=size)


def bootstrap_ci(
    values: np.ndarray, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Percentile CI of an array of bootstrap replicates."""
    v = np.asarray(values, dtype=float)
    return (
        float(np.mean(v)),
        float(np.quantile(v, alpha / 2)),
        float(np.quantile(v, 1 - alpha / 2)),
    )
