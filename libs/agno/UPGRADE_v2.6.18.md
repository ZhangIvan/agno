# 升级日志: v2.6.14 -> v2.6.18

> 分支: `codex/agno-merge-v2.6.18` (基于 `codex/agno-merge-v2.6.14`)
> 上游版本: agno v2.6.18
> 合并提交: `b253f7fe5a80767726045661d767fdb5c3ac79de`
> 上游来源: `v2.6.18` GitHub 源码包导入为本地临时提交 `6e16da639`
> 合并范围: v2.6.15, v2.6.16, v2.6.17, v2.6.18 传递性吸收
> 上游提交数: 16 commits (GitHub compare: `v2.6.14...v2.6.18`)
> 代码变更量: 177 files changed, 5884 insertions(+), 2018 deletions(-)
> 冲突文件: **0 个**
> 验证状态: py_compile 通过, ruff check 通过, format.bat 通过；validate.bat 因本地缺少 mypy 未完成

说明: 命令行环境直连 GitHub 443 失败，Git fetch 也在 schannel TLS 阶段失败。本次通过本机代理下载 `v2.6.18` 源码包，并以 `v2.6.14` 为父提交导入本地临时 upstream commit 后执行三方 merge。

---

## 一、上游吸收的新功能

### 1.1 AgentOS MCP 自定义、作用域化、身份感知工具

| 功能 | PR | 涉及文件 | 说明 |
|------|----|----------|------|
| AgentOS MCP server 工具扩展 | #8404 | `os/mcp.py`, `os/app.py`, `os/config.py` | 支持面向 AgentOS 的 scoped / identity-aware MCP 工具暴露 |
| MCP server 测试 | #8404 | `tests/unit/os/test_mcp_server.py` | 新增 MCP server 行为覆盖 |

这部分是 v2.6.15 的主要功能增量。本 fork 里已有的自定义 `os/routers/storage/` 未被触碰，Storage Router 继续保留。

### 1.2 Parallel Web GA API 适配

| 功能 | PR | 涉及文件 | 说明 |
|------|----|----------|------|
| ParallelBackend 适配 `parallel-web >= 1.0` | #8412 | `context/web/parallel.py` | 更新 context provider 的 Parallel backend 调用方式 |
| ParallelTools 适配 `parallel-web >= 1.0` | #8453 | `tools/parallel.py` | 更新工具层 Parallel API，并补充测试 |

如果项目依赖 `parallel-web`，升级后应使用 GA API 版本。旧版 Parallel API 调用路径不再是推荐路径。

### 1.3 Slack HITL 与 Slack Context 增强

| 功能 | PR | 涉及文件 | 说明 |
|------|----|----------|------|
| Slack HITL DB approval record 修复 | #8386 | `os/interfaces/slack/hitl.py`, `router.py`, `events.py` | required tools 的 approval record 能正确解析 |
| SlackContextProvider token gate | #8411 | `context/slack/provider.py` | 仅在 user token 可用时启用 legacy `search_messages` |
| Slack HITL required approval 示例 | #8386 | `cookbook/05_agent_os/interfaces/slack/hitl_required_approval.py` | 新增 cookbook 示例 |

### 1.4 Registry 与组件重建修复

| 功能 | PR | 涉及文件 | 说明 |
|------|----|----------|------|
| registry 工具结构化去重 | #8450 | `registry/registry.py` | 重建 toolkit 时避免重复注册等价工具 |
| DB component 加载容错 | #8461 | `agent/agent.py`, `team/team.py` | Agent/Team 从 DB 加载失败时跳过损坏组件，继续加载其他组件 |
| provider/name round-trip | #8461 | `models/utils.py` | 新增 `get_model_from_dict()`，按序列化的 provider/name 还原模型 |
| provider catalog 补全 | #8461 | `models/utils.py` | 补充 `ollama-responses`, `openrouter-responses`, `litellm-openai` 等 provider 映射 |

