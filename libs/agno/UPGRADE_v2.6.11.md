# 升级日志: v2.6.4 → v2.6.11

> 分支: `merge-agno-v2.6.11` (基于 `merge-agno-v2.6.4`)
> 上游版本: agno v2.6.11 (2026-05-28)
> 合并提交数: 169 commits (v2.6.5 ~ v2.6.11)
> 冲突文件: 6 个 (13 处冲突)
> 审查修复: 10 个问题 (8 Critical, 2 High)

---

## 一、上游吸收的新功能

### v2.6.5 — 安全修复 + 上下文增强

| 功能                                 | 说明                                  | 影响                                         |
|------------------------------------|-------------------------------------|--------------------------------------------|
| **Gmail/Calendar ContextProvider** | 新增邮件和日历上下文提供者                       | 新增 `context/gmail/`、`context/calendar/` 模块 |
| **Workflow on_error**              | Condition 步骤支持错误处理                  | `workflow.py` 新增参数                         |
| **MongoDB Scheduler**              | Mongo DB 后端支持定时任务                   | `db/` 新增 scheduler 支持                      |
| **Slack 搜索和媒体工具**                  | SlackContextProvider 支持消息搜索和媒体      | `context/slack/` 新增工具                      |
| **ChromaDB 线程修复**                  | async batch upsert 改用 worker thread | `vectordb/chroma/` 行为变更                    |
| **Toolkit per-tool instructions**  | Toolkit 注册的工具支持独立指令                 | `tools/` 新功能                               |

### v2.6.6 — 安全加固 + Wiki 增强

| 功能                           | 说明                                                   | 影响                              |
|------------------------------|------------------------------------------------------|---------------------------------|
| **Notion Wiki Backend**      | Wiki 上下文支持 Notion 数据库                                | 新增 `context/wiki/notion_ops.py` |
| **Slack HITL 多行审批**          | 支持 confirmation/approval/user_input 等暂停类型            | `os/interfaces/slack/` 大幅扩展     |
| **JWT 用户 ID 绑定**             | WebSocket/Traces/Approvals 的 user_id 绑定到 JWT subject | **安全修复**                        |
| **重复工具名警告**                  | Agent/Team 注册同名工具时发出警告                               | 调试友好                            |
| **Anthropic context window** | 新增 context window 模式匹配                               | `models/anthropic/`             |

### v2.6.7 — 用户隔离 + Gemini Interactions

| 功能                     | 说明                                                     | 影响                                            |
|------------------------|--------------------------------------------------------|-----------------------------------------------|
| **GeminiInteractions** | Google Interactions API 模型（Deep Research, Antigravity） | 新增 `models/google/gemini_interactions.py`     |
| **AgentOS 用户隔离**       | 基于 JWT 的 per-user 数据隔离                                 | **新增 `os/middleware/user_scope.py`**          |
| **SSRF Guard**         | 知识库 reader 的 `allowed_hosts` 白名单验证                     | 新增 `knowledge/reader/utils/url_validation.py` |
| **Qdrant 去重**          | 修复 async_insert 中重复调用 sparse encoder                   | 性能修复                                          |

### v2.6.8 — Antigravity + 路径安全

| 功能                               | 说明                                               | 影响                                              |
|----------------------------------|--------------------------------------------------|-------------------------------------------------|
| **Antigravity Agent**            | Google Antigravity 外部 Agent 集成                   | 新增 `agents/antigravity/`、`tools/antigravity.py` |
| **Path Safety**                  | 文件系统工具的集中路径安全检查                                  | 新增 `utils/path_safety.py`                       |
| **Anthropic server tool blocks** | 保留 message history 中的 server tool content blocks | `models/anthropic/` 修复                          |
| **Parallel MCP User-Agent**      | 向 Parallel MCP 后端发送 User-Agent 标识                | `tools/mcp/`                                    |

### v2.6.9 — PgVector 修复 + 审批增强

| 功能                           | 说明                                 | 影响                        |
|------------------------------|------------------------------------|---------------------------|
| **PgVector prefix_match**    | 前缀匹配搜索修复（之前无效）                     | `vectordb/pgvector/` 重要修复 |
| **PgVector hybrid_search**   | 空 tsquery 使用 literal empty 处理      | `vectordb/pgvector/` 修复   |
| **Approval metadata**        | 审批记录通过 metadata bag 传递给 post-hooks | workflow 新功能              |
| **Claude temperature/top_p** | 修复 `is not None` 判断（之前 0 值被忽略）     | `models/anthropic/` 重要修复  |

### v2.6.10 — 新模型 + 流式增强

