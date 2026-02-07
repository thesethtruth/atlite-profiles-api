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
```

## Notes

- Use repeated `--cutout` values to run multiple weather years.
- Use repeated `--slope` and `--azimuth` values for multiple solar orientations.
- `list-turbines` supports `--sort` values: `name`, `hub_height`, `power`.
- Default sort is `power` descending; `hub_height` is descending; `name` is ascending.
