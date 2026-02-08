# Docker Deployment

This deployment builds static docs with MkDocs, runs the FastAPI app, and serves both behind Caddy on a single port.

## Run With Compose (Recommended)

```bash
docker compose up --build
```

## Compose Services

- `app`: single container that runs both:
- FastAPI on internal `:8000`
- Caddy on exposed `:8085`

Mounted volumes:

- `/cutouts:/data`
- `./output:/app/output`

## Run Without Compose

```bash
docker build -t renewables-profiles .
docker run --rm -p 8085:8085 \
  -v "/cutouts:/data" \
  -v "$(pwd)/output:/app/output" \
  renewables-profiles
```

## Routes

- API: `http://localhost:8085/api/*` (prefix `/api` is stripped before forwarding to FastAPI)
- Docs: `http://localhost:8085/docs/` (prefix `/docs` is stripped before serving static site files)
- FastAPI Swagger UI: `http://localhost:8085/api/docs`

Examples:

```bash
curl http://localhost:8085/api/health
open http://localhost:8085/docs/
```
