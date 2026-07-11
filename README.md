# Grok Search CLI

面向终端用户及 Codex、Claude Code、Pi 等 CLI Agent 的实时网络搜索工具。它通过 Grok 执行 AI 搜索，通过 Tavily/Firecrawl 抓取网页和发现站点链接，并提供可跨进程继续的六阶段搜索规划协议。

本版本是纯 CLI，已彻底移除 MCP server、FastMCP 和 MCP 配置方式。

## 安装

要求 Python 3.10+。推荐使用 `uvx` 从仓库运行：

```bash
uvx --from git+https://github.com/GuDaStudio/GrokSearch@grok-with-tavily grok-search --help
```

本地开发安装：

```bash
python -m pip install -e .
grok-search --version
```

## 配置

可直接导出环境变量：

```bash
export GROK_API_URL="https://your-api.example/v1"
export GROK_API_KEY="your-key"
export GROK_MODEL="grok-4.20-beta"
export TAVILY_API_URL="https://api.tavily.com"
export TAVILY_API_KEY="your-tavily-key"
```

GuDa 用户只需：

```bash
export GUDA_API_KEY="your-guda-key"
```

也可导入 env-style 文件。CLI 会复制到用户配置目录并限制为当前用户读写；`TAVILY_URL` 会自动规范化为 `TAVILY_API_URL`：

```bash
grok-search config import-env /path/to/credentials.env
grok-search config show --check
```

API Key 不会写入搜索/规划 session，也不会在配置诊断中明文显示。

## 输出协议

默认输出紧凑 JSON：

```json
{"schema_version":1,"ok":true,"command":"model.current","data":{"model":"grok-4.20-beta"},"meta":{}}
```

- `--pretty`：缩进 JSON，适合人工查看。
- `--quiet`：只输出正文、标量或核心数组，适合管道。
- stdout 只包含结果；失败 JSON 和诊断写入 stderr。
- 退出码：`0` 成功、`1` 内部错误、`2` 参数错误、`3` 配置错误、`4` session 不存在/过期、`5` 网络错误、`6` 上游错误。

## 命令

```bash
# 搜索并保存信源 7 天
grok-search search "Python 3.14 最新变化" --extra-sources 3

# 使用 search 返回的 session_id 获取信源
grok-search sources get SESSION_ID

# 抓取网页；Tavily 失败时尝试 Firecrawl
grok-search fetch https://example.com

# 映射站点链接
grok-search map https://docs.example.com --max-depth 2 --limit 100

# 配置与模型
grok-search config show --check
grok-search model list
grok-search model current
grok-search model set MODEL_ID

# session 管理
grok-search session list
grok-search session show SESSION_ID --kind planning
grok-search session delete SESSION_ID --kind sources
grok-search session clear --kind all
```

完整参数通过 `grok-search COMMAND --help` 查看。

## 六阶段 Agent 搜索规划

阶段顺序：

```text
intent → complexity → sub-query → search-term → tool-mapping → execution
```

`plan intent` 创建并返回 `session_id`，后续命令复用该 ID。复杂度 1 需要前三阶段，复杂度 2 需要前五阶段，复杂度 3 需要全部阶段。`sub-query`、`search-term` 和 `tool-mapping` 可多次追加；`--revision` 用于替换对应阶段。

```bash
grok-search plan intent \
  --thought "明确研究目标" \
  --core-question "Python 3.14 对异步编程有哪些变化？" \
  --query-type analytical \
  --time-sensitivity recent

grok-search plan complexity SESSION_ID \
  --thought "需要多来源验证" \
  --level 3 \
  --estimated-sub-queries 3 \
  --estimated-tool-calls 8 \
  --justification "涉及发布说明、文档和迁移影响"
```

## Claude Code 集成

这些命令只管理当前 Git 项目 `.claude/settings.json` 中的 `WebFetch` 和 `WebSearch`：

```bash
grok-search integrations claude status
grok-search integrations claude disable-builtins
grok-search integrations claude enable-builtins
```

## Agent Skill

仓库提供 `skills/search-cli`。它指导 Agent 选择 CLI 命令、解析 JSON、复用 session 并安全处理错误。可安装到：

```text
~/.codex/skills/search-cli
~/.claude/skills/search-cli
~/.pi/agent/skills/search-cli
```

## 从 MCP 版本迁移

| 旧 MCP 工具 | 新 CLI |
|---|---|
| `web_search` | `grok-search search` |
| `get_sources` | `grok-search sources get` |
| `web_fetch` | `grok-search fetch` |
| `web_map` | `grok-search map` |
| `get_config_info` | `grok-search config show --check` |
| `switch_model` | `grok-search model set` |
| `toggle_builtin_tools` | `grok-search integrations claude ...` |
| 六个 `plan_*` 工具 | 六个 `grok-search plan ...` 子命令 |

请删除旧的 `claude mcp` 配置；CLI 不再启动 stdio server。

## 开发验证

```bash
python -m pip install -e '.[dev]'
python -m compileall -q src tests
python -m pytest -q
python -m build
```

[English documentation](docs/README_EN.md)

## License

MIT
