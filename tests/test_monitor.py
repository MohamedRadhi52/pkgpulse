import pandas as pd
import pytest
from mlflow import MlflowClient

from pkgpulse.forecast import tracking
from pkgpulse.forecast.backtest import scales
from pkgpulse.forecast.lgbm import fit_models
from pkgpulse.monitor.drift import decide

# Backtest où LightGBM a une MASE de 0,8 à chaque origine : seuil de dérive de 0,8.
RESULTS = pd.DataFrame(
    {
        "model": "lightgbm",
        "level": "paquet",
        "h": 1,
        "origin": pd.date_range("2026-03-01", periods=20, freq="8D"),
        "ase": 0.8,
    }
)


@pytest.fixture(scope="module")
def mlflow_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("mlflow")


@pytest.fixture
def registry(mlflow_dir, series):
    """Registre vide à chaque test, avec un champion ; une seule base pour tout le module."""
    tracking.setup(mlflow_dir)
    client = MlflowClient()
    for model in client.search_registered_models():
        client.delete_registered_model(model.name)
    tracking.register(fit_models(series), tracking.CHAMPION)


def forecasts(series, role, relative_error, days=10):
    """Prévisions à J+1 des derniers jours, décalées d'une erreur relative donnée."""
    recent = series[series["ds"] > series["ds"].max() - pd.Timedelta(days=days)]
    recent = recent.merge(scales(series)[["unique_id", "mase_scale"]], on="unique_id")
    return recent.assign(
        role=role,
        h=1,
        origin=recent["ds"] - pd.Timedelta(days=1),
        y_hat=recent["y"] * (1 + relative_error),
    )[["unique_id", "level", "role", "origin", "ds", "h", "y_hat", "mase_scale"]]


def test_accurate_forecasts_keep_the_champion(registry, series):
    decision = decide(forecasts(series, tracking.CHAMPION, 0.01), series, RESULTS)
    assert decision.startswith("pas de dérive")
    assert not tracking.has_alias(tracking.CHALLENGER)


def test_simulated_drift_triggers_retraining(registry, series):
    decision = decide(forecasts(series, tracking.CHAMPION, 2.0), series, RESULTS)
    assert decision.startswith("dérive détectée")
    assert tracking.has_alias(tracking.CHALLENGER)


@pytest.mark.parametrize(
    ("challenger_error", "outcome"), [(0.05, "challenger promu"), (0.9, "challenger écarté")]
)
def test_challenger_is_promoted_only_if_better(registry, series, challenger_error, outcome):
    tracking.register(fit_models(series), tracking.CHALLENGER)
    history = pd.concat(
        [
            forecasts(series, tracking.CHAMPION, 0.5),
            forecasts(series, tracking.CHALLENGER, challenger_error),
        ]
    )
    assert decide(history, series, RESULTS).startswith(outcome)
    assert not tracking.has_alias(tracking.CHALLENGER)
