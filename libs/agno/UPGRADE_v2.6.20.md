# 升级日志: v2.6.18 -> v2.6.20

> 分支: `codex/agno-merge-v2.6.20` (基于 `codex/agno-merge-v2.6.18`)
> 上游版本: agno v2.6.20
> 合并提交: `6088895285954928d9617bdd52b511f51e80209b`
> Parent 1: `809e76cf00d44c18a1d69a5d48f5ae471cca1096` (`codex/agno-merge-v2.6.18`)
> Parent 2: `4ee266d10f1da92cdc6e22b78e81d71c83d27da6` (`v2.6.20`)
> 合并范围: v2.6.19, v2.6.20 传递吸收
> 上游提交数: 47 commits (`v2.6.18..v2.6.20`)
> 核心库变更量: 107 files changed, 9986 insertions(+), 1830 deletions(-)
> 冲突文件: 6 个
> 验证状态: py_compile 通过, ruff check 通过, ruff format --check 通过, git diff --check 通过

说明: 本次先通过 `git fetch upstream --tags` 拉取到 `v2.6.20` tag。由于本机默认解析到的 GitHub IP 在 HTTPS 握手阶段不稳定，补齐 partial clone blob 时使用了可用 GitHub 解析并完成标准 `git merge v2.6.20 --no-commit` 三方合并。

---

## 一、上游吸收的新功能

### 1.1 Run checkpointing 与统一 /continue

| 功能 | PR | 涉及文件 | 说明 |
|------|----|----------|------|
| Run checkpointing | #8092 | `agent/_run.py`, `team/_run.py`, `os/checkpoints.py`, `os/routers/*/router.py` | 支持在工具批次后写入 checkpoint，便于崩溃恢复、继续运行和时间线回放 |
| Unified `/continue` | #8092 | `agent/_run.py`, `team/_run.py`, `run/*`, cookbook checkpoint/time-travel 示例 | Agent/Team 统一 continue、fork、regenerate 相关运行路径 |
| Checkpoint cookbook | #8092 | `cookbook/02_agents/18_checkpointing/`, `cookbook/03_teams/23_checkpointing/` | 新增 Agent/Team checkpoint、恢复、端点示例 |

合并重点: 本 fork 的 `user_message_prefix` 需要包裹所有实际模型调用。上游在非流式模型调用上新增 `after_tool_results=...checkpoint...` 回调，本次合并后同时保留 prefix 包裹和 checkpoint 回调。

### 1.2 StudioTool

| 功能 | PR | 涉及文件 | 说明 |
|------|----|----------|------|
| StudioTool | #7575 | `tools/studio.py`, `cookbook/05_agent_os/studio_tool/` | 支持动态创建、编辑、版本化 Agent/Team/Workflow 组件 |
| Studio cookbook | #7575 | `standalone_studio_agent.py`, `studio_tools_agent.py`, `studio_hitl_agent*.py` | 覆盖本地、AgentOS、HITL 和版本化流程 |

对老项目影响: 这是新增工具，默认不改变现有 Agent/Team 行为。若启用版本化，需关注 `db_version` / `draft_version` 和发布流程。

### 1.3 ClickHouse traces DB

| 功能 | PR | 涉及文件 | 说明 |
|------|----|----------|------|
| ClickHouse DB for traces | #7799 | `db/clickhouse/*`, `vectordb/clickhouse/clickhousedb.py`, `tests/*/clickhouse*` | 新增 ClickHouse trace 存储适配和测试 |
| Trace filter 修复 | #8564 | `os/routers/traces/traces.py` | scoped users 下 trace conditions 使用 canonical key |

对老项目影响: 只有使用 ClickHouse trace 存储或 trace scoped filters 时需要额外验证。

### 1.4 AG-UI 模块拆分与增强

| 功能 | PR | 涉及文件 | 说明 |
|------|----|----------|------|
| AG-UI utils 拆分 | #8364 | `os/interfaces/agui/input.py`, `state.py`, `stream.py`, `handlers.py`, `router.py` | 将原 `utils.py` 拆成输入、状态、流式、handler 模块 |
| AG-UI shared state 示例 | #8364 | `cookbook/05_agent_os/interfaces/agui/shared_state.py` | 新增状态共享示例 |
| Run event union 修复 | #8351/#8358 | `run/team.py`, tests | TeamRunOutputEvent union 增加 post-hook events |

合并影响: 上游将 `media.py` rename 为 `input.py`，本 fork 之前吸收的 AG-UI media 逻辑由上游新模块承接。

### 1.5 Google tools 统一认证