| 功能                  | 说明                             | 影响                           |
|---------------------|--------------------------------|------------------------------|
| **Inception Labs**  | 新增 Inception 模型提供商             | 新增 `models/inception/`       |
| **Xiaomi MiMo**     | 新增小米 MiMo 模型提供商                | 新增 `models/xiaomi/`          |
| **YouTools**        | You.com Search API 集成          | 新增 `tools/youcom.py`         |
| **Cancel Run 持久化**  | Agent/Team/Workflow 取消运行持久化    | `agent/`、`team/`、`workflow/` |
| **Registry 知识库**    | AgentOS 注册表支持知识库和 Managers     | 新增 `os/routers/registry/`    |
| **JSON DB UTF-8**   | JSON 文件读写使用 `encoding="utf-8"` | `db/json/` 修复                |
| **NULL Embeddings** | 修复嵌入为空值写入数据库的问题                | `vectordb/` 重要修复             |
| **MCP 连接崩溃**        | MCP 连接失败不再导致 Agent 崩溃          | `tools/mcp/` 重要修复            |

### v2.6.11 — Task API + Manifest

| 功能                           | 说明                   | 影响          |
|------------------------------|----------------------|-------------|
| **Task/Monitor API**         | 新增任务管理和监控 API 工具     | 新增 `tools/` |
| **Manifest**                 | AgentOS 实体级别的 UI 元数据 | `os/` 新功能   |
| **WhatsApp Graph API v25.0** | WhatsApp API 版本升级    | 紧急修复        |

---

## 二、定制功能保留状态

以下功能在合并中完整保留，未被覆盖：

| 功能                        | 涉及文件                                                                      | 验证结果                          |
|---------------------------|---------------------------------------------------------------------------|-------------------------------|
| lean_references           | `agent.py`, `_utils.py`, `_default_tools.py`, `team.py`, `team/_utils.py` | ✅ 3 处引用                       |
| user_message_prefix       | `agent.py`, `_run.py` (8 个方法)                                             | ✅ 9 处引用                       |
| 多云存储后端                    | `knowledge/storage/` (6 个文件)                                              | ✅ 全部存在                        |
| 知识库页面图片                   | `knowledge.py`, `utils.py`, `reader/`                                     | ✅ 34 处引用                      |
| Doubao Embedder           | `knowledge/embedder/doubao.py`                                            | ✅ 存在                          |
| AgentOS Storage Router    | `os/routers/storage/` (3 个文件)                                             | ✅ 全部存在                        |
| MCP 异步清理                  | `tools/mcp/mcp.py` (asyncio.shield)                                       | ✅ 1 处                         |
| PGVector 重试               | `vectordb/pgvector/pgvector.py`                                           | ✅ _async_embed_one_with_retry |
| OpenAI 图片注入               | `models/openai/chat.py`                                                   | ✅ 存在                          |
| 中文支持 (ensure_ascii=False) | `db/json/json_db.py`, `agent/_utils.py`                                   | ✅ 2 处                         |
| JWT WebSocket Router      | `os/routers/workflows/router.py`                                          | ✅ 完整保留                        |

---

## 三、合并中修复的问题

| #  | 严重性         | 文件            | 问题描述                                                             | 修复内容                                         |
|----|-------------|---------------|------------------------------------------------------------------|----------------------------------------------|
| 1  | 🔴 Critical | `mcp.py`      | 重复 `_safe_cleanup` 定义，第一个是死代码                                    | 删除第一个定义                                      |
| 2  | 🔴 Critical | `mcp.py`      | `_safe_cleanup` 缩进错误：`_active_contexts`/`_initialized` 在 `if` 块内 | 取消缩进到方法级                                     |
| 3  | 🔴 Critical | `pgvector.py` | `_async_embed_one_with_retry` 重试耗尽后不 raise，静默吞掉错误                | 添加 `raise`                                   |
| 4  | 🔴 Critical | `router.py`   | `validate_websocket_token` 未导入，运行时 NameError                     | 添加导入                                         |
| 5  | 🔴 Critical | `router.py`   | `handle_workflow_subscription` 缺少 `ws_auth`，JWT 隔离被绕过            | 传递 `ws_auth=ws_auth`                         |
| 6  | 🔴 Critical | `team.py`     | `lean_references` 传给 `_init.__init__()` 但其不接受此参数 → TypeError     | 改为直接赋值                                       |
| 7  | 🟠 High     | `_run.py`     | 同步 `_continue_run_stream` 缺少 output_model 分支                     | 补齐 `IntermediateRunContentEvent` 分支          |
| 8  | 🟠 High     | `_run.py`     | `_acontinue_run_stream` 缺少 `session_state` 参数                    | 补齐 `session_state=run_context.session_state` |
| 9  | ⚠ Warning   | `mcp.py`      | `except (RuntimeError, BaseException)` 冗余模式 (5 处)                | 统一为 `except BaseException`                   |
| 10 | ⚠ Warning   | `_run.py`     | `_CANCEL_BYPASS_EVENT_TYPES` 与 `_user_message_prefix` 需共存        | 正确组合两者                                       |

