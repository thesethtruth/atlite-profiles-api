# API

The API entrypoint is `profiles-api`.

## Start Server

```bash
uv run profiles-api
```

Default bind is `0.0.0.0:8000`.

## Endpoints

- `GET /health`
- `GET /turbines`
- `GET /turbines/{turbine_model}`
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

`POST /generate` also accepts optional `turbine_config` to run with an inline custom turbine definition:

```json
{
  "turbine_model": "NREL_ReferenceTurbine_2020ATB_4MW",
  "turbine_config": {
    "name": "API_Custom",
    "hub_height_m": 120,
    "wind_speeds": [0, 10, 20],
    "power_curve_mw": [0, 2, 4],
    "manufacturer": "ACME",
    "source": "api"
  }
}
```

When `turbine_config` is provided, the generator uses it instead of resolving `turbine_model` from the catalog.

`turbine_config` fields:

- `name` (string, required)
- `hub_height_m` (number > 0, required)
- `wind_speeds` (array[number], required, at least 2 values)
- `power_curve_mw` (array[number], required, same length as `wind_speeds`)
- `rated_power_mw` (number > 0, optional)
- `manufacturer` (string, optional)
- `source` (string, optional)
