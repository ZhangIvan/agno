# 升级日志: v2.6.12 → v2.6.14

> 分支: `merge-agno-v2.6.14` (基于 `merge-agno-v2.6.12`)
> 上游版本: agno v2.6.14 (合并提交 `6741a7940`)
> 合并方式: **跳过 v2.6.13 直接合并到 v2.6.14**，v2.6.13 的变更被传递性吸收
> 上游提交数: 18 commits (v2.6.12..v2.6.14)
> 冲突文件: **2 个** (远少于 v2.6.12 的 31 个)
> 审查修复: 0 个 (无新引入问题)

---

## 一、上游吸收的新功能

### 1.1 Learnings CRUD 端点 (AgentOS) 🆕

| 功能 | 说明 | 影响 |
|------|------|------|
| **Learnings Router** | AgentOS 新增完整的 learnings（学习记忆）CRUD 端点 | 新增 `os/routers/learnings/` 模块（router + schema） |
| **学习 ID 构建** | 统一的 `build_learning_id` 逻辑 | `learn/utils.py` |
| **记忆 Schema 重构** | `learn/schemas.py` 记忆结构增强 | DB schema 迁移（见 5.1） |

```python
# 新增的 AgentOS 端点（自动注册）
# GET    /os/learnings          — 列出学习记忆
# POST   /os/learnings          — 创建学习记忆
# GET    /os/learnings/{id}     — 获取单个
# PUT    /os/learnings/{id}     — 更新
# DELETE /os/learnings/{id}     — 删除
```

### 1.2 Workflows HITL 的 Socket 支持 🆕

| 功能 | 说明 | 影响 |
|------|------|------|
| **`acontinue_run` 原生支持 background/websocket** | 恢复暂停的工作流时支持 WebSocket 流式传输 | `workflow/workflow.py` 新增 `_acontinue_run_background_stream_ws` |
| **事件缓冲与重连** | 通过 `WebSocketHandler` 透传 `_handle_event`，支持客户端重连 | 解决了定制分支中手动绕过方案的缺陷（见四） |

这是本次合并中**最重要的定制功能整合点** — 详见第四节。

### 1.3 AgentOS 注册表自动填充 🆕

| 功能 | 说明 | 影响 |
|------|------|------|
| **auto-populate registry** | 从 agents/teams/workflows 自动填充 AgentOS 注册表 | `os/app.py`, `registry/registry.py`, `os/utils.py` |

```python
# AgentOS 现在自动发现并注册本地的 Agent / Team / Workflow
# 无需手动注册即可通过 /os 端点访问
```

### 1.4 Context Provider 子代理事件流 🆕

| 功能 | 说明 | 影响 |
|------|------|------|
| **stream sub-agent events** | context provider 的 update 工具现在流式输出子代理事件 | `context/provider.py`, `context/wiki/provider.py` |

### 1.5 Slack App Manifest (AgentOS 接口) 🆕

| 功能 | 说明 | 影响 |
|------|------|------|
| **Slack manifest** | AgentOS 提供 Slack 应用 manifest JSON | 新增 `os/interfaces/slack/manifest.json`, `os/app.py` |

---

## 二、上游修复的 Bug

### 稳定性修复

| # | 修复 | PR | 说明 | 影响 |
|---|------|----|------|------|
| 1 | **Gemini 线程安全竞争** | #7797 | 移除每响应的 Gemini 客户端清理（导致并发竞争） | `models/base.py` 大幅重构（1391 行变更） |
| 2 | **MCPTools 会话泄漏** | #8230 | refresh 后的 MCPTools session 在 call task 中未关闭 | `tools/mcp/mcp.py`, `tools/mcp/multi_mcp.py` |
| 3 | **MultiMCP 连接失败清理** | #8163 | 部分连接失败时残留资源未清理 | `tools/mcp/multi_mcp.py` |
| 4 | **content hash 忽略 metadata** | #8310 | `upsert=False` 插入相同文档时 metadata 不同却被合并 | `knowledge/knowledge.py` |
| 5 | **json_schema Optional dataclass** | #8329 | 无 type 的 Optional dataclass 字段生成错误 schema | `utils/json_schema.py` |
| 6 | **工具参数空白丢失** | #8131 | 工具调用参数的空白字符被错误去除 | `utils/functions.py` |
| 7 | **DaytonaTools 路径注入** | #8289 | shell 路径未加引号，存在注入风险 | `tools/daytona.py` |
| 8 | **followup JSON 指令** | #8357 | `json_object` 模式的 provider 在 followup prompt 中缺少 JSON 指令 | `agent/` |

