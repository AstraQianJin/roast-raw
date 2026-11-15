# 接手指令 · Roast Raw 0.29 收尾 / 0.30

> 版本 v2（2026-11-15）。上一版写于 0.29 开工前，已被本轮安全修复与目录变动部分作废；以本文件为准。
> 用法：整段复制给新 Agent，作为它的第一条消息。

---

你是 Roast Raw 项目的执行 Agent。先读文件，再动手；不要凭记忆写任何路径、版本号、断言数。

## 一、身份与边界

- 项目是**单人力量举训练账本**，Web only：Vue 3 + Vite + Motion One 前端，FastAPI + SQLite 后端。不做 Android、不做离线缓存、不做同步服务。
- 界面文案**英文**，与用户对话**简体中文**，回执按 `AGENTS.md` 的五字段（RESULT / EVIDENCE / SCOPE / BOUNDARY / NEXT）。
- 本轮**不 push、不部署**（用户 2026-11-15 裁定）；「停即部署预览」条款暂停。每完成一个 0.01 就本地提交一次，证据用本地构建 + 本地截图，BOUNDARY 写「未部署」。
- 提交命令固定：`git -c user.name=Astra -c user.email=astra@local commit -m "..."`（仓库无 git 身份）。禁止 `--amend`、`--no-verify`、改 git config。
- `Ref/` 与两个老项目只读；不手改 `data/plan.json`、不手改 `web/dist/`；不放宽容差、不删断言、不中和 sabotage。

## 二、必读（按顺序，只读需要的部分）

1. `C:\Users\Astra\Desktop\Roast Raw\AGENTS.md` — 证据契约、环境事实、禁区。
2. `C:\Users\Astra\Desktop\Roast Raw\TODO.md` — 执行队列、0.29/0.30 施工详单、已确认决策、未决问题。
3. `C:\Users\Astra\Desktop\RR\skills\roast-raw-agent\SKILL.md` — 项目流程与事实路由表（它不在仓库里，是 Agent 区的技能库）。
4. `C:\Users\Astra\Desktop\Roast Raw\docs\项目交接.md` — 只在需要产品口径时按章节读，全文 83 KB，不要整篇吞。

## 三、先建立基线（不许跳过）

```sh
cd "C:\Users\Astra\Desktop\Roast Raw"
git status --short
git log --oneline -5
node tests/verify.js
```

- 期望：工作树干净；最近提交 `41c6a00`；`verify.js` exit 0。
- 若 `verify.js` 非 0，**先如实报红基线**，不要边改边修。
- `tests/browser.mjs` 自 0.21 起就是红基线（旧主题切换与三输入注册页断言失效），**不得**当作绿灯证据；它在 0.35 重写。
- 版本唯一来源 `web/package.json`（现 `0.0.28`）；`web/src/App.vue` 的 `releaseVersion` 由同一字段派生。

## 四、当前进度（事实，不是计划）

- 0.27（邀请码/五档）与 0.28（每账户账本 + 档位门控）已提交。
- 0.29 已完成三项：T2 空口令 fail-closed（无口令 `create_app()` 抛错，夹具走 `RR_ALLOW_OPEN_FIXTURE=1`）、T1 `_scoped` 有界 LRU（64 视图 / 1800 秒 TTL / 锁 / 视图不共享字典，`tests/test_cache.py` 8 条）、P0-03a 六处首页假宣传文案。
- 0.29 **未完成**：P0-01 刷新实测、P0-02 首页数字同源。
- 补充事实：`rplref` 已于 2026-11-15 瘦身 2243.6 MB（删除 mirror 下 archive/ref 重复副本与派生缓存），删除依据与恢复路径在 `RR\ref-projects\rplref\_repo\MIRROR_SLIMMED.md`。

## 五、任务一 · P0-01 刷新不闪 404（先实测，再决定改不改）

- 现状：`web/src/App.vue` 模板次序为 `loading` → 请求错误 → 空账本 → `!plan` → `!validRoute`。0.28 调过次序但**从未实测**，所以先测。
- 判据（用户定稿，不许软化）：3M 带宽（≈375 000 B/s、latency 40ms）连续刷新 10 次；**不判「立即」时点**（SPA 首屏 JS 未到之前空正文正常），判 **200ms、800ms、最终加载完成**；禁词 `NOT IN THIS PLAN`、`404`、`NO SESSION`、`Return to the cycle`；**最终态断言：30 秒内必须出现计划内容，不得停在骨架**；不设单次骨架停留阈值；空白正文判失败。
- 证据写到 `C:\Users\Astra\Desktop\RR\shots\0.29\p0-01-refresh.json`（10 次 × 3 时点的原文与命中标记）。
- 若失败：把缺陷连同实测数据记进 TODO 的 0.38 审查清单，**不要**因此推迟开周日期（起点仍是 2026-11-23）。
- 若仍闪才动代码：骨架块提到 `!plan` 之前，固定高度、`role="status"`、禁 shimmer；`todayCtaLabel` 在 `plan` 为空时输出 `·`。

## 六、任务二 · P0-02 首页数字同源

