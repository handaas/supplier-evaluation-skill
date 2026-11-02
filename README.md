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

在**旷湖SKILL平台**为本 Skill 创建所需在线 MCP 服务后，复制下面整段发给智能体，只替换最后一行的 Token：

```text
请帮我安装并配置 supplier-evaluation-skill：
1. 阅读并遵循 https://github.com/handaas/supplier-evaluation-skill 的 SKILL.md 与 README.md，按当前环境规范安装到实际包含 SKILL.md 的目录；保留已有配置，不默认全局注册。
2. 使用旷湖SKILL平台在线 MCP：本 README「接入 MCP 服务」列出本场景所需的多个服务地址，逐个注入对应 `*_MCP_URL`；平台返回的地址优先。不部署本地 MCP，不索要 INTEGRATOR_ID / SECRET_ID / SECRET_KEY。
3. 将完整 handaas-token 作为本 Skill 专属 `SUPPLIER_EVALUATION_MCP_TOKEN` 注入运行 Python 的进程（若已设置域级 `*_MCP_TOKEN`，它们优先，须先清理）；环境变量必须真正到达该进程，只保存文件或在别的终端 export 不算完成。
4. Token 原样保留逗号等字符：不拆分、不解码、不放进 URL、不手动加 Bearer。不要把 Token 写入仓库、SKILL.md、README、示例配置、报告或终端历史；若只能使用仓库外的私有环境文件，权限设为 0600，并由启动器显式加载。不要回显 Token、请求头或原始鉴权错误；Token 注意保管，请勿泄露。
5. 正式执行真实查询：不加 --dry-run，直接运行本 README 的报告命令生成 HTML / Markdown / JSON；按问题范围使用默认预算，不为填模板扩大调用，也不重复请求。
6. 只返回脱敏结果：安装目录、私有配置位置、真实查询调用次数与数据范围、报告路径。缺少地址或 Token 时明确说明缺失项，不要把连接失败说成企业没有数据。

handaas-token：<在此粘贴本人在旷湖SKILL平台获取的完整 Token>
```

Token 只放在运行进程的环境变量或仓库外的私有配置中；用户粘贴本指引即视为授权按默认预算执行真实查询；不要擅自扩大调用范围。

### 智能体安装约定

1. 先读 `SKILL.md`，按当前智能体的规范安装依赖；以实际包含 `SKILL.md` 的目录为 Skill 根目录，保留已有安装与配置，不假设克隆后还嵌套一层同名目录，也不默认全局注册。
2. 使用旷湖SKILL平台为本 Skill 一键创建的在线 MCP，同一个 `handaas-token` 供本 Skill 所需全部服务复用。在线安装不克隆 handaas-mcp-server、不启动本地服务、不索要 INTEGRATOR_ID / SECRET_ID / SECRET_KEY。
3. 将完整 Token 保存到本机智能体的私有密钥/环境配置，并作为 `SUPPLIER_EVALUATION_MCP_TOKEN` 注入运行 Python 脚本的进程环境；将下表服务地址逐一注入对应 `*_MCP_URL`。不要只注册智能体原生 MCP 而漏配 Python 进程；脚本不会自动加载 `.env`，也不会读取 `config.json` 的 `remote_mcp`。宿主无持久环境机制时，可用仓库外的私有环境文件配合宿主启动器显式加载（POSIX 权限 0600，Windows 仅限当前用户）；不能安全持久化时明确报告，不宣称配置完成。
4. Token 是不透明字符串，逗号等字符完整保留：不拆分、不解码、不写入 URL、不重复添加 Bearer 前缀（客户端自动加 `Authorization: Bearer`）。只设置本 Skill 专属的 `SUPPLIER_EVALUATION_MCP_TOKEN`；不要配置共享 Token 变量，也不要同时设置域级 `*_MCP_TOKEN`。不得把单一服务地址复用于全部域；每个域只使用自己的 `*_MCP_URL`。
5. 在线验收先逐域用 `get_connection` 确认连接方式为 remote（缺 URL 时脚本可能回退本地，在线流程不得回退），再用 `MultiMcpClient.ensure_session` + `session.list_tools` 逐域做元数据握手，只 `initialize` / `list_tools`，不 `call_tool`。`--dry-run` 只证明离线编排，不证明在线权限；未验证项写“未验证”。默认按本页显式 `--dry-run` 做离线验收；若用户的一键指引明确要求正式执行，则逐域元数据检查后直接执行真实查询并生成报告。
6. 完成后仅报告：安装位置、配置文件位置、各服务的脱敏连接与工具数、离线报告路径。真实 Token 不进入命令参数、日志、回复、仓库、README、SKILL.md、config.example.json、报告或共享配置。普通安装不等于授权付费数据调用。

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

本场景直连以下 6 个 MCP server 获取数据。在旷湖SKILL平台一键创建本 Skill 所需的在线 MCP 服务，下表所有服务共用本 Skill 专属 Token（`SUPPLIER_EVALUATION_MCP_TOKEN`）。

| MCP 服务 | 环境变量 |
| --- | --- |
| 企业工商 | `ENTERPRISE_MCP_URL` |
| 企业风险 | `ENTERPRISE_RISK_MCP_URL` |
| 企业经营 | `ENTERPRISE_OPERATION_MCP_URL` |
| 渠道 | `FACTORY_CHANNEL_MCP_URL` |
| 工厂 | `FACTORY_INSIGHT_MCP_URL` |
| 招聘 | `RECRUITMENT_MCP_URL` |

### 方式一：使用旷湖SKILL平台在线 MCP（推荐）

