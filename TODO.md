# TODO — Roast Raw 执行队列

> 本文件只记录**未完成工作、已确认决策和执行契约**。完成历史一律查 `git log`，此处不复述。
> 版本唯一来源是 `web/package.json`（patch 位映射页面显示的第 `0.xx` 版）。发生冲突时的优先级：**用户最新裁定 > 本文件 > `docs/项目交接.md` > 旧散文**。
> 执行 Agent 的流程纪律在 `AGENTS.md` 与 `C:\Users\Astra\Desktop\RR\skills\roast-raw-agent\SKILL.md`；本文件只回答「做什么、做到什么算完」。

---

## 0 · 状态快照（2026-11-16 · 0.61）

| 项 | 值 |
|---|---|
| 版本 | `web/package.json` = **0.0.60**（页面显示 0.61）；本地提交；重建批次末版 |
| 工作树 | 以本节所在提交为准 |
| 最近提交 | `58d3ab2` 0.60 · `025f36c` 0.56 · `3704aa4` 0.55 · `8f21457` 0.51 · `6be8e4e` 0.50 · `252871e` 0.49 |
| 门禁 | 0.61：`verify.js` exit 0（6820 检查、356 用例）；`build` exit 0（125.16 kB css / 312.68 kB js）；`browser.mjs` 28 项 exit 0；`browser --sabotage` exit 1 |
| 红基线 | 无 |
| 发布 | 0.61 部署与 push 见 §1C 末行 |
| 证据落点 | `RR\shots\0.60\`（28 项浏览器检查、7 张视口截图）；0.50/0.51/0.55/0.56/0.59 各留有当版截图 |
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

## 1 · 下一动作：本批五版（0.41–0.45）已全部实现、发布并 push；等用户真人验收与重评分（规格见 §2A）

入口是 `C:\Users\Astra\Desktop\roast-raw-review-report-implementation-plan.pdf`（0.40 本地预览的只读审查，总评 6.3/10：美学 7、逻辑 5、UX 6、文案 7）。用户 2026-11-15 已定：切五版、统计按明细逐行展开、HTTPS 暂不做、末版含 P2 全部并部署 + push + 真人验收。按 §2A 从 0.41 起逐版执行，每版一步到底。

**0.40 收工口径**：已部署 `http://82.157.146.30/`（0.0.40）、已 push `origin/master`（`6c0c595..9597dc7`）。

**接手指令**：0.38 已由独立会话审查并收口（`ed2380c`）；0.39 日历 `9597dc7`；0.40 已部署与 push。历史口径：0.38 = 一个**未写过本轮代码**的会话审查 0.29–0.37，逐条实测 §4 `P1` 清单与 `docs/项目交接.md` §12 推断项，清单逐条关闭后交用户。0.39 发布（push + 部署）**只在用户另行下令后**执行。

---

## 1A · 0.46 单版：用户 2026-11-15 追加的五件事（已实现，本地提交 `c0a8c09`）

| # | 要求 | 交付 |
|---|---|---|
| 1 | 落地页展示图改回跟手左右滑动，其他卡片在后渐隐渐显 | `WelcomeView.vue` 丢掉滚动读取（`readTour`/`--tour-p`/62vh×4 高塔），换成 pointer 拖拽：`dragX` 跟手位移、松手按 `max(28px, 14% 宽)` 翻页、首尾阻尼 0.3、纵向手势交还页面滚动（`touch-action: pan-y`）；每张卡片按 `(i − index) × 100% + dragPct` 位移并缩放/降透明度/灰度。圆点只选帧不滚页面，`←/→` 可切。`verify.js` 与 `browser.mjs` 对应断言同步重写（`Input.dispatchMouseEvent` 真实按下→移动→松开，断言四张卡都带位移、松手后 Figure 2、1 前 3 后、rail 50%、页面未滚、无横向溢出）。 |
| 2 | 计划推迟到下周一 + 未开始状态 | 生产计划 `rpl-raw-2026-11-16` 经 `server/tools/roll_cycle.py`（快照→归档→播种）切到 `rpl-raw-2026-11-23`（`data/plan.json` 早已是这一份）。UI 侧新增 `/cycle` 的 `NOT STARTED` 带（`data-testid="cycle-prestart-band"`，只有 `calendar.status==='upcoming'` 才渲染）与 `STARTS IN {{n}} days` 指标；Today 侧原有 `CyclePrestart` 保留。`verify.js` 增 3 条静态断言。 |
| 3 | Vault 折叠面板太矮、字与边框没间距 | `ArchiveView.vue` 的 `summary` 从 44 px 高 / `12px 4px` 内边距改为 52 px 高 / `16px 12px` 内边距，加边框与底色，展开态换 `--panel2` 并去掉下方圆角；`[open]` 子元素左右 12 px、底部 14 px 留白；`.report-details` 22 px/6 px 收紧为 18 px。 |
| 4 | 从首页点进计划卡约 1 秒 | 三段：① `main.py` 挂 `GZipMiddleware(1024)`——`/api/plan` 线上 512 KB 压到约十分之一（此前实测 1959 ms）；② `/api/analysis` 加进程内缓存，键是「计划内容哈希 + log 哈希 + mode」（实测 1701 ms），计划或日志一变自动失效；③ `App.vue.refresh()` 原来 `/api/cycle` 先跑、再 `Promise.all` 五路、再顺序取 prescription/body-metrics，改成 8 路一次并发。 |
| 5 | 所有页面、功能、文案列到桌面 `审查.md`（英文） | `C:\Users\Astra\Desktop\审查.md`：路由表、15 个界面逐屏（目的/控件/状态/原文文案）、能力清单、逐组件文案（从 `.vue` 模板机械抽取）、API 表面、统计口径、档位门禁、遗留项。 |