### 详细说明: Gemini 线程安全竞争 (#7797)

这是本次合并中代码变更量最大的修复。上游在每次模型响应后清理 Gemini 客户端，但这在并发场景下引发竞争条件：

```python
# 问题 (v2.6.12): 每响应都重建/清理客户端 → 并发请求相互踩踏
# 修复 (v2.6.14): 客户端生命周期与 model 实例绑定，不在 per-response 层清理
```

**影响**: `models/base.py` 因此有 1391 行变更。本次合并**自动合并成功**，定制代码（`models/openai/chat.py` 的图片注入）未受影响。

### 详细说明: content hash 包含 metadata (#8310)

```python
# 修复前 (v2.6.12): hash 仅基于路径，metadata 不同也被判为重复
hash = f"{path}"

# 修复后 (v2.6.14): metadata 纳入 hash
hash_parts = [path, json.dumps(metadata, sort_keys=True, default=str)]
```

**影响**: 知识库 `upsert=False` 插入行为修正 — 相同路径但不同 metadata 的文档不再被错误折叠。定制功能（page_image_storage）与此变更**正确合并**（保留了 `os` + `json` 双导入，见四）。

---

## 三、定制功能保留状态

所有定制功能在合并中完整保留，**均未被覆盖**：

| 功能 | 涉及文件 | 验证结果 |
|------|----------|----------|
| lean_references | `agent.py`, `_utils.py`, `_default_tools.py`, `team.py`, `team/_utils.py` | Agent 3 处 + Team 3 处引用 |
| user_message_prefix | `agent.py`, `_run.py` (8 个方法) | 9 处引用 |
| 多云存储后端 | `knowledge/storage/` (6 个文件) | 全部存在 |
| 知识库页面图片 | `knowledge.py`, `utils.py`, `reader/` | 34 处引用 |
| Doubao Embedder | `knowledge/embedder/doubao.py` | 存在 |
| AgentOS Storage Router | `os/routers/storage/` (3 个文件) | 全部存在 |
| MCP 异步清理 | `tools/mcp/mcp.py` (asyncio.shield + `_safe_cleanup`) | 4 处引用，完整保留 |
| PGVector 重试 | `vectordb/pgvector/pgvector.py` | rate-limit 检测存在 |
| OpenAI 图片注入 | `models/openai/chat.py` | 存在（models/base.py 重构未触及） |
| 中文支持 (ensure_ascii=False) | `_utils.py` 等 | 3 处 |
| JWT WebSocket Router | `os/routers/workflows/router.py` | 完整保留（见四） |

---

## 四、冲突解决详情（2 个文件）

本次合并冲突极少（仅 2 个），全部为低风险：

### 4.1 `knowledge/knowledge.py` — 导入冲突 🟢

upstream 新增 `import json`（用于 content hash），与定制的 `import os`（用于存储路径）冲突。两者都被实际使用，**保留双导入**：

```python
# 合并后:
import io
import json   # upstream (content hash)
import os     # custom (storage: os.path, os.unlink)
import time
```

### 4.2 `os/routers/workflows/router.py` — 绕过方案替换为原生支持 🟢

这是本次合并的关键整合点。定制分支之前用**手动后台任务绕过** WebSocket 续传：

```python
# 定制分支 (v2.6.12) — 临时绕过方案 + 大段 TODO:
async def _drive_continue_stream():
    response_stream = await workflow.acontinue_run(stream=True, ...)
    async for event in response_stream:
        await websocket.send_text(json.dumps(event, ...))  # 直接转发

asyncio.create_task(_drive_continue_stream())
# TODO: acontinue_run() 不支持 background/websocket ...
# 这绕过了 _handle_event 的事件缓冲，重连客户端收不到这些事件
```