- 新增 `server/tools/landing_facts.py`：读 `data/plan.json`，取**一个样例课日**（默认 `W01 · DAY A`），写紧凑 JSON 到 `web/src/landing-facts.json`。不许把整份 plan 塞进前端 bundle（gzip 增量必须 < 2 KB）。
- 字段：`planId, startDate, week, day, date, label, lifts[{lift, movement, top_kg, pct, sets, reps}], set_count, day_total_kg, cycle_total_kg, tonnage_basis`。
- 口径：`day_total_kg` 是该日总和且**不含热身**；`cycle_total_kg` 必须等于 `meta.cycleTonnageKg`；`pct` = 顶重 / 该动作训练最大值 × 100，取 `meta.anchors` 同源值，找不到同源值就**删掉该字段**并隐藏前端百分比。
- 三处消费，共用同一份 facts：`WelcomeView.vue` hero（徽标 + 三张卡 + `4,041 kg / 17 SETS`）、分享卡同三项、`App.vue` NEXT 药丸（`todayCtaLabel` / `todayCtaDate`）。删掉全部字面值，不许手写。
- verify 新增两条断言：① 重跑生成器与产物逐字节相等；② 从 `data/plan.json` **独立复算** `day_total_kg`、`set_count`、`cycle_total_kg`（不调用被测函数）。
- 收尾再 grep 一次假宣传词：`No account|Zero account|CSV|XLSX|Chinese UI|rest timer|Phone app`。

## 七、任务三 · 0.30 计划未开始态

1. **日期重算**：目标 `startDate 2026-11-23`、`endDate 2027-02-21`、测试日 `2027-02-20`；`planId` 若改则 `rpl-raw-2026-11-23`。只走 `server/tools/gen_data.py` → `synth_plan.py`，禁止手改 JSON；`meta.motto` 里写死的测试日期改由生成器模板填充。相对时长不变（到测试 89 天、到结束 90 天），`cycleTonnageKg 139568.0` 作零差基线。
2. **planId 变更必须迁移**：旧库已播种 `rpl-raw-2026-11-16` → 归档旧周期（保留计划与日志、可回读）+ 播种新周期；**不许原地改日期**。
3. **断言强度不降**：锚点日期至少一条断言直接读 `plan.meta.startDate`；「必须落在测试周」改按周次相对判断；`tests/browser.mjs` 填问卷的日期也从 plan 读。
4. **未开始态页面**（`web/src/components/CyclePrestart.vue`，挂 `/today` 顶部）：倒计时环（目标日取 `plan.meta.startDate`，不写死）+ 首次课预习 + 热身与活动度 + 恢复基线。恢复基线**只给采样提示、不给数值门槛**，缺数据写 `Not sampled`，不写 0。
5. 硬约束：纯客户端派生，未开始态**不发任何 `/api/ai/*` 请求**（用 CDP 网络日志作证）；免费档可见；`/api/performance`、`/api/geometry`、`/api/vault` 仍锁。
6. 验收：320/390/1280 三宽截图，有数据/空数据各一张，日期与 plan 完全一致。

## 八、验收与证据

```sh
node tests/verify.js          # 必须 exit 0
npm --prefix web run build    # 必须 exit 0
server/.venv/Scripts/python.exe C:\Users\Astra\Desktop\RR\skills\roast-raw-agent\scripts\check_skill.py --root .
```

- 截图与 JSON 一律落 `C:\Users\Astra\Desktop\RR\shots\0.29\`，0.30 落 `RR\shots\0.30\`。
- 回执五段，一段一行，写完自查：BOUNDARY 不许空；不许把「本地构建成功」说成「已上线」；不许引用记忆里的用例数。

## 九、禁做清单

- 不 push、不部署、不改共享服务器、不覆盖远程仓库。
- 不打印或提交任何密钥、cookie、`/etc/roast-raw.env`、SQLite 库文件。
- 不动 `Ref/`（除既有的 `Ref/07_Permissions/ACCESS.md` 那一处授权例外）。
- 不运行老项目的构建/部署流程；只读其源码做审美或契约溯源。
- 不擅自把新需求塞进当前版本——新需求写进 TODO 队列。
- 不在没有实测的情况下宣称 P0-01 已修；本项目已经因为「改了但没测」吃过一次亏。

## 十、目录事实（省得重新找）

| 要找什么 | 位置 |
|---|---|
| 项目仓库 | `C:\Users\Astra\Desktop\Roast Raw`（git `master`） |
| Agent 区（技能库/打包件/截图） | `C:\Users\Astra\Desktop\RR`（非 git） |
| 技能库与自检脚本 | `RR\skills\roast-raw-agent\`（`SKILL.md` + `scripts\check_skill.py`） |
| 打包件 | `RR\builds\Agent.skill` |
| 旧 App（原身，只读） | `C:\Users\Astra\Desktop\RR\ref-projects\roast-powerlifting` |
| 旧仓索引与快照（只读） | `C:\Users\Astra\Desktop\RR\ref-projects\rplref`（`_INDEX.md` / `_MANIFEST.md` / `_snapshots`） |
| 权威开发详单（外部 Agent 产出） | `C:\Users\Astra\Downloads\roast-raw-dev-brief-2026-11-15-consolidated.md` |
| 本轮路线与决策 | `TODO.md` §1–§6 |

目录治理（`RR\ref-projects\`、`RR\shots\`、`RR\Archive` 等）方案已写进 `TODO.md` §7，**尚未执行**；执行前先看那一节的三点默认值。
