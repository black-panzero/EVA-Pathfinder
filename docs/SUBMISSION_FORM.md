# NASA Space Apps 2026: submission form answers (ready to paste)

Checked against `EVA_Pathfinder_Handoff/03_NASA_RULES_AND_SUBMISSION.md`, `07_SUBMISSION_CONTENT_TEMPLATES.md` and the official 2026 Submission Guide PDF (audit 2026-11-16). Team: **Midgardians**.

## Project Name
EVA Pathfinder

## Summary (≈170 words)
EVA Pathfinder is a hyperlocal Marswalk map and return-aware planner built on real NASA and USGS data of Jezero Crater, where Perseverance is exploring. We combined a 20 m orbital elevation model, a 6 m orbital image mosaic, the USGS geologic map, Perseverance's recorded positions and photos, and historical MEDA weather data into one aligned 8 × 4.5 km map. A mission planner places a habitat, chooses science stops such as Wildcat Ridge (where Perseverance found organic-rich rock) and sets limits for slope, time and supplies. The planner computes two routes, a shortest one and a gentler terrain-aware one, and checks that the whole round trip, including the walk home, fits the budget with a planning reserve kept back. In the Contingency Lab a blocked path can be simulated mid-walk: the system replans from the crew's current position with the resources already used, and states clearly when no feasible return exists. Every number is labelled as observed, derived, assumed or simulated, with a link to its source. It is a research prototype, not a certified navigation tool.

## Project Demonstration
**[Team to add]** Public link to either a deck of **at most 7 slides including the title slide** or a video of **at most 30 seconds**. Test it in an incognito window before pasting. Storyboard and video script: `docs/NASA_SUBMISSION_DRAFT.md`.

## Project
https://midgardians.darelladero.tech/ (live app, verified). Code: https://github.com/black-panzero/EVA-Pathfinder

## Project Details

**What it does**
EVA Pathfinder answers one question for a crew on a Mars surface walk (EVA): "Can we get there, do the science, and still get home within our limits?" It joins real orbital terrain, geology and rover observations into one local map, then plans and checks a round-trip walk against time and supply limits.

**How it works**
1. **Real, aligned data.** A Python pipeline downloads the USGS Mars 2020 CTX elevation model (20 m) and image mosaic (6 m), verifies their SHA-256 checksums and crops a study area from the Jezero crater floor to the delta front. Both products share one Mars map projection and grid. As a cross-check we compared our elevations with 252 elevations recorded at Perseverance's positions: the median difference is 1.55 m. The USGS geologic map (SIM 3464) is reprojected onto the same grid and shown as regional context, because USGS documents 100–200 m offsets for it. Habitat and science-site coordinates come from Perseverance's recorded positions, not from guesses. Rover photos are placed only where their metadata matches a recorded position.
2. **Pathfinder.** Each 20 m cell is a square on a board. Cells steeper than the slope limit, or without data, are off-limits. An A* search finds two routes: the shortest one, and a terrain-aware one that prefers gentler ground. Distances are ground metres on Mars, corrected for latitude; no Earth map projections are used.
3. **Guardian.** The walk (habitat → science stops → habitat) is converted into time, with extra time for climbing, so out and back differ. Science time and supply use are added. The plan is FEASIBLE only if the total fits within the budget after the planning reserve. Otherwise it is INFEASIBLE with a plain reason such as "insufficient time" or "slope exceeds limit".
4. **Contingency Lab.** The user moves a mission-progress slider and drops a simulated blocked zone. The system finds where the crew is, counts what they have already used, and replans home on a copy of the map. If the habitat is cut off, it reports "no feasible return" instead of drawing a route.
5. **Evidence trail.** Every value carries a label (observed, derived, assumed, simulated or unknown) with source links, checksums and a downloadable JSON report.

**Results on real terrain (default inputs, illustrative assumptions)**
- Landing site → Wildcat Ridge → landing site: shortest route 5.75 km, steepest cell 15.0°; terrain-aware route 5.97 km, steepest 12.5°.
- Planned time 216 of 315 usable minutes, so FEASIBLE. With a 50% reserve, INFEASIBLE (insufficient time).
- A simulated blocked zone on the return path produces a detour. Enclosing the habitat produces "no feasible return".
- Elevation source: USGS CTX DTM, SHA-256 16a1aa66…327b.
- Planning time is about 0.2 s per full evaluation on an Intel i5-7300U laptop CPU.

**Benefits and intended impact**
- Planners see terrain, science value and "can we get home?" in one place.
- Return-aware checks and replanning from the crew's current position target the riskiest part of a surface walk: being far from the habitat when something changes.
- Clear labels show what the map can and cannot know. A 20 m elevation model cannot see rocks, so this is a planning aid, not a certified navigation or life-support system.
- The approach can extend to rover waypoint planning and higher-resolution (HiRISE) maps.

