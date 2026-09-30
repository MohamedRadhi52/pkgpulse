import numpy as np
import pandas as pd

from pkgpulse.forecast.backtest import run_backtest
from pkgpulse.forecast.features import FEATURES, build_features
from pkgpulse.forecast.lgbm import forecast_lgbm

ORIGIN = pd.Timestamp("2026-04-10")


def poison_future(series, after):
    return series.assign(y=series["y"].where(series["ds"] <= after, 1e12))


def test_features_at_origin_ignore_later_values(series):
    clean = build_features(series, 7)
    poisoned = build_features(poison_future(series, ORIGIN), 7)
    known = clean["origin"] <= ORIGIN
    pd.testing.assert_frame_equal(clean.loc[known, FEATURES], poisoned.loc[known, FEATURES])


def test_lightgbm_forecast_is_unchanged_when_future_is_poisoned(series):
    clean = run_backtest(series, pd.DatetimeIndex([ORIGIN]), [forecast_lgbm])
    poisoned = poison_future(series, ORIGIN + pd.Timedelta(days=7))
    dirty = run_backtest(poisoned, pd.DatetimeIndex([ORIGIN]), [forecast_lgbm])
    np.testing.assert_allclose(clean["y_hat"], dirty["y_hat"])
