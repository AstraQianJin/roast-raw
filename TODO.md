# TODO — 想法与执行方向

> 只保留未完成工作及依赖；当前版本查 web/package.json，完成历史查 git。长期协作见 AGENTS.md 与项目 Skill，产品口径见 docs/项目交接.md「本轮确认」。每推进0.01更新；有证据才删除活动项，不复制完成台账。

## 当前执行

- **进度（2026-11-15）**：0.27（邀请码/档位）与 0.28（每账户账本+门控）已本地提交，`verify.js` 退出 0；**0.29（安全与首屏）进行中**：T2 空口令 fail-closed（`RR_ALLOW_OPEN_FIXTURE=1` 只给夹具，`serve_fixture.py` 与 `verify.js` 已注入）、T1 `_scoped` 有界 LRU+锁+TTL+不共享字典（`tests/test_cache.py` 8 条）、P0-03a 首页假宣传文案已改；**未完成**：P0-01 刷新 10 次实测、P0-02 首页数字与 plan 同源（现仍是手写 110.5/70.5/4,041 与 `W05 · DAY B` 标签）。每个 0.01 仍按「本地提交+本地构建+本地截图」，不 push、不部署。
- **0.29 已知偏差（待用户裁定）**：详单 §8.2 期望夹具模式下 `/api/session` 返回 `authenticated: False`、`/api/plan` 401；但夹具前端靠 `authenticated` 决定是否跳登录，改成 False 会让本地预览与浏览器回归全不可用。现取「夹具身份可用 + `/api/session` 显式带 `fixture: true`」：无口令且无夹具开关时启动即抛错，生产带口令时该分支关闭。
- `tests/browser.mjs` 自 0.21 起为红基线（主题切换、三输入注册页等旧契约已失效），按 0.30 重写，本轮不再用其作为 0.27–0.29 的绿灯证据。

- 已批准顺序（2026-11-14改）：本地每0.01新提交、跳过push；0.09–0.12审美回炉、0.13–0.14 AI+待办、0.15–0.19综合审查打磨、0.20才部署新服务器并推私有远程；0.20部署后用户真环境验收，问题回本地修再更新。0.09–0.12每节点给用户简洁预览（截图/清单），减少打扰、不反复问。
- 2026-11-14追加裁定：0.13起一次连续推进到0.20；0.15–0.19全自主（独立审查+修复不逐轮等用户反馈），用户只在0.20部署后真环境验收一次性给反馈。共享口令已由用户指定并设为本机用户环境变量 RR_ACCESS_PASSWORD（值不入仓/不入文档/不入bundle）。
- **2026-11-15 用户裁定（本轮，覆盖上两条中冲突部分）**：执行下方「本轮路线 0.27–0.34」。①注册开放但必须持邀请码，邀请码分档（Free/Lite/Plus/Pro/Ultra），成员权限与定价照老站 ExDark（http://49.233.196.202/ ，本地参照 Ref/06_Publish_Reference/hub_index.html #license）；②首页做老站同款会员对比（规格见 R6）；③Android、iOS 均显示 Coming Soon；④完成率按审查推荐口径（R5）；⑤**发布与部署推迟到本轮全部修完**：本轮内不 push、不正式部署、**也暂停 AGENTS「停即部署预览」**，每次停止仍须本地提交，证据改用本地构建+本地截图，BOUNDARY 写明“未部署”；全部完成后由用户另行下令才进入 0.34 发布。

## 本轮路线 0.27–0.34（2026-11-15 用户裁定，按序执行）

> 依据：老站线上 http://49.233.196.202/ `#license`（2026-11-15 抓取）与本地 `Ref/06_Publish_Reference/hub_index.html`，两者冲突以线上为准。本节写的是范围与验收，实现细节在已确认目标内可自决；标「ASK」的点没定，按括号里的默认值做，在回执 BOUNDARY 里写明。每版 = 本地提交 + 本地构建 + 本地截图，不 push、不部署。

| 版次 | 条目 | 范围 | 验收 |
|---|---|---|---|
| 0.27 | R1 会员档位 + 邀请码（服务端） | 见 R1 | 单测：五档兑换 / 过期降档 / 重复使用 / 吊销 / 无码注册拒绝；`node tests/verify.js` 退出码 0 |
| 0.28 | R2 每账户独立账本 + R3 档位门控 | 见 R2、R3 | 两账户互相看不到对方数据；每个门控接口都有「低档 403 / 达标 200」成对用例；迁移前快照存在，旧库升级往返零差 |
| 0.29 | 安全与首屏（详单 §5、§8、§7） | T2 空口令 fail-closed（启动即拒；夹具走 `RR_ALLOW_OPEN_FIXTURE=1`，部署禁设）、T1 `_scoped` 有界 LRU（上限 64 / TTL 30min / 锁 / 修浅拷贝共享字典）、P0-01 刷新闪 404 骨架加载、P0-02 首页数字全部同源于 plan、P0-03a 删假宣传文案 | 不配口令 `create_app()` 抛错；70 账号淘汰 + 8 线程不丢；刷新 10 次 0 次闪 404（含 3M 节流）；首页每个数字能在课表找到对应行 |
| 0.30 | 计划未开始态（用户 2026-11-15 新增） | 周期改为 2026-11-23 开始（测试日/结束日全站重算并只有一处来源）；未开始态页面：倒计时 + 本周准备清单（首次课预习、热身与活动度、恢复基线：睡眠/静息心率/体重取样），全部由 plan 数据规则派生，免费、离线、可复算，不接 AI | 重算后 seed 校验通过、旧测试日期同步；未开始态在 320/390/1280 截图；清单纯规则派生（无网络请求、无 AI 调用） |
| 0.31 | 门控与出口（详单 §8、§3） | T6 读开写关（自有数据 GET 放开、写入口锁；派生视图整块锁）、T5 降档主动刷新（403→重取 session、`timed_until` 一次性定时器、`visibilitychange`，不轮询）、T3 孤表审计+表级隔离单测、P0-03b CSV/XLSX 导出、P0-04 `/about` | 门控端点对照表逐行成对（低档 403/达标 200，读放写关）；一小时 `/api/session` ≤5 次；12 张表孤儿查询全 0；三格式导出逐行一致 |
| 0.32 | T4 迁移（详单 §9） | `cycles` 主键改 `(account_id,id)`；12 张表外键重建；迁移前快照；`user_version` 升位；导入 409 文案改「同账号占用/另存新 ID」 | 旧库升级零差；同一 `planId` 两账户并存互不可见；同账户重复仍 409；测试改名 `test_same_cycle_id_allowed_across_accounts` |
| 0.33 | R4 视觉欠账 | GEAR 小片与单侧配片、Sheiko 热身（只给主项）、比赛三盏裁判灯、测试周四组 UI（SBD 三组 + 计划里真实存在的行，各自独立输入行） | 四宽截图 + 每个交互一次实点（灯 2 白=GOOD、2 红=MISS） |
| 0.34 | R4b 测试周真存（用户裁定 A） | 新表 `test_results`：一级四变式、二级四变式、5km（用时/配速/心率/备注）入库；ASSAY 可对比、导出/分享卡带出 | 八项+5km 写入读回一致；降档后仍可读可导出；迁移零差 |
| 0.35 | R5 + P1 清理 | 完成率单函数（PLANNED/DONE/extra/显式零/未来日/三类分开）；重写 `tests/browser.mjs`；P1 清单（处方重复、显示版本号不显示哈希、内部标识 `S.Main\|…`、自重 `KG TOP 0`、吨数 139.5/139.6、FEB13/FEB14、CTA 闪烁） | `verify.js` 与 `browser.mjs` 都退出码 0；对每个改写断言做一次故意破坏；P1 逐项截图 |
| 0.36 | R6 + R7 | 见 R6、R7 | 320/360/390/412/1280 无横向溢出；折叠/展开、粘性表头、CNY/USD 切换、减少动效模式各截一张 |
| 0.37 | R8 | 见 R8 | 兑换升档、Pro 续期、过期回落都在界面上走通并截图 |
| 0.38 | 独立审查 + 修复 | 由没写代码的会话审 0.29–0.37（含详单 §12 的推断项逐条实测） | 审查清单逐条关闭；verify + build 全部退出码 0（browser 自 0.35 起重写后再作绿灯） |
| 0.39 | 发布（只在用户另行下令后） | 见原 0.34 发布口径 | `deploy.py` 访问契约全 PASS + 公网探测 + `/api/ai/status` `configured: true` |

