# TODO — 想法与执行方向

> 只保留未完成工作及依赖；当前版本查 web/package.json，完成历史查 git。长期协作见 AGENTS.md 与项目 Skill，产品口径见 docs/项目交接.md「本轮确认」。每推进0.01更新；有证据才删除活动项，不复制完成台账。

## 当前执行

- 已批准顺序（2026-11-14改）：本地每0.01新提交、跳过push；0.09–0.12审美回炉、0.13–0.14 AI+待办、0.15–0.19综合审查打磨、0.20才部署新服务器并推私有远程；0.20部署后用户真环境验收，问题回本地修再更新。0.09–0.12每节点给用户简洁预览（截图/清单），减少打扰、不反复问。
- 2026-11-14追加裁定：0.13起一次连续推进到0.20；0.15–0.19全自主（独立审查+修复不逐轮等用户反馈），用户只在0.20部署后真环境验收一次性给反馈。共享口令已由用户指定并设为本机用户环境变量 RR_ACCESS_PASSWORD（值不入仓/不入文档/不入bundle）。

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
- 新服务器82.157.146.30，SSH ubuntu（roast-raw alias）、sudo；旧49.233.196.202用户2026-11-14授权完全自由（覆盖前带时间戳备份）；0.20后保留老站+首页友链指向新站。仅本地0.20验证后部署；先公网HTTP，域名/TLS后续。访问口径2026-11-14再更新（用户裁定，效仿老站）：落地/发布页公开无登录，新增注册/登录页与 MyPlan 入口；仅 journal API（/api/* 除 health/login/register/logout/session）需账户会话。owner 由环境变量 RR_ACCESS_USERNAME（默认 Astra）/RR_ACCESS_PASSWORD 注入播种（值不入仓/文档/bundle）；用户名不区分大小写、密码区分大小写（PBKDF2-SHA256），HttpOnly SameSite=Lax 会话 cookie 30 天，改密码即全员登出；注册开放额外账户共用同一本训记。这是访问控制非传输加密，不宣称 HTTPS。
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
