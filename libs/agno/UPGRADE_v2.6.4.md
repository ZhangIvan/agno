# 升级日志: v2.5.9 → v2.6.4

> 分支: `merge-agno-v2.6.4` (基于 `feature/2.5.9-dev-v1`)
> 上游版本: agno v2.6.4 (2026-04-28)
> 合并提交数: 209 commits (v2.5.10 ~ v2.6.4)

---

## 一、上游吸收的新功能

### v2.6.0 — 重大更新

| 功能 | 说明 | 影响 |
|------|------|------|
| **Fallback Models** | Agent/Team 支持备用模型，主模型失败时自动切换 | `agent.py` 新增 `fallback_config` 参数 |
| **ContextProvider** | 新增上下文提供者抽象 (`agno.context`) | 新增模块 |
| **Factories** | AgentFactory, TeamFactory, WorkflowFactory | 新增 `agno.factory` 模块 |
| **HITL (Human-in-the-loop)** | 团队和工作流的审批/暂停/继续机制 | `team.py`, `workflow.py` 新增参数 |
| **多框架支持** | ClaudeAgentSDK, Langgraph, DSPy 集成 | 新增适配器 |
| **Reconnection & Resume** | 断线重连和恢复运行 | `agent.py` 新增方法 |
| **WikiContextProvider** | 文件系统和 Git 后端的 Wiki 上下文 (v2.6.4) | 新增 `agno.context.wiki` 模块 |

### v2.5.10 ~ v2.5.17 — 改进与修复

| 版本 | 关键变更 |
|------|----------|
| v2.5.10 | MLflow 集成、Docling Reader、MCP 竞态条件修复 |
| v2.5.11 | Google 工具包、AgenticChunking 自定义 prompt、工具调用兼容性修复 |
| v2.5.12 | SchedulerTools、Claude server tool blocks 修复 |
| v2.5.13 | ChromaDB 动态批处理、Reader chunk_size 传递、Workflow HITL 修复 |
| v2.5.14 | **Fallback Models (Agent/Team)**、Azure Blob SAS 认证 |
| v2.5.15 | Team Skills 支持、嵌套 Workflow、Post-execution HITL review |
| v2.5.16 | **Knowledge: knowledge_table 读取修复**、LLMsTxtTools、Azure AI Foundry Claude |
| v2.5.17 | CancelledError 处理修复、自定义 db 表名保留、MCP headers 修复 |

### v2.6.1 ~ v2.6.4

| 版本 | 关键变更 |
|------|----------|
| v2.6.1 | Claude Prompt Caching (多块)、ParallelMCPBackend |
| v2.6.2 | Workspace Tools (本地工具包 + HITL 门控) |
| v2.6.3 | WorkspaceContextProvider |
| v2.6.4 | WikiContextProvider (文件系统 + Git 后端) |

---

## 二、定制功能保留状态

以下功能在合并中完整保留，未被覆盖：

| 功能 | 涉及文件 | 状态 |
|------|----------|------|
| lean_references | `agent.py`, `_utils.py`, `_default_tools.py`, `team.py`, `team/_utils.py` | ✅ 保留 |
| user_message_prefix | `agent.py`, `_run.py` (8个调用点) | ✅ 保留 |
| 多云存储后端 | `knowledge/storage/` (7个文件) | ✅ 保留 |
| 知识库页面图片 | `knowledge.py`, `utils.py`, `reader/` | ✅ 保留 |
| Doubao Embedder | `knowledge/embedder/doubao.py` | ✅ 保留 |
| AgentOS Storage Router | `os/routers/storage/` (3个文件) | ✅ 保留 |
| MCP 异步清理 | `tools/mcp/mcp.py` | ✅ 保留 |
| PGVector 重试 | `vectordb/pgvector/pgvector.py` | ✅ 保留 |
| OpenAI 图片注入 | `models/openai/chat.py` | ✅ 保留 |
| 中文支持 (ensure_ascii=False) | `agent/_utils.py` | ✅ 保留 |
| Reader 错误处理 | `knowledge/reader/*.py` (raise ValueError) | ✅ 保留 |

---

## 三、合并中修复的问题

| 问题 | 文件 | 修复内容 |
|------|------|----------|
| `__aenter__` 失败后未抛出异常 | `tools/mcp/mcp.py` | 添加 `raise` 防止 `UnboundLocalError` |
| 重复的空 embedding 检查 | `vectordb/pgvector/pgvector.py` | 删除重复代码块 |
| 顺序 URL 签名 | `knowledge/knowledge.py` | 改为 `asyncio.gather` 并行化 |
| Semaphore 每次调用创建 | `knowledge/knowledge.py` | 提升为实例级 `_sign_semaphore` |
| 未使用的 import (`os`, `logging`) | `_default_tools.py`, `pgvector.py` | 删除 |
| f-string 无变量、bare except | `pdf_reader.py`, `page_capture.py` | 修复 |

