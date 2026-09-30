import numpy as np
import pandas as pd

from pkgpulse.forecast.backtest import mase_table, run_backtest

ORIGIN = pd.Timestamp("2026-04-10")


def test_backtest_gives_models_nothing_after_origin(series):
    seen = []

    def spy(train):
        seen.append(train["ds"].max())
        last = train[train["ds"] == train["ds"].max()]
        return pd.concat(
            last.assign(ds=last["ds"] + pd.Timedelta(days=h), model="spy", y_hat=last["y"])
            for h in (1, 7)
        )[["unique_id", "ds", "model", "y_hat"]]

    origins = pd.DatetimeIndex([ORIGIN, ORIGIN + pd.Timedelta(days=8)])
    run_backtest(series, origins, [spy])
    assert seen == list(origins)


def test_mase_is_one_for_an_error_equal_to_the_seasonal_naive_error():
    ds = pd.date_range("2026-01-01", periods=60, freq="D")
    linear = pd.DataFrame(
        {
            "unique_id": "s",
            "level": "total",
            "ds": ds,
            "y": np.arange(60.0),
            "versions_published": 0,
        }
    )

    def off_by_seven(train):
        last = train.iloc[-1]
        return pd.DataFrame(
            {
                "unique_id": "s",
                "ds": [last["ds"] + pd.Timedelta(days=h) for h in (1, 7)],
                "model": "m",
                "y_hat": [last["y"] + h + 7 for h in (1, 7)],
            }
        )

    results = run_backtest(linear, pd.DatetimeIndex([ds[40]]), [off_by_seven])
    assert mase_table(results).loc[("total", "m")].tolist() == [1.0, 1.0]
