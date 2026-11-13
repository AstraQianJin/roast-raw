# Roast Raw 0.01

Web-only training journal foundation. Vue 3 + Vite + Motion One, FastAPI and SQLite. No login, no offline data cache, no synchronization service. Dates use Asia/Shanghai and missed sessions never shift the calendar.

## Layout

```text
web/                 Vue source, design tokens, anatomy and capacity views
server/app/          FastAPI, SQLite store, Beijing calendar, validation
server/app/stats/    Shared classification, prescription and statistics engine
server/tools/        Legacy adapter and arbitrary-length synthetic plans
data/                Generated plan, movement library, geometry and ranges
  schema/            RPL-Raw-v1 and independent RPL-Review-v1 contracts
tests/               Fixture, import, API, restart and CDP browser regressions
docs/shots/          Local screenshots, not old App screenshots
Ref/                 Read-only reference inputs; permission files never ship
```

## Local setup

Run from this directory in Git Bash on Windows (Python 3.13+, Node 22.12+ and Chrome). On macOS/Linux use `server/.venv/bin/python` instead of the Windows Python path.

```sh
python -m venv server/.venv
server/.venv/Scripts/python.exe -m pip install --index-url https://mirrors.aliyun.com/pypi/simple -r server/requirements.txt
npm --prefix web ci
server/.venv/Scripts/python.exe server/tools/gen_data.py
npm --prefix web run build
server/.venv/Scripts/python.exe -m uvicorn server.app.main:app --host 127.0.0.1 --port 8000
```

The Aliyun mirror is the default because pypi.org timed out from this machine; substitute `--index-url https://pypi.org/simple` where the official index is reachable.

Open <http://127.0.0.1:8000>. Built pages and API share one local origin; deep-link reloads return the Vue shell. For development, leave the API running and run `npm --prefix web run dev`, then open <http://127.0.0.1:5173> (Vite proxies `/api`). Never expose either development server to the public internet.

SQLite defaults to `data/roastraw.sqlite3`. Set `RR_DB_PATH` to choose a different database. The generated plan seeds an **empty** database only; regenerating JSON does not silently replace an existing live cycle. The full import/archive workflow is deferred. To preview another seed without discarding data, point `RR_DB_PATH` at a new database path.

## Verification

```sh
node tests/verify.js
npm --prefix web run build
node tests/browser.mjs
```

`RR_PYTHON` overrides the test Python path; `CHROME_PATH` overrides Chrome. Browser tests launch isolated loopback servers and temporary databases, use CDP device emulation rather than window dimensions, and save screenshots in `docs/shots/`. They do not write test logs into the working database. The training-day regression uses an explicitly fixed clock; delivery Today screenshots use the real Beijing date.

`verify.js` checks exact integer totals, six-group weekly raw values at 1e-9, cycle half-up display values, and 16-leaf weekly values within the supplied 0.1 tolerance. It tests 8/17/21-week plans and a separate child with a deliberately altered bench coefficient: the same fixture assertions must fail with exit code 1. Python tests include strict imports, calendar boundaries, API last-write-wins behavior and an actual server restart/readback.

## API foundation

- `GET /api/health`, `/api/cycle`, `/api/plan`, `/api/today`, `/api/geometry`
- `GET /api/analysis?mode=plan` or `mode=log`
- `GET /api/log?cycle_id=...`
- `PUT /api/log` with `cycle_id`, `week`, `day`, `seq`, `load`, `sets`, `reps`, `rpe`, `note`
- `POST /api/plan/validate`: strict validation only, **does not import or persist**

One log describes one prescribed exercise row. Unlogged rows retain planned volume in log mode, while completion counts only real logged sets. Zero sets explicitly replaces a planned row. Last-write-wins updates and the append-only log journal commit together. Actual tonnage uses recorded last-set load/reps × actual sets and is an estimate; planned tonnage follows segment loads with the legacy main/variation rounding rules.

Six core tables exist: `cycles`, `plans`, `logs`, `readiness`, `archives`, `body_metrics`, plus `logs_journal`. A schema-version guard rejects unsupported databases without resetting them. No migration from an older Roast product is attempted.

## Scope and provenance

Today/Plan, default-visible 16-leaf anatomy, deep links, light/dark themes, genuine statistics and minimal persistence are implemented. Full logging/readiness/body-metric forms, plan replacement, archive/review export, questionnaire, AI and deployment remain later milestones. Readiness values never auto-adjust loads. Unknown reference values stay null; back-group ranges are not presented as individual-muscle targets.

Anatomy paths are the supplied `Ref/02_Stats/muscle_geo.json`, derived from body-muscles 1.0.0 (Apache-2.0). Only coordinates are reused, not its React component; no React dependency is added. See `docs/body-muscles-LICENSE.txt` for upstream notice/license. Five fixed OKLCH bands encode weekly relative volume, not recovery.

Permission files, keys, environment files, databases, virtualenvs and build outputs are Git-ignored. No secret is needed for local 0.01. This repository has no remote configured; nothing is deployed or pushed. The old project and both remote servers are outside this implementation's write scope.