v2.6.14 上游实现了 TODO 描述的**正式修复** — `acontinue_run` 现在原生支持 `background` / `websocket` / `enable_websocket` 参数，并通过 `_acontinue_run_background_stream_ws` 透传 `WebSocketHandler`：

```python
# 合并后 (v2.6.14) — 采用上游原生实现:
await workflow.acontinue_run(
    run_response=existing_run,
    session_id=session_id,
    stream=True,
    stream_events=True,
    background=True,
    websocket=websocket,
    enable_websocket=True,
)
```

**为何丢弃定制方案**: 上游实现正是定制 TODO 中列出的 4 步正式修复（添加 background/websocket 参数 → 添加 websocket_handler 参数 → 透传 _handle_event → 新增 background_stream 方法）。定制绕过方案自身承认"重连客户端收不到这些事件"，上游方案修复了这一缺陷。**未丢失任何定制业务逻辑** — JWT WebSocket Router 等其余代码完整保留。

---

## 五、老项目升级 SDK 需要注意的事项

### 5.1 数据库 Schema 变更（需评估）

| 变更 | 说明 | 迁移影响 |
|------|------|----------|
| **learn/schemas.py 记忆结构重构** | 学习记忆表结构增强 | 如使用了 `learn/` 模块，需检查 DB 迁移 |
| **db/base.py 新增** | 数据库基类抽象层（+234 行） | 内部重构，对调用方透明 |
| **postgres/mongo/sqlite 适配器增强** | 三套数据库适配器同步增强 | 内部实现，接口不变 |

> **建议**: 升级后对 PostgreSQL/MongoDB 执行现有迁移脚本，验证 learnings 表结构。

### 5.2 行为变更（需要验证）

| 变更 | 影响范围 | 说明 |
|------|----------|------|
| **content hash 含 metadata** | 知识库 `upsert=False` 插入 | 相同路径不同 metadata 不再折叠（修复 bug） |
| **Gemini 并发模型** | 使用 Gemini 且有并发请求 | **修复线程安全问题** — 之前并发可能竞争踩踏 |
| **MCP 会话清理** | 使用 MCPTools/multi_mcp | 连接失败时资源清理更彻底（修复泄漏） |
| **工具参数空白保留** | 工具参数含空白字符 | 空白现在被正确保留（之前被去除） |
| **acontinue_run 新增参数** | 调用工作流续传的代码 | 新增可选参数，向后兼容 |
| **registry 自动填充** | 使用 AgentOS | agents/teams/workflows 现在自动注册到 /os |

### 5.3 安全注意事项

