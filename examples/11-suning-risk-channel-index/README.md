# 苏宁易购风险与渠道人工复核索引

- 用户需求：整理苏宁易购集团股份有限公司的司法风险记录和渠道关系搜索结果，形成采购人工复核索引；不要推断现金流、账期能力或给出附条件准入建议。
- 决策用途：验证风险事件与渠道关系两个相关域能够独立呈现，且渠道线索不会抵消风险。
- 本轮结果：**本轮检查通过**
- 实际工具调用：22；失败 0
- 章节覆盖率：69%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 工商主体必须确认
- 司法风险维度或开庭记录至少一项真实非空
- 渠道关联搜索返回或分类样本至少一项真实非空
- 渠道关系状态明确为待核或已核事实
- 不推断现金流、账期能力或准入结论

## 本轮自动检查发现


## 使用局限

- 公开司法记录需核验案由、角色、金额和最新状态
- 渠道搜索结果不等于真实销售关系或销量
- 公开数据不能直接测算现金流和账期

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 supplier-evaluation-skill/scripts/compose_fusion_report.py --enterprise '苏宁易购集团股份有限公司' --keyword-type name --output supplier-evaluation-skill/output/11-suning-risk-channel-index/report.json --report-output supplier-evaluation-skill/output/11-suning-risk-channel-index/report.html
```

## 逐场景业务复核

当前冻结产物逐项满足场景契约；结论仅限本轮公开数据和报告口径。

- **pass** 工商主体必须确认：工商=苏宁易购集团股份有限公司/91320000608950987L
- **pass** 司法风险维度或开庭记录至少一项真实非空：风险集合=1/20
- **pass** 渠道关联搜索返回或分类样本至少一项真实非空：渠道样本=['11', '710015', '575045']
- **pass** 渠道关系状态明确为待核或已核事实：关系核验状态=关联搜索结果未逐条确认与目标法人的关系
- **pass** 不推断现金流、账期能力或准入结论：risk/channel 两域均至少一项 data、无 error；风险域开庭画像有实际数据，其他风险子项可为 empty；报告未输出现金流/账期/准入结论

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)