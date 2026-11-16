# Roast Raw

A single-user powerlifting training journal: cycle plan, day-by-day prescription, logged sets, analysis and review export — a pure training view. Vue 3 + Vite + Motion One on the front end, FastAPI + SQLite on the back end. Web only — no Android app, no offline cache, no sync service.

**Status (2026-11-15).** The live site is the 0.20 build at <http://82.157.146.30/>: public landing page, journal API behind account sign-in. Local development has reached `0.0.28` and version `0.29` (security and first-screen work) is in progress; nothing is pushed or deployed until the owner says so. The version label shown in the UI is the patch of `web/package.json` (`0.0.2` displays as `0.02`).

## Layout

```text
AGENTS.md            Agent rules, evidence contract, environment facts
TODO.md              Execution queue: next action, version order, approved decisions
web/                 Vue source, design tokens, anatomy and capacity views
server/app/          FastAPI app, SQLite store, Beijing calendar, strict validation
server/app/stats/    Classification, prescription and statistics engine (one source)
server/tools/        Plan generation, legacy adapter, deploy and invite tools
data/                Generated plan, movement library, geometry, ranges
  schema/            RPL-Raw-v1 and RPL-Review-v1 exchange contracts
tests/               Fixture, import, API, restart, cache and CDP browser regressions
docs/                Product contracts, aesthetics notes, licence, screenshots
Ref/                 Read-only reference inputs (never ships credentials)
```

Product contracts, statistical definitions and the full API surface live in [docs/项目交接.md](docs/项目交接.md) — this README deliberately keeps only what a person needs to run the app.

## Local setup

Run from this directory on Windows with Python 3.13+, Node 22.12+ and Chrome. On macOS/Linux use `server/.venv/bin/python` instead of the Windows Python path.

```sh
python -m venv server/.venv
server/.venv/Scripts/python.exe -m pip install --index-url https://mirrors.aliyun.com/pypi/simple -r server/requirements.txt
npm --prefix web ci
server/.venv/Scripts/python.exe server/tools/gen_data.py
npm --prefix web run build
server/.venv/Scripts/python.exe -m uvicorn server.app.main:app --host 127.0.0.1 --port 8000
```

The Aliyun mirror is the default because pypi.org times out from this machine; substitute `--index-url https://pypi.org/simple` where the official index is reachable.

Open <http://127.0.0.1:8000>. Built pages and API share one origin, and deep-link reloads return the Vue shell. For development, keep the API running and start `npm --prefix web run dev`, then open <http://127.0.0.1:5173> (Vite proxies `/api`). Never expose either development server to the internet.

The app refuses to start without `RR_ACCESS_PASSWORD`; for a local fixture preview only, `tests/serve_fixture.py` sets `RR_ALLOW_OPEN_FIXTURE=1` and prints a warning — never set that variable on a deployed host. SQLite defaults to `data/roastraw.sqlite3`; set `RR_DB_PATH` to use another file. The generated plan seeds an **empty** database only, so regenerating JSON never replaces a live cycle.

## Verification

```sh
node tests/verify.js
npm --prefix web run build
node tests/browser.mjs
```

`verify.js` covers statistics, contracts, imports, restarts and sabotage; `browser.mjs` is a green baseline as of 0.35 and exits non-zero if one of its checks breaks — run it with `--sabotage` to see the harness fail on purpose. Browser tests launch isolated loopback servers with temporary databases, use CDP device emulation rather than window dimensions, and write screenshots to `SHOTS_DIR` (default `..\RR\shots\<release>`); nothing lands in the repository. `RR_PYTHON`, `CHROME_PATH`, `RR_DEVICE_WIDTH` and `SHOTS_DIR` override the test Python, Chrome, capture width and output folder.

## Notes

- Dates are fixed to Asia/Shanghai; missed sessions never shift the calendar. The cycle start moves only by whole weeks, and only through the plan generator.
- Keys, environment files, databases, virtualenvs and build output are git-ignored. `Ref/07_Permissions/ACCESS.md` is the trackable, secret-free permission pointer.
- The old app (`Roast PowerLifting`) and its reference index (`RPLRef`) are read-only historical sources at `..\RR\ref-projects\`; see [AGENTS.md](AGENTS.md) before touching either.
- Where to read next: [TODO.md](TODO.md) for what happens next, [AGENTS.md](AGENTS.md) for how work is judged, [docs/项目交接.md](docs/项目交接.md) for product detail.
