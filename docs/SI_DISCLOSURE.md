# Use of Super Intelligence (SI) / AI tools

Required by the NASA Space Apps 2026 Submission Guide: "Code and data: Must acknowledge SI generation in descriptive text and metadata."

| Area | SI used? | How |
|---|---|---|
| Project specification documents (`EVA_Pathfinder_Handoff/`, `01`-`08`) | Yes | Drafted with an LLM chatbot, as the documents themselves state |
| Source code (backend, frontend, scripts, tests) | Yes | Written by an AI coding agent (Claude Code by Anthropic) and reviewed and run by the team |
| Data pipeline and derived data products | Yes (code) | The code that downloads, verifies and derives the data was AI-written. The data itself is NASA/USGS observation, not generated |
| Documentation (`README.md`, `docs/`) | Yes | AI-written from verified run outputs |
| Images, maps, screenshots | **No** | Map imagery is USGS/NASA CTX data, rover photos are NASA/JPL-Caltech raw images, and screenshots are captures of the running app. No AI-generated or AI-modified imagery |
| Video / audio | **No** | None produced with SI. A demo video, if recorded, will be a screen capture |
| NASA branding | Not used | No NASA logos, insignia or mission identifiers were generated or modified |
| Runtime behaviour | **No AI at runtime** | Route planning and feasibility are deterministic A* search and arithmetic |

**Where the disclosure appears:**
- The app's side rail and its "How it works" guide.
- The `<meta name="ai-disclosure">` tag in `frontend/index.html`.
- `x-ai-disclosure` in `frontend/package.json`.
- `README.md` and `NOTICE.md`.
- The submission form text.

**Human contribution [team to complete before submission]:** describe who owns the idea, what was decided, validated or changed by team members, and how the team checked the results.
