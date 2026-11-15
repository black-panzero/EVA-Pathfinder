# NASA Space Apps 2026: submission form answers (ready to paste)

## Project Name
Project Midgardians: EVA Pathfinder

## Summary (≈175 words, ≈1,200 characters)
EVA Pathfinder is a hyperlocal "Marswalk" map and mission-safety planner built on real NASA and USGS data of Jezero Crater, where Perseverance is exploring. We combined a 20 m orbital elevation model, a 6 m orbital image mosaic, the USGS geologic map, Perseverance's recorded positions and photos, and historical MEDA weather data into one aligned 8 × 4.5 km map. An astronaut or mission planner places a habitat, chooses science stops such as Wildcat Ridge (where Perseverance found organic-rich rock) and sets limits for slope, time and supplies. The planner computes two routes, a shortest one and a gentler terrain-aware one, and checks that the whole round trip, including getting home, fits within the budget plus a safety reserve. In the Contingency Lab a blocked path can be simulated mid-walk: the system replans from the crew's current position with the resources already used, and clearly says when no safe return exists. Every number is labelled as observed, derived, assumed or simulated, with links to its source. It is a research prototype, not a certified navigation tool.

## Project Demonstration
https://<ADD YOUR PUBLIC SLIDES OR VIDEO LINK>

## Project
https://<ADD YOUR PUBLIC GITHUB REPO LINK>

## Project Details

**What it does**
EVA Pathfinder answers one question for a crew on a Mars surface walk (EVA): "Can we get there, do the science, and still get home safely?" It joins real orbital terrain, geology and rover observations into one local map, then plans and checks a round-trip walk against time and supply limits.

**How it works**
1. **Real, aligned data.** A Python pipeline downloads the USGS Mars 2020 CTX elevation model (20 m) and image mosaic (6 m), verifies checksums and crops a study area from the Jezero crater floor to the delta front. Both products share one Mars map projection and grid. As an independent check we compared our elevations with 252 elevations recorded by Perseverance itself: the median difference is 1.55 m. The USGS geologic map (SIM 3464) is reprojected onto the same grid and shown as regional context, because USGS documents 100–200 m offsets for it. Habitat and science-site coordinates come from Perseverance's recorded parking positions, not from guesses. Rover photos are placed only where their site/drive metadata matches a recorded position.
2. **Pathfinder.** Each 20 m cell is a square on a board. Cells steeper than the slope limit, or without data, are off-limits. An A* search finds two routes: the shortest one, and a terrain-aware one that prefers gentler ground. Distances are true ground metres on Mars, corrected for latitude; no Earth map projections are used.
3. **Guardian.** The walk (habitat → science stops → habitat) is converted into time, with extra time for climbing, so out and back differ. Science time and supply use are added. The plan is FEASIBLE only if the total fits within the budget after a safety reserve. Otherwise it is INFEASIBLE with a plain reason such as "insufficient time" or "slope exceeds limit".
4. **Contingency Lab.** The user moves a mission-progress slider and drops a simulated blocked zone. The system finds where the crew is, counts what they have already used, and replans home on a copy of the map. If the habitat is cut off, it reports "no feasible return" instead of drawing a fake route.
5. **Evidence trail.** Every value carries a label (NASA observation, derived, illustrative model, simulated or unknown) with source links, checksums and a downloadable JSON report.

**Example result (real terrain).** From the Perseverance landing site to Wildcat Ridge and back: the shortest route is 5.75 km with a 15.0° steepest slope; the terrain-aware route is 5.97 km with a 12.5° steepest slope. The trip takes 216 of 315 usable minutes, so it is FEASIBLE. With a 50 % reserve it becomes INFEASIBLE. A simulated blocked zone on the return path produces a detour; enclosing the habitat produces an honest "no feasible return".

**Benefits and impact**
- Mission planners see terrain, science value and "can we get home?" in one place, instead of switching between separate maps and spreadsheets.
- Return-aware checks and replanning from the crew's current position target the riskiest part of a surface walk: being far from the habitat when something goes wrong.
- Honest labelling of observed vs assumed vs simulated data builds trust and shows exactly what the map can and cannot know. A 20 m elevation model cannot see rocks, so this is a planning aid, not a certified navigation system.
- The same approach can feed rover waypoint planning and future higher-resolution (HiRISE) maps.

**Tools and technologies**
Python 3.12 (FastAPI, Pydantic, NumPy, rasterio/GDAL, pyproj, Shapely, pyogrio), TypeScript, React, Vite, Leaflet (flat map coordinates with no Earth projection), pytest, Vitest and Playwright. It runs on an ordinary laptop CPU (tested on an Intel i5 with 8 GB RAM), with no GPU, cloud service or paid API, and works offline once the data is downloaded. The engine is deterministic and uses no AI at runtime.

