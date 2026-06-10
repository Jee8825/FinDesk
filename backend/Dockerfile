FROM python:3.11-slim

WORKDIR /srv
COPY shared/py /srv/shared/py
COPY backend/pyproject.toml /srv/backend/pyproject.toml
COPY backend/app /srv/backend/app
COPY backend/alembic.ini /srv/backend/alembic.ini

RUN pip install --no-cache-dir /srv/shared/py /srv/backend

WORKDIR /srv/backend
EXPOSE 8080
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080"]
