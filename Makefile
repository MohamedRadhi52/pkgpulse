PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: install lint format test ingest

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
