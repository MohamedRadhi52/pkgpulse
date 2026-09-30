"""Anomalies : résidus à un jour du modèle global, notés par un score robuste."""

import numpy as np
import pandas as pd

from pkgpulse.forecast.features import FEATURES, build_features
from pkgpulse.forecast.lgbm import fit_models

THRESHOLD = 4.0  # en écarts robustes
WINDOW = 56  # jours de résidus passés servant de référence


def one_step_residuals(series: pd.DataFrame, origin_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Résidus relatifs à J+1 : modèle réentraîné chaque semaine, prévision chaque jour.

    Les variables d'une origine n'utilisent que les données jusqu'à cette origine, et chaque
    modèle ne voit que les cibles antérieures à sa semaine : aucune fuite.
    """
    rows = build_features(series, 1)
    rows = rows[rows["target"].notna()]
    ends = [*origin_dates[1:], series["ds"].max()]
    parts = []
    for start, end in zip(origin_dates, ends, strict=True):
        model = fit_models(series[series["ds"] <= start], horizons=(1,))[1]
        week = rows[(rows["origin"] >= start) & (rows["origin"] < end)]
        parts.append(week.assign(residual=week["target"] - model.predict(week[FEATURES])))
    return pd.concat(parts, ignore_index=True)[["unique_id", "level", "ds", "residual"]]


def robust_scores(residuals: pd.DataFrame) -> pd.DataFrame:
    """Score de chaque résidu par rapport aux 56 jours précédents (médiane et MAD)."""

    def score(r: pd.Series) -> pd.Series:
        past = r.shift(1).rolling(WINDOW, min_periods=28)
        median = past.median()
        mad = past.apply(lambda w: np.median(np.abs(w - np.median(w))), raw=True)
        return (r - median) / (1.4826 * mad)

    scored = residuals.sort_values(["unique_id", "ds"]).copy()
    scored["score"] = scored.groupby("unique_id")["residual"].transform(score)
    scored["anomaly"] = np.select(
        [scored["score"] > THRESHOLD, scored["score"] < -THRESHOLD], ["pic", "creux"], ""
    )
    return scored
