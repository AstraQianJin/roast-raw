# AGENTS.md

> **给接手的 Agent：只读这一份就能开工。** 全文只写四样——唤醒、红线、指针、收尾。
> 会随发版变的值（版本号、断言条数、容差值、检查 ID）**一律不写**，去 §3 按「路径 + 符号名」查。
> 分工：本文＝规矩与入口；`README.md`＝setup 与 API 细节；`docs/项目交接.md`＝最终裁决与统计口径；`docs/0.01地基_已验证发现.md`＝已验证的坑。
> **需求裁决序**：用户最新明确指令 ＞ 本文件协作与安全规则 ＞ `docs/项目交接.md` §0 ＋ `docs/0.01提示词.md` ＞ 其余文档 ＞ `Ref/` 内历史散句。代码与门禁是实测证据，不代替用户决定；有冲突先问用户。
> Token 纪律：先读 §0、§2、§7 与 `TODO.md` 当前执行区；其余按任务跳 §4 / §6、按 §3 查指针，不重复通读长交接。本文管长期规则，`TODO.md` 管需求与方向，git 管完成历史。

---

## 0 · 唤醒（每次接手先跑，上下文被压缩后必跑）

```bash
git log --oneline -5          # 我在哪、上一版收尾到哪
node tests/verify.js          # 链子是绿是红（约 1 分钟；退出码是唯一答案）
```

1. 重读 §2 红线 + §7 停手规则——这两节不能凭记忆。
2. 看 `git log` 与 `git status`：确认基线与未提交改动。
3. **没跑完 verify.js，不许产出任何「全绿 / 没坏」的结论**；基线红着时先报红，别边修边说好。
4. 碰 UI 才加跑 `npm --prefix web run build && node tests/browser.mjs`（浏览器回归吃 `web/dist`，不吃 dev server）。

## 1 · 项目与目录

力量举（SBD）「计划 + 记录 + 容量统计」Web 产品。任意周数，13 只是样本。只做 Web + 服务器存储；不做 APP / WebView / APK / iOS，不做离线与同步。

| 目录 | 角色 |
|---|---|
| `web/` | Vue 3 + Vite + Motion One；手写 CSS、不引 UI 组件库；界面纯英文 |
| `server/app/` | FastAPI + SQLite 单进程；API、存储、北京日历、fail-closed 校验 |
| `server/app/stats/` | **统计单源**：分类 / 处方 / 引擎；前端只渲染 API 结果，不算统计 |
| `server/tools/` | `gen_data.py`（v4→Raw-v1 适配器）、`synth_plan.py`（任意周数合成） |
| `data/` | 生成的 plan / movements / geometry / ranges ＋ `schema/` 现行契约 |
| `tests/` | `verify.js`（fixture＋合成＋反向）、`browser.mjs`（CDP）、Python 契约回归 |
| `docs/` | 交接、已验证发现、截图、上游许可证 |
| `Ref/` | **只读**参考库（fixture、老代码、老契约、密钥目录）；不写、不删 |

三条架构事实，违反任一即 bug：

1. **单向生成**：`Ref/` 权威源 → `gen_data.py` → `data/*.json` → `npm run build` → `web/dist` → uvicorn 静态服务。逆着手改任何一环都不是捷径。
2. **单源**：统计只在 `server/app/stats/`；日历只在 `calendar.py`；契约只在 `data/schema/`；令牌只在 `web/src/tokens.css`。同一事实的第二份手抄副本就是待修缺陷。
3. **只读边界**：`Ref/` 不写一字；老项目 `Roast PowerLifting` 只读回查（仅当 `Ref/` 缺文件），不改、不 git、不部署；老服务器 `49.233.196.202` 永不动。

### 1.1 · 英文基准

界面、按钮、空态、错误、截图文字以英文为唯一基准；内部文档（本文、README、docs/）可用中文。标识符 / 注释 / 提交信息用英文。不许先写中文再硬翻。

### 1.2 · 栈已定，开工先找轮子

