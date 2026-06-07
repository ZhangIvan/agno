# 升级日志: v2.6.11 → v2.6.12

> 分支: `merge-agno-v2.6.12` (基于 `merge-agno-v2.6.11`)
> 上游版本: agno v2.6.12 (2026-06-05)
> 合并提交数: 18 commits (v2.6.12)
> 冲突文件: 31 个
> 审查修复: 2 个问题 (1 Critical, 1 High)

---

## 一、上游吸收的新功能

### 新增 Provider: Tuning Engines

| 功能 | 说明 | 影响 |
|------|------|------|
| **Tuning Engines** | 受控 AI 控制面板，OpenAI 兼容端点，支持路由、策略控制、trace 和用量报告 | 新增 `models/tuning_engines/` 模块 |

使用方式：

```python
from agno.models.tuning_engines import TuningEngines

agent = Agent(
    model=TuningEngines(id="gpt-4o", api_key="your-key"),
    ...
)
```

环境变量: `TUNING_ENGINES_API_KEY`、`TUNING_ENGINES_BASE_URL`

### AG-UI 状态事件 (State Events)

| 功能 | 说明 | 影响 |
|------|------|------|
| **StateSnapshotEvent** | AG-UI 接口支持在运行开始时发出初始状态快照 | `os/interfaces/agui/router.py` 新增 `StateSnapshotEvent` |
| **多模态输入保留** | AG-UI 前端发送的图片/音频/视频/文件现在正确传递给 Agent | 新增 `os/interfaces/agui/media.py` |
| **ag-ui-protocol 升级** | 要求 `ag-ui-protocol>=0.1.15` + 新增 `jsonpatch>=1.33` 依赖 | **依赖变更** |

AG-UI 现在支持完整的会话状态管理和多模态输入：

```python
# AG-UI 前端发送的媒体现在能正确传递
response = agent.arun(
    input="描述这张图片",
    images=[Image(url="https://example.com/img.png")],
    ...
)
```

### HTML 文件生成

| 功能 | 说明 | 影响 |
|------|------|------|
| **generate_html_file** | FileGenerationTools 新增 HTML 文件生成能力 | `tools/file_generation.py` 新增方法 |

```python
from agno.tools.file_generation import FileGenerationTools

tools = FileGenerationTools(enable_html_generation=True)
# Agent 可以直接生成 HTML 文件
```

### MiniMax M3 模型

| 功能 | 说明 | 影响 |
|------|------|------|
| **MiniMax M3** | 默认模型从 M2 升级为 M3 | `models/minimax/` 默认值变更 |

---

## 二、上游修复的 Bug

### 稳定性修复

| # | 修复 | 说明 | 影响 |
|---|------|------|------|
| 1 | **AG-UI reasoning 事件顺序** | text message 现在在 reasoning events 之前关闭，修复协议合规性 | `os/interfaces/agui/utils.py` |
| 2 | **ArxivReader API 迁移** | `Client.results()` 替代已废弃的 `search.results()` | `knowledge/reader/arxiv_reader.py` |
| 3 | **session from_dict IndexError** | `runs` 列表为空时 `runs[0]` 抛 IndexError，现在先检查空列表 | `session/agent.py`, `session/team.py` |
| 4 | **Milvus sparse search 参数** | `drop_ratio_build` → `drop_ratio_search`（之前用了错误的参数名，sparse 搜索效果受损） | `vectordb/milvus/milvus.py` |
| 5 | **agentic_state JSON Schema** | `enable_agentic_state` 工具对 `dict` 类型参数生成错误的 schema，现在 `bare dict` → `{type: object, additionalProperties: true}` | `utils/json_schema.py` |
| 6 | **ag-ui-protocol 版本锁定** | `>=0.1.14` 防止 reasoning role validation 错误 | `pyproject.toml` 依赖变更 |

### 详细说明: session from_dict IndexError

此 bug 在反序列化空的 `runs` 列表时触发：

