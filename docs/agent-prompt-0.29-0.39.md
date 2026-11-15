# 接手指令 v3 · Roast Raw 0.29 → 0.39（开发全流程）

> 取代 `docs/agent-prompt-0.29-0.30.md`（那份只覆盖到 0.30，且写作时目录未搬迁）。本份是唯一有效的交接口径。
> 生成日期 2026-11-15。阅读顺序：本文件 → `AGENTS.md` → `TODO.md` → `RR\skills\roast-raw-agent\SKILL.md` → `docs\项目交接.md` 的对应小节。

## 身份与边界

你是 Roast Raw 的执行 Agent。仓库 `C:\Users\Astra\Desktop\Roast Raw`（git `master`）。只做 Web：Vue 3 + Vite + Motion One + 手写 CSS + FastAPI + SQLite。界面英文、对话中文。

- 不 push、不正式部署、不恢复「停即部署预览」——发布只在用户另行下令后。
- 提交：`git -c user.name=Astra -c user.email=astra@local commit`；禁 `--amend`、`--no-verify`、改 git config、`commit -am` 后不检查未跟踪文件。
- 不手改 `data/plan.json`、`web/dist/`、任何生成物；改 `server/tools/gen_data.py` / `synth_plan.py` 后跑生成链。
- 不弱化断言、不删断言、不中和 sabotage。策略变更时保留原 fixture 链并另加独立算出的新期望。
- `Ref/` 只读；两个老项目只读，不跑其构建/部署流程。

## 目录事实（2026-11-15 搬迁后，照此写路径）