### 0.29 施工详单 · 安全与首屏

> 状态（2026-11-15）：T2、T1、P0-03a 已完成并提交（`32e923e`、`7ed231c`）；本节剩下 **P0-01** 与 **P0-02** 未做。四条 ASK 是暂定默认值，用户改一处即可。

**① P0-01 刷新不闪 404（未做）**

- 现状：`web/src/App.vue` 模板次序为 `loading` → 请求错误 → 空账本 → `!plan`（`Reading the plan.`）→ `!validRoute`（`NOT IN THIS PLAN`）；0.28 加过 `!plan` 一层，**从未实测**，因此不能宣称已修。
- 改法：实测若仍闪，把骨架块提前到 `!plan` 之前（`<div class="day-skeleton" role="status" aria-live="polite">`，三行灰条，占位高度与课日卡一致）；`todayCtaLabel` 在 `plan` 为空时不再渲染 `NO SESSION`，改渲染 `·` 占位，避免首屏出现"错误感"文案。
- 验收（CDP，本机夹具服务）：设 3M 带宽，连续刷新 10 次，每次在立即 / 200ms / 800ms 三个时点取 `document.body.innerText`；断言**不出现** `NOT IN THIS PLAN`、`404`、空正文，允许骨架与 `Reading the plan.`；不设骨架停留时长阈值。空白正文同样判失败（ASK-1 默认：算失败）。
- 证据：`C:\Users\Astra\Desktop\RR\shots-0.29\p0-01-refresh.json`（10 次 × 3 时点的原文与命中标记）。

**② P0-02 首页数字同源（未做）**

- 新工具：`server/tools/landing_facts.py`，读 `data/plan.json`，写 `web/src/landing-facts.json`（小文件，只含一个样例课日）。
- 字段：`{planId, startDate, week, day, date, label, lifts[{lift, movement, top_kg, pct, sets, reps}], set_count, total_kg, tonnage_basis}`。
- 口径：`top_kg` = 该日该主项处方最大重量，**不含热身**；`set_count` = 该日全部处方组数（主项 + 变式 + 辅项）；`total_kg` = Σ(重量 × 次数 × 组数)，取整与 `meta.cycleTonnageKg` 同 basis（主项 0.5 kg / 变式 2.5 kg）；`label` 由 `W{week:02d} · DAY {day}` 生成。样例课日默认 **W01 · DAY A**（ASK-2；理由是首页现有那串数字本就属于该日，改标签最省且不需再造数据）。
- 前端改点：`web/src/components/WelcomeView.vue` 第 134（`W05 · DAY B` 徽标）、139（`4,041 kg / 17 SETS`）、181–184（`DAY B · W05` 与 `110.5 / 70.5 / 4,041`）、198–201（分享卡同三项）全部绑定 facts；删除全部字面值。hero 与分享卡**强制同一课日**。
- verify 断言：新增 `landingFactsCheck()` —— 重跑生成器、与产物逐字节相等；再从 `data/plan.json` 独立复算 `total_kg` 与 `set_count`，两个数必须与产物一致（不调用被测函数，避免自证）。
- 验收：首页每个数字可在 plan 中找到对应行；`node tests/verify.js` 退出 0；`npm --prefix web run build` 后 gzip 增量 < 2 KB（不把整份 plan 塞进 bundle）。

**③ P0-03a 假宣传（已完成 6 处）**

已改：`Check-offs and the day summary`（删"休息计时器"）、`JSON export …`（删 CSV/XLSX）、`SELF-COACHED` 三标签（删 "Zero account"）、分享区（删"英文/中文界面""no account"）、分享卡清单（`No watermark` 替换 `No account required`）、08 段（`Six routes served by one FastAPI process` 替换 `Every link works on your server`）。收尾时再全仓 grep `No account|Zero account|CSV|XLSX|Chinese UI|rest timer|Phone app` 清零，命中即改。

### 0.30 施工详单 · 计划未开始（含 11-23 重算）

**① 日期重算（唯一真相 `plan.meta.startDate`）**

- 目标值：`startDate 2026-11-23`、`endDate 2027-02-21`、测试日 `2027-02-20`；`planId rpl-raw-2026-11-23`、`name` 同步；`profile.start_date` 同步；`meta.motto` 里写死的 `TEST 2027-02-13` 与 `12.7W (89 days to test)` 改为由生成器按日期模板填充，禁止手写。
- 生成路径：只走 `server/tools/gen_data.py` → `synth_plan.py`，`data/plan.json` 不手改（项目既有禁令）。`Adjust start date` 已走 `/questionnaire` 重建计划，**不新增"整周推迟"操作**，避免两套日期来源。
- 断言：`validate_plan` 通过；49 节；`cycleTonnageKg` 与偏移前一致（日期不影响负荷，可作零差基线）；所有读日期做期望的用例改为从 plan 取，个别"必须落在测试周"的语义断言改为按周次相对判断（换写法，不降强度）。

**② 未开始态页面（`web/src/components/CyclePrestart.vue` 扩容，ASK-3 默认：/today 顶部）**

- 区块一：倒计时环（现有 `days → pct/num/lbl` 逻辑不动）。
- 区块二：首次课预习 —— 取 plan 第一节（W01 Day A）：动作名、组×次、顶重、配片（复用既有负荷计算，不另造算法）。
- 区块三：热身与活动度 —— 取当天 `warmups` entry 的阶梯（空杆×5 / 35%×3 / 50%×2 / 65%×1），按动作分行。
- 区块四：恢复基线 —— 只展示"本周该采样哪几项 + 怎么测"，缺数据显示 `未取样`，不显示 0（ASK-4 默认：不写库、不给数值门槛）。
- 硬约束：纯客户端派生，未开始态**不发任何 `/api/ai/*` 请求**（CDP 网络日志为证）；免费档可见，付费派生视图（performance/geometry/vault）仍锁。
- 验收：320/390/1280 三宽截图；四宽无横向溢出；空数据态与有数据态各一张；日期显示与 plan 完全一致。

