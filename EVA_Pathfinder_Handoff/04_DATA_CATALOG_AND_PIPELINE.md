# NASA / USGS DATA CATALOG & REPRODUCIBLE PIPELINE

**Goal:** Obtain a genuine, geospatially valid hyperlocal Marswalk dataset using at least three complementary categories: optical, topography, and geological context. Optional archived atmosphere and ground photos add depth.

## 1. Sources (verify access, data conditions and metadata before using)

### P0 — topography / numeric terrain

- **Name:** Mars 2020 Terrain Relative Navigation CTX DTM Mosaic.
- **Mission / instrument:** Mars Reconnaissance Orbiter (MRO) Context Camera (CTX); prepared by USGS Astrogeology for Mars 2020.
- **Catalog:** https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_dtm_mosaic
- **GeoTIFF:** https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif
- **Publisher metadata:** about 9.3 MB, 1,596 x 1,512 pixels, 20 m/pixel, elevation metres, Equirectangular Mars projection, planetocentric latitude, positive-east longitude, spherical radius ~3,396,190 m. The product reports CTX registration characteristics and limitations. Always confirm **actual file CRS and affine transform**, not simply metadata in this handoff.
- **Citation:** USGS Astrogeology; source catalog references Fergason et al., 2020; DOI https://doi.org/10.5066/P906QQT8.
- **Usage constraint:** Publisher says cite authors. Preserve exact product title, URL and processing credit.
- **Caveat:** Originally created for landing-relative navigation, not human on-foot safety. 20 m resolution misses small hazards. Dataset may include a gap patched using other topography; verify quality mask and extent.

### P0 — optical context

- **Name:** Mars 2020 Terrain Relative Navigation Context Camera Orthorectified Image Mosaic.
- **Mission:** MRO CTX; USGS controlled map product in support of Perseverance. ~6 m per pixel.
- **Official catalog:** https://www.usgs.gov/data/mars-2020-terrain-relative-navigation-context-camera-orthorectified-image-mosaic
- **DOI:** https://doi.org/10.5066/P9GV1ND3
- **Alternative NASA viewer:** https://trek.nasa.gov/mars/
- **Action:** Follow actual release links to get the orthomosaic/metadata; confirm georegistration against DEM and clip to same extent. If imagery cannot be obtained legally/technically within available time, display a labelled DEM hillshade but mark optical integration incomplete, not verified.

### P0 — geology and science context

- **Name:** *Geologic map of Jezero crater and the Nili Planum region, Mars*.
- **Authors:** Vivian Z. Sun and Kathryn M. Stack (2020); USGS Scientific Investigations Map 3464, scale 1:75,000.
- **Official:** https://pubs.usgs.gov/publication/sim3464
- **Map:** https://www.usgs.gov/maps/geologic-map-jezero-crater-and-nili-planum-region-mars
- **Map/GIS distribution:** follow the `Database`, `Metadata` and map files on the publication page; verify CRS and available formats.
- **Use:** regional context in a science stop; optional geologic-unit overlay if correct GIS transform is proven.
- **Caveat:** regional units are not an astronaut-scale physical hazard map; no arbitrary pixel tracing presented as precise geology.

### P1 — surface images

- **Name:** Perseverance Raw Images Gallery.
- **Mission/instruments:** Perseverance cameras; exact camera name must be recorded per image.
- **Official:** https://mars.nasa.gov/mars2020/multimedia/raw-images/
- **Use:** contextual image panel per science area; only precisely geolocate with verified rover localization and camera metadata.
- **Credit:** NASA/JPL-Caltech plus other credits shown on individual images. Store image source URL and license/usage note in manifest.

### P1 — atmospheric history

- **Name:** Mars Environmental Dynamics Analyzer (MEDA), PDS Atmospheres Node.
- **Mission/instrument:** Perseverance MEDA.
- **Official:** https://pdsatmospheres.nmsu.edu/data_and_services/atmospheres_data/PERSEVERANCE/meda.html
- **Citation:** Rodriguez-Manfredi et al. (2021), NASA PDS MEDA, DOI https://doi.org/10.17189/1522849.
- **Use:** a selected calibrated/derived CSV value with timestamp/sol, quantity, unit, quality, source file ID and location/sensor scope.
- **Important:** choose a small set using PDS index/query; do not download the multi-GB annual releases. Derived vs calibrated values differ; include quality flags. **Not a live forecast or extrapolated map layer.**

### Inspiration only

- **Curiosity Mount Sharp route:** https://science.nasa.gov/resource/curiositys-proposed-path-up-mount-sharp/ (visual storytelling reference, not Jezero route data).
- **NASA Worldview:** https://worldview.earthdata.nasa.gov/ (Earth-based interface inspiration; **not Mars imagery**).
- **Mars Trek:** https://trek.nasa.gov/mars/ (existing Mars GIS layer portal; distinguish original EVA Guardian contributions from existing Trek tools).

## 2. What to download, exactly