**顺手修的既有工具问题**：`server/tools/deploy.py` 原用 `scp` 上传 payload，本机 sshd 关掉了 sftp 子系统导致 `Connection closed`；改成同一 ssh 通道 `cat >` 管道上传。本次发布遇到宿主 ssh 连接被拒（HTTP 仍 200），非代码问题，见 §0 发布记录。

---

## 1B · 0.47 单版：视觉与信息层级重构（用户 2026-11-16）

| # | 要求 | 交付 |
|---|---|---|
| 1 | 展示图回到“扑克扇形”，去掉下方四个圆点 | `WelcomeView.vue` 的 `frameStyle` 改成扇形：每张卡按 `(i − index + dragPct)` 做 `x = offset × 15 %`、`y = |offset| × 32 px`、`rotate = offset × 3.2°`、按距离缩放与降饱和，前排阴影最重；拖动、翻页阈值、`←/→`、`pan-y` 纵向交还页面全部保留。`wl-tour-dots` 与 `wl-tour-rail` 连同其 CSS 一并删除，`browser.mjs` 断言改为 `dots: 0`＋`turned: 4`＋`dropped: 3`＋`loaded: 4`。 |
| 2 | 手机周次条回到一行纯小方块（9–17 周自适应、不许两行） | `BlockWeekNav.vue` 的 `.bw-week` 去掉圆角卡、`W01` 文字与 `deload/test` 小字，改成 `display:grid; grid-template-columns: repeat(var(--count), minmax(0, 1fr)); aspect-ratio:1` 的正方块，卡里只放周号；颜色由块相位（`--seg`）给边框，当前周反色填充，deload 斜纹、test 双描边。`browser.mjs` 增“一行、方块、无标签”三条断言。 |
| 3 | 动作行恢复角色左侧细线（主项红 / 变式蓝 / 辅助绿） | 根因是 `ExerciseRows.vue` 的 scoped 样式把 `.exercise` 重置成“无边框、无背景、无圆角”的表格行，把 `style.css` 里的 `border-left: 3px solid var(--role)` 整条覆盖掉了。改为卡片：`border-left: 4px solid var(--role)`＋`linear-gradient(100deg, color-mix(--role 9%) → #FFFFFF 44%)`＋淡投影，`main` 用 `--main`、`sbdVar/nonSbdVar` 用 `--variation`、`accessory` 用 `--accessory`。 |
| 4 | Block→Week、Week→Day、Day→动作都套“细线＋渐隐”，卡片尽量上移 | `.week-card` 与 `.day-card` 改为 4 px 左细线＋同族渐隐，颜色取所在块相位；块页顺序改为 周次方块 → 编辑式摘要 → 指标 → 周卡 → `LoadProfile`；周页改为 周次方块 → 周摘要 → 日卡（原 `week-header`／`top-intensity` 合并进摘要）。 |
| 5 | 周次下方给 Cycle/Block/Week/Day 各一版编辑式摘要 | Cycle 页保留 NOT STARTED 带与三指标；Block 页加 `seg-line`（“W01–W04 · 4 weeks reaching 82.5 %1RM · 56.24 t across 16 sessions”）；Week 页加 `seg-brief`（衬线大标题“Mid-grip bench carries this week at 73 kg — 75 % of 1RM and 4 working sets on Nov 25.”＋吨位/课次/顶强度三项）；Day 卡加 `day-brief`（最重主项的 动作 + 重量 + 强度 + 组数）。所有数字来自 plan/analysis，不手写。 |
| 6 | 日视图不该借用周的 SBD 与肌群 | `server/app/stats/engine.py` 新增按天聚合的 `perSession`（`lifts` / `equivalent` / `groups` / `leaves`，与周共用同一个 cycle 峰值刻度算 `heat`）；`App.vue` 在日路由打开时把 `WeekCapacity` 切到该会话数据并把标题改 `SESSION CAPACITY`，`MuscleMap` 切到该会话 `leaves` 并标 `THIS SESSION`（今日页同样按当日会话）。`browser.mjs` 断言 `data-scope=session`、标题、`THIS SESSION` 与当日 17 组。 |

