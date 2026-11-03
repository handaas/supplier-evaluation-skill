# supplier-evaluation-skill：已验收示例

本目录只展示 **4 个完全通过的真实正向场景**（最低要求4例）。

每例均为真实、非空、非缓存调用；技术检查、独立业务检查和离线浏览器检查全部通过。不把空数据、报错处理或仅生成页面计作通过。历史验收记录保留在本地 test-records/；本目录的 HTML/Markdown 由原 JSON 重渲染，不代表重新查询或重新验收。

| 场景 | 真实使用需求 | 报告 |
|---|---|---|
| [立讯精密供应商预筛证据缺口表](09-luxshare-prescreen-gap-register/README.md) | 整理立讯精密工业股份有限公司的工商主体、工厂平台线索和公开风险事件，形成供应商预筛证据与缺口表；不要给出合格、准入或供货能力推荐。 | [HTML](09-luxshare-prescreen-gap-register/report.html) / [MD](09-luxshare-prescreen-gap-register/report.md) / [JSON](09-luxshare-prescreen-gap-register/report.json) |
| [比亚迪扩张信号与产能缺口审计](10-byd-expansion-signal-audit/README.md) | 核对比亚迪股份有限公司的招聘、经营规模和工厂平台线索，区分公开扩张信号与实际可用产能；不要据此判断稳定履约或推荐准入。 | [HTML](10-byd-expansion-signal-audit/report.html) / [MD](10-byd-expansion-signal-audit/report.md) / [JSON](10-byd-expansion-signal-audit/report.json) |
| [苏宁易购风险与渠道人工复核索引](11-suning-risk-channel-index/README.md) | 整理苏宁易购集团股份有限公司的司法风险记录和渠道关系搜索结果，形成采购人工复核索引；不要推断现金流、账期能力或给出附条件准入建议。 | [HTML](11-suning-risk-channel-index/report.html) / [MD](11-suning-risk-channel-index/report.md) / [JSON](11-suning-risk-channel-index/report.json) |
| [渠道覆盖型供应商评估](03-channel-coverage/README.md) | 评估美的集团股份有限公司的渠道竞争力、工厂能力和财务稳健信号。 | [HTML](03-channel-coverage/report.html) / [MD](03-channel-coverage/report.md) / [JSON](03-channel-coverage/report.json) |

- [逐例验收结果](results.json) · [业务复核](review.json) · [证据摘要](evidence-index.json)
- 完整测试记录仅存于本地 test-records/live-replaced-20261027/（仅本地审计用，不随本目录发布），不属于可展示示例。
- 当前数据与结论限于原查询时点及公开样本；覆盖率不代表准确率或低风险。