---

## 四、代码变更重点说明

### 4.1 agent/_run.py — 最高风险，13 处冲突

**核心变化**: 上游新增 `_CANCEL_BYPASS_EVENT_TYPES`（`RunCancelledEvent`, `RunCompletedEvent`），stream
方法在迭代事件时跳过终端事件的取消检查，让 run 自身的 cancel handler 处理。同时新增 `output_model` 分支（
`IntermediateRunContentEvent`）。

**合并策略**: 我们的 `_user_message_prefix` context manager 包裹上游的新逻辑，两者共存：

```python
# 合并前 (我们的代码):
with _user_message_prefix(agent, run_messages):
  for event in handle_model_response_stream(...):
    raise_if_cancelled(run_response.run_id)
    yield event

# 合并后 (组合方案):
with _user_message_prefix(agent, run_messages):
  if agent.output_model is None:
    for event in handle_model_response_stream(...):
      if not isinstance(event, _CANCEL_BYPASS_EVENT_TYPES):
        raise_if_cancelled(run_response.run_id)
      yield event
  else:
    for event in handle_model_response_stream(...):
      if not isinstance(event, _CANCEL_BYPASS_EVENT_TYPES):
        raise_if_cancelled(run_response.run_id)
      if isinstance(event, RunContentEvent):
        if stream_events:
          yield IntermediateRunContentEvent(...)
      else:
        yield event
    for event in generate_response_with_output_model_stream(...):
      if not isinstance(event, _CANCEL_BYPASS_EVENT_TYPES):
        raise_if_cancelled(run_response.run_id)
      yield event
```

涉及 8 个方法：`_run`, `_arun`, `_continue_run`, `_acontinue_run` (非 stream) + `_run_stream`, `_arun_stream`,
`_continue_run_stream`, `_acontinue_run_stream` (stream)。

### 4.2 tools/mcp/mcp.py — 3 处冲突

保留了我们的 `asyncio.shield` + `CancelledError` 处理模式（防止 cancel scope 错误传播），同时采用上游的 `BaseException`
更健壮的异常捕获。`_safe_cleanup` 方法修复了缩进 bug。

### 4.3 vectordb/pgvector/pgvector.py — 1 处冲突

保留了我们的 `_async_embed_one_with_retry` 方法（含 page_image_storage 签名 + 指数退避重试），并修复了重试耗尽后不抛出异常的
bug。我们的 `_async_embed_documents` 使用 semaphore + image/text 分离策略，比上游的简单版本更优。

### 4.4 os/routers/workflows/router.py — 1 处冲突

保留了完整的 JWT WebSocket 路由，修复了 `validate_websocket_token` 缺失导入和 `ws_auth` 安全问题。

---

## 五、老版本 (v2.6.4) 直接使用会遇到的问题

### 5.1 安全问题

| 问题                      | 影响                                                             | v2.6.11 修复                 | 应对方案                  |
|-------------------------|----------------------------------------------------------------|----------------------------|-----------------------|
| **JWT 用户 ID 伪造 (IDOR)** | WebSocket/Traces/Approvals 路由中 user_id 来自请求参数而非 JWT，可被伪造访问他人数据 | JWT subject 绑定 (v2.6.6)    | **必须升级** — 无法通过配置绕过   |
| **WebSocket JWT 隔离绕过**  | reconnect/continue-workflow 未传递 ws_auth，所有权检查被跳过               | ws_auth 传递 (本次合并修复)        | **必须升级** — 涉及本次审查修复   |
| **SSRF 攻击**             | 知识库 reader 可访问内网 URL                                           | allowed_hosts 白名单 (v2.6.7) | 升级或在 reader 前加 URL 过滤 |
| **路径穿越**                | 文件系统相关工具未做路径安全检查                                               | path_safety 工具 (v2.6.8)    | 升级或自行添加路径校验           |

### 5.2 稳定性问题

