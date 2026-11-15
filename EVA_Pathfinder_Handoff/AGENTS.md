# AGENTS.md — Mandatory Instructions for Coding Agents

Project: **EVA Pathfinder / EVA Guardian**.

This repository initially contains **instructions, not working software**. Your mandate is to implement the actual project, verify it, and produce truthful NASA submission drafts. Before code: read `README.md`, `01_MASTER_BUILD_PROMPT.md`, `02_PLATFORM_SPECIFICATION.md`, `03_NASA_RULES_AND_SUBMISSION.md`, `04_DATA_CATALOG_AND_PIPELINE.md`, `05_IMPLEMENTATION_PLAN.md`, `06_TESTING_AND_ACCEPTANCE.md`, `07_SUBMISSION_CONTENT_TEMPLATES.md`, `08_DOMAIN_AND_API_CONTRACTS.md`, `NASA_CHALLENGE_BRIEF.md`, and `references/` official guide.

## Required behavior

1. Build a **real** georeferenced Jezero-based 2D Marswalk app, with evidence of actual NASA/USGS DEM processing, and aligned other data where available. No fake NASA rasters, non-geolocated image pins, Earth CRS mistakes, or invented numerical results.
2. P0: Mars DEM data + reproducible preprocessing; A* valid 2D terrain routing; outbound/science/return resource constraint checks; blocked-path replan from simulated current position; basic working map UI; provenance and tests.
3. Write code and run it. Execute tests. Prefer a robust small feature over big unexecuted scaffolding; report accurately which parts are incomplete.
4. Run on a modest CPU laptop. No GPU, paid API, cloud credentials, LLM or ROS 2 for MVP.
5. Use Python/FastAPI and React/TypeScript, DDD bounded contexts, DDA provenance, composition/OOP with typed abstractions. Use source manifests and deterministic policies.
6. Label **observed / derived / assumed / simulated / unknown** separately in UI, API and reports. No real-world astronaut safety guarantees.
7. Follow `03_NASA_RULES_AND_SUBMISSION.md`. NASA guide notes that SI supports execution, not original idea generation. AI assisted planning this packet: ensure human ownership/verification and accurate SI disclosure. Do not generate NASA logos or unwatermarked AI visuals.
8. Don't claim that public uploads, link visibility, external account actions or NASA submission happened unless independently confirmed.
9. Protect source licensing; credit every relevant data, image, software, quote and model dependency. No image or likeness of a person under age 18 in submission assets.
10. Respect priority sequence. Do not create pseudo 3D/AI chat before the verified data->route->Guardian->replan pipeline.

## Required final response

Files changed, actual datasets downloaded, actual CRS and hash, working features, commands to run, tests executed and results, screenshot/demo files **if actually generated**, scientific limitations, blockers and human actions needed for final public submission.
