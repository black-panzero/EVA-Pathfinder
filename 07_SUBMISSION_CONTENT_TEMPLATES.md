# NASA SPACE APPS — HUMAN-REVIEWED FORM CONTENT AND DEMO

**Template, not a submitted project.** Fill based on **actual implementation**; delete unbuilt features and claims. Public links cannot be invented. The user-supplied form and official 2026 guide control character and demo limits. NASA SI policy/idea-origin caveats are in `03_NASA_RULES_AND_SUBMISSION.md`.

## Project Name

**EVA Pathfinder — EVA Guardian**

## Summary (planned scope; edit into past tense only after features run)

> EVA Pathfinder is a hyperlocal Marswalk mapping and mission-planning prototype for future human exploration. The proposed application integrates NASA Mars orbital imagery, elevation data and geological context for a selected location in Jezero Crater. Its Pathfinder engine computes terrain-constrained route options to a scientific destination; its EVA Guardian engine evaluates a complete round trip against illustrative time and resource budgets. A contingency mode simulates an unexpected blocked corridor and reassesses whether a feasible return remains under the model. The interface distinguishes mission observations from derived terrain metrics, assumed resource rates and simulated events. The project illustrates how records from NASA's robotic Mars missions can support transparent, science-oriented decisions for future surface exploration. It is an educational research prototype, not operational astronaut navigation or life-support software.

**Review:** Keep <=1,500 characters and ideally 50–200 words; ensure 'integrates', 'computes', 'simulates' are true. If not built, replace with 'we designed/prototyped' and state exactly what works. Count in the live form.

## Project Demonstration (required)

**URL:** `TO_BE_PROVIDED_BY_TEAM`  
**One format only:** **up to 7 slides inclusive** of title/intro OR **video <=30 seconds**. Host publicly without authentication. No fake URLs.

### Suggested seven-slide storyboard

1. **Title/team/challenge:** EVA Pathfinder / EVA Guardian; team name and members inserted by humans.
2. **Problem:** data from Mars missions exists, but a Marswalk needs linked local science, terrain and constraints.
3. **Real NASA data:** show actual Jezero imagery, elevation DEM and geological context with credits and resolution.
4. **Map and route:** show genuine calculated path(s), real coordinate/measurement provenance.
5. **Guardian:** show modeled round-trip duration/budget and accepted/rejected reason.
6. **Contingency:** demonstrate one simulated blockage, updated path and reserve or explicit infeasibility.
7. **What was proven/limits:** test status, evidence labeling, scientific limitations and future potential.

**Video alternative:** 0–4s challenge/problem; 4–10s NASA layers; 10–18s working route and resource check; 18–25s contingency replan; 25–30s impact/limitations. Strict duration with measured file length. If narration isn't English, include English subtitles. All generated visuals marked as per guide. Do not use under-18 likeness.

## Project final URL (required)

**URL:** `TO_BE_PROVIDED_BY_TEAM` — repo, deployed site or project presentation accessible to judges without credentials; test in private/incognito browser.

## Project Details (planned method; revise after building)

### Problem

Mars missions have gathered topography, surface images, geological interpretation and environmental measurements. A future astronaut needs a hyperlocal integrated view, with both an exploration objective and realistic understanding of mission limits. Conventional image viewers do not by themselves establish that a complete round trip meets chosen constraints.

### Solution and workflow

EVA Pathfinder brings multiple NASA/USGS datasets into a common local Mars spatial reference. Users can explore optical/topographic/geological context, choose a hypothetical habitat and a documented science target, and examine terrain-constrained routes. A* computes candidate paths from a preprocessed DEM and masked terrain; elevation, distance and assumptions are shown. EVA Guardian evaluates travel and activity time against configured resource reserves. A scenario simulator injects a blocked route and recomputes return feasibility from the crew's simulated current location. Observations and the team's calculations are explicitly differentiated.

### Innovation and benefits

The value is **evidence-aware, return-aware mission planning**: not simply drawing a path to a science destination, but assessing a complete expedition, presenting uncertainty, and responding transparently to a simulated contingency. The same interfaces could later support robotic scouting and local navigation, but these are future work unless implemented.

### Implementation tools

**REPLACE AFTER INSPECTION:** Python, Rasterio, GDAL, NumPy, A*, FastAPI; React/TypeScript/Vite; GeoTIFF/JSON; pytest and browser tests. Do not claim anything unused.

### Limitations

20 m orbital elevation data cannot reveal every astronaut-scale hazard. Geologic maps are regional context, historic MEDA data would not forecast live local weather, and simplified mission budgets are hypothetical—not NASA-certified resource models. The prototype must not be used for real life-safety decisions.

### Results and evidence

**INSERT ACTUAL:** dataset ID and hash; test run outcome; study-area extent; route distances/elevations, demo screenshot, contingency result, performance metrics. **Do not use invented numerical improvements.**

## Use of SI (required form select-all + explanation)

- **Select actual categories** of chatbot/LLM, coding assistance, generative imagery/audio, or other SI tools used; never select 'I did not use SI' if AI assisted this work.
- The official guide states that SI should accelerate execution, not originate the team's idea. The team's human ownership/original contribution must be reviewed honestly.
- **Suggested truthful description, adapt to fact:** 'AI-assisted tools were used to help draft technical specifications, research implementation options and assist with coding/documentation/testing. The team reviewed sources, selected the final scientific scope and validated computed results. AI-assisted code/data are identified in repository documentation; any generated media are visibly marked or acknowledged as required.'
- Do not include SI-generated NASA branding. SI images/videos visibly watermarked; generated audio metadata/text credited; SI-assisted code/data credited.

## NASA Data (used sources only; provide each as link text + full URL)

| Link text | URL | Include when |
|---|---|---|
| Mars 2020 Terrain Relative Navigation CTX DTM Mosaic | https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_dtm_mosaic | Actual DEM ingestion |
| Mars 2020 CTX Orthorectified Image Mosaic | https://www.usgs.gov/data/mars-2020-terrain-relative-navigation-context-camera-orthorectified-image-mosaic | Optical layer truly used |
| NASA Mars Trek | https://trek.nasa.gov/mars/ | Data layer/service actually used, not only visited |
| NASA Mars 2020 Perseverance Raw Images Gallery | https://mars.nasa.gov/mars2020/multimedia/raw-images/ | Actual rover image used; credit specific image too |
| NASA PDS Perseverance MEDA | https://pdsatmospheres.nmsu.edu/data_and_services/atmospheres_data/PERSEVERANCE/meda.html | Actual MEDA historical record used |
| NASA Perseverance Location Map | https://science.nasa.gov/mission/mars-2020-perseverance/location-map/ | Actual route context used |

## Space Agency Partner & Other Data (used sources only)

- USGS Sun & Stack (2020) Jezero geologic map: https://pubs.usgs.gov/publication/sim3464
- USGS CTX DTM / image mosaics may also be listed with USGS agency attribution; the provenance record should explain NASA mission source + USGS processing clearly.
- Python https://www.python.org/; FastAPI https://fastapi.tiangolo.com/; Rasterio https://rasterio.readthedocs.io/; NumPy https://numpy.org/; GDAL https://gdal.org/; React https://react.dev/; Vite https://vite.dev/; Leaflet https://leafletjs.com/ (ONLY if used).
- All actual additional open source dependencies, images, icons, fonts, reference texts, illustrative art and their licenses must appear in a final sourced list.

## Final human checks

Team title & names; exact date/time/event; project summary character length; working public links; demo compliant length; sources/license/SI disclosures; no under-18 likeness; terms/original-work assertion truthful; click **Submit for Judging**, verify success.
