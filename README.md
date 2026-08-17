# Sales Coach 销售作战卡生成器

把客户/公司情报采集与可视化作战卡生成，封装成一个可复用的 skill。联网搜索客户背景，生成带 META 仪表盘、决策链、战略时间线、来源汇总的 HTML 作战卡，供销售见客户前快速掌握全局。

## 安装

### WorkBuddy
把本仓库整体放到 `~/.workbuddy/skills/sales-coach/`（目录名即 skill 名）。刷新后，对话里说"分析 XX 客户""给我 YY 的作战卡"即可触发。

### 其他 Agent（Cursor / Codex / 通用）
1. 把仓库内容放进项目（如 `./sales-coach/`）。
2. 将 `AGENTS.md` 并入你的 Agent 指令文件：
   - Cursor：`.cursorrules` 或 `.cursor/rules/sales-coach.mdc`
   - Codex：`AGENTS.md` / `codex.md`
   - 通用：项目根 `AGENTS.md`（多数 Agent 认）
3. `references/` 知识文件留在同目录作参考。

## 使用
1. 对话给出客户名 + 我方立场（如"以千问办公立场分析小红书"）。
2. Agent 联网采集 → 写 `clients/<客户>.md`。
3. 运行 `python3 references/gen_card_html.py clients/<客户>.md` → 生成 `_card.html`。
4. 浏览器打开 HTML。

## 立场配置
仓库已附带默认 `myCompany.json`，内容为 `{ "active": "qianwen-office" }`，开箱即用。切换立场直接编辑该文件把 `active` 改成 `companyMatrix.json` 里的预设键（tencent / aliyun / huawei / aws / azure / moonshot / zhipu / baichuan / qianwen-office）；自定义立场加到 `profiles`，例如：
```json
{ "active": "my-co", "profiles": { "my-co": { "companyName": "我的公司", "products": [...], "strengths": [...], "competitors": [...], "avoidPhrases": [...], "defaultPositioning": "..." } } }
```
也可在对话里直接说"以千问办公立场分析 XX"，无需改文件。

## 目录结构
```
sales-coach/
├── SKILL.md                 # 完整工作手册（WorkBuddy 原生识别）
├── AGENTS.md                # 跨 Agent 通用指令
├── README.md
└── references/
    ├── gen_card_html.py     # 渲染器（纯标准库，零依赖）
    ├── companyMatrix.json   # 立场档案
    ├── battleCardTemplate.md
    ├── searchQueries.md
    └── stagePlaybooks.md
```

## 数据目录
- **WorkBuddy**：`~/.workbuddy/sales-coach/`（含 `clients/<客户>.md` 与 `myCompany.json`）。
- **其他平台（千问办公 / QoderWork / Cursor / Codex）**：用**项目相对路径**，即本仓库下的 `clients/` 与 `myCompany.json`。客户档案与立场文件随项目走，便于团队共享同一份配置。

## 已验证平台（含千问办公 / QoderWork）
两个平台**均支持「加载 AGENTS.md 作为自定义指令」+「运行 Python 脚本」**，可完整使用（含可视化 HTML 作战卡）：
- **QoderWork**（阿里 AI 编程 IDE）：把 `AGENTS.md` 并入项目指令 → 终端跑 `python3 references/gen_card_html.py clients/<客户>.md` → 生成的 `_card.html` 在 IDE 预览/浏览器打开。
- **千问办公**（钉钉/千问办公 AI 套件）：把 `AGENTS.md` 设为自定义智能体指令 → 终端/代码节点跑同上命令 → 生成后把 HTML 路径发用户，由用户浏览器打开。
- 工具差异：原 `WebSearch`/`WebFetch`/`present_files` 为 WorkBuddy 专用；其他平台用其内置搜索+代码执行替代，并改用「告知文件路径」方式展示 HTML（详见 SKILL.md Platform Support 段）。

## 贡献
Fork → 改 → 提 PR。常见优化：扩充 `companyMatrix.json` 立场、丰富 `searchQueries.md`、改进 `gen_card_html.py` 可视化。

## 隐私
`clients/` 含真实商业情报，**请勿提交公开仓库**。本仓库仅含 skill 本体与文档。