### 已确认决策（2026-11-15 用户裁定，取代上方默认值）

- **P0-01 判定（改）**：不判「立即」时点的空白（SPA 首屏 JS 未到之前空正文正常）；判 **200ms、800ms、最终加载完成**三个时点；禁词追加 `NO SESSION`、`Return to the cycle`（与 404 属同一页）；新增**最终态断言**：3M 带宽下 **30 秒内必须出现计划内容**，不得停在骨架；不设单次骨架停留阈值；空白正文仍判失败。
- **T1（确认保持）**：64 / 30min TTL / `time.monotonic` / 重启清零 全部保持；新增要求：把**线上 worker 数写入部署配置备注**（`AGENTS.md` 环境节 + `server/tools/deploy.py` 注释），worker 数将来变化不必回头改 64。
- **P0-02（补丁）**：`total_kg` 必须拆成 `day_total_kg`（该日总和，不含热身）与 `cycle_total_kg`（整周期，**必须等于** `meta.cycleTonnageKg`）；`pct` 定义为「顶重占该动作训练最大值的百分比」，与 plan 同源，**找不到同源最大值就删该字段**；消费方扩到三处：hero、分享卡、**NEXT 药丸**（`App.vue` 的 `todayCtaLabel` / `todayCtaDate`）；任一入口要换课日就单独生成一份 facts，绝不手写。
- **0.30 重算（确认，仅在推迟分支做）**：+7 天后相对时长不变，到测试 89 天、到结束 90 天，`motto` 的 `12.7W (89 days)` 数值不变，只有绝对日期 +7；三条硬要求见下节；`planId` 若改，旧库已播种的旧 planId **必须归档旧周期 + 播种新周期**，不原地改日期。
- **未开始态（确认）**：只给采样提示、不给数值门槛（未开始态无基线，给门槛就是假精确，门槛留训练期）；四块内容全部从 plan 读；倒计时目标日取 **`plan.meta.startDate`**，不写死 11-16；缺数据显示 `Not sampled`（中文口径「未取样」），**不写 0**。

### 落地方案：关键代码 · 关键数据 · 审美

#### 1. 关键数据（0.30 重算前后对照）

| 项 | 现值（11-16 版） | 改后（11-23 版） | 备注 |
|---|---|---|---|
| `meta.startDate` | 2026-11-16 | **2026-11-23** | 唯一真相；其余日期由它派生 |
| `meta.endDate` | 2027-02-14 | **2027-02-21** | 13 周整 |
| 测试日 | 2027-02-13 | **2027-02-20** | 结束前一天 |
| 到测试 / 到结束 | 89 / 90 天 | **89 / 90 天** | 相对时长不变，motto 数值不动 |
| 周数 / 节数 | 13 / 49 | 13 / 49 | 不变 |
| `meta.cycleTonnageKg` | 139568.0 | **139568.0** | 日期不影响负荷，作零差基线 |
| `meta.planId` | `rpl-raw-2026-11-16` | `rpl-raw-2026-11-23`（若改） | 改则必须走归档+重播种 |

#### 2. 0.29 · P0-01 代码要点

现状模板次序（`web/src/App.vue`）：`loading` → 请求错误 → 空账本 → `!plan`（`Reading the plan.`）→ `!validRoute`（`NOT IN THIS PLAN`）。0.28 已把 `!plan` 放在 `!validRoute` 之前，**但从未实测**。若实测仍闪，按下面收敛：

```vue
<!-- 骨架：固定高度占位，不用 shimmer 动画（尊重减少动效偏好） -->
<main :aria-busy="loading">
  <div v-if="loading || !plan" class="day-skeleton" role="status" aria-live="polite">
    <span class="sk-line w-40"></span><span class="sk-line w-70"></span><span class="sk-line w-55"></span>
    <span class="sr-only">Reading the plan.</span>
  </div>
  <div v-else-if="!validRoute" class="empty-state">NOT IN THIS PLAN …</div>
```

```css
.day-skeleton { display: grid; gap: 10px; padding: 18px 16px; border: 1px solid var(--hair); border-radius: 14px; background: var(--panel); min-height: 168px; }
.sk-line { height: 14px; border-radius: 3px; background: var(--soft); }
```

- `todayCtaLabel` 在 `plan` 为空时输出 `·`，不渲染 `NO SESSION`（该文案是禁词之一）。
- 探针草图（一次性，不入仓）：`page.emulateNetworkConditions({downloadThroughput: 375000, uploadThroughput: 375000, latency: 40})` → 10 次 `page.reload()`；每次取 200ms、800ms 的 `document.body.innerText`，再 `waitForFunction` 等计划内容出现（上限 30s）；断言三个时点都不含 `NOT IN THIS PLAN|404|NO SESSION|Return to the cycle`，且最终态命中计划内容，正文非空。

#### 3. 0.29 · P0-02 数据契约与生成器

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

- `server/tools/landing_facts.py`：读 `data/plan.json`，按 `week` + `day` 取该课日；字段名以 `sessions[0]` 实际结构为准（**先打印一条真实 session 再写映射，禁止凭记忆猜键名**）；输出紧凑 JSON（`separators=(',', ':')`），产物 `web/src/landing-facts.json`。
- `cycle_total_kg` 直接取 `meta.cycleTonnageKg`，并在 verify 里断言两者相等（防止将来有人只改一个）。
- `pct`：`top_kg / 该动作训练最大值 × 100`，训练最大值取 `meta.anchors` 同源值；同源值缺失则**不输出该字段**，前端隐藏百分比标签。
- 三处绑定：hero 徽标与三张卡（`W0x · DAY y`、`top_kg`、`set_count`、`day_total_kg`）、分享卡同三项、`App.vue` NEXT 药丸（`todayCtaLabel` / `todayCtaDate`）。三处共享同一份 facts；要换日就再生成一份，不手写。
- verify 新断言：①重跑生成器与产物逐字节相等；②从 `data/plan.json` 独立复算 `day_total_kg`、`set_count`、`cycle_total_kg` 与产物一致（不调用被测函数）。

#### 4. 0.30 · 重算三条硬要求

1. **只走脚本**：`server/tools/gen_data.py`（adapt）→ `synth_plan.py`（build），`data/plan.json` 禁止手改；
2. **planId 变更必须迁移**：旧库已播种 `rpl-raw-2026-11-16` → 归档旧周期（保留其计划与日志，可回读）、以新 planId 播种新周期；**不允许**把旧周期原地改日期。实现须复用既有 archive 机制；若无，则新增 `archive_cycle` + 迁移前后快照 + 往返读回单测；
3. **断言强度不降**：锚点日期必须有一条断言直接读 `plan.meta.startDate`；「必须落在测试周」这类断言改为按周次相对判断；`tests/browser.mjs:1245` 填问卷的日期也改成从 plan 读，不写死。

#### 5. 0.30 · 未开始态四区块

