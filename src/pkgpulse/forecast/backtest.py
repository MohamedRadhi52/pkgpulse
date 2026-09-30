"""Backtest à origine glissante : à chaque origine, les modèles ne voient que le passé."""

from collections.abc import Callable

import pandas as pd

HORIZONS = (1, 7)
FIRST_ORIGIN = pd.Timestamp("2026-03-01")
# Premières origines, qui ont servi à choisir la forme du modèle (DECISIONS.md, décision 11).
DESIGN_ORIGINS = 6

Forecaster = Callable[[pd.DataFrame], pd.DataFrame]


def origins(series: pd.DataFrame, first: pd.Timestamp = FIRST_ORIGIN) -> pd.DatetimeIndex:
    """Une origine tous les 8 jours, pour que chaque jour de la semaine serve tour à tour
    d'origine, tant que l'horizon le plus long reste observable."""
    return pd.date_range(first, series["ds"].max() - pd.Timedelta(days=max(HORIZONS)), freq="8D")


def scales(train: pd.DataFrame) -> pd.DataFrame:
    """Par série : erreur moyenne du naïf saisonnier (dénominateur de la MASE) et niveau récent."""
    y = train.groupby("unique_id")["y"]
    return pd.DataFrame(
        {
            "mase_scale": y.apply(lambda s: s.diff(7).abs().mean()),
            "level_scale": y.apply(lambda s: s.tail(28).mean()).clip(lower=1),
        }
    ).reset_index()


def run_backtest(
    series: pd.DataFrame, origin_dates: pd.DatetimeIndex, forecasters: list[Forecaster]
) -> pd.DataFrame:
    """Prévisions de chaque modèle à chaque origine, avec la valeur réalisée et les échelles."""
    parts = []
    for origin in origin_dates:
        train = series[series["ds"] <= origin]  # coupure : rien de postérieur à l'origine
        preds = pd.concat([forecast(train) for forecast in forecasters], ignore_index=True)
        preds["h"] = (preds["ds"] - origin).dt.days
        preds = preds[preds["h"].isin(HORIZONS)].assign(origin=origin)
        parts.append(preds.merge(scales(train), on="unique_id"))
    actuals = series[["unique_id", "level", "ds", "y"]]
    results = pd.concat(parts, ignore_index=True).merge(actuals, on=["unique_id", "ds"])
    results["ase"] = (results["y"] - results["y_hat"]).abs() / results["mase_scale"]
    results["error"] = (results["y"] - results["y_hat"]).abs() / results["level_scale"]
    return results


def validation(results: pd.DataFrame) -> pd.DataFrame:
    """Résultats des seules origines de validation, jamais vues pendant la conception."""
    design = sorted(results["origin"].unique())[:DESIGN_ORIGINS]
    return results[~results["origin"].isin(design)]


def mase_table(results: pd.DataFrame) -> pd.DataFrame:
    """MASE moyenne des séries, par niveau, modèle et horizon."""
    per_series = results.groupby(["level", "model", "h", "unique_id"])["ase"].mean()
    return per_series.groupby(["level", "model", "h"]).mean().unstack("h").round(3)
