# EVA Pathfinder / EVA Guardian — Engineering Handoff

**Purpose:** A ready-to-give-to-Codex/Claude-Code specification bundle for **building** a NASA Space Apps 2026 research prototype end to end. **This bundle contains planning and handoff instructions, not the implemented app.**

## Fastest way to use

1. Unzip this bundle in a new writable repository.
2. Open it in **Codex or Claude Code**. The agents will discover `AGENTS.md` or `CLAUDE.md` at the repo root.
3. Paste the complete short instruction below into the agent:

> **Build EVA Pathfinder / EVA Guardian end-to-end. Read `01_MASTER_BUILD_PROMPT.md`, `02_PLATFORM_SPECIFICATION.md`, every numbered support document, `NASA_CHALLENGE_BRIEF.md`, and the uploaded official PDF in `references/`. Follow the constraints and implementation sequence. Implement real Mars data ingestion, actual slope-aware A* route planning, round-trip Guardian resource checks, one deterministic blocked-return contingency, interactive map, source provenance, tests, documentation, and NASA submission-ready drafts. Execute code/tests and report evidence; don't just generate plans. Do not claim unbuilt features, fabricate routes, datasets or submission links.**

4. The agent should implement the working application **in this same repository**, preserving these documents as requirements.
5. Human team reviews scientific methods, SI disclosures, originality, source usage, public hosting, demo and official submission.

## Files

| File | Purpose |
|---|---|
| `01_MASTER_BUILD_PROMPT.md` | **Primary autonomous build instruction** |
| `02_PLATFORM_SPECIFICATION.md` | **Platform product design, UX/visualizations, system architecture, DDD, DDA and OOP** |
| `03_NASA_RULES_AND_SUBMISSION.md` | 2026 submission rules, integrity, AI disclosure, links and eligibility |
| `04_DATA_CATALOG_AND_PIPELINE.md` | Actual dataset URLs, spatial correctness and provenance pipeline |
| `05_IMPLEMENTATION_PLAN.md` | Priority-based executable engineering plan |
| `06_TESTING_AND_ACCEPTANCE.md` | Algorithm/integration/data QA and definition of done |
| `07_SUBMISSION_CONTENT_TEMPLATES.md` | Form-ready but human-verified summary/details, source fields and demo storyboard |
| `08_DOMAIN_AND_API_CONTRACTS.md` | Domain model, JSON DTO examples and HTTP API boundaries |
| `NASA_CHALLENGE_BRIEF.md` | User-provided challenge brief/source links |
| `AGENTS.md` | Codex and general coding-agent steering file |
| `CLAUDE.md` | Claude Code steering file |
| `config/dataset_manifest.example.json` | Unverified source manifest seed; must not imply acquired data |
| `config/mission.delta-return.example.json` | Example hypothetical mission with **unselected** real coordinates |
| `references/NASA_Space_Apps_Project_Submission_Guide_2026.pdf` | Original user-uploaded official 15-page guide |

## What is being built

An interactive Marswalk map focused on a **verified slice of Jezero Crater**, with authentic optical/topographic/geologic context. The user chooses a science site, receives computed route alternatives, views a round-trip budget, and can inject an obstacle to test return replanning. Scientific/provenance labeling distinguishes observations, calculations, modeling assumptions and simulated events.

**Expected stack:** Python/FastAPI, Rasterio/NumPy/GDAL, A*, React/TypeScript/Vite; CPU-only, modular monolith. Real scientific data required for scientific claims. No full robotic simulator or LLM dependencies for MVP.

## Important NASA rules

The user-provided 2026 guide says submissions close **Sunday November 15, 2026 at 11:59 p.m. in team local event time**; Universal Event uses Team Owner's locale. Public demo is **<=30s video or <=7 slides**; public project URL also required. An actual NASA data/resource is required for Global Award eligibility. All outside assets and SI use must be credited; SI-generated visuals must be visibly marked; the guide says SI should not originate the solution idea. Human original-work confirmation must be truthful. See `03_NASA_RULES_AND_SUBMISSION.md`.

## Science and safety limits

This is a research prototype. 20 m elevation pixels cannot reveal all astronaut-scale hazards. Astronaut resource estimates and emergency events are illustrative. No flight certification or actual real-time Mars astronaut navigational safety claims.

## Technical source links

- DEM: https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_dtm_mosaic
- Optical: https://www.usgs.gov/data/mars-2020-terrain-relative-navigation-context-camera-orthorectified-image-mosaic
- Geology: https://pubs.usgs.gov/publication/sim3464
- Atmosphere (optional): https://pdsatmospheres.nmsu.edu/data_and_services/atmospheres_data/PERSEVERANCE/meda.html
- NASA challenge home: https://www.spaceappschallenge.org/2026/

**Status:** Specifications created. Application, downloads, verification tests, hosting and official submission have **not** been performed by this documentation package.
