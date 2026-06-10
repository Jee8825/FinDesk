FROM python:3.11-slim

WORKDIR /srv
COPY shared/py /srv/shared/py
COPY tools /srv/tools
COPY agents/pyproject.toml /srv/agents/pyproject.toml
COPY agents/findesk_agents /srv/agents/findesk_agents
COPY prompts /srv/prompts

RUN pip install --no-cache-dir /srv/shared/py /srv/tools /srv/agents

WORKDIR /srv/agents
CMD ["python", "-m", "findesk_agents.worker"]
