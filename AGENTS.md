# AGENTS.md

## Entry and authority

Read [.qoder/skills/roast-raw-agent/SKILL.md](.qoder/skills/roast-raw-agent/SKILL.md), then [TODO.md](TODO.md) current work and approved decisions. The Skill owns the complete workflow; this file is its entry and safety summary, not a competing specification. [README.md](README.md) owns setup/API/recovery; [docs/项目交接.md](docs/项目交接.md) owns detailed product contracts. Read relevant headings only. User's latest explicit instruction outranks old prose; tests are evidence, not product decisions.

After entry or compression, from the Roast Raw root run:

```sh
git status --short
git log --oneline -5
node tests/verify.js
```

No completed zero exit code means no all-green claim. UI changes also require build, browser regression and real browser use. Report unverified layers explicitly.

## Safety boundaries

- Only Web: Vue/Vite/Motion One + FastAPI/SQLite. No Android/WebView/APK, offline training cache or sync service. English UI, handwritten CSS, anatomy default-visible, editorial report layout.
- Ref and the old project are read-only. Old Skills may be inspected; never run old build/deploy workflows or touch the old server. The only approved Ref edit changes SSH root to ubuntu in Ref/07_Permissions/ACCESS.md.
- Never print, commit or package keys/environment secrets/databases. AI/GitHub use process environment, SSH uses key/config. Never alter permissions or evade a denied operation. Credential steps are in Ref/07_Permissions/ACCESS.md; current TODO decisions override stale timings there.
- Keep fail-closed imports, fixed Asia/Shanghai calendar, arbitrary weeks, actual-only completion and explicit zero sets. Preserve historical records/prescription versions. Back up before migration; do not reinterpret old fatigue.
- Do not hand-edit generated data/dist, loosen tolerances, delete assertions or neutralize sabotage. Statistics, calendar, schemas and tokens each retain one source.
- Keep raw sets, SBD equivalent capacity and muscle coefficients distinct. Consult current decisions before policy changes; retain legacy fixture verification.
- Do not deploy/push early, overwrite shared services/repositories, delete source data or perform destructive git operations. Current destination/timing approval is scoped in TODO.md; milestone policy is not blanket permission.

## Work and handoff

Delegate by exclusive file ownership; only main runs generation, gates and commits. Verify actual diffs. Ask about unresolved product/statistical/scope decisions; choose small reversible implementation details within confirmed goals. Update TODO every hundredth-version step; remove only verified work. Create local new commits between tenth-version remote milestones. Version comes only from web/package.json and matching lockfile.

New requirements that do not belong to the current milestone go into the TODO backlog, never into the active version scope; re-prioritize unfinished and unassigned TODO items when adding them. Do not silently expand a milestone.

Report concise outcome, actual evidence, changed scope, unverified boundaries and next owner. Separate facts from plans. Do not claim human acceptance, tool availability, deployment or usage figures without evidence. Use status emoji only when explicitly requested.

## Capabilities, not products

Use whatever installed tooling provides these capabilities; if none is installed, install a suitable compliant one or fall back to built-in tools. Never depend on a specific extension name or version.

- UI evidence: automated regression plus a real browser for golden/failure paths; screenshots at the audited widths and themes.
- Independent review: UI and delivery changes are reviewed by a session or reviewer that did not implement them; findings name exact locations, not vague taste.
- Handover diagrams: architecture/flow diagrams for docs when useful; keep generated artifacts out of runtime code.
- Documents: office-format tooling for deliverables when requested; project facts stay in README/TODO/handover docs.

Mobile-device, generic-governance or duplicate-automation tooling adds nothing here; do not let it override the Skill's single governance entry or the Web-only boundary.
