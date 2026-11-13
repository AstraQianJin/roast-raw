---
name: roast-raw-agent
description: Develop and hand off Roast Raw, the Vue/FastAPI powerlifting journal. Use for project onboarding, compressed-context recovery, logs/readiness/body metrics, prescription and capacity changes, import/archive/review, questionnaire/AI/test-week work, responsive UI audits, and authorized milestone delivery. Load current TODO decisions before implementing; retain legacy regression and secret/read-only boundaries.
---

# Roast Raw agent

## Start with evidence

Use the Roast Raw workspace, not the adjacent RR session folder. Read root AGENTS.md and TODO.md current execution and approved decisions. Read only the task-specific sections of docs/项目交接.md. User's latest explicit decision outranks old prose; code and tests are evidence, not product authority.

At entry and after context compression run from the project root:

```sh
git status --short
git log --oneline -5
node tests/verify.js
```

Report a red baseline before changing it. Do not say all green unless the command completed with exit code zero. Check current version in web/package.json; its patch maps to the hundredth-version display in App.vue. Never copy volatile versions, assertion counts or tolerances into instructions.

## Keep boundaries intact

- Build only Web: Vue 3, Vite, Motion One, handwritten CSS, FastAPI and SQLite. No Android, WebView, offline training cache, synchronization service or runtime UI/chart framework.
- Keep user-facing text English. Keep statistics in server/app/stats, calendar in server/app/calendar.py, contracts in data/schema, design tokens in web/src/tokens.css.
- Do not hand-edit generated data or web/dist. Change server/tools/gen_data.py or a validated prescription operation, then run the generation chain where required.
- Keep Ref read-only. The sole approved exception changes the new server SSH username to ubuntu in Ref/07_Permissions/ACCESS.md. Old Skills may be read for experience; do not modify or run old-project deployment/build workflows. Never touch the old server.
- Never print, package or commit credentials. Read AI/GitHub credentials from child-process environment; use SSH key/config. Do not alter ACLs or switch tools to evade a denied read. EPERM proves only that the attempted process could not read.
- Keep strict import validation: reject with file/week/day/movement/field/expected details; no quiet repair. v4 enters through the adapter only.
- Keep fixed Asia/Shanghai dates and arbitrary week counts. Missing logs do not count as completion; explicit zero sets replace planned rows.
- Keep real set counts, SBD equivalent capacity and muscle coefficients separate. Transfer coefficients are approved experience parameters, not scientific precision. Read the active decision section before changing policy.
- Keep historical plans/logs and prescription versions recoverable. Before migrations take a consistent SQLite backup, version-gate the operation, and prove old data readback. Never reinterpret old fatigue as positive recovery.
- Do not weaken tolerances, delete assertions or neutralize sabotage. When policy intentionally changes, retain the original source-to-fixture chain and add independently calculated new-policy expectations.

## Find facts, not copies

| Question | Source |
|---|---|
| Setup, runtime API and recovery | README.md |
| Current work and confirmed product choices | TODO.md |
| Detailed product contracts | docs/项目交接.md, by section heading |
| Version | web/package.json; web/src/App.vue releaseVersion |
| Classification/prescriptions/volume | server/app/stats/classify.py, prescription.py, engine.py |
| Calendar | server/app/calendar.py calendar_state |
| SQLite, journal and migration | server/app/store.py Store |
| HTTP boundary | server/app/main.py create_app |
| Strict imports | server/app/validation.py validate_plan, validate_legacy |
| Plan generation | server/tools/gen_data.py adapt; synth_plan.py build |
| Exchange schemas | data/schema/RPL-Raw-v1.json, RPL-Review-v1.json |
| Legacy fixture and arithmetic | Ref/02_Stats/capData.json, mmData.json; Ref/04_Legacy_Code/day_model.py |
| Movement coefficients and geometry | data/movements.json, muscle_geo.json, ranges.json |
| UI and anatomy | web/src/App.vue; web/src/components/MuscleMap.vue |
| Automated evidence | tests/verify.js, tests/browser.mjs, tests/cdp.mjs |
| Credential steps only | Ref/07_Permissions/ACCESS.md; latest deployment decisions in TODO.md |