Vue3 / Vite / Motion One / FastAPI / SQLite 已定，不更换；不引 React / ECharts / Chart.js 等。引新库前先搜，并报三件事：能离线内联、许可证可见（MIT / Apache / BSD）、体积算账；判据记进提交信息或回执。现成例子：人体路径复用 body-muscles 1.0.0（Apache-2.0）坐标，不引其 React 组件，见 `docs/body-muscles-LICENSE.txt`。

## 2 · 红线（全文以 docs/项目交接.md §0 ＋ 0.01提示词.md 裁决）

| # | 规矩 | 为什么 |
|---|---|---|
| 1 | **只做 Web**：不做 APP / WebView / APK / iOS，不做离线缓存与同步服务 | 产品边界 |
| 2 | **0.01 不部署**；部署窗口只 0.05 / 0.10，只到新服务器 `82.157.146.30`（先 HTTP）；`项目交接.md` 与 `ACCESS.md` 里「按 0.01 部署」散句无效 | §0 最终裁决 |
| 3 | **密钥**：`Ref/07_Permissions/RR.pem`、`DeepSeek.key`、`Github.key` 只读；AI/GitHub 用进程环境变量，SSH 用密钥文件；不打印、不进 git/前端/构建产物，不改权限绕过拒绝 | 泄露即事故 |
| 4 | **fail-closed 导入**：失败即拒绝＋逐字段报错（文件/周/日/动作/字段/期望值）；不静默修复；v4 仅经适配器 | 静默修复＝错数据 |
| 5 | **不编辑计划**：导入新计划＝换数据；不做计划编辑 UI | 计划单源 |
| 6 | **固定日历不滑期**：时区 Asia/Shanghai；没练成标未完成 | 日历即契约 |
| 7 | **任意周数**：不写死 13；8 / 17 周合成必须过 | 13 只是样本 |
| 8 | **断言必须能红**：不放宽容差、不删断言、不把 sabotage 改恒真；反向验证长期保留 | 恒真断言＝没有断言 |
| 9 | **免登录单人**：全站单份数据；写冲突 last-write-wins ＋ append-only  journal | 0.01 边界 |
| 10 | **视觉基准**：老站是基准不是灵感；不卡片堆、不把统计藏二级标签、不用 16 行热力表替代人体图；不用老 APP 截图 | 第一验收画面＝人体图 |

**不主动做**：未经批准的部署、非 §7 里程碑 push / 加远程、删 `Ref/` 或 `data/` 源、放宽回归判定、打印密钥、`rm -rf`。里程碑推送也必须有已授权的明确目标。

## 3 · 数字去哪查

**唯一去处是「路径 + 符号名」**。没 shell 的宿主用读文件 / 搜索按同一路径找，结论等价。

| 想知道 | 去处（路径 + 符号名） |
|---|---|
| 当前版本 | `web/package.json` 的 `version`（SemVer 的 patch 对应产品百分位版次）；显示由 `web/src/App.vue` 的 `releaseVersion` 派生 |
| 现在全绿吗 | `tests/verify.js` 实际退出码 |
| 有哪些回归 | `tests/verify.js`（fixture / precision / library / synthesis / sabotage ＋ unittest）、`tests/browser.mjs` |
| 统计口径 / 舍入 / 分类 | `server/app/stats/engine.py` 的 `analyze` / `r1`；`classify.py`；`prescription.py` |
| 北京日历 / 未完成 | `server/app/calendar.py` 的 `calendar_state` |
| 表 / LWW / journal / 版本闸门 | `server/app/store.py` 的 `initialize` |
| fail-closed 校验 / 测试日 | `server/app/validation.py` 的 `validate_legacy` / `validate_plan` / `test_dates` |
| 适配器 / 合成 | `server/tools/gen_data.py` 的 `adapt`；`server/tools/synth_plan.py` 的 `build` |
| 现行契约 | `data/schema/RPL-Raw-v1.json`、`RPL-Review-v1.json` |
| fixture（带 BOM，utf-8-sig） | `Ref/02_Stats/capData.json`、`mmData.json`；口径 `Ref/04_Legacy_Code/day_model.py` |
| 几何 / 动作库 / 系数 | `data/muscle_geo.json`、`data/movements.json`；源 `Ref/02_Stats/muscle_map.json`、`coefficient_matrix.csv` |
| 令牌 / 主题 / 导航深链 | `web/src/tokens.css`；`web/src/App.vue` |
| 人体图 / 色阶 / P-S | `web/src/components/MuscleMap.vue`；许可证 `docs/body-muscles-LICENSE.txt` |
| 密钥 / 服务器步骤 / 环境变量名 | `Ref/07_Permissions/ACCESS.md`；`DEEPSEEK_API_KEY` |
| 最终裁决 / 统计口径 / 路线 | `docs/项目交接.md` §0 / §4 / §20；坑 `docs/0.01地基_已验证发现.md` |
| setup / API / 范围细节 | `README.md` |
| 用户想法 / 具体方向 / 待决定 | 根 `TODO.md`；只留未完成项，完成证据查 git |
| 交付截图 | `docs/shots/`（只放本项目 UI） |

