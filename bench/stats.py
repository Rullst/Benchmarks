"""Small statistics helpers used by the harness and the aggregator."""

from __future__ import annotations

import statistics


def summary(values: list) -> dict | None:
    """Median and spread of the non-missing values."""
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    median = statistics.median(clean)
    low, high = min(clean), max(clean)
    return {
        "median": round(median, 4),
        "min": round(low, 4),
        "max": round(high, 4),
        "spread": round((high - low) / median, 4) if median else None,
        "n": len(clean),
    }


def ratio(value, baseline) -> float | None:
    if value is None or baseline in (None, 0):
        return None
    return float(value) / float(baseline)


def get_path(data: dict, path: str):
    """Read 'a.b.c' from nested dicts; None when any part is missing."""
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def window_median(samples: list[tuple[float, int]], start: float, end: float) -> float | None:
    """Median RAM of the samples between two fractions of the sampled period."""
    if not samples:
        return None
    t0, t1 = samples[0][0], samples[-1][0]
    span = (t1 - t0) or 1.0
    picked = [ram for t, ram in samples if start <= (t - t0) / span <= end]
    return statistics.median(picked) if picked else None
