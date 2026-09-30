import pytest
from fastapi.testclient import TestClient

from pkgpulse.api import main

FORECASTS = """unique_id,level,origin,ds,h,y_hat,lower,upper
total,total,2026-09-29,2026-10-06,7,1200.0,1000.0,1400.0
total,total,2026-09-29,2026-09-30,1,1000.0,900.0,1100.0
paquet:serde,paquet,2026-09-29,2026-09-30,1,50.0,40.0,60.0
"""
ANOMALIES = """unique_id,level,ds,residual,score,anomaly
paquet:serde,paquet,2026-05-25,-0.5,-6.2,creux
total,total,2026-09-20,0.3,4.5,pic
"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "forecasts.csv").write_text(FORECASTS)
    (tmp_path / "anomalies.csv").write_text(ANOMALIES)
    monkeypatch.setenv("PKGPULSE_DATA_URL", str(tmp_path))
    main.cached_rows.cache_clear()
    return TestClient(main.app)


def test_forecast_gives_both_horizons_in_order(client):
    body = client.get("/forecast", params={"series": "total"}).json()
    assert body["origin"] == "2026-09-29"
    assert [(f["horizon"], f["value"], f["upper"]) for f in body["forecasts"]] == [
        (1, 1000.0, 1100.0),
        (7, 1200.0, 1400.0),
    ]


def test_unknown_series_is_not_found(client):
    assert client.get("/forecast", params={"series": "paquet:inconnu"}).status_code == 404


def test_series_can_be_filtered_by_level(client):
    assert client.get("/series", params={"level": "paquet"}).json() == ["paquet:serde"]


def test_only_recent_anomalies_are_returned(client):
    body = client.get("/anomalies", params={"days": 30}).json()
    assert [(a["series"], a["kind"]) for a in body] == [("total", "pic")]


def test_unpublished_data_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("PKGPULSE_DATA_URL", str(tmp_path / "vide"))
    main.cached_rows.cache_clear()
    assert TestClient(main.app).get("/forecast").status_code == 503
