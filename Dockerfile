FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /usr/local/bin/uv

ENV PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy project files
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/

RUN uv sync --frozen --no-dev

ENTRYPOINT ["vigia"]
CMD ["run"]