| 区块 | 数据来源 | 空态 |
|---|---|---|
| 倒计时环 | `plan.meta.startDate`（推迟后 11-23） | 无 |
| 首次课预习 | plan 第一节：动作、组×次、顶重、配片（复用既有负荷计算） | `Not sampled` |
| 热身与活动度 | 当日 `warmups` entry 阶梯（空杆×5 / 35%×3 / 50%×2 / 65%×1） | `Not sampled` |
| 恢复基线 | 仅提示「本周测哪几项、怎么测」 | `Not sampled` |

- 全部客户端派生，未开始态**不发任何 `/api/ai/*` 请求**；免费档可见；`/api/performance`、`/api/geometry`、`/api/vault` 仍锁。

#### 6. 审美基线（沿用 2026-11-14 裁定）

- 只复用旧 App / 旧站视觉语言与 `tokens.css` 变量，不新增装饰性巧思；骨架用 `--soft` 灰条、不做 shimmer。
- 数字排版沿用 hero 现有 `clamp()` 字号与 `small` 单位写法；小标题沿用 `section-label` 大写 + 字距。
- 未开始态四块沿用 `.prestart` / `.facts` 卡片的边框、圆角与底纹，不新造卡片样式。
- 交互控件可视高度 ≥44px；三宽（320/390/1280）无横向溢出；减少动效模式下不跑动画。

#### 7. 验收矩阵

| 版 | 命令 | 证据 |
|---|---|---|
| 0.29 | `node tests/verify.js`、`npm --prefix web run build` | `shots-0.29/`：P0-01 十次刷新 JSON + 三时点快照、首页 hero/分享卡/NEXT 三处截图、hero 数字回溯表 |
| 0.30 | 同上 + `node tests/browser.mjs`（0.35 前仍红，不作绿灯） | `shots-0.30/`：320/390/1280 未开始态、有数据/空数据各一张、日期与 plan 对照表 |

#### 8. 风险与回滚

- P0-01 若 30s 内未出现计划内容：记为缺陷，**不阻塞开周**（起点仍 11-23），进 0.38 审查清单。
- `landing-facts.json` 与 plan 漂移：由 verify 两条断言拦截，不允许"先改 JSON 再说"。
- 重算若波及线上已播种周期：先快照再迁移，归档旧周期；本地无日志、线上 owner 记录极少，风险可控。




- **五档**：`free < lite < plus < pro < ultra`，高档包含低档全部能力。价格只做展示，**本轮不接支付**（首页写 “Pricing is published. Checkout opens soon.”）。

| 档位 | 价格（照老站） | 计费 | 拿到的方式 |
|---|---|---|---|
| Free | $0 | 永久免费 | 任何有效邀请码注册时的最低档 |
| Lite | US$19.9 · ¥68 | 一次性，永久 | Lite 码 |
| Plus | US$69.9 · ¥198 | 一次性，永久 | Plus 码 |
| Pro | US$19.9/mo · ¥98/mo | 按月 | Pro 码，每个码默认 30 天（ASK：天数，默认 30） |
| Ultra | 不标价 | 仅邀请 | Ultra 码；owner 播种时固定为 Ultra |

- **注册必须带邀请码**：`/api/register` 加必填 `invite_code`；码无效、已用尽、已吊销、已过有效期一律 422，提示文案不能泄露码是否存在。保留现有用户名规则与 PBKDF2。
- **邀请码分档**：每个码带 `tier`、`max_uses`（默认 1）、`expires_at`（码本身的有效期，可空）、`grant_days`（只对 Pro 有意义）、`revoked_at`、`note`。数据库只存码的 sha256，明文只在生成时打印一次。格式 `RR-{TIER}-XXXX-XXXX`，去掉 0/O/1/I 这类易混字符。
- **发码工具**：新建 `server/tools/invite.py`（create / list / revoke），只在本机或经 SSH 由 owner 运行，**不做网页管理后台**（ASK：要不要后台，默认不要）。
- **永久档与限时档分开存**：账户存 `base_tier`（永久，取历次 Lite/Plus/Ultra 兑换的最高档）和 `timed_tier` + `timed_until`（Pro）。实际档位 = 两者取高，限时档过期就自动回落到 `base_tier`。照老站：「过期掉的是档位，不是数据」——**降档绝不删除、不隐藏已有记录，只锁住新的操作入口**。
- **已登录账户兑换**：新增 `POST /api/membership/redeem`。高档码升档；Pro 码在当前 `timed_until` 基础上顺延；低档码不会降档（返回 200 并说明“已是更高档位”，同时不消耗这个码）。
- **设备上限 5**（老站四档都是 5）：新增会话表，每账户最多 5 个有效会话，第 6 次登录淘汰最早的；改密码仍然让该账户全部会话失效。
- **迁移**：`accounts` 加列走附加迁移，迁移前先快照；老账户默认 `base_tier=free`，owner 播种后为 `ultra`。

### R2 · 每账户独立账本（0.28）

- 取代旧口径「注册账户共用同一本训记」。所有 journal 数据表（周期、计划版本、logs、readiness、body metrics、attempts、AI 调用记录与配额、deletion tokens 等，以 `store.py` 实际表为准）加 `account_id`，**所有查询都按会话里的账户过滤**。
- 迁移：先整库快照 → 现有数据全部归 owner → 加索引。旧快照用新代码打开，数据零丢失。
- 新账户首次登录是空账本，走现有导入流程；首页演示数据不受影响。
- AI 每日 20 次配额改成按账户算（北京日不变）。

### R3 · 档位门控（服务端为准，前端只做展示，0.28）

照老站能力矩阵映射到 Roast Raw 现有功能（ASK：映射可调，默认如下）：

| 能力（首页对比表用的英文行名） | Free | Lite | Plus | Pro | Ultra |
|---|---|---|---|---|---|
| Logging & daily prescription（Day 记录 + 处方） | ✓ | ✓ | ✓ | ✓ | ✓ |
| Cycle, block & week views（四层计划视图） | ✓ | ✓ | ✓ | ✓ | ✓ |
| Plan import & export（导入 / 导出 / 归档删除三件套） | ✓ | ✓ | ✓ | ✓ | ✓ |
| Basic stats（ASSAY Overview） | ✓ | ✓ | ✓ | ✓ | ✓ |
| Share card（日分享卡） | ✓ | ✓ | ✓ | ✓ | ✓ |
| Gear & Sheiko warm-ups（配片 + 热身） | — | ✓ | ✓ | ✓ | ✓ |
| Test week & meet attempts（测试周 + 三盏灯） | — | ✓ | ✓ | ✓ | ✓ |
| Muscle-group map（肌群图与肌群贡献） | — | — | ✓ | ✓ | ✓ |
| Lift register & trends（ASSAY By lift / Trend：逐动作完成率、e1RM） | — | — | ✓ | ✓ | ✓ |
| Recovery & body metrics（readiness、体重/身体趋势） | — | — | ✓ | ✓ | ✓ |
| ORACLE AI brief（20 次/北京日） | — | — | — | ✓ | ✓ |
| VAULT cloud ledger（云账本状态与备份） | — | — | — | ✓ | ✓ |
| Devices per account | 5 | 5 | 5 | 5 | 5 |

