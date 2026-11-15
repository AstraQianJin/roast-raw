# TODO — Roast Raw 执行队列

> 本文件只记录**未完成工作、已确认决策和执行契约**。完成历史一律查 `git log`，此处不复述。
> 版本唯一来源是 `web/package.json`（patch 位映射页面显示的第 `0.xx` 版）。发生冲突时的优先级：**用户最新裁定 > 本文件 > `docs/项目交接.md` > 旧散文**。
> 执行 Agent 的流程纪律在 `AGENTS.md` 与 `C:\Users\Astra\Desktop\RR\skills\roast-raw-agent\SKILL.md`；本文件只回答「做什么、做到什么算完」。

---

## 0 · 状态快照（2026-11-15 · 0.37 收工）

| 项 | 值 |
|---|---|
| 版本 | `web/package.json` = **0.0.38**；0.29–0.38 本地提交，未 push、未部署（0.39 日历、0.40 上线按用户指令紧随） |
| 工作树 | 以本节所在提交为准 |
| 最近提交 | 见 `git log --oneline -3` |
| 门禁 | `node tests/verify.js` exit 0（334 Python 用例 / 6637 检查）；`npm --prefix web run build` exit 0；`node tests/browser.mjs` exit 0（15 项断言、8 张截图），`--sabotage` exit 1；`check_skill.py --root .` PASS |
| 红基线 | 无 |
| 部署 | 线上仍是 0.20 版 `http://82.157.146.30/`。本轮**不 push、不部署**（用户 2026-11-15 裁定） |
| 证据落点 | `RR\shots\0.36\`（会员矩阵 9 张 + tour 3 张 + `membership-evidence.json`）、`RR\shots\0.37\`（`account-panel-421.png` 及套件 8 张） |
| 老项目 | 两个老项目已迁 `RR\ref-projects\`；`rplref` 瘦身记录见 `RR\ref-projects\rplref\_repo\MIRROR_SLIMMED.md` |

**长期边界**：只做 Web（Vue 3 + Vite + Motion One + FastAPI + SQLite）；界面英文、对话中文；`Ref/` 与两个老项目只读；不手改 `data/plan.json` 与 `web/dist/`；不弱化断言、不中和 sabotage。

**0.30 留下的既成事实**（后续版本必须遵守，勿重新推导）：

- 计划日历唯一真相是 `data/plan.json` 的 `meta.startDate`（现为 **2026-11-23**，结束 2027-02-21，测试日 2027-02-20）。
- 移动日历只能 `server/tools/gen_data.py --start-date <ISO>`：它会按同一 delta 平移源里所有日期字面量，并让 `meta.motto` 的 `TEST <iso>` / `<x.x>W (<n> days to test)` 由日历填充。
- `planId` 变更必须 `server/tools/roll_cycle.py`：先快照，再归档旧周期（保留计划/日志/问卷可回读）、播种新周期；**禁止原地改日期**。本机 `data/roastraw.sqlite3` 已按此完成 `rpl-raw-2026-11-16`（archived）→ `rpl-raw-2026-11-23`（active）。
- `data/plan.json` 与 `web/src/landing-facts.json` 都是生成物；`day D` 标题里的 `(W13 TEST)` 来自源表，属于源文本，不是手写。
- **schema v6（0.32）**：`cycles` 复合主键 `(account_id, id)`，13 张子表带 `account_id` + 复合外键；迁移只能走 `Store.upgrade_cycle_keys()`（快照→重建→`PRAGMA user_version=6`），遇到孤儿会点名中止，`activate_plan` 只接受 v6。任何新子表都必须带 `account_id` 并挂到 `(account_id, cycle_id)`，否则 `tests/test_isolation.py` 直接红。
- **进程环境**：用户级 `PYTHONPYCACHEPREFIX` 曾指向 `C:\Users\Astra\Desktop\RPLRef\Cache\pycache`，会在桌面凭空生成一个「RPLRef」字节码镜像（2026-11-15 已改指向 `%LOCALAPPDATA%\Temp\rr-pycache` 并删除该目录）。屏幕外跑 Python 时字节码落点看这个变量，不是看仓库。

- **schema v7（0.34）**：新表 `test_results(account_id, cycle_id, item_id, …)` 存一级四变式、二级四变式与 5km 结果，主键 `(account_id, cycle_id, item_id)`，外键挂 `cycles(account_id, id)`；迁移只能走 `Store.upgrade_test_results()`（快照→建表→`PRAGMA user_version=7`）。旧升级步骤（`upgrade`/`upgrade_prescriptions`/…/`upgrade_cycle_keys`）都把 7 当「已完成」，`activate_plan` 只接受 6 或 7。写入需 `test_week` 档，读与导出全档开放。本机 live 库已迁移：`user_version` 6→7、既有表行数零差、`foreign_key_check` 空。

---

## 1 · 下一动作：0.38 审查收口 → 0.39 日历 → 0.40 上线（用户指令，连续执行）

**接手指令**：0.38 = 一个**未写过本轮代码**的会话审查 0.29–0.37，逐条实测 §4 `P1` 清单与 `docs/项目交接.md` §12 推断项，清单逐条关闭后交用户。0.39 发布（push + 部署）**只在用户另行下令后**执行。

**0.38 审查基线**：审查报告 `RR\review-0.38.md`（0 FAIL / 5 部分 / 10 PASS，缺陷 D-01～D-09、U-01/U-02）。本轮按报告关闭：D-01 兑换后重取 plan/analysis/geometry 且缺 geometry 时降级占位；D-02 动作 register 改用 R5 已到期口径（`asOf` + `min(actual, planned)`）；D-03 落地页 nav/footer/邀请链接全部 44px 命中区；D-04 `aria-expanded` + `aria-controls`；D-05 `BarbellStrip` 赛扣默认 0；D-06 分享卡 watch 赛扣；D-07 `SHOTS_DIR` 跟随 `package.json` 版本；D-09 UI 与画布片组对拍断言；D-08 文档漂移（§12 指向、31 链接/20 表、`user_version=7`、12 项能力）已改。U-01 按用户裁定：测试周注记拆到 `testTitleEn`，仅测试周显示。版本 0.0.38。

**0.37 已交付（R8）**：`web/src/components/MembershipPanel.vue` 挂在 VAULT 的 `#account` 段：档位豆数 + 档名、永久档 `PERMANENT` / 限时档 `UNTIL <北京时间日期>`、`SIGNED-IN DEVICES x / 5`（`GET /api/membership/sessions`，本机标 `THIS DEVICE`，其他设备可逐个 `DELETE` 登出）、`Redeem a code` 走 `POST /api/membership/redeem` 并 `refreshSessionOnce` 刷新会话能力表；`RegisterView` 支持 `/register?code=` 预填（读 `URLSearchParams`，转大写）。`verify.js` 新增 `membershipPanelCheck()`，`browser.mjs` 新增账户面板断言（档位/设备数/44px/兑换回执）。

