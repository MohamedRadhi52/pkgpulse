import pandas as pd

from pkgpulse.forecast.hierarchy import bottom_up_table


def test_bottom_up_sums_tracked_crates_and_others():
    origin = pd.Timestamp("2026-04-10")
    results = pd.DataFrame(
        {
            "model": "m",
            "origin": origin,
            "h": 1,
            "ds": origin + pd.Timedelta(days=1),
            "level": ["total", "paquet", "paquet", "autres"],
            "y": [100.0, 30.0, 20.0, 50.0],
            "y_hat": [90.0, 30.0, 25.0, 45.0],
            "mase_scale": 10.0,
        }
    )
    assert bottom_up_table(results)[["direct", "ascendant"]].iloc[0].tolist() == [1.0, 0.0]
