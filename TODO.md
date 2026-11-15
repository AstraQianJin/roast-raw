# TODO — Roast Raw 执行队列

> 本文件只记录**未完成工作、已确认决策和执行契约**。完成历史一律查 `git log`，此处不复述。
> 版本唯一来源是 `web/package.json`（patch 位映射页面显示的第 `0.xx` 版）。发生冲突时的优先级：**用户最新裁定 > 本文件 > `docs/项目交接.md` > 旧散文**。
> 执行 Agent 的流程纪律在 `AGENTS.md` 与 `C:\Users\Astra\Desktop\RR\skills\roast-raw-agent\SKILL.md`；本文件只回答「做什么、做到什么算完」。

---

## 0 · 状态快照（2026-11-15 收工）

| 项 | 值 |
|---|---|
| 版本 | `web/package.json` = **0.0.28**；0.29 已落地 3/4，尚未发版 |
| 工作树 | 干净（`git status --short` 无输出） |
| 最近提交 | `41c6a00` 技能库外迁 |
| 门禁 | 0.29 partial 时 `node tests/verify.js` 302 用例 / 6290 断言、exit 0（sabotage 子进程仍按预期红）；`npm --prefix web run build` exit 0 |
| 红基线 | `tests/browser.mjs` 自 0.21 起失效（删主题切换、注册页改四输入，旧断言过时）；**0.35 重写后才可作绿灯证据** |
| 部署 | 线上仍是 0.20 版 `http://82.157.146.30/`（公开落地页 + 账户门控 journal）。本轮**不 push、不部署**（用户 2026-11-15 裁定） |
| 证据落点 | `C:\Users\Astra\Desktop\RR\shots-0.2x\`；目录治理执行后改为 `RR\shots\0.2x\` |
| 老项目 | `RPLRef` 2026-11-15 已瘦身 2243.6 MB（删除 mirror\archive、mirror\ref 重复副本与派生缓存），依据与恢复路径见 `RPLRef\_repo\MIRROR_SLIMMED.md` |

**长期边界**：只做 Web（Vue 3 + Vite + Motion One + FastAPI + SQLite）；界面英文、对话中文；`Ref/` 与两个老项目只读；不手改 `data/plan.json` 与 `web/dist/`；不弱化断言、不中和 sabotage。

---

## 1 · 下一动作：0.29 收尾（做完即本地提交）

按序执行，一步一提交。提交前跑门禁，回执按 `AGENTS.md` 五字段。

1. **P0-01 刷新实测**（判据见 §3.1）。结论只有两种：通过 → 记证据；不通过 → 记缺陷进 0.38 审查清单，**起点仍为 2026-11-23，不因它推迟**。
2. **P0-02 首页数字同源**（契约见 §3.2）：新增 `server/tools/landing_facts.py` → 产物 `web/src/landing-facts.json` → hero、分享卡、NEXT 药丸三处绑定 → verify 新增复算断言。
3. **P0-03a 收尾**：全仓 grep `No account|Zero account|CSV|XLSX|Chinese UI|rest timer|Phone app`，命中即改。
4. **门禁**：`node tests/verify.js` exit 0、`npm --prefix web run build` exit 0；`check_skill.py --root .` PASS。

---

## 2 · 版本队列（0.29 → 0.39，顺序已定，不并行）

| 版本 | 主题 | 关键范围 | 验收判据 |
|---|---|---|---|
| **0.29** | 安全与首屏 | T2 空口令 fail-closed、T1 `_scoped` 有界 LRU、P0-01 刷新不闪、P0-02 首页同源、P0-03a 假宣传 | §1 四条；`verify.js` exit 0 |
| **0.30** | 计划未开始态 | 周期推迟到 2026-11-23（全站日期单源重算）、`CyclePrestart` 四区块 | 重算零差（`cycleTonnageKg` 不变）、三宽截图、无 `/api/ai/*` 请求 |
| **0.31** | 门控与出口 | T6 读开写关、T5 降档主动刷新、T3 孤表审计 + 表级隔离单测、P0-03b 导出、P0-04 `/about` | 门控端点逐行成对；一小时 `/api/session` ≤5 次；12 张表孤儿 0 |
| **0.32** | T4 迁移 | `cycles` 主键改 `(account_id, id)`；12 张表外键重建；`user_version` 升位 | 旧库升级零差；同 `planId` 两账户并存互不可见；同账户重复仍 409 |
| **0.33** | R4 视觉欠账 | GEAR 小片与单侧配片、Sheiko 热身（只给主项）、比赛三盏裁判灯、测试周四组 UI | 四宽截图 + 每个交互一次实点 |
| **0.34** | R4b 测试周真存 | 新表 `test_results`：八项变式 + 5km 入库；ASSAY 可对比、导出/分享卡带出 | 八项 + 5km 写入读回一致；降档后仍可读可导出；迁移零差 |
| **0.35** | R5 + P1 | 完成率单函数；重写 `tests/browser.mjs`；P1 清单清理 | `verify.js` 与 `browser.mjs` 都 exit 0；每个改写断言做一次故意破坏 |
| **0.36** | R6 + R7 | 首页会员对比矩阵；老站首页效果补齐 | 320/360/390/412/1280 无横向溢出；折叠/币种/动效各一张 |
| **0.37** | R8 | 账户内会员面板（档位、Pro 到期、设备 5、兑换码） | 兑换升档、续期、过期回落都在界面走通 |
| **0.38** | 独立审查 | 未写代码的会话审 0.29–0.37，含详单 §12 推断项逐条实测 | 审查清单逐条关闭；0.29 遗留的 P0-01 缺陷在此复核 |
| **0.39** | 发布 | 部署 + push（**只在用户另行下令后**） | `deploy.py` 访问契约全 PASS + 公网探测 + `/api/ai/status` `configured: true` |

---

## 3 · 施工详单

### 3.1 · 0.29 ① P0-01 刷新不闪 404（未做）

- **现状**（`web/src/App.vue` 模板次序）：`loading` → 请求错误 → 空账本 → `!plan`（`Reading the plan.`）→ `!validRoute`（`NOT IN THIS PLAN`）。0.28 已把 `!plan` 提到 `!validRoute` 之前，**但从未实测**，因此不得宣称已修。
- **改法**（仅当实测仍闪）：骨架块推进到 `!plan` 之前，固定高度占位，禁用 shimmer；`todayCtaLabel` 在 `plan` 为空时渲染 `·`，不再输出 `NO SESSION`。
- **判据（用户 2026-11-15 定稿，不许软化）**：
  - 3M 带宽（≈375 000 B/s、latency 40ms），连续刷新 10 次；
  - 取样时点：**不判「立即」**（SPA 首屏 JS 未到之前空正文属正常），判 **200ms、800ms** 与**最终加载完成**；
  - 禁词：`NOT IN THIS PLAN`、`404`、`NO SESSION`、`Return to the cycle`；
  - **最终态断言**：30 秒内必须出现计划内容，不得停在骨架；
  - 不设单次骨架停留阈值；**空白正文仍判失败**。
- **证据**：`RR\shots-0.29\p0-01-refresh.json`（10 次 × 3 时点的原文与命中标记）。

### 3.2 · 0.29 ② P0-02 首页数字同源（未做）

- **生成器** `server/tools/landing_facts.py`：读 `data/plan.json`，取一个样例课日，写紧凑 JSON 到 `web/src/landing-facts.json`（不许把整份 plan 塞进 bundle）。
- **字段契约**：
  ```json
  {
    "planId": "rpl-raw-2026-11-23",
    "startDate": "2026-11-23",
    "week": 1, "day": "A", "date": "2026-11-23", "label": "W01 · DAY A",
    "lifts": [{ "lift": "S", "movement": "High-bar Squat", "top_kg": 110.5, "pct": 72.5, "sets": 5, "reps": 5 }],
    "set_count": 17,
    "day_total_kg": 4041,
    "cycle_total_kg": 139568.0,
    "tonnage_basis": "prescribed loads rounded to 0.5 kg (main) / 2.5 kg (variation)"
  }
  ```
- **口径（用户补丁）**：
  - `day_total_kg` = 该日总和，**不含热身**；
  - `cycle_total_kg` = 整周期，**必须等于 `meta.cycleTonnageKg`**（一个字段不能既当日又当周期）；
  - `pct` = 顶重 / 该动作训练最大值 × 100，训练最大值取 `meta.anchors` 同源值；**找不到同源值就删该字段**，前端隐藏百分比；
  - 样例课日默认 `W01 · DAY A`（首页现有那串数字本就属于该日）。
- **消费方三处，共用同一份 facts**：`WelcomeView.vue` hero（徽标 + 三张卡 + `4,041 kg / 17 SETS`）、分享卡同三项、`App.vue` NEXT 药丸（`todayCtaLabel` / `todayCtaDate`）。任一入口要换课日就重新生成一份，**绝不手写**。
- **verify 新增断言**：① 重跑生成器与产物逐字节相等；② 从 `data/plan.json` 独立复算 `day_total_kg`、`set_count`、`cycle_total_kg`（不调用被测函数，避免自证）。
- **验收**：首页每个数字都能在 plan 找到对应行；`verify.js` exit 0；build 后 gzip 增量 < 2 KB。

### 3.3 · 0.29 ③ P0-03a 假宣传（已完成，收尾待做）

已删 6 处：休息计时器、CSV/XLSX 导出、`SELF-COACHED` 的 "Zero account"、分享区「英文/中文界面」「no account」、分享卡 `No account required`→`No watermark`、`Every link works on your server`→`Six routes served by one FastAPI process`。收尾见 §1 第 3 条。

### 3.4 · 0.30 ① 日期重算（唯一真相 `plan.meta.startDate`）

- **目标值**：`startDate 2026-11-23`、`endDate 2027-02-21`、测试日 `2027-02-20`；`planId` 若要改则 `rpl-raw-2026-11-23`；`profile.start_date` 同步；`meta.motto` 里写死的 `TEST 2027-02-13`、`12.7W (89 days to test)` 改由生成器模板填充，禁止手写。
- **三条硬要求（用户定）**：
  1. **只走脚本**：`server/tools/gen_data.py`（adapt）→ `synth_plan.py`（build），`data/plan.json` 禁止手改；
  2. **planId 变更必须迁移**：旧库已播种的 `rpl-raw-2026-11-16` → 归档旧周期（保留计划与日志、可回读）+ 以新 planId 播种新周期；**不允许**原地改日期；
  3. **断言强度不降**：锚点日期必须有一条断言直接读 `plan.meta.startDate`；「必须落在测试周」改为按周次相对判断；`tests/browser.mjs` 填问卷的日期也改成从 plan 读，不写死。
- **只在这一分支做**：+7 天后相对时长不变（到测试 89 天、到结束 90 天），`12.7W (89 days)` 数值不变，只是绝对日期 +7。

### 3.5 · 0.30 ② 未开始态页面（`CyclePrestart.vue` 扩容，挂在 `/today` 顶部）

| 区块 | 数据来源 | 空态 |
|---|---|---|
| 倒计时环 | `plan.meta.startDate`（推迟后 11-23，**不写死**） | 无 |
| 首次课预习 | plan 第一节：动作、组×次、顶重、配片（复用既有负荷计算，不另造算法） | `Not sampled` |
| 热身与活动度 | 当日 `warmups` 阶梯（空杆×5 / 35%×3 / 50%×2 / 65%×1），按动作分行 | `Not sampled` |
| 恢复基线 | **只提示「本周测哪几项、怎么测」**，不给数值门槛（未开始态无基线，门槛留训练期） | `Not sampled`（**不写 0**） |

- **硬约束**：纯客户端派生，未开始态**不发任何 `/api/ai/*` 请求**（CDP 网络日志为证）；免费档可见；`/api/performance`、`/api/geometry`、`/api/vault` 仍锁。
- **验收**：320/390/1280 三宽截图，有数据/空数据各一张，日期与 plan 完全一致，四宽无横向溢出。

---

## 4 · 后续版本规格（0.31 起，实现细节可自决，口径变动须先问）

### T3 · 孤表审计（0.31）

以 `store.py` 实际表为准（`cycles` `plans` `logs` `readiness` `readiness_v2` `archives` `body_metrics` `questionnaires` `ai_calls` `attempts` `deletion_tokens` `accounts`，外加处方版本表与会话表），逐表写「孤儿查询」（引用了不存在 `cycle_id` 的行数必须为 0），并写表级隔离单测：A 账户写、B 账户读不到。

### T4 · 主键与迁移（0.32）

`cycles.id TEXT PRIMARY KEY` 全局唯一是缺陷：改成复合主键 `(account_id, id)`，相关表外键随之重建，`user_version` 升位，迁移前快照，导入 409 文案改为「同账号占用 / 另存新 ID」，单测改名 `test_same_cycle_id_allowed_across_accounts`。

### T5 · 降档主动刷新（0.31）

403 → 立即重取 `/api/session`；`timed_until` 到点用**一次性定时器**；`visibilitychange` 回前台补一次刷新。**禁止轮询**（4C4G / 3M 带宽约束）。验收：静置一小时 `/api/session` ≤ 5 次。

### T6 · 读开写关（0.31）

自有数据 GET 放开、写入口锁；派生视图（`performance` / `geometry` / `vault`）整块锁。与 0.28 的差异：free 账号的 DailyRecord **不再整体隐藏**，改为可读、写入口锁。

### R4 · 视觉欠账（0.33）

GEAR 小片与单侧配片；Sheiko 热身（只给主项）；比赛三盏裁判灯（2 白 = GOOD、2 红 = MISS）；测试周四组 UI：SBD 三组 + 计划里真实存在的行，各自独立输入行。

### R4b · 测试周真存（0.34，用户裁定「新表真存」）

新表 `test_results`：一级四变式、二级四变式、5km（用时/配速/心率/备注）入库；ASSAY 可对比，导出与分享卡带出。`meta.testPlan` 现为 `null`（八项变式与 5km 在数据里不存在），本版补齐。

### R5 · 完成率口径（0.35，用户已同意审查推荐）

- 分母只算**到今天（Asia/Shanghai）已到期的计划组**，未来计划不进分母。
- 每组：有实际记录算完成；超额组取 `min(实际组, 计划组)`，不把完成率推过 100%。
- 显式记 0 组 = 有意跳过：进分母、不计完成，该场标「已回顾」，与「没打开」区分。
- 主项 / 变式 / 辅项**三类分开报**，不合加权总数；计划外加练单列 `extra`，不进完成率。
- 只在一个统计函数里实现，ASSAY Overview、动作 register、周卡共用；单测覆盖未来日、超额组、显式零、计划外动作。

### R6 · 首页会员对比（0.36，重点）

位置：`WelcomeView.vue` 截图 deck / 三类用户之后、下载段之前；编号顺延（`09 / Membership`，下载改 `10 / Download`，末段 `11 / Friends`）。单主题（ex 暖纸），只用 `tokens.css` 现有令牌，手写 CSS，不引 UI 库。

文案（英文为准）：小标 `09 / Membership`；标题 `Five tiers, with Free as the base.`；导语 `An invite code sets your tier. Higher tiers include everything below them. When a tier lapses you drop a tier, not your data.`；表下 `Pricing is published. Checkout opens soon. Registration needs an invite code.`

桌面（≥861px）：
1. 表头四列 Free / Lite / Plus / Pro，Ultra 不占列。每列三层：档名（展示衬线大字）、主价格（大号等宽数字）、计费说明（小号等宽大写 `ONE-TIME` / `MONTHLY`）。档名上方用 `BeanMark` 咖啡豆个数表示档位（Free 0、Lite 1、Plus 2、Pro 3）。
2. 币种切换 `CNY | USD`，默认 CNY；切换时价格 180ms 上下翻牌，表格高度不跳。
3. 推荐列：Plus 表头上一枚 `RECOMMENDED` 胶囊，整列底色深半档、两侧 1px 墨线、表头用现有硬投影令牌。
4. 列聚焦：悬停任一格整列高亮 + 表头上浮 2px，其余列不变暗；键盘 Tab 同样生效。
5. 粘性表头：`ResizeObserver` 实测顶栏高度写入 `--topH`，不写死像素。
6. 能力行：前 6 行（价格、计费、设备数、记录与处方、计划视图、导入导出）默认展开，其余折叠；表底 `Show every row ↓` / `Show fewer rows ↑`（带 `aria-expanded`），`grid-template-rows: 0fr → 1fr` 240ms，不用固定 max-height；无 JS 时全部显示。
7. 对勾入场：首次进入视口时 ✓ 用 SVG 描边逐行画出（错开 30ms，总时长 ≤600ms），— 只淡入，仅播一次。
8. 阶梯标记：能力行左侧细竖线标出从哪一档开始包含（Lite 起 / Plus 起 / Pro 起）。

Ultra 横条（表格正下方）：墨底纸字，左 `ULTRA` 等宽小字 + 金色描边咖啡豆，中 `Invite only · includes every Pro capability`，右 `Have a code? Register →`；进入视口时上沿细光左→右扫一次 900ms。

手机（<861px，不横向滚动）：顶部四档改可左右拖的档位卡（复用首页 deck 跟手拖拽 + 吸附），每卡：豆子、档名、价格、计费、该档新增 2–3 项能力，Plus 带 `RECOMMENDED`；卡下能力清单每项一行四档小标（`Free ✓ Lite ✓ Plus — Pro —`）；拖到哪档，该档列加粗高亮联动；深层能力同样默认折叠。

统一要求：`prefers-reduced-motion: reduce` 关全部动效；能力行名与格子内容来自 R3 能力表导出的静态 JSON，不在 Vue 手抄；表格用真 `<table>` / `<th scope>`，✓/— 带 `aria-label`，开关可键盘操作。截图验收：1280 折叠/展开/列聚焦/USD；390 档位卡拖到 Plus 并联动；320 无溢出；减少动效一张。

### R7 · 老站首页效果补齐（0.36）

先逐条对比老站 `Ref/06_Publish_Reference/hub_index.html` 与当前 `WelcomeView.vue`，列「老站有 / 新站有没有 / 处理」清单进 `docs/审美回炉清单.md`，再补缺。已知要核对：滚动驱动截图 tour（滚动决定图层、已过图层抬起变暗、底部 `--tour-p` 进度线、圆点跳转）、分享按钮（系统面板否则复制链接 + `Link copied`）、`--topH` 实测、`.rv` 滚动入场、Friends 段互链。**不搬**：中英切换、暗色主题、Mini/Max 密度、Android APK 下载（两端均 Coming Soon）。

### R8 · 账户内会员面板（0.37）

VAULT 账户区（`#account`）：当前档位（豆子 + 档名）、永久档、Pro 到期日（北京时间）、已登录设备 x/5（可逐个登出）。`Redeem a code` 输入框：成功即时刷新并解除锁定态，失败提示与注册页一致。`/register` 支持 `?code=` 预填（输入框在用户名之上）。首页右上不加档位徽章；应用内顶栏右侧可显示很小档位字样。

### P1 清理清单（并入 0.35）

处方重复、显示版本号不显示哈希、内部标识 `S.Main\|…`、自重 `KG TOP 0`、吨数 139.5/139.6、`FEB13/FEB14`、CTA 闪烁。逐项截图。

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

## 7 · 目录治理（方案已定，未执行；执行时按此表逐条改）

### 7.1 · 已完成的先行项

- `Agent.skill` 已移出仓库 → `RR\builds\Agent.skill`。
- Skill 库已外迁 → `RR\skills\roast-raw-agent\`（`SKILL.md` + `scripts\check_skill.py`）与 `RR\skills\INDEX.md`；仓库 `.qoder\` 已删；`check_skill.py` 改为按脚本自身位置定位。
- `RPLRef` 已瘦身（见 §0 表末行）。

### 7.2 · 目标树

```
C:\Users\Astra\Desktop\RR\
├─ ref-projects\        roast-powerlifting\（530 MB） rplref\（2826 MB，已瘦身）
├─ skills\              INDEX.md  roast-raw-agent\
├─ builds\              Agent.skill
├─ shots\               0.21…0.28  archive\
├─ scratch\             18 个截图脚本 + 4 个老项目探针 + _s27.json + rr-login-repro.mjs
├─ notes\               3 份 RoastRaw-*.md
├─ Archive\             reviews\（2 zip） oneoff\（3 个已执行补丁脚本）
└─ .workbuddy\ .qoder-credits\   历史记录，不动
```

### 7.3 · 逐条改动（全量普查结果，2026-11-15）

**A 组 · 搬 `ref-projects`（19 处）**：`Roast Raw\AGENTS.md` 环境节、`docs\0.01地基_已验证发现.md`、`docs\0.01提示词.md`、`docs\项目交接.md` 三处老项目根 + 一处 `_snapshots`、`docs\审美调研.md`、`RR\skills\roast-raw-agent\SKILL.md` 两处、`RR\RoastRaw-Context-Pack.md` 两处、`RR\RoastRaw-审查策略与预算.md` 四处、`RR\_old_probe.py` / `_old_probe2.py` / `_old_structure.py` / `_old_text.py` 各第 2 行。
**A 组不改**：`Ref\00_README.md`、`Ref\01_Current\SPEC.md`（只读快照，内文停在迁移前是对的；在 `AGENTS.md` 记一句即可）。

**B 组 · 搬 `shots`（21 处脚本 + 仓库 18 处文本）**：`_shot028.mjs`、`_crop_log.mjs`、`_drag_test.mjs`、`_shot_analysis.mjs`、`_shot_cycle.mjs`、`_shot_cycle2.mjs`、`_shot_fix.mjs`、`_shot_l5.mjs`、`_shot_old.mjs`（2 处）、`_shot_round2/3/4/5/6.mjs`、`_shot_sections.mjs`、`_shot_sections2.mjs`、`_shot_sections3.mjs`、`_shot_zoom.mjs` 的绝对输出路径；`TODO.md` 三处 `shots-0.29` / `shots-0.30` 与七行历史中的 `RR/shots-0.2x`、两处 `shots-archive`；`docs\agent-prompt-*.md` 两处；`RR\RoastRaw-UI改版决策.md` 四处；`RR\skills\INDEX.md`。

**C 组 · 分类（无指针）**：探针脚本 → `scratch\`；3 份 `RoastRaw-*.md` → `notes\`；2 个 review zip → `Archive\reviews\`；3 个 `_apply28_*.py` → `Archive\oneoff\`。

### 7.4 · 执行顺序与校验

1. 关掉占用两个老目录的编辑器窗口；建 `ref-projects` 并 `Move-Item`（同盘改名，5 GB 预计 1–3 分钟）→ 改 A 组 19 处 → 每个新路径 `Test-Path`。
2. 建 `shots` 搬 8 个版本目录 → 改 B 组 → 对每个脚本默认输出目录做 `Test-Path`（不存在就建，不实际截图）。
3. 建 `scratch / notes / Archive` 分类落位 → 打印树核对条目数。
4. `git status` 只应显示文档改动；`check_skill.py --root .` PASS；`verify.js` exit 0；build exit 0。

### 7.5 · 三点默认值（用户未回话时按此执行，回话即改）

1. `Archive\` 收：reviews 两 zip + `_apply28_*` 三补丁 + 将来 `Archive\shots`（`docs/shots` 那 183 张）；`_old_*.py` 留 `scratch`。
2. `shots\` 版本目录名用 **`0.21`**（不用 `v0.21`），与 `TODO` 版本号一致。
3. 两个老项目深层（`RPLRef\_repo\mirror`、`Roast PowerLifting` 深层）**不再逐文件扫**；在治理提交里记一句「仅扫索引层，深层未逐文件扫，只读不执行」。

### 7.6 · 后续（与 0.35 绑定的仓库内整理）

`docs/shots` 183 张（33.9 MB，被 git 跟踪）迁 `RR\shots\archive`，**6 张 `old-ref-*.png` 留仓**到 `docs/ref-shots/`；`.gitignore` 加 `docs/shots/`；`tests/browser.mjs` 输出目录改可配置 `SHOTS_DIR`（默认 `RR/shots/<ver>`）。`docs/` 内部分层 `spec/` `handoffs/` `licenses/` `ref-shots/`。只从 HEAD 移除，历史 blob 仍在；要真瘦需重写历史（单独授权，本轮不做）。

---

## 8 · 风险与红线

- **不许**放宽容差、删断言、中和 sabotage、手改 `data/plan.json` 或 `web/dist/`、改 git config、`--amend`、`--no-verify`。提交必须 `git -c user.name=Astra -c user.email=astra@local commit`。
- **不许**在未获授权时 push / 部署 / 覆盖共享服务；`server/tools/deploy.py` 覆盖式写 env 会删 `DEEPSEEK_API_KEY`。
- **不许**把密钥、cookie、数据库、env 文件打进回执、文档、bundle 或截图。
- P0-01 若 30s 内未出现计划内容：记缺陷、进 0.38 清单，**不阻塞开周**（起点仍 11-23）。
- `landing-facts.json` 与 plan 漂移由 verify 两条断言拦截，不允许「先改 JSON 再说」。
- 0.30 重算若波及线上已播种周期：先快照再迁移，归档旧周期；线上 owner 记录极少，风险可控。
- `browser.mjs` 在 0.35 前始终是红基线，**不得**拿来当绿灯证据；`verify.js` 绿也不证明任何界面渲染。

---

## 9 · 未决问题（需要用户一句话）

1. 0.30 的 `planId` 是否随日期改为 `rpl-raw-2026-11-23`（改则须归档旧周期 + 重播种）。
2. `pct` 若在 `meta.anchors` 找不到同源训练最大值 → 删字段（实现时按真实数据定，不需要提前回话）。
3. §7.5 三点默认值是否照此执行。