**只准查不准记**：版本号、断言条数、容差值（在 `verify.js`）、某文件是否在仓。它们错了不会报错，只会静默骗过你。

## 4 · 任务 → 首改 → 必跑 → 收尾证据

| 任务 | 首改 | 必跑 | 收尾必交 |
|---|---|---|---|
| UI / 交互 | `web/src/*` | `npm --prefix web run build` → `verify.js` ＋ `browser.mjs` | 退出码 ＋ 320/360/390/412 × 浅/深截图 ＋ 逐位置问题清单 |
| 统计 | `server/app/stats/*` | `verify.js` | 退出码 ＋ 分层 max diff ＋ sabotage 仍红 |
| 数据 / 适配器 | `server/tools/gen_data.py`（不手改 `data/*.json`） | `gen_data.py` → `verify.js` | 动作库完整性 / 排除项 / tonnage 实测值 |
| API / 存储 | `server/app/main.py`、`store.py` | `verify.js`（含真实重启回读） | 退出码 |
| 契约 | `data/schema/*` | `verify.js`（test_import） | 逐字段报错样例 ＋ 往返 |
| 只写文档 | 文档本身 | 不需跑 | 只写指针，不写死数字 |

视觉收尾：截图是证据，不是审美签收；真人验收按 §0 排在 0.10 及以后大版本，Agent 只准备证据。

## 5 · 命令

```bash
node tests/verify.js                     # 统计/契约/回归总门禁（约 1 分钟）
npm --prefix web run build               # 浏览器回归与单进程服务都吃 dist
node tests/browser.mjs                   # CDP 验收＋截图（自起隔离端口与临时库）
server/.venv/Scripts/python.exe server/tools/gen_data.py          # 重生成数据
server/.venv/Scripts/python.exe server/tools/synth_plan.py 8      # 任意周数合成到 stdout
server/.venv/Scripts/python.exe -m uvicorn server.app.main:app --host 127.0.0.1 --port 8000
npm --prefix web run dev                 # 开发态 5173，代理 /api
```

完整 setup（venv / pip 镜像 / npm ci）见 `README.md`，不在此抄。
提交身份：`git -c user.name=Astra -c user.email=astra@roastraw.local commit …`（身份不写 config；密钥目录任何新文件自动被 `Ref/07_Permissions/*` 忽略，勿改该规则）。

## 6 · 症状 → 对策（拿报错原文搜这张表，别通读）

| 症状 / 关键词 | 去哪看 |
|---|---|
| pip 超时 / pypi 不可达 | 用 aliyun 镜像，见 `README.md` Local setup |
| fixture 乱码 / 键缺失 | BOM：用 `utf-8-sig` 读 |
| 截图宽度被 clamp 到约 504 | 用 CDP `Emulation.setDeviceMetricsOverride`，不要 `--window-size` |
| 找不到 chrome / python | `CHROME_PATH` / `RR_PYTHON` 环境变量 |
| 改了 UI 但回归看到旧页 | `browser.mjs` 吃 `web/dist`，先 build |
| 16 叶周值恰差 0.1 | 舍入约定差异，不是 bug；容差在 `verify.js` |
| `format: date` 不校验 | 缺 `jsonschema[format-nongpl]` |
| 读密钥 EPERM | 只证实当前进程不可读，不据此推断 ACL 或平台原因；按批准的注入方式执行，不重试绕过、不改权限、不打印 |
| 端口 / 库被占 | 回归自起临时端口；手动跑换端口或 `RR_DB_PATH` |
| 「按 0.01 部署」字样 | 无效散句，按 §0 裁决：只 0.05 / 0.10 |
| 重生成想覆盖活周期 | `gen_data.py` 只种空库；换 `RR_DB_PATH` 预览 |

