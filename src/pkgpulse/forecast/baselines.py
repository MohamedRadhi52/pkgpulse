"""Références : naïf saisonnier (même jour de la semaine précédente) et ETS."""

import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import AutoETS, SeasonalNaive


def forecast_baselines(train: pd.DataFrame, horizon: int = 7) -> pd.DataFrame:
    """Prévisions de 1 à horizon jours après le dernier jour : unique_id, ds, model, y_hat."""
    models = [
        SeasonalNaive(season_length=7, alias="naif_saisonnier"),
        AutoETS(season_length=7, alias="ets"),
    ]
    wide = StatsForecast(models=models, freq="D", n_jobs=-1).forecast(
        df=train[["unique_id", "ds", "y"]], h=horizon
    )
    return wide.melt(id_vars=["unique_id", "ds"], var_name="model", value_name="y_hat")
