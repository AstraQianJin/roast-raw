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

## Language and tone

- **Talk to the owner in Simplified Chinese.** Every reply, progress note, question and receipt body is Chinese, regardless of the repository, code, commit messages or UI copy being English. Speaking English to the owner is a defect, not a style choice.
- **Product copy stays English.** Interface strings, button labels, empty states and errors remain English by product ruling; Chinese belongs to conversation, documents and receipts.
- **Terms: Chinese first, English identifier after.** One plain Chinese phrase, then the identifier in parentheses on first use; never open with a bare abbreviation.
- **Short by default.** Conclusion first, evidence second; no preamble, no restating the request, no "next I will" inside a completion.

## Safety boundaries

- Only Web: Vue/Vite/Motion One + FastAPI/SQLite. No Android/WebView/APK, offline training cache or sync service. English UI, handwritten CSS, anatomy default-visible. App pages reuse the old App visual language and keep no original decorative inventions beyond the barbell load UI and the muscle map (user ruling 2026-11-14); the landing keeps the ported release-page style. Light = old ex warm paper, Dark = old dark.
- Ref and the old project source are read-only. Old Skills may be inspected; never run old build/deploy workflows. The old server is fully usable per user ruling 2026-11-14 (timestamped backup before any overwrite); after 0.20 keep the old site plus a friend link to the new site. The only approved Ref edit changes SSH root to ubuntu in Ref/07_Permissions/ACCESS.md.
- Never print, commit or package keys/environment secrets/databases. AI/GitHub use process environment, SSH uses key/config. Never alter permissions or evade a denied operation. Credential steps are in Ref/07_Permissions/ACCESS.md; current TODO decisions override stale timings there.
- Keep fail-closed imports, fixed Asia/Shanghai calendar, arbitrary weeks, actual-only completion and explicit zero sets. Preserve historical records/prescription versions. Back up before migration; do not reinterpret old fatigue.
- Do not hand-edit generated data/dist, loosen tolerances, delete assertions or neutralize sabotage. Statistics, calendar, schemas and tokens each retain one source.
- Keep raw sets, SBD equivalent capacity and muscle coefficients distinct. Consult current decisions before policy changes; retain legacy fixture verification.
- Do not overwrite shared services/repositories, delete source data or perform destructive git operations. Git push to the private remote and the formal acceptance deployment happen only at 0.20 (destination scoped in TODO.md). Stop-and-deploy preview below is the standing exception for preview builds.
- Stop-and-deploy preview (user ruling 2026-11-14): whenever work stops for any reason (batch close, blocker, waiting on a ruling), first create the local commit, then deploy the current build to the new server as an HTML preview so the owner can inspect it in a phone browser. The preview keeps the release landing public and gates the journal API behind account sign-in (owner seeded from the environment-injected username/password at deploy time, never written to repo, docs or bundle). Preview deploys reuse the same timestamped-backup pipeline as the formal deployment.

## Work and handoff

Delegate by exclusive file ownership; only main runs generation, gates and commits. Verify actual diffs. Ask about unresolved product/statistical/scope decisions; choose small reversible implementation details within confirmed goals. Update TODO every hundredth-version step; remove only verified work. Create local new commits between tenth-version remote milestones. Version comes only from web/package.json and matching lockfile.

New requirements that do not belong to the current milestone go into the TODO backlog, never into the active version scope; re-prioritize unfinished and unassigned TODO items when adding them. Do not silently expand a milestone.

Report through the receipt contract below. Do not claim human acceptance, tool availability, deployment or usage figures without evidence. Use status emoji only when explicitly requested; the receipt labels carry the structure without them.

## Receipts

A report is one of two kinds, and the reader must know which without guessing:

- **Completion** — only what already happened and was verified.
- **Plan** — only what has not been executed yet.

Never mix them in one block. When both are needed, completion first, a lone `---` line, then the plan. A completion containing "next I will", or a plan containing "already fixed", is a defective receipt.

### Completion skeleton

Five fields, fixed order, one line each. The label may be the English key or its Chinese equivalent (结果 / 证据 / 范围 / 边界 / 下一步); choose one set for the whole receipt and keep the content in Simplified Chinese.

```
RESULT   one sentence: what changed, and whether it worked
EVIDENCE only re-checkable values: exit code, PASS/FAIL counts, sha256, HTTP status, measured px, preview URL
SCOPE    files, screens or layers actually touched
BOUNDARY what was not done or not verified, and why — an empty BOUNDARY means the receipt is false
NEXT     owner plus action, each tagged GO / ASK / HUMAN
```