For broad discovery use workspace search when it resolves the correct workspace; a routing failure is not evidence that files are absent. Read known absolute paths directly. Verify a symbol or path before recommending it.

## Work by file ownership

Define contracts and understand the change before delegating edits. Assign each file to one writer. Subagents must not run generation chains, gates, commits, deployment or edit governance; main consolidates and runs them sequentially. Review actual diffs, not agent self-evaluation.

For product behavior/statistical meaning/scope ambiguity ask the user with concise alternatives. Resolve local implementation details within confirmed goals using the smallest reversible choice. After repeated failure change the approach; preserve three-line handoff: tried / failure / next action.

## Verify the affected layer

- Statistics/data/contracts/API: run node tests/verify.js, including original fixture, arbitrary-week synthesis, real restart and sabotage. Do not generate expected numbers from the engine under test and call that independent evidence.
- UI: build with npm --prefix web run build, run verify.js and node tests/browser.mjs, then start the dev server and exercise golden/failure paths in a real browser. Built regression reads dist, not the dev server.
- Responsive audit: 320/360/390/412 widths, light/dark. Measure horizontal overflow and actual horizontal scrolling, visible interactive controls at least 44px, focus/deep links, theme layout shifts, empty/data/expanded/failure states. Capture screenshots with CDP emulation rather than window dimensions. Keep live-date and fixture-date evidence labelled.
- Console audit: capture Runtime.exceptionThrown, console error and Log error events. Vue-caught errors may not appear as uncaught exceptions.
- Document changes: run the bundled checker, then verify changed Markdown pointers. Unknown runtime paths/placeholders are not evidence of missing source files.
- Research claims: trace each claim to authors/year/publication and DOI/PMID when applicable, explicitly mark unavailable identifiers, preprints and verification limits. A valid citation format does not establish scientific truth. Do not label personal transfer parameters as study-derived.
- Visual evidence proves mechanical properties, not aesthetic acceptance. The user performs final human acceptance.

## Deliver without overclaiming

Update TODO every hundredth-version step: distinguish ideas from approved directions, remove verified completed work, retain unresolved dependencies. Change version in package.json and sync lockfile. Create new local commits only when authorized, review staged files and secrets, never bypass hooks or modify git config.

Remote pushes occur only at tenth-version milestones and only to the explicitly authorized destination. Deployment timing, host, SSH identity, anonymous-access risk and AI quota come from current TODO decisions. Do not deploy early, create a public repository, overwrite an existing repository/service or claim deployment from a local build. Back up before shared-server replacement and verify health/restart/readback.

Keep progress concise. A completion receipt states outcome, measured evidence, changed scope, unverified boundaries and next owner. Separate completed facts from future plans. Never substitute tool-call counts for billing/token usage. Use status emoji only when explicitly requested.

## Adapted experience and package

This workflow adapts the checks from the existing rpl-handoff, rpl-site-audit, rpl-doc-pointers and rpl-citation-audit Skills in the user's RPLRef mirror. It does not redistribute their scripts or inherit Android rules, old gate commands, three-theme assumptions or old deployment targets. Existing Roast Raw CDP tests remain the executable UI evidence; no additional runtime dependency is introduced.

Validate with:

```sh
server/.venv/Scripts/python.exe .qoder/skills/roast-raw-agent/scripts/check_skill.py --root .
```

Package only this Skill directory into Agent.skill. Exclude project data, screenshots, Ref, credentials, environment files, databases and caches. The archive is a ZIP with roast-raw-agent/SKILL.md at its entry. Project source and packaged archive do not imply global installation or current-session catalog activation.
