# Grok Search CLI

面向终端用户及 Codex、Claude Code、Pi 等 CLI Agent 的实时网络搜索工具。它通过 Grok 执行 AI 搜索，通过 Tavily/Firecrawl 抓取网页和发现站点链接，并提供可跨进程继续的六阶段搜索规划协议。

本版本是纯 CLI，已彻底移除 MCP server、FastMCP 和 MCP 配置方式。

## 安装

要求 Python 3.10+。推荐使用 `uvx` 从仓库运行：

```bash
uvx --from git+https://github.com/GuDaStudio/GrokSearch@grok-with-tavily search --help
```

本地开发安装：

```bash
python -m pip install -e .
search --version
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

也可导入 env-style 文件。CLI 会复制到用户配置目录并限制为当前用户读写；`TAVILY_URL` 会自动规范化为 `TAVILY_API_URL`。如果输入的是 Tavily Hikari MCP 地址 `https://<origin>/mcp`，运行时会自动使用其 REST 兼容地址 `https://<origin>/api/tavily`：

```bash
search config import-env /path/to/credentials.env
search config show --check
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
search search "Python 3.14 最新变化" --extra-sources 3

# 使用 search 返回的 session_id 获取信源
search sources get SESSION_ID

# 抓取网页；Tavily 失败时尝试 Firecrawl
search fetch https://example.com

# 映射站点链接
search map https://docs.example.com --max-depth 2 --limit 100

# 配置与模型
search config show --check
search model list
search model current
search model set MODEL_ID

# session 管理
search session list
search session show SESSION_ID --kind planning
search session delete SESSION_ID --kind sources
search session clear --kind all
```

完整参数通过 `search COMMAND --help` 查看。

## 六阶段 Agent 搜索规划

阶段顺序：

```text
intent → complexity → sub-query → search-term → tool-mapping → execution
```

`plan intent` 创建并返回 `session_id`，后续命令复用该 ID。阶段必须按顺序提交；复杂度 1 需要前三阶段，复杂度 2 需要前五阶段，复杂度 3 需要全部阶段。`sub-query`、`search-term` 和 `tool-mapping` 可多次追加，同一 sub-query 可映射多个工具调用；singleton 阶段必须使用 `--revision` 才能替换。revision 会清除依赖该阶段的下游数据。只有依赖、ID、搜索词、工具调用覆盖、无重复 execution ID、并行组无内部依赖且估算均有效时，`plan_complete` 才为 true。

搜索结果若包含无法映射到来源的 `[[N]]` 引用，会在 `meta.warnings` 返回 `missing_citations` 和缺失编号；按段落/句子检测到中英文事实内容未引用时返回 `uncited_content`，其他位置的引用不会掩盖该段落。CLI 不会猜测或伪造来源，等价 URL（包括根路径有无 `/`）会规范化去重。`session show` 是严格只读操作，不刷新七天 TTL。

```bash
search plan intent \
  --thought "明确研究目标" \
  --core-question "Python 3.14 对异步编程有哪些变化？" \
  --query-type analytical \
  --time-sensitivity recent

search plan complexity SESSION_ID \
  --thought "需要多来源验证" \
  --level 3 \
  --estimated-sub-queries 3 \
  --estimated-tool-calls 8 \
  --justification "涉及发布说明、文档和迁移影响"
```

## Claude Code 集成

这些命令只管理当前 Git 项目 `.claude/settings.json` 中的 `WebFetch` 和 `WebSearch`：

```bash
search integrations claude status
search integrations claude disable-builtins
search integrations claude enable-builtins
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
| `web_search` | `search search` |
| `get_sources` | `search sources get` |
| `web_fetch` | `search fetch` |
| `web_map` | `search map` |
| `get_config_info` | `search config show --check` |
| `switch_model` | `search model set` |
| `toggle_builtin_tools` | `search integrations claude ...` |
| 六个 `plan_*` 工具 | 六个 `search plan ...` 子命令 |

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