- 服务端：门控接口低档返回 403 `{"error":"…","required_tier":"plus"}`；前端统一用一个锁定态组件：显示所需档位 + “Redeem a code” 链接到账户会员面板，不弹窗、不遮挡已有数据。
- 已有数据在降档后仍可**只读查看和导出**（ASK：默认可读可导出、不可新增）。
- 档位判断只有一处来源（服务端一个函数 + 一张能力表），前端从 `/api/session` 拿 `tier` 与能力列表，不在前端再抄一份矩阵。首页对比表也从这张能力表生成（构建时导出为静态 JSON），避免两份副本漂移。

### R5 · 完成率口径（0.30，审查推荐，用户已同意）

- 分母只算**到今天为止（Asia/Shanghai）已经到期的计划组**，未来的计划不进分母。
- 每个计划组：有实际记录就算完成；超出计划的组不把完成率推过 100%（每个动作取 `min(实际组, 计划组)`）。
- 显式记 0 组 = 有意跳过：计入分母、不计完成，但这一场标为“已回顾”，与“没打开”区分显示。
- 主项 / 变式 / 辅项三类分开报，**不合成一个加权总数**；计划外加练单独列成 “extra”，不进完成率。
- 这一口径只在一个统计函数里实现，ASSAY Overview、动作 register、周卡共用；单测覆盖：未来日、超额组、显式零、计划外动作。

### R6 · 首页会员对比（0.31，重点）

位置：`WelcomeView.vue` 里放在截图 deck / 三类用户之后、下载段之前，编号顺延（`09 / Membership`，下载改 `10 / Download`，最后加 `11 / Friends`）。单主题（ex 暖纸），颜色、字体、阴影只用 `tokens.css` 现有令牌，手写 CSS，不引新 UI 库。

**文案（英文为准）**
- 小标：`09 / Membership`
- 标题：`Five tiers, with Free as the base.`
- 导语：`An invite code sets your tier. Higher tiers include everything below them. When a tier lapses you drop a tier, not your data.`
- 表下说明：`Pricing is published. Checkout opens soon. Registration needs an invite code.`

**桌面（≥861px）：对比矩阵**
1. 表头四列 Free / Lite / Plus / Pro，Ultra 不占列（照老站）。每列表头三层：档名（展示衬线大字）、主价格（大号等宽数字）、计费说明（小号等宽大写，如 `ONE-TIME` / `MONTHLY`）。档名上方用 `BeanMark` 咖啡豆的个数表示档位高低（Free 0 颗，Lite 1，Plus 2，Pro 3），这是本项目自己的品牌元素，不另画图标。
2. **币种切换**：表头右上一个小的 `CNY | USD` 分段开关，默认 CNY；切换时价格数字做 180ms 上下翻牌（旧数字上移淡出、新数字下方淡入），表格高度不跳。
3. **推荐列**：Plus 列表头上方一枚小胶囊 `RECOMMENDED`（ASK：要不要、放哪一列，默认 Plus），整列底色比纸色深半档，列两侧 1px 墨线，表头加项目现有的硬投影令牌。
4. **列聚焦**：鼠标移到某一列任意格子，整列高亮（底色加深 + 表头上浮 2px），其余列不变暗；键盘 Tab 到表头时同样生效。
5. **粘性表头**：向下滚时表头贴在顶栏下面，顶栏高度用 `ResizeObserver` 实测写入 `--topH`（照老站），不写死像素。
6. **能力行**：前 6 行（价格、计费、设备数、记录与处方、计划视图、导入导出）默认展开，其余行折叠。表底一个文字按钮 `Show every row ↓` / `Show fewer rows ↑`，带 `aria-expanded`；展开用 `grid-template-rows: 0fr → 1fr` 动画 240ms，不用固定 max-height。没有 JS 时所有行直接显示。
7. **对勾入场**：表格第一次滚进视口时，✓ 用 SVG 描边从左到右逐行画出（每行错开 30ms，总时长不超过 600ms）；— 只淡入。只播一次。
8. 档位分组标记：能力行左侧用一条细竖线标出从哪一档开始包含（Lite 起 / Plus 起 / Pro 起），让读者一眼看出“阶梯”。

**Ultra 横条**（表格正下方，紧贴）
- 整条墨色底、纸色字：左边 `ULTRA` 等宽小字 + 一颗金色描边咖啡豆，中间 `Invite only · includes every Pro capability`，右边 `Have a code? Register →` 链到 `/register`。
- 进入视口时横条上沿有一道细光从左扫到右，只扫一次，时长 900ms。

**手机（<861px）：不横向滚动**
- 顶部四档改成一排可左右拖动的档位卡（复用首页截图 deck 的跟手拖拽 + 吸附逻辑），每张卡：豆子、档名、价格、计费、该档“新增”的 2–3 项能力；Plus 卡带 `RECOMMENDED`。
- 卡片下面是能力清单：每项能力一块，块内一行四个档位小标（`Free ✓ Lite ✓ Plus — Pro —`）。320px 下不换出边框、不横滚。
- 当前拖到哪张档位卡，下面清单里该档那一列加粗高亮，两者联动。
- 同样默认折叠深层能力，按钮同桌面。

**统一要求**
- `prefers-reduced-motion: reduce` 时关闭翻牌、描边、扫光、拖拽惯性，内容全部直接可见。
- 能力行名和每格内容来自 R3 那张能力表（构建时导出的静态 JSON），不在 Vue 里手抄。
- 可访问性：表格用真正的 `<table>`、`<th scope>`；✓ / — 带 `aria-label="Included"` / `"Not included"`；切换开关可键盘操作。
- 截图验收：1280 折叠 / 展开 / 列聚焦 / USD；390 档位卡拖到 Plus 并联动清单；320 无溢出；减少动效模式一张。

### R7 · 老站首页效果补齐（0.31）

- 先逐条对比老站 `hub_index.html` 与当前 `WelcomeView.vue`，列一张「老站有 / 新站有没有 / 处理」清单放进 `docs/审美回炉清单.md`，再补缺的。
- 已知要核对的老站效果：滚动驱动的截图 tour（滚动位置决定当前图层，已过的图层抬起变暗形成层叠，底部细进度线 `--tour-p`，圆点可点跳转）；分享按钮（有系统分享面板就用，否则复制链接 + `Link copied` toast）；`--topH` 实测顶栏高度；`.rv` 滚动入场；Friends 段（Roast Raw 新站与老站互链）。
- **不搬**：中英切换（界面只用英文）、暗色主题、Mini/Max 密度切换（ASK：默认不搬）、Android APK 下载（Android、iOS 都显示 Coming Soon）。

### R8 · 账户内会员面板（0.32）

- 位置：VAULT 账户区（`#account`）。显示当前档位（豆子 + 档名）、永久档、Pro 到期日（北京时间）、本账户已登录设备数（x / 5，可逐个登出）。
- `Redeem a code` 输入框：成功后档位即时刷新、对应锁定态解除；失败提示与注册页一致。
- `/register` 支持 `?code=` 预填（首页 Ultra 横条和分享出去的邀请链接用），码输入框在用户名之上。
- 首页右上 `MyPlan` 旁不加档位徽章（避免首页拥挤）；进入应用后顶栏右侧可显示一个很小的档位字样（ASK：默认显示）。

## 已确认路线（尚未做）

