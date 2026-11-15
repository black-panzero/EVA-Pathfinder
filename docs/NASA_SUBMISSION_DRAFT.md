# NASA Space Apps Challenge 2026: submission draft

**Challenge:** Interplanetary Survival Guide: Martian Map
**Project:** EVA Pathfinder / EVA Guardian

> **For the human team. Read first.**
> - The official 2026 submission guide is now in `EVA_Pathfinder_Handoff/references/` and was checked by an audit on 2026-11-16 (see `docs/DECISIONS.md`).
> - The guide (as summarised in the build prompt) says AI tools may speed up building but must not originate the team's solution concept. The concept documents and this software were produced with AI assistance. **The team must independently own, validate and be able to defend the idea before claiming it as original.** Do not sign an originality statement unless it is true.
> - No public repository, demo URL, video or slide deck has been published by the agent. Fill those links in only after you create and check them.

## Project name
EVA Pathfinder (team: Midgardians)

## High-level summary (draft, ~150 words)
EVA Pathfinder is a hyperlocal Marswalk map of a real 8 × 4.5 km area of Jezero Crater. It combines the USGS Mars 2020 CTX 20 m terrain model, the 6 m CTX orthomosaic, the USGS geologic map (SIM 3464), Perseverance rover localizations, geolocated Navcam photos and a historical MEDA record. EVA Guardian plans walking routes between a simulated habitat and documented science sites (Wildcat Ridge on the delta front, the Three Forks sample depot). It compares a shortest feasible route with a terrain-aware route and checks the whole round trip against a time and consumable budget with a reserve. In the Contingency Lab a planner can inject a simulated blocked zone mid-mission. The engine replans from the crew's current position with the resources already spent, and reports an honest "no feasible return" when none exists. Every number is labelled as observed, derived, assumed or simulated, and linked to its source.

## Project demonstration
- Option A: up to 7 slides. Storyboard below. Make them from the screenshots in `docs/screenshots/`.
- Option B: a 30 s video following `DEMO_RUNBOOK.md` ("30-second video cut").
- Link: **[team to add after upload]**

## Project repository
**[team to add after creating the public repo and choosing a licence]**

## Use of NASA data and resources
| Resource | How it is used |
|---|---|
| USGS / NASA Mars 2020 TRN CTX DTM mosaic, 20 m (MRO CTX) | Elevation, slope, routing costs, elevation profiles |
| USGS / NASA Mars 2020 TRN CTX orthomosaic, 6 m | Optical base map, aligned to the DTM grid |
| USGS SIM 3464 geologic map of Jezero crater and Nili Planum (Sun & Stack 2020) | Geologic unit overlay and units crossed by each route (regional context) |
| NASA/JPL Mars 2020 waypoint service | Coordinates of the habitat and science sites; independent check of the DEM (median 1.55 m absolute difference over 252 rover positions) |
| NASA/JPL Mars 2020 raw images (Navcam) | Ground-view photos at science sites, geolocated by site/drive |
| NASA PDS MEDA derived data, sol 684 | Historical surface pressure and long-wave irradiance at the depot |
| NASA/JPL news releases (Wildcat Ridge, Three Forks depot) | Science context for waypoints |

## Space agency partner data
None used.

## Tools, languages, hardware
Python 3.12 (FastAPI, Pydantic, NumPy, rasterio/GDAL, pyproj, shapely, pyogrio), TypeScript + React + Vite, Leaflet (CRS.Simple, no Web Mercator), Vitest, pytest, Playwright. Runs locally on a CPU-only laptop (tested on an Intel i5-7300U); no GPU, cloud or paid APIs.

## Use of artificial intelligence (disclosure, accurate as of this build)
- The software code, data pipeline, tests and documentation in the repository were written by an AI coding agent (Claude Code by Anthropic) from specification documents that were themselves developed with AI assistance.
- No AI-generated images, video, audio or maps are used. Map imagery is NASA/USGS data, and screenshots are captures of the running application.
- The navigation and feasibility engine uses no AI or LLM at runtime. It is deterministic A* and arithmetic.
- **[Team: describe your own human contributions, validation and any further AI use here.]**