### 1.5 注册模型参数重建保留

| 功能 | PR | 涉及文件 | 说明 |
|------|----|----------|------|
| Preserve Registered Model Params on Reconstruction | #8476 | `models/utils.py`, `tests/unit/models/test_provider_resolution.py` | Agent 重建时复用 live registered model 实例，保留 `azure_endpoint`, `base_url`, API key 等连接参数 |

这是 v2.6.18 的唯一功能性修复。对依赖 registry 重建 Agent/Team 的老项目尤其重要，之前这些运行时参数可能在序列化/反序列化后变成 `None`。

---

## 二、上游修复的 Bug

| # | 修复 | PR | 影响范围 |
|---|------|----|----------|
| 1 | ParallelBackend 支持 `parallel-web >= 1.0` GA API | #8412 | Web context provider |
| 2 | Slack HITL required tools approval record 解析 | #8386 | AgentOS Slack interface |
| 3 | Slack bot token 下禁用 legacy `search_messages` | #8411 | SlackContextProvider |
| 4 | Registry tools 结构化去重 | #8450 | AgentOS registry |
| 5 | ParallelTools 支持 `parallel-web >= 1.0` GA API | #8453 | `tools/parallel.py` |
| 6 | DB component 加载失败不再中断全量加载 | #8461 | `get_agents()`, `get_teams()` |
| 7 | provider/name 序列化后能正确恢复模型类 | #8461 | `models/utils.py` |
| 8 | 已注册模型重建时保留运行时连接参数 | #8476 | registry/model reconstruction |

### 高影响修复: 注册模型参数保留 (#8476)

上游修复点是: 当 Agent 从 registry 或 DB config 重建时，如果模型已经在 registry 中注册，优先复用 live instance，而不是只按 `id` / provider/name 创建一个新实例。这样 Azure/OpenRouter/Ollama 等模型的 endpoint/base_url/API key 等运行时参数不会丢失。

对本 fork 的影响: 该修复集中在 `models/utils.py`，没有覆盖 `models/openai/chat.py` 的图片注入定制逻辑。

### 高影响修复: DB component 加载容错 (#8461)

`get_agents()` 和 `get_teams()` 现在对单个损坏组件使用 `try/except` 包裹，记录错误后继续加载其他组件。AgentOS 列表接口因此更健壮，不会因为一个坏配置导致整页失败。

对本 fork 的影响: `agent/agent.py` 和 `team/team.py` 中的 `lean_references` 参数仍完整保留。

---

## 三、定制功能保留状态

| 定制功能 | 涉及文件 | 验证结果 |
|----------|----------|----------|
| lean_references | `agent.py`, `_utils.py`, `_default_tools.py`, `team.py`, `team/_utils.py` | Agent 3 处 + Team 3 处 |
| user_message_prefix | `agent.py`, `_run.py` | `_user_message_prefix` 9 处 |
| 多云存储后端 | `knowledge/storage/` | `base.py` 存在，OSS/COS/TOS/Qiniu 后端保留 |
| 知识库页面图片 | `knowledge.py`, `knowledge/utils.py`, `knowledge/reader/` | `page_image_storage` 34 处 |
| Doubao Embedder | `knowledge/embedder/doubao.py` | 文件存在 |
| AgentOS Storage Router | `os/routers/storage/` | 自定义 router 保留 |
| MCP 异步清理 | `tools/mcp/mcp.py` | `_safe_cleanup` / `asyncio.shield` 4 处 |
| PGVector retry | `vectordb/pgvector/pgvector.py` | retry / 429 / rate-limit 相关命中 22 处 |
| OpenAI image injection | `models/openai/chat.py` | 文件未被本轮 upstream 变更覆盖 |
| 中文 JSON 支持 | `agent/_utils.py`, `team/_utils.py` | `ensure_ascii=False` 保留 |

---

## 四、冲突解决详情

本次 merge 自动完成，**没有 Git 文本冲突**。