| 版次 | 用户需求 | 执行方向 | 验收与依赖 | 状态 |
|---|---|---|---|---|
| 0.10 | 审美回炉清单扩展 | 已完成：ex暖纸Light+双主题周期六色+硬投影token；导航单行四项、Settings齿轮、L/D主题段；逐页清单 docs/审美回炉清单.md；verify+browser全绿（1755断言） | 逐页清单+独立审查+用户候选对比 | 已完成 |
| 0.11 | 发布页动效 | 审查老项目站点源码的发布页首页，照抄所有动效；新建落地首页+应用内关键动效同步升级，内容填新项目；/welcome独立路由且设为首页（/渲染落地页，Today迁/today，深链与回归同步改） | 动效清单+实现 | 已完成 |
| 0.12 | 完成上述全部修改 | 落地0.09–0.11清单 | 全回归+四宽双主题截图 | 已完成 |
| 0.13 | 停即部署+AI | 已完成：Basic口令门（环境变量启用，401整站）、DeepSeek展望/聊天/北京日20次事务配额/失败导出、v5迁移ai_calls、deploy.py备份管线；verify+browser全绿+1次真实调用 | 停即部署预览协议已入AGENTS/Skill | 已完成 |
| 0.14 | 测试周+删除 | 已完成：测试周/比赛三把（92.5/100/102.5%向下2.5kg、逐把确认、miss重复/good不降）；归档删除三件套（强制导出token+精确ID二次确认+删前快照+删全部子表）；v5扩展attempts/deletion_tokens；13+4单测、browser全绿（1902断言） | 迁移仍走未发布v5扩展 | 已完成 |
| 0.15–0.19 | 综合审查打磨 | 已完成：0.15老App视觉语言全页复用+主项杠铃UI（去除TOP/WORK/BACKOFF、重量前置、LOG内联）；0.16不对称单行清理+真实横向溢出修复（CycleStrip周范围标签、容量值列宽）+noOverflow改用clientWidth并新增ink溢出断言（移动端innerWidth会随溢出膨胀使旧断言恒真）；0.17日分享卡TopSet骨架+赛扣杠铃；0.18复刻老App开训前屏（倒计时环+事实卡+LOAD PROFILE相位柱/顶组%1RM线，固定日历口径改写note与Adjust入口）；0.19自审+回归加固+README/Skill指针同步。verify 6290 checks、browser 2235断言/174截图全绿 | 审查结论点名位置 | 已完成 |
| 0.20 | 部署、推送 | 访问口径已按用户裁定改为「公开落地页 + 账户登录」，并已于 2026-11-14 20:40 部署上线：SPA 外壳与 /welcome /login /register 公开、仅 journal API 需会话、accounts 表附加迁移（不动 user_version）、PBKDF2 口令与 HttpOnly SameSite=Lax 会话 cookie、用户名不区分大小写、SPA 外壳 no-store 防止手机留旧页；deploy.py 部署后从公网核验完整访问契约而非只探 health。线上 `GET /` 200 且无 Basic 挑战、`/api/plan` 401、`Astra` 任意大小写登录 200、注册/登出复锁均 PASS（25/25 项，见 README 访问段）。owner 口令统一为本机用户环境变量 RR_ACCESS_USERNAME/RR_ACCESS_PASSWORD（值不入仓/文档/bundle） | 验收：公网实测 25/25 PASS（landing/资产/welcome/login/register 公开、匿名 journal 401、错口令 401、owner 登录 200、登出复锁）；待最末一步：私有远程 AstraQianJin/roast-raw 推送 | 已完成（部署）；推送待办 |

