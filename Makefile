PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
DATA_DIR ?= data
SAMPLE_DIR := data/sample
DBT_FLAGS := --project-dir dbt --profiles-dir dbt

# Chemin absolu : l'ingestion et dbt lisent les mêmes données, quel que soit le dossier courant.
export PKGPULSE_DATA_DIR = $(abspath $(DATA_DIR))

.PHONY: install lint format test ingest dbt sample check

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

# Données synthétiques au format bronze : dbt tourne sans télécharger crates.io.
sample:
	$(BIN)/python -m pkgpulse.sample $(SAMPLE_DIR)

# Les mêmes vérifications que la CI.
check: lint test sample
	$(MAKE) dbt DATA_DIR=$(SAMPLE_DIR)
