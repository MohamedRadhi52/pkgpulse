import pandas as pd

from pkgpulse.dashboard import build


def test_dashboard_data_combines_history_and_forecasts(tmp_path):
    pd.DataFrame(
        {
            "unique_id": "total",
            "level": "total",
            "ds": ["2026-09-28", "2026-09-29"],
            "y": [100.0, 120.0],
            "y_hat": [110.0, 118.0],
            "scale": [100.0, 100.0],
            "anomaly": [None, "pic"],
        }
    ).to_csv(tmp_path / "one_step.csv", index=False)
    pd.DataFrame(
        {
            "unique_id": "total",
            "level": "total",
            "origin": "2026-09-29",
            "ds": ["2026-09-30", "2026-10-06"],
            "h": [1, 7],
            "y_hat": [130.0, 140.0],
            "lower": [120.0, 125.0],
            "upper": [140.0, 155.0],
        }
    ).to_csv(tmp_path / "forecasts.csv", index=False)
    pd.DataFrame(
        {"level": "total", "model": "lightgbm", "h": [1], "coverage": [0.95], "half_width": [0.1]}
    ).to_csv(tmp_path / "backtest_coverage.csv", index=False)
    pd.DataFrame({"level": ["total"], "model": ["lightgbm"], "1": [0.5], "7": [0.7]}).to_csv(
        tmp_path / "backtest_mase.csv", index=False
    )
    pd.DataFrame(columns=["level", "role", "h", "ds", "mase", "mase_7d", "threshold"]).to_csv(
        tmp_path / "monitoring.csv", index=False
    )

    data = build(tmp_path)

    total = data["series"]["total"]
    assert data["updated"] == "2026-09-29"
    assert total["history"]["lower"] == [100, 108]
    assert total["history"]["anomaly"] == ["", "pic"]
    assert total["forecast"]["h"] == [1, 7]
    assert data["monitoring"] == []