**0.36 已交付（R6 + R7）**：`MembershipMatrix.vue` 从 `web/src/membership.json` 渲染四列（Ultra 不占列）+ 手机 `scroll-snap` 四卡；`WelcomeView.vue` 新增 sticky `.wl-top`、`wl-share`/`wl-toast`、滚动驱动 `wl-tour`（替换原 deck 手势）；`docs\审美回炉清单.md` 补老站对照表。

**0.35 留下的既成事实**（后续版本必须遵守）：

- 完成率只有一个实现：`server/app/stats/completion.py`。`engine.analyze(plan, logs, mode, today=)` 透传日期，计划/日志视图用「今天」（`server/app/calendar.py` 的 `SHANGHAI`），review 用周期结束日（整周期口径）。组件不再自己算百分比。
- `perWeek` 的 `tonnageKg` 现在给未四舍五入的原值，周期总数仍是 `r1` 后的一个数；页面上的 `139.6 t` 与周卡相加不再出现 `139.5`。
- 截图不进仓库：`tests/browser.mjs` 写 `SHOTS_DIR`（默认 `..\RR\shots\<release>`），`docs/shots/` 已进 `.gitignore`，6 张 `old-ref-*.png` 留在 `docs/ref-shots/`。


---

## 2 · 版本队列（0.29 → 0.39，顺序已定，不并行）

| 版本 | 主题 | 关键范围 | 验收判据 |
|---|---|---|---|
| ~~0.29~~ ✅ | 安全与首屏 | T2 空口令 fail-closed、T1 `_scoped` 有界 LRU、P0-01 刷新不闪、P0-02 首页同源、P0-03a 假宣传 | 已交付 `b0cbc64`；详单见 git |
| ~~0.30~~ ✅ | 计划未开始态 | 周期推迟到 2026-11-23、`CyclePrestart` 四区块 | 已交付 `6c56b7d` + `aa1cd8b`；重算零差 |
| ~~0.31~~ ✅ | 门控与出口 | T6 读开写关、T5 降档刷新、T3 孤表审计、P0-03b 导出、P0-04 `/about` | 已交付 `1397e65`；317 用例 / 6587 检查 |
| ~~0.32~~ ✅ | T4 迁移 | 复合主键 + 14 张表重建 + `user_version=7`（0.34 再升位） | 已交付 `0809155`；旧库行数零差、孤儿 0 |
| ~~0.33~~ ✅ | R4 视觉欠账 | GEAR 小片与单侧配片、Sheiko 热身（只给主项）、比赛三盏裁判灯、测试周四组 UI、赛扣开关 | 已交付 `556e88f`；实机 421/320/1280 无横向溢出，四交互各实点一次 |
| ~~0.34~~ ✅ | R4b 测试周真存 | 新表 `test_results`：八项变式 + 5km 入库；ASSAY 可对比、导出/分享卡带出 | 已交付 `745dba0`；八项 + 5km 写入读回一致（132.5 kg ×1 / 24:30），三档无横向溢出 |
| ~~0.35~~ ✅ | R5 + P1 | 完成率单函数、重写 `tests/browser.mjs`、P1 复核与清理、`docs/shots` 迁出 | 已交付；`verify.js` 334 用例 / 6633 检查 exit 0，`browser.mjs` 11 项 exit 0、`--sabotage` exit 1 |
| ~~0.36~~ ✅ | R6 + R7 | 首页会员对比矩阵；老站首页效果补齐（`--topH`、分享、滚动 tour） | 已交付；`verify.js` 334 用例 / 6636 检查 exit 0，`browser.mjs` 13 项 exit 0、`--sabotage` exit 1；1280 四列两币种、390 四卡、320 无溢出 |
| ~~0.37~~ ✅ | R8 | 账户内会员面板（档位、Pro 到期、设备 5、兑换码） | 已交付；面板实机 421 段实测：`Ultra` + `PERMANENT`、设备 `1 / 5`、控件 44px、`RR-BROWSER-PLUS` 回执；browser 15 项 exit 0 |
| **0.38** | 独立审查 | 未写代码的会话审 0.29–0.37，含 `docs/项目交接.md` §12 推断项逐条实测 | 审查清单逐条关闭；0.29 遗留的 P0-01 缺陷在此复核 |
| **0.39** | 发布 | 部署 + push（**只在用户另行下令后**） | `deploy.py` 访问契约全 PASS + 公网探测 + `/api/ai/status` `configured: true` |