| 问题                                  | 影响                                             | v2.6.11 修复                  | 应对方案                 |
|-------------------------------------|------------------------------------------------|-----------------------------|----------------------|
| **MCP 连接崩溃**                        | MCP 连接失败导致整个 Agent 崩溃                          | 防止连接失败传播 (v2.6.10)          | **必须升级** — 线上可能频繁触发  |
| **NULL Embeddings**                 | 嵌入失败时写入空值到数据库，导致搜索返回空结果                        | NULL embedding 检测 (v2.6.10) | **必须升级** — 知识库搜索受影响  |
| **PgVector prefix_match 无效**        | `prefix_match=True` 实际未执行前缀匹配                  | 修复实现 (v2.6.9)               | 升级 — 关键搜索功能失效        |
| **嵌入重试静默失败**                        | 重试耗尽后不抛异常，返回无嵌入文档                              | 添加 raise (本次合并修复)           | **必须升级** — 已在本次合并中修复 |
| **MCP _safe_cleanup 缩进 bug**        | _context 为 None 时 _initialized 不重置，MCP 实例状态不一致 | 修复缩进 (本次合并修复)               | **必须升级** — 已在本次合并中修复 |
| **Claude temperature=0 失效**         | `if temperature` 把 0 当 False，使用模型默认温度          | `is not None` 判断 (v2.6.9)   | 升级 — 需要精确控制温度时受影响    |
| **Anthropic server tool blocks 丢失** | message history 中 server tool 内容被清除            | 保留 content blocks (v2.6.8)  | 升级 — 多轮对话异常          |
| **音频文件句柄泄露**                        | OpenAI transcribe_audio 不关闭文件                  | `with open` 模式 (v2.6.10)    | 升级 — 长时间运行可能耗尽句柄     |

### 5.3 功能缺失

| 功能                        | 说明                                 | v2.6.11 新增                  | 影响评估             |
|---------------------------|------------------------------------|-----------------------------|------------------|
| **Output Model (stream)** | stream 方法支持 output_model 生成结构化输出   | IntermediateRunContentEvent | 需要流式结构化输出的场景必须升级 |
| **Cancel Run 持久化**        | Agent/Team/Workflow 运行取消可持久化恢复     | v2.6.10                     | 长时间运行任务必须升级      |
| **用户隔离**                  | AgentOS 基于 JWT 的 per-user 数据隔离     | v2.6.7                      | 多租户部署必须升级        |
| **Slack HITL 审批**         | 完整的 Slack 人机交互审批流程                 | v2.6.5~v2.6.6               | 需要审批流程的团队必须升级    |
| **Inception / MiMo 模型**   | 新模型提供商                             | v2.6.10                     | 按需升级             |
| **GeminiInteractions**    | Google Deep Research / Antigravity | v2.6.7~v2.6.8               | 按需升级             |
| **Antigravity Agent**     | Google 外部 Agent 集成                 | v2.6.8                      | 按需升级             |

### 5.4 兼容性变更

| 变更                             | 说明                                                                | 迁移方式                |
|--------------------------------|-------------------------------------------------------------------|---------------------|
| `_CANCEL_BYPASS_EVENT_TYPES`   | 新增常量，stream 方法中部分事件跳过取消检查                                         | 无需改动 — 自动兼容         |
| `BaseException` 替代 `Exception` | MCP 异常处理升级为 `BaseException`                                       | 无需改动 — 兼容           |
| `session_state` 参数             | `_continue_run_stream` 和 `_acontinue_run_stream` 传递 session_state | 无需改动 — 参数已默认 None   |
| JSON DB `encoding="utf-8"`     | 所有 JSON 文件读写使用 UTF-8 编码                                           | 无需改动 — 兼容改善         |
| Workflow `on_error`            | Condition 步骤新增错误处理                                                | 需要时配置 `on_error` 参数 |
| Registry 知识库支持                 | AgentOS 注册表新增知识库配置                                                | 需要时配置               |

---

## 六、升级注意事项

### 6.1 升级前检查清单

- [ ] 确认当前分支已提交所有本地改动
- [ ] 备份数据库（如使用 PostgreSQL/MongoDB）
- [ ] 检查 `pyproject.toml` 中的依赖变更
- [ ] 如使用 AgentOS，确认 JWT 配置正确（新增用户隔离依赖 JWT）
- [ ] 如使用 PgVector，确认 `prefix_match` 参数行为符合预期

### 6.2 升级后重点测试

