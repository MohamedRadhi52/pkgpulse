import numpy as np
import pandas as pd

from pkgpulse.anomalies.detect import robust_scores


def test_robust_score_flags_a_spike():
    ds = pd.date_range("2026-01-01", periods=80, freq="D")
    residual = np.random.default_rng(1).normal(0, 0.05, 80)
    residual[70] = 1.0
    residuals = pd.DataFrame({"unique_id": "s", "level": "paquet", "ds": ds, "residual": residual})
    scored = robust_scores(residuals)
    assert scored.loc[scored["anomaly"] != "", "ds"].tolist() == [ds[70]]
