"""Ligne de commande : python -m pkgpulse.monitor."""

import logging

import pandas as pd

from pkgpulse.config import BACKTEST_PATH, DATA_DIR, EXPORT_DIR, HISTORY_PATH
from pkgpulse.forecast import tracking
from pkgpulse.forecast.series import load_series
from pkgpulse.monitor.drift import daily_mase, decide, realized_errors, thresholds

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    series = load_series(EXPORT_DIR)
    history = pd.read_parquet(HISTORY_PATH)
    results = pd.read_parquet(BACKTEST_PATH)
    tracking.setup(DATA_DIR)
    decision = decide(history, series, results)

    mase = daily_mase(realized_errors(history, series))
    report = mase.merge(thresholds(results).reset_index(), on=["level", "h"])
    report.round(3).to_csv(EXPORT_DIR / "monitoring.csv", index=False)
    log.info("Bilan monitoring : %s", decision)


if __name__ == "__main__":
    main()
