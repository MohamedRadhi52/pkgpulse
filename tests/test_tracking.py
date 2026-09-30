import mlflow

from pkgpulse.forecast import tracking
from pkgpulse.forecast.lgbm import fit_models, predict


def test_models_are_served_with_or_without_champion(tmp_path, series):
    tracking.setup(tmp_path)
    tracking.register(fit_models(series), None)
    served = predict(tracking.load_models(), series)
    assert len(served) == 2 * series["unique_id"].nunique()

    tracking.register(fit_models(series), tracking.CHAMPION)
    aliases = mlflow.MlflowClient().get_registered_model("pkgpulse-lgbm-h1").aliases
    assert aliases == {"champion": 2}
