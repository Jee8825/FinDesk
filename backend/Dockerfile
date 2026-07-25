FROM python:3.11-slim

WORKDIR /srv
COPY shared/py /srv/shared/py
# The backend depends on findesk-tools: decide_approval executes approved
# actions through the tool layer (ims/email/treds) with a minted token. Without
# this COPY the image fails at pip-install — findesk-tools is a path dependency
# with no PyPI release, so it cannot be resolved from the index.
COPY tools /srv/tools
COPY backend/pyproject.toml /srv/backend/pyproject.toml
COPY backend/app /srv/backend/app
COPY backend/alembic.ini /srv/backend/alembic.ini

RUN pip install --no-cache-dir /srv/shared/py /srv/tools /srv/backend

WORKDIR /srv/backend
EXPOSE 8080
# Render injects PORT; the default keeps `docker run` and compose unchanged.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
