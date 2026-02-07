FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends caddy \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN uv sync --frozen --group dev \
    && uv run mkdocs build --strict

COPY deploy/Caddyfile /etc/caddy/Caddyfile

EXPOSE 8085

CMD ["/app/deploy/start.sh"]
