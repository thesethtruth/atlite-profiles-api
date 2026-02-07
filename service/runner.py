from pathlib import Path


def get_available_turbines() -> list[str]:
    from core.cutout_processing import get_available_turbine_list

    return get_available_turbine_list()


def run_profiles(
    *,
    profile_type: str,
    latitude: float,
    longitude: float,
    base_path: Path,
    output_dir: Path,
    cutouts: list[str],
    turbine_model: str,
    slopes: list[float],
    azimuths: list[float],
    panel_model: str,
    visualize: bool = False,
) -> dict:
    from core.profile_generator import (
        ProfileConfig,
        ProfileGenerator,
        SolarConfig,
        WindConfig,
    )

    profile_config = ProfileConfig(
        location={"lat": latitude, "lon": longitude},
        base_path=base_path,
        output_dir=output_dir,
        cutouts=[Path(cutout) for cutout in cutouts],
    )
    wind_config = WindConfig(turbine_model=turbine_model)
    solar_config = SolarConfig(
        slopes=slopes,
        azimuths=azimuths,
        panel_model=panel_model,
        output_subdir="solar_profiles",
    )
    generator = ProfileGenerator(
        profile_config=profile_config,
        wind_config=wind_config,
        solar_config=solar_config,
    )

    wind_count = 0
    solar_count = 0

    if profile_type in {"wind", "both"}:
        wind_profiles = generator.generate_wind_profiles()
        wind_count = len(wind_profiles)
        if visualize:
            generator.visualize_wind_profiles()

    if profile_type in {"solar", "both"}:
        solar_profiles = generator.generate_solar_profiles()
        solar_count = len(solar_profiles)
        if visualize:
            generator.visualize_solar_profiles_monthly(color_key="azimuth")

    return {
        "status": "ok",
        "profile_type": profile_type,
        "wind_profiles": wind_count,
        "solar_profiles": solar_count,
        "output_dir": str(output_dir),
    }
