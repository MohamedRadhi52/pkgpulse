"""Suivi MLflow : métriques du backtest et registre des modèles, champion et challenger."""

from pathlib import Path

import mlflow
import pandas as pd
from mlflow import MlflowClient

from pkgpulse.forecast import lgbm
from pkgpulse.forecast.backtest import HORIZONS

EXPERIMENT = "pkgpulse"
CHAMPION = "champion"
CHALLENGER = "challenger"


def setup(data_dir: Path) -> None:
    mlflow.set_tracking_uri(f"sqlite:///{data_dir / 'mlflow.db'}")
    if mlflow.get_experiment_by_name(EXPERIMENT) is None:
        mlflow.create_experiment(EXPERIMENT, artifact_location=(data_dir / "mlartifacts").as_uri())
    mlflow.set_experiment(EXPERIMENT)


def model_name(h: int) -> str:
    return f"pkgpulse-lgbm-h{h}"


def record_backtest(mase: pd.DataFrame, params: dict, artifacts: list[Path]) -> None:
    """Une exécution MLflow par backtest : paramètres, MASE par niveau, modèle et horizon."""
    horizon_params = {
        f"h{h}_{key}": value for h, hp in lgbm.HORIZON_PARAMS.items() for key, value in hp.items()
    }
    with mlflow.start_run(run_name="backtest"):
        mlflow.log_params({**params, **lgbm.PARAMS, **horizon_params})
        for (level, model, h), value in mase.stack().items():
            mlflow.log_metric(f"mase_{model}_{level}_h{h}", value)
        for path in artifacts:
            mlflow.log_artifact(str(path))


def register(models: dict, alias: str | None) -> None:
    """Enregistre un modèle par horizon, avec l'alias demandé."""
    client = MlflowClient()
    with mlflow.start_run(run_name=f"modèle {alias or 'sans alias'}"):
        for h, model in models.items():
            info = mlflow.lightgbm.log_model(
                model, name=f"lgbm_h{h}", registered_model_name=model_name(h)
            )
            if alias:
                client.set_registered_model_alias(
                    model_name(h), alias, info.registered_model_version
                )


def has_alias(alias: str) -> bool:
    found = MlflowClient().search_registered_models(f"name = '{model_name(HORIZONS[0])}'")
    return bool(found) and alias in found[0].aliases


def load_models(alias: str = CHAMPION) -> dict:
    """Modèles d'un alias ; tant qu'aucun champion n'est désigné, la dernière version."""
    client = MlflowClient()
    models = {}
    for h in HORIZONS:
        name = model_name(h)
        latest = max(int(v.version) for v in client.search_model_versions(f"name='{name}'"))
        version = client.get_registered_model(name).aliases.get(alias, latest)
        models[h] = mlflow.lightgbm.load_model(f"models:/{name}/{version}")
    return models


def promote_challenger() -> None:
    client = MlflowClient()
    for h in HORIZONS:
        name = model_name(h)
        version = client.get_registered_model(name).aliases[CHALLENGER]
        client.set_registered_model_alias(name, CHAMPION, version)
        client.delete_registered_model_alias(name, CHALLENGER)


def drop_challenger() -> None:
    client = MlflowClient()
    for h in HORIZONS:
        client.delete_registered_model_alias(model_name(h), CHALLENGER)