**What makes it creative**
- Every coordinate is tied to a real rover record.
- Our elevation data is cross-checked against the rover's own measurements.
- The mid-walk emergency replans from the crew's actual position and remaining supplies.
- The system admits failure openly instead of showing a reassuring fake route.

**Factors we considered**
- Scientific honesty: no invented data; clear labels; known map offsets disclosed.
- Correct Mars geometry: Mars sphere, latitude-corrected distances.
- Safety: hard slope limits, unknown terrain blocked by default, and raising the reserve can never turn an unsafe plan into a safe one (tested).
- Accessibility: text status as well as colour, keyboard-usable controls, mobile layout.
- Reproducibility: checksums, a run manifest, and 58 automated tests.

## Use of Super Intelligence (SI)
Select the options for **code** and **data/text** (documentation). Do NOT select images, video or audio: none of our visuals are AI-generated; all map imagery is NASA/USGS data and all screenshots are captures of the running app.

Disclosure text (already in the repository's README.md and NOTICE.md; paste wherever a description is requested):
> The software code, data-processing pipeline, tests and documentation were written with an AI coding assistant (Claude Code by Anthropic), working from specification documents that were also developed with AI assistance. The team reviewed, ran and validated the results. No AI-generated images, video or audio are used. The route-planning and feasibility engine uses no AI at runtime.

## NASA Data
| Link Text | Link Url |
|---|---|
| Mars 2020 Terrain Relative Navigation CTX DTM Mosaic (20 m) – USGS/NASA | https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_dtm_mosaic |
| Mars 2020 Terrain Relative Navigation CTX Orthomosaic (6 m) – USGS/NASA | https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_orthorectified_image_mosaic |
| Mars 2020 Perseverance "Where is the Rover" waypoints | https://mars.nasa.gov/mars2020/mission/where-is-the-rover/ |
| Mars 2020 Perseverance Raw Images (Navcam) | https://mars.nasa.gov/mars2020/multimedia/raw-images/ |
| Mars 2020 MEDA environmental data – NASA PDS Atmospheres Node | https://atmos.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/ |
| NASA/JPL: Perseverance Investigates Geologically Rich Mars Terrain (Wildcat Ridge) | https://www.jpl.nasa.gov/news/nasas-perseverance-rover-investigates-geologically-rich-mars-terrain/ |
| NASA/JPL PIA24929: Rock Cores From Wildcat Ridge | https://www.jpl.nasa.gov/images/pia24929-perseverance-rock-cores-from-wildcat-ridge/ |
| NASA/JPL: Perseverance Deposits First Sample (Three Forks depot) | https://www.jpl.nasa.gov/news/nasas-perseverance-rover-deposits-first-sample-on-mars-surface |
| NASA/JPL PIA25682: Three Forks Sample Depot Map | https://www.jpl.nasa.gov/images/pia25682-perseverances-three-forks-sample-depot-map/ |

## Space Agency Partner & Other Data
| Link Text | Link Url |
|---|---|
| USGS SIM 3464 Geologic Map of Jezero Crater and Nili Planum (Sun & Stack, 2020) | https://doi.org/10.3133/sim3464 |
| Claude Code (Anthropic) – AI coding assistant | https://claude.com/claude-code |
| FastAPI (MIT) | https://github.com/fastapi/fastapi |
| Pydantic (MIT) | https://github.com/pydantic/pydantic |
| NumPy (BSD) | https://github.com/numpy/numpy |
| rasterio (BSD) / GDAL (MIT) | https://github.com/rasterio/rasterio |
| pyproj (MIT) | https://github.com/pyproj4/pyproj |
| Shapely (BSD) | https://github.com/shapely/shapely |
| pyogrio (MIT) | https://github.com/geopandas/pyogrio |
| Pillow (MIT-CMU) | https://github.com/python-pillow/Pillow |
| React (MIT) | https://github.com/facebook/react |
| Vite (MIT) | https://github.com/vitejs/vite |
| Leaflet (BSD-2) | https://github.com/Leaflet/Leaflet |
| Playwright (Apache-2.0) | https://github.com/microsoft/playwright |
| pytest (MIT) / Vitest (MIT) | https://github.com/pytest-dev/pytest |

## Project Submission Verification
Tick these yourselves, and only if they are true:
- **Terms and Conditions:** read the 2026 Submission Guide first.
- **All Work is Original:** every external resource is listed above. The concept and code were made with AI assistance, so the team must be comfortable owning, explaining and defending the idea before confirming.