| 用途 | 路径 |
|---|---|
| 仓库 | `C:\Users\Astra\Desktop\Roast Raw` |
| Agent 区 | `C:\Users\Astra\Desktop\RR` |
| 老项目（只读） | `RR\ref-projects\roast-powerlifting`、`RR\ref-projects\rplref` |
| Skill + 自检脚本 | `RR\skills\roast-raw-agent\SKILL.md`、`RR\skills\roast-raw-agent\scripts\check_skill.py` |
| 截图与证据 | `RR\shots\0.29\` 起，逐版本一目录（`RR\shots\0.30\` …） |
| 探针脚本 | `RR\scratch\`（一次性，不入仓） |
| 笔记 | `RR\notes\` |
| 历史存档 | `RR\Archive\`（含 `oneoff\` 已执行补丁） |

`Ref\00_README.md`、`Ref\01_Current\SPEC.md` 里的绝对 Desktop 路径是迁移前快照，**保持原样是对的**，不要"修"。

## 基线（进来先自己验一遍，不要照抄）

- 版本：`web/package.json` = `0.0.28`；`App.vue` 的 `releaseVersion` 由 patch 派生。
- 0.29 已落地三项并提交：`32e923e`、`7ed231c`；之后是文档提交 `ef40ecb`、`82c1aff`、`14ddc2e`、`4fc6433`、`6cbb698`、`0434552`。
- 门禁基线：`node tests/verify.js` 在 0.29 partial 时 302 用例 / 6290 断言 / exit 0，Python 段约 315 s，sabotage 子进程按预期红。
- `tests/browser.mjs` 自 0.21 起是**红基线**（主题切换被删、注册页改四输入），0.35 重写后才可当绿灯证据。
- 已知欠账：`docs/shots` 183 张仍被 git 跟踪（33.9 MB），`tests/browser.mjs:72` 仍硬写 `docs/shots`；迁移留到 0.35 一并做，别单独动。

进来第一条命令：

```sh
git status --short
git log --oneline -8
node tests/verify.js        # 约 6–7 分钟；有红就先报红，不要开始改
```

## 0.29 剩余三项（按序，一步一提交）

### ① P0-01 刷新不闪 404（先实测，再决定改不改）

- 现状：`App.vue` 模板次序已是 `loading → 请求错误 → 空账本 → !plan → !validRoute`，0.28 调过序但**从未实测**，因此不得宣称已修。
- 判据（用户定稿，不许软化）：3M 带宽（375 000 B/s、latency 40ms）连续刷新 10 次；**不判「立即」时点**（SPA 首屏 JS 未到时空正文属正常），判 **200ms / 800ms / 最终加载完成**；禁词 `NOT IN THIS PLAN`、`404`、`NO SESSION`、`Return to the cycle`；最终态断言「30 秒内必须出现计划内容，不得停在骨架」；不设单次骨架停留阈值；**空白正文判失败**。
- 仅当实测仍闪才上骨架：固定高度占位、`--soft` 灰条、**不做 shimmer**；`todayCtaLabel` 在 `plan` 为空时输出 `·`，不输出 `NO SESSION`。
- 证据：`RR\shots\0.29\p0-01-refresh.json`（10 次 × 3 时点的正文与命中标记）。
- 不通过的处理：**起点不动，仍 2026-11-23**，缺陷记进 0.38 审查清单，不因它推迟 0.30。

### ② P0-02 首页数字同源（生成器 + 三处共用 + 复算断言）

- 新增 `server/tools/landing_facts.py`：读 `data/plan.json`，取一个样例课日，写紧凑 JSON 到 `web/src/landing-facts.json`（不把整份 plan 塞进 bundle）。
- 字段契约：

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

- 口径：`day_total_kg` 只算该日、不含热身；`cycle_total_kg` 必须等于 `meta.cycleTonnageKg`（一个字段不许兼当日与整周期）；`pct` = 顶重 / 该动作训练最大值 × 100，最大值取 `meta.anchors` 同源值，**找不到就删字段并在前端隐藏**；样例课日默认 `W01 · DAY A`。
- 消费方三处共用同一份 facts：`WelcomeView.vue` hero（徽标 + 三卡 + `4,041 kg / 17 SETS`）、分享卡同三项、`App.vue` NEXT 药丸（`todayCtaLabel` / `todayCtaDate`）。任一处要换课日就重新生成，**绝不手写**。
- verify 新增：① 重跑生成器与产物逐字节相等；② 从 `data/plan.json` 独立复算 `day_total_kg`、`set_count`、`cycle_total_kg`（不调用被测函数，避免自证）。
- 验收：首页每个数字都能在 plan 找到对应行；`verify.js` exit 0；build 后 gzip 增量 < 2 KB。

### ③ P0-03a 收尾 + 门禁

- 全仓 grep `No account|Zero account|CSV|XLSX|Chinese UI|rest timer|Phone app`，命中即改（已删 6 处，这里只做残留检查）。
- `node tests/verify.js` exit 0、`npm --prefix web run build` exit 0、`check_skill.py --root .` PASS，然后提交。

## 0.30 · 计划未开始态

### ① 日期重算（唯一真相 `plan.meta.startDate`）

- 目标：`startDate 2026-11-23`、`endDate 2027-02-21`、测试日 `2027-02-20`；`planId` 若改则 `rpl-raw-2026-11-23`；`profile.start_date` 同步；`meta.motto` 里的 `TEST 2027-02-13`、`12.7W (89 days to test)` 由模板填充，禁止手写。
- 三条硬要求：**只走脚本**（`gen_data.py` adapt → `synth_plan.py` build）；**planId 变更必须归档旧周期 + 播种新周期**（旧库 `rpl-raw-2026-11-16` 保留计划与日志可回读），不许原地改日期；**断言强度不降**——必须有一条断言直接读 `plan.meta.startDate`，「落在测试周」改为按周次相对判断，`browser.mjs` 填问卷的日期也从 plan 读。
- 只在推迟分支做：+7 天后相对时长不变（到测试 89 天、到结束 90 天），`12.7W (89 days)` 数值不变。`cycleTonnageKg` 139568.0 作零差基线。

### ② 未开始态页面（`CyclePrestart.vue` 扩容，挂 `/today` 顶部）

| 区块 | 数据来源 | 空态 |
|---|---|---|
| 倒计时环 | `plan.meta.startDate`（推迟后 11-23，**不写死**） | 无 |
| 首次课预习 | plan 第一节：动作、组×次、顶重、配片（复用既有负荷计算） | `Not sampled` |
| 热身与活动度 | 当日 `warmups` 阶梯（空杆×5 / 35%×3 / 50%×2 / 65%×1）按动作分行 | `Not sampled` |
| 恢复基线 | 只提示「本周测哪几项、怎么测」，**不给数值门槛** | `Not sampled`（不写 0） |

- 硬约束：纯客户端派生，未开始态**不发任何 `/api/ai/*` 请求**（CDP 网络日志为证）；免费档可见；`/api/performance`、`/api/geometry`、`/api/vault` 仍锁。
- 验收：320/390/1280 三宽截图，有数据/空数据各一张，日期与 plan 一致，无横向溢出。

## 0.31 → 0.39 队列（顺序已定，不并行）

| 版本 | 主题 | 关键范围 | 验收 |
|---|---|---|---|
| 0.31 | 门控与出口 | T6 读开写关、T5 降档主动刷新、T3 孤表审计 + 表级隔离单测、P0-03b 导出、P0-04 `/about` | 门控端点逐行成对；一小时 `/api/session` ≤5 次；12 张表孤儿 0 |
| 0.32 | T4 迁移 | `cycles` 主键改 `(account_id, id)`、12 张表外键重建、`user_version` 升位 | 旧库升级零差；同 `planId` 两账户互不可见；同账户重复仍 409 |
| 0.33 | R4 视觉欠账 | GEAR 小片与单侧配片、Sheiko 热身（只给主项）、比赛三盏裁判灯、测试周四组 UI | 四宽截图 + 每个交互一次实点 |
| 0.34 | R4b 测试周真存 | 新表 `test_results`：八项变式 + 5km 入库；ASSAY 可对比、导出/分享卡带出 | 八项 + 5km 读写一致；降档后可读可导出；迁移零差 |
| 0.35 | R5 + P1 | 完成率单函数；重写 `tests/browser.mjs`（顺带把 `docs/shots` 迁出、输出目录改 `SHOTS_DIR`）；P1 清单清理 | `verify.js` 与 `browser.mjs` 都 exit 0；每个改写断言做一次故意破坏 |
| 0.36 | R6 + R7 | 首页会员对比矩阵；老站首页效果补齐 | 320/360/390/412/1280 无横向溢出；折叠/币种/动效各一张 |
| 0.37 | R8 | 账户内会员面板（档位、Pro 到期、设备 5、兑换码、`/register?code=` 预填） | 兑换升档、续期、过期回落都在界面走通 |
| 0.38 | 独立审查 | 未写代码的会话审 0.29–0.37；含详单 §12 推断项逐条实测 | 审查清单逐条关闭；0.29 若遗留 P0-01 缺陷在此复核 |
| 0.39 | 发布 | 部署 + push（**只在用户另行下令后**） | `deploy.py` 访问契约全 PASS + 公网探测 + `/api/ai/status` `configured: true` |

口径细节都在 `TODO.md` §4（T3–T6、R4–R8、P1）与 §6（数据/代码/审美基线），实现前按小节读，不要整篇背。

## 已确认决策（优先级高于任何默认值）

- 夹具模式：`/api/session` 返回 `authenticated: true` 时**必须同时带 `fixture: true`**；部署环境**永不**设 `RR_ALLOW_OPEN_FIXTURE`。
- T1：64 视图 / 30 分钟 TTL / `time.monotonic` / 重启清零全部保持；线上 worker 数写进部署配置备注，以后改 worker 不必回头改 64。
- 未开始态：只给采样提示、不给数值门槛；四块内容全从 plan 读；缺数据 `Not sampled`，不写 0。
- 训练/恢复建议：纯规则派生、免费开放、不接 AI。
- 本轮运行方式：每个 0.01 本地提交 + 本地构建 + 本地截图；BOUNDARY 写「未部署」。

## 验收命令与分层

| 改动类型 | 必跑 |
|---|---|
| 文档/指针 | `check_skill.py --root .` + 打开改动处逐个确认路径可达；**不跑全量** |
| 统计/数据/契约/API | `node tests/verify.js`（含原 fixture、任意周合成、真重启、sabotage） |
| UI | `npm --prefix web run build` + `verify.js` + 真实浏览器过金/失败路径；`browser.mjs` 在 0.35 前不算证据 |
| 迁移 | 迁移前 SQLite 快照 + 旧库读回零差 + 双账户隔离 |

`check_skill.py` 用法（从仓库根）：

```sh
server/.venv/Scripts/python.exe C:\Users\Astra\Desktop\RR\skills\roast-raw-agent\scripts\check_skill.py --root .
```

## 禁做清单

1. 手改 `data/plan.json`、`web/dist/`、`web/src/landing-facts.json`（只能由生成器写）。
2. 改 `Ref/`、改两个老项目、改 `RR\ref-projects\` 内任何内容。
3. 用桌面旧路径（`Desktop\Roast Power Lifting`、`Desktop\RPLRef`、`RR\shots-0.2x`）——全部失效。
4. 把截图写进仓库 `docs/shots`（0.35 前先落 `RR\shots\<ver>`）。
5. 弱化/删除断言、中和 sabotage、为过门禁放宽容差。
6. push、部署、恢复「停即部署预览」、`--amend`、`--no-verify`、改 git config。
7. 打印或提交任何凭据（`DEEPSEEK_API_KEY`、`GH_TOKEN`、口令哈希）。
8. 在未读完 `TODO.md` 对应小节前凭记忆改统计口径。

## 回执格式

每个 0.01 一次，五字段单块：`RESULT` / `EVIDENCE`（可复算的命令与数字）/ `SCOPE`（改了哪些文件）/ `BOUNDARY`（未验证什么，含「未部署」）/ `NEXT`（归属 GO / ASK / HUMAN）。计划另起一块，用单独一行 `---` 隔开。结论先行，不复述需求，不堆免责声明。
