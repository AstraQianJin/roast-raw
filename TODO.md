# TODO — 想法与执行方向

> 只保留未完成工作及依赖；当前版本查 web/package.json，完成历史查 git。长期协作见 AGENTS.md 与项目 Skill，产品口径见 docs/项目交接.md「本轮确认」。每推进0.01更新；有证据才删除活动项，不复制完成台账。

## 当前执行

- 已批准顺序（2026-11-14改）：本地每0.01新提交、跳过push；0.09–0.12审美回炉、0.13–0.14 AI+待办、0.15–0.19综合审查打磨、0.20才部署新服务器并推私有远程；0.20部署后用户真环境验收，问题回本地修再更新。0.09–0.12每节点给用户简洁预览（截图/清单），减少打扰、不反复问。
- 2026-11-14追加裁定：0.13起一次连续推进到0.20；0.15–0.19全自主（独立审查+修复不逐轮等用户反馈），用户只在0.20部署后真环境验收一次性给反馈。共享口令已由用户指定并设为本机用户环境变量 RR_ACCESS_PASSWORD（值不入仓/不入文档/不入bundle）。
- **2026-11-15 用户裁定（本轮，覆盖上两条中冲突部分）**：执行下方「本轮路线 0.27–0.34」。①注册开放但必须持邀请码，邀请码分档（Free/Lite/Plus/Pro/Ultra），成员权限与定价照老站 ExDark（http://49.233.196.202/ ，本地参照 Ref/06_Publish_Reference/hub_index.html #license）；②首页做老站同款会员对比（规格见 R6）；③Android、iOS 均显示 Coming Soon；④完成率按审查推荐口径（R5）；⑤**发布与部署推迟到本轮全部修完**：本轮内不 push、不正式部署、**也暂停 AGENTS「停即部署预览」**，每次停止仍须本地提交，证据改用本地构建+本地截图，BOUNDARY 写明“未部署”；全部完成后由用户另行下令才进入 0.34 发布。

## 本轮路线 0.27–0.34（2026-11-15 用户裁定，按序执行）

> 依据：老站线上 http://49.233.196.202/ `#license`（2026-11-15 抓取）与本地 `Ref/06_Publish_Reference/hub_index.html`，两者冲突以线上为准。本节写的是范围与验收，实现细节在已确认目标内可自决；标「ASK」的点没定，按括号里的默认值做，在回执 BOUNDARY 里写明。每版 = 本地提交 + 本地构建 + 本地截图，不 push、不部署。

| 版次 | 条目 | 范围 | 验收 |
|---|---|---|---|
| 0.27 | R1 会员档位 + 邀请码（服务端） | 见 R1 | 单测：五档兑换 / 过期降档 / 重复使用 / 吊销 / 无码注册拒绝；`node tests/verify.js` 退出码 0 |
| 0.28 | R2 每账户独立账本 + R3 档位门控 | 见 R2、R3 | 两账户互相看不到对方数据；每个门控接口都有「低档 403 / 达标 200」成对用例；迁移前快照存在，旧库升级往返零差 |
| 0.29 | R4 补 L3 欠账 | GEAR 小片与单侧配片、Sheiko 热身（只给主项）、比赛三盏裁判灯、测试周四组 UI（`RR/RoastRaw-UI改版决策.md` W9/W10/T1–T6；T6 5km 字段沿用默认） | 四宽截图 + 每个交互一次实点（灯 2 白=GOOD、2 红=MISS） |
| 0.30 | R5 完成率口径 + 重写 `tests/browser.mjs` | 见 R5；browser.mjs 按单主题、四柱路由、新首页重写，不删能红的断言，只替换已失效的旧契约 | `verify.js` 与 `browser.mjs` 都退出码 0；对每个改写断言做一次故意破坏，证明能变红 |
| 0.31 | R6 首页会员对比 + 老站效果补齐 | 见 R6、R7 | 320/360/390/412/1280 无横向溢出；折叠/展开、粘性表头、CNY/USD 切换、减少动效模式各截一张 |
| 0.32 | R8 账户内会员面板 | 见 R8 | 兑换升档、Pro 续期、过期回落都在界面上走通并截图 |
| 0.33 | 独立审查 + 修复 | 由没写代码的会话审 0.27–0.32；问题要写「哪页 · 哪个元素 · 什么问题」；修完全量回归 | 审查清单逐条关闭；verify + browser + build 全部退出码 0 |
| 0.34 | 发布（只在用户另行下令后） | 部署新服务器 + 推送私有远程；部署前从服务器取回 `DEEPSEEK_API_KEY` 放进进程环境，部署后 `/api/ai/status` 必须 `configured: true`；首页友链指回老站 | `deploy.py` 访问契约全 PASS + 公网探测 |

### R1 · 会员档位与邀请码（服务端，0.27）

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
