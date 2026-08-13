---
name: supplier-evaluation-report
description: Use for generating a 供应商评估报告 (供应商评估, 供应商准入, 合作伙伴评估, 供货能力评估). Directly connects to 6 MCP servers (enterprise / risk / operation / factory-channel / factory-insight / recruitment), pulls raw data, and runs cross-domain analysis — supply capability × compliance risk, account-period risk × financial stability, channel competitiveness, capacity-operation fit — producing a scored admission verdict. Trigger when users ask for "供应商评估", "供应商准入", "合作伙伴评估", "供货能力评估", "供应商尽调". Infer the enterprise name, connect MCPs, cross-analyze, and produce a radar + gauge + verdict report.
---

# 供应商评估报告

## 定位

供应商 / 合作伙伴准入评估 skill。**直接连接 6 个 MCP server**（工商 / 风险 / 经营 / 渠道 / 工厂 / 招聘），获取多源原始数据，运行**跨维度交叉分析**——产出单维度原子 skill 无法生成的关联洞察、专项评分矩阵与结构化准入结论。

## 与原子 skill 的区别

原子 skill 各自只连一个 MCP、产出单维度报告。本 skill 直连 6 个 MCP 拿原始数据，做交叉分析：

- **供货能力 × 合规风险** — 工厂产能/设备/产线 × 处罚/异常/限高风险 → 供货中断风险评估
- **账期风险 × 财务稳健** — accountPeriodRisk × 实缴率/融资/规模 → 账期违约风险
- **渠道竞争力** — channelCount vs peerAvgChannelCount → 同行对比定位
- **产能 × 经营规模匹配** — factory scale vs operation scale → 产能匹配度

## 用户契约

1. 不要向用户索要 product_id、MCP 工具名、内部参数；只接受企业名称 / 统一信用代码 / 注册号。
2. 接受自然目标，自动补全企业全称、直连多 MCP、交叉分析。
3. 默认直连多 MCP；`--dry-run` 读缓存报告做交叉分析骨架；`--reports-dir` 走旧融合引擎。
4. 同时产出 HTML（雷达图 + 评分仪表盘 + 准入结论 + 交叉明细）、Markdown、JSON。
5. 绝不打印密钥 / 签名 / token；默认 dry-run，真实查询需 MCP 配置完整。
6. 数据不足的维度如实标注，不臆造；准入结论全部基于数据交叉验证。

## 直连的 6 个 MCP

| MCP server | 工具 | 数据用途 |
| --- | --- | --- |
| enterprise-mcp-server | base_info / holders / invest / main_person | 工商基础、股权、关联方 |
| enterprise-risk-mcp-server | score / litigation / hearings / penalties / anomalies / restrictions / mortgage | 风险全景、诉讼结构 |
| enterprise-operation-mcp-server | business_scale / financing / trends / rankings | 经营规模、资本运作 |
| factory-channel-mcp-server | channel_analysis / channel_search | 渠道结构、供应商分析、同行对比 |
| factory-insight-mcp-server | factory_profile / factory_capabilities / product_stats | 工厂概况、产能设备、产品统计 |
| recruitment-mcp-server | trend / employer_profile | 招聘活跃度 |

## 交叉分析产出

| 产出 | 说明 |
| --- | --- |
| 专项评分 | 供货能力 / 合规健康度 / 财务稳健性 / 风险隔离度（0-100） |
| 准入结论 | 推荐准入 / 附条件准入 / 需深入调查 / 不建议合作 + 阻断项 + 关注点 |
| 跨维度洞察 | 供货风险 / 账期财务 / 渠道竞争力 / 产能匹配 |
| 明细章节 | 工商基础 / 供货能力 / 渠道分析 / 风险评分 / 风险明细 / 经营 / 招聘 |

## 脚本速查

```bash
# 默认：直连多 MCP 交叉分析（需 MCP 连接配置）
python scripts/compose_fusion_report.py \
  --enterprise "某公司" \
  --output output/供应商.json \
  --report-output output/供应商.html

# dry-run：读缓存报告做交叉分析（不调真实 MCP）
python scripts/compose_fusion_report.py \
  --enterprise "某公司" \
  --dry-run \
  --output output/供应商.json \
  --report-output output/供应商.html

# 旧模式：聚合已有原子报告（fusion_engine）
python scripts/compose_fusion_report.py \
  --enterprise "某公司" \
  --reports-dir ../../reports_探迹 \
  --output output/供应商.json \
  --report-output output/供应商.html
```

## 输出字段

- `verdict` — 准入结论（recommendation / level / blockers / key_concerns / summary）。
- `specialty_scores` — 4 项专项评分（供货能力 / 合规健康度 / 财务稳健性 / 风险隔离度）+ 均值。
- `metrics` — 指标卡（综合风险 / 对外投资 / 供应商综合评分 / 注册资本 / 资本实缴率 / 融资轮次 / 股东 / 成立年限 + 各专项评分）。
- `insights` — 供应商场景跨维度洞察。
- `core_analysis.sections` — 12 个明细章节（含雷达图 + 2 个 gauge + 交叉明细表）。


- MCP 返回的嵌套 JSON 字符串（如金额 `{"coinType":"人民币","value":430000000.0}`、地址 `{"city":"杭州市",...}`）必须解析为可读文本（如"4.30 亿 人民币"、"浙江省杭州市"），绝不在报告正文、表格或指标中输出原始 JSON 字符串。
- 报告所有章节标题、指标卡标签必须用中文；`core_analysis.sections` 的 `title` 字段必须中文，不可显示英文 key（如 `holders`、`investments`）。
- 指标值必须可读化：金额格式为"X 亿/万 + 币种"，地址拼接省市区，比率显示百分号。详见 `references/report-output.md` 的「数据格式约束」。

## 按需加载 references

- 报告结构规范：`references/report-output.md`。
- 证据评分模型：`references/evidence-scoring.md`。
- 维度矩阵：`references/dimension-matrix.md`。