---

## 3 · 已完成版本索引（详单不再复述，实现与判据查 git）

| 版本 | 提交 | 落地内容 | 证据 |
|---|---|---|---|
| 0.29 | `b0cbc64` | 空口令 fail-closed、`_scoped` 有界 LRU(64/30min)、刷新骨架与 `!plan` 次序实测、首页数字改由 `landing_facts.py` 单源、6 处假宣传清理 | `RR\shots\0.29\` |
| 0.30 | `6c56b7d` `aa1cd8b` | `gen_data.py --start-date 2026-11-23` 全站单源重算、`roll_cycle.py` 归档 `rpl-raw-2026-11-16` 并播种 `-11-23`、`CyclePrestart` 四区块、桌面 hero 按钮堆叠 | `RR\shots\0.30\` |
| 0.31 | `1397e65` | 读开写关（含免费档 DailyRecord 常驻 + 禁用表单）、403/`timed_until`/`visibilitychange` 三处一次性刷新、孤表审计 + 表级隔离、`/api/export/logs.csv`、`/about`、`cdp.mjs` 补 `Network.enable` | `RR\shots\0.31\` |
| 0.32 | `0809155` | `cycles` 复合主键、14 张表复合外键重建、写入/读取全线按账户过滤、导入 409 改「同账号占用」、审计扩到 29 条链接 | `RR\scratch\migrate-live-032.py` 输出 + `tests/test_ledger.py` |
| 0.33 | `556e88f` | 杠铃片算术抽成 `web/src/plate-load.js`（小片带数值标签、单侧配片、缺量上报）；`GearPlates` 小片柜进 GEAR；热身只列主项且无主项日不留空位；比赛三盏裁判灯（2 白 GOOD / 2 红 MISS）；测试周 SBD 三组 + 计划真实行第四组，各带独立输入；赛扣开关（设置内，默认关，设备本地）贯穿配片、分享卡与起跑页 | `RR\shots\0.33\` |
| 0.34 | `745dba0` | `testPlan` 补齐九项（一级四变式 / 二级四变式 / 5km）且全部落在证据测试日；`test_results` v7 表 + `upgrade_test_results()`；`GET/PUT /api/test-results`（写需 `test_week`、举重项 0.5kg 步进、跑步项要用时）与 `/api/export/tests.csv`；AttemptBoard 九行真存（44px 控件）、ASSAY 按 SBD 锚点算百分比、分享卡带「已记录/总数」一行；`test_results.py` 8 个新用例 | `RR\shots\0.34\` |
| 0.35 | 见 `git log` | R5 完成率收进 `server/app/stats/completion.py`（到期才进分母、`min(实际, 计划)`、显式零标 reviewed、三类分报、超额记 `extra`）；`engine.analyze(..., today=)` 透传，review 用周期结束日；`tests/test_completion.py` 8 用例 + `verify.js` 新增 `completionCheck()`（今天的分母由 plan.json 手算）；`tests/browser.mjs` 重写为绿灯基线（10 组断言 + `--sabotage`）并支持 `SHOTS_DIR`；`docs/shots` 183 张迁 `RR\shots\archive\`、6 张老参考留 `docs/ref-shots\`；P1 复核：吨数改由未四舍五入的周值相加、TrendView 不再显示 `S.Main|…` 内部标识，其余项复现不到 | `RR\shots\0.35\` |
| 0.36 | 见 `git log` | `MembershipMatrix.vue`：数据只读 `web/src/membership.json`（`verify.js` 断言无手抄价格/能力文案）、四列 + Ultra 条、Plus `RECOMMENDED`、CNY/USD 翻牌、`0fr → 1fr` 折叠、整列聚焦、`ResizeObserver` 写 `--topH`；手机 `scroll-snap` 四卡 + 四档标联动；`WelcomeView.vue` sticky 顶栏 + `wl-share`/`wl-toast`（share → clipboard → execCommand）与滚动驱动 `wl-tour`（sticky stage、`is-prev`、`--tour-p`、44px 圆点）；`docs/审美回炉清单.md` 补老站对照表；`browser.mjs` 增会员矩阵/手机卡/tour 三组断言 | `RR\shots\0.36\` |

**仍生效的生成物契约**（改生成器时守住，别再抄第二份）：

- `server/tools/landing_facts.py` 读 `data/plan.json` → 写 `web/src/landing-facts.json`；字段 `planId / startDate / week / day / date / label / lifts[] / set_count / day_total_kg / cycle_total_kg / tonnage_basis`。
- `day_total_kg` 是样例日（`W01 · DAY A`）且不含热身；`cycle_total_kg` 必须等于 `meta.cycleTonnageKg`；`pct` 与该动作 `meta.anchors` 同源，取不到就删字段并由前端隐藏。
- 消费方三处共用同一份 facts：`WelcomeView.vue` hero、分享卡、`App.vue` NEXT 药丸。换课日只重新生成，**不手写**。

## 4 · 后续版本规格（0.31 起，实现细节可自决，口径变动须先问）

### T3 · 孤表审计（已完成 0.31：`server/tools/audit_orphans.py` + `tests/test_isolation.py`，31 条链接 / 20 张表、live 库孤儿 0）

以 `store.py` 实际表为准（`cycles` `plans` `logs` `readiness` `readiness_v2` `archives` `body_metrics` `questionnaires` `ai_calls` `attempts` `deletion_tokens` `accounts`，外加处方版本表与会话表），逐表写「孤儿查询」（引用了不存在 `cycle_id` 的行数必须为 0），并写表级隔离单测：A 账户写、B 账户读不到。

### T4 · 主键与迁移（已完成 0.32：`Store.upgrade_cycle_keys()` 重建 14 张表到复合键、`user_version=7`（0.34 再升位）、导入 409 改「同账号占用」、`test_same_cycle_id_allowed_across_accounts`）

`cycles.id TEXT PRIMARY KEY` 全局唯一是缺陷：改成复合主键 `(account_id, id)`，相关表外键随之重建，`user_version` 升位，迁移前快照，导入 409 文案改为「同账号占用 / 另存新 ID」，单测改名 `test_same_cycle_id_allowed_across_accounts`。

### T5 · 降档主动刷新（已完成 0.31：403 重取 session、`timed_until` 一次性定时器、`visibilitychange` 补刷新；120 s 静置 0 次，无 `setInterval`）

403 → 立即重取 `/api/session`；`timed_until` 到点用**一次性定时器**；`visibilitychange` 回前台补一次刷新。**禁止轮询**（4C4G / 3M 带宽约束）。验收：静置一小时 `/api/session` ≤ 5 次。

### T6 · 读开写关（已完成 0.31：免费档 DailyRecord 可读、写入口锁；`tests/test_gates.py` 逐行成对）

自有数据 GET 放开、写入口锁；派生视图（`performance` / `geometry` / `vault`）整块锁。与 0.28 的差异：free 账号的 DailyRecord **不再整体隐藏**，改为可读、写入口锁。

### R4 · 视觉欠账（已完成 0.33，`556e88f`）

GEAR 小片与单侧配片；Sheiko 热身（只给主项）；比赛三盏裁判灯（2 白 = GOOD、2 红 = MISS）；测试周四组 UI：SBD 三组 + 计划里真实存在的行，各自独立输入行。实现细节查 git，判定口径见 `RR\shots\0.33\r4-evidence.json`。

### R4a · 赛扣（已完成 0.33，用户裁定「默认关、放设置里」）

- 语义：赛扣按**一对 5 kg** 计入总重；关时只有杆重是固定重量。
- 位置：VAULT 账户区 `Gear setup` 内的开关（`data-testid=collar-toggle`），**默认关**。
- 归属：设备级场地事实，存 `localStorage('rr.gear.collars')`，不随计划导出、不上服务器（沿用老项目「场地库存在本机」的裁定）。
- 贯穿：`GearPlates` 分片、`BarbellStrip` 文案、`AttemptBoard`、`CyclePrestart`、分享卡（含底部说明行）与 GEAR 摘要 chip 读同一开关。
- 不动配重口径：开关只改「杆 / 扣 / 片」的拆解，不改任何 `loadKg`、处方、统计或导出字段。

### R4c · 证据宽度协议（0.33 起，取代原「四宽取哪四个」问题）

- 基准机是用户实机**荣耀 500 Pro**（6.55″、2736×1264 物理像素、DPR 3 ⇒ 约 421 CSS px 视口）。
- 宽度不写死：截图脚本读 `RR_DEVICE_WIDTH`（默认 421），并把页面 `window.innerWidth` 实测值写进 evidence；换机只改变量与 `AGENTS.md` 的那段话。
- 每版响应式证据固定三档：实机宽、**320**（窄底线）、**1280**（桌面），报告横向溢出、控件可视高度与截图宽度。

### R4b · 测试周真存（已完成 0.34，`745dba0`）

- `meta.testPlan` 由 `gen_data.py` 生成：`tests` 声明 `sbd/tier1/tier2/fivekm`，`dates` 全部等于证据测试日，`items` 九项（`low_bar_squat`/`wide_grip_bench`/`sumo_deadlift`/`power_clean` 属 tier1；`ohp`/`pull_up`/`dip`/`barbell_row` 属 tier2；`five_km` 为 run）。`validation.py` 只校验组与 kind，不再要求 `testPlan.dates` 与证据日期逐键相等。
- `test_results` 存在每账户每周期的独立表里，SBD 试举仍在 `attempts`；读与导出全档开放，写要 `test_week`，降档后旧结果照样可读可导出。
- 界面：AttemptBoard 九行各带独立 Save（举重项 Load/Reps，5km 项 Time/Avg HR/Note，控件高 44px）；ASSAY Overview 新增 TEST DAY 区块，用对应 SBD 锚点算百分比；分享卡多一行 `TEST BATTERY n / 9 RECORDED`。

### R5 · 完成率口径（已完成 0.35：`server/app/stats/completion.py` + `engine.analyze(today=)` + `tests/test_completion.py` 8 用例 + `verify.js` 的 `completionCheck()`）

- 分母只算**到今天（Asia/Shanghai）已到期的计划组**，未来计划不进分母。
- 每组：有实际记录算完成；超额组取 `min(实际组, 计划组)`，不把完成率推过 100%。
- 显式记 0 组 = 有意跳过：进分母、不计完成，该场标「已回顾」，与「没打开」区分。
- 主项 / 变式 / 辅项**三类分开报**，不合加权总数；计划外加练单列 `extra`，不进完成率。
- 只在一个统计函数里实现，ASSAY Overview、动作 register、周卡共用。计划视图与日志视图按当天算；review 把 as-of 设成周期结束日，所以空周期评审给出 0% 而不是 `null`。

### R6 · 首页会员对比（已完成 0.36）

落地：`web/src/components/MembershipMatrix.vue`（约 340 行）。数据只从 `web/src/membership.json` 取，`verify.js` 的 `membershipMatrixCheck()` 断言四列、五档、12 项能力、组件内无手抄价格与能力文案、真 `<th scope>`、`ResizeObserver`、`prefers-reduced-motion`。桌面：Plus 列 `RECOMMENDED` 胶囊 + 深半档 + 两侧墨线、CNY/USD 180ms 翻牌、前 6 行默认展开其余 `grid-template-rows: 0fr → 1fr` 240ms（行始终在文档里，折叠时 `aria-hidden`）、悬停/键盘整列聚焦、勾号默认可见（描边动画只叠加，减动效下仍可见）。手机：`scroll-snap` 四张卡（`data-tier` / `aria-current`）+ 每行四档标 `.on` 联动 + 深层折叠。Ultra 墨底条进视口扫光一次。`WelcomeView.vue` 插在 `08 /` 与下载段之间，编号 `09 / Membership`、下载改 `10 /`。

### R7 · 老站首页效果补齐（已完成 0.36）

对照表在 `docs/审美回炉清单.md`。已补：`--topH` 实测（`ResizeObserver` 观察 `.wl-top`）、分享（`navigator.share` → 剪贴板 → `execCommand`，成功 `Link copied` 1900ms）、滚动驱动 tour（`wl-tour` `62vh × 4` 容器 + sticky stage、`is-on`/`is-prev` 抬起变暗、`--tour-p` 1px 进度线、44px 圆点 `scrollTo`、rAF 节流），deck 手势代码已删除。不搬：中英切换、暗色、Mini/Max、APK、第三方友链（目标地址不可核验）。

### R8 · 账户内会员面板（已完成 0.37）

落地：`web/src/components/MembershipPanel.vue` 挂在 `#account`（VAULT 页）。档位豆数 + 档名；永久档写 `PERMANENT`，限时档写 `UNTIL <北京时间日期>`；设备 `x / 5` 来自 `GET /api/membership/sessions`（本机标 `THIS DEVICE`，其余可 `DELETE /api/membership/sessions/{id}` 登出）；`Redeem a code` 走 `POST /api/membership/redeem`，成功后 `refreshSessionOnce` 重读会话并即时解除锁定态，失败沿用注册页同一句提示。时间戳解析做了防御：SQLite 的 `YYYY-MM-DD HH:MM:SS` 先补 `T`/`Z`，无效值渲染为空而不是抛错（首版 `Invalid time value` 让整块组件静默不挂载，已修）。

