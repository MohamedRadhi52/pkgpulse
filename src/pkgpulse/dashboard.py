"""Données du tableau de bord (site/data.json), construites à partir des exports du pipeline."""

import json
import sys
from pathlib import Path

import pandas as pd

from pkgpulse.config import EXPORT_DIR

HISTORY_DAYS = 120


def columns(frame: pd.DataFrame) -> dict[str, list]:
    """Une liste par colonne, dates en texte et volumes entiers : un format compact pour le site."""
    frame = frame.assign(ds=frame["ds"].dt.strftime("%Y-%m-%d"))
    for name in frame.columns[frame.dtypes == "float64"]:
        frame[name] = frame[name].round().astype("int64")
    return frame.to_dict("list")


def records(path: Path) -> list[dict]:
    return json.loads(pd.read_csv(path).to_json(orient="records"))


def build(export_dir: Path) -> dict:
    """Pour chaque série : 120 jours de réalisé et de prévision rejouée à J+1, puis J+1 et J+7."""
    one_step = pd.read_csv(export_dir / "one_step.csv", parse_dates=["ds"])
    forecasts = pd.read_csv(export_dir / "forecasts.csv", parse_dates=["origin", "ds"])
    coverage = pd.read_csv(export_dir / "backtest_coverage.csv")
    lightgbm = coverage[(coverage["model"] == "lightgbm") & (coverage["h"] == 1)]

    recent = one_step[one_step["ds"] > one_step["ds"].max() - pd.Timedelta(days=HISTORY_DAYS)]
    width = recent["level"].map(lightgbm.set_index("level")["half_width"]) * recent["scale"]
    recent = recent.assign(
        lower=(recent["y_hat"] - width).clip(lower=0),
        upper=recent["y_hat"] + width,
        anomaly=recent["anomaly"].fillna(""),
    )
    history = ["ds", "y", "y_hat", "lower", "upper", "anomaly"]
    future = ["ds", "h", "y_hat", "lower", "upper"]
    return {
        "updated": forecasts["origin"].max().strftime("%Y-%m-%d"),
        "series": {
            uid: {
                "level": group["level"].iloc[0],
                "history": columns(group[history]),
                "forecast": columns(forecasts.loc[forecasts["unique_id"] == uid, future]),
            }
            for uid, group in recent.groupby("unique_id")
        },
        "backtest": records(export_dir / "backtest_mase.csv"),
        "monitoring": records(export_dir / "monitoring.csv"),
    }


if __name__ == "__main__":
    data = build(EXPORT_DIR)
    (Path(sys.argv[1]) / "data.json").write_text(json.dumps(data, ensure_ascii=False))
