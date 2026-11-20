FROM python:3.12.15-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PATH="/srv/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY app app
COPY alembic.ini ./
COPY migrations migrations
RUN uv sync --locked --no-dev