**门禁**：`verify.js` exit 0（6814 检查、356 用例，sabotage 照旧 exit 1）；`build` exit 0；`browser.mjs` 24 项 exit 0（新增扇形、周方块、日级容量/肌群三条）；截图 `RR\shots\0.47\`（15 张）。


**0.38 审查基线**：审查报告 `RR\review-0.38.md`（0 FAIL / 5 部分 / 10 PASS，缺陷 D-01～D-09、U-01/U-02）。本轮按报告关闭：D-01 兑换后重取 plan/analysis/geometry 且缺 geometry 时降级占位；D-02 动作 register 改用 R5 已到期口径（`asOf` + `min(actual, planned)`）；D-03 落地页 nav/footer/邀请链接全部 44px 命中区；D-04 `aria-expanded` + `aria-controls`；D-05 `BarbellStrip` 赛扣默认 0；D-06 分享卡 watch 赛扣；D-07 `SHOTS_DIR` 跟随 `package.json` 版本；D-09 UI 与画布片组对拍断言；D-08 文档漂移（§12 指向、31 链接/20 表、`user_version=7`、12 项能力）已改。U-01 按用户裁定：测试周注记拆到 `testTitleEn`，仅测试周显示。版本 0.0.38。

**0.37 已交付（R8）**：`web/src/components/MembershipPanel.vue` 挂在 VAULT 的 `#account` 段：档位豆数 + 档名、永久档 `PERMANENT` / 限时档 `UNTIL <北京时间日期>`、`SIGNED-IN DEVICES x / 5`（`GET /api/membership/sessions`，本机标 `THIS DEVICE`，其他设备可逐个 `DELETE` 登出）、`Redeem a code` 走 `POST /api/membership/redeem` 并 `refreshSessionOnce` 刷新会话能力表；`RegisterView` 支持 `/register?code=` 预填（读 `URLSearchParams`，转大写）。`verify.js` 新增 `membershipPanelCheck()`，`browser.mjs` 新增账户面板断言（档位/设备数/44px/兑换回执）。

**0.36 已交付（R6 + R7）**：`MembershipMatrix.vue` 从 `web/src/membership.json` 渲染四列（Ultra 不占列）+ 手机 `scroll-snap` 四卡；`WelcomeView.vue` 新增 sticky `.wl-top`、`wl-share`/`wl-toast`、滚动驱动 `wl-tour`（替换原 deck 手势）；`docs\审美回炉清单.md` 补老站对照表。

**0.35 留下的既成事实**（后续版本必须遵守）：

- 完成率只有一个实现：`server/app/stats/completion.py`。`engine.analyze(plan, logs, mode, today=)` 透传日期，计划/日志视图用「今天」（`server/app/calendar.py` 的 `SHANGHAI`），review 用周期结束日（整周期口径）。组件不再自己算百分比。
- `perWeek` 的 `tonnageKg` 现在给未四舍五入的原值，周期总数仍是 `r1` 后的一个数；页面上的 `139.6 t` 与周卡相加不再出现 `139.5`。
- 截图不进仓库：`tests/browser.mjs` 写 `SHOTS_DIR`（默认 `..\RR\shots\<release>`），`docs/shots/` 已进 `.gitignore`，6 张 `old-ref-*.png` 留在 `docs/ref-shots/`。


---

## 1C · 重建批次（0.50 → 0.60）：纯粹训练系统（用户 2026-11-16 裁定）

**0.49 实况更正（2026-11-16 复核）**：`252871e` 实际只改了 `BlockWeekNav.vue`、`WelcomeView.vue`、`style.css` 与 `App.vue` 版本号一行。旧表把「移除 ORACLE / 热身 / 配重柜 / 分享 / 等待条 / 日历入口」记为已交付，属空账：`App.vue` 仍渲染 ORACLE 导航与 `/questionnaire` 页、`WarmupSuggestions`、`GearPlates` + 赛扣开关、`ShareButton`、`CyclePrestart` 与 `cycle-prestart-band`、`/cycle` 里的日历跳转，`verify.js` 56 处、`browser.mjs` 36 处仍在钉这些功能。裁定中的重构**从 0.50 起做**，0.49 只保留「13 周方块单行」这一条属实交付。

**总纲**：回归最纯粹的训练视图。训练以外功能全量下线，三大分析支柱（`WeekCapacity` / `MuscleMap` / `LoadProfile`）提升为一等公民。

