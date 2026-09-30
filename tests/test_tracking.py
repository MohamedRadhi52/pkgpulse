import mlflow
import pandas as pd

from pkgpulse.forecast import tracking
from pkgpulse.forecast.lgbm import fit_models, predict

MASE = pd.DataFrame(
    {1: [0.9], 7: [0.8]},
    index=pd.MultiIndex.from_tuples([("total", "lightgbm")], names=["level", "model"]),
).rename_axis(columns="h")


def test_models_are_served_with_or_without_champion(tmp_path, series):
    tracking.setup(tmp_path)
    tracking.record_backtest(MASE, {}, [], fit_models(series), champion=False)
    served = predict(tracking.load_models((1, 7)), series)
    assert len(served) == 2 * series["unique_id"].nunique()

    tracking.record_backtest(MASE, {}, [], fit_models(series), champion=True)
    aliases = mlflow.MlflowClient().get_registered_model("pkgpulse-lgbm-h1").aliases
    assert aliases == {"champion": 2}