在旷湖SKILL平台为本 Skill 一键创建所需的在线 MCP 服务并获取平台 Token，保存为本 Skill 专属的 `SUPPLIER_EVALUATION_MCP_TOKEN`。下表所有服务复用同一个值，只需配置一次。

macOS / Linux：

```bash
export SUPPLIER_EVALUATION_MCP_TOKEN="<平台完整Token>"
export ENTERPRISE_MCP_URL="https://mcp.handaas.com/enterprise/enterprise_profile"
export ENTERPRISE_RISK_MCP_URL="https://mcp.handaas.com/enterprise/risk_insight"
export ENTERPRISE_OPERATION_MCP_URL="https://mcp.handaas.com/enterprise/operation_insight"
export FACTORY_CHANNEL_MCP_URL="https://mcp.handaas.com/factory/channel_insight"
export FACTORY_INSIGHT_MCP_URL="https://mcp.handaas.com/factory/factory_insight"
export RECRUITMENT_MCP_URL="https://mcp.handaas.com/recruiting/recruiting_bigdata"
```

Windows PowerShell：

```powershell
$env:SUPPLIER_EVALUATION_MCP_TOKEN = "<平台完整Token>"
$env:ENTERPRISE_MCP_URL = "https://mcp.handaas.com/enterprise/enterprise_profile"
$env:ENTERPRISE_RISK_MCP_URL = "https://mcp.handaas.com/enterprise/risk_insight"
$env:ENTERPRISE_OPERATION_MCP_URL = "https://mcp.handaas.com/enterprise/operation_insight"
$env:FACTORY_CHANNEL_MCP_URL = "https://mcp.handaas.com/factory/channel_insight"
$env:FACTORY_INSIGHT_MCP_URL = "https://mcp.handaas.com/factory/factory_insight"
$env:RECRUITMENT_MCP_URL = "https://mcp.handaas.com/recruiting/recruiting_bigdata"
```

将 `<平台完整Token>` 替换为你在旷湖SKILL平台获取的完整 Token（同一 Token 供上表所有服务复用，逗号等字符完整保留），URL 中无需重复填写。

> 以上示例只配置当前 shell。要让智能体持久使用，必须按上方“智能体安装约定”把 Token 与 URL 注入运行 Python 脚本的进程环境，并确保子进程继承；仅写入某个文件不会自动生效。

### 方式二：连接本地部署的 MCP 服务（可选）

仅当不使用在线 MCP 时使用；本地部署需要各 server 自己的 `.env` 凭证，与上方在线 Token 是两套独立方案，在线安装无需本节。分别在各 MCP server 目录下部署：

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

`--dry-run` 只验证离线报告骨架，不发起任何 MCP 连接，不能证明在线权限或 Token 有效。离线骨架验证：

```bash
python scripts/compose_fusion_report.py \
  --enterprise "测试企业" --dry-run \
  --output output/report.json
```

在线元数据验收：在 Skill 根目录执行下面脚本，先逐域确认 remote（缺在线地址时脚本可能回退本地，在线验收不得回退），再逐域 `initialize` + `list_tools`，不调用任何业务工具；只打印域名与工具数，不输出配置、Token 或原始错误。

```bash
python3 - <<'PY'
import asyncio, sys
sys.path.insert(0, "scripts")
from multi_mcp_client import SERVER_REGISTRY, get_connection, MultiMcpClient

async def main() -> int:
    # 先确认所有域都为 remote；任何缺在线地址的域都直接中止，不打开任何会话
    for domain in SERVER_REGISTRY:
        if get_connection(domain).get("mode") != "remote":
            print(f"未通过：{domain} 未配置在线地址（在线验收不回退本地）。")
            return 1
    failed = False
    async with MultiMcpClient() as client:
        for domain in SERVER_REGISTRY:
            try:
                session = await client.ensure_session(domain)
                result = await session.list_tools()
                tool_list = result.tools
                print(f"OK {domain}: {len(tool_list)} tools")
            except Exception:
                print(f"FAIL {domain}: 在线握手未完成（已脱敏）")
                failed = True
    return 1 if failed else 0

sys.exit(asyncio.run(main()))
PY
```

验收结果只含域名与工具数；出现 `FAIL` / `未通过` 时按域名核对对应 `*_MCP_URL` 与 `SUPPLIER_EVALUATION_MCP_TOKEN` 配置后重试。

工具数仅证明握手与元数据获取；还须对照 `SKILL.md` 或脚本核对所需工具名。空工具列表或缺少所需工具时，安装尚未就绪，不得宣称业务可用，也不要用付费业务调用来代替元数据检查。

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

> 以下文件来自当前真实验收通过案例；`examples/` 只收录完全通过的公开示例。

| 文件 | 说明 | 链接 |
| --- | --- | --- |
| HTML 报告 | 浏览器直接打开，含离线图表 | [查看](examples/live-replaced-20261027/reports/09-luxshare-prescreen-gap-register/report.html) |
| Markdown 报告 | 纯文本格式，适合 Git / 文档系统 | [查看](examples/live-replaced-20261027/reports/09-luxshare-prescreen-gap-register/report.md) |
| JSON 原始数据 | 结构化数据，适合二次处理 | [查看](examples/live-replaced-20261027/reports/09-luxshare-prescreen-gap-register/report.json) |
| 全部已验收案例 | 本 skill 当前全部完全通过示例 | [查看](examples/README.md) |

完整的 8 场景测试、未完全通过案例和历史运行保存在 [test-records](test-records/README.md)，不作为公开示例。

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