| 0.22 | L2 + 首页截图交互 | 已完成：`/plan` 周期总览、`/plan/block/:id` 块概览、`/plan/week/:n` 当周三天视图分离；删 4 张 Block 卡与 week rail，周方块直接跳周；指标区三等列等高；无主项日去掉 ACCESSORY WORK；主项重量放大、日标题句式大小写；LoadProfile 文献式图注/轴说明/去卡片阴影；首页去左右箭头改 pointer 跟手拖拽+吸附、细轨滑块指示器、图注名与简介居中、截图扩到 4 张（390×844 实拍）。证据：RR/shots-0.22。 | 未做：L3 全部；browser.mjs 旧契约待 L3 后重写；公网部署待用户验收 | 本地完成 |
| 0.23 | L5 首页复刻与品牌 | 已完成：`WelcomeView.vue` 重写为九段（hero 四事实卡 SBD/16 叶周图/AI 展望/云端同账本、01 CAPACITY+CONDITIONING 20–60 等效分钟、02 纸质会话 MAIN LIFTS/TOTAL LOAD 4,041 kg、03 1080×1440 分享卡、04 AI 对比、05 云端同账本、06 截图 deck、07 三类用户、08 六环链条、09 下载 Coming Soon）；新建 `BeanMark.vue`（23px 咖啡豆，masthead 与 favicon 同款）；`App.vue` 周页加 conditioning 卡（13 周柱+20–60 带+ESTIMATE）；截图 4 张按当前构建重拍（390×844）。证据：`RR/shots-0.23`（m-top、v-*、d-*、zoom-mark、deck-dragged），build 0；拖拽实测 Figure 1→2。 | 未做：GitHub 转公开与推送、L3、browser.mjs 旧契约、公网视觉验收 | 本地完成 |
| 0.24 | L6 四柱导航与层级 | 已完成：Plan 全面改名 Cycle（路由 `/cycle` + 旧 `/plan` 重定向、导航 CYCLE/ANALYSIS/OUTLOOK/ARCHIVE、面包屑与导入文案）；右上设置齿轮与注销删除，设置内容（导入/处方设置/登出/服务器与身体数据）并入 Archive `#account`；右上新增 TODAY/NEXT 渐变胶囊直达当日或下一场；Cycle 页 4 张阶段卡（区间/周数/场次/吨位/TOP%/相位条），Block 页 4 张周卡（吨位/场次/TOP%/强度条）；新建 `AnalysisView.vue`：Overview（KPI + SBD 目标阶梯 + Block 贡献 + Set mix）/ By lift（S/B/D 周容量与 TOP% + 周表）/ Muscle / Trend 四页签，页面由 4978px 收短；Outlook 改 Questionnaire / AI brief / Both 三页签；Archive 账户区加身体数据卡。证据：`RR/shots-0.24`，390/1280 七路由无横向溢出，build 0。 | 未做：Analysis 动作级明细（逐动作 e1RM 与完成率）、Outlook AI 流重做、Archive 云备份状态、Day 独立页、browser.mjs 旧契约、公网视觉验收 | 本地完成 |
| 0.25 | 层级可视化与四柱改名 | 已完成：TODAY/NEXT 悬停保住红底（全局 `a:hover` 曾把它刷白）；新建 `BlockWeekNav.vue`（块标签 + 该块周条）统一挂在 Cycle / Block / Week / Day 四层；Week 页七天改成 `.day-card` 卡（日期块、日字母、TOP 主项、状态点、`+` 展开），展开后是 `SESSION PLAN` 分区，展开/休息卡不再被 `undefined === undefined` 误判为整行；Block 周卡加 S/B/D 顶组%、SETS、TONNAGE、阶段说明；Analysis 的 By lift 增加主项/变式/辅项三段 `exercise register`（每动作一行：组数、周次、场次、吨位、顶重、%1RM），删掉 13 周大表；OUTLOOK→FORESIGHT、ARCHIVE→VAULT（导航与文案，路由保留），Vault 顶部加云账本/身体/账号三张状态卡，Foresight 收进单一面板并统一输入圆角；DeepSeek 公网实测 `AI_OK`（quota 19/20，返回三档 aggressive/stable/conservative）。证据：`RR/shots-0.25`，390/1280 八路由无溢出，console 0。 | 未做：Day 内动作行仍是旧卡（L3）、AI 三档前端解析未校验、云备份开关与体重历史、browser.mjs 旧契约、push | 本地完成 |
| 0.26 | 系列化 + 权限协议 + 补欠 | 已完成：四柱统一为 `CYCLE / ASSAY / ORACLE / VAULT`（`RR / 0N · 名称 — 定位`），Cycle 不动，ASSAY=本地数据分析、ORACLE=AI 计算、VAULT=云账本，路由保留 `/analysis` `/questionnaire` `/archive`；AGENTS.md 与 Skill 新增持久「权限与环境」协议（SSH 别名、服务与 env 文件、deploy.py 覆盖式写 env 会删 DEEPSEEK、密钥只走进程环境、本地 fixture 无 AI 属预期、禁止打印）；`ExerciseRows.vue` 重写为期刊式动作行（序号/名称/RPE/行内 LOG + 每段一行 TOP SET/BACK-OFF/TECH/BW，重量与 % 同行，删杠铃 UI 与卡片边框）；ASSAY 动作 register 增加计划组/实际组完成率与 Epley e1RM（`logs` 由 App 注入）；Vault 身体卡接 `/api/body-metrics` 画读数折线，活跃回顾去掉整框红边。证据：`RR/shots-0.26`，390/1280 六路由 scrollWidth=视口，console 0。 | 未做：GEAR 小片与 Sheiko 热身编排、browser.mjs 旧契约、push、ORACLE 三档前端解析 | 本地完成 |
| 0.27 | R1 会员档位 + 邀请码（服务端） | 已完成：`membership.py` 单一能力表（五档/价格/能力），邀请码只存 sha256、分档与用量/有效期/吊销、`POST /api/membership/redeem`、账户 `base_tier` + Pro `timed_tier/timed_until` 过期回落、5 设备会话、`/api/register` 必填邀请码（无效/用尽/吊销/过期一律 422 不泄露存在性）、`server/tools/invite.py`（create/list/revoke，无网页后台）、注册页邀请码输入框。证据：`RR/shots-0.27`（320/360/390/412 注册页与错误码提示），`tests/test_membership.py` 全绿。 | 未做：首页对比表、账户会员面板（0.31/0.32） | 已提交 `1b02449` |
| 0.28 | R2 每账户独立账本 + R3 档位门控 | 已完成：`upgrade_ledger` 给 journal 全表加 `account_id` 并先快照（现有数据归 owner，加每账户单活跃周期唯一索引）、`ScopedStore` + `ContextVar` 按会话解析账本、`/api/performance` `/api/geometry` readiness/body-metrics/attempts/AI/vault 七八个门控点统一 403 `required_tier`+`capability`、`web/src/membership.json` 由服务端能力表导出并有 verify 防漂移、前端 `LockedFeature` 锁定态（紧凑版单行）、空账本首登态与导入（`current` 为空时比较与确认走首次分支、成功后收表单并显示 “Cycle activated.”）。证据：`RR/shots-0.28`（free 三处门控 1280/390、ASSAY/ORACLE 锁定、plus 对照、空账本→首次导入激活），`node tests/verify.js` 退出 0（294 Python 用例、6290 断言、sabotage 仍红）；两账户 `active_cycle_id` 各自独立、free `GET /api/geometry` 403、plus 200。 | 未做：browser.mjs 旧契约（0.21 起即红基线，0.30 重写）、首页对比表与会员面板（0.31/0.32）、push/部署（按用户裁定推迟） | 已提交 |



保留优点：Dark配色、肌群图点击切换、PLAN页面。待改：

1. 主题切换按钮傻大 → 收成 L/D 小钮。
2. 顶部五导航（PLAN/ANALYSIS/ARCHIVE/OUTLOOK/SETTINGS）折成两行 → 单行。
3. Light模式换老默认ex暖纸色（#F1F0EB系）。
4. 周期条只有灰块+红当前周，增肌/转化/竞赛无区别 → 按老站分阶段分色分段标名称/周数；其他Block处同改。
5. 页面平、无数据张力（MEV/MRV不可视化、当周计划平）→ 老站结构+容量条带MEV/MAV/MRV刻度+大字层级，微调优化。
6. RECOVERY & BODY METRIC 默认折叠且上移。
7. 动作页LOG按钮傻大 → 收小。
8. GEAR/WarmUp丑；顺序改为 RECOVERY & BODY METRIC → GEAR → WarmUp。
9. 字体：老站展示体（花体好看的部分）+清晰正文体；方方正正难看的替换；候选0.10对比后定。
10. 导航：Settings收进顶栏齿轮图标，导航剩四项单行；/settings深链保留；主题L/D小钮顶栏右。
11. 视觉语言：数据页老站编辑风（大数字层级/分段边框/纸感底/展示体标题），操作表单页保留清晰卡片。
12. 落地页叙事：发布页式官网（hero大标题+功能亮点+真实截图+版本更新线+进入应用按钮）。

## 已批准交付边界（完成后移除）