| 功能 | PR | 涉及文件 | 说明 |
|------|----|----------|------|
| Google auth base class | #8267 | `tools/google/base.py`, `tools/google/auth/*`, `calendar.py`, `drive.py`, `gmail.py`, `sheets.py`, `slides.py` | 统一 Google 工具认证、token 和 decorator 逻辑 |
| Google cookbook 重组 | #8267 | `cookbook/91_tools/google/*` | 将 calendar/drive/gmail/slides/workspace 示例按目录拆分 |

对老项目影响: 使用 Google tools 的项目应回归测试 OAuth/service-account/token 读取路径。

### 1.6 新工具和模型能力

| 功能 | PR | 涉及文件 | 说明 |
|------|----|----------|------|
| Scavio search toolkit | #8508 | `tools/scavio.py`, `cookbook/91_tools/scavio_tools.py`, tests | 新增 Scavio 搜索工具 |
| OpenAI chat citations | #5885 | `models/openai/chat.py`, cookbook citations 示例 | 支持 OpenAI chat responses 中的 citations |
| LiteLLM structured output | #5881 | `models/litellm/chat.py`, tests | 将 `response_format` 传给 LiteLLM completion |

---

## 二、上游修复的 Bug

| # | 修复 | PR | 影响范围 |
|---|------|----|----------|
| 1 | `BaseRunOutputEvent.to_dict()` 序列化 singular `image` 字段 | #8524 | run events / media |
| 2 | PIIDetectionGuardrail 自动编译原始 regex 字符串 | #7775 | guardrails |
| 3 | guidance retry 在 plain retry 之后绕过 limit | #8094 | model fallback/retry |
| 4 | knowledge serialization 防止 unicode escaping | #7041 | knowledge serialization |
| 5 | AccuracyResult stats 默认 None，避免 AttributeError | #7674 | eval accuracy |
| 6 | GeminiInteractions lazy import，避免强制 google-genai >= 2.0.0 | #8429 | Google model integrations |
| 7 | async delegate path 中 await cancellation check | #8489 | Agent/Team async delegate |
| 8 | FileTools search/listing 输出 POSIX paths | #7526 | file tools |
| 9 | 避免 OpenAILike providers 自动追加 Chat suffix | #8428 | OpenAI-like providers |
| 10 | 支持传入 SentenceTransformerReranker cross encoder | #8415 | reranker |
| 11 | HackerNews user id 字段读取修复 | #8422 | hackernews tool |
| 12 | MCP ToolResult metadata 合并为单字段，并保留 `structuredContent` | #8580/#7715 | MCP tools |
| 13 | Toolkit.__init__ mutable default argument 修复 | #8253 | tools toolkit |
| 14 | Reddit 写入范围限制到 allowed subreddits | #8539 | reddit tool |
| 15 | MoviePy 输出原子写入 | #8537 | moviepy tool |
| 16 | OS resync path-less routes guard，workflow deep_copy 重建 step_id | #8465 | AgentOS / workflow |
| 17 | quick prompt 数量上限移除 | #8577 | AgentOS config / manifest |
| 18 | numeric enum token type format 修复 | #8554 | tokens / schema formatting |

---

## 三、定制功能保留状态

| 定制功能 | 涉及文件 | 验证结果 |
|----------|----------|----------|
| lean_references | `agent.py`, `_utils.py`, `_default_tools.py`, `team.py`, `team/_utils.py` | `agent.py` 命中 3 处，转换逻辑继续使用 `output_docs` |
| user_message_prefix | `agent.py`, `agent/_run.py` | `_run.py` 中 `with _user_message_prefix` 命中 8 处 |
| 多云存储后端 | `knowledge/storage/` | OSS/COS/TOS/Qiniu 后端文件保留 |
| 知识库页面图片 | `knowledge.py`, `knowledge/utils.py`, `knowledge/reader/` | `page_image_storage` 命中 34 处 |
| Doubao Embedder | `knowledge/embedder/doubao.py` | 文件保留 |
| AgentOS Storage Router | `os/routers/storage/` | 自定义 router 保留 |
| MCP 异步清理 | `tools/mcp/mcp.py` | `_safe_cleanup` / `asyncio.shield` 逻辑保留 |
| PGVector retry | `vectordb/pgvector/pgvector.py` | rate-limit/retry 逻辑保留 |
| OpenAI image injection | `models/openai/chat.py` | 与上游 citations 改动共存 |
| 中文 JSON 支持 | `agent/_utils.py`, `team/_utils.py`, `_default_tools.py` | `ensure_ascii=False` 保留，并补上上游 indent/default 细节 |

---

## 四、冲突解决详情