**未验证边界**：成功升档的界面路径（fixture 所有者账号本身是 Ultra，兑换只会返回「already has that tier or higher」）；升档/续期/过期回落在 API 层由 `tests/test_membership.py` 覆盖，浏览器只证到了面板与回执这一段。0.38 审查时应补一个低档账号的端到端升档实测。

VAULT 账户区（`#account`）：当前档位（豆子 + 档名）、永久档、Pro 到期日（北京时间）、已登录设备 x/5（可逐个登出）。`Redeem a code` 输入框：成功即时刷新并解除锁定态，失败提示与注册页一致。`/register` 支持 `?code=` 预填（输入框在用户名之上）。首页右上不加档位徽章；应用内顶栏右侧可显示很小档位字样。

### P1 清理清单（0.35 已逐项复核）

| 项 | 复核结果 | 处置 |
|---|---|---|
| 处方重复 | 当天两行同名主项是计划的真实结构（`1×3` 工作行 + `1×6` TOP / `2×6` BACK-OFF 行），各带独立 LOG；真正重复的整块热身已在 0.33 由 `mainWarmups` 过滤掉 | 不动（不是重复渲染） |
| 显示版本号不显示哈希 | 落地页页脚、账户页、review 头都显示 `0.35` 这类版本号 | 已随版本消失 |
| 内部标识 `S.Main\|…` | `TrendView.vue` 的下拉曾把 `S.Main\|low-bar squat` 整串当选项文本 | 已修：选项只显示动作名（`movementLabel()` 去掉命名空间），完整 ID 仍留在详情行的「Exact movement ID」 |
| 自重 `KG TOP 0` | 实测渲染里没有 `TOP 0` / `0 KG`；自重动作走 `system-load` 文案 | 已随版本消失 |
| 吨数 139.5/139.6 | `engine.py` 的 `perWeek.tonnageKg` 曾先 `r1` 再被页面相加 | 已修：周值给原值，页面相加仍得 `139.6`（`verify.js` 与 `browser.mjs` 两侧都有断言） |
| `FEB13/FEB14` | 已无（0.30 改日历后消失） | 已随版本消失 |
| CTA 闪烁 | 落地页 CTA 为静态 `<a>`，无动画/无透明度过渡；实测 `opacity: 1`、`transform: none` | 复现不到，不动 |

