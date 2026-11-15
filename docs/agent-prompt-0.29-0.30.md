# 交接提示词 · 0.29 收尾 + 0.30（计划未开始）

把下面整段粘给新 Agent 即可。仓库在 `C:\Users\Astra\Desktop\Roast Raw`（Windows，PowerShell）。

---

## 角色与边界

你是 Roast Raw 的实现 Agent。项目是力量举训练账本 Web 应用（Vue 3 + Vite + 手写 CSS，FastAPI + SQLite），单人项目，用户是唯一产品负责人。

开工前必须按顺序读，不许凭记忆：

1. `C:\Users\Astra\Desktop\Roast Raw\AGENTS.md`（治理与回执契约）
2. `C:\Users\Astra\Desktop\Roast Raw\.qoder\skills\roast-raw-agent\SKILL.md`（流程、证据分层、提交纪律）
3. `TODO.md` 的「当前执行」「本轮路线」「0.29 施工详单」「0.30 施工详单」「已确认决策」「落地方案：关键代码 · 关键数据 · 审美」

四条绝对边界：不 push、不部署（用户 2026-11-15 裁定暂停「停即部署预览」）；不改 `git config`（提交用 `git -c user.name=Astra -c user.email=astra@local commit`）；不手改 `data/plan.json` 与 `web/dist`；UI 文案英文，与你沟通用简体中文。

## 当前状态

- 版本号唯一来源 `web/package.json`（现 `0.0.28`），`web/src/App.vue` 的 `releaseVersion` 同步。
- 已提交：`3b946cf`（0.28）、`32e923e` + `7ed231c`（0.29 的 T2/T1/P0-03a 与配套单测）。
- 0.29 已完成：T2 空口令 fail-closed（`RR_ALLOW_OPEN_FIXTURE=1` 只给夹具，`serve_fixture.py` 与 `tests/verify.js` 已注入）、T1 `_scoped` 有界 LRU（64 条 / 30 分钟 TTL / 锁 / 视图不与 base 共享字典）、P0-03a 六处假宣传文案。
- 0.29 剩余：**P0-01**（刷新闪 404 实测与必要时骨架）、**P0-02**（首页数字同源）。
- `tests/browser.mjs` 自 0.21 起是红基线，不得当绿灯证据；重写排在 0.35。

## 任务一：P0-01 刷新不闪 404

按 `TODO.md`「0.29 施工详单 ①」与「关键代码 2」执行：

- 起夹具服务（`tests/serve_fixture.py`，它已设 `RR_ALLOW_OPEN_FIXTURE=1` 并向 stderr 打印警告）。
- CDP 设 3M 带宽（download/upload 375000 B/s，latency 40ms），连续刷新 10 次。
- 每次取 **200ms、800ms** 的 `document.body.innerText`，再等最终态（上限 30 秒）计划内容出现。
- 断言：三处都不出现 `NOT IN THIS PLAN`、`404`、`NO SESSION`、`Return to the cycle`；正文非空（「立即」时点不判空）；最终态 30 秒内命中计划内容，不得停在骨架。
- 只有实测失败才改 `web/src/App.vue`：骨架块固定高度、`!plan` 分支先于 `!validRoute`、`todayCtaLabel` 空值时输出 `·`。改完重跑 10 次。
- 证据写到 `C:\Users\Astra\Desktop\RR\shots-0.29\p0-01-refresh.json`。

## 任务二：P0-02 首页数字同源

按「0.29 施工详单 ②」与「关键代码 3」执行：

- 新增 `server/tools/landing_facts.py`：读 `data/plan.json`，先 `print` 一条真实 `session` 确认键名，再做映射；按 `week` + `day` 选课日（默认 W01 · DAY A）；输出 `web/src/landing-facts.json`（紧凑 JSON）。
- 字段：`planId / startDate / week / day / date / label / lifts[{lift, movement, top_kg, pct, sets, reps}] / set_count / day_total_kg / cycle_total_kg / tonnage_basis`。
- 口径：`top_kg` 不含热身；`set_count` 为该日全部处方组数；`day_total_kg` = Σ(重量×次数×组数)；`cycle_total_kg` 必须等于 `meta.cycleTonnageKg`；`pct` = 顶重 / 该动作训练最大值（`meta.anchors` 同源），无同源值则不输出该字段。
- 前端改点：`web/src/components/WelcomeView.vue` 的 hero 徽标、三张卡、分享卡，以及 `web/src/App.vue` 的 NEXT 药丸（`todayCtaLabel` / `todayCtaDate`），全部绑定 facts，删除字面值 `110.5 / 70.5 / 4,041 / 17 SETS / W05 · DAY B`。
- `tests/verify.js` 新增 `landingFactsCheck()`：重跑生成器与产物逐字节相等；再从 plan 独立复算三个数，与产物一致（不调用被测函数）。
- 全仓 grep `No account|Zero account|CSV|XLSX|Chinese UI|rest timer|Phone app` 应清零。

## 任务三：0.30 计划未开始（本轮先出方案不改代码，等用户确认日期口径后再动）

按「0.30 施工详单」与「关键代码 4/5/6」执行：

- 重算只走脚本 `server/tools/gen_data.py` → `synth_plan.py`；目标 `startDate 2026-11-23`、`endDate 2027-02-21`、测试日 `2027-02-20`；`motto` 里的天数不变、绝对日期由生成器填。
- `planId` 若改：归档旧周期、播种新周期，不原地改日期；先快照，迁移后读回。
- 断言：锚点日期直接读 `plan.meta.startDate`；「必须落在测试周」改成按周次相对；`tests/browser.mjs:1245` 改为从 plan 读日期。
- 未开始态扩 `web/src/components/CyclePrestart.vue`：倒计时（目标取 `plan.meta.startDate`）、首次课预习、热身与活动度、恢复基线（只给采样提示，缺数据 `Not sampled`，不写 0）；不发 `/api/ai/*` 请求。

## 验收与回执

- 每版：`node tests/verify.js` 退出 0、`npm --prefix web run build` 退出 0，截图存 `C:\Users\Astra\Desktop\RR\shots-0.29` / `shots-0.30`。
- 提交前看 `git status` 与 diff，确认无凭据、无 dist、无 Ref 改动；提交信息写清版本与改动。
- 回执按 `AGENTS.md` 五段：RESULT / EVIDENCE / SCOPE / BOUNDARY / NEXT，中文内容、结论在前；`browser.mjs` 红基线要明说是红。
- 停止时提交本地版本；**本次不部署**，BOUNDARY 写明「未部署」。

## 禁做清单

- 不 push、不部署、不启 systemd、不改 `/etc/roast-raw.env`。
- 不改 `git config`、不 `--amend`、不 `--no-verify`。
- 不手写首页数字、不手改 plan 日期、不把整份 `plan.json` 塞进前端 bundle。
- 不弱化或删除断言来换绿灯；发现旧断言失效要说明它为什么失效再改。
