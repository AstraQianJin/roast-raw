# Roast Raw

Agents: read [AGENTS.md](AGENTS.md) first, then the active requirements in [TODO.md](TODO.md). Do not rebuild or restore the repository from historical handoff snapshots. Current version comes only from `web/package.json`; its SemVer patch is the product’s hundredth-version label (for example `0.0.2` displays as `0.02`).

Web-only training journal foundation. Vue 3 + Vite + Motion One, FastAPI and SQLite. No login, no offline data cache, no synchronization service. Dates use Asia/Shanghai and missed sessions never shift the calendar.

## Layout

```text
AGENTS.md            Agent rules, evidence and source pointers
TODO.md              Active user ideas, approved directions and open decisions
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

`RR_PYTHON` overrides the test Python path; `CHROME_PATH` overrides Chrome. Browser tests launch isolated loopback servers and temporary databases, use CDP device emulation rather than window dimensions, and save screenshots in `docs/shots/`. They do not write test logs into the working database. Regular Today screenshots use the real Beijing date. Additional `today-training-*` screenshots use an explicitly fixed scheduled training-day clock; the date and session badge remain visible so fixture evidence cannot be confused with live Today.

`verify.js` checks exact integer totals, six-group weekly raw values at 1e-9, cycle half-up display values, and 16-leaf weekly values within the supplied 0.1 tolerance. It tests 8/17/21-week plans and a separate child with a deliberately altered bench coefficient: the same fixture assertions must fail with exit code 1. Python tests include strict imports, calendar boundaries, API last-write-wins behavior and an actual server restart/readback.

## API foundation

- `GET /api/health`, `/api/cycle`, `/api/plan`, `/api/today`, `/api/geometry`
- `GET /api/analysis?mode=plan` or `mode=log`
- `GET /api/performance?cycle_id=...`: actual singles and explicitly estimated weekly movement performance; no planned fallback
- `GET /api/archive`: read-only historical cycle summaries; excludes the active cycle
- `GET /api/review?cycle_id=...`, `/api/review/export?cycle_id=...`: independent review and JSON download; exporting never archives the active cycle
- `GET /api/log?cycle_id=...`
- `PUT /api/log` with `cycle_id`, `week`, `day`, `seq`, `load`, `sets`, `reps`, `rpe`, `note`
- `GET /api/readiness?cycle_id=...&date=YYYY-MM-DD&session_id=week|day`, `PUT /api/readiness`
- `GET /api/body-metrics?cycle_id=...&date=YYYY-MM-DD`, `PUT /api/body-metrics`
- `GET /api/prescription?cycle_id=...`: manual reference 1RMs, immutable versions and dated system-load adjustments
- `POST /api/prescription/preview`: `cycle_id`, `current_id`, complete `references` map; no prescription write
- `POST /api/prescription/apply`: same fields plus reviewed `preview_id`; rejects stale versions
- `GET /api/prescription/version?cycle_id=...&revision_id=...`, `POST /api/prescription/restore` with `cycle_id`, `current_id`, `revision_id`
- `POST /api/plan/validate`: strict validation only, **does not import or persist**
- `POST /api/plan/import/preview`: `plan_json` (original UTF-8 JSON text), `filename` (display only); validated current/new plan comparison, no database write
- `POST /api/plan/import/confirm`: same upload plus `current_id`, `candidate_id`, `confirm: true`; rejects stale records and existing cycle IDs

One log describes one prescribed exercise row. Unlogged rows retain planned volume in log mode, while completion counts only real logged sets. Zero sets explicitly replaces a planned row. Last-write-wins updates and the append-only log journal commit together. Actual tonnage uses recorded last-set load/reps × actual sets and is an estimate; planned tonnage follows segment loads with the legacy main/variation rounding rules.

Recovery and body metrics have separate explicit saves. Recovery/arousal/nutrition use positive 1–7 ratings; joint pain is a separate warning. HRV and resting HR need 28 distinct valid prior dates per field; fewer than three scored inputs leaves the score and REC unknown. Missing values remain null. Bodyweight uses the same date or nearest past date, never a future record. Readiness only advises; it never rewrites prescriptions. A personal time-performance curve is not implemented because matched benchmark observations are not yet collected.

Analysis reports working sets, SBD equivalent capacity and muscle allocation separately. Approved variation transfer factors discount only equivalent capacity; raw sets and completion are unchanged. Unknown transfer factors are excluded explicitly. Legacy prescriptions retain their original 1:1 capacity basis. Weekly MEV/MRV comparisons use equivalent capacity; cycle working-set totals remain raw. GPP/cardio and equipment details are collapsed reading views, not inferred training completion.

Muscle heat uses the highest planned weekly muscle-weighted volume across the full cycle. Weeks, primary/secondary filters and plan/log modes share this fixed denominator. Color bands and bar widths saturate at 100%; raw values remain uncapped. Direct-set MEV/MRV references do not determine heat. Mobile Analysis reads anatomy, weekly summary, sixteen muscles, capacity and trends in that order.

Recorded performance uses actual last-set loads only: singles retain their original load; ordinary 2–10 reps use an explicitly labelled Epley estimate (`load × (1 + reps / 30)`). Power Clean multi-rep and timed/unit rows have no estimate. Missing/zero logs remain null; charts break at missing weeks. Pull-up/dip observations use recorded total system weight, not external adjustment. Highest weekly values retain their source date/key and method. Neither estimates nor trends update reference 1RMs or goal attainment.

Review exports preserve the plan, recorded logs, body metrics, positive readiness and separately labelled legacy fatigue, all prescription versions and append-only journal payloads. A single SQLite read transaction supplies the export; its SHA-256 covers canonical sorted JSON excluding `integrity`. Weekly comparisons use actual-only recorded sets rather than the analysis view's unlogged planned fallback. Missing actual rows remain null. Completion uses raw main/variation/accessory sets with 60/25/15 weights; composite uses goal/bodyweight/completion with 40/40/20 weights and never redistributes missing weights. Bodyweight cut/bulk progress is `(current − start) / (target − start) × 100`, uncapped. Maintenance within ±1% scores 100, then loses 10 points per additional percentage point down to zero. Only an explicit initial weight, target and same/prior actual dated reading can score. Ordinary singles/e1RM do not count as test-day goal attainment: until explicit test records are implemented, that component and the composite remain null. Downloading a review does not end a cycle; historical views contain no write controls. No destructive archive deletion is provided.

Reference 1RMs are manual, not estimated performance. Settings previews and explicitly applies the approved eight-variation policy; no startup recalculation occurs. Prescribed percentages take priority; missing percentages use the legacy `render_day.py` RTS reps/RPE lookup, labelled as an estimate, including Power Clean without Epley extrapolation. The legacy implementation rounds the lookup to whole percentages; its contradictory 3@9 comment is not used. Pull-up/dip weights are total system loads; external assistance or added load remains unknown without an action-date or prior bodyweight reading. The versioned plan retains its original validated `basePlan`; dates, sets, reps, target RPE, movement identity and muscle coefficients are unchanged. Other library variation 1RMs may be maintained but do not silently trigger additional recalculations.

Settings imports Raw-v1 or legacy v4 JSON only. Duplicate keys, nonfinite numbers, unknown movements and contract failures are rejected with contextual field errors. The original upload hash includes its UTF-8 BOM, if present; v4 enters only through the adapter. Preview compares complete old/new plans without writing. Explicit confirmation checks the complete active source, including records and journals, inside `BEGIN IMMEDIATE`; intervening saves require a fresh preview. A consistent backup precedes the version-gated transaction that freezes the old review, archives its cycle, activates the new plan and seeds its prescription history. Existing cycle IDs never overwrite data. Old records and journals remain cycle-scoped and read-only; all record writes recheck active status inside their transaction. Failed transactions leave logical data unchanged; a lost confirmation response is not proof of rollback, so check the current cycle before previewing again. The database schema is unchanged by plan replacement.

The store keeps `cycles`, `plans`, `logs`, legacy `readiness`, `archives`, `body_metrics`, immutable `prescription_versions`, and append-only journals. Positive recovery lives in `readiness_v2`; old fatigue is preserved without reinterpretation. Schema upgrades take a consistent SQLite snapshot in the database's sibling `backups/` directory before a transactional, version-gated migration. Unsupported versions are rejected, not reset. To restore, stop the owned API process, preserve the current database and its WAL/SHM companions together, copy the selected snapshot to a new path, check SQLite integrity, then launch with `RR_DB_PATH` pointing to that copy. No migration from an older Roast product is attempted.

## Scope and provenance

Today/Plan include default-visible compact anatomy and weekly capacity. Analysis owns the full sixteen-muscle list, detailed reference context and cycle capacity board. Day deep links expand, scroll to and focus the selected day. Light/dark themes, genuine statistics and minimal persistence are implemented. Inline exercise logging and date-associated recovery/body-metric forms are implemented. Archive history and independent review export are available at `/archive` and `/archive/:cycleId`. Strict plan replacement is available in Settings. Questionnaire, AI and deployment remain later milestones. Readiness values never auto-adjust loads. Unknown reference values stay null; back-group ranges are not presented as individual-muscle targets.

Anatomy paths are the supplied `Ref/02_Stats/muscle_geo.json`, derived from body-muscles 1.0.0 (Apache-2.0). Only coordinates are reused, not its React component; no React dependency is added. See `docs/body-muscles-LICENSE.txt` for upstream notice/license. Five fixed OKLCH bands encode volume relative to the cycle-wide planned weekly maximum, not recovery.

Keys, environment files, databases, virtualenvs and build outputs are Git-ignored; the secret-free permissions `ACCESS.md` remains trackable. No secret is needed for local development. Check actual remote/publication state with `git remote -v` and the release evidence, not a frozen README claim. Local commits may happen between releases; remote pushes only happen at each 0.10 milestone after validation and destination approval. Deployment remains restricted to the milestones in AGENTS.md. The old project and old server remain outside the write scope.
