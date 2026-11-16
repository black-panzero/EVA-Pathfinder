#!/usr/bin/env python3
"""Prepare the EVA Pathfinder study area from real NASA/USGS sources.

Steps (each fails loudly on a contract violation):
  1. Download allowlisted sources that are missing (config/sources.json) and verify sha256.
  2. Crop the 20 m CTX DTM to the configured window; verify the 6 m CTX orthomosaic shares
     the same CRS and grid origin, then crop it to exactly the same bounds.
  3. Export map overlays (orthoimage, hillshade, elevation, slope) as PNG.
  4. Reproject the USGS SIM 3464 geologic units (MTM) to the DTM CRS, clip and rasterize.
  5. Resolve science waypoints from NASA rover localization records (site/drive).
  6. Check DEM elevations against rover-reported geoid elevations (supporting cross-check
     (rover elevations derive from orbital-map localization), not an independent validation).
  7. Estimate optical-vs-DEM misregistration by cross-correlating gradient images.
  8. Fetch geolocated Navcam images (matched by site/drive) and summarise one MEDA sol.
  9. Write georeferenced GeoTIFFs (slope_deg, valid_coverage, ortho_crop) next to the PNGs.
 10. Write data/processed/<study_area>/manifest.json with provenance for every artifact, and
     data/source_manifest.json (one record per product, handoff 04 section 4 field names).

Usage:  python scripts/prepare_data.py [--offline]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pyproj
import rasterio
from PIL import Image
from rasterio.features import rasterize
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.domain.terrain import MARS_RADIUS_M, TerrainGrid, compute_slope_deg  # noqa: E402

PROCESSING_VERSION = "1.0.0"
USER_AGENT = "eva-pathfinder-data-prep/1.0"
GEOLOGY_GDB = "sim3464_JezeroNili_FINAL/Geodatabase/Nili.gdb"
RAW_IMAGE_API = "https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json&num=100&page=0&sol={sol}&search={instrument}"


def log(msg: str) -> None:
    print(f"[prepare] {msg}", flush=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path, timeout: int = 600) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=timeout) as r, tmp.open("wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.replace(dest)


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


# ----------------------------------------------------------------------------- sources
def ensure_sources(sources: list[dict], offline: bool) -> dict[str, dict]:
    status: dict[str, dict] = {}
    for s in sources:
        sid = s["source_id"]
        rec = {"source_id": sid, "status": "UNAVAILABLE", "files": []}
        targets: list[tuple[Path, str, str | None]] = []
        if "files" in s:
            base = ROOT / s["local_path"]
            for name, digest in s["files"].items():
                targets.append((base / name, s["url"].rstrip("/") + "/" + name, digest))
        elif s["local_path"].endswith("/"):
            # Per-item feed (raw images): hash whatever cached feed files exist now. The status is
            # finalised after the photos are fetched (finalise_feed_status); never prefilled as verified.
            base = ROOT / s["local_path"]
            for path in sorted(base.glob("*.json")) if base.exists() else []:
                rec["files"].append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": path.stat().st_size, "verified_against_config": False})
            rec["status"] = "PARTIAL" if rec["files"] else "UNAVAILABLE"
            rec["note"] = "cached feed JSON hashed; status finalised after photo download"
            status[sid] = rec
            continue
        else:
            targets.append((ROOT / s["local_path"], s["url"], s.get("sha256")))
        ok = True
        for path, url, digest in targets:
            if not path.exists():
                if offline:
                    log(f"MISSING (offline): {path}")
                    ok = False
                    continue
                log(f"downloading {url}")
                try:
                    fetch(url, path)
                except Exception as exc:  # recorded, not hidden
                    log(f"DOWNLOAD FAILED {url}: {exc}")
                    ok = False
                    continue
            actual = sha256_file(path)
            if digest and actual != digest:
                raise SystemExit(f"CHECKSUM MISMATCH for {path}: expected {digest}, got {actual}")
            rec["files"].append({"path": str(path.relative_to(ROOT)), "sha256": actual, "bytes": path.stat().st_size, "verified_against_config": bool(digest)})
        rec["status"] = "AVAILABLE_VERIFIED" if ok else "UNAVAILABLE"
        status[sid] = rec
    return status


# ----------------------------------------------------------------------------- rasters
def crop_dem(dem_path: Path, window: dict, out_tif: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(dem_path) as src:
        if src.crs is None or "Mars" not in src.crs.to_wkt():
            raise SystemExit("DEM CRS is missing or not a Mars CRS")
        if src.crs.linear_units not in ("metre", "meter"):
            raise SystemExit(f"DEM CRS linear units are {src.crs.linear_units}, expected metre")
        t = src.transform
        if abs(t.b) > 1e-9 or abs(t.d) > 1e-9 or t.e >= 0:
            raise SystemExit("DEM is not north-up (rotation terms present or positive y step)")
        w = Window(window["col_off"], window["row_off"], window["width"], window["height"])
        data = src.read(1, window=w).astype("float64")
        nodata = src.nodata
        wt = src.window_transform(w)
        profile = src.profile.copy()
        crs_wkt = src.crs.to_wkt()
    valid = np.isfinite(data)
    if nodata is not None:
        valid &= ~np.isclose(data, nodata)
    valid &= data > -1e30
    data[~valid] = np.nan
    profile.update(width=window["width"], height=window["height"], transform=wt, nodata=np.float32(-3.4028226550889045e38), compress="deflate", dtype="float32")
    profile.pop("blockxsize", None)
    profile.pop("blockysize", None)
    profile.pop("tiled", None)
    out_tif.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(np.where(valid, data, profile["nodata"]).astype("float32"), 1)
    meta = {"transform": list(wt)[:6], "crs_wkt": crs_wkt, "nodata": float(nodata) if nodata is not None else None}
    return data, meta


def crop_ortho(ortho_path: Path, dem_meta: dict, shape: tuple[int, int]) -> tuple[np.ndarray, dict]:
    a, b, c, d, e, f = dem_meta["transform"]
    with rasterio.open(ortho_path) as src:
        if src.crs.to_wkt() != dem_meta["crs_wkt"]:
            raise SystemExit("DATA_UNALIGNED: orthomosaic CRS differs from DEM CRS")
        ot = src.transform
        col = (c - ot.c) / ot.a
        row = (f - ot.f) / ot.e
        if abs(col - round(col)) > 1e-6 or abs(row - round(row)) > 1e-6:
            raise SystemExit(f"DATA_UNALIGNED: crop edge does not fall on an ortho pixel edge (col={col}, row={row})")
        ratio = a / ot.a
        width = round(shape[1] * ratio)
        height = round(shape[0] * ratio)
        w = Window(round(col), round(row), width, height)
        img = src.read(1, window=w)
        meta = {"transform": list(src.window_transform(w))[:6], "pixel_m": ot.a, "nodata": src.nodata, "ratio": ratio,
                "grid_origin_difference_m": [float(ot.c - (c - col * ot.a)), float(ot.f - (f - row * ot.e))]}
    return img, meta


def to_png_gray(arr: np.ndarray, path: Path, mask: np.ndarray | None = None) -> None:
    rgba = np.zeros((*arr.shape, 4), dtype=np.uint8)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = arr
    rgba[..., 3] = 255 if mask is None else np.where(mask, 255, 0)
    Image.fromarray(rgba, "RGBA").save(path, optimize=True)


def colormap(values01: np.ndarray, stops: list[tuple[float, tuple[int, int, int]]]) -> np.ndarray:
    xs = np.array([s[0] for s in stops])
    out = np.zeros((*values01.shape, 3), dtype=np.uint8)
    for ch in range(3):
        ys = np.array([s[1][ch] for s in stops], dtype=float)
        out[..., ch] = np.interp(values01, xs, ys).astype(np.uint8)
    return out


def hillshade(grid: TerrainGrid, azimuth_deg: float = 315.0, altitude_deg: float = 45.0) -> np.ndarray:
    z = grid.elevation_m
    dzdx = np.gradient(z, axis=1) / grid.dx_row_m[:, None]
    dzdy = -np.gradient(z, axis=0) / grid.dy_m  # row index increases southward
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(-dzdx, dzdy)
    az = math.radians(360.0 - azimuth_deg + 90.0)
    alt = math.radians(altitude_deg)
    hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(hs, 0, 1)


# ----------------------------------------------------------------------------- geology
def prepare_geology(zip_path: Path, extract_root: Path, grid: TerrainGrid, out_dir: Path, unit_notes: dict) -> dict:
    import pyogrio.raw
    import shapely
    from pyproj import CRS, Transformer
    from shapely.geometry import box

    gdb = extract_root / GEOLOGY_GDB
    if not gdb.exists():
        with zipfile.ZipFile(zip_path) as zf:
            members = [m for m in zf.namelist() if m.startswith("sim3464_JezeroNili_FINAL/Geodatabase/") or m.startswith("sim3464_JezeroNili_FINAL/CoordinateSystems/")]
            zf.extractall(extract_root, members=members)
    meta, _fids, geoms, fields = pyogrio.raw.read(str(gdb), layer="GeoUnits_v1", columns=["symbol", "name"])
    src_crs = CRS.from_wkt(meta["crs"])
    dst_crs = CRS.from_wkt(grid.crs_wkt)
    tr = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    sym_idx = list(meta["fields"]).index("symbol")
    name_idx = list(meta["fields"]).index("name")
    shapes = [shapely.from_wkb(g) for g in geoms]
    shapes = [shapely.transform(s, lambda xy: np.column_stack(tr.transform(xy[:, 0], xy[:, 1]))) for s in shapes]
    e0, n_top = grid.origin_e_m, grid.origin_n_m
    bounds = box(e0, n_top - grid.height * grid.res_m, e0 + grid.width * grid.res_m, n_top)
    symbols: dict[str, dict] = {}
    pairs = []
    for s, sym, name in zip(shapes, fields[sym_idx], fields[name_idx]):
        if s is None or s.is_empty or not s.intersects(bounds):
            continue
        sym = str(sym)
        name = "Crater rim unit" if name == "Crater riim unit" else str(name)  # source typo, normalised
        if sym not in symbols:
            symbols[sym] = {"code": len(symbols) + 1, "symbol": sym, "name": name, "note": unit_notes.get(sym, "")}
        pairs.append((shapely.intersection(s, bounds), symbols[sym]["code"]))
    transform = rasterio.Affine(grid.res_m, 0, e0, 0, -grid.res_m, n_top)
    raster = rasterize(pairs, out_shape=(grid.height, grid.width), transform=transform, fill=0, dtype="uint8") if pairs else np.zeros((grid.height, grid.width), np.uint8)
    np.save(out_dir / "geology_units.npy", raster)
    palette = [(214, 125, 72), (110, 160, 200), (196, 170, 96), (150, 110, 170), (120, 180, 120), (220, 200, 140), (180, 90, 90), (90, 140, 140), (200, 140, 180), (160, 160, 90), (130, 130, 200), (230, 160, 90), (100, 100, 100), (170, 200, 220)]
    rgba = np.zeros((grid.height, grid.width, 4), np.uint8)
    for unit in symbols.values():
        col = palette[(unit["code"] - 1) % len(palette)]
        unit["color"] = "#%02x%02x%02x" % col
        m = raster == unit["code"]
        rgba[m, :3] = col
        rgba[m, 3] = 255
        unit["cells"] = int(m.sum())
    Image.fromarray(rgba, "RGBA").save(out_dir / "geology.png", optimize=True)
    return {"units": sorted(symbols.values(), key=lambda u: u["code"]), "coverage_fraction": float((raster > 0).mean()), "source_crs": src_crs.name, "_source_crs_wkt": src_crs.to_wkt()}


# ----------------------------------------------------------------------------- rover records
def load_waypoints(path: Path) -> list[dict]:
    return [f["properties"] for f in json.loads(path.read_text())["features"]]


def lonlat_to_eqc(lon: float, lat: float) -> tuple[float, float]:
    return MARS_RADIUS_M * math.radians(lon), MARS_RADIUS_M * math.radians(lat)


def resolve_record(waypoints: list[dict], site: int, drive: int) -> dict:
    hits = [w for w in waypoints if w["site"] == site and w["drive"] == drive]
    if not hits:
        raise SystemExit(f"No rover waypoint record for site {site} drive {drive}")
    finals = [w for w in hits if w.get("final") == "y"]
    return (finals or hits)[0]


def resolve_by_sol(waypoints: list[dict], sol: int) -> dict:
    """Rover position on a given sol: the last end-of-drive localization on or before that sol."""
    finals = [w for w in waypoints if w.get("final") == "y" and w["sol"] <= sol]
    if not finals:
        raise SystemExit(f"No rover localization on or before sol {sol}")
    return max(finals, key=lambda w: (w["sol"], w["site"], w["drive"]))


def place_any(grid: TerrainGrid, rec: dict) -> dict:
    """Like place(), but allows positions outside the planning grid (context sites)."""
    e, n = lonlat_to_eqc(rec["lon"], rec["lat"])
    x, y = e - grid.origin_e_m, n - (grid.origin_n_m - grid.height * grid.res_m)
    if grid.contains_xy(x, y):
        return {**place(grid, rec), "in_planning_area": True}
    return {"x_m": round(x, 2), "y_m": round(y, 2), "lon_deg": rec["lon"], "lat_deg": rec["lat"], "cell": None,
            "sol": rec["sol"], "site": rec["site"], "drive": rec["drive"], "rover_elev_geoid_m": rec.get("elev_geoid"),
            "dem_elev_m": None, "in_planning_area": False}


def place(grid: TerrainGrid, rec: dict) -> dict:
    e, n = lonlat_to_eqc(rec["lon"], rec["lat"])
    x, y = e - grid.origin_e_m, n - (grid.origin_n_m - grid.height * grid.res_m)
    if not grid.contains_xy(x, y):
        raise SystemExit(f"Record site {rec['site']} drive {rec['drive']} lies outside the study area")
    r, c = grid.xy_to_cell(x, y)
    return {"x_m": round(x, 2), "y_m": round(y, 2), "lon_deg": rec["lon"], "lat_deg": rec["lat"], "cell": [r, c],
            "sol": rec["sol"], "site": rec["site"], "drive": rec["drive"],
            "rover_elev_geoid_m": rec.get("elev_geoid"), "dem_elev_m": None if math.isnan(grid.elevation_m[r, c]) else round(float(grid.elevation_m[r, c]), 2)}


def elevation_check(grid: TerrainGrid, waypoints: list[dict]) -> dict:
    diffs = []
    for w in waypoints:
        if w.get("final") != "y" or w.get("elev_geoid") is None:
            continue
        e, n = lonlat_to_eqc(w["lon"], w["lat"])
        x, y = e - grid.origin_e_m, n - (grid.origin_n_m - grid.height * grid.res_m)
        if not grid.contains_xy(x, y):
            continue
        z = grid.sample_bilinear(x, y)
        if z is not None:
            diffs.append(z - w["elev_geoid"])
    d = np.array(diffs)
    if d.size == 0:
        return {"n": 0}
    return {"n": int(d.size), "median_dem_minus_rover_m": round(float(np.median(d)), 2), "mean_m": round(float(d.mean()), 2),
            "p05_m": round(float(np.percentile(d, 5)), 2), "p95_m": round(float(np.percentile(d, 95)), 2),
            "median_abs_m": round(float(np.median(np.abs(d))), 2)}


def traverse_polyline(grid: TerrainGrid, waypoints: list[dict]) -> list[dict]:
    """Every end-of-drive localization (whole mission); x/y in the planning frame, may lie outside it."""
    out = []
    for w in waypoints:
        if w.get("final") != "y":
            continue
        e, n = lonlat_to_eqc(w["lon"], w["lat"])
        x, y = e - grid.origin_e_m, n - (grid.origin_n_m - grid.height * grid.res_m)
        out.append({"x_m": round(x, 1), "y_m": round(y, 1), "lon_deg": round(w["lon"], 6), "lat_deg": round(w["lat"], 6),
                    "sol": w["sol"], "site": w["site"], "drive": w["drive"], "in_planning_area": grid.contains_xy(x, y)})
    return out


def write_context_image(ortho_path: Path, out_jpg: Path, factor: int = 2) -> dict:
    """Whole source orthomosaic, block-averaged by `factor`, as a JPEG context layer with lon/lat bounds."""
    from rasterio.enums import Resampling

    with rasterio.open(ortho_path) as src:
        h, w = src.height // factor, src.width // factor
        img = src.read(1, out_shape=(h, w), resampling=Resampling.average)
        b = src.bounds
        res = src.transform.a * factor
    Image.fromarray(img, "L").save(out_jpg, quality=82, optimize=True, progressive=True)
    deg = 180.0 / math.pi / MARS_RADIUS_M
    return {"file": out_jpg.name, "source_id": "usgs-m2020-trn-ctx-ortho-6m", "resolution_m": res, "size_px": [w, h],
            "lon_range_deg": [round(b.left * deg, 6), round(b.right * deg, 6)], "lat_range_deg": [round(b.bottom * deg, 6), round(b.top * deg, 6)],
            "evidence_level": "NASA_OBSERVATION", "note": "Whole Mars 2020 TRN CTX orthomosaic, block-averaged for display. Routing uses only the planning area."}


# ----------------------------------------------------------------------------- alignment
def registration_check(grid: TerrainGrid, ortho: np.ndarray, ratio: float, max_shift: int = 4) -> dict:
    """Cross-correlate gradient magnitude of the ortho (block-averaged onto the DEM grid) with the
    DEM hillshade-independent gradient magnitude. Reports the integer-cell shift that maximises
    normalised correlation. Illumination differs, so this is a coarse check, not a co-registration."""
    h, w = grid.height, grid.width
    o = ortho.astype(float)
    # area-average ortho pixels onto 20 m cells (ratio = 20/6 is not integer; use index binning)
    rows = np.minimum((np.arange(o.shape[0]) / ratio).astype(int), h - 1)
    cols = np.minimum((np.arange(o.shape[1]) / ratio).astype(int), w - 1)
    acc = np.zeros((h, w))
    cnt = np.zeros((h, w))
    np.add.at(acc, (rows[:, None], cols[None, :]), o)
    np.add.at(cnt, (rows[:, None], cols[None, :]), 1)
    o20 = acc / np.maximum(cnt, 1)
    go = np.hypot(*np.gradient(o20))
    gz = np.nan_to_num(compute_slope_deg(grid.elevation_m, grid.dx_row_m, grid.dy_m))
    m = max_shift
    core_o = go[m:-m, m:-m]
    best = (-2.0, 0, 0)
    table = {}
    for dr in range(-m, m + 1):
        for dc in range(-m, m + 1):
            core_z = gz[m + dr:h - m + dr, m + dc:w - m + dc]
            a = core_o - core_o.mean()
            b = core_z - core_z.mean()
            r = float((a * b).sum() / math.sqrt((a * a).sum() * (b * b).sum()))
            table[f"{dr},{dc}"] = round(r, 4)
            if r > best[0]:
                best = (r, dr, dc)
    return {"method": "normalised cross-correlation of ortho gradient magnitude vs DEM slope, integer 20 m shifts",
            "best_shift_cells": {"rows": best[1], "cols": best[2]}, "best_correlation": round(best[0], 4),
            "zero_shift_correlation": table["0,0"], "searched_shift_cells": m}


# ----------------------------------------------------------------------------- photos
def fetch_photos(grid: TerrainGrid, waypoints: list[dict], requests: list[dict], sites: dict, raw_dir: Path, out_dir: Path, offline: bool) -> list[dict]:
    photos = []
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    index = {(w["site"], w["drive"]): w for w in waypoints}
    for req in requests:
        cache = raw_dir / f"sol{req['sol']:04d}_{req['instrument']}.json"
        if not cache.exists():
            if offline:
                log(f"photo feed cache missing (offline): {cache}")
                continue
            try:
                fetch(RAW_IMAGE_API.format(sol=req["sol"], instrument=req["instrument"]), cache, timeout=120)
            except Exception as exc:
                log(f"raw image feed failed for sol {req['sol']}: {exc}")
                continue
        feed = json.loads(cache.read_text())
        chosen = 0
        for img in feed.get("images", []):
            if chosen >= req["max_images"]:
                break
            if img["camera"]["instrument"] != req["instrument"] or img.get("sample_type") != "Full":
                continue
            rec = index.get((img["site"], int(img["drive"])))
            if rec is None:
                continue  # no localization record for this site/drive -> not geolocated, skip
            dims = img["extended"].get("dimension", "")
            if "1280,960" not in dims.replace(" ", "") and "1296" not in dims and "1288" not in dims:
                continue
            fname = f"{img['imageid']}_800.jpg"
            dest = out_dir / fname
            if not dest.exists():
                if offline:
                    continue
                try:
                    fetch(img["image_files"]["medium"], dest, timeout=120)
                except Exception as exc:
                    log(f"image download failed {img['imageid']}: {exc}")
                    continue
            p = place(grid, rec)
            anchor = sites[req["site_id"]]
            lat_mid = math.radians((p["lat_deg"] + anchor["lat_deg"]) / 2.0)
            dx_ground = (p["x_m"] - anchor["x_m"]) * math.cos(lat_mid)
            dy_ground = p["y_m"] - anchor["y_m"]
            dist = math.hypot(dx_ground, dy_ground)
            photos.append({
                "photo_id": img["imageid"], "file": f"photos/{fname}", "sha256": sha256_file(dest),
                "site_id": req["site_id"], "site_name": sites[req["site_id"]]["name"],
                "instrument": img["camera"]["instrument"], "sol": img["sol"], "date_taken_utc": img.get("date_taken_utc"),
                "date_taken_mars": img.get("date_taken_mars"), "mast_azimuth_deg": img["extended"].get("mastAz"),
                "mast_elevation_deg": img["extended"].get("mastEl"), "caption": img.get("caption", "").strip(),
                "credit": img.get("credit", "NASA/JPL-Caltech"), "source_url": img.get("link"),
                "usage_terms": PHOTO_USAGE_TERMS,
                "full_res_url": img["image_files"].get("full_res"),
                "geolocation": {"basis": f"Rover site {rec['site']} / drive {rec['drive']} localization record matched to the image's site/drive metadata", **p,
                                "site_anchor_record": {"site": anchor["site"], "drive": anchor["drive"]},
                                "distance_to_site_anchor_m": round(dist, 1),
                                "distance_note": f"This image's site/drive record ({rec['site']}/{rec['drive']}) is ~{dist:.0f} m (ground distance, east-west scaled by cos(latitude)) from the site's anchor record ({anchor['site']}/{anchor['drive']}) used for '{anchor['name']}'."},
                "evidence_level": "NASA_OBSERVATION",
            })
            chosen += 1
    return photos


# ----------------------------------------------------------------------------- MEDA
def summarise_meda(meda_dir: Path, sol: int) -> dict | None:
    ps = next(meda_dir.glob(f"WE__{sol:04d}*DER_PS*P01.CSV"), None)
    tirs = next(meda_dir.glob(f"WE__{sol:04d}*DER_TIRS*P01.CSV"), None)
    if ps is None:
        return None

    def hourly(path: Path, column: str, quality_cols: list[str]) -> tuple[list[dict], dict]:
        sums: dict[int, list[float]] = {}
        q = {"rows_in_file": 0, "excluded_empty": 0, "excluded_unparseable_or_nonfinite": 0, "excluded_other_sol_or_bad_lmst": 0, "samples_used": 0,
             "columns": {c: {} for c in quality_cols}}
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                q["rows_in_file"] += 1
                v = row.get(column, "").strip()
                lmst = row["LMST"]
                if not v:
                    q["excluded_empty"] += 1
                    continue
                if "M" not in lmst:
                    q["excluded_other_sol_or_bad_lmst"] += 1
                    continue
                try:
                    val = float(v)
                except ValueError:
                    q["excluded_unparseable_or_nonfinite"] += 1
                    continue
                if not math.isfinite(val):
                    q["excluded_unparseable_or_nonfinite"] += 1
                    continue
                if not lmst.startswith(f"{sol:05d}M"):
                    q["excluded_other_sol_or_bad_lmst"] += 1
                    continue
                hour = int(lmst.split("M")[1][:2])
                sums.setdefault(hour, []).append(val)
                q["samples_used"] += 1
                for c in quality_cols:
                    cv = (row.get(c) or "").strip()
                    key = "empty" if not cv else cv
                    q["columns"][c][key] = q["columns"][c].get(key, 0) + 1
        return [{"lmst_hour": h, "mean": round(float(np.mean(v)), 3), "min": round(float(np.min(v)), 3), "max": round(float(np.max(v)), 3), "n": len(v)} for h, v in sorted(sums.items())], q

    filters = ("Samples kept: value column non-empty, parses as a finite float, and LMST string contains 'M' and starts with "
               f"'{sol:05d}M' (i.e. belongs to sol {sol}). No quality-flag, uncertainty or transducer filtering was applied; "
               "flag/uncertainty columns are summarised per series under 'quality' (counts over the samples used) so a reader can judge them.")
    ps_hourly, ps_q = hourly(ps, "PRESSURE", ["PRESSURE_UNCERTAINTY", "TRANSDUCER"])
    unc = ps_q["columns"]["PRESSURE_UNCERTAINTY"]
    ps_quality = {**{k: v for k, v in ps_q.items() if k != "columns"},
                  "pressure_uncertainty_present": ps_q["samples_used"] - unc.get("empty", 0),
                  "pressure_uncertainty_missing": unc.get("empty", 0),
                  "transducer_usage": ps_q["columns"]["TRANSDUCER"],
                  "label_definitions": {"PRESSURE_UNCERTAINTY": "Pressure uncertainty (PDS label)", "TRANSDUCER": "Transducer used: 1 / 2 (PDS label)"}}

    out = {
        "sol": sol, "evidence_level": "NASA_OBSERVATION", "scope": "Historical record measured at the Perseverance rover during sol 684 (Three Forks depot operations). Not a forecast and not a measurement at any future EVA time.",
        "series": [{"variable": "PRESSURE", "unit": "Pa", "instrument": "MEDA PS", "file": ps.name, "sha256": sha256_file(ps), "hourly": ps_hourly, "quality": ps_quality}],
        "aggregation": "Arithmetic mean/min/max per Local Mean Solar Time hour of the kept samples for this sol (see filters_applied). Quality flags were not applied as filters.",
        "filters_applied": filters,
        "product_level": "PDS 'data_derived_env' (derived, not calibrated) P01 files",
        "citation": "Rodriguez-Manfredi et al. (2021), Mars 2020 MEDA bundle, DOI 10.17189/1522849",
    }
    if tirs is not None:
        flag_cols = ["RSM_HEAD_OUTSIDE_TIRS_UPWARD_LOOKING_FOV", "WHEEL_OUTSIDE_TIRS_DOWNWARD_LOOKING_FOV", "SUN_OUTSIDE_TIRS_FOV", "ROVER_LOW_TILT",
                     "TIRS_GROUND_FOOTPRINT_NOT_IN_SHADOW", "ROVER_HGA_OFF", "SKYCAM_OFF", "ROVER_STILL"]
        t_hourly, t_q = hourly(tirs, "UPWARD_LW_IRRADIANCE", ["UPWARD_LW_UNCERTAINTY", *flag_cols])
        u = t_q["columns"].pop("UPWARD_LW_UNCERTAINTY")
        t_quality = {**{k: v for k, v in t_q.items() if k != "columns"},
                     "upward_lw_uncertainty_present": t_q["samples_used"] - u.get("empty", 0),
                     "upward_lw_uncertainty_missing": u.get("empty", 0),
                     "flag_counts": t_q["columns"],
                     "flag_definitions": {"RSM_HEAD_OUTSIDE_TIRS_UPWARD_LOOKING_FOV": "0 = RSM head obstructing upward FoV, 1 = outside",
                                          "WHEEL_OUTSIDE_TIRS_DOWNWARD_LOOKING_FOV": "0 = front right wheel obstructing downward FoV, 1 = outside",
                                          "SUN_OUTSIDE_TIRS_FOV": "0 = Sun in upward FoV, 1 = Sun outside FoV",
                                          "ROVER_LOW_TILT": "0 = tilt >= 20 deg, 1 = tilt <= 20 deg",
                                          "TIRS_GROUND_FOOTPRINT_NOT_IN_SHADOW": "0 = ground footprint shadowed by rover, 1 = not shadowed",
                                          "ROVER_HGA_OFF": "0 = HGA on, 1 = off", "SKYCAM_OFF": "0 = SkyCam on, 1 = off",
                                          "ROVER_STILL": "0 = rover moving, 1 = motionless"},
                     "flag_note": "Definitions from the PDS label (WE__0684...DER_TIRS...P01.xml). 'empty' = flag not given for that sample."}
        out["series"].append({"variable": "UPWARD_LW_IRRADIANCE", "unit": "W/m^2", "instrument": "MEDA TIRS", "file": tirs.name, "sha256": sha256_file(tirs), "hourly": t_hourly,
                              "quality": t_quality,
                              "note": "Upward long-wave irradiance from the ground; a proxy for ground warmth, not air temperature."})
    return out


# ----------------------------------------------------------------------------- source rasters / geotiffs
def source_raster_info(path: Path, sha: str | None, is_dem: bool) -> dict:
    with rasterio.open(path) as ds:
        unit_tag = ds.units[0] or ""
        info = {"file": str(path.relative_to(ROOT)), "sha256": sha, "bytes": path.stat().st_size, "width": ds.width, "height": ds.height,
                "band_count": ds.count, "dtype": ds.dtypes[0], "crs_name": pyproj.CRS.from_wkt(ds.crs.to_wkt()).name, "crs_wkt": ds.crs.to_wkt(),
                "transform": list(ds.transform)[:6], "bounds": {"left": ds.bounds.left, "bottom": ds.bounds.bottom, "right": ds.bounds.right, "top": ds.bounds.top},
                "nodata": None if ds.nodata is None else float(ds.nodata), "band_unit_tag": unit_tag, "band_tags": ds.tags(1), "dataset_tags": ds.tags()}
        if not unit_tag:
            info["band_unit_note"] = ("Band unit tag is empty in the GeoTIFF; units from publisher metadata: metres of elevation relative to the Mars geoid."
                                      if is_dem else "Band unit tag is empty in the GeoTIFF; per publisher metadata values are 8-bit DN (relative brightness).")
        a = ds.read(1)
    valid = np.isfinite(a) if a.dtype.kind == "f" else np.ones(a.shape, bool)
    if info["nodata"] is not None:
        valid &= ~np.isclose(a, info["nodata"]) if a.dtype.kind == "f" else a != info["nodata"]
    if a.dtype.kind == "f":
        valid &= a > -1e30
    info["valid_fraction"] = float(valid.mean())
    info["valid_percent"] = round(float(valid.mean() * 100), 4)
    key = "elevation" if is_dem else "dn"
    info[f"{key}_min"] = round(float(a[valid].min()), 3) if valid.any() else None
    info[f"{key}_max"] = round(float(a[valid].max()), 3) if valid.any() else None
    info["stats_method"] = "full-file read (every pixel), no decimation"
    return info


def write_geotiff(path: Path, arr: np.ndarray, transform: list[float], crs_wkt: str, dtype: str, nodata: float | None, tags: dict) -> None:
    profile = {"driver": "GTiff", "width": arr.shape[1], "height": arr.shape[0], "count": 1, "dtype": dtype, "crs": rasterio.crs.CRS.from_wkt(crs_wkt),
               "transform": rasterio.Affine(*transform), "compress": "deflate"}
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype(dtype), 1)
        dst.update_tags(**tags)
        if "units" in tags:
            dst.set_band_unit(1, tags["units"])


def finalise_feed_status(rec: dict, requests: list[dict], photos: list[dict], raw_dir: Path, out_dir: Path) -> dict:
    caches = [raw_dir / f"sol{r['sol']:04d}_{r['instrument']}.json" for r in requests]
    have_cache = [c.exists() for c in caches]
    for ph in photos:
        p = out_dir / ph["file"]
        if p.exists():
            rec["files"].append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size, "verified_against_config": False})
    wanted = sum(r["max_images"] for r in requests)
    n_photo_files = sum(1 for f in rec["files"] if f["path"].endswith(".jpg"))
    if all(have_cache) and n_photo_files >= wanted:
        rec["status"] = "AVAILABLE_VERIFIED"
    elif any(have_cache) or n_photo_files:
        rec["status"] = "PARTIAL"
    else:
        rec["status"] = "UNAVAILABLE"
    rec["note"] = f"{sum(have_cache)}/{len(caches)} cached feed JSON files and {n_photo_files}/{wanted} requested photos present and hashed"
    return rec


CATEGORY_MAP = {"topography": "topographic", "optical": "optical", "geology": "geological", "rover_localization": "surface_image",
                "rover_imagery": "surface_image", "atmosphere_history": "atmospheric"}
PHOTO_USAGE_TERMS = "NASA/JPL-Caltech raw images; NASA media guidelines: credit required, not endorsed"
LON_CONVENTION = "as used: east-positive; native CRS central meridian 0, domain -180..180"


def write_source_manifest(sources: list[dict], status: dict, source_raster: dict, manifest: dict, waypoints: list[dict], photos: list[dict],
                          meda: dict | None, geo_info: dict | None, geo_src_wkt: str | None, valid: np.ndarray, elev_check: dict) -> None:
    """data/source_manifest.json: one record per product, field names from
    EVA_Pathfinder_Handoff/config/dataset_manifest.example.json plus the extra 04 section 4 fields."""
    crop_valid_pct = float(valid.mean() * 100)
    dem, ortho = source_raster["dem"], source_raster["ortho"]
    lons = [w["lon"] for w in waypoints]
    lats = [w["lat"] for w in waypoints]
    sols = [w["sol"] for w in waypoints if w.get("sol") is not None]
    def raster_extent(r: dict) -> dict:
        b = r["bounds"]
        return {"projected_m": b, "lon_deg": [round(math.degrees(b["left"] / MARS_RADIUS_M), 6), round(math.degrees(b["right"] / MARS_RADIUS_M), 6)],
                "lat_deg": [round(math.degrees(b["bottom"] / MARS_RADIUS_M), 6), round(math.degrees(b["top"] / MARS_RADIUS_M), 6)],
                "study_area_crop": {"lon_deg": manifest["grid"]["lon_range_deg"], "lat_deg": manifest["grid"]["lat_range_deg"]}}
    per = {
        "usgs-m2020-trn-ctx-dtm-20m": {
            "agency": "USGS Astrogeology / NASA mission-derived data", "crs_wkt": dem["crs_wkt"], "coordinate_type": "projected (Equirectangular, metres) on Mars 2000 sphere; planetocentric latitude",
            "pixel_spacing_m": 20.0, "vertical_units": "m (relative to Mars geoid)", "extent": raster_extent(dem), "nodata": dem["nodata"],
            "time_coverage": "Not stated in the file; built from CTX stereo images acquired before the 2020 product release (Fergason et al. 2020).",
            "processing_steps": ["sha256 checked against config/sources.json", "CRS checked: Mars body, metre linear units, north-up affine (no rotation)",
                                 "window crop (dem_window in config/study_area.json) -> dem_crop.tif, float32, nodata preserved",
                                 "slope (central differences on projected metre cells, EW scaled by cos(lat)) -> slope_deg.tif / slope.png",
                                 "validity mask -> valid_coverage.tif", "hillshade/elevation PNGs for display"],
            "verification_notes": [f"Full-file read: {dem['width']}x{dem['height']} px, valid {dem['valid_percent']}%, elevation {dem['elevation_min']}..{dem['elevation_max']} m",
                                   f"Band unit tag: '{dem['band_unit_tag']}'" + (" (empty; units from publisher metadata)" if not dem["band_unit_tag"] else ""),
                                   f"Supporting cross-check (rover elevations derive from orbital-map localization): DEM minus rover geoid elevation median {elev_check.get('median_dem_minus_rover_m')} m over n={elev_check.get('n')} end-of-drive records"],
            "limitations": ["Originally created for landing-relative (Terrain Relative Navigation) navigation; not human on-foot safety data",
                            "Dataset may include a gap patched using other topography (MOLA topography per product name, as stated in handoff 04); no separate quality mask was provided, validity checked from the raster itself",
                            "20 m posts cannot resolve rocks, small scarps or soil strength",
                            f"crop is {crop_valid_pct:.0f}% valid ({crop_valid_pct:.4f}% of {valid.size} cells)"],
        },
        "usgs-m2020-trn-ctx-ortho-6m": {
            "agency": "USGS Astrogeology / NASA mission-derived data", "crs_wkt": ortho["crs_wkt"], "coordinate_type": "projected (Equirectangular, metres) on Mars 2000 sphere; planetocentric latitude",
            "pixel_spacing_m": 6.0, "vertical_units": None, "extent": raster_extent(ortho), "nodata": ortho["nodata"],
            "time_coverage": "Not stated in the file; CTX images acquired before the 2020 product release (Fergason et al. 2020).",
            "processing_steps": ["sha256 checked against config/sources.json", "CRS compared to DEM (identical WKT required)", "crop edge required to fall on an ortho pixel edge; grid origin difference vs DEM checked against alignment tolerance",
                                 "crop to the DEM bounds -> ortho_crop.tif (uint8, 6 m) and ortho.png", "gradient cross-correlation against DEM slope (coarse registration check)"],
            "verification_notes": [f"Full-file read: {ortho['width']}x{ortho['height']} px, non-nodata {ortho['valid_percent']}%, DN {ortho['dn_min']}..{ortho['dn_max']}",
                                   f"Grid origin difference vs DEM: {manifest['alignment']['ortho_dem_grid_origin_difference_m']} m; registration check best shift {manifest['alignment']['registration_check']['best_shift_cells']} cells (inconclusive, illumination-biased)"],
            "limitations": ["Relative brightness (8-bit DN), not calibrated reflectance", "Illumination from original CTX acquisitions", "Optical-topographic alignment checked by shared grid and a coarse correlation only"],
        },
        "usgs-sim3464-geology": {
            "agency": "USGS", "crs_wkt": geo_src_wkt, "coordinate_type": f"projected (source CRS: {geo_info['source_crs'] if geo_info else 'unknown'}); reprojected to the DEM CRS for rasterization",
            "pixel_spacing_m": None, "vertical_units": None, "extent": {"study_area_crop": {"lon_deg": manifest["grid"]["lon_range_deg"], "lat_deg": manifest["grid"]["lat_range_deg"]}, "coverage_fraction_of_crop": geo_info["coverage_fraction"] if geo_info else None},
            "nodata": "0 in geology_units.npy (unmapped)", "time_coverage": "Interpretive map published 2020",
            "processing_steps": ["sha256 checked", "GeoUnits_v1 layer read from Nili.gdb", "reprojected (pyproj) from map CRS to DEM CRS", "clipped and rasterized at 20 m -> geology_units.npy / geology.png"],
            "verification_notes": ["File integrity verified by sha256 (status AVAILABLE_VERIFIED refers to the file). The API reports this source PARTIAL because of alignment."],
            "limitations": ["Regional 1:75,000 interpretive map; not a detailed footpath hazard layer",
                            "USGS metadata: mapped on a semi-controlled CTX mosaic; random offsets of about 100-200 m from the surface operations CTX mosaic (alignment PARTIAL)"],
        },
        "usgs-sim3464-pamphlet": {
            "agency": "USGS", "crs_wkt": None, "coordinate_type": None, "pixel_spacing_m": None, "vertical_units": None, "extent": None, "nodata": None, "time_coverage": "Published 2020",
            "processing_steps": ["sha256 checked against config/sources.json (pinned)"], "verification_notes": ["Used only as a text reference for unit descriptions"],
            "limitations": ["Document only; unit notes in config/science_sites.json are short paraphrases"],
        },
        "nasa-m2020-waypoints": {
            "agency": "NASA/JPL-Caltech", "crs_wkt": None, "coordinate_type": "geographic lon/lat degrees on Mars 2000 sphere (planetocentric), east-positive; elev_geoid metres",
            "pixel_spacing_m": None, "vertical_units": "m (elev_geoid, relative to Mars geoid)",
            "extent": {"lon_deg": [min(lons), max(lons)], "lat_deg": [min(lats), max(lats)]}, "nodata": None,
            "time_coverage": f"sols {min(sols)}-{max(sols)} (snapshot of the public service downloaded 2026-11-15)" if sols else None,
            "processing_steps": ["sha256 checked against config/sources.json (pinned)", "site/drive records resolved (final='y' preferred)", "lon/lat -> Equirectangular metres with R=3396190 m -> local x/y"],
            "verification_notes": ["Elevation comparison against the DEM is a supporting cross-check only: rover localizations derive from orbital-map localization"],
            "limitations": ["Positions are rover localizations near (not exactly at) targets", "Localization is tied to orbital base maps; not independent ground truth", "Public service snapshot may be revised"],
            "category_note": "config category 'rover_localization' has no exact match in the 04 enum; mapped to the closest allowed value 'surface_image' (surface mission data).",
        },
        "nasa-m2020-raw-images-api": {
            "agency": "NASA/JPL-Caltech", "crs_wkt": None, "coordinate_type": "none per image; geolocated only via matching site/drive localization records",
            "pixel_spacing_m": None, "vertical_units": None, "extent": None, "nodata": None,
            "time_coverage": "; ".join(f"sol {ph['sol']} ({ph['date_taken_utc']} UTC)" for ph in photos) or None,
            "processing_steps": ["feed JSON cached per sol/instrument and hashed", "Full-frame NAVCAM_LEFT images matched to waypoint site/drive", "800 px browse JPEG downloaded and hashed"],
            "verification_notes": [status["nasa-m2020-raw-images-api"].get("note", "")] + [ph["geolocation"]["distance_note"] for ph in photos],
            "limitations": ["Raw (unprocessed) browse images", "Camera pointing (mast az/el) recorded but not used to project imagery", "Image location = rover position, not the imaged terrain"],
            "usage_terms": PHOTO_USAGE_TERMS,
        },
        "pds-m2020-meda-derived-sol0684": {
            "agency": "NASA PDS Atmospheres Node / MEDA team", "crs_wkt": None, "coordinate_type": "none (in-situ at rover position)", "pixel_spacing_m": None, "vertical_units": None, "extent": None, "nodata": "empty CSV cells",
            "time_coverage": "sol 684 (LMST 00:00-24:00)",
            "processing_steps": ["sha256 checked against config/sources.json", "hourly LMST mean/min/max", (meda or {}).get("filters_applied", "")],
            "verification_notes": ["Quality/uncertainty and flag columns summarised per series in meda.json 'quality'"],
            "limitations": ["Historical single-sol record; not a forecast", "Derived (data_derived_env) values, not calibrated", "No quality-flag filtering applied"],
        },
    }
    products = []
    for s in sources:
        sid = s["source_id"]
        st = status.get(sid, {"status": "UNAVAILABLE", "files": []})
        files = st.get("files", [])
        x = per.get(sid, {})
        single = len(files) == 1
        rec = {
            "id": sid, "name": s["title"], "agency": x.get("agency", s.get("producer")), "mission": s.get("mission"), "instrument": s.get("instrument"),
            "category": CATEGORY_MAP.get(s.get("category", ""), s.get("category")),
            "source_url": s.get("landing_page"), "direct_download_url": s.get("url"),
            "catalog_pages": s.get("catalog_pages", []), "doi": s.get("doi_url"),
            "product_identifier": s.get("product_identifier", Path(s["local_path"]).name or s["title"]),
            "citation": s.get("citation"), "usage_terms": x.get("usage_terms", s.get("license")), "license_checked": bool(s.get("license")),
            "catalog_version": "1.0",
            "source_acquired": bool(files), "acquired_date": "2026-11-15" if files else None,
            "local_path": s["local_path"] if files else None,
            "sha256": files[0]["sha256"] if single else None, "bytes": files[0]["bytes"] if single else sum(f["bytes"] for f in files) or None,
            "files": files,
            "status": st["status"], "target_body": "Mars",
            "crs_wkt": x.get("crs_wkt"), "coordinate_type": x.get("coordinate_type"), "longitude_convention": LON_CONVENTION,
            "pixel_spacing_m": x.get("pixel_spacing_m"), "vertical_units": x.get("vertical_units"), "units": s.get("units"),
            "extent": x.get("extent"), "nodata": x.get("nodata"), "time_coverage": x.get("time_coverage"),
            "processing_steps": x.get("processing_steps", []), "derived_from": [], "verification_notes": x.get("verification_notes", []),
            "limitations": x.get("limitations", []),
        }
        if "category_note" in x:
            rec["category_note"] = x["category_note"]
        if s.get("catalog_pages_note"):
            rec["catalog_pages_note"] = s["catalog_pages_note"]
        if not single and files:
            rec["sha256_note"] = "multiple files: see 'files' for each sha256; 'bytes' is the total"
        products.append(rec)
    doc = {"$comment": "Generated by scripts/prepare_data.py from config/sources.json and the actual files; field names follow EVA_Pathfinder_Handoff/config/dataset_manifest.example.json.",
           "catalog_version": "1.0", "generated_at": manifest["created_at"], "study_area_id": manifest["study_area_id"],
           "category_enum": ["optical", "topographic", "geological", "atmospheric", "surface_image"], "products": products}
    (ROOT / "data/source_manifest.json").write_text(json.dumps(doc, indent=2))


# ----------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="never download; use cached raw files only")
    args = ap.parse_args()

    sources = json.loads((ROOT / "config/sources.json").read_text())["sources"]
    by_id = {s["source_id"]: s for s in sources}
    area = json.loads((ROOT / "config/study_area.json").read_text())
    science = json.loads((ROOT / "config/science_sites.json").read_text())
    win = area["dem_window"]
    if win["width"] * win["height"] > area["max_cells"]:
        raise SystemExit("study area exceeds max_cells")

    status = ensure_sources(sources, args.offline)
    dem_src = ROOT / by_id[area["dem_source_id"]]["local_path"]
    if status[area["dem_source_id"]]["status"] != "AVAILABLE_VERIFIED":
        raise SystemExit("DEM unavailable: refusing to build a NASA-labelled study area without it")

    out = ROOT / "data/processed" / area["study_area_id"]
    out.mkdir(parents=True, exist_ok=True)
    created = now_iso()

    log("cropping DEM")
    dem, dem_meta = crop_dem(dem_src, win, out / "dem_crop.tif")
    grid = TerrainGrid.from_geotiff(out / "dem_crop.tif", dataset_id=area["dem_source_id"])
    slope = compute_slope_deg(grid.elevation_m, grid.dx_row_m, grid.dy_m)
    valid = np.isfinite(dem)

    log("cropping orthomosaic")
    ortho_src = ROOT / by_id[area["optical_source_id"]]["local_path"]
    ortho, ortho_meta = crop_ortho(ortho_src, dem_meta, dem.shape)
    origin_err = max(abs(v) for v in ortho_meta["grid_origin_difference_m"])
    if origin_err > area["alignment_tolerance_m"]:
        raise SystemExit(f"DATA_UNALIGNED: ortho/DEM grid origin differ by {origin_err} m")
    to_png_gray(ortho, out / "ortho.png", mask=ortho != (ortho_meta["nodata"] or 0))

    log("rendering derived overlays")
    hs = hillshade(grid)
    to_png_gray((np.nan_to_num(hs) * 255).astype(np.uint8), out / "hillshade.png", mask=valid)
    zmin, zmax = float(np.nanmin(dem)), float(np.nanmax(dem))
    elev_rgb = colormap((np.nan_to_num(dem, nan=zmin) - zmin) / (zmax - zmin), [(0, (40, 30, 80)), (0.35, (40, 120, 150)), (0.65, (200, 180, 90)), (1, (250, 245, 230))])
    Image.fromarray(np.dstack([elev_rgb, np.where(valid, 255, 0).astype(np.uint8)]), "RGBA").save(out / "elevation.png", optimize=True)
    slope_stops = [(0, (30, 60, 40)), (5 / 30, (90, 150, 70)), (10 / 30, (230, 200, 60)), (15 / 30, (230, 120, 40)), (20 / 30, (200, 40, 40)), (1, (120, 0, 60))]
    slope_rgb = colormap(np.clip(np.nan_to_num(slope) / 30.0, 0, 1), slope_stops)
    Image.fromarray(np.dstack([slope_rgb, np.where(np.isfinite(slope), 255, 0).astype(np.uint8)]), "RGBA").save(out / "slope.png", optimize=True)

    log("preparing geology")
    geo_info = None
    if status["usgs-sim3464-geology"]["status"] == "AVAILABLE_VERIFIED":
        geo_info = prepare_geology(ROOT / by_id["usgs-sim3464-geology"]["local_path"], ROOT / "data/raw/usgs_sim3464", grid, out, science["geology_unit_notes"])

    log("resolving waypoints")
    waypoints = load_waypoints(ROOT / by_id["nasa-m2020-waypoints"]["local_path"])
    habitat = {**{k: v for k, v in science["habitat"].items() if k != "rover_record"}, **place(grid, resolve_record(waypoints, **science["habitat"]["rover_record"]))}
    sites = []
    geo_raster = np.load(out / "geology_units.npy") if geo_info else None
    geo_lookup = {u["code"]: u for u in geo_info["units"]} if geo_info else {}
    for s in science["sites"] + science.get("sample_sites", []):
        if "rover_record" in s:
            p = place_any(grid, resolve_record(waypoints, **s["rover_record"]))
        else:
            rec = dict(resolve_by_sol(waypoints, int(s["rover_sol"])))
            rp = s.get("report_position")
            if rp:  # NASA Initial Report coordinates are the authoritative position for the coring
                rec.update({"lon": rp["lon"], "lat": rp["lat"], "elev_geoid": rp.get("elev_m", rec.get("elev_geoid"))})
            p = place_any(grid, rec)
            p["sample_sol"] = int(s["rover_sol"])
            p["position_source"] = rp["source"] if rp else "NASA rover localization on or before the coring sol"
        entry = {**{k: v for k, v in s.items() if k not in ("rover_record", "rover_sol", "report_position")}, **p}
        if geo_raster is not None and p["cell"] is not None:
            code = int(geo_raster[p["cell"][0], p["cell"][1]])
            u = geo_lookup.get(code)
            entry["mapped_geologic_unit"] = {"symbol": u["symbol"], "name": u["name"], "caveat": "Regional context only: SIM 3464 units may be offset 100-200 m from this base map."} if u else None
        sites.append(entry)
    elev_check = elevation_check(grid, waypoints)
    traverse = traverse_polyline(grid, waypoints)

    log("writing whole-mosaic context image")
    context = write_context_image(ortho_src, out / "context_ortho.jpg")

    log("estimating optical/DEM registration")
    reg = registration_check(grid, ortho, ortho_meta["ratio"])

    log("fetching geolocated rover photos")
    photos = fetch_photos(grid, waypoints, science["photos"], {s["id"]: s for s in sites}, ROOT / "data/raw/m2020_raw_images", out / "photos", args.offline)

    log("summarising MEDA record")
    meda = summarise_meda(ROOT / "data/raw/m2020_meda", 684)

    (out / "science_sites.json").write_text(json.dumps({"habitat": habitat, "sites": sites}, indent=2))
    (out / "rover_traverse.json").write_text(json.dumps({"source_id": "nasa-m2020-waypoints", "points": traverse}, indent=1))
    (out / "photos.json").write_text(json.dumps(photos, indent=2))
    (out / "meda.json").write_text(json.dumps(meda, indent=2) if meda else "null")
    geo_src_wkt = geo_info.pop("_source_crs_wkt", None) if geo_info else None
    if geo_info:
        (out / "geology_units.json").write_text(json.dumps(geo_info, indent=2))

    log("writing georeferenced GeoTIFFs")
    write_geotiff(out / "slope_deg.tif", np.where(np.isfinite(slope), slope, np.nan), dem_meta["transform"], dem_meta["crs_wkt"], "float32", float("nan"),
                  {"units": "degrees", "description": "Slope from dem_crop.tif, central differences on projected metre cells (compute_slope_deg); NaN = no data"})
    write_geotiff(out / "valid_coverage.tif", valid.astype(np.uint8), dem_meta["transform"], dem_meta["crs_wkt"], "uint8", None,
                  {"description": "1 = valid DEM cell, 0 = no data"})
    write_geotiff(out / "ortho_crop.tif", ortho, ortho_meta["transform"], dem_meta["crs_wkt"], "uint8", float(ortho_meta["nodata"] or 0),
                  {"units": "DN", "description": "CTX orthomosaic crop, 6 m, same bounds as dem_crop.tif; 8-bit relative brightness"})
    for tif, tr in (("slope_deg.tif", dem_meta["transform"]), ("valid_coverage.tif", dem_meta["transform"]), ("ortho_crop.tif", ortho_meta["transform"])):
        with rasterio.open(out / tif) as chk:
            if chk.crs.to_wkt() != dem_meta["crs_wkt"] or any(abs(x - y) > 1e-6 for x, y in zip(list(chk.transform)[:6], tr)):
                raise SystemExit(f"{tif}: written CRS/transform does not match the intended grid")

    log("recording source raster metadata")
    source_raster = {
        "dem": source_raster_info(dem_src, status[area["dem_source_id"]]["files"][0]["sha256"], True),
        "ortho": source_raster_info(ortho_src, status[area["optical_source_id"]]["files"][0]["sha256"], False),
    }
    source_raster["dem"]["crop_nodata_written"] = float(np.float32(-3.4028226550889045e38))
    source_raster["dem"]["crop_nodata_note"] = "dem_crop.tif stores nodata as float32 -3.4028226550889045e38 (same value as the source); the app reads it as NaN."
    status["nasa-m2020-raw-images-api"] = finalise_feed_status(status["nasa-m2020-raw-images-api"], science["photos"], photos, ROOT / "data/raw/m2020_raw_images", out)

    def art(aid: str, fname: str, src_ids: list[str], level: str, units: str, limitations: str, res: float | None = 20.0) -> dict:
        p = out / fname
        return {"artifact_id": aid, "file": fname, "source_ids": src_ids, "processing_version": PROCESSING_VERSION,
                "checksum_sha256": sha256_file(p) if p.exists() else None, "created_at": created, "crs": "Equirectangular Mars 2000 Sphere IAU (R=3396190 m), lat_ts=0, lon_0=0",
                "resolution_m": res, "nodata_policy": "nodata -> transparent / unknown; never navigable by default", "units": units, "evidence_level": level, "limitations": limitations}

    x0_e, ytop_n = grid.origin_e_m, grid.origin_n_m
    lat_c = math.degrees((ytop_n - grid.height * grid.res_m / 2) / MARS_RADIUS_M)
    manifest = {
        "study_area_id": area["study_area_id"], "name": area["name"], "body": "Mars", "created_at": created, "processing_version": PROCESSING_VERSION,
        "context": context,
        "crs": {"name": "Equirectangular Mars 2000 Sphere IAU", "wkt": grid.crs_wkt, "sphere_radius_m": MARS_RADIUS_M, "latitude_convention": "planetocentric (sphere: identical to planetographic)", "longitude_convention": "east-positive; native CRS central meridian 0, domain -180..180 (values here 77.3-77.5 E)", "lat_true_scale_deg": 0.0,
                "local_frame": "x_m = easting - origin_easting; y_m = northing - origin_northing_bottom. Projected metres. East-west ground distance = projected distance * cos(latitude).",
                "east_west_scale_factor_at_center": round(math.cos(math.radians(lat_c)), 6)},
        "grid": {"width": grid.width, "height": grid.height, "res_m": grid.res_m, "origin_easting_m": x0_e, "origin_northing_top_m": ytop_n, "origin_northing_bottom_m": ytop_n - grid.height * grid.res_m,
                 "dem_window_in_source": win, "lon_range_deg": [round(math.degrees(x0_e / MARS_RADIUS_M), 6), round(math.degrees((x0_e + grid.width * grid.res_m) / MARS_RADIUS_M), 6)],
                 "lat_range_deg": [round(math.degrees((ytop_n - grid.height * grid.res_m) / MARS_RADIUS_M), 6), round(math.degrees(ytop_n / MARS_RADIUS_M), 6)], "north_up_verified": True},
        "dem_stats": {"valid_fraction": float(valid.mean()), "min_m": round(zmin, 2), "max_m": round(zmax, 2), "mean_m": round(float(np.nanmean(dem)), 2),
                      "slope_deg_p50": round(float(np.nanpercentile(slope, 50)), 2), "slope_deg_p95": round(float(np.nanpercentile(slope, 95)), 2), "slope_deg_max": round(float(np.nanmax(slope)), 2)},
        "alignment": {"ortho_dem_same_crs": True, "ortho_dem_grid_origin_difference_m": ortho_meta["grid_origin_difference_m"], "ortho_pixel_m": ortho_meta["pixel_m"],
                      "ortho_crop_px": [int(ortho.shape[1]), int(ortho.shape[0])], "registration_check": reg, "dem_vs_rover_elevation": elev_check,
                      "geology_status": "PARTIAL" if geo_info else "UNAVAILABLE", "geology_note": by_id["usgs-sim3464-geology"]["known_limitation"]},
        "source_status": status,
        "sources": sources,
        "artifacts": [
            {**art("dem-crop", "dem_crop.tif", ["usgs-m2020-trn-ctx-dtm-20m"], "NASA_OBSERVATION", "m (geoid)", "20 m posts: cannot resolve rocks, small scarps or soil strength."),
             "nodata_value": source_raster["dem"]["crop_nodata_written"]},
            art("ortho", "ortho.png", ["usgs-m2020-trn-ctx-ortho-6m"], "NASA_OBSERVATION", "DN 0-255 (unstretched)", "Relative brightness only; illumination from the original CTX acquisitions.", 6.0),
            art("context-ortho", "context_ortho.jpg", ["usgs-m2020-trn-ctx-ortho-6m"], "NASA_OBSERVATION", "DN 0-255, JPEG", "Whole source mosaic block-averaged to 12 m for display; lossy JPEG; not used for routing.", 12.0),
            art("hillshade", "hillshade.png", ["usgs-m2020-trn-ctx-dtm-20m"], "DERIVED", "relative shading", "Synthetic illumination az 315, alt 45."),
            art("elevation", "elevation.png", ["usgs-m2020-trn-ctx-dtm-20m"], "DERIVED", f"colour ramp {zmin:.0f} to {zmax:.0f} m", "Visualization only."),
            art("slope", "slope.png", ["usgs-m2020-trn-ctx-dtm-20m"], "DERIVED", "degrees, colour ramp 0-30", "Central-difference slope over 40 m baselines; one-sided at borders."),
            art("geology", "geology.png", ["usgs-sim3464-geology"], "DERIVED", "categorical", "Rasterized interpretive map; 100-200 m offsets vs base map per USGS metadata."),
            art("science-sites", "science_sites.json", ["nasa-m2020-waypoints"], "NASA_OBSERVATION", "local m + lon/lat deg", "Positions are rover localizations near (not exactly at) targets.", None),
            art("rover-traverse", "rover_traverse.json", ["nasa-m2020-waypoints"], "NASA_OBSERVATION", "local m", "End-of-drive points only.", None),
            art("photos", "photos.json", ["nasa-m2020-raw-images-api", "nasa-m2020-waypoints"], "NASA_OBSERVATION", "-", "Raw (unprocessed) Navcam browse images.", None),
            art("meda", "meda.json", ["pds-m2020-meda-derived-sol0684"], "NASA_OBSERVATION", "Pa, W/m^2", "Historical single-sol record.", None),
            {**art("slope-deg-tif", "slope_deg.tif", ["usgs-m2020-trn-ctx-dtm-20m"], "DERIVED", "degrees (float32)", "Central-difference slope over 40 m baselines; one-sided at borders. Same grid/CRS/transform as dem_crop.tif."),
             "nodata_value": "NaN"},
            {**art("valid-coverage", "valid_coverage.tif", ["usgs-m2020-trn-ctx-dtm-20m"], "DERIVED", "uint8 mask (1 valid, 0 no data)", "DEM validity only; says nothing about surface safety."),
             "nodata_value": None},
            {**art("ortho-crop", "ortho_crop.tif", ["usgs-m2020-trn-ctx-ortho-6m"], "NASA_OBSERVATION", "DN 0-255 (uint8, unstretched)", "Relative brightness only; illumination from the original CTX acquisitions.", 6.0),
             "nodata_value": float(ortho_meta["nodata"] or 0)},
        ],
        "source_raster": source_raster,
        "name_mapping": {
            "_note": "Handoff 04 section 3 expected names -> files actually written in data/processed/<study_area_id>/ (existing names kept so the app keeps working).",
            "jezero_dem_crop.tif": "dem_crop.tif",
            "jezero_optical_crop.*": "ortho_crop.tif (georeferenced GeoTIFF); ortho.png is the display copy",
            "slope_deg.tif": "slope_deg.tif",
            "valid_coverage.tif": "valid_coverage.tif",
            "route_cost.tif": "computed per request, not persisted",
            "study_area_metadata.json": "manifest.json",
            "science_sites.json": "science_sites.json",
            "observations.json": "photos.json + meda.json",
            "docs/DATA_PROVENANCE.md": "docs/DATA_PROVENANCE.md (maintained outside the pipeline)",
            "data/processed/ (flat)": f"data/processed/{area['study_area_id']}/ (one folder per study area)",
        },
        "deviations": [
            {"topic": "study_area_size",
             "handoff_guidance": "04 section 2 suggests a 2-4 km wide DEM-valid region",
             "actual": f"{grid.width * grid.res_m / 1000:.1f} x {grid.height * grid.res_m / 1000:.1f} km projected ({grid.width} x {grid.height} cells at {grid.res_m:.0f} m)",
             "reason": ("The window must contain the hypothetical habitat at the Octavia E. Butler landing localization (site 3 / drive 0), the Wildcat Ridge delta-front "
                        "target (site 26 / drive 1222) and the Three Forks sample depot (site 32 / drive 250). These published rover localizations are several km apart, "
                        "so a 2-4 km window cannot hold all three. The window is still 100% DEM-valid, inside optical coverage, and within max_cells."),
             "window_changed": False},
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    write_source_manifest(sources, status, source_raster, manifest, waypoints, photos, meda, geo_info, geo_src_wkt, valid, elev_check)
    log(f"done -> {out.relative_to(ROOT)}")
    log(f"DEM {grid.width}x{grid.height} valid={valid.mean():.4f} elev {zmin:.1f}..{zmax:.1f} m; rover elevation check {elev_check}")
    log(f"registration {reg['best_shift_cells']} r={reg['best_correlation']} (zero-shift r={reg['zero_shift_correlation']}); photos={len(photos)}; geology units={len(geo_info['units']) if geo_info else 0}")


if __name__ == "__main__":
    main()
