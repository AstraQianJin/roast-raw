# AGENTS.md

## Entry and authority

Read the project Skill at `C:\Users\Astra\Desktop\RR\skills\roast-raw-agent\SKILL.md` (agent folder, outside this repo), then [TODO.md](TODO.md) for the execution queue and approved decisions. The Skill owns the workflow; this file is its entry and safety summary, not a competing specification. [README.md](README.md) owns setup and how to run; [docs/项目交接.md](docs/项目交接.md) owns detailed product contracts — read only the headings you need. The user's latest explicit instruction outranks old prose; tests are evidence, not product decisions.

After entry or compression, from the Roast Raw root run:

```sh
git status --short
git log --oneline -5
node tests/verify.js
```

No completed zero exit code means no all-green claim. UI changes also require build, browser regression and real browser use. Report unverified layers explicitly.

## Language and tone

- **Talk to the owner in Simplified Chinese.** Every reply, progress note, question and receipt body is Chinese; repository text, code, commit messages and UI copy stay English.
- **Terms: Chinese first, English identifier after.** One plain Chinese phrase, then the identifier in parentheses on first use.
- **Short by default.** Conclusion first, evidence second; no preamble, no restating the request, no "next I will" inside a completion.

## Safety boundaries

- Only Web: Vue/Vite/Motion One + FastAPI/SQLite. No Android/WebView/APK, offline training cache or sync service. English UI, handwritten CSS, anatomy default-visible. App pages reuse the old App visual language; the landing keeps the ported release-page style. Light = old ex warm paper, Dark = old dark.
- `Ref/` and the old project sources are read-only. Old Skills may be inspected; never run old build/deploy workflows. The old server stays usable for reference (timestamped backup before any overwrite); the old site keeps a friend link to the new one.
- Never print, commit or package keys, environment files, databases or session tokens. AI/GitHub use process environment, SSH uses key/config. Never alter permissions or evade a denied operation.
- Keep fail-closed imports, fixed Asia/Shanghai calendar, arbitrary weeks, actual-only completion and explicit zero sets. Preserve historical records and prescription versions; back up before migration; never reinterpret old fatigue as positive recovery.
- Do not hand-edit generated data or `web/dist`, loosen tolerances, delete assertions or neutralize sabotage. Statistics, calendar, schemas and design tokens each retain one source.
- Keep raw sets, SBD equivalent capacity and muscle coefficients distinct. Consult current decisions before policy changes; keep the legacy fixture chain intact.
- Do not overwrite shared services or repositories, delete source data or run destructive git operations. **Push and deployment happen only when the owner explicitly orders them** (see the running rules below).
- **Running rules for this round (owner ruling 2026-11-15)**: every 0.01 step ends in a local commit plus local build plus local screenshots; **no push, no formal deploy, and the earlier "stop-and-deploy preview" clause is suspended**. Stop-and-deploy resumes only when the owner says so. A stop without a preview is complete as long as the commit exists and `BOUNDARY` states "未部署".

## Permissions and environment (read before touching the live service)

These facts are easy to forget and expensive to rediscover. They are pointers and rules, never secret values.