| 文件 | 冲突点 | 解决方式 | 理由 |
|------|--------|----------|------|
| `libs/agno/agno/agent/_default_tools.py` | knowledge search 结果格式化 | 使用 `output_docs`，同时加入上游 `indent=2`, `default=str`, `allow_unicode=True` | 保留 `lean_references` 瘦身引用，同时吸收上游可读序列化和中文 YAML 支持 |
| `libs/agno/agno/agent/_utils.py` | `convert_documents_to_string()` | 使用 `output_docs`，JSON/YAML 均保留中文，JSON 使用 `indent=2` | 保留本 fork 的 metadata stripping，不回退到 upstream 原始 docs |
| `libs/agno/agno/team/_utils.py` | Team 文档引用格式化 | 与 Agent 侧一致，使用 `output_docs` + `allow_unicode=True` + `indent=2` | Agent/Team 行为保持一致 |
| `libs/agno/agno/agent/_run.py` | import 与四个非流式模型调用 | 同时保留 `contextmanager`、`unix_time`；模型调用保留 `_user_message_prefix` 包裹并传入 `after_tool_results` callback | `user_message_prefix` 是本 fork 核心定制；上游 checkpoint callback 是 v2.6.20 新功能，两者必须叠加 |
| `libs/agno/agno/agent/_run.py` | `save_run_response_to_file()` | 使用上游 `encoding="utf-8"`，保留 `ensure_ascii=False` | 明确 UTF-8 写入，避免中文输出转义或系统默认编码差异 |
| `libs/agno/agno/os/config.py` | `field_validator` import | 接受上游移除 quick prompt cap 后的 import，删除未使用 `field_validator` | v2.6.20 明确移除 quick prompt cap；保留 import 会导致 ruff F401 |
| `libs/agno/pyproject.toml` | version | 更新为 `2.6.20` | 与上游发布版本一致 |

额外清理:
- `cookbook/03_teams/23_remote_agents/README.md` 两处尾随空格。
- `cookbook/05_agent_os/studio_tool/README.md` 多余 EOF 空行。

---

## 五、老项目升级 SDK 注意事项

| 变更 | 影响 | 建议 |
|------|------|------|
| checkpoint/unified continue | 使用 AgentOS run endpoints、continue、regenerate、fork 的项目 | 回归测试 run resume、tool-batch checkpoint、错误恢复 |
| AG-UI utils 拆分 | 直接 import `agno.os.interfaces.agui.utils` 内部函数的项目 | 改用 `input.py`, `state.py`, `stream.py`, `handlers.py` 中的新位置 |
| quick prompt cap 移除 | 依赖最多 3 条 quick prompts 校验的项目 | 如仍需限制，在应用层自行校验 |
| Google tools auth 重构 | 使用 Google Calendar/Drive/Gmail/Sheets/Slides tools 的项目 | 验证 OAuth、service account、token 持久化 |
| MCP ToolResult metadata | 依赖 MCP metadata 字段结构的项目 | 检查 `structuredContent` 和 metadata 字段兼容 |
| ClickHouse traces DB | 使用 traces 存储或 ClickHouse 的项目 | 准备 ClickHouse 连接配置并跑集成测试 |
| StudioTool | 开启动态组件编辑的项目 | 明确权限边界和版本发布流程 |
| OpenAI citations | 需要引用溯源的 OpenAI chat 项目 | 验证 citations 输出结构和下游渲染 |

兼容性矩阵:

| 场景 | v2.6.18 -> v2.6.20 | 是否需要代码调整 |
|------|--------------------|------------------|
| 基础 Agent/Team 对话 | 兼容 | 否 |
| 知识库引用与页面图片 | 兼容，本 fork 定制保留 | 否 |
| 多云图片存储 | 兼容 | 否 |
| AgentOS checkpoint/continue | 新功能增强 | 建议回归测试 |
| AG-UI | 内部模块路径变化 | 若直接引用内部 utils，需要调整 |
| Google tools | 认证架构重构 | 建议回归测试 |
| MCP tools | metadata 行为修复 | 检查下游字段读取 |
| StudioTool | 新增能力 | 按需启用 |

---

## 六、升级检查清单

升级前:
- [ ] 确认当前分支或工作区改动已提交或 stash。
- [ ] 若使用 AgentOS DB/registry，备份组件配置。
- [ ] 若使用 Google tools，准备 OAuth/service-account 测试账号。
- [ ] 若使用 AG-UI，检查是否 import 了内部 `utils.py`。
- [ ] 若启用 checkpoint，准备 run resume/fork/regenerate 测试用例。

升级后:
1. 验证基础 Agent/Team 同步、异步、stream run。
2. 验证 `user_message_prefix` 在 sync/async/stream/continue 中生效。
3. 验证 `lean_references` 对 Agent/Team knowledge references 仍生效。
4. 验证 knowledge page image 上传、签名 URL、多云存储。
5. 验证 AgentOS checkpoint、continue、regenerate、fork endpoints。
6. 验证 Google tools auth、token 保存和刷新。
7. 验证 MCP tool result metadata / structuredContent。
8. 验证 OpenAI citations 与 image injection 共存。

