"""API de prévision : lit les fichiers publiés par le pipeline, dans Cloud Storage ou en local."""

import csv
import datetime as dt
import io
import os
import time
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from google.cloud import storage
from pydantic import BaseModel

REFRESH_SECONDS = 3600  # le pipeline publie une fois par jour

app = FastAPI(
    title="PkgPulse",
    description="Prévisions des téléchargements de crates.io à J+1 et J+7, et anomalies récentes.",
    version="1.0",
)


class Forecast(BaseModel):
    date: dt.date
    horizon: int
    value: float
    lower: float
    upper: float


class SeriesForecast(BaseModel):
    series: str
    level: str
    origin: dt.date
    forecasts: list[Forecast]


class Anomaly(BaseModel):
    date: dt.date
    series: str
    level: str
    kind: str
    score: float


def read_rows(name: str) -> list[dict[str, str]]:
    """Lit un fichier publié dans PKGPULSE_DATA_URL : dossier local ou gs://bucket/préfixe."""
    location = os.environ.get("PKGPULSE_DATA_URL", "data/export")
    if location.startswith("gs://"):
        bucket, _, prefix = location.removeprefix("gs://").partition("/")
        blob = storage.Client().bucket(bucket).blob(f"{prefix}/{name}")
        if not blob.exists():
            raise HTTPException(503, "données pas encore publiées")
        text = blob.download_as_text()
    else:
        path = Path(location) / name
        if not path.exists():
            raise HTTPException(503, "données pas encore publiées")
        text = path.read_text()
    return list(csv.DictReader(io.StringIO(text)))


@lru_cache(maxsize=4)
def cached_rows(name: str, period: int) -> list[dict[str, str]]:
    return read_rows(name)


def rows(name: str) -> list[dict[str, str]]:
    """Relit un fichier au plus une fois par heure."""
    return cached_rows(name, int(time.time() // REFRESH_SECONDS))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/series")
def list_series(level: str | None = None) -> list[str]:
    """Séries prévues : total, autres, categorie:<slug> et paquet:<nom>."""
    return sorted(
        {r["unique_id"] for r in rows("forecasts.csv") if level is None or r["level"] == level}
    )


@app.get("/forecast")
def forecast(series: str = "total") -> SeriesForecast:
    """Prévisions J+1 et J+7 d'une série, avec leur intervalle à 90 %."""
    found = [r for r in rows("forecasts.csv") if r["unique_id"] == series]
    if not found:
        raise HTTPException(404, f"série inconnue : {series}")
    return SeriesForecast(
        series=series,
        level=found[0]["level"],
        origin=found[0]["origin"],
        forecasts=[
            Forecast(
                date=r["ds"], horizon=r["h"], value=r["y_hat"], lower=r["lower"], upper=r["upper"]
            )
            for r in sorted(found, key=lambda r: int(r["h"]))
        ],
    )


@app.get("/anomalies")
def anomalies(days: int = Query(30, ge=1, le=365), level: str | None = None) -> list[Anomaly]:
    """Anomalies des derniers jours connus, de la plus récente à la plus ancienne."""
    last_day = dt.date.fromisoformat(rows("forecasts.csv")[0]["origin"])
    since = (last_day - dt.timedelta(days=days)).isoformat()
    recent = [
        r
        for r in rows("anomalies.csv")
        if r["ds"] > since and (level is None or r["level"] == level)
    ]
    return [
        Anomaly(
            date=r["ds"],
            series=r["unique_id"],
            level=r["level"],
            kind=r["anomaly"],
            score=r["score"],
        )
        for r in sorted(recent, key=lambda r: (r["ds"], r["unique_id"]), reverse=True)
    ]
