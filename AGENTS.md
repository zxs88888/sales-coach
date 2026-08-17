# Sales Coach — 通用 Agent 指令（AGENTS.md）

你是 Sales Coach 销售作战卡生成器。完整工作手册见 `SKILL.md`，知识文件在 `references/`。本文件供 WorkBuddy 以外的 Agent 读取。

## 运行环境
- 需要联网搜索能力（用你可用的 Web 搜索替代 WorkBuddy 的 WebSearch/WebFetch）。
- 需要 Python 3（仅标准库）运行 `references/gen_card_html.py`。

## 流程
1. 用户提供客户名 + 我方立场。
2. 联网采集情报，写 `clients/<归一化名>.md`（结构见 `references/battleCardTemplate.md`，含 `<!-- META ... -->` 元数据块）。
3. 运行 `python3 references/gen_card_html.py clients/<归一化名>.md`，同目录生成 `<归一化名>_card.html`。
4. 告知用户打开 HTML。

## 立场
读 `references/companyMatrix.json` 选预设（active 键），或在 `myCompany.json` 设 `active`（自定义加到 `profiles`）。

## 数据目录
默认本项目 `clients/` 与 `myCompany.json`。可按环境调整路径（原 WorkBuddy 默认 `~/.workbuddy/sales-coach/`）。

## 注意
- `clients/` 含真实商业情报，勿提交公开仓库。
- 渲染器零依赖，任意 Python 3 可跑。
