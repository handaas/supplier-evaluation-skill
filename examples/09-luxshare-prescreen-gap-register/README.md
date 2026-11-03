# 立讯精密供应商预筛证据缺口表

- 用户需求：整理立讯精密工业股份有限公司的工商主体、工厂平台线索和公开风险事件，形成供应商预筛证据与缺口表；不要给出合格、准入或供货能力推荐。
- 决策用途：验证制造供应商预筛中主体归属、工厂线索和风险记录能否被分别核对。
- 本轮结果：**本轮检查通过**
- 实际工具调用：22；失败 0
- 章节覆盖率：77%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 工商主体必须确认
- 工厂平台名称或产品线索至少一项真实非空
- 风险维度或风险代表记录至少一项真实非空
- 工厂记录无法映射工商标识时明确待核
- 不输出准入、合格或供货能力推荐

## 本轮自动检查发现


## 使用局限

- 不替代现场验厂、质量体系审核和历史交付核验
- 工厂平台主体 ID 不一定等同工商统一信用代码
- 实际产能、良率和交付能力缺失时必须保持未知

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 supplier-evaluation-skill/scripts/compose_fusion_report.py --enterprise '立讯精密工业股份有限公司' --keyword-type name --output supplier-evaluation-skill/output/09-luxshare-prescreen-gap-register/report.json --report-output supplier-evaluation-skill/output/09-luxshare-prescreen-gap-register/report.html
```

## 逐场景业务复核

当前冻结产物逐项满足场景契约；结论仅限本轮公开数据和报告口径。

- **pass** 工商主体必须确认：工商=立讯精密工业股份有限公司/91440300760482233Q
- **pass** 工厂平台名称或产品线索至少一项真实非空：工厂线索=['立讯精密工业股份有限公司', '37622fc02a0537bc', '23']
- **pass** 风险维度或风险代表记录至少一项真实非空：风险集合=2/20/1
- **pass** 工厂记录无法映射工商标识时明确待核：关系核验=True、工厂主体ID=37622fc02a0537bc
- **pass** 不输出准入、合格或供货能力推荐：enterprise/factory/risk 三域均至少一项 data、无 error；风险域的处罚与开庭有实际数据，另有部分风险子项 empty；报告未输出准入/合格/供货推荐

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)
[页面截图](browser.png)