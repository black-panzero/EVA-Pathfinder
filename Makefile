# EVA Pathfinder / EVA Guardian - common tasks. CPU-only, no credentials required.
PY      ?= .venv/bin/python
PYENV   := env -u PYTHONPATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
API_PORT ?= 8000

.PHONY: setup data inspect test test-backend test-frontend lint dev api web build smoke clean

setup:            ## create venv + install backend and frontend deps
	uv venv --python 3.12 .venv || python3 -m venv .venv
	uv pip install --python $(PY) -r backend/requirements.txt || $(PY) -m pip install -r backend/requirements.txt
	cd frontend && npm ci || npm install

data:             ## download (if missing) + verify + prepare real NASA/USGS data
	$(PYENV) $(PY) scripts/prepare_data.py

inspect:          ## print data inspection report -> docs/DATA_INSPECTION.md
	$(PYENV) $(PY) scripts/inspect_data.py

test: test-backend test-frontend

test-backend:
	cd backend && $(PYENV) ../$(PY) -m pytest -q

test-frontend:
	cd frontend && npx vitest run

lint:
	$(PYENV) $(PY) -m ruff check backend scripts
	cd backend && $(PYENV) ../$(PY) -m mypy app --ignore-missing-imports
	cd frontend && npx tsc -b

api:              ## run the API on :8000
	cd backend && $(PYENV) ../$(PY) -m uvicorn app.api.main:app --host 127.0.0.1 --port $(API_PORT)

web:              ## run the Vite dev server on :5173 (proxies /api to :8000)
	cd frontend && npx vite --host 127.0.0.1 --port 5173

dev:              ## run API and web together (Ctrl+C stops both)
	$(MAKE) -j2 api web

build:
	cd frontend && npx tsc -b && npx vite build

smoke:            ## browser smoke test + screenshots (servers must be running)
	$(PYENV) $(PY) scripts/browser_smoke.py

clean:
	rm -rf frontend/dist backend/.pytest_cache .ruff_cache .mypy_cache
