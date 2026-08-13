# 融合报告结构规范

## 报告章节（9 章）

1. **企业综合画像摘要** — 一句话定位 + 综合评分 + 置信度 + 评估结论
2. **多维度评分雷达图** — 8 维度信号评分雷达（ECharts radar）
3. **维度评分详情** — 表格：维度/评分/证据强度/覆盖度/数据来源/关键发现
4. **工商基础与股权** — 来自 enterprise-report
5. **创新实力评估** — 来自 patent + trademark + qualification
6. **市场活跃度** — 来自 bidding + news + exhibition
7. **风险健康度** — 来自 enterprise-risk
8. **经营与数字化** — 来自 operation + recruitment + cloudmigration
9. **综合研判** — 基于评分的结论（全部有数据支撑）

## 质量门禁

- 如果**所有**维度均无数据 → 拒绝生成报告，报 `QualityGateError`
- 空维度在雷达图上显示 0 分（视觉可见覆盖缺口）
- 综合研判只引用有数据的维度，不外推空维度

### 数据格式约束（铁律）

以下约束适用于 compose_report.py 组装数据与 render_report.py 渲染输出的全过程：

1. **嵌套 JSON 字符串必须解析**：MCP 返回的某些字段（如 `regCapital`、`addressValue`、`subscriptionDetail`）可能是 JSON 字符串（例：`{"coinType":"人民币","value":430000000.0}`）。compose 层必须调用 `_unwrap_json_str()` / `_parse_reg_capital()` / `_flatten_addr()` 解析为可读文本（如"4.30 亿 人民币"、"浙江省杭州市滨江区..."）。绝不在报告正文、表格单元格或指标值中输出原始 JSON 字符串。

2. **section 标题必须用中文**：`core_analysis.sections` 数组中每个 section 的 `title` 字段必须使用中文（如"企业基本信息"、"对外投资"、"股东信息"）。`key` 字段用英文 snake_case 供程序索引，但 `title` 绝不可显示英文 key。即使缺少 sections 数组，渲染器回退逻辑也内置了 `_TITLE_MAP` 映射。

3. **指标值可读化**：所有 `metrics` 的 `value` 字段必须格式化为人类可读形式：
   - 金额：`10995210218.0` → `109.95 亿 人民币`（≥1 亿用亿，≥1 万用万）
   - 地址：嵌套 dict → 省+市+区拼接 或取 `value` 字段
   - 比率：`0.8858` → `88.58%`
   - 日期：保持 `yyyy-MM-dd` 格式
   - "-" 表示字段缺失（MCP 未返回）；`0` 表示真实为零

4. **企业画像指标提取**：有 fuzzy_search 的 skill 必须从返回的 record 中提取 `regCapitalValue` / `foundTime` / `operStatus` / `enterpriseType` / `legalRepresentative`，通过 `_enrich_metrics_with_profile()` 追加为指标卡。

5. **分布派生指标**：`_derive_core_metrics()` 从 core_analysis 各 section 计算分布指标（CR3 集中度、覆盖城市/平台/类目数、价格区间、正面占比等），确保指标总数 M ≥ 6。

## 禁止项

- 不出现 `matchKeyword=`、`product_id`、`secret_id`、工具名
- 不出现"联网收集""Skill 生成"等过程语言
- 不臆造空维度的数据或结论