`RESULT` says FAIL when it failed. "Basically done", "should be fine" and "looks good" are not results. One line carries one fact; prefer a list over a table unless the rows are genuinely parallel data.

### Plan skeleton

```
GOAL   one sentence that can be judged done or not done
STEPS  numbered, each naming its artifact: a file, command output, screenshot or URL
ORDER  prerequisites and blockers, or "none"
ASK    the decision the owner must make, with options and costs — or "nothing to decide"
```

A step without an artifact is not a step. `ASK` is never left blank; when there is nothing to rule on, say so explicitly.

### What counts as evidence

Evidence is a value someone else can re-obtain. Feelings, tool-call counts and a model's own assessment are not evidence. Which command proves which layer:

| Layer | Proof | Does not prove |
|---|---|---|
| Statistics, data, contracts, API | `node tests/verify.js` exit code and check count | that any screen renders |
| UI mechanics | `npm --prefix web run build`, `node tests/browser.mjs`, then real browser use | that the owner accepts the look |
| Responsive and theme | CDP screenshots at the audited widths in both themes, overflow measured | aesthetic acceptance |
| Deployment | `server/tools/deploy.py` access-contract output plus a probe from the public host | that a local build is live |
| Documents | bundled Skill checker, then each changed pointer opened | that the prose is correct |

A local build is never a deployment. A green suite is never human acceptance. Never quote a version, assertion count, tolerance or check ID from memory — read it from the source named in the Skill's fact table, and keep volatile numbers out of this file.

When a suite fails, report the red baseline before touching it. If the failure is load-sensitive rather than a product defect, say so and show the isolated re-run; never widen a timeout or tolerance to make it pass.

### Next-step ownership

- `GO` — the agent can run it now: build, suites, preview deploy, screenshots, public probes.
- `ASK` — the owner must rule first: scope, order, credentials, statistical policy. The agent runs it after the ruling.
- `HUMAN` — only the owner can do it: aesthetic final acceptance, real-environment sign-off. The agent prepares evidence and waits.

### Stopping

A stop without a preview is an incomplete stop. At every stop — batch close, blocker, or waiting on a ruling — commit locally, deploy the preview, and put the preview URL and its access-contract result in `EVIDENCE`. If the deploy itself is the blocker, state that in `BOUNDARY` rather than implying the site is updated.

### Worked example

Braces are placeholders for whatever the run actually produced. Never copy example values into a real receipt.

```
RESULT   The release landing is public; the journal API now requires an account.
EVIDENCE verify.js exit {0}; browser.mjs exit {0}; deploy access contract {n}/{n} PASS;
         GET / {200}, GET /api/plan {401}, owner sign-in {200}; preview http://{host}/
SCOPE    server/app/main.py gate, web/src/App.vue guard, server/tools/deploy.py post-deploy check
BOUNDARY Aesthetic acceptance belongs to the owner; HTTP only, no TLS; AI quota path not re-tested.
NEXT     GO re-probe after any redeploy · HUMAN owner signs in on a phone and accepts the look
```

The owner can re-obtain every number in `EVIDENCE`, sees exactly what was touched in `SCOPE`, and knows in `BOUNDARY` what is still unproven. That is the whole point of the format.

### Two defective receipts

**Mixing fact and intention.** "I made the landing public, next I'll check the sign-in redirect, should be fine." The first clause is a verified fact, the second is unexecuted, and "should be fine" is a guess dressed as a conclusion. Split into a completion carrying only the proven part, `---`, then a plan whose steps each name an artifact.

**Local build claimed as live.** "Sign-in is fixed, all green." No exit code, no public probe, no preview URL — the owner cannot tell whether the server changed or only the working tree did. Name the suite and its exit code, the deployed access-contract result, and the URL the owner can open.

## Capabilities, not products

Use whatever installed tooling provides these capabilities; if none is installed, install a suitable compliant one or fall back to built-in tools. Never depend on a specific extension name or version.

- UI evidence: automated regression plus a real browser for golden/failure paths; screenshots at the audited widths and themes.
- Independent review: UI and delivery changes are reviewed by a session or reviewer that did not implement them; findings name exact locations, not vague taste.
- Handover diagrams: architecture/flow diagrams for docs when useful; keep generated artifacts out of runtime code.
- Documents: office-format tooling for deliverables when requested; project facts stay in README/TODO/handover docs.

Mobile-device, generic-governance or duplicate-automation tooling adds nothing here; do not let it override the Skill's single governance entry or the Web-only boundary.