### 档位与邀请码（0.27/0.28 已实现，留作口径）

五档 `free < lite < plus < pro < ultra`，高档包含低档；价格只展示不接支付。Free $0 永久；Lite US$19.9/¥68 一次性；Plus US$69.9/¥198 一次性；Pro US$19.9/mo · ¥98/mo 按月（每码默认 30 天）；Ultra 不标价、仅邀请、owner 播种固定 Ultra。注册必填邀请码（无效/用尽/吊销/过期一律 422，不泄露是否存在）；码只存 sha256，格式 `RR-{TIER}-XXXX-XXXX`（去掉 0/O/1/I）；`server/tools/invite.py` create/list/revoke，无网页后台。账户存 `base_tier`（永久，取历次最高）+ `timed_tier` / `timed_until`（Pro），实际档取两者高；**过期掉档不掉数据**，已有记录不删不藏，只锁新入口。设备上限 5，第 6 次登录淘汰最早会话，改密码全失效。

能力矩阵（前端从 `/api/session` 拿，不在 Vue 抄第二份）：Logging & daily prescription / Cycle, block & week views / Plan import & export / Basic stats / Share card 全部档位 ✓；Gear & Sheiko warm-ups / Test week & meet attempts 从 Lite ✓；Muscle-group map / Lift register & trends / Recovery & body metrics 从 Plus ✓；ORACLE AI brief（20 次/北京日）/ VAULT cloud ledger 从 Pro ✓；Devices 全档 5。

