config = """  - name: europe-{year}
    filename: europe-{year}-era5.nc
    target: data
    cutout:
      module: era5
      x: [-12.0, 42.0]
      y: [33.0, 72.0]
      time: "{year}"
      chunks:
        time: 600
    prepare:
      features: [height, wind, influx, temperature]
"""
years = [1987, 1997, 2012, 2004, 2023]  # ETM/II3050 years
for year in years:
    print(config.replace("{year}", str(year)))