### 4.1 `AGENTS.md` 的特殊处理

当前 fork 分支中 tracked `AGENTS.md` 已被删除，但工作区存在未跟踪的本地 Codex 版 `AGENTS.md`。上游 `v2.6.18` 源码包中也包含 `AGENTS.md`。

处理方式:
- merge 前将未跟踪 `AGENTS.md` 备份到 `.tmp/AGENTS.md.local-before-v2.6.18-merge`
- merge 后恢复本地未跟踪文件
- 不把该文件纳入本次 merge commit

理由: 这是工作区级别的 agent 指令文件，不属于当前 tracked fork 历史；直接纳入会混入与 upstream merge 无关的本地说明变更。

### 4.2 代码冲突

无。上游 v2.6.15-v2.6.18 的核心改动集中在 AgentOS MCP、Slack、Parallel、registry、models utils 等区域，与本 fork 的知识库图片、多云存储、Doubao、PGVector retry、OpenAI image injection 等定制点没有产生文本冲突。

---

## 五、老项目升级 SDK 需要注意的事项

| 变更 | 影响 | 建议 |
|------|------|------|
| `parallel-web >= 1.0` GA API | 使用 ParallelBackend/ParallelTools 的项目 | 确认依赖版本与新 API 匹配 |
| AgentOS MCP server 增强 | 使用 AgentOS MCP 的项目 | 验证 custom/scoped/identity-aware tools 暴露符合预期 |
| Slack HITL approval 修复 | 使用 Slack HITL 的项目 | 重新测试 required tools 审批流 |
| SlackContextProvider token gate | 使用 Slack context 的项目 | bot token 场景下不要依赖 legacy `search_messages` |
| Registry 工具去重 | 使用 AgentOS registry 的项目 | 重复 toolkit 实例将被结构化去重 |
| DB component 加载容错 | Agent/Team 从 DB 加载 | 单个坏配置会被跳过并记录日志 |
| Model provider round-trip | Agent/Team 序列化重建 | provider/name 映射更完整 |
| Registered model params 保留 | 使用注册模型 + 重建 Agent | endpoint/base_url/API key 等运行时参数不再丢失 |

兼容性矩阵:

| 场景 | v2.6.14 -> v2.6.18 | 是否需要代码调整 |
|------|--------------------|------------------|
| 基础 Agent 对话 | 兼容 | 否 |
| 知识库检索和页面图片 | 兼容，定制功能保留 | 否 |
| 多云图片存储 | 兼容 | 否 |
| AgentOS MCP | 新功能增强 | 按需验证 |
| Slack HITL | 行为修复 | 建议回归测试 |
| Parallel tools/context | API 适配新依赖 | 检查依赖版本 |
| Registry/model reconstruction | 行为修复 | 建议测试注册模型重建 |

---

## 六、升级检查清单

升级前:
- [ ] 确认当前分支已提交或备份本地改动
- [ ] 如果使用 AgentOS DB，备份 registry/component 配置
- [ ] 如果使用 Slack HITL，准备 required tools 审批流测试
- [ ] 如果使用 Parallel，确认 `parallel-web` 依赖版本

升级后:
1. 验证基础 Agent/Team 对话。
2. 验证 `lean_references` 对知识库引用仍生效。
3. 验证 `user_message_prefix` 在同步/异步/stream/continue run 中仍生效。
4. 验证知识库页面图片上传、签名 URL、多云存储。
5. 验证 AgentOS MCP server 工具暴露。
6. 验证 Slack HITL required tools approval。
7. 验证 registry 中注册模型重建后 endpoint/base_url/API key 不丢失。

本次已运行:

```bash
python -m py_compile libs/agno/agno/agent/_run.py libs/agno/agno/agent/agent.py libs/agno/agno/knowledge/knowledge.py libs/agno/agno/models/utils.py libs/agno/agno/os/mcp.py libs/agno/agno/registry/registry.py
python -m ruff check libs/agno/agno
scripts\format.bat
```