---

## 5 · 已确认决策（用户 2026-11-15 裁定，优先级高于任何默认值）

- **P0-01 判定**：不判「立即」时点空白；判 200ms、800ms、最终加载完成；禁词加 `NO SESSION`、`Return to the cycle`；新增最终态断言「3M 下 30 秒内必须出现计划内容，不得停在骨架」；不设单次骨架停留阈值；空白正文算失败。今晚若不通过：**起点不动，仍 11-23**，P0-01 记进 0.38 清单。
- **T1**：64 视图 / 30 分钟 TTL / `time.monotonic` / 进程重启清零 全部保持；**线上 worker 数写进部署配置备注**（`AGENTS.md` 环境节 + `server/tools/deploy.py` 注释），以后 worker 数变了不必回头改 64。
- **P0-02**：`day_total_kg` 与 `cycle_total_kg` 拆开；`cycle_total_kg` 必须等于 `meta.cycleTonnageKg`；`pct` 与 `meta.anchors` 同源，找不到就删字段；消费方三处（hero、分享卡、NEXT 药丸）共用一份 facts。
- **0.30 重算**：只在推迟分支做；只走脚本、不手改日期；planId 变更必须归档旧周期 + 播种新周期；断言强度不降。
- **未开始态**：只给采样提示，不给数值门槛；四块内容全从 plan 读；倒计时取 `plan.meta.startDate`；缺数据 `Not sampled`，不写 0。
- **夹具模式**：`/api/session` 返回 `authenticated: true` 同时带 `fixture: true`；部署环境**永不**设 `RR_ALLOW_OPEN_FIXTURE`。详单 §8.2 原「返回 False」的期望已由用户改掉。
- **本轮运行方式**：每个 0.01 本地提交 + 本地构建 + 本地截图；**不 push、不正式部署、暂停「停即部署预览」**；BOUNDARY 写「未部署」；发布由用户另行下令。
- **训练/恢复建议**：纯规则派生，免费开放，不接 AI（详单要求）。

---

## 6 · 关键数据 / 关键代码 / 审美基线

### 6.1 · 0.30 重算前后对照

| 项 | 现值（11-16 版） | 改后（11-23 版） | 备注 |
|---|---|---|---|
| `meta.startDate` | 2026-11-16 | **2026-11-23** | 唯一真相，其余日期由它派生 |
| `meta.endDate` | 2027-02-14 | **2027-02-21** | 13 周整 |
| 测试日 | 2027-02-13 | **2027-02-20** | 结束前一天 |
| 到测试 / 到结束 | 89 / 90 天 | **89 / 90 天** | 相对时长不变，motto 数值不动 |
| 周数 / 节数 | 13 / 49 | 13 / 49 | 不变 |
| `meta.cycleTonnageKg` | 139568.0 | **139568.0** | 日期不影响负荷，作零差基线 |
| `meta.planId` | `rpl-raw-2026-11-16` | `rpl-raw-2026-11-23`（若改） | 改则归档 + 重播种，不原地改日期 |

### 6.2 · 骨架代码（仅当 P0-01 实测仍闪才上）

```vue
<!-- 固定高度占位，不用 shimmer 动画（尊重减少动效偏好） -->
<main :aria-busy="loading">
  <div v-if="loading || !plan" class="day-skeleton" role="status" aria-live="polite">
    <span class="sk-line w-40"></span><span class="sk-line w-70"></span><span class="sk-line w-55"></span>
    <span class="sr-only">Reading the plan.</span>
  </div>
  <div v-else-if="!validRoute" class="empty-state">NOT IN THIS PLAN …</div>
</main>
```

```css
.day-skeleton { display: grid; gap: 10px; padding: 18px 16px; border: 1px solid var(--hair); border-radius: 14px; background: var(--panel); min-height: 168px; }
.sk-line { height: 14px; border-radius: 3px; background: var(--soft); }
```

- `todayCtaLabel` 在 `plan` 为空时输出 `·`，不渲染 `NO SESSION`。
- 探针（一次性，不入仓）：`page.emulateNetworkConditions({downloadThroughput: 375000, uploadThroughput: 375000, latency: 40})` → 10 次 `page.reload()`；每次取 200ms / 800ms 的 `document.body.innerText`，再 `waitForFunction` 等计划内容（上限 30s）。

### 6.3 · 审美基线（沿用 2026-11-14 裁定）

只复用旧 App / 旧站视觉语言与 `tokens.css` 变量，不新增装饰性巧思；骨架用 `--soft` 灰条、不做 shimmer；数字排版沿用 hero 现有 `clamp()` 字号与 `small` 单位；小标题沿用 `section-label` 大写 + 字距；未开始态四块沿用 `.prestart` / `.facts` 的边框、圆角与底纹；交互控件可视高度 ≥44px；三宽无横向溢出；减少动效模式不跑动画。Light = 旧 ex 暖纸，Dark = 旧 dark。

---

## 7 · 目录治理（2026-11-15 已执行，本节保留为改动记录与回滚依据）