- GitHub：AstraQianJin/roast-raw，私有；同名存在先检查、不覆盖。每0.10整倍数推送，其间本地新提交。推送坑：本机 git credential.helper=helper-selector 会弹 GUI 劫持认证并报 "User cancelled dialog"，需禁用弹窗 + GIT_ASKPASS 注入 GH_TOKEN。允许必要的合规开发工具（MIT/Apache/BSD、报告体积），不允许新运行时UI框架或MPL例外。
- 新服务器82.157.146.30，SSH ubuntu（roast-raw alias）、sudo；旧49.233.196.202用户2026-11-14授权完全自由（覆盖前带时间戳备份）；0.20后保留老站+首页友链指向新站。仅本地0.20验证后部署；先公网HTTP，域名/TLS后续。访问口径2026-11-14再更新（用户裁定，效仿老站）：落地/发布页公开无登录，新增注册/登录页与 MyPlan 入口；仅 journal API（/api/* 除 health/login/register/logout/session）需账户会话。owner 由环境变量 RR_ACCESS_USERNAME（默认 Astra）/RR_ACCESS_PASSWORD 注入播种（值不入仓/文档/bundle）；用户名不区分大小写、密码区分大小写（PBKDF2-SHA256），HttpOnly SameSite=Lax 会话 cookie 30 天，改密码即全员登出；~~注册开放额外账户共用同一本训记~~（2026-11-15 作废：改为邀请码分档注册+每账户独立账本，见本轮路线 R1–R3）。这是访问控制非传输加密，不宣称 HTTPS。
- AI/GitHub仅进程环境 DEEPSEEK_API_KEY/GH_TOKEN；部署AI放 /etc/roastraw.env，经systemd EnvironmentFile读取，不进源码或前端。凭据存在与用户报告不替代实际验证；不重复ACL修复。
- 部署前整库一致快照、每日备份保留30份、恢复演练；不覆盖未知服务。Agent.skill只含Skill源和脚本，不含Ref/凭据/数据/截图。

## 可选后续（不在本轮）

- 域名/TLS、访问收紧、多provider、PWA另定。
- axe-core为MPL未批准，社区webapp-testing仅候选未安装；保留CDP，不为凑工具安装。

## 待办归属（2026-11-14重排）

| 需求 | 来源与口径 | 归属 |
|---|---|---|
| 归档删除三件套：二次确认+强制导出+删logs/readiness | 交接§12.1/§14.3已确认；当前未实现，README措辞为「未实现」 | 0.13–0.14 |
| 公开落地页 + 账户登录/注册（取代原「整站共享简单口令」） | 用户2026-11-14裁定，效仿老站首页；仅 journal API 需会话，非传输加密 | 0.20随部署 |
| 审美打磨 | 用户2026-11-14反馈；已升为主线 | 0.09–0.12与0.15–0.19 |
| 0.21 UI 改版（L0/L1） | 单主题收口（删 D/切换/记忆/跟随系统）、生产补 /shots 静态挂载、首页删三按钮与花体单行品牌、右上 MyPlan、截图轮播改左右渐隐牌堆、分享卡收为按钮 | 部署后公网 /shots/* 返真实 PNG；首页 390/1280 无横向溢出 | 已完成；L2/L3 待续 |

## 维护纪律

- 用户原意与技术方向分开；拒绝建议不列已确认范围。
- 不存密钥/测试条数/容差/用量；技术错误先查证，已确认口径不反复问。
- 完成历史用git，阻塞项写真实依赖，不用「基本完成」替代验收。

## 目录治理（下一版次群待办，2026-11-15 立项，未执行）

**目标**：根目录回到「4 个可见文件 + 5 个可见目录」。现状为 5 个被跟踪文件（`AGENTS.md` `README.md` `TODO.md` `Agent.skill` `.gitignore`）与 8 个目录（`.git` `.qoder` `data` `docs` `Ref` `server` `tests` `web`），其中真正的问题是三类东西混住：文档、截图证据、打包产物。

**结论先定死（已核实，不再讨论）**：

| 对象 | 处置 | 依据 |
|---|---|---|
| `docs/` | 留仓库内，只做内部分层 + 搬走截图 | `AGENTS.md:5`、`SKILL.md:10/41`、`check_skill.py:31`、`TODO.md:3` 全指向 `docs/项目交接.md`；移出仓库则 clone 后无产品规格 |
| `tests/` | 留根目录，不并入 `data/`、不迁 RR | `verify.js` 跑 `unittest discover -s tests`；测试用 `Path(__file__).parents[1]` 推仓库根；`serve_fixture.py`/`browser.mjs`/`cdp.mjs` 是 Python+Vue 共用的证据层 |
| `.qoder/` | 留原地（隐藏目录） | `AGENTS.md:5` 入口指针、`check_skill.py:8` 硬编码该路径、`SKILL.md:104` 的打包结构以它为源 |
| `Ref/` | 留（21 文件 / 1.56 MB） | Skill 事实路由表多处指针，迁出收益不抵风险 |
| `.git` | 不删 | 43 提交 + GitHub 远程；删了丢 0.20 基线、0.27–0.29 回滚点与 diff 复核能力；222.6 MB 主因是历史里的截图 |

### 任务一 · `Agent.skill` 移出仓库

- 动作：`git rm` 根级 `Agent.skill`，文件移到 `C:\Users\Astra\Desktop\RR\builds\Agent.skill`。
- 改动 3 处：`TODO.md`（交付边界那条“Agent.skill 只含 Skill 源和脚本”改为“打包产物不入仓，见 RR/builds”）、`docs/项目交接.md:38`、`.qoder/skills/roast-raw-agent/SKILL.md:104`（打包输出路径）。

### 任务二 · `docs/shots` 移出仓库（183 张 / 33.9 MB）

- 动作：搬到 `C:\Users\Astra\Desktop\RR\shots-archive\`；**6 张 `old-ref-*.png` 必须留在仓库**（老界面审美对照证据），移到 `docs/ref-shots/`。`.gitignore` 加 `docs/shots/`。
- 改动 7 处，第 1 条是代码，必须同提交：`tests/browser.mjs:72`（输出目录改为可配置 `SHOTS_DIR`，默认 `RR/shots-<ver>`，不再硬写 `docs/shots`）、`README.md:19`、`README.md:50`、`docs/0.01提示词.md:151`、`docs/审美回炉清单.md:32`、`docs/审美调研.md:5`、`.gitignore`。
- `web/public/shots/` 的 6 张是落地页资源，**不动**；搬迁前核对两边有无重名，避免覆盖落地页图。
- 只从 HEAD 移除：历史 blob 仍在（仓库体积不会立刻降），要真瘦需重写历史，另立任务。

### 任务三 · `docs/` 内部分层

- 结构：`docs/spec/`（`项目交接.md`、`审美回炉清单.md`、`审美调研.md`）、`docs/handoffs/`（`agent-prompt-0.29-0.30.md`、`0.01提示词.md`、`0.01地基_已验证发现.md`）、`docs/licenses/`（`body-muscles-LICENSE.txt`）、`docs/ref-shots/`（6 张老样张）。
- 要改：`AGENTS.md:5`、`SKILL.md:10/41`、`check_skill.py:31` 白名单、`README.md:107`、`docs/项目交接.md:13/58/500`（自述布局）、`docs/0.01提示词.md:3/13/14/40`（或整篇冻结、文件头加“路径已迁移”注记）、`TODO.md:3/276`。
- **不能改**：`Ref/01_Current/SPEC.md:50`、`Ref/02_Stats/muscle_map.json:5/71`、`Ref/04_Legacy_Code/day_model.py:13/424`（都是老仓 `mobile/docs/...` 路径，Ref 只读）；`docs/审美调研.md:13/14/71`（同为老仓路径）；`TODO.md` 的 0.10 历史行（保留原文，不改写历史）。

### 哈希结论（已核实，搬迁不需要重算任何摘要）

`variations.digest()` 是规范化 plan JSON 的 sha256、`sourceSha256` 是上传原文件字节的 sha256、`gen_data.py:45` 对数据文件字节做 sha256、`store.py` 的口令/会话/邀请码哈希——全是内容摘要，与路径无关。只有 0.30 重新生成 plan 才会变，属预期变化。

### 执行顺序与验收

1. `chore: move Agent.skill out of repo`（3 处）；
2. `chore: move docs/shots out, keep 6 reference samples`（7 处，含 `browser.mjs`，跑一次 build + `verify.js`）；
3. `chore: split docs into spec/handoffs/licenses`（12 处，跑 `check_skill.py` + `verify.js`）。
- 每个提交只做一件事；三条命令都要退出 0；`browser.mjs` 仍是红基线，不作绿灯，但截图路径改动后至少证明它能把文件写到新目录。
- 可选后续（需单独授权，本轮不做）：`git filter-repo` 重写 43 个提交剥离截图历史，再强推远程——会改全部提交哈希，执行前须完整镜像备份。

