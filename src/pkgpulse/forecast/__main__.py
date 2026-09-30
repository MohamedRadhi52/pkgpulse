"""Ligne de commande : python -m pkgpulse.forecast backtest|predict."""

import argparse
import logging

import pandas as pd

from pkgpulse.config import DATA_DIR, EXPORT_DIR
from pkgpulse.forecast import tracking
from pkgpulse.forecast.backtest import HORIZONS, mase_table, origins, run_backtest
from pkgpulse.forecast.baselines import forecast_baselines
from pkgpulse.forecast.conformal import coverage_table, quantiles
from pkgpulse.forecast.lgbm import fit_models, forecast_lgbm, predict
from pkgpulse.forecast.series import load_series

BACKTEST_PATH = DATA_DIR / "forecast" / "backtest.parquet"

log = logging.getLogger(__name__)


def backtest() -> None:
    """Backtest de tous les modèles, tableaux exportés, suivi MLflow et registre."""
    series = load_series(EXPORT_DIR)
    results = run_backtest(series, origins(series), [forecast_baselines, forecast_lgbm])
    BACKTEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.to_parquet(BACKTEST_PATH)

    mase = mase_table(results)
    tables = {
        "backtest_mase": mase.reset_index(),
        "backtest_coverage": coverage_table(results),
    }
    for name, table in tables.items():
        table.to_csv(EXPORT_DIR / f"{name}.csv", index=False)
    log.info("MASE par niveau, modèle et horizon :\n%s", mase)

    champion = beats_baselines(mase)
    log.info("Bilan backtest : LightGBM %s les références", "bat" if champion else "ne bat pas")
    tracking.setup(DATA_DIR)
    tracking.record_backtest(
        mase,
        {"origins": results["origin"].nunique(), "last_day": str(series["ds"].max().date())},
        [EXPORT_DIR / f"{name}.csv" for name in tables],
        fit_models(series),
        champion,
    )


def beats_baselines(mase: pd.DataFrame) -> bool:
    """LightGBM devient champion s'il bat les deux références, en moyenne, à chaque horizon."""
    by_model = mase.groupby(level="model").mean()
    return bool((by_model.loc["lightgbm"] < by_model.drop(index="lightgbm").min()).all())


def forecast(origin: pd.Timestamp | None) -> None:
    """Prévisions J+1 et J+7 de chaque série, avec intervalles conformels à 90 %."""
    series = load_series(EXPORT_DIR)
    tracking.setup(DATA_DIR)
    if origin is None:
        models = tracking.load_models(HORIZONS)
    else:
        # Prévision datée : modèles réentraînés sur les seules données connues à cette date.
        series = series[series["ds"] <= origin]
        models = fit_models(series)
    origin = series["ds"].max()
    preds = predict(models, series)
    preds["h"] = (preds["ds"] - origin).dt.days

    levels = series.drop_duplicates("unique_id")[["unique_id", "level"]]
    results = pd.read_parquet(BACKTEST_PATH)
    widths = quantiles(results[results["origin"] < origin]).query("model == 'lightgbm'")
    preds = preds.merge(levels, on="unique_id").merge(
        widths[["level", "h", "q"]], on=["level", "h"]
    )
    preds["lower"] = (preds["y_hat"] - preds["q"] * preds["scale"]).clip(lower=0)
    preds["upper"] = preds["y_hat"] + preds["q"] * preds["scale"]
    columns = ["unique_id", "level", "origin", "ds", "h", "y_hat", "lower", "upper"]
    preds = preds.assign(origin=origin)[columns].round(0)
    preds.to_csv(EXPORT_DIR / "forecasts.csv", index=False)
    log.info(
        "Bilan prévision : %d séries depuis le %s", preds["unique_id"].nunique(), origin.date()
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m pkgpulse.forecast")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backtest", help="backtest glissant, métriques et registre MLflow")
    predict_parser = commands.add_parser("predict", help="prévisions J+1 et J+7")
    predict_parser.add_argument("--origin", type=pd.Timestamp, help="prévoir depuis ce jour passé")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if args.command == "backtest":
        backtest()
    else:
        forecast(args.origin)


if __name__ == "__main__":
    main()
