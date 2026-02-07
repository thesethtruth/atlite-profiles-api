# API

The API entrypoint is `profiles-api`.

## Start Server

```bash
uv run profiles-api
```

Default bind is `0.0.0.0:8000`.

## Endpoints

- `GET /health`
- `GET /turbines
- `GET /turbines?force_update=true` to refresh cache from source
- `POST /generate`

### Example Request

```bash
curl -X POST http://localhost:8000/generate \\
  -H "Content-Type: application/json" \\
  -d '{
    "profile_type": "both",
    "latitude": 52.0,
    "longitude": 5.0,
    "base_path": "/data",
    "output_dir": "output",
    "cutouts": ["europe-2024-era5.nc"],
    "turbine_model": "NREL_ReferenceTurbine_2020ATB_4MW",
    "slopes": [30.0],
    "azimuths": [180.0],
    "panel_model": "CSi",
    "visualize": false
  }'
```