```python
# 修复前 (v2.6.11):
if runs is not None and isinstance(runs[0], dict):  # runs=[] → IndexError!
    ...

# 修复后 (v2.6.12):
if runs and isinstance(runs[0], dict):  # runs=[] → 跳过，安全
    ...
```

**影响范围**: 所有通过 `AgentSession.from_dict()` 或 `TeamSession.from_dict()` 反序列化会话数据的场景，尤其是新创建的空会话。

### 详细说明: Milvus sparse search 参数错误

```python
# 修复前 (v2.6.11) — 使用了错误的参数:
"param": {"metric_type": "IP", "params": {"drop_ratio_build": 0.2}}  # ❌ 这是 build 时参数

# 修复后 (v2.6.12) — 正确的 search 时参数:
"param": {"metric_type": "IP", "params": {"drop_ratio_search": 0.2}}  # ✅ search 时参数
```

**影响**: Milvus sparse vector 搜索（hybrid search）效果可能一直不理想，因为 `drop_ratio_build` 在搜索时被 Milvus 忽略。

---

## 三、定制功能保留状态

以下功能在合并中完整保留，未被覆盖：

| 功能 | 涉及文件 | 验证结果 |
|------|----------|----------|
| lean_references | `agent.py`, `_utils.py`, `_default_tools.py`, `team.py`, `team/_utils.py` | 3 处引用 |
| user_message_prefix | `agent.py`, `_run.py` (8 个方法) | 9 处引用 |
| 多云存储后端 | `knowledge/storage/` (6 个文件) | 全部存在 |
| 知识库页面图片 | `knowledge.py`, `utils.py`, `reader/` | 34 处引用 |
| Doubao Embedder | `knowledge/embedder/doubao.py` | 存在 |
| AgentOS Storage Router | `os/routers/storage/` (3 个文件) | 全部存在 |
| MCP 异步清理 | `tools/mcp/mcp.py` (asyncio.shield) | 存在 |
| PGVector 重试 | `vectordb/pgvector/pgvector.py` | rate-limit 检测存在 |
| OpenAI 图片注入 | `models/openai/chat.py` | 存在 |
| 中文支持 (ensure_ascii=False) | `db/json/json_db.py`, `agent/_utils.py` | 2 处 |
| JWT WebSocket Router | `os/routers/workflows/router.py` | 完整保留 |

---

## 四、合并中修复的问题

| # | 严重性 | 文件 | 问题描述 | 修复内容 |
|---|--------|------|----------|----------|
| 1 | 🔴 Critical | `_run.py` | `_continue_run_stream` 和 `_acontinue_run_stream` 错误包含 output_model 分支，引用不存在的 `generate_response_with_output_model_stream` | 简化为直接调用 `handle_model_response_stream`（与上游一致） |
| 2 | 🟠 High | `_run.py` | `_acontinue_run_stream` 导入了不再使用的 `agenerate_response_with_output_model_stream` | 移除未使用的导入 |

### 详细说明: _continue_run_stream output_model 问题

**问题**: 在之前的 v2.6.11 合并中，`_continue_run_stream`（恢复运行）被错误地加上了 output_model 的 if/else 分支和 `IntermediateRunContentEvent` 处理。但上游的 continue 方法不处理 output_model — 它只在 `_run`/`_arun`/`_run_stream`/`_arun_stream` 四个主运行方法中处理。

**修复**: 将 `_continue_run_stream` 和 `_acontinue_run_stream` 简化为只使用 `_user_message_prefix` 包裹的简单 `handle_model_response_stream` 调用：

```python
# 修复后:
with _user_message_prefix(agent, run_messages):
    for event in handle_model_response_stream(...):
        if not isinstance(event, _CANCEL_BYPASS_EVENT_TYPES):
            raise_if_cancelled(run_response.run_id)
        yield event
```

---

## 五、老项目升级 SDK 需要注意的事项

### 5.1 依赖变更（必须处理）

| 变更 | 说明 | 迁移方式 |
|------|------|----------|
| `ag-ui-protocol>=0.1.15` | AG-UI 依赖最低版本升级 | `pip install ag-ui-protocol>=0.1.15` |
| `jsonpatch>=1.33` | AG-UI 新增依赖（状态管理需要） | `pip install jsonpatch>=1.33` |
| `pip install agno[agui]` | 使用 extras 会自动安装 | 推荐方式 |

