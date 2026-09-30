"""Erreurs réalisées, MASE glissante et règle champion contre challenger (DECISIONS.md, 17)."""

import pandas as pd

from pkgpulse.forecast import tracking
from pkgpulse.forecast.lgbm import fit_models

WINDOW_DAYS = 7
DECISION_LEVEL = "paquet"  # 200 séries : le signal le plus stable


def realized_errors(history: pd.DataFrame, series: pd.DataFrame) -> pd.DataFrame:
    """Chaque prévision passée dont la valeur est connue, avec son erreur rapportée à la MASE."""
    errors = history.merge(series[["unique_id", "ds", "y"]], on=["unique_id", "ds"])
    return errors.assign(ase=(errors["y"] - errors["y_hat"]).abs() / errors["mase_scale"])


def daily_mase(errors: pd.DataFrame) -> pd.DataFrame:
    """MASE par jour cible, niveau, rôle et horizon, et sa moyenne glissante sur 7 jours."""
    keys = ["level", "role", "h"]
    daily = errors.groupby([*keys, "ds"])["ase"].mean().reset_index(name="mase")
    rolling = daily.groupby(keys)["mase"].rolling(WINDOW_DAYS, min_periods=WINDOW_DAYS).mean()
    return daily.assign(mase_7d=rolling.reset_index(level=keys, drop=True))


def thresholds(results: pd.DataFrame) -> pd.Series:
    """Seuil de dérive par niveau et horizon : MASE des 5 % pires origines du backtest."""
    per_origin = results[results["model"] == "lightgbm"].groupby(["level", "h", "origin"])["ase"]
    return per_origin.mean().groupby(["level", "h"]).quantile(0.95).rename("threshold")


def decide(history: pd.DataFrame, series: pd.DataFrame, results: pd.DataFrame) -> str:
    """Applique la règle du jour et décrit la décision prise."""
    errors = realized_errors(history, series)
    if tracking.has_alias(tracking.CHALLENGER):
        return compare_challenger(errors)
    mase = daily_mase(errors)
    watched = mase[
        (mase["level"] == DECISION_LEVEL) & (mase["role"] == tracking.CHAMPION) & (mase["h"] == 1)
    ]["mase_7d"].dropna()
    limit = thresholds(results)[(DECISION_LEVEL, 1)]
    if watched.empty:
        return f"moins de {WINDOW_DAYS} jours d'erreurs réalisées, seuil de {limit:.2f}"
    current = f"MASE sur 7 jours de {watched.iloc[-1]:.2f} pour un seuil de {limit:.2f}"
    if watched.iloc[-1] <= limit:
        return f"pas de dérive, {current}"
    tracking.register(fit_models(series), tracking.CHALLENGER)
    return f"dérive détectée, {current} : challenger entraîné"


def compare_challenger(errors: pd.DataFrame) -> str:
    """Après 7 jours, promeut le challenger s'il bat le champion sur les mêmes jours et séries."""
    watched = errors[(errors["level"] == DECISION_LEVEL) & (errors["h"] == 1)]
    days = watched.loc[watched["role"] == tracking.CHALLENGER, "ds"].unique()
    if len(days) < WINDOW_DAYS:
        return f"challenger en observation, {len(days)} jours sur {WINDOW_DAYS}"
    mase = watched[watched["ds"].isin(days)].groupby("role")["ase"].mean()
    duel = f"MASE de {mase[tracking.CHALLENGER]:.3f} contre {mase[tracking.CHAMPION]:.3f}"
    if mase[tracking.CHALLENGER] < mase[tracking.CHAMPION]:
        tracking.promote_challenger()
        return f"challenger promu champion, {duel}"
    tracking.drop_challenger()
    return f"challenger écarté, {duel}"
