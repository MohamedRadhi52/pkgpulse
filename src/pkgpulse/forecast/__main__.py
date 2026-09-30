"""Ligne de commande : python -m pkgpulse.forecast backtest."""

import argparse
import logging

from pkgpulse.config import DATA_DIR, EXPORT_DIR
from pkgpulse.forecast.backtest import mase_table, origins, run_backtest
from pkgpulse.forecast.baselines import forecast_baselines
from pkgpulse.forecast.series import load_series

BACKTEST_PATH = DATA_DIR / "forecast" / "backtest.parquet"

log = logging.getLogger(__name__)


def backtest() -> None:
    """Backtest des références, résultats détaillés et tableau de MASE exporté."""
    series = load_series(EXPORT_DIR)
    results = run_backtest(series, origins(series), [forecast_baselines])
    BACKTEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.to_parquet(BACKTEST_PATH)
    mase = mase_table(results)
    mase.reset_index().to_csv(EXPORT_DIR / "backtest_mase.csv", index=False)
    log.info("MASE par niveau, modèle et horizon :\n%s", mase)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m pkgpulse.forecast")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backtest", help="backtest glissant et MASE par niveau")
    parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    backtest()


if __name__ == "__main__":
    main()
