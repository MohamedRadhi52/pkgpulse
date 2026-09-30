"""Suivi MLflow : métriques du backtest et registre des modèles, avec l'alias champion."""

from pathlib import Path

import mlflow
import pandas as pd
from mlflow import MlflowClient

from pkgpulse.forecast import lgbm

EXPERIMENT = "pkgpulse"


def setup(data_dir: Path) -> None:
    mlflow.set_tracking_uri(f"sqlite:///{data_dir / 'mlflow.db'}")
    if mlflow.get_experiment_by_name(EXPERIMENT) is None:
        mlflow.create_experiment(EXPERIMENT, artifact_location=(data_dir / "mlartifacts").as_uri())
    mlflow.set_experiment(EXPERIMENT)


def model_name(h: int) -> str:
    return f"pkgpulse-lgbm-h{h}"


def record_backtest(
    mase: pd.DataFrame, params: dict, artifacts: list[Path], models: dict, champion: bool
) -> None:
    """Une exécution MLflow par backtest ; les modèles entrent au registre, champions ou non."""
    horizon_params = {
        f"h{h}_{key}": value for h, hp in lgbm.HORIZON_PARAMS.items() for key, value in hp.items()
    }
    with mlflow.start_run(run_name="backtest"):
        mlflow.log_params({**params, **lgbm.PARAMS, **horizon_params})
        for (level, model, h), value in mase.stack().items():
            mlflow.log_metric(f"mase_{model}_{level}_h{h}", value)
        for path in artifacts:
            mlflow.log_artifact(str(path))
        client = MlflowClient()
        for h, model in models.items():
            info = mlflow.lightgbm.log_model(
                model, name=f"lgbm_h{h}", registered_model_name=model_name(h)
            )
            if champion:
                client.set_registered_model_alias(
                    model_name(h), "champion", info.registered_model_version
                )


def load_models(horizons) -> dict:
    """Modèles servis : le champion, ou à défaut la dernière version enregistrée."""
    client = MlflowClient()
    models = {}
    for h in horizons:
        name = model_name(h)
        latest = max(int(v.version) for v in client.search_model_versions(f"name='{name}'"))
        version = client.get_registered_model(name).aliases.get("champion", latest)
        models[h] = mlflow.lightgbm.load_model(f"models:/{name}/{version}")
    return models
