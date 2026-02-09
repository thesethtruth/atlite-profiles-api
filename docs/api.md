# API

The API entrypoint is `profiles-api`.

## Start Server

```bash
uv run profiles-api
```

Default bind is `0.0.0.0:8000`.

## Endpoints

- `GET /health`
- `GET /cutouts`
- `GET /turbines`
- `GET /turbines/{turbine_model}`
- `GET /solar-technologies`
- `GET /solar-technologies/{technology}`
- `POST /generate`

At startup, inspect path parameters are constrained to the server's currently
available catalogs (local `config/*` + atlite). In OpenAPI/Swagger this appears
as enum values for `turbine_model` and `technology`.

Cutouts are discovered at startup from `config/api.yaml`:

```yaml
cutout_sources:
  - data
  - /mnt/shared/cutouts
  - /srv/era5/**/*.nc
```

All matching `.nc` files are globbed and exposed as:

- `GET /cutouts` response items
- OpenAPI enum values for `POST /generate` request field `cutouts`

In Docker Compose, host `/cutouts` is mounted as container `/data`, and
`config/api.yaml` includes `/data` as a default cutout source.

During startup, the API also attempts to inspect metadata for each discovered
cutout and stores it in shared app state for reuse across requests.

`POST /generate` validates requested coordinates against cached cutout bounds
(`x`/`y`) before running generation. If any selected cutout is out of bounds,
the endpoint returns `422` immediately with the offending cutout name(s) and
their bounds.
`base_path` is not accepted by the API; cutout paths are resolved from the
startup catalog.

### Example Request

```bash
curl -X POST http://localhost:8000/generate \\
  -H "Content-Type: application/json" \\
  -d '{
    "profile_type": "both",
    "latitude": 52.0,
    "longitude": 5.0,
    "output_dir": "output",
    "cutouts": ["nl-2012-era5.nc"],
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
    "rated_power_mw": 4,
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

`POST /generate` also accepts optional `solar_technology_config` to run with an inline custom solar panel definition:

```json
{
  "panel_model": "CSi",
  "solar_technology_config": {
    "model": "huld",
    "name": "API_Custom_Solar",
    "efficiency": 0.1,
    "c_temp_amb": 1.0,
    "c_temp_irrad": 0.035,
    "r_tamb": 293.0,
    "r_tmod": 298.0,
    "r_irradiance": 1000.0,
    "k_1": -0.017162,
    "k_2": -0.040289,
    "k_3": -0.004681,
    "k_4": 0.000148,
    "k_5": 0.000169,
    "k_6": 0.000005,
    "inverter_efficiency": 0.9,
    "manufacturer": "ACME",
    "source": "api"
  }
}
```

When `solar_technology_config` is provided, the generator uses it instead of resolving `panel_model` from the catalog.

`solar_technology_config` fields:

- `model` (string, required): either `huld` or `bofinger`
- `name` (string, required)
- `inverter_efficiency` (number, required)
- `manufacturer` (string, optional)
- `source` (string, optional)
- model-specific coefficients:
  - `huld`: `efficiency`, `c_temp_amb`, `c_temp_irrad`, `r_tamb`, `r_tmod`,
    `r_irradiance`, `k_1..k_6`
  - `bofinger`: `threshold`, `area`, `rated_production`, `A`, `B`, `C`, `D`,
    `NOCT`, `Tstd`, `Tamb`, `Intc`, `ta`

### Generate Response Shape

`POST /generate` returns one shared root-level `index` array. Wind and solar
payloads contain only per-series values keyed by profile name:

```json
{
  "status": "ok",
  "profile_type": "both",
  "wind_profiles": 1,
  "solar_profiles": 1,
  "index": ["2024-01-01T00:00:00"],
  "wind_profile_data": {
    "2024_NREL_ReferenceTurbine_2020ATB_4MW": {
      "values": [0.42]
    }
  },
  "solar_profile_data": {
    "2024_slope30.0_azimuth180.0": {
      "values": [0.28]
    }
  }
}
```
