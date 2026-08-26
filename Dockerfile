FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

COPY src/ ./src/

RUN uv sync --no-dev

# Copy config if exists
COPY vigia.yaml* ./

ENTRYPOINT ["vigia"]
CMD ["run"]