**Tools and technologies**
Python 3.12 (FastAPI, Pydantic, NumPy, rasterio/GDAL, pyproj, Shapely, pyogrio), TypeScript, React, Vite, Leaflet (flat map coordinates, no Earth projection), Pyodide (the same Python engine running in the browser for the public build), IBM Plex fonts, Lucide icons, pytest, Vitest and Playwright. It runs on an ordinary laptop CPU with no GPU, cloud service or paid API. The engine is deterministic and uses no AI at runtime.

**What makes it creative**
- Every coordinate is tied to a real rover record.
- Our elevation data is cross-checked against rover-reported elevations.
- The mid-walk emergency replans from the crew's actual position and remaining supplies.
- The system admits failure openly instead of showing a fake route.

**Factors we considered**
- Scientific honesty: no invented data, labels on every value, known map offsets disclosed.
- Correct Mars geometry.
- Hard slope limits.
- Unknown terrain blocked by default.
- Raising the reserve can never turn an infeasible plan into a feasible one (tested).
- Accessibility: text status as well as colour, keyboard-usable controls, mobile layout.
- Reproducibility: checksums, a run manifest and automated tests.

**Use of AI (also shown inside the app and in `docs/SI_DISCLOSURE.md`)**
The software code, data pipeline, tests and documentation were written with an AI coding assistant (Claude Code by Anthropic), from project specification documents that were also drafted with AI assistance. The team reviewed and ran the results. No AI-generated images, video or audio are used.

## Use of Super Intelligence (SI)
Select every option that applies:
- **Code**
- **Text/data** (documentation and the data pipeline)
- **Chatbot / large language model** (the specification documents were drafted with an LLM)

Do **not** select image, video or audio generation. None was used.

## NASA Data
| Link Text | Link Url |
|---|---|
| Mars 2020 Terrain Relative Navigation CTX DTM Mosaic (20 m), USGS/NASA | https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_dtm_mosaic |
| Mars 2020 Terrain Relative Navigation CTX Orthomosaic (6 m), USGS/NASA | https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_orthorectified_image_mosaic |
| Mars 2020 Perseverance "Where is the Rover" waypoints | https://mars.nasa.gov/mars2020/mission/where-is-the-rover/ |
| Perseverance Navcam raw image NLF_0684_0727665509_222ECM_N0321062NCAM08111_02_095J (NASA/JPL-Caltech) | https://mars.nasa.gov/mars2020/multimedia/raw-images/NLF_0684_0727665509_222ECM_N0321062NCAM08111_02_095J |
| Perseverance Navcam raw image NLF_0502_0711519639_144ECM_N0261222NCAM00501_01_295J (NASA/JPL-Caltech) | https://mars.nasa.gov/mars2020/multimedia/raw-images/NLF_0502_0711519639_144ECM_N0261222NCAM00501_01_295J |
| Mars 2020 MEDA environmental data, sol 684 (NASA PDS Atmospheres Node) | https://atmos.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/ |
| NASA/JPL: Perseverance Investigates Geologically Rich Mars Terrain (Wildcat Ridge) | https://www.jpl.nasa.gov/news/nasas-perseverance-rover-investigates-geologically-rich-mars-terrain/ |
| NASA/JPL PIA24929: Rock Cores From Wildcat Ridge | https://www.jpl.nasa.gov/images/pia24929-perseverance-rock-cores-from-wildcat-ridge/ |
| NASA/JPL: Perseverance Deposits First Sample on Mars Surface (Three Forks) | https://www.jpl.nasa.gov/news/nasas-perseverance-rover-deposits-first-sample-on-mars-surface |
| NASA/JPL PIA25682: Three Forks Sample Depot Map | https://www.jpl.nasa.gov/images/pia25682-perseverances-three-forks-sample-depot-map/ |

## Space Agency Partner & Other Data
| Link Text | Link Url |
|---|---|
| USGS SIM 3464 Geologic Map of Jezero Crater and Nili Planum (Sun & Stack, 2020) | https://doi.org/10.3133/sim3464 |
| Claude Code (Anthropic), AI coding assistant | https://claude.com/claude-code |
| Pyodide (MPL-2.0), Python in the browser | https://github.com/pyodide/pyodide |
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
| Lucide icons (ISC) | https://github.com/lucide-icons/lucide |
| IBM Plex Sans and Mono fonts (SIL OFL 1.1) | https://github.com/IBM/plex |
| pytest (MIT) | https://github.com/pytest-dev/pytest |
| Vitest (MIT) | https://github.com/vitest-dev/vitest |
| Testing Library (MIT) | https://github.com/testing-library/react-testing-library |
| Playwright (Apache-2.0) | https://github.com/microsoft/playwright |

## Project Submission Verification (humans only)
- **Terms and Conditions:** tick only after reading the 2026 Submission Guide (`EVA_Pathfinder_Handoff/references/`).
- **All Work is Original:**
  - The guide says SI should not be used to come up with the idea. The specification documents and the code here were produced with AI assistance.
  - Before ticking, the team must write down its own human contribution (idea ownership, validation, decisions) in `docs/NASA_SUBMISSION_DRAFT.md`, and be able to defend the concept.
  - If unsure, ask the organizers.