## 7 · 歧义、版本与远程

**遇到歧义优先问用户**：涉及产品行为、统计含义、需求冲突、信息架构、优先级或范围时，先给简短选项、推荐与代价，得到答复后再执行该项；可继续无依赖的明确任务，不用猜测替用户拍板。局部实现细节在已确认目标内取最小可逆方案；技术错误先查证，不把每个定位问题都甩给用户。

**每推进 0.01 必更新根 `TODO.md`**：保留用户想法与具体执行方向的区别；新增需求当天录入，完成且有证据后从活动区删除；未完成/待裁定保留并注明依赖。完成历史用 git，不另建完成台账；版本号只改 `web/package.json` 并同步 lockfile。

**每到 0.10 的整倍数才推 git 远程**（例如 0.10、0.20、0.30）：其间只做本地新提交；先完成回归、TODO 更新、暂存内容与密钥检查，再向已明确授权的项目远程推送。该节奏不等于授权自建公开仓库、改远程地址或强推；首次远程的仓库名/归属/可见性、授权或凭据缺失时先问用户，未推如实标记，不跳过、不假报。

**危险操作须确认**：部署、加/改远程、非里程碑 push、删参考/数据源、破坏性 git、`rm -rf`；不得泄露密钥、绕过权限拒绝或放松回归判定。只报三行：卡在哪、试过什么、要批准哪一步。
同一处失败超过三次换方案或交接会话，写三行：已试什么 / 错在哪 / 下一步。

## 8 · 能力受限与并行

做不到就说做不到：**弱宿主让结论变少，不让结论变假**。没 shell → 命令原文列给人跑，标「这一层未验证」；没浏览器 → 只做静态与断言层，明说未真浏览器验证；子智能体按文件所有权切活，同一文件同一时刻一个写者，**子智能体不得自触发生成链或门禁**，由主控汇总串行跑。「已修好」不算，`git diff` 与退出码才算；模型自评的「通过」不作数。

## 9 · 回执（给人读）

问答、进度、短确认一律素文，不套骨架。结论类消息用五条骨架，顺序固定，一行一件事：

1. 状态句：`✅` 做成 / `❌` 没做成 / `📋` 未执行的计划——一句话封顶。
2. `📊` 证据：退出码、PASS/FAIL、sha 前缀、实测值；取不到写「未取」，不写感受。
3. `🧩` 做法 / 影响：改了什么、动到哪屏；计划写步骤＋产出物。
4. `⚠️` 边界：没做的、做不到的；**空着等于说假话**。
5. `➡️` 下一步给归属 · `❓` 待你定：下一步分 🟢 Agent 可直接跑 / 🟡 需你裁定 / 🔴 需真人签收；无需拍板显式写「无需你决定」。

约束：emoji 只做状态标记（白名单 ✅ ❌ 📊 🧩 ⚠️ ➡️ ❓ 📋 🎯 ⏳ 🔴），单条 ≤8 个、不叠用、表格内与数字旁不放；完成块与计划块同消息时中间独占一行 `---`，不混写；不许「基本完成 / 应该没问题」这类软化词。

## 10 · 维护本文件

**只有这几种情况改本文**：目录 / 主线迁移、出现新破坏面、换构建或门禁入口、权威源改名（只改指针）、出现新纯转发文件或失效指针。
**不写**：版本号、条数、项数、检查 ID、日期、进度、待办、模型排名。判据一句：**「下次发版会变吗？」** 会变 → 写指针。
若宿主只认别的文件名（`CLAUDE.md` 等）：优先直接改名；需同时识别多名用软链；软链不可用才允许转发文件并登记进 `docs/` 台账，宿主不再需要时立即删除。