| 版本 | 主题 | 范围 | 验收 |
|---|---|---|---|
| **0.50** ✅ | 纯度 · 入口与导航 | 已交付：删主导航 ORACLE 与 `/questionnaire`（`/questionnaire`、`/oracle` 重定向到 `/analysis`）、`WarmupSuggestions`、`GearPlates` + 赛扣开关 + `gear-settings.js`、`ShareButton`/`ShareCard`/`share.js`、`CyclePrestart` 与 `countdown` 带、`/cycle` 日历跳转（入口移入 Vault）、`PrescriptionSettings`、落地页会员矩阵 | `verify.js` exit 0（6794 检查）；`browser.mjs` 23 项 exit 0；`--sabotage` exit 1 |
| **0.51** ✓ | 13 周丝带 + 单行层级 | `BlockWeekNav` 接入 Today（Today 从 `CycleStrip` 迁走）；Block 周卡改单列行（4px 顶部强度线四色、衬线周标题、SBD 比例芯片、吨位/组数/课次/峰值四格）；Week 日卡改单行折叠（`动作 · 重量 · 组次` + `OPEN SESSION →`）；Day 独立 `/cycle/week/:w/day/:d` 页：会话头 + `ExerciseRows` 置顶 + 晨脉抽屉 + 日级 `MuscleMap`/`WeekCapacity` + 返回周入口 | `verify.js` exit 0（6800 检查 / 356 用例，含新增 `pureViewCheck`）；`build` exit 0；`browser.mjs` 25 项 exit 0（`RR\shots\0.51\`）；`--sabotage` exit 1 |
| ~~0.52~~ ✅ | Block 单周一行（并入 0.51 交付） | `.week-deck` 改单列行；`.week-band` 4px 顶部强度线四色（`#2E6B65` ≤70% / `#1D4ED8` 71–76% / `#6D28D9` 77–82% / `#B91C1C` >82% 或 Test）；衬线周标题、SBD 比例芯片、等宽吨位/组数/课次/峰值 %1RM | `browser.mjs` 实测 B1 四卡四行、左缘同一列、色带 `rgb(29,78,216)/rgb(109,40,217)×2/rgb(46,107,101)` |
| ~~0.53~~ ✅ | Week 单日一行（并入 0.51 交付） | `.day-stack` 单列行；折叠态只留 `动作 · 重量 · 组次 TOP/BACK-OFF` 与右侧 `OPEN SESSION →`；删除卡内 `day-detail`/`ExerciseRows`/`DailyRecord` 展开 | 实测 W1 四行四顶：`High-bar Squat · 110.5 kg · 1×3 WORK` / `Mid-grip Bench · 73 kg · 1×6 TOP, 3×6 BACK-OFF` / `Conventional Deadlift · 133 kg · 1×4 TOP, 3×4 BACK-OFF` / `Accessory / conditioning` |
| ~~0.54~~ ✅ | Day 独立训练台（并入 0.51 交付） | `planView === 'day'` 独立模板：`.session-head`（动作/重量/%1RM/组次 + `17 SETS · 6 PRESCRIBED ROWS`）、`ExerciseRows` 置顶、`details.day-recovery` 收晨脉、日级 `MuscleMap [THIS SESSION]` + `WeekCapacity [SESSION CAPACITY]`、面包屑返回周 | 实测 `/cycle/week/1/day/A`：会话 17 组、6 行、`cap=session`、`kicker=SESSION CAPACITY`、`map=THIS SESSION`，无周级内容串入 |
| **0.55** | 三支柱一等公民 | SBD 容量 Main/变式/辅助分报 + MEV/MRV 标尺；16-leaf 肌群热图；`LoadProfile` 周吨位阶梯 + 峰值强度天花板；Block 详情与周期总览双映射 | 三视窗读数与 API 一致，日视图自动切 session |
| **0.56** ✅ | 门禁重写 | 纯度断言下到文件级（11 个组件/模块必须不存在、两条退役路由必须重定向、源码树禁 `STARTS IN`/`ORACLE`/`Gear setup` 等文案）；`AboutView` 删问卷与 ORACLE 段落；`browser.mjs` 改 day/ribbon/rows/纯度分组 | `verify.js` exit 0（6804 检查 / 356 用例）；`browser.mjs` 28 项 exit 0（`RR\shots\0.56\`） |
| ~~0.57~~ ✅ | 响应式复核（并入 0.56 交付） | 320 / 360 / 390 / 412 四宽度扫周页（`clientWidth` 实测、0 横向溢出、主控件 ≥44px）；320 日行改两行网格（`letter date open` / `line` 跨整行），修掉 `NOV 23` 被切 14px | 四宽度 `overflow=0`、内部 scroller 0；截图 `narrow-320` |
| **0.58** ✓ | 文档与交接 | `README.md` 去 share card；`AGENTS.md` 证据基线改写为纯度断言；`docs/项目交接.md` §0 顶部加 2026-11-16 裁定（下线清单 + 13.9/13.10/§17 转历史） | `check_skill.py --root .` exit 0（PASS Skill metadata, body, folder and project pointers） |
| **0.59** | 版本收口 | `package.json` 0.0.59 + lockfile；全量门禁；`RR\shots\0.59\` | `verify.js`/`build`/`browser.mjs` 全绿 + `--sabotage` exit 1 |
| **0.60** ✅ | 发布 | 备份 → `deploy.py` 部署 → push；部署后 `ACCESS-CONTRACT-OK`、公网探针 | `ACCESS-CONTRACT-OK`，公网 `/` 200、`health` version 0.59、匿名 API 401；push `21fe910..d4db5c3` |
| **0.61** ✅ | 装备提醒回归 · 状态监控下线 · 八变式归类 | 从 `252871e` 取回 `GearPlates.vue`（按处方主项重量给出每侧配片、微片柜与「不计算赛扣」说明），Today 与 Day 各挂一处 `EQUIPMENT / PLATES PER SIDE`；删除 `DailyRecord.vue` 及 Today/Day 的晨脉记录入口（状态监控下线），server readiness 端点保留但 UI 零引用；八变式归类：`meta.variationPolicy = eight-variations-v1`，`policy_of()` 统一 plan/analysis/completion/review，`label_plan()` 在 `GET /api/plan?labels=policy` 与 engine 分析内按策略重标 role/bucket/lift，OHP、俯身杠铃划船、引体、双杠计入 `sbdVar`，系数按用户裁定（S .90 / B .90 / D .85 / PC .15 / OHP .35 / PU .10 / Dip .60 / Row .25）；存储计划仍保留 legacy 字段证据，加载与吨位不变 | `verify.js` exit 0（6820 检查 / 356 用例，含新增 `variationPolicyCheck`：289 主项 / 289 变式 / 154 辅助组）；`build` exit 0（125.16 kB css / 312.68 kB js）；`browser.mjs` 28 项 exit 0（`RR\shots\0.60\`，`gear=true`、`warmup=false`）；`--sabotage` exit 1 |

**两条待裁定（0.50 用默认值执行，落地后标 ASK）**：
- 「设置」默认只下线 Gear setup（赛扣开关），保留 `PrescriptionSettings`——它是修正参考 1RM 与处方版本回滚的唯一界面，删掉等于让处方冻结在导入那一刻。
- 「首页推销」默认不动落地页会员矩阵与训练页档位门禁（门禁是能力契约，不是推销）；若指落地页推销面，需另行下令。

---

## 2 · 版本队列（0.29 → 0.40，顺序已定，不并行）

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
| ~~0.38~~ ✅ | 审查收口 | `RR/review-0.38.md` 的 D-01～D-09、U-01/U-02 逐条关闭；版本 0.0.38 | 已交付 `ed2380c`；339 用例 / 6661 检查 exit 0、`--sabotage` exit 1、browser 16 项 exit 0 |
| ~~0.39~~ ✅ | R9 健身日历 | 独立 `/calendar`、周/月/议程、只读、全部历史 + 未来空档、区间内 REST / 区间外留白、`/cycle` 内链入口 | 已交付 `9597dc7`；日历 6 用例、browser 16 项 exit 0（证据 `RR\shots\0.39`） |
| ~~0.40~~ ✅ | 发布 | 备份 → Store v6→v7 → `deploy.py` 部署 → push `origin/master` | 备份 `roast-raw-20261115-223521.tar.gz` 13M；线上 `user_version=7` / 20 表；ACCESS-CONTRACT-OK；AI `configured: true`；公网 200；push `6c0c595..9597dc7` |

---

## 2A · 审查修复批次（0.41 → 0.45，依据 `roast-raw-review-report-implementation-plan.pdf`）

**批次运行规则（用户 2026-11-15 裁定，覆盖 §5 里的旧运行方式）**

- **一步到底**：每版一次做完本版全部项，收尾一次门禁（`verify.js` + `npm --prefix web run build` + `browser.mjs` + 三宽截图）、一次本地提交，然后直接进下一版。中途不停、不做预览部署、不为默认值已有答案的问题请示（`AGENTS.md`「Plan then act」）。
- **只有 0.45 部署 + push**，并在部署后交用户真人验收；0.41–0.44 的 `BOUNDARY` 一律写「未部署」，提交必须存在。
- **停的条件只有两个**：某项出现没有安全默认值的口径/范围问题，或操作不可逆且未被授权。
- **版本号**：`web/package.json` 逐版 patch +1（0.0.41 → 0.0.45），`App.vue` `releaseVersion` 同步；版本唯一来源仍是 `package.json`。
- **口径裁定（用户 2026-11-15）**：训练数字一律**按计划明细逐行展开**为准，main / variation / accessory 三类分报。报告里的 730 vs 732 只在「展开后是多少」这一个意义上被采信，报告值本身不是目标值。
- **HTTPS（报告 P0-2）不进本批**：用户裁定「暂时不需要」。因此报告 P0 三项实际落两项；0.45 重评分时该项不计分、不得声称已解决，降级记录写进 §9。
- **不许**：放宽容差、删断言、中和 sabotage、手改 `data/plan.json` 或 `web/dist`、为对齐报告数字反改处方结构。

| 版本 | 主题 | 报告项 | 关键判据（一句话） |
|---|---|---|---|
| ~~0.41~~ ✅ | 训练数字单源 | P0-1 | 六处显示同值，且都等于明细逐行展开值 |
| ~~0.42~~ ✅ | 确定性 Cycle 页 + 块测试日 | P0-3 | 10 次重载结构相同；B1 不出现别的块的测试日 |
| ~~0.43~~ ✅ | P1 逻辑 | P1-4/5/6/7 | 日历逐行对拍、试举取整单测、全站无死链、强制失败有错误态 |
| ~~0.44~~ ✅ | P1 审美 | P1-8/9 | 421/320/1280 三宽无截断缺字、次要标签 WCAG AA |
| ~~0.45~~ ✅ | P2 文案与账户 + 发布 | P2-10/11/12 | 文案清单零残留、试举行可区分、能退出登录；部署成功 + 重评分达标 |

### 0.41 · P0-1 训练数字单源

**目标**：报告证据表那七行冲突（总组数、吨数、W1 Session A 组数、W1 图、W13 顶值、深蹲组数、Session A 首行）在页面上不可能再出现第二种答案 —— 一个计算，处处渲染。

**落点**

1. `server/app/stats/totals.py`（新）：唯一计数函数。输入 `plan` + `mode`，输出 `cycle{totalSets, mainSets, variationSets, accessorySets, tonnageKg}`、`perWeek[]`（`n / total / main / variation / accessory / tonnageKg / topPct / topLift`）、`perSession[]`（`week / day / total / rows[]`）、`perLift[]`。计数规则写进模块 docstring：**一行×行内 `sets` = 组**；`main` / `sbdVar + nonSbdVar` / `accessory` 三类分报，`total` 为三类之和；组数不做任何「去重」「估计」；吨数 = Σ(`loadKg × reps × sets`)，周期值求和后 `r1`，周值给未舍入原值（沿用 0.35 契约）；`%1RM` 只读 `meta.anchors`，取不到就不给该字段。
2. `engine.analyze()` 改为调用它，`stats/completion.py`、`prescription.py` 的组数不再各自累加。
3. `server/tools/landing_facts.py` 改读同一函数，`web/src/landing-facts.json` 重新生成（只重生成一次，之后随源变）。
4. 前端去掉第二本账：`App.vue` 的 `todaySetCount`、`todayTotals`、`todayRows.reduce(tonnageKg)`、`analysis.cycle.auxSets`、`analysis.perWeek[].total`、`blockTonnage` 全部改为读 API 字段；`Header "N SETS · M ROWS"` 的 N 由函数给，不再来自周合计或手写；`AnalysisView.vue`、`LoadProfile.vue`、`CycleStrip.vue`、`ShareCard.vue` 的同一周/周期读同一字段。
5. `verify.js` 新增 `totalsReconcileCheck()`：对 W1/W5/W13 与 Session A/D 六个面（Cycle header、ASSAY 三 tab、`/api/calendar` 会话 `prescribedSets`、`landing-facts.json`、周卡、分享卡）同值比对；期望值从 `server/tools/gen_data.py` 的源表**独立手算**，不从 `engine` 取。
6. `tests/test_totals.py`：三类分报、显式 0 组、空周、变式与辅项计入 total、吨数一位小数与周值原值、`meta.anchors` 缺失时字段消失。

**完成判据**：报告证据表七行逐条复核，每行只剩一个数；`verify.js` exit 0 且新增检查通过；`/cycle`、`/analysis` 三 tab、`/calendar`、落地页 hero 在同一周期上显示同一组数。

**0.41 已交付**：`server/app/stats/totals.py` 是唯一计数实现（一行×行内 `sets`，三类分报；吨数取每行 `tonnageKg`，因为 27 行带 `segments`，`load×reps×sets` 算不出该值）；`engine`、`calendar`、`landing_facts` 全部改读它；前端三处本地求和与落地页手写 13 周序列已删。实测 732 组 / 139.568 t（139.6 t），W1 71 组 / 16.93 t，W1 Day A 17 组 6 行，B1 56.24 t，四块 56.24+52.16+29.12+2.05=139.57→139.6 t。证据 `RR\shots\0.41\totals-evidence.json`。

**证据**：`RR\shots\0.41\`（三宽）、`plan-totals-evidence.json`（七行对照：面 / 值 / 来源函数字段）。

### 0.42 · P0-3 确定性 Cycle 页 + 块测试日

**目标**：`/cycle` 两次刷新长得一样；每个块只显示自己的测试日。

**落点**

1. 确定性：`App.vue` 的 Current Week 卡与 `Review Active Cycle` / `How Do I Read This?` 按钮改为**数据到齐后再定稿**（`await` 后渲染，或先骨架后替换）；禁止「先渲染再 `v-if` 移除」。查明 0.40 里随 `analysis` 到达次序翻转的分支并收成一个。
2. 重载证据：10 次 `reload`（含 `emulateNetworkConditions` 3M + 40ms latency），逐次对 `#main` 结构做快照哈希，全部相同；任一不同即失败，不写「偶发」。
3. 块测试日：`App.vue:398` 与 `:415` 现在把 `plan.testPlan?.dates?.sbd` 传给**每个** `LoadProfile`，所以 B1（11–12 月）显示 2027 年 2 月。改为块域映射：由 `plan.weeks[]` 中 `kind === 'test'` 的周定位所属 block，只有该 block 传日期，其余块传 `null` 并渲染 `No test in this block`；`/cycle` 页头的 TEST DAY 仍显示全局 SBD 日。
4. `tests/test_blocks.py`：每块最多一个测试周；有测试周的块其测试日落在块日期区间内；无测试周的块解析为 `null`。
5. `browser.mjs`：`/cycle/block/B1` 断言不出现测试日字符串；`/cycle` 断言 Group 参数与重载后一致。

