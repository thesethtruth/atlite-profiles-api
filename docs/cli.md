# CLI

The CLI entrypoint is `profiles-cli`.

## Commands

```bash
uv run profiles-cli --help
uv run profiles-cli list-turbines
uv run profiles-cli list-turbines --sort name
uv run profiles-cli list-turbines --sort hub_height
uv run profiles-cli list-turbines --sort power
uv run profiles-cli generate --profile-type both --base-path data --output-dir output --cutout europe-2024-era5.nc
uv run profiles-cli inspect-turbine Vestas_V162_5.6
```

## Notes

- Use repeated `--cutout` values to run multiple weather years.
- Use repeated `--slope` and `--azimuth` values for multiple solar orientations.
- `list-turbines` supports `--sort` values: `name`, `hub_height`, `power`.
- Default sort is `power` descending; `hub_height` is descending; `name` is ascending.
- `inspect-turbine` renders a two-card view: metadata on the left and power-curve chart on the right.
- API returns the same payload at `GET /turbines/{turbine_model}`.
