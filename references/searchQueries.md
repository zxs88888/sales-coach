# Search Queries — 情报采集查询模板

8 组分路查询。模板里 `{客户}` 替换为归一化前的客户名（含全称/品牌名），`{客户简称}` 用品牌别名。
**执行纪律**：同分析内不重复相同 query（去重）；用户口述已答的类别直接跳过该类；单路失败不阻断；
高价值结果（官网、36kr/huxiu 原文）用 WebFetch 补细节；一手源（官网/财报/新闻稿）优先，聚合/SEO 内容降置信。

## 中文模板（默认，locale=zh）

1. **公司画像**：`{客户} 官网`、`{客户} 公司简介 主营业务 规模`、`{客户} 融资 估值 2026`
2. **战略动态**：`{客户} 2026 战略 发布 合作`、`{客户} 最新 业务调整 组织架构`
3. **技术招聘**：`{客户} 招聘 钉钉 低代码 实施`、`{客户} 招聘 AI应用 智能体 工程师`
4. **协同/办公工具采用**：`{客户} 用 钉钉 企业微信 飞书 哪个`、`{客户} 钉钉组织 渗透率 席位数`
5. **AI/Agent 供应商**：`{客户} AI智能体 办公 落地`、`{客户} 用 Copilot 飞书智能 WPS AI 吗`
6. **风险决策**：`{客户} 负面 处罚 诉讼 裁员 2026`、`{客户} 高管 变动 CTO CIO`
7. **预算/项目**：`{客户} 数字化 办公 协同 项目`、`{客户} 钉钉服务商 集成商 代理商`
8. **行业地位**：`{客户} 行业排名 市场份额 竞品`、`{客户} 客户案例 标杆`

## 英文模板（locale=en，海外/英文名主体）

1. **Company profile**：`{客户} official website`、`{客户} company overview funding valuation 2026`
2. **Strategy**：`{客户} 2026 strategy announcement partnership`
3. **Tech hiring**：`{客户} jobs DingTalk low-code AI agent engineer`
4. **Collaboration suite**：`{客户} uses DingTalk WeCom Feishu which collaboration suite`
5. **AI/Agent vendor**：`{客户} AI agent office Copilot Feishu partnership`
6. **Risk/decision**：`{客户} lawsuit layoffs leadership change 2026`
7. **Budget/projects**：`{客户} RFP digital transformation project`
8. **Market position**：`{客户} market share competitors`

## locale 判断

- 用户标注「海外/英文名」或归一化后仍含大量英文字母（如 `stripe`、`nvidia`）→ 切英文模板。
- 否则默认中文模板；即使客户是外企中国区，也优先中文（搜中国区主体）。

## 限流 / 反爬提示

- 不要在一轮里并发狂打 WebSearch；~8–10 路已覆盖核心信号，避免触发限流/超时。
- 若返回大量 SEO 聚合页（无实质信息），换更具体的 query（加年份/人名/产品名）而非重复同一句。
- 微信公众号/36kr 等 WebFetch 可能受限：抓取失败不阻断，该维度在「数据质量声明」里标注覆盖不足。
- 全部 8 路 0 有效结果 → 转「探测清单 + 提示口述」（见 SKILL.md CRITICAL #8）。