## Seven-slide storyboard (7 slides in total, title slide included; guide limit is 7)
1. **Title.** EVA Pathfinder · Team Midgardians · team member names **[team to add]** · challenge "Interplanetary Survival Guide: Martian Map" (NASA Space Apps 2026). One line: "A Marswalk planner that always checks the way home". Small footer: "Software written with AI assistance (Claude Code); all imagery NASA/USGS".
2. **Problem and data.** An astronaut on a Marswalk needs one local view that connects terrain, science targets and "can we still get home?". The map is real Jezero data on one grid: CTX DTM 20 m, ortho 6 m and USGS geology (regional context, ±100-200 m). Rover elevations match the DEM within a 1.55 m median. Images: `01_plan_overview.png`, `02_slope_layer.png`.
3. **Computed routes.** Shortest (5.75 km round trip, max 15.0°) vs terrain-aware (5.97 km, max 12.5°) under the same hard limits, with the elevation profile. Image: `04_route_comparison.png`; feasibility: `05_feasibility.png`.
4. **Feasibility.** Round-trip time and supplies against a planning reserve, with plain reasons (`INSUFFICIENT_TIME`, `SLOPE_EXCEEDS_LIMIT`). Raising the reserve never makes a plan feasible.
5. **Contingency Lab.** A simulated blocked zone mid-return is replanned from the crew position with the resources already spent. An enclosed habitat gives an honest "no feasible return". Images: `06_contingency_replan.png`, `07_no_feasible_return.png`.
6. **Evidence trail.** Observed / derived / assumed / simulated / unknown labels, rover photos tied to site/drive, MEDA history and checksums. Images: `08_rover_photos.png`, `10_data_sources.png`.
7. **Limits and future.** A 20 m DEM cannot see rocks; this is not flight-certified. Next steps: HiRISE-scale terrain, rover ground-view registration, ROS 2 waypoint export. Links: live app and repository (after verification).

## 30-second video script (alternative to slides; guide limit 30 s)
- **0:00-0:05**: "We are team Midgardians. This is EVA Pathfinder, for the Interplanetary Survival Guide: Martian Map challenge." Show the title card.
- **0:05-0:12**: Real Jezero map. Toggle Slope and show both routes. Caption "Real NASA/USGS terrain · computed, not drawn".
- **0:12-0:18**: Feasibility step showing Feasible, 99 min return margin. Caption "Round trip checked, including the way home".
- **0:18-0:26**: Contingency: run the scenario (detour), then the enclosed habitat ("no feasible return"). Caption "Simulated event · honest result".
- **0:26-0:30**: "Next: higher-resolution terrain and rover waypoints. Research prototype, not flight-certified." Show the URL card.
- Measure the final export; it must be 30 s or less. Put the AI disclosure in the video description.

## References
- Fergason, R.L., et al. (2020). Mars 2020 Terrain Relative Navigation flight product generation: digital terrain model and orthorectified image mosaic. 51st LPSC. Products: https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_dtm_mosaic and https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_orthorectified_image_mosaic
- Sun, V.Z., and Stack, K.M. (2020). Geologic map of Jezero crater and the Nili Planum region, Mars. USGS SIM 3464. https://doi.org/10.3133/sim3464
- NASA/JPL (15 Sept 2022). NASA's Perseverance Rover Investigates Geologically Rich Mars Terrain. https://www.jpl.nasa.gov/news/nasas-perseverance-rover-investigates-geologically-rich-mars-terrain/
- NASA/JPL. PIA24929: Perseverance Rock Cores From Wildcat Ridge. https://www.jpl.nasa.gov/images/pia24929-perseverance-rock-cores-from-wildcat-ridge/
- NASA/JPL (Dec 2022). NASA's Perseverance Rover Deposits First Sample on Mars Surface. https://www.jpl.nasa.gov/news/nasas-perseverance-rover-deposits-first-sample-on-mars-surface
- NASA/JPL. PIA25682: Perseverance's Three Forks Sample Depot Map. https://www.jpl.nasa.gov/images/pia25682-perseverances-three-forks-sample-depot-map/
- NASA/JPL. Mars 2020 "Where is the rover" waypoint service. https://mars.nasa.gov/mars2020/mission/where-is-the-rover/
- Mars 2020 MEDA bundle, NASA PDS Atmospheres Node. https://atmos.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/
- NASA/JPL-Caltech Mars 2020 raw images. https://mars.nasa.gov/mars2020/multimedia/raw-images/
