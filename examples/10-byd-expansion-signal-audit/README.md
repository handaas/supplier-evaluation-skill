# 比亚迪扩张信号与产能缺口审计

- 用户需求：核对比亚迪股份有限公司的招聘、经营规模和工厂平台线索，区分公开扩张信号与实际可用产能；不要据此判断稳定履约或推荐准入。
- 决策用途：验证招聘与经营数据不会被错误外推为产能和交付能力。
- 本轮结果：**本轮检查通过**
- 实际工具调用：22；失败 0
- 章节覆盖率：69%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 工商主体必须确认
- 招聘域至少一个实际字段非空
- 经营规模或融资域至少一个实际字段非空
- 工厂平台产品或认证线索至少一项非空
- 招聘和经营不得被等同实际产能或稳定履约

## 本轮自动检查发现


## 使用局限

- 招聘不能证明员工到岗、产线爬坡或可用产能
- 具体产品适配需技术审核
- 实际产能与历史交付需现场和订单证据

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 supplier-evaluation-skill/scripts/compose_fusion_report.py --enterprise '比亚迪股份有限公司' --keyword-type name --output supplier-evaluation-skill/output/10-byd-expansion-signal-audit/report.json --report-output supplier-evaluation-skill/output/10-byd-expansion-signal-audit/report.html
```

## 逐场景业务复核

当前冻结产物逐项满足场景契约；结论仅限本轮公开数据和报告口径。

- **pass** 工商主体必须确认：工商=比亚迪股份有限公司/91440300192317458F
- **pass** 招聘域至少一个实际字段非空：招聘=['126960', '126960', '7863 元/月']
- **pass** 经营规模或融资域至少一个实际字段非空：经营=['10000人以上', '10亿以上', '7', '10']
- **pass** 工厂平台产品或认证线索至少一项非空：工厂=["['CCC', 'ISO9000\\\\ISO140000?OHSAS18000?QC080000?RoHS']", '305']
- **pass** 招聘和经营不得被等同实际产能或稳定履约：recruitment/operation/factory=data/data/data，未将信号写成实际产能/稳定履约

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)