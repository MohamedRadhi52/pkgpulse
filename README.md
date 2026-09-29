# PkgPulse

Plateforme data quotidienne sur les téléchargements de crates.io, le registre de paquets Rust :
ingestion idempotente, entrepôt en architecture médaillon avec dbt, prévision de la demande à J+1
et J+7, détection d'anomalies.

Projet en cours de construction.

## Démarrage

Prérequis : Python 3.14 et make.

```bash
make install   # environnement virtuel, dépendances et hooks pre-commit
make lint
make test
make ingest    # backfill de l'archive depuis le 2025-11-01, puis dump du jour
```

Documentation : [cadrage](docs/cadrage.md) et [journal des décisions](docs/DECISIONS.md).
