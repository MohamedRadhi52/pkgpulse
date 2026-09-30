"""Modèle global LightGBM : un modèle par horizon, appris sur toutes les séries à la fois."""

import lightgbm as lgb
import pandas as pd

from pkgpulse.forecast.backtest import HORIZONS
from pkgpulse.forecast.features import FEATURES, SHORT_TERM, build_features

PARAMS = {"objective": "l1", "learning_rate": 0.05, "verbose": -1}
# Réglages par horizon, choisis sur les six premières origines du backtest (DECISIONS.md, 11).
HORIZON_PARAMS = {
    1: {"n_estimators": 200, "num_leaves": 15, "min_child_samples": 200},
    7: {"n_estimators": 300, "num_leaves": 31, "min_child_samples": 50},
}


def features_for(h: int) -> list[str]:
    return FEATURES if h == 1 else [name for name in FEATURES if name not in SHORT_TERM]


def fit_models(train: pd.DataFrame, horizons=HORIZONS) -> dict[int, lgb.LGBMRegressor]:
    """Un modèle par horizon, appris sur les couples (origine, cible) dont la cible est connue."""
    models = {}
    for h in horizons:
        rows = build_features(train, h)
        known = rows[rows["target"].notna()]
        model = lgb.LGBMRegressor(**PARAMS, **HORIZON_PARAMS[h])
        models[h] = model.fit(known[features_for(h)], known["target"])
    return models


def predict(models: dict[int, lgb.LGBMRegressor], train: pd.DataFrame) -> pd.DataFrame:
    """Prévisions depuis le dernier jour de train : unique_id, ds, model, y_hat, scale."""
    origin = train["ds"].max()
    parts = []
    for h, model in models.items():
        rows = build_features(train, h)
        last = rows[rows["origin"] == origin]
        parts.append(
            last.assign(
                model="lightgbm", y_hat=model.predict(last[features_for(h)]) * last["reference"]
            )
        )
    return pd.concat(parts, ignore_index=True)[["unique_id", "ds", "model", "y_hat", "scale"]]


def forecast_lgbm(train: pd.DataFrame) -> pd.DataFrame:
    return predict(fit_models(train), train).drop(columns="scale")