如使用 AG-UI 接口：

```bash
pip install agno[agui] --upgrade
```

### 5.2 行为变更（需要验证）

| 变更 | 影响范围 | 说明 |
|------|----------|------|
| **MiniMax 默认模型 M2 → M3** | 使用 MiniMax 且未指定模型 ID 的项目 | 模型行为可能不同，建议显式指定 `id="MiniMax-M2"` 如果需要保持一致 |
| **session from_dict 空列表** | 反序列化新创建的空会话 | **修复了 bug** — 之前会 IndexError，现在安全跳过 |
| **AG-UI 初始状态快照** | 使用 AG-UI 接口的前端 | 新增 `StateSnapshotEvent`，前端需要处理此事件类型 |
| **AG-UI 多模态传递** | 通过 AG-UI 发送图片/音频的项目 | 之前多模态内容被丢弃，现在正确传递 |
| **Milvus sparse search 参数修正** | 使用 Milvus hybrid search 的项目 | `drop_ratio_build` → `drop_ratio_search`，搜索效果可能变化（变好） |
| **agentic_state dict schema** | 使用 `enable_agentic_state=True` 且工具接受 `dict` 参数 | Schema 生成修复，之前可能导致工具调用失败 |

### 5.3 安全注意事项

本次无新增安全问题。但如果从 v2.6.4 或更早版本跳级升级，请参考 `UPGRADE_v2.6.11.md` 中的安全问题章节，尤其是：

- JWT 用户 ID 伪造 (IDOR) — v2.6.6 修复
- SSRF 攻击 — v2.6.7 修复
- 路径穿越 — v2.6.8 修复

### 5.4 兼容性矩阵

| 使用场景 | v2.6.11 → v2.6.12 升级 | 需要改动? |
|----------|----------------------|-----------|
| 基础 Agent 对话 | ✅ 完全兼容 | 否 |
| 知识库检索 | ✅ 完全兼容 | 否 |
| MCP 工具 | ✅ 完全兼容 | 否 |
| AG-UI 前端 | ⚠️ 需处理新事件类型 | 处理 `StateSnapshotEvent` |
| MiniMax 模型 | ⚠️ 默认模型变更 | 显式指定模型 ID |
| Milvus hybrid search | ✅ 修复改善 | 否（效果变好） |
| FileGenerationTools | ✅ 新增 HTML 支持 | 按需启用 |
| session 反序列化 | ✅ 修复空列表 | 否 |
| Tuning Engines | 🆕 新 Provider | 按需使用 |

---

## 六、升级检查清单

### 升级前

- [ ] 确认当前分支已提交所有本地改动
- [ ] 备份数据库（PostgreSQL/MongoDB）
- [ ] 如使用 AG-UI，准备升级 `ag-ui-protocol` 和安装 `jsonpatch`
- [ ] 如使用 MiniMax，检查模型 ID 是否显式指定

### 升级后测试

1. **知识库检索** — 验证 `lean_references` 正常工作
2. **Agent 对话** — 验证 `user_message_prefix` 在所有 8 个调用点正常
3. **AG-UI 接口** — 验证 `StateSnapshotEvent` 处理，多模态输入传递
4. **Milvus hybrid search** — 验证 sparse 搜索效果是否改善
5. **Session 反序列化** — 验证空会话和新会话的 `from_dict` 正常
6. **MCP 连接** — 验证异步清理正常
7. **文件生成** — 验证 HTML 生成功能（如启用）
8. **MiniMax 模型** — 验证默认模型行为（如使用）

### 运行验证命令

