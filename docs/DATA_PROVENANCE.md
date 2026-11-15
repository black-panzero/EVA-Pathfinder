# Data provenance

All sources are allowlisted in `config/sources.json`. `scripts/prepare_data.py` downloads only those URLs, verifies the SHA-256 values recorded there, and fails on a mismatch. Raw files live in `data/raw/` (git-ignored). Derived products and their checksums are in `data/processed/jezero-delta-return-v1/manifest.json`. A full numeric report is in `docs/DATA_INSPECTION.md`.

## Sources actually downloaded (2026-11-15)

| Source ID | Product | Category | Downloaded file | SHA-256 | Status |
|---|---|---|---|---|---|
| `usgs-m2020-trn-ctx-dtm-20m` | Mars 2020 TRN CTX DTM mosaic, MOLA topography, delta geoid, 20 m ([product page](https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_dtm_mosaic)) | Topography | `JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif` (9,662,387 B) | `16a1aa66c3f48c1bca252795827db7b417876217aff0f5e1aff18027fab2327b` | AVAILABLE_VERIFIED |
| `usgs-m2020-trn-ctx-ortho-6m` | Mars 2020 TRN CTX orthorectified mosaic, 6 m ([product page](https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_orthorectified_image_mosaic)) | Optical | `JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0.tif` (36,269,402 B) | `842b457afee7c2672022b66e3f60be836c6d52e99474015bfd9ced60099b8615` | AVAILABLE_VERIFIED |
| `usgs-sim3464-geology` | Sun & Stack 2020, USGS SIM 3464 GIS database ([doi:10.3133/sim3464](https://doi.org/10.3133/sim3464)) | Geology | `sim3464_database.zip` (349,336,873 B), layer `GeoUnits_v1` | `a88bd53a5573743cc4a20036c10e585106d08a433ad2f34af269e9cea1529f87` | PARTIAL (documented 100-200 m offsets) |
| `usgs-sim3464-pamphlet` | SIM 3464 pamphlet (unit context) | Geology | `sim3464_pamphlet.pdf` | recorded in manifest | AVAILABLE_VERIFIED |
| `nasa-m2020-waypoints` | Perseverance localized waypoints (MMGIS `M20_waypoints.json`) | Rover localization | `M20_waypoints.json` | recorded in manifest | AVAILABLE_VERIFIED |
| `nasa-m2020-raw-images-api` | Mars 2020 raw image API (Navcam), sols 502 and 684 | Rover imagery | 2 images, 800 px browse JPGs | per image in `photos.json` | AVAILABLE_VERIFIED |
| `pds-m2020-meda-derived-sol0684` | MEDA derived PS + TIRS + ancillary, sol 684 (PDS Atmospheres Node) | Atmosphere history | 3 CSVs + PDS4 labels | PS `90aa19a5…`, TIRS `938a3ba2…`, ANCILLARY `485606c3…` | AVAILABLE_VERIFIED |

## Coordinate reference

- CRS (DEM and ortho): `Equirectangular Mars 2000 Sphere IAU`, sphere radius 3,396,190 m, standard parallel 0°, central meridian 0°, units metre, north-up (checked: no rotation terms, negative y step).
- Longitudes are east-positive (0-360). On a sphere, planetocentric and planetographic latitude are identical.
- Study-area window in the source DEM: `col_off 516, row_off 690, width 405, height 225`.
- Extent: 77.33457-77.47122 °E, 18.41246-18.48838 °N. Origin easting 4,583,983.251 m, northing top 1,095,893.140 m.
- Local API frame: `x_m = easting − origin`, `y_m = northing − bottom`, in projected metres. East-west ground metres = projected × cos(lat), which is 0.9486 at the centre.
- Geology source CRS is Transverse Mercator `MTM_clon77.5E` (Mars 2000 sphere). It is reprojected vertex by vertex with pyproj into the DEM CRS, then clipped and rasterized at 20 m.
- Rover waypoint lon/lat are converted with `E = R·lon_rad`, `N = R·lat_rad` on the same sphere.

## Real values (sample)

| Item | Value |
|---|---|
| DEM valid fraction in crop | 100.000 % |
| Elevation min / mean / max | −2610.88 / −2504.95 / −2356.21 m |
| Slope p50 / p95 / max | 2.98 / 10.45 / 34.13 ° |
| Habitat cell (landing localization) | DEM −2567.19 m, rover-reported −2569.91 m |
| Wildcat Ridge (site 26 / drive 1222) | 18.458647°N 77.405925°E; DEM −2519.85 m, rover −2523.17 m |
| Three Forks depot (site 32 / drive 250) | 18.452523°N 77.407847°E; DEM −2546.64 m, rover −2545.48 m |
| DEM − rover elevation over 252 localizations | median +0.37 m, median absolute 1.55 m, 5-95 % −3.51 to +4.82 m |

## Derived artifacts

Each artifact in `manifest.json` carries `artifact_id`, `source_ids`, `processing_version`, `checksum_sha256`, `created_at`, `crs`, `resolution_m`, `nodata_policy`, `units`, `evidence_level` and `limitations`:

`dem_crop.tif` (NASA observation, cropped, not resampled), `ortho.png` (observation, unstretched DN), `hillshade.png`, `elevation.png`, `slope.png`, `geology.png` + `geology_units.npy` (derived), `science_sites.json`, `rover_traverse.json`, `photos.json` + `photos/*.jpg`, `meda.json`.

## Rover photographs

| Photo | Site | Geolocation basis |
|---|---|---|
| `NLF_0684_0727665509_222ECM_N0321062NCAM08111_02_095J` (Navcam left, sol 684) | Three Forks depot | Image metadata site 32 / drive 1062 matched to a published localization record with the same site/drive |
| `NLF_0502_0711519639_144ECM_N0261222NCAM00501_01_295J` (Navcam left, sol 502) | Wildcat Ridge | Image metadata site 26 / drive 1222 matched to the localization record used for the site |

Credit: NASA/JPL-Caltech. These are raw, unprocessed browse images. Each one links to its NASA raw-image page.

## Attribution

- CTX DTM and orthomosaic: USGS Astrogeology Science Center; NASA/JPL-Caltech/MSSS (MRO Context Camera).
- Geology: Sun, V.Z., and Stack, K.M., 2020, USGS SIM 3464, https://doi.org/10.3133/sim3464 (public domain).
- Rover localization and imagery: NASA/JPL-Caltech.
- MEDA: Mars 2020 MEDA team, NASA PDS Atmospheres Node (`urn:nasa:pds:mars2020_meda`).

## Reproduce

```bash
make setup && make data && make inspect
```

`make data` re-downloads any missing raw file and refuses to continue on a checksum mismatch.
