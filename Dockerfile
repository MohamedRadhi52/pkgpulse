# Image de l'API seule : ni pipeline ni modèles, seulement la lecture des fichiers publiés.
FROM python:3.14-slim

WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY src/pkgpulse/__init__.py src/pkgpulse/__init__.py
COPY src/pkgpulse/api src/pkgpulse/api

ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1
USER nobody
CMD ["sh", "-c", "exec uvicorn pkgpulse.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
