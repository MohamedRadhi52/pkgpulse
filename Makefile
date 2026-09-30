PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
DATA_DIR ?= data
SAMPLE_DIR := data/sample
DBT_FLAGS := --project-dir dbt --profiles-dir dbt

# Chemin absolu : l'ingestion et dbt lisent les mêmes données, quel que soit le dossier courant.
export PKGPULSE_DATA_DIR = $(abspath $(DATA_DIR))

.PHONY: install lint format test ingest dbt dbt-bigquery publish api monitor dashboard backtest forecast anomalies sample check airflow-test

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --quiet --disable-pip-version-check -r requirements-dev.txt -e .
	$(BIN)/pre-commit install

lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

test:
	$(BIN)/pytest

# Backfill ou rattrapage depuis l'archive, puis dump du jour.
ingest:
	$(BIN)/python -m pkgpulse.ingest archive
	$(BIN)/python -m pkgpulse.ingest dump

# Fraîcheur des sources, puis modèles, tests et snapshot dans l'ordre du lineage.
dbt:
	$(BIN)/dbt source freshness $(DBT_FLAGS)
	$(BIN)/dbt build $(DBT_FLAGS)

# Le même projet dbt sur BigQuery : tables externes sur la couche bronze copiée dans Cloud Storage,
# puis build. Demande des identifiants GCP et la variable GCP_PROJECT_ID.
dbt-bigquery:
	$(BIN)/dbt run-operation create_bronze_tables --args '{bucket: $(GCP_PROJECT_ID)-pkgpulse}' \
		--target bigquery $(DBT_FLAGS)
	$(BIN)/dbt build --target bigquery $(DBT_FLAGS)

# Agrégats gold en CSV dans $(DATA_DIR)/export, publiés par le pipeline dans la release gold.
publish:
	$(BIN)/python -m pkgpulse.publish

# Backtest glissant sur les exports gold ; tableaux de résultats dans $(DATA_DIR)/export.
backtest:
	$(BIN)/python -m pkgpulse.forecast backtest

# Prévisions J+1 et J+7 des champions ; ORIGIN=AAAA-MM-JJ pour prévoir depuis un jour passé.
forecast:
	$(BIN)/python -m pkgpulse.forecast predict $(if $(ORIGIN),--origin $(ORIGIN))

# Erreurs réalisées, MASE glissante et règle champion contre challenger.
monitor:
	$(BIN)/python -m pkgpulse.monitor

# Anomalies sur les résidus de prévision à J+1, exportées dans $(DATA_DIR)/export.
anomalies:
	$(BIN)/python -m pkgpulse.anomalies

# API en local sur les exports du pipeline, documentation sur http://127.0.0.1:8000/docs
api:
	PKGPULSE_DATA_URL=$(PKGPULSE_DATA_DIR)/export $(BIN)/uvicorn pkgpulse.api.main:app --reload

# Données du tableau de bord (site/data.json) ; aperçu local : python -m http.server -d site
dashboard:
	$(BIN)/python -m pkgpulse.dashboard site

# Données synthétiques au format bronze : dbt tourne sans télécharger crates.io.
sample:
	$(BIN)/python -m pkgpulse.sample $(SAMPLE_DIR)

# Les mêmes vérifications que la CI.
check: lint test sample
	$(MAKE) dbt DATA_DIR=$(SAMPLE_DIR)

# DAG Airflow sur l'échantillon, rejoué sur les sept derniers jours (backfill), dans un
# environnement séparé : Airflow impose ses propres versions de dépendances.
AIRFLOW_VERSION := 3.3.2
AIRFLOW_VENV := .venv-airflow
AIRFLOW := AIRFLOW_HOME=$(abspath data/airflow) AIRFLOW__CORE__DAGS_FOLDER=$(abspath airflow/dags) \
	AIRFLOW__CORE__LOAD_EXAMPLES=false $(AIRFLOW_VENV)/bin/airflow

airflow-test:
	$(PYTHON) -m venv $(AIRFLOW_VENV)
	$(AIRFLOW_VENV)/bin/pip install --quiet --disable-pip-version-check "apache-airflow==$(AIRFLOW_VERSION)" \
		--constraint https://raw.githubusercontent.com/apache/airflow/constraints-$(AIRFLOW_VERSION)/constraints-3.14.txt
	$(AIRFLOW) db migrate
	for days in 7 6 5 4 3 2 1; do \
		$(AIRFLOW) dags test pkgpulse_daily $$(date -u -d "$$days days ago" +%F) -c '{"sample": true}' || exit 1; \
	done