1. **知识库检索** — 验证 `lean_references` 正常（LLM 收到精简元数据，`run_response.references` 保留完整元数据）
2. **页面图片** — 验证图片上传、URL 签名、检索正常（OSS/COS/TOS/七牛）
3. **Agent 对话** — 验证 `user_message_prefix` 在同步/异步/stream 模式下正常
4. **MCP 连接** — 验证异步清理在连接断开时不崩溃，重试逻辑正常
5. **嵌入重试** — 验证速率限制下的指数退避重试正常，重试耗尽后正确抛出异常
6. **WebSocket** — 验证 JWT 认证流程、reconnect/continue-workflow 的用户隔离
7. **Cancel Run** — 如使用取消功能，测试持久化和恢复
8. **Output Model** — 如使用 output_model，测试 stream 模式下的结构化输出
9. **AgentOS 用户隔离** — 多用户场景下数据隔离验证

### 6.3 运行验证命令

```bash
# 语法检查（所有冲突文件）
python -m py_compile libs/agno/agno/agent/_run.py
python -m py_compile libs/agno/agno/tools/mcp/mcp.py
python -m py_compile libs/agno/agno/vectordb/pgvector/pgvector.py

# 格式化 + 代码检查
bash scripts/format.sh
bash scripts/validate.sh

# 自定义功能完整性验证
grep -c "lean_references" libs/agno/agno/agent/agent.py        # >= 3
grep -c "_user_message_prefix" libs/agno/agno/agent/_run.py    # >= 9
grep -c "page_image_storage" libs/agno/agno/knowledge/knowledge.py  # >= 20
ls libs/agno/agno/knowledge/storage/base.py                    # 存在
ls libs/agno/agno/knowledge/embedder/doubao.py                 # 存在
```

---

## 七、冲突解决统计

| 文件                               | 冲突数    | 风险等级  | 解决策略                                                                      |
|----------------------------------|--------|-------|---------------------------------------------------------------------------|
| `agent/_run.py`                  | 7      | 🔴 极高 | `_user_message_prefix` + `_CANCEL_BYPASS_EVENT_TYPES` + output_model 分支组合 |
| `tools/mcp/mcp.py`               | 3      | 🟠 高  | 保留 asyncio.shield + 采用 BaseException                                      |
| `os/routers/workflows/router.py` | 1      | 🟠 中  | 保留完整 JWT WebSocket Router                                                 |
| `vectordb/pgvector/pgvector.py`  | 1      | 🟡 中  | 保留 _async_embed_one_with_retry + 修复 raise                                 |
| `db/json/json_db.py`             | 2      | 🟢 低  | 合并 ensure_ascii=False + encoding="utf-8"                                  |
| `knowledge/reader/csv_reader.py` | 1      | 🟢 低  | 合并 \n 分隔符 + 空内容过滤                                                         |
| **总计**                           | **13** | —     | —                                                                         |

---

## 八、后续合并指南

未来需要合并更新的上游版本时，使用 `agno-merge` skill：

```
/agno-merge v2.7.0
```

关键原则：

- **始终使用 `--no-commit`** 合并，先审查再提交
- **合并后运行审查工作流** — 使用 ultracode 模式进行多维度并行审查
- **`_run.py` 是最高风险文件** — 需要手动确认所有 `_user_message_prefix` 包裹点 + `_CANCEL_BYPASS_EVENT_TYPES` 组合
- **检查 sync/async 一致性** — 确保 stream 和非 stream、sync 和 async 四个变体保持一致
- **检查 `session_state` 传递** — 上游可能会在更多方法中需要此参数
- **合并后运行 `format.sh` + `validate.sh`** — 确保代码质量
- **检查定制功能完整性** — 用 grep 验证关键标识符存在

---

## 九、版本对比: v2.6.4 vs v2.6.11

| 维度         | v2.6.4                                         | v2.6.11                                                       |
|------------|------------------------------------------------|---------------------------------------------------------------|
| 模型提供商      | OpenAI, Anthropic, Google, Mistral, DeepSeek 等 | +Cloudflare, +Inception, +MiniMax, +MiMo, +GeminiInteractions |
| AgentOS 安全 | 基础 os_security_key                             | +JWT 用户隔离, +RBAC, +IDOR 防护                                    |
| 知识库        | 基础检索 + 自定义增强                                   | +SSRF 防护, +路径安全                                               |
| MCP        | 基础连接 + 自定义 async cleanup                       | +连接失败防护, +BaseException                                       |
| Stream     | 基础流式 + _user_message_prefix                    | +_CANCEL_BYPASS_EVENT_TYPES, +output_model stream             |
| AgentOS 接口 | HTTP REST                                      | +Slack HITL, +WebSocket JWT                                   |
| PgVector   | 自定义重试逻辑                                        | +prefix_match 修复, +NULL embedding 防护                          |
| 新增文件       | —                                              | +32 个新模块文件                                                    |
