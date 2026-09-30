"""Intervalles de prédiction conformels, calibrés sur les erreurs du backtest."""

import math

import numpy as np
import pandas as pd

ALPHA = 0.1  # intervalles à 90 %


def conformal_quantile(errors, alpha: float = ALPHA) -> float:
    """Quantile corrigé pour un échantillon fini : couverture moyenne d'au moins 1 - alpha."""
    errors = np.sort(np.asarray(errors, dtype=float))
    rank = math.ceil((len(errors) + 1) * (1 - alpha))
    return float(errors[min(rank, len(errors)) - 1])


def quantiles(results: pd.DataFrame, alpha: float = ALPHA) -> pd.DataFrame:
    """Demi-largeur des intervalles par niveau, modèle et horizon, en part du niveau récent."""
    grouped = results.groupby(["level", "model", "h"])["error"]
    return grouped.apply(lambda e: conformal_quantile(e, alpha)).rename("q").reset_index()


def coverage_table(results: pd.DataFrame, alpha: float = ALPHA, warmup: int = 4) -> pd.DataFrame:
    """Couverture mesurée sans fuite : à chaque origine, le quantile ne vient que du passé."""
    rows = []
    for (level, model, h), group in results.groupby(["level", "model", "h"]):
        dates = sorted(group["origin"].unique())
        for origin in dates[warmup:]:
            q = conformal_quantile(group.loc[group["origin"] < origin, "error"], alpha)
            current = group[group["origin"] == origin]
            rows.append((level, model, h, (current["error"] <= q).sum(), len(current), q))
    table = pd.DataFrame(rows, columns=["level", "model", "h", "covered", "n", "q"])
    summary = table.groupby(["level", "model", "h"]).agg(
        covered=("covered", "sum"), n=("n", "sum"), q=("q", "mean")
    )
    summary["coverage"] = (summary["covered"] / summary["n"]).round(3)
    summary["half_width"] = summary["q"].round(3)
    return summary[["coverage", "half_width"]].reset_index()
