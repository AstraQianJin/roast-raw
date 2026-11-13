# Ref — 参考与权限（只读）

这个目录是下一个 Agent 的**只读参考区**，不是生成物，不参与构建。
老项目 `c:\Users\Astra\Desktop\Roast PowerLifting` 仍然只读；这里只放本轮确认要交接的副本。

## 子目录

| 目录 | 内容 | 用法 |
|---|---|---|
| `01_Current/` | `SPEC.md`、`plan_12w5_sample.json`（当前 13 周计划样本） | 先读 SPEC；计划样本只作字段参考，**13 周不是常量**。 |
| `02_Stats/` | `muscle_map.json`、`muscle_geo.json`、`coefficient_matrix.csv`、`capData.json`、`mmData.json`、`validate_stats.py` | 统计口径与 16 叶/六组系数；fixture 用于逐周断言。 |
| `03_Contracts/` | `RPL-Plan-v4.json`、`RPL-JTS-v1.json`、`RPL-Gear-v2.json` | 老契约参考；新计划 JSON 以 RPL-Plan 升级版为基础。 |
| `04_Legacy_Code/` | `day_model.py`、`render_day.py` | 老站统计与版面的实现参考，**不要直接跑**。 |
| `05_Archive/` | `plan_site.html`、`plan_text.txt`、`today-390-dark.png` | 老 `/plan/` 与老 Today 的快照；只参考结构/层级，不参考老 APP 截图。 |
| `06_Publish_Reference/` | `hub_index.html`、`friends.json` | 老发布页结构与 friends；只放新 Web 截图。 |
| `07_Permissions/` | `RR.pem`、`ACCESS.md` | 新服务器密钥与访问步骤；**不要打印/提交密钥内容**。 |

## 命名规则

- 目录：`NN_英文短名`，NN 两位，按阅读顺序。
- 文件：`snake_case` 或契约原名（`RPL-Plan-v4.json`），不要出现 `final/new/old2` 这类版本词。
- 新生成物放 `Build/ Data/ Release/`，不要往 `Ref/` 写。
- 老项目文件名形如 `*_ProMax.xlsx` 是历史快照，不要顺手改名。

## 硬规矩

1. `07_Permissions/RR.pem` 只在本机使用；不进 git、不进构建产物、不发聊天。
2. 不部署、不 SSH、不动老项目/老服务器，除非用户明确批准。
3. 老站的截图/HTML 只作版面参考；新 Web 截图才进发布页。
4. 周数、deload、test 都由计划 JSON 决定；不要在代码里写死 13。
