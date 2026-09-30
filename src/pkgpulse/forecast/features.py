"""Variables du modèle global : décalages compatibles avec l'horizon, niveau récent, calendrier."""

import pandas as pd

FEATURES = [
    "level",
    "target_dow",
    *[f"lag_{k}" for k in range(7)],
    "same_day_1w",
    "same_day_2w",
    "mean_7",
    "trend",
    "last_ratio",
    "versions_7",
]
# Dynamique du dernier jour et de la dernière semaine : utile à J+1, du bruit à J+7.
SHORT_TERM = ["trend", "last_ratio"]


def build_features(series: pd.DataFrame, h: int) -> pd.DataFrame:
    """Une ligne par série et par origine t : variables connues en t, cible y(t + h).

    Les volumes sont divisés par la moyenne des 28 jours avant l'origine (scale), pour qu'un seul
    modèle apprenne sur des séries d'ordres de grandeur très différents. La cible est rapportée à
    une référence : le même jour de la semaine précédente à J+1, où le modèle corrige le naïf
    saisonnier ; la moyenne des 28 jours au-delà, plus stable qu'un seul jour (DECISIONS.md, 11).
    """
    by_series = series.groupby("unique_id", sort=False)
    y = by_series["y"]
    scale = y.transform(lambda s: s.rolling(28).mean()).clip(lower=1)
    mean_7 = y.transform(lambda s: s.rolling(7).mean())
    target_date = series["ds"] + pd.Timedelta(days=h)
    rows = pd.DataFrame(
        {
            "unique_id": series["unique_id"],
            "level": series["level"].astype("category"),
            "origin": series["ds"],
            "ds": target_date,
            "target_dow": target_date.dt.dayofweek,
            "scale": scale,
            # Même jour de la semaine que la cible, une semaine plus tôt : connu car h <= 7.
            "base": y.shift(7 - h).clip(lower=1),
        }
    )
    for k in range(7):
        rows[f"lag_{k}"] = y.shift(k) / scale
    rows["same_day_1w"] = rows["base"] / scale
    rows["same_day_2w"] = y.shift(14 - h) / scale
    rows["mean_7"] = mean_7 / scale
    rows["trend"] = mean_7 / mean_7.groupby(series["unique_id"]).shift(7)
    rows["last_ratio"] = y.shift(0) / y.shift(7).clip(
        lower=1
    )  # évolution du dernier jour sur une semaine
    rows["versions_7"] = by_series["versions_published"].transform(lambda s: s.rolling(7).sum())
    rows["reference"] = rows["base"] if h == 1 else scale
    rows["target"] = y.shift(-h) / rows["reference"]
    return rows[rows["scale"].notna()]