**执行结果**：`RR` 现为 `ref-projects\`（roast-powerlifting 15 项 / rplref 9 项）、`shots\0.21…0.28`、`scratch\36 文件`、`notes\3 份`、`Archive\oneoff\3 补丁`、`skills\`、`builds\`；根级散落文件 36 个全部归位；仓库侧 9 个文件、RR 侧 13 个文件共 32 处指针改为新路径；`Ref\00_README.md` 与 `Ref\01_Current\SPEC.md` 按 7.3 的"不改"保留原样。

### 7.1 · 已完成的先行项

- `Agent.skill` 已移出仓库 → `RR\builds\Agent.skill`。
- Skill 库已外迁 → `RR\skills\roast-raw-agent\`（`SKILL.md` + `scripts\check_skill.py`）与 `RR\skills\INDEX.md`；仓库 `.qoder\` 已删；`check_skill.py` 改为按脚本自身位置定位。
- `rplref` 已瘦身（见 §0 表末行）。
- 两个老项目与 RR 目录结构已搬迁（见本节执行结果）；指针已全量改写并复查残留。

### 7.2 · 目标树

```
C:\Users\Astra\Desktop\RR\
├─ ref-projects\        roast-powerlifting\  rplref\（已瘦身至 2243.6 MB，见 _repo\MIRROR_SLIMMED.md）
├─ skills\              INDEX.md  roast-raw-agent\
├─ builds\              Agent.skill
├─ shots\               0.21…0.32  archive\
├─ scratch\             截图脚本（shot-029/030/031/031-free）、schema-dump.py、migrate-live-032.py、老项目探针
├─ notes\               3 份 RoastRaw-*.md
├─ Archive\             reviews\（2 zip） oneoff\（3 个已执行补丁脚本）
└─ .workbuddy\ .qoder-credits\   历史记录，不动
```

### 7.3 · 逐条改动（2026-11-15 普查并已执行）

**A 组 · 搬 `ref-projects`（19 处）**：`Roast Raw\AGENTS.md` 环境节、`docs\0.01地基_已验证发现.md`、`docs\0.01提示词.md`、`docs\项目交接.md` 三处老项目根 + 一处 `_snapshots`、`docs\审美调研.md`、`RR\skills\roast-raw-agent\SKILL.md` 两处、`RR\RoastRaw-Context-Pack.md` 两处、`RR\RoastRaw-审查策略与预算.md` 四处、`RR\_old_probe.py` / `_old_probe2.py` / `_old_structure.py` / `_old_text.py` 各第 2 行。
**A 组不改**：`Ref\00_README.md`、`Ref\01_Current\SPEC.md`（只读快照，内文停在迁移前是对的；在 `AGENTS.md` 记一句即可）。

**B 组 · 搬 `shots`（21 处脚本 + 仓库 18 处文本）**：`_shot028.mjs`、`_crop_log.mjs`、`_drag_test.mjs`、`_shot_analysis.mjs`、`_shot_cycle.mjs`、`_shot_cycle2.mjs`、`_shot_fix.mjs`、`_shot_l5.mjs`、`_shot_old.mjs`（2 处）、`_shot_round2/3/4/5/6.mjs`、`_shot_sections.mjs`、`_shot_sections2.mjs`、`_shot_sections3.mjs`、`_shot_zoom.mjs` 的绝对输出路径；`TODO.md` 三处新版本截图目录名与历史行中的 RR 截图根、两处 archive 目录（均已改写）；`docs\agent-prompt-*.md` 两处；`RR\RoastRaw-UI改版决策.md` 四处；`RR\skills\INDEX.md`。

**C 组 · 分类（无指针）**：探针脚本 → `scratch\`；3 份 `RoastRaw-*.md` → `notes\`；2 个 review zip → `Archive\reviews\`；3 个 `_apply28_*.py` → `Archive\oneoff\`。

### 7.4 · 执行顺序与校验（已按此顺序执行）

1. 关掉占用两个老目录的编辑器窗口；建 `ref-projects` 并 `Move-Item`（同盘改名，5 GB 预计 1–3 分钟）→ 改 A 组 19 处 → 每个新路径 `Test-Path`。
2. 建 `shots` 搬 8 个版本目录 → 改 B 组 → 对每个脚本默认输出目录做 `Test-Path`（不存在就建，不实际截图）。
3. 建 `scratch / notes / Archive` 分类落位 → 打印树核对条目数。
4. `git status` 只应显示文档改动；`check_skill.py --root .` PASS；`verify.js` exit 0；build exit 0。

### 7.5 · 三点默认值（用户未回话时按此执行，回话即改）

1. `Archive\` 收：reviews 两 zip + `_apply28_*` 三补丁 + 将来 `Archive\shots`（`docs/shots` 那 183 张）；`_old_*.py` 留 `scratch`。
2. `shots\` 版本目录名用 **`0.21`**（不用 `v0.21`），与 `TODO` 版本号一致。
3. 两个老项目深层（`RPLRef\_repo\mirror`、`Roast PowerLifting` 深层）**不再逐文件扫**；在治理提交里记一句「仅扫索引层，深层未逐文件扫，只读不执行」。

### 7.6 · 截图与测试布局（0.35 已完成）

`docs/shots` 183 张已迁 `RR\shots\archive`，**6 张 `old-ref-*.png` 留仓**在 `docs/ref-shots/`；`.gitignore` 已加 `docs/shots/`；`tests/browser.mjs` 的输出目录改可配置 `SHOTS_DIR`（默认 `..\RR\shots\<release>`）。只从 HEAD 移除，历史 blob 仍在；要真瘦需重写历史（单独授权，本轮不做）。`docs/` 内部分层 `spec/` `handoffs/` `licenses/` `ref-shots/` 仍待做（不影响 0.36–0.39）。

---

## 8 · 风险与红线

- **不许**放宽容差、删断言、中和 sabotage、手改 `data/plan.json` 或 `web/dist/`、改 git config、`--amend`、`--no-verify`。提交必须 `git -c user.name=Astra -c user.email=astra@local commit`。
- **不许**在未获授权时 push / 部署 / 覆盖共享服务；`server/tools/deploy.py` 覆盖式写 env 会删 `DEEPSEEK_API_KEY`。
- **不许**把密钥、cookie、数据库、env 文件打进回执、文档、bundle 或截图。
- P0-01 若 30s 内未出现计划内容：记缺陷、进 0.38 清单，**不阻塞开周**（起点仍 11-23）。
- `landing-facts.json` 与 plan 漂移由 verify 两条断言拦截，不允许「先改 JSON 再说」。
- 0.30 重算若波及线上已播种周期：先快照再迁移，归档旧周期；线上 owner 记录极少，风险可控。
- `browser.mjs` 自 0.35 起是绿灯基线；它证明界面机制，不证明审美，也不能替代 `verify.js`。
- **扫描类脚本禁止把输出写进被扫描目录**：2026-11-15 一次全盘普查把结果文件放在 `RR\` 内又递归扫到自己，逻辑体积滚到 62 GB（已删除，见 `RR` 现状）；此类脚本输出一律写系统临时目录，且必须带 `-Depth` 或显式排除自身。

---

## 9 · 未决问题（需要用户一句话）

**已闭环**：`planId` 已于 0.30 定为 `rpl-raw-2026-11-23`（旧周期已归档）；`pct` 缺失即删字段已按 `meta.anchors` 落地（0.29 verify 覆盖）；§7.5 三点默认值已执行并入 §7；`docs/shots` 183 张已于 0.35 迁出仓库（`RR\shots\archive\`，6 张老参考留 `docs/ref-shots\`）。

仍悬着、且影响后续版本的：

1. **线上怎么迁**：`http://82.157.146.30/` 还是 0.20 旧 schema（v1 期），本地库已到 v7。要上线必须整库替换或对线上库跑同一条迁移链，两种都要先停服务 + 备份。需用户推翻 2026-11-15 的「不 push、不部署」裁定才动手。
2. **`days[3].titleEn` 里的 `(W13 TEST)`**：属源模板文本，0.30 保留了它。若判定为文案回退，需把清理固化进 `gen_data.py` 而不是手改 `plan.json`。