**完成判据**：10 次重载结构哈希相同；B1 页无 2027-02 的日期；`/cycle` 首屏即含 Current Week 卡，无需二次刷新。

**0.42 已交付**：根因是 `App.vue` 把全局 `plan.testPlan.dates.sbd` 传给**每个** `LoadProfile`；改为 `blockTestDate`（只有拥有 `kind==='test'` 周的块才给日期，并校验日期落在该周区间内），非测试块渲染 `No test in this block`。重载确定性用 10 次 3M/150ms 节流重载的结构快照断言。**报告里的「Current Week 卡 / Review Active Cycle / How Do I Read This?」在 0.41 源码中不存在**（全仓只搜到 ArchiveView 的 Review active cycle 链接），那一段复现不到；因此改用结构快照把「有元素在首屏出现、重载后消失」这个失败模式钉死。证据 `RR\shots\0.42\determinism-evidence.json`。

**证据**：`RR\shots\0.42\`、`reload-determinism.json`（10 条哈希 + 每次 `window.innerWidth`）。

### 0.43 · P1 逻辑四项

| 项 | 落点 | 完成判据 |
|---|---|---|
| P1-4 日历详情映射 | `server/app/calendar.py` 会话 `rows` 与 `App.vue` 日视图共用同一 `week/day` 标识与处方行；`CalendarView.vue` 不再自建「选中日」副本，详情跳 `/cycle/week/:week/day/:day` | Session A 详情与 `/cycle/week/1/day/A` 逐行一致：标签、`3×6 @ 110.5 kg` 首深蹲行、组数 |
| P1-5 第三次试举取整 | 卧推 102.5% → 100% 地板到 97.5 kg，与第二次并列。规则：地板后若 ≤ 前一次，则**进位到下一 2.5 kg 档**；若仍并列（如封顶重量），页面显式标 `TIE` 并说明。实现落在 `server/app/stats/attempts.py` | `tests/test_attempts.py` 覆盖 95 / 100 / 102.5% 三边界 × 深蹲/卧推/硬拉九组，第三次严格 > 第二次或标 TIE |
| P1-6 死拒（dead affordance） | Oracle 调用历史条目：有详情就打开详情抽屉，没有就渲染为不可点击文本（无 `cursor:pointer`、无 `role=button`、无 toast）；随后全站逐元素点击审计 | 每个可点元素点击后都有可观察结果；`browser.mjs` 新增 `clickThroughCheck()` 白名单式列出被审计元素 |
| P1-7 加载与错误态 | Oracle、Calendar、Vault、Week 13、测试日建议：加载给骨架/进度文案，失败给可见错误 + `Retry`（禁止裸 spinner 或静默空） | 强制慢网与强制 500 各截一张，`docs`/证据 JSON 记两端状态；失败后可重试成功 |

**完成判据**：上表四项各自可复测；`verify.js` exit 0；`browser.mjs` 新增断言不计入「只数行数」的凑数检查。

**0.43 已交付**：试举阶梯加 `ceil25`——地板后若 ≤ 前一次则进到下一 2.5 kg 档，卧推 97.5 kg 参考值从 `[90, 97.5, 97.5]` 变为 `[90, 97.5, 100]`（`test_attempts.py` 覆盖 13 个参考值 × 三档，并对旧 fixture 期望注明政策变更理由）。日历详情标题由 `B · S`（只有动作字母）改成 `SESSION D · B · D · S lifts`；`browser.mjs` 抓日详情→点进 `/cycle/week/:week/:day`，逐行按序比对（实测 W13 D 详情 9 行 / 页 12 行，页会把带 `segments` 的行拆开，故比对是「有序包含」而非数量相等）。Oracle 调用历史原来点了无反应（`showCall` 失败只把错误丢进全局 `failure`，成功但无文本时模板什么都不渲染），现在每次点击必有回应：加载中、错误原因 +「只有耗时与用量，正文未存」、或正文本身。日历用 `Network.setBlockedURLs` 强制断供，实测出 `The calendar could not be loaded… Retry`（44 px），放开后重载恢复。Calendar / Vault / Week 13 原本已有错误 + 重试路径，本版只补证据不重写。证据 `RR\shots\0.43\logic-evidence.json`。

### 0.44 · P1 审美两项

| 项 | 落点 | 完成判据 |
|---|---|---|
| P1-8 截断策略 | 一条规则：caption / GPP 卡 / Vault 文本不得词中或句中截断。做法按内容取：换行、展开、`read more`、或**在源文本里缩短**（`gen_data.py` / 组件文案），不使用 `text-overflow` 硬切 | 421 / 320 / 1280 三宽逐面截图，逐个 caption 卡检查无缺字、无「…」半句；`truncation-sweep.json` 记每处元素的 `scrollWidth/clientWidth` |
| P1-9 对比度与密度 | 次要灰标签提亮到 cream 背景上 WCAG AA（正文 4.5:1，非正文 3:1），实测比值写进证据；`MuscleMap` 图放大；`ExerciseRows` 密集表加斑马纹/分组留白，不改编辑风格（不改 tokens 主色、不加装饰） | 对比度实测表逐元素给比值；桌面与 421 下密集表可读、无横向溢出 |

**完成判据**：三宽无截断；对比度比值全部达标；审美基线（§6.3）不变。审美接受仍归用户，本版只交机械证据。

**0.44 已交付**：删掉内容文本上的 `text-overflow: ellipsis`（块卡标题、动作条名称、预启动事实格），改成换行；`ExerciseRows` 每两行加 `--panel2` 斑马纹并把行距加到 12/10 px；肌肉图 `min(52vh, 400px)`、紧凑态 300 px（实测 300×173、双视图）。`browser.mjs` 新增逐元素扫描：三页 288 + 837 个元素，`scrollWidth > clientWidth` 且 `overflow: hidden/clip` 的 0 处；≤12 px 次要标签按有效背景算对比度，低于 4.4 的 0 处。**过程中修掉的是测量脚本自身的 bug**：把 `rgb(r, g, b)` 第三通道当 alpha 读，导致所有实色背景被跳过、误报「白字白底」；改成只有 `rgba()` 才读 alpha 后归零。证据 `RR\shots\0.44\aesthetic-evidence.json`。

### 0.45 · P2 三项 + 发布 + 重评分

**P2-10 文案统一**：B3/B4 `1 WEEKS` → `1 WEEK`；B1 补 `W01` 标；`SBD / MEV / MRV / RPE / GPP / t / ses` 首次使用处给定义（Assay 页脚术语表 + 就地首次提示）；舍入统一（一位小数或整数，全站一致）；复数统一（`1,650 tokens`）。

**P2-11 重复行标注 + 容量标尺**：Session 表里同动作两行必须可区分 —— 行首加 `TOP` / `BACK-OFF` 标（来源是处方行 `mode`，不手写）；`WeekCapacity.vue` 的容量条给带刻度标尺，MEV/MRV 标记写明含义。

**P2-12 账户与状态标签**：顶栏加 `Sign out`（+ 最小档案菜单：档位、设备数，复用 `MembershipPanel` 字段，不新建页面）；`0% done · elapsed`、`NEXT NOV 16`、`start date` 改成说人话（如 `Cycle starts 23 Nov 2026 · 89 days to test`）；Vault 设备会话给白话说明与 `Revoke`；Oracle 问卷加时间预估与「可保存稍后继续」；`Generate` / `Use` 按钮在前提不满足时禁用并就地说明原因。

**发布（用户 2026-11-15 授权，仅此一次）**

1. 全量门禁：`verify.js` exit 0、`npm --prefix web run build` exit 0、`browser.mjs` exit 0、`--sabotage` exit 1、`check_skill.py` PASS。
2. 三宽 × 双主题截图 → `RR\shots\0.45\` + `*-evidence.json`。
3. 线上备份（时间戳 tar.gz）→ 若 schema 变化走 `Store.upgrade_*` 并验 `user_version` / 表数 / `foreign_key_check`。
4. `deploy.py` 注入 `RR_ACCESS_USERNAME` / `RR_ACCESS_PASSWORD` / `DEEPSEEK_API_KEY`（三者缺一即中止，禁止删 key 部署）→ `/api/ai/status?cycle_id=…` 必须 `configured: true` → 公网 200 → ACCESS-CONTRACT-OK。
5. push 走 SSH + 临时 deploy key，推完**当次删除** key。
6. 交用户真人验收：按报告 §Verification 的八项清单 + 重评分（目标 Logic 8 / Aesthetics 8 / UX 8 / Text 9），HTTPS 项标注「未做，用户裁定暂不需要」。

**完成判据**：报告 12 项里 11 项有可复测证据（P0-2 明确未做），线上版本号 = `web/package.json`，重评分表落 `RR\shots\0.45\`。

**0.45 已交付并发布（2026-11-15）**：`1 WEEKS` 改为按数量取单复数；同动作重复行在行首加 `TOP` / `BACK-OFF` 标（取自首个 segment，不手写）；`WeekCapacity` 加 0 / 中值 / 满量程刻度轴，并用白话写清 MEV 是最低有效量、MRV 是可恢复上限；新增 `Glossary.vue`（SBD / MEV / MRV / RPE / GPP / t / ses / TOP-BACK-OFF 八条）挂在 Analysis 页；顶栏加 `Sign out`（≤480 px 隐藏，账户面板的 `Sign out on this device` 全宽度保留——320 px 下顶栏会被挤到 333 px，这是本版取舍）。**发布实测**：`health` 报 `version 0.45`；`ACCESS-CONTRACT-OK`（落地页公开、门禁开、匿名 401、owner 登录 200、cookie HttpOnly + SameSite=Lax、登出掉 cookie）；`/api/ai/status` `configured: true`、今日配额 `0/20`；`deploy.py` 先写 `/opt/roast-raw-backups/roast-raw-<stamp>.tar.gz` 再解包；`git push` `7115181..0673ae1`。证据 `RR\shots\0.45\release-evidence.json`。

**本版未做（如实记）**：Vault 设备 `Revoke` 控件、Oracle 问卷时间预估与更多 Generate 门控、状态标签白话化只做了部分。这三项不影响 P0/P1 的判定，仍挂在 P2-12 名下。

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

### R9 · 健身日历（0.39）

独立 `/calendar`：`server/app/calendar.py::calendar_days()` 按半开区间 `from <= date < to` 跨 active + 归档周期投影会话，`GET /api/calendar?from=&to=`（FastAPI 必须 `Query(alias='from'/'to')`，普通参数名会 422）。每会话返回 `cycleId/week/day/title/block/kind/prescribedSets/loggedSets/rowCount/lifts/topLoadKg/status/rows`；状态四态：有正记录 `completed`、全显式 0 `skipped`、过期无记录 `missed`、未到 `planned`。视图周/月/议程；只读，详情给出处，不写任何记录。空档语义（用户 2026-11-15 裁定）：周期跨度**以内**无课日标 REST，跨度**以外**留白；服务端回 `cycles` 跨度，前端 `inSpan()` 判定。入口只放 `/cycle` 页内链（主栏仍四项，不动 320px 四链接断言）。版本 0.0.39。

---

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
- **审查修复批次（2026-11-15 裁定）**：报告 `roast-raw-review-report-implementation-plan.pdf` 按五版执行（0.41 P0-1 / 0.42 P0-3 / 0.43 P1 逻辑 / 0.44 P1 审美 / 0.45 P2 全部）；**每版一步执行到位，中途不停、不预览部署、不为有安全默认值的问题请示**；**只有 0.45 部署 + push 并交用户真人验收**。旧的「每版本地提交 + 不 push 不部署」在 0.41–0.44 继续有效，0.45 的发布是用户明确下令。
- **统计口径（2026-11-15 裁定）**：训练数字以**计划明细逐行展开**为准（一行 × 行内 `sets`），main / variation / accessory 三类分报；报告里的 730 / 732 只作冲突证据，不作目标值。
- **HTTPS（2026-11-15 裁定）**：**暂时不做**。裸 IP `82.157.146.30` 无法取得公网受信证书；报告 P0-2 移出本批，0.45 重评分时该项不计分，不得声称已解决。

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

0. **HTTPS 与「not secure」提示（2026-11-15 用户裁定暂不做，0.42 起的批次内不做）**：整站与登录表单仍走明文 HTTP，浏览器会继续显示不安全提示，登录口令在公网明文传输。要做只能三选一：绑域名 + Let's Encrypt、域名反代（Cloudflare Tunnel 等）、或无域名自签 + 强制跳转（警告无法消除）。本批不碰，也不写「已修复」。

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
