# 渠道覆盖型供应商评估

- 用户需求：评估美的集团股份有限公司的渠道竞争力、工厂能力和财务稳健信号。
- 决策用途：判断家电供应商的渠道与供货基础。
- 本轮结果：**本轮检查通过**
- 实际工具调用：22；失败 0
- 章节覆盖率：69%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 渠道数量与同行对比口径清楚
- 工厂和经营数据相互独立
- 财务稳健不由注册资本单独决定
- 风险明细无虚构补全

## 本轮自动检查发现


## 使用局限

- 渠道数据不等于实际销售份额
- 财务结论不替代审计报告

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 supplier-evaluation-skill/scripts/compose_fusion_report.py --enterprise '美的集团股份有限公司' --keyword-type name --output supplier-evaluation-skill/output/03-channel-coverage/report.json --report-output supplier-evaluation-skill/output/03-channel-coverage/report.html
```

## 逐场景业务复核

当前冻结产物逐项满足场景契约；结论仅限本轮公开数据和报告口径。

- **pass** 渠道数量与同行对比口径清楚：渠道仅列关联搜索4、财务/销售分类样本0，并明确关系未逐条确认、无同行分母、不作领先或覆盖结论。 当前第五轮result.started_at=2026-10-26T18:45:29+08:00，invocation_id=1793011529316788000；calls=22，HTML/MD均含当前标题。；本轮当前产物：technical=passed，successful_data_calls=18；subject.enterprise=美的集团股份有限公司，resolved=True；metrics[上游风险评分=100；对外投资=134；注册资本=人民币 76.06亿；融资轮次=10；数据产品账期标签=低；在招岗位=5961；开庭公告=900；股东数量=14；成立年限=26 年]；quality={'total_sections': 13, 'populated_sections': 9, 'empty_sections': 4, 'coverage_pct': 69, 'data_sources': 6, 'cross_insights': 3}；非空章节=['供应商概况', '工厂平台返回线索', '渠道关联搜索事实', '股东出资结构', '对外投资清单（关联方敞口）', '风险维度统计', '开庭公告明细', '经营规模与资本运作', '招聘公开统计']；代表记录=3；calls[recruitment:recruitment_trend=data；recruitment:recruitment_employer_profile=data；channel:channel_insight_channel_search=data(4/4)；channel:channel_insight_channel_analysis=data；factory:factory_insight_factory_profile=data；factory:factory_insight_factory_capabilities=data；factory:factory_insight_factory_product_stats=data；operation:operation_insight_business_scale=data；operation:operation_insight_financing_info=data；operation:operation_insight_company_trends=data；operation:operation_insight_enterprise_rankings=data(10/77)；enterprise:enterprise_get_enterprise_base_info=data；enterprise:enterprise_get_enterprise_holder_info=data；enterprise:enterprise_get_enterprise_invest_info=data(50/134)；enterprise:enterprise_get_enterprise_main_person_info=data(10/10)；risk:enterprise_risk_insight_score=data；risk:risk_insight_litigation_risk_profile=data；risk:risk_insight_court_hearings=data(20/900)；risk:risk_insight_penalties=empty；risk:risk_insight_business_anomalies=empty；risk:risk_insight_chattel_mortgage=empty；risk:risk_insight_consumption_restrictions=empty]
- **pass** 工厂和经营数据相互独立：工厂只列产品70且声明核心产能缺失；经营另列人员、营业额、融资10与上榜10。 当前第五轮result.started_at=2026-10-26T18:45:29+08:00，invocation_id=1793011529316788000；calls=22，HTML/MD均含当前标题。；本轮当前产物：technical=passed，successful_data_calls=18；subject.enterprise=美的集团股份有限公司，resolved=True；metrics[上游风险评分=100；对外投资=134；注册资本=人民币 76.06亿；融资轮次=10；数据产品账期标签=低；在招岗位=5961；开庭公告=900；股东数量=14；成立年限=26 年]；quality={'total_sections': 13, 'populated_sections': 9, 'empty_sections': 4, 'coverage_pct': 69, 'data_sources': 6, 'cross_insights': 3}；非空章节=['供应商概况', '工厂平台返回线索', '渠道关联搜索事实', '股东出资结构', '对外投资清单（关联方敞口）', '风险维度统计', '开庭公告明细', '经营规模与资本运作', '招聘公开统计']；代表记录=3；calls[recruitment:recruitment_trend=data；recruitment:recruitment_employer_profile=data；channel:channel_insight_channel_search=data(4/4)；channel:channel_insight_channel_analysis=data；factory:factory_insight_factory_profile=data；factory:factory_insight_factory_capabilities=data；factory:factory_insight_factory_product_stats=data；operation:operation_insight_business_scale=data；operation:operation_insight_financing_info=data；operation:operation_insight_company_trends=data；operation:operation_insight_enterprise_rankings=data(10/77)；enterprise:enterprise_get_enterprise_base_info=data；enterprise:enterprise_get_enterprise_holder_info=data；enterprise:enterprise_get_enterprise_invest_info=data(50/134)；enterprise:enterprise_get_enterprise_main_person_info=data(10/10)；risk:enterprise_risk_insight_score=data；risk:risk_insight_litigation_risk_profile=data；risk:risk_insight_court_hearings=data(20/900)；risk:risk_insight_penalties=empty；risk:risk_insight_business_anomalies=empty；risk:risk_insight_chattel_mortgage=empty；risk:risk_insight_consumption_restrictions=empty]
- **pass** 财务稳健不由注册资本单独决定：洞察明确缺审计财务、现金流、应收账款账龄和偿债指标，不能由账期标签或资本信息评价稳健。 当前第五轮result.started_at=2026-10-26T18:45:29+08:00，invocation_id=1793011529316788000；calls=22，HTML/MD均含当前标题。；本轮当前产物：technical=passed，successful_data_calls=18；subject.enterprise=美的集团股份有限公司，resolved=True；metrics[上游风险评分=100；对外投资=134；注册资本=人民币 76.06亿；融资轮次=10；数据产品账期标签=低；在招岗位=5961；开庭公告=900；股东数量=14；成立年限=26 年]；quality={'total_sections': 13, 'populated_sections': 9, 'empty_sections': 4, 'coverage_pct': 69, 'data_sources': 6, 'cross_insights': 3}；非空章节=['供应商概况', '工厂平台返回线索', '渠道关联搜索事实', '股东出资结构', '对外投资清单（关联方敞口）', '风险维度统计', '开庭公告明细', '经营规模与资本运作', '招聘公开统计']；代表记录=3；calls[recruitment:recruitment_trend=data；recruitment:recruitment_employer_profile=data；channel:channel_insight_channel_search=data(4/4)；channel:channel_insight_channel_analysis=data；factory:factory_insight_factory_profile=data；factory:factory_insight_factory_capabilities=data；factory:factory_insight_factory_product_stats=data；operation:operation_insight_business_scale=data；operation:operation_insight_financing_info=data；operation:operation_insight_company_trends=data；operation:operation_insight_enterprise_rankings=data(10/77)；enterprise:enterprise_get_enterprise_base_info=data；enterprise:enterprise_get_enterprise_holder_info=data；enterprise:enterprise_get_enterprise_invest_info=data(50/134)；enterprise:enterprise_get_enterprise_main_person_info=data(10/10)；risk:enterprise_risk_insight_score=data；risk:risk_insight_litigation_risk_profile=data；risk:risk_insight_court_hearings=data(20/900)；risk:risk_insight_penalties=empty；risk:risk_insight_business_anomalies=empty；risk:risk_insight_chattel_mortgage=empty；risk:risk_insight_consumption_restrictions=empty]
- **pass** 风险明细无虚构补全：20条开庭样本按上游字段展示，缺案号/主体/日期使用“-”且明确无法逐案去重。 当前第五轮result.started_at=2026-10-26T18:45:29+08:00，invocation_id=1793011529316788000；calls=22，HTML/MD均含当前标题。；本轮当前产物：technical=passed，successful_data_calls=18；subject.enterprise=美的集团股份有限公司，resolved=True；metrics[上游风险评分=100；对外投资=134；注册资本=人民币 76.06亿；融资轮次=10；数据产品账期标签=低；在招岗位=5961；开庭公告=900；股东数量=14；成立年限=26 年]；quality={'total_sections': 13, 'populated_sections': 9, 'empty_sections': 4, 'coverage_pct': 69, 'data_sources': 6, 'cross_insights': 3}；非空章节=['供应商概况', '工厂平台返回线索', '渠道关联搜索事实', '股东出资结构', '对外投资清单（关联方敞口）', '风险维度统计', '开庭公告明细', '经营规模与资本运作', '招聘公开统计']；代表记录=3；calls[recruitment:recruitment_trend=data；recruitment:recruitment_employer_profile=data；channel:channel_insight_channel_search=data(4/4)；channel:channel_insight_channel_analysis=data；factory:factory_insight_factory_profile=data；factory:factory_insight_factory_capabilities=data；factory:factory_insight_factory_product_stats=data；operation:operation_insight_business_scale=data；operation:operation_insight_financing_info=data；operation:operation_insight_company_trends=data；operation:operation_insight_enterprise_rankings=data(10/77)；enterprise:enterprise_get_enterprise_base_info=data；enterprise:enterprise_get_enterprise_holder_info=data；enterprise:enterprise_get_enterprise_invest_info=data(50/134)；enterprise:enterprise_get_enterprise_main_person_info=data(10/10)；risk:enterprise_risk_insight_score=data；risk:risk_insight_litigation_risk_profile=data；risk:risk_insight_court_hearings=data(20/900)；risk:risk_insight_penalties=empty；risk:risk_insight_business_anomalies=empty；risk:risk_insight_chattel_mortgage=empty；risk:risk_insight_consumption_restrictions=empty]

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)