（原第 3 条「0.33 四宽取哪四个」已由用户 2026-11-15 裁定：以实机荣耀 500 Pro 视口为准、宽度不写死，见 §4 `R4c`。）

---

## 10 · 交接卡（换 Agent / 换会话时先读这一节，再读 §1）

**路径**

- 源码仓库：`C:\Users\Astra\Desktop\Roast Raw`（分支 `master`）。
- 主项目目录：`C:\Users\Astra\Desktop\RR` —— 只放 Skill、scratch 探针、截图证据，**不放源码**。
- 老项目只读：`RR\ref-projects\roast-powerlifting`、`RR\ref-projects\rplref`；仓库内 `Ref\` 只读。

**命令（本机 PATH 无 git/node，必须写绝对路径）**

```powershell
$git = "C:\Users\Astra\AppData\Local\Programs\WorkBuddy\resources\vendor\PortableGit\cmd\git.exe"
& $git -c user.name=Astra -c user.email=astra@local commit -m "..."
```

```powershell
# 门禁（约 4–5 分钟；前台 15s 预算会被转后台，用 TaskOutput 取回）
$env:RR_ACCESS_PASSWORD=''; $env:RR_ALLOW_OPEN_FIXTURE='1'; $env:DEEPSEEK_API_KEY=''
node tests/verify.js            # 期望 exit 0；末尾应出现 "PASS verify.js" 与 "PASS governance"
npm --prefix web run build      # 期望 exit 0
server\.venv\Scripts\python.exe "C:\Users\Astra\Desktop\RR\skills\roast-raw-agent\scripts\check_skill.py" --root .
```

**只跑 Python 子集**

```powershell
server\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"   # 全量 317
server\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -k gates  # 单主题
```

**已知会骗人的地方**

- `tests/verify.js` 绿不代表界面能渲染；`tests/browser.mjs` 自 0.35 起是绿灯基线（登录前那一条 401 是门控探针，已按基线过滤）。
- `verify.js` 日志里出现 `FAIL: fixture weekly chest W1` 是 sabotage 子进程的**预期红**，不是失败。
- `tests/cdp.mjs` 曾经没 `Network.enable`，`requestLog` 恒空（0.31 已修）；引用「没有某请求」的网络证据前先确认该事件真的在采样。
- 探针必须过滤预期的 `403 (Forbidden)` console 行，否则 exit 1。
- `store.logs()` 只返回 `load/sets/reps/rpe/note/updated_at`，key 是 `"week|day|seq"` 字符串，没有 `date`。
- PowerShell 里 `python -c` 引号/反斜杠易炸：改写文件一律写临时 `.py` 再 `python 那个文件`。
- `rg` 全仓搜索会超时，必须限定 `tests/ server/ web/src/`。
- `with sqlite3.connect(...)` 在 Windows 上不关连接会导致临时目录 `PermissionError`，用 `contextlib.closing`。
- 截图一律 CDP 模拟宽高，不靠窗口尺寸；证据落 `RR\shots\<版本>\`，含一份 `*-evidence.json` 记录测到的数值。
