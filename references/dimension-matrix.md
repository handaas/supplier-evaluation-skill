# 维度矩阵

定义 8 个融合维度与 21 个原子 skill 的映射关系。

| 融合维度 | 权重 | 原子 skill | 说明 |
| --- | --- | --- | --- |
| 创新实力 | 15 | patent-report, trademark-report, qualification-report | 专利储备、商标布局、资质认证 |
| 风险健康度 | 15 | enterprise-risk-report | 风险评分、诉讼情况、合规状态 |
| 工商基础 | 12 | enterprise-report | 注册资本、股权结构、对外投资 |
| 市场活跃度 | 12 | bidding-report, news-report, exhibition-report | 招投标、舆情健康、展会活动 |
| 经营状况 | 12 | enterprise-operation-report, recruitment-report | 经营规模、融资、招聘 |
| 数字化程度 | 10 | cloudmigration-report | 上云资产、域名、云支出 |
| 供应链与渠道 | 8 | factory-channel-report, factory-insight-report | 渠道能力、工厂产能 |
| 外贸与电商 | 8 | customs-report, estore-report, goods-report, store-report | 出口贸易、网店、商品 |

## 关键信号提取规则

每个维度从原子报告中提取以下信号：
- **metrics**：指标卡数据（label + value + delta）
- **insights**：深度洞察（feature + evidence + interpretation）
- **core_analysis**：章节数据（sections 声明 + 实际数据行）
- **data_rows**：核心分析的总数据行数

## 维度评分的信号强度判定

| 维度 | 判为"强"的条件 |
| --- | --- |
| 创新实力 | 专利总数 > 10 |
| 风险健康度 | 风险评分存在（直接权威评估） |
| 市场活跃度 | 招投标数 > 5 |
| 其他维度 | metrics ≥ 4 且数据行 ≥ 10 |
