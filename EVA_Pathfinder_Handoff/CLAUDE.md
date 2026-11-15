# CLAUDE.md — EVA Pathfinder / EVA Guardian

**Immediately follow `AGENTS.md` and `01_MASTER_BUILD_PROMPT.md`**. Both are normative. Read the rest of the handoff requirements before coding; they cover NASA 2026 rules, exact mission data, geospatial correctness, DDD/DDA/OOP architecture and acceptance tests.

## Execution mandate

Implement an actual working end-to-end Marswalk prototype, not another plan. Use real Jezero CTX DEM, actual terrain-gradient and A* routing, round-trip resource feasibility with illustrative parameters, one blocked-return contingency, a source-labelled React map, tests and human-reviewable submission drafts.

Maintain a short task list and check off working vertical slices; run tests as you go; generate `docs/DECISIONS.md` and `docs/VERIFICATION_REPORT.md`. If NASA data cannot be downloaded, record the failure, continue with **clearly labeled synthetic test fixtures**, and never call the scientific demo real NASA-data-based until it is.

No fabricated status, tests, URLs, astronaut-certified estimates, raster values or source citations. No Earth WGS84 distance functions for Mars. NASA SI/originality restrictions must be followed; do not accept terms on behalf of humans. Finish with an evidence-backed report of verified work and blockers.