本次已运行:

```bash
python -m py_compile libs/agno/agno/agent/_run.py libs/agno/agno/agent/agent.py libs/agno/agno/team/_run.py libs/agno/agno/team/team.py libs/agno/agno/knowledge/knowledge.py libs/agno/agno/os/config.py libs/agno/agno/os/checkpoints.py
python -m ruff check libs/agno/agno
python -m ruff format --check libs/agno/agno
git diff --cached --check
```

定制功能验证:

```bash
Select-String -Path libs/agno/agno/agent/_run.py -Pattern "with _user_message_prefix" | Measure-Object
Select-String -Path libs/agno/agno/agent/agent.py -Pattern "lean_references" | Measure-Object
Select-String -Path libs/agno/agno/knowledge/knowledge.py -Pattern "page_image_storage" | Measure-Object
```

结果:
- `_user_message_prefix`: 8
- `lean_references` in `agent.py`: 3
- `page_image_storage`: 34

未完整运行:

```bash
./scripts/validate.sh
```

原因: 本次先完成 merge 与核心库静态验证，未跑全量 validate。全量 validate 会覆盖 agno、agno_infra、cookbook，耗时和依赖面更大，建议在 push/PR 前单独运行。

---

## 七、版本对比

| 维度 | v2.6.18 | v2.6.20 |
|------|---------|---------|
| Run lifecycle | 常规 run/continue | checkpoint、unified continue、regenerate、fork 增强 |
| AgentOS storage | 常规 DB/session | 新增 checkpoint 支撑 |
| AG-UI | utils 聚合模块 | input/state/stream/handlers 拆分 |
| Studio | 无内置 StudioTool | 新增 StudioTool 动态组件编排 |
| Traces DB | 常规 trace 存储 | 新增 ClickHouse traces DB |
| Google tools | 分散认证逻辑 | 统一 auth base/decorator/token |
| OpenAI chat | 常规 chat/media | citations 支持 |
| MCP tools | metadata 结构较分散 | ToolResult metadata 合并并保留 structuredContent |
| Knowledge serialization | 本 fork 保留中文 | 上游也补充 unicode escaping 修复，本 fork 定制继续保留 |
| Quick prompts | 存在数量限制 | 上游移除 cap |

---

## 八、上游提交 / PR 摘要

| Commit | PR | 标题 |
|--------|----|------|
| `a7314ee79` | #8092 | feat: run checkpointing + unified /continue |
| `f93287462` | #8531 | chore: Release v2.6.19 |
| `fb5762b11` | #7575 | feat: introduce StudioTool for dynamic agent, team, workflow composition |
| `d036a1138` | #7799 | feat: clickhouse db for traces |
| `e5af3ae64` | #8364 | refactor: split agui/utils.py into focused modules |
| `271bc14e6` | #8267 | feat: refactor Google toolkits with unified auth base class |
| `ced1dd523` | #8508 | feat: add Scavio search toolkit |
| `de216236d` | #5885 | fix: add support for citations in OpenAI chat responses |
| `6bc79123e` | #5881 | fix: pass response_format to LiteLLM completion |
| `0d94dfdff` | #7715 | fix: preserve structuredContent from MCP CallToolResult |
| `6883a4b2f` | #8580 | refactor: consolidate MCP ToolResult metadata into a single field |
| `edf2c3d85` | #8577 | fix: quick prompt cap removal |
| `16ffc5b8a` | #8253 | fix: replace mutable default argument in Toolkit.__init__ |
| `7eae6e5f0` | #8539 | fix: scope reddit writes to allowed subreddits |
| `71a736a4b` | #8537 | fix: write MoviePy outputs atomically |
| `52b1a94a7` | #8564 | fix: canonical conditions key for scoped trace filters |
| `03a221c18` | #8465 | fix: path-less routes in OS resync and workflow deep_copy step_id |
| `4ee266d10` | #8576 | chore: Release v2.6.20 |

---

## 九、合并提交信息

| 项目 | 值 |
|------|----|
| Merge commit | `6088895285954928d9617bdd52b511f51e80209b` |
| Parent 1 | `809e76cf00d44c18a1d69a5d48f5ae471cca1096` |
| Parent 2 | `4ee266d10f1da92cdc6e22b78e81d71c83d27da6` |
| Conflict files | 6 |
| Resolved conflict files | `_default_tools.py`, `_run.py`, `_utils.py`, `os/config.py`, `team/_utils.py`, `pyproject.toml` |
| Verification | py_compile passed; ruff check passed; ruff format --check passed; git diff --check passed |
