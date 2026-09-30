import numpy as np
import pytest

from pkgpulse.forecast.conformal import conformal_quantile


@pytest.mark.parametrize(("n", "expected"), [(9, 9.0), (19, 18.0)])
def test_conformal_quantile_uses_finite_sample_rank(n, expected):
    assert conformal_quantile(np.arange(1, n + 1)) == expected