- **Production host**: SSH alias `roast-raw` (identity `ubuntu`), service directory `/opt/roast-raw`, systemd unit `roast-raw`, environment file `/etc/roast-raw.env` (root-owned, mode 600), public URL `http://82.157.146.30/`. Landing is public; every `/api/*` journal route is account-gated. The running server is currently the 0.20 build.
- **Deploy rewrites the environment file.** `server/tools/deploy.py` writes `/etc/roast-raw.env` from the local process environment on every run; it does not merge. `RR_ACCESS_USERNAME` and `RR_ACCESS_PASSWORD` are required; `DEEPSEEK_API_KEY` is only written when present locally, so a deploy without it silently deletes AI access. After any deploy call `/api/ai/status?cycle_id=…` and require `configured: true`. Never echo the key. Record the production worker count in this section when it is next measured — the scoped cache bound (64 views) is per worker and must not be re-derived from it.
- **Key locations**: owner credentials and DeepSeek live in user-level environment variables on this Windows host and in the server env file; GitHub uses `GH_TOKEN` (user environment) because `gh` is not installed — call the GitHub REST API with `Invoke-RestMethod`. `C:\Users\Astra\Desktop\RR\ref-projects\rplref\_credentials` and `Ref/07_Permissions` are read-only pointers; never print, copy or commit their contents.
- **Local preview is not production.** `tests/serve_fixture.py` runs without the access gate and without the DeepSeek key (fixture mode needs `RR_ALLOW_OPEN_FIXTURE=1`, which is never set on a deployment host), so "DeepSeek is not configured" locally is expected. AI behaviour is only evidenced against a deployed host.
- **Old projects and references**: `Roast PowerLifting` (original app, read-only) and `RPLRef` (its index, read-only) now live inside the agent area at `C:\Users\Astra\Desktop\RR\ref-projects\`, renamed `roast-powerlifting` and `rplref` (moved 2026-11-15, TODO §7). `rplref\_repo\mirror` was slimmed on 2026-11-15 — deletion record and restore paths are in `rplref\_repo\MIRROR_SLIMMED.md`. Absolute Desktop paths inside `Ref/` are pre-migration snapshots and stay unchanged on purpose.
- **Remote state is volatile.** Never infer a push or a deployment from a local build. The version comes from `web/package.json`, never from this file.

## Work and handoff

Delegate by exclusive file ownership; only main runs generation, gates, commits and deployments. Review actual diffs, not agent self-evaluation. Ask about unresolved product, statistical or scope decisions; resolve small implementation details yourself within confirmed goals.

New requirements that do not belong to the current milestone go into the TODO queue, never into the active version scope; re-prioritize unfinished items when adding them. Do not silently expand a milestone. Update TODO at each hundredth-version step; remove only verified work.

Commits: `git -c user.name=Astra -c user.email=astra@local commit` (the repo has no configured identity). Never `--amend`, `--no-verify`, or edit git config.

Plan then act in the same turn. When a plan is handed over, check every open question in it against a safe default; if each one has one, execute the plan now and record the defaults used. Waiting for a ruling is only legitimate when no default is safe or the action is destructive and irreversible. On 2026-11-15 a relocation plan was delivered with "execute later" and three open questions that already had defaults, so nothing moved until the owner demanded it — treat that as the failure mode this rule exists to prevent.

## Bulk filesystem work (measured on this host)

- **Disk questions go through an MFT reader, not a recursive shell walk.** WizTree (`C:\Program Files\WizTree\WizTree64.exe`) scans this 476 GB volume — about 1.85 M files and 689 k folders — in roughly 17 s, because it reads the NTFS master file table instead of opening files. `Get-ChildItem -Recurse | Measure-Object` costs one syscall and one Defender inspection per file and takes minutes; never use it to answer "what is filling the disk".
- **Repo-wide text search uses `git grep` or `rg`, not `Select-String -Recurse`.** Both are index- or parallel-backed. `rg` is present on this host in the DoubaoWork runtime; fall back to `git grep` for tracked files.
- **A scan's output must never live inside the tree it scans.** On 2026-11-15 an audit wrote its result file into `RR\` while enumerating `RR\`, so every pass copied the previous file into itself, and the file grew to 62 GB of logical size while starving the disk. Write scan output to the system temp directory, bound the walk with `-Depth` or an explicit exclusion, or name exactly the files to read.
- **Stopping a pipeline is not stopping the writer.** Before deleting a runaway file, read its size twice to confirm it stopped growing, and re-check after the delete.
- **Match the gate to the change.** Docs-only edits need the bundled Skill checker plus the changed pointers opened. The full `verify.js` takes minutes and is dominated by the Python suite, so reserve it for code, data, contract or migration changes.

## Receipts

A report is one of two kinds, and the reader must know which without guessing: **completion** (only what already happened and was verified) or **plan** (only what has not been executed). Never mix them in one block; when both are needed, completion first, then a lone `---` line, then the plan.

Completion skeleton — five lines, fixed order. Labels may be the English keys or 结果 / 证据 / 范围 / 边界 / 下一步; pick one set and keep the body in Chinese.

```
RESULT   one sentence: what changed, and whether it worked
EVIDENCE only re-checkable values: exit code, PASS/FAIL counts, sha256, HTTP status, measured px, file path
SCOPE    files, screens or layers actually touched
BOUNDARY what was not done or not verified, and why — an empty BOUNDARY means the receipt is false
NEXT     owner plus action, each tagged GO / ASK / HUMAN
```

Plan skeleton: `GOAL` (one judgeable sentence), `STEPS` (numbered, each naming its artifact), `ORDER` (prerequisites or "none"), `ASK` (the decision the owner must make, with options and costs — or an explicit "nothing to decide"). A step without an artifact is not a step.

### Evidence widths (device protocol, owner ruling 2026-11-15)

- The reference phone is the owner's HONOR 500 Pro: 6.55 in panel, 2736×1264 physical pixels, so roughly a 421 px CSS viewport at DPR 3. Every responsive claim is captured at that viewport, at 320 px as the narrow floor, and at 1280 px for desktop.
- Never hardcode a device width in product CSS, tests or prose. Screenshot scripts take the width from `RR_DEVICE_WIDTH` (default 421) and record the value the page actually reported through `window.innerWidth`; a new phone changes the variable and this paragraph, nothing else.
- Report the measured numbers, not the intent: overflow (`scrollWidth - clientWidth`), control height, and the width each screenshot was taken at.

### What counts as evidence

Evidence is a value someone else can re-obtain. Feelings, tool-call counts and a model's own assessment are not evidence.

| Layer | Proof | Does not prove |
|---|---|---|
| Statistics, data, contracts, API | `node tests/verify.js` exit code and check count | that any screen renders |
| UI mechanics | `npm --prefix web run build`, `node tests/browser.mjs`, then real browser use | that the owner accepts the look |
| Responsive and theme | CDP screenshots at the audited widths in both themes, overflow measured | aesthetic acceptance |
| Deployment | `deploy.py` access-contract output plus a probe from the public host | that a local build is live |
| Documents | bundled Skill checker, then each changed pointer opened | that the prose is correct |

A local build is never a deployment. A green suite is never human acceptance. Never quote a version, assertion count, tolerance or check ID from memory — read it from the source named in the Skill's fact table. If a suite fails, report the red baseline before touching it; a load-sensitive failure means an isolated re-run, never a widened timeout.

### Next-step ownership

- `GO` — the agent can run it now: build, suites, screenshots, preview or deploy once authorized, public probes.
- `ASK` — the owner must rule first: scope, order, credentials, statistical policy.
- `HUMAN` — only the owner can do it: aesthetic acceptance, real-environment sign-off.

`tests/browser.mjs` has been a red baseline since 0.21 (theme toggle removed, register page changed) and is rewritten in 0.35; until then it is never green-light evidence.