本次未完整运行:

```bash
scripts\validate.bat
```

原因: 本地环境缺少 `mypy`，脚本在 agno 与 agno_infra validate 阶段提示 `mypy is not installed` 后退出。

定制功能验证命令:

```bash
rg -c "lean_references" libs/agno/agno/agent/agent.py
rg -c "lean_references" libs/agno/agno/team/team.py
rg -c "_user_message_prefix" libs/agno/agno/agent/_run.py
rg -c "page_image_storage" libs/agno/agno/knowledge/knowledge.py
rg -c "_safe_cleanup|asyncio\.shield" libs/agno/agno/tools/mcp/mcp.py
rg -c "rate.limit|rate_limit|Too Many Requests|429|retry" libs/agno/agno/vectordb/pgvector/pgvector.py
```

---

## 七、版本对比

| 维度 | v2.6.14 | v2.6.18 |
|------|---------|---------|
| AgentOS MCP | 基础 MCP server | + scoped / identity-aware custom tools |
| Parallel Web | 旧 API 路径 | 支持 `parallel-web >= 1.0` GA API |
| Slack HITL | required tools approval 存在解析问题 | DB approval record 正确解析 |
| Slack Context | bot token 可能触发 legacy `search_messages` | 按 user token gate |
| Registry | 重复 toolkit 可能重复注册 | 结构化去重 |
| Component loading | 单个坏配置可能影响整体加载 | 单组件失败跳过并记录 |
| Model reconstruction | 注册模型运行时参数可能丢失 | 复用 live registered model instance |
| Cookbooks | 旧学习/AG-UI 示例 | 刷新 08_learning、AG-UI、Slack/MCP 示例 |

---

## 八、上游提交/PR 摘要

| Commit | PR | 标题 |
|--------|----|------|
| `6911b331` | #8380 | chore: apply formatting fixes missed by merged PRs |
| `c52b7419` | #8379 | cookbook: refresh 08_learning and add AgentOS learning demo |
| `5cf1ed7f` | #8383 | chore: update model guidance to gpt-5.5 |
| `ef174763` | #8404 | feat: custom, scoped, identity-aware tools for the AgentOS MCP server |
| `eb48321c` | #8414 | chore: Release v2.6.15 |
| `5f2288f0` | #8412 | fix: update ParallelBackend for parallel-web >= 1.0 GA API |
| `370e321b` | #8421 | chore: release 2.6.16 |
| `19302420` | #8386 | fix: resolve DB approval record for required tools in Slack HITL |
| `815d6853` | #8411 | fix: gate legacy search_messages on user token in SlackContextProvider |
| `440c9193` | #8450 | fix: dedupe registry tools structurally |
| `ff736c76` | #8453 | fix: update ParallelTools for parallel-web >= 1.0 GA API |
| `0c2531eb` | #8461 | fix: resilient DB component loading, provider round-trip, and catalog |
| `6a257850` | #8464 | chore: release 2.6.17 |
| `096d27ad` | #8376 | cookbook: update AG-UI examples to OpenAIResponses and gpt-5.4 |
| `5c5440d3` | #8476 | fix: preserve registered model params when reconstructing agents |
| `140b2b14` | #8479 | chore: release 2.6.18 |

---

## 九、合并提交信息

| 项目 | 值 |
|------|----|
| Merge commit | `b253f7fe5a80767726045661d767fdb5c3ac79de` |
| Parent 1 | `a3836a66684675bcbf4a10d306dccbd57a1cfb9b` (`codex/agno-merge-v2.6.14`) |
| Parent 2 | `6e16da639d0b327feb78acd4c1bf15e692688b8b` (local source import for upstream `v2.6.18`) |
| Conflict files | 0 |
| Verification | py_compile passed; ruff check passed; format.bat passed; validate.bat blocked by missing mypy |
| 临时文件 | `.tmp/` 仅用于下载源码包和 release/compare HTML，不应提交 |

