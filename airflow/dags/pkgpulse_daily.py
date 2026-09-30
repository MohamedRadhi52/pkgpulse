"""DAG quotidien PkgPulse : ingestion, dbt, puis export des agrégats gold.

En production, le même enchaînement tourne dans GitHub Actions (.github/workflows/daily.yml),
gratuit pour un dépôt public. Ce DAG porte la logique d'orchestration : dépendances, relances et
date logique, qui permet de rejouer des jours passés (backfill) sans risque de doublon.
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, Param, chain

REPO = Path(__file__).resolve().parents[2]

with DAG(
    dag_id="pkgpulse_daily",
    schedule="17 5 * * *",  # après le dump de crates.io, pris vers 2 h UTC
    start_date=datetime(2026, 9, 1),
    catchup=False,
    max_active_runs=1,
    params={"sample": Param(False, type="boolean", description="échantillon synthétique")},
    tags=["pkgpulse"],
) as dag:
    make = f"make -C {REPO} DATA_DIR={{{{ 'data/sample' if params.sample else 'data' }}}}"
    ingest = BashOperator(
        task_id="ingest",
        bash_command=make + " {{ 'sample' if params.sample else 'ingest' }}",
        # Relance sûre : l'ingestion est idempotente (docs/DECISIONS.md, décisions 5 et 9).
        retries=2,
        retry_delay=timedelta(minutes=10),
    )
    dbt = BashOperator(task_id="dbt", bash_command=f"{make} dbt")
    export = BashOperator(task_id="export", bash_command=f"{make} publish")
    chain(ingest, dbt, export)
