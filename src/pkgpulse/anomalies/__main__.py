"""Ligne de commande : python -m pkgpulse.anomalies."""

import logging

from pkgpulse.anomalies.detect import one_step_residuals, robust_scores
from pkgpulse.config import EXPORT_DIR
from pkgpulse.forecast.backtest import origins
from pkgpulse.forecast.series import load_series

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    series = load_series(EXPORT_DIR)
    scored = robust_scores(one_step_residuals(series, origins(series)))
    flagged = scored[scored["anomaly"] != ""]
    flagged.round(3).to_csv(EXPORT_DIR / "anomalies.csv", index=False)
    log.info("Bilan anomalies : %d jours signalés sur %d résidus", len(flagged), len(scored))


if __name__ == "__main__":
    main()