```bash
# 语法检查
python -m py_compile libs/agno/agno/agent/_run.py
python -m py_compile libs/agno/agno/tools/mcp/mcp.py
python -m py_compile libs/agno/agno/vectordb/pgvector/pgvector.py

# 格式化 + 代码检查
python -m ruff format libs/agno/agno/
python -m ruff check libs/agno/agno/

# 自定义功能完整性验证
grep -c "lean_references" libs/agno/agno/agent/agent.py        # >= 3
grep -c "_user_message_prefix" libs/agno/agno/agent/_run.py    # >= 9
grep -c "page_image_storage" libs/agno/agno/knowledge/knowledge.py  # >= 20
ls libs/agno/agno/knowledge/storage/base.py                    # 存在
ls libs/agno/agno/knowledge/embedder/doubao.py                 # 存在
```

---

## 七、冲突解决统计

| 文件 | 冲突数 | 风险等级 | 解决策略 |
|------|--------|----------|----------|
| `agent/_run.py` | 8 | 🔴 极高 | `_user_message_prefix` 包裹 + `_CANCEL_BYPASS_EVENT_TYPES` + output_model 分支组合 |
| `tools/mcp/mcp.py` | 3 | 🟠 高 | 保留 `asyncio.shield` + `CancelledError` + 上游 `BaseException` |
| `vectordb/pgvector/pgvector.py` | 1 | 🟠 高 | 保留自定义重试逻辑 + 上游 batch embedding |
| `tools/file_generation.py` | 2 | 🟡 中 | 接受上游 HTML 生成新增功能 |
| `knowledge/reader/arxiv_reader.py` | 1 | 🟡 中 | 合并上游 API 迁移 + 我们的空内容过滤 |
| `knowledge/reader/csv_reader.py` | 1 | 🟡 中 | 保留我们的空内容过滤 |
| `db/json/json_db.py` | 2 | 🟢 低 | 合并 `ensure_ascii=False` + `encoding="utf-8"` |
| `os/routers/workflows/router.py` | 1 | 🟢 低 | 保留 JWT WebSocket Router |
| `reasoning/openai.py` | 1 | 🟢 低 | 接受上游 M3 支持 |
| Cookbook 文件 | 19 | ⬜ 无 | 接受上游（纯示例文件） |
| 其他文件 | 5 | ⬜ 无 | 接受上游 |
| **总计** | **31** | — | — |

---

## 八、新功能快速上手

### 8.1 Tuning Engines Provider

Tuning Engines 提供受控的 AI 网关，可以在 OpenAI 兼容 API 上实现路由、策略控制和审计。

```python
import os
os.environ["TUNING_ENGINES_API_KEY"] = "your-inference-key"

from agno.agent import Agent
from agno.models.tuning_engines import TuningEngines

agent = Agent(
    model=TuningEngines(id="gpt-4o"),
    instructions="你是一个有用的助手",
)

agent.print_response("你好")
```

### 8.2 HTML 文件生成

FileGenerationTools 现在支持生成 HTML 文件：

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.file_generation import FileGenerationTools

agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[FileGenerationTools(enable_html_generation=True)],
    instructions="根据用户需求生成 HTML 文件",
)
```

### 8.3 AG-UI 状态事件

AG-UI 接口现在在运行开始时发出初始状态快照，并在多模态输入时正确传递媒体：

```python
# 前端需要处理新的事件类型
# StateSnapshotEvent — 运行开始时的初始状态
# 多模态内容 (images/audio/videos/files) 现在正确传递给 Agent
```

---

## 九、版本对比: v2.6.11 vs v2.6.12

| 维度 | v2.6.11 | v2.6.12 |
|------|---------|---------|
| 模型提供商 | OpenAI, Anthropic, Google, Mistral, DeepSeek, MiniMax 等 | +Tuning Engines |
| AG-UI | 基础 text 事件 | +StateSnapshotEvent, +多模态输入, +jsonpatch |
| 文件生成 | JSON, CSV, PDF, DOCX, TXT | +HTML |
| MiniMax | 默认 M2 | 默认 M3 |
| Milvus | `drop_ratio_build` (错误参数) | `drop_ratio_search` (正确参数) |
| Session | 空 runs → IndexError | 空 runs → 安全跳过 |
| ag-ui-protocol | 无版本约束 | `>=0.1.15` |
| 代码变更 | — | 13 核心文件, +340/-31 行 |