---

## 四、代码变更重点说明

### 4.1 agent/_run.py — 冲突最密集

合并方式：上游的 `call_model_with_fallback` / `acall_model_with_fallback` 替代了直接 `model.response()` 调用，我们的 `_user_message_prefix` context manager 正确包裹了新的 fallback 调用。

```
合并前:  with _user_message_prefix(agent, run_messages):
             model_response = agent.model.response(...)
合并后:  with _user_message_prefix(agent, run_messages):
             model_response = call_model_with_fallback(agent.model, agent.fallback_config, ...)
```

涉及 8 个调用点：`_run`, `_run_stream`, `_arun`, `_arun_stream`, `_continue_run`, `_continue_run_stream`, `_acontinue_run`, `_acontinue_run_stream`。

### 4.2 knowledge/knowledge.py — 新增并发控制

URL 签名和文件上传操作现在使用实例级 `asyncio.Semaphore`（`_sign_semaphore`）控制并发，默认值 `upload_concurrency=10`：

```python
# __post_init__ 中初始化一次
self._sign_semaphore = asyncio.Semaphore(self.upload_concurrency)

# 使用时
async with self._sign_semaphore:
    url = await storage.async_sign_url(...)
```

### 4.3 Reader 文件 — 统一错误处理

所有 reader 在合并后保持 `raise ValueError(...)` 的错误处理模式（而非上游的 `return []`）。这确保了错误能正确传播到调用方，而不是静默返回空结果。

---

## 五、升级注意事项

### 5.1 Breaking Changes

- **`/sessions` 端点** (v2.6.0): 现在默认返回所有 session 类型，之前只返回 AgentSession
- **OpenAIChat 默认模型**: 从 `gpt-4o` 变为 `gpt-5.4-mini`（上游变更）。如果需要使用旧行为，需显式指定 `id="gpt-4o"`

### 5.2 新增依赖

- v2.6.4 新增的 ContextProvider、Factory 等功能可能引入新的可选依赖，按需安装
- 检查 `pyproject.toml` 中的依赖变更

### 5.3 测试建议

升级后重点测试以下场景：

1. **知识库检索** — 验证 `lean_references` 正常工作（LLM 收到精简元数据，`run_response.references` 保留完整元数据）
2. **页面图片** — 验证图片上传、URL 签名、检索正常（OSS/COS/TOS/七牛）
3. **Agent 对话** — 验证 `user_message_prefix` 在同步/异步模式下正常
4. **Fallback Models** — 新功能，如使用需测试主模型失败后的切换逻辑
5. **MCP 连接** — 验证异步清理在连接断开时不会崩溃
6. **嵌入重试** — 验证速率限制下的重试逻辑正常

### 5.4 运行验证脚本

```bash
source .venv/bin/activate
bash scripts/format.sh
bash scripts/validate.sh
```

---

## 六、后续合并指南

未来需要合并更新的上游版本时，使用 `agno-merge` skill：

```
/agno-merge v2.7.0
```

该 skill 包含完整的定制功能清单、冲突解决策略、验证步骤和回滚方案。

关键原则：
- **始终使用 `--no-commit`** 合并，先审查再提交
- **优先解决简单冲突**（reader → utils → knowledge → agent），由易到难
- **`_run.py` 是最高风险文件** — 需要手动确认所有 `_user_message_prefix` 包裹点
- **合并后运行 `format.sh` + `validate.sh`** — 确保代码质量
- **检查定制功能完整性** — 用 grep 验证关键标识符存在

---

## 七、冲突解决统计

| 文件 | 冲突数量 | 风险等级 |
|------|----------|----------|
| `agent/_run.py` | 4 | 极高 |
| `knowledge/knowledge.py` | 19 | 中 |
| `knowledge/reader/pdf_reader.py` | 6 | 中 |
| `knowledge/reader/docx_reader.py` | 3 | 中 |
| `knowledge/reader/pptx_reader.py` | 3 | 中 |
| 9 个其他 reader 文件 | 各 1-3 | 低 |
| `models/openai/chat.py` | 自动合并 | 中 |
| `tools/mcp/mcp.py` | 自动合并 | 低 |
| `vectordb/pgvector/pgvector.py` | 自动合并 | 低 |
| **总计** | **~50** | — |