1. DEM GeoTIFF: **first download**, report checksum, dimensions, CRS, transform, bounds, nodata, per-band unit, elevation range, and valid %.
2. Aligned optical orthomosaic or derived, verifiably legal imagery: **second download**, report product version, extent, transform and credits.
3. Geology GIS or publication with one documented regional unit/science target: **third source**; assert accurate geolocation only when verified.
4. One vetted photo and small MEDA CSV samples: optional, and only if time remains.

**Spatial selection:** Choose a 2–4 km-wide real DEM-valid region that overlaps optical coverage; place a hypothetical habitat at a valid grid cell and verified science context within same region. Choose exact values after reading the raster; do not copy guesses from this document as real Martian coordinates.

## 3. End-to-end processing specification

```text
Acquire source (official URL)
  -> validate hash/metadata/usage
  -> select crop within common valid extent
  -> transform/reproject only with explicit Mars CRS
  -> optical + DEM pixel alignment check
  -> compute slope and no-data mask
  -> assign traversal and exclusion policies
  -> prepare map display tiles / lightweight raster
  -> generate science target manifest and source ledger
  -> run route and Guardian analysis
  -> export reproducible evidence report
```

### Spatial correctness rules

- Datum/body is Mars. Respect **planetocentric** latitude and positive-east longitude domain stated by source; do not confuse with Earth WGS84 or reverse positive-east/positive-west longitudes.
- Use original projected meter-based coordinates (if confirmed) for lengths, or rigorously transform to an appropriate local Mars metric projection using the documented Mars planetary radius. Do not blindly call `EPSG:4326` / `EPSG:3857`.
- Verify affine transform, pixel axes, crop origin, nodata and rotated rasters. If pixels not north-up, handle affine transforms fully.
- For DEM gradient, use numerical derivatives based on projected metre cell dimensions; mask edges adjacent to nodata rather than smearing invalid data.
- For route length, calculate actual distances between neighbor cell center coordinates derived from affine transform; no conversions from degrees using Earth's radius.
- Do not infer observed traction or soil bearing strength from CTX DEM. Choose traversability as **model based on local derived slope only**, with explicit limitations.
- Before image overlay, verify sampled landmark correspondences or pixel-to-world bounds. If data are unregistered, show side-by-side contextual image and label limitation.

### Expected processed outputs

```
data/processed/jezero_dem_crop.tif
  data/processed/jezero_optical_crop.*
  data/processed/slope_deg.tif
  data/processed/valid_coverage.tif
  data/processed/route_cost.tif
  data/processed/study_area_metadata.json
  data/processed/science_sites.json
  data/processed/observations.json  # optional
  docs/DATA_PROVENANCE.md
```

Large downloaded files should be ignored in Git by default; link to source and provide a reproducible script. Small processed datasets may be included if distribution and rights allow; preserve attribution.

## 4. Machine-readable manifest contract

Use `config/dataset_manifest.example.json` to initialize a real `data/source_manifest.json` (created by the build agent only after download). Required fields per product:

- `id`, `name`, `agency`, `mission`, `instrument`, `category` (`optical`, `topographic`, `geological`, `atmospheric`, `surface_image`)
- `source_url`, `direct_download_url` (optional), `product_identifier`, `citation`, `usage_terms`, `license_checked`
- `source_acquired` boolean, `local_path` if acquired, `sha256` if downloaded, `bytes`, `status` (`AVAILABLE_VERIFIED`, `PARTIAL`, `UNAVAILABLE`)
- `target_body`, `crs_wkt`/`crs_projjson` (if spatial), `longitude_convention`, `coordinate_type`, `pixel_spacing_m`, `extent`, `nodata`, `units`
- `time_coverage`, `processing_steps`, `derived_from`, `limitations`, `verification_notes`

**Never prefill verified flags or checksums with imaginary results.** Sample schema initially has `source_acquired: false`, `status: UNAVAILABLE`.

## 5. Data verification commands (suggested)

```bash
python - <<'PY'
import rasterio
p = 'data/raw/jezero_ctx_dem.tif'
with rasterio.open(p) as ds:
    print('CRS', ds.crs, 'transform', ds.transform)
    print('bounds', ds.bounds, 'shape', ds.height, ds.width)
    print('nodata', ds.nodata, 'dtype', ds.dtypes)
    print('band tags', ds.tags(1))
    a = ds.read(1, masked=True)
    print('valid', a.count(), 'min', a.min(), 'max', a.max())
PY
```

Verify original raster orientation and metadata with GDAL's `gdalinfo` where available. `sha256sum data/raw/jezero_ctx_dem.tif` to record a source checksum. Avoid making assumptions based only on website preview images.

## 6. Failure policy

- If source URL is unavailable: document exact URL and error, check official alternate, do not scrape prohibited content.
- If a raster is not georeferenced or imagery does not align: do not overlay unregistered data or label them geolocated.
- If none of the authentic data can be obtained: build unit tests and synthetic demo honestly marked; mark scientific MVP incomplete and explain why.
- If no verified scientific target can be located in the chosen crop: pick a different valid crop or use a geologic-context target and explicitly state that precise ground location is hypothetical.