| 项目 | 状态 |
|------|------|
| DaytonaTools shell 路径注入 (#8289) | ✅ 已修复（路径加引号） |
| 其余安全项 | 本次无新增问题 |

如从 v2.6.10 或更早版本跳级升级，请参考 `UPGRADE_v2.6.11.md` 与 `UPGRADE_v2.6.12.md` 的安全章节（JWT IDOR、SSRF、路径穿越）。

### 5.4 兼容性矩阵

| 使用场景 | v2.6.12 → v2.6.14 升级 | 需要改动? |
|----------|----------------------|-----------|
| 基础 Agent 对话 | ✅ 完全兼容 | 否 |
| 知识库检索 | ✅ 完全兼容（hash 行为改善） | 否 |
| MCP 工具 | ✅ 完全兼容（清理更彻底） | 否 |
| Gemini 并发 | ✅ 修复线程安全 | 否 |
| Workflows HITL (WebSocket) | ✅ 改善（重连可收事件） | 否 |
| Learnings 模块 | ⚠️ schema 变更 | 检查 DB 迁移 |
| AgentOS | 🆕 自动注册 + learnings 端点 | 按需使用 |
| Multi-cloud 存储 | ✅ 完全兼容 | 否 |

---

## 六、升级检查清单

### 升级前

- [ ] 确认当前分支已提交所有本地改动
- [ ] 备份数据库（PostgreSQL/MongoDB）
- [ ] 如使用 `learn/` 模块，准备检查 learnings 表结构迁移

### 升级后测试

1. **知识库检索** — 验证 `lean_references` 正常、page_image_storage 正常
2. **Agent 对话** — 验证 `user_message_prefix` 在所有 8 个调用点正常
3. **Workflows HITL** — 验证 WebSocket 续传 + 客户端重连能收到事件（**重点验证本次整合点**）
4. **MCP 连接** — 验证异步清理（asyncio.shield）+ 连接失败清理
5. **Gemini 并发** — 验证多并发请求不再竞争
6. **AgentOS** — 验证 registry 自动填充 + learnings 端点

### 运行验证命令

```bash
# 语法检查
python -m py_compile libs/agno/agno/agent/_run.py
python -m py_compile libs/agno/agno/models/base.py
python -m py_compile libs/agno/agno/workflow/workflow.py
python -m py_compile libs/agno/agno/tools/mcp/mcp.py

# 格式化 + 代码检查
python -m ruff format libs/agno/agno/
python -m ruff check libs/agno/agno/

# 自定义功能完整性验证
grep -c "lean_references" libs/agno/agno/agent/agent.py        # >= 3
grep -c "_user_message_prefix" libs/agno/agno/agent/_run.py    # >= 9
grep -c "page_image_storage" libs/agno/agno/knowledge/knowledge.py  # >= 20
grep -c "_safe_cleanup\|asyncio\.shield" libs/agno/agno/tools/mcp/mcp.py  # >= 4
ls libs/agno/agno/knowledge/storage/base.py                    # 存在
ls libs/agno/agno/knowledge/embedder/doubao.py                 # 存在

# 单元测试（本次合并已通过 333 项）
python -m pytest libs/agno/tests/unit/ -q
```

---

## 七、冲突解决统计

| 文件 | 冲突数 | 风险等级 | 解决策略 |
|------|--------|----------|----------|
| `knowledge/knowledge.py` | 1 | 🟢 低 | 保留双导入 `json` + `os` |
| `os/routers/workflows/router.py` | 1 | 🟢 低 | 采用上游原生 `acontinue_run(background, websocket)`，丢弃定制绕过方案 |
| **总计** | **2** | — | — |

> 对比 v2.6.12 合并的 31 个冲突，本次冲突极少，主要因为 v2.6.14 的改动集中在 `models/base.py`、`db/`、`learn/` 等与定制功能交集较小的模块，且 `agent/_run.py`、`agent/agent.py` **未被上游触及**。

---

## 八、版本对比: v2.6.12 vs v2.6.14

| 维度 | v2.6.12 | v2.6.14 |
|------|---------|---------|
| AgentOS | 基础端点 | +learnings CRUD + registry 自动填充 + Slack manifest |
| Workflows HITL | acontinue_run 无 socket 支持 | +原生 background/websocket + 重连事件缓冲 |
| Context Provider | 基础 | +子代理事件流 |
| Gemini | per-response 清理（并发竞争） | 客户端生命周期绑定（线程安全） |
| MCP | 基础清理 | +连接失败资源清理 + 会话泄漏修复 |
| 知识库 hash | 仅基于路径 | +metadata（修复 upsert 折叠） |
| json_schema | Optional dataclass 字段错误 | 正确处理 |
| 工具参数 | 空白被去除 | 空白保留 |
| models/base.py | — | 大幅重构（+1391 行） |
| 代码变更 | — | 41 文件, +4587/-830 行 |
| 冲突数 | 31 | **2** |

---

## 九、合并提交信息

```
commit 6741a7940
Merge: eae7be464 (fork) ← 0c6469489 (v2.6.14)
merge: absorb upstream agno v2.6.14 features and fixes
```

验证状态：py_compile 全通过 · ruff check + format 干净 · 333 单元测试通过（1 跳过：motor 未安装）。
