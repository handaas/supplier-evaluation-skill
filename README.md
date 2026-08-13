# 供应商评估报告

一个可被本地智能体使用的 HandaaS 场景研判 Skill。用户只需要说"使用供应商评估，对比亚迪股份有限公司做供应商准入评估"，智能体会自动连接多个 MCP 服务、获取原始数据，通过证据评分模型在多个维度上交叉评分，输出综合画像报告（HTML + Markdown + JSON + PDF 四件套），内嵌 ECharts 5.x 雷达图与仪表盘，离线可打开。

> 直连 6 个 MCP server（工商 / 风险 / 经营 / 渠道 / 工厂 / 招聘），从供货能力 × 合规风险、账期风险 × 财务稳定性、渠道竞争力、产能-经营匹配等维度交叉评分，输出供应商准入评估报告。

## 目录

- [一句话安装](#一句话安装)
- [快速验证](#快速验证)
- [接入 MCP 服务](#接入-mcp-服务)
- [生成报告](#生成报告)
- [效果预览](#效果预览)
- [命令行用法](#命令行用法)
- [故障排查](#故障排查)

## 一句话安装

给普通用户最省事的方式：复制下面这段话到任意支持 Git / Shell / Python 的智能体工具里（Claude Code、Codex、Cursor、Gemini CLI、Windsurf、Cline 等）。

```text
请帮我安装并调试 HandaaS supplier-evaluation-skill：先完整读取 https://github.com/handaas/supplier-evaluation-skill 这个项目的 README.md，再克隆仓库并按 README 自动完成安装、配置文件创建、校验、模拟运行验证和示例报告生成。若当前工具支持 Skill 目录安装，就把 supplier-evaluation-skill/ 安装到对应 skills 目录；若不支持，就把该仓库作为本地工具包使用。请提醒我只在本地配置自己的企业数据接口参数或在线 MCP token，不要提交凭证；除非需要真实接口密钥，否则不要中断询问。
```

智能体读取 README 后会自动完成克隆、安装、配置、校验和模拟运行，并告诉你后续如何使用。

## 快速验证

不需要配置 MCP 也能先跑起来，验证报告骨架和评分逻辑：

```bash
cd supplier-evaluation-skill
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/compose_fusion_report.py \
  --enterprise "比亚迪股份有限公司" \
  --dry-run \
  --output output/report.json \
  --report-output output/report.html
```

打开 `output/report.html` 即可看到完整的雷达图与评分报告效果。

## 接入 MCP 服务

本场景直连以下 6 个 MCP server 获取数据。在 [HandaaS 平台](https://www.handaas.com/) 创建 MCP 对接器时，选择以下所需的在线服务，所选服务共用同一个 token。

| MCP 服务 | 环境变量 |
| --- | --- |
| 企业工商 | `ENTERPRISE_MCP_URL` |
| 企业风险 | `ENTERPRISE_RISK_MCP_URL` |
| 企业经营 | `ENTERPRISE_OPERATION_MCP_URL` |
| 渠道 | `FACTORY_CHANNEL_MCP_URL` |
| 工厂 | `FACTORY_INSIGHT_MCP_URL` |
| 招聘 | `RECRUITMENT_MCP_URL` |

### 方式一：使用官方在线 MCP（推荐）

登录 [HandaaS 平台](https://www.handaas.com/)，注册并创建 MCP 对接器，选择需要的在线服务，获取 token。同一个对接器中选择的 MCP 服务共用同一个 token，只需配置一次。

macOS / Linux：

```bash
export SUPPLIER_EVALUATION_MCP_TOKEN="<your-token>"
export ENTERPRISE_MCP_URL="https://mcp.handaas.com/enterprise/enterprise_profile"
export ENTERPRISE_RISK_MCP_URL="https://mcp.handaas.com/enterprise/risk_insight"
export ENTERPRISE_OPERATION_MCP_URL="https://mcp.handaas.com/enterprise/operation_insight"
export FACTORY_CHANNEL_MCP_URL="https://mcp.handaas.com/factory/channel_insight"
export FACTORY_INSIGHT_MCP_URL="https://mcp.handaas.com/factory/factory_insight"
export RECRUITMENT_MCP_URL="https://mcp.handaas.com/recruitment/recruitment_bigdata"
```

Windows PowerShell：

```powershell
$env:SUPPLIER_EVALUATION_MCP_TOKEN = "<your-token>"
$env:ENTERPRISE_MCP_URL = "https://mcp.handaas.com/enterprise/enterprise_profile"
$env:ENTERPRISE_RISK_MCP_URL = "https://mcp.handaas.com/enterprise/risk_insight"
$env:ENTERPRISE_OPERATION_MCP_URL = "https://mcp.handaas.com/enterprise/operation_insight"
$env:FACTORY_CHANNEL_MCP_URL = "https://mcp.handaas.com/factory/channel_insight"
$env:FACTORY_INSIGHT_MCP_URL = "https://mcp.handaas.com/factory/factory_insight"
$env:RECRUITMENT_MCP_URL = "https://mcp.handaas.com/recruitment/recruitment_bigdata"
```

将 `<your-token>` 替换为你在 HandaaS 平台获取的实际 token。token 由 `SUPPLIER_EVALUATION_MCP_TOKEN` 统一携带，URL 中无需重复填写。

### 方式二：连接本地部署的 MCP 服务

### 方式二：连接本地部署的 MCP 服务

分别在各 MCP server 目录下部署：

```bash
cd ../handaas-mcp-server/enterprise-mcp-server
python3 -m venv mcp_env
source mcp_env/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 编辑 .env 填入凭证
./start_mcp_server.sh
```

在使用 Skill 的 shell 中指定各 MCP 地址（端口按实际分配修改）。

### MCP 连接验证

```bash
python scripts/compose_fusion_report.py \
  --enterprise "测试企业" --dry-run \
  --output output/report.json
```

## 生成报告

### 真实查询 + 渲染

```bash
python scripts/compose_fusion_report.py \
  --enterprise "比亚迪股份有限公司" \
  --output output/report.json \
  --report-output output/report.html \
  --pdf-output output/report.pdf
```

同时产出四个文件：

| 文件 | 说明 |
| --- | --- |
| `output/report.html` | 浏览器直接打开，含 8 维度雷达图与仪表盘 |
| `output/report.md` | Markdown 格式，适合放入 Wiki / 文档系统 |
| `output/report.json` | 结构化原始数据，含各维度评分与证据 |
| `output/report.pdf` | 打印友好版，需安装 Playwright |

### 聚合已有原子报告

如果已经有各原子 skill 的报告 JSON，也可以聚合生成：

```bash
python scripts/compose_fusion_report.py \
  --enterprise "比亚迪股份有限公司" \
  --reports-dir ../reports_探迹/ \
  --output output/report.json \
  --report-output output/report.html
```

### 重渲染已有 JSON

```bash
python scripts/render_report.py \
  --input output/report.json \
  --output output/report.html
```

## 效果预览

> 以下示例来自真实查询，可直接打开查看完整效果。

| 文件 | 说明 | 链接 |
| --- | --- | --- |
| HTML 报告 | 浏览器直接打开，含雷达图与仪表盘 | [查看](examples/report.html) |
| Markdown 报告 | 纯文本格式，适合 Git / 文档系统 | [查看](examples/report.md) |
| JSON 原始数据 | 结构化数据，适合二次处理 | [查看](examples/report.json) |
| PDF 报告 | 打印友好版 | [查看](examples/report.pdf) |

## 命令行用法

### 模拟运行（不调真实 API）

```bash
python scripts/compose_fusion_report.py \
  --enterprise "测试企业" \
  --dry-run \
  --output output/report.json
```

### 真实查询

```bash
python scripts/compose_fusion_report.py \
  --enterprise "比亚迪股份有限公司" \
  --output output/report.json \
  --report-output output/report.html
```

## 故障排查

### 1. 某个 MCP 连不上

检查对应环境变量是否设置：

```bash
echo "$ENTERPRISE_MCP_URL"
python scripts/compose_fusion_report.py --enterprise "测试" --dry-run --output /dev/null
```

### 2. 评分维度数据缺失

场景报告支持部分 MCP 缺失时降级运行；缺失的维度会标注"数据不足"，不影响其他维度的评分和报告生成。

### 3. 报告内容为空

使用 `--dry-run` 验证报告骨架是否正常，再逐步排查各 MCP 返回数据。

### 5. PDF 导出不可用

PDF 导出需要 Playwright + Chromium：

```bash
pip install playwright
playwright install chromium
```

## 相关文档

- [SKILL.md](SKILL.md) — Skill 契约
- [references/report-output.md](references/report-output.md) — 融合报告结构规范
- [项目使用说明](../docs/使用说明.md) — 整体架构与工作流
