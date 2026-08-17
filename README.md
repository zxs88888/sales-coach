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
编辑 `myCompany.json`：`{ "active": "qianwen-office" }`。
预设见 `references/companyMatrix.json`（tencent / aliyun / huawei / aws / azure / moonshot / zhipu / baichuan / qianwen-office）。自定义加到 `myCompany.json.profiles`。

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
默认 `~/.workbuddy/sales-coach/`，含 `clients/<客户>.md` 与 `myCompany.json`。可按环境改路径。

## 贡献
Fork → 改 → 提 PR。常见优化：扩充 `companyMatrix.json` 立场、丰富 `searchQueries.md`、改进 `gen_card_html.py` 可视化。

## 隐私
`clients/` 含真实商业情报，**请勿提交公开仓库**。本仓库仅含 skill 本体与文档。
