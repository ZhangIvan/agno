# 升级日志: v2.8.6 -> v2.8.7

> 分支: `merge-agno-v2.8.7`（基于 `merge-agno-v2.8.6`）
> 上游版本: agno v2.8.7
> 合并提交: `c76b6c09a3a5a9a34e55017a77dcf7a06b171198`
> Parent 1: `ac4d7a286b2d74c01ab1bedcd20fc2d327bf6622`（`merge-agno-v2.8.6` 分支末尾，含前一轮升级的全部定制修复）
> Parent 2: `03d2bf051bfdd3d4a04becce6977712070b30c4d`（`v2.8.7`）
> 上游提交数: 14 commits（`v2.8.6..v2.8.7`），10 个涉及 `libs/agno/agno/`
> 核心库变更量: 27 files changed, +3132/−66（含约 460 行新测试）
> 冲突文件: 1 个（`models/base.py`）
> 验证状态: `ruff check` 全部通过；`mypy` **0 个发现**（较上一轮的"1 个确认存量问题"更进一步，见下）；1764/1766 相关单测通过（2 个失败与本次无关，延续上一轮已确认的存量问题）

**版本选择说明**：升级前 `git fetch upstream --tags` 发现上游同时存在 `v2.8.7`（稳定版）和 `v3.0.0a1`（`feat/v3.0` 分支上的 alpha 预发布版）。按要求只走稳定版路线，`v3.0.0a1` 未纳入本次合并范围。

---

## 一、上游改动内容

| # | 改动 | PR | 性质 |
|---|---|---|---|
| 1 | `Team.load()` 在 SqliteDb 上必现崩溃（`load_component_graph() got an unexpected keyword argument 'label'`）| #9337 | **真实 bug 修复**——只要用 SqliteDb 调用过 `Team.load()`，之前 100% 复现 |
| 2 | Cohere 模型丢弃值为 0 的采样参数（如 `temperature=0`） | #9300 | 修复 |
| 3 | 工具调用结果反序列化时，顶层 confirmation 状态未透传给 `tool_execution` | #9351 | 修复（HITL 相关） |
| 4 | 同步 scheduler 数据库调用阻塞事件循环 | #9370 | 修复 |
| 5 | 音频类工具结果处理更健壮；配套把 `models/base.py` 里生成媒体跟进消息的逻辑简化（见二） | #9331 | 修复 |
| 6 | 新增 `AdvisorTools`（让 agent 调用"顾问模型"获取反馈意见） | #7196 | 新功能，本项目未使用 |
| 7 | 新增 `OpenRouteService` 工具包（路径规划） | #9287 | 新功能，本项目未使用 |
| 8 | `StudioTools` 增加组件感知的调度工具与历史参数 | #9352 | 新功能，本项目生产代码不经过 AgentOS/Studio |
| 9 | 持久化组件的工具反序列化支持按 toolkit 归属重新绑定同名函数 | #9358 | 内部改进，见二 |
| 10 | `FileSystemTools` 允许覆盖 toolkit 名称 | #9363 | 本项目未使用 FileSystem |

---

## 二、冲突解决详情（唯一一处）

**`libs/agno/agno/models/base.py`** —— `Model._handle_function_call_media()`：这个方法负责在工具调用产出图片/视频/音频/文件时，生成一条跟进的 user 消息把媒体带给模型。

- 我们这边（继承自上一轮 v2.8.6 合并的状态）：会把触发媒体的原始工具结果文本拼进跟进消息（`media_source_contents` → `content_parts` → `" ".join(content_parts)`）。
- 上游 v2.8.7（PR #9331）：整段简化成固定文案 `"The tool call above generated the attached media."`，**不是简单的文案措辞调整**——PR 描述指出旧逻辑在模型不支持某种媒体类型（比如 `OpenAIResponses` 不支持音频输入）时会拼出一条空的、语义不完整的消息，可能让模型误以为要用户"重新分享内容"而不是确认工具调用已完成，是一个真实的非确定性 bug。

**处理方式**：没有只改冲突的那一行，而是采纳了上游的完整简化版本，把 `has_media`/`media_source_contents`/`content_parts`/`source_info` 这一整套现在已经不需要的中间变量一起删掉了（用 `diff` 逐字节比对过，合并后的函数体跟 v2.8.7 tag 完全一致）。**附带收获**：上一轮升级指南（`UPGRADE_v2.8.6.md` 第五节）里明确记录过一个"确认是纯上游存量、本次不处理"的 mypy 发现，就出在这段被删掉的代码里（`media_source_contents.append(result_message.content)` 那行的类型不严谨问题）——这次跟着上游的删除自然消失了，不需要再单独处理。`validate.sh` 的 mypy 检查这次是真正的 0 发现（`Success: no issues found in 973 source files`），比上一轮更干净。

其余 26 个文件全部自动合并，均为新增文件（`tools/advisor.py`、`tools/openrouteservice.py` 等）或与本次改动区域不重叠。

---

## 三、定制功能保留状态

跟上一轮完全一致，因为这次改动没有触及任何一处定制文件：

| 定制功能 | 校验结果 |
|---|---|
| lean_references | `agent.py` 命中 3 处 |
| user_message_prefix | `_run.py` 命中 9 处 |
| 知识库页面图片 | `page_image_storage` 命中 35 处 |
| 多云存储 / Doubao Embedder / AgentOS Storage Router | 文件均存在，未受影响 |

**特别核实**：`agent/_storage.py` 这次有改动（+33 行，PR #9358 的"toolkit 归属重新绑定"），这个文件正是 `AgentCom-las-feature` 项目直接 `from agno.agent._storage import aread_or_create_session` 依赖的模块——已确认这次改动完全在 `to_dict()`/`from_dict()`（组件序列化）范围内，不涉及 `aread_or_create_session` 函数本身，那处下游依赖不受影响。

---

## 四、验证结果

```bash
./scripts/format.sh     # 通过，0 处需要重新格式化
./scripts/validate.sh   # ruff 全通过；mypy 0 发现（较上一轮的1个存量问题更进一步）
```

单元测试：
- 本次改动直接涉及的模块（`tools/advisor`、`tools/openrouteservice`、`tools/studio`、`tools/scheduler`、`models/cohere`、`registry`、`run/requirement`、`scheduler/cron`、`agent/team config`、`fs/toolkit`）：**全部通过**
- `agent/`、`team/`、`workflow/`、`learn/` 全量重跑：1764 通过、2 失败——失败的还是上一轮已经定位并确认为合并前既存、与升级无关的那两个（`test_knowledge_retriever_tool_priority.py`，mock 夹具用位置参数调 API 的历史问题）
- `models/` 目录：17 个文件因为本地开发环境没装 anthropic/aws/litellm/ollama/volcengine 等 provider SDK 而收集失败，跟本次改动无关（这些文件本身在这次范围内没有变化），沿用上一轮"本地环境不强行装满所有 provider SDK"的判断

---

## 五、版本对比

| 维度 | v2.8.6 | v2.8.7 |
|---|---|---|
| `Team.load()` + SqliteDb | 必现崩溃 | 已修复 |
| 媒体跟进消息（`_handle_function_call_media`） | 依赖工具结果原文拼接，模型不支持媒体时可能语义不完整 | 固定文案，自包含，不再依赖原文 |
| 持久化组件的工具反序列化 | 同名函数可能绑错 toolkit | 按声明顺序 + 归属正确重新绑定 |
| 新工具 | — | AdvisorTools、OpenRouteService |

---

## 六、合并提交信息

| 项目 | 值 |
|---|---|
| Merge commit | `c76b6c09a3a5a9a34e55017a77dcf7a06b171198` |
| Parent 1 | `ac4d7a286b2d74c01ab1bedcd20fc2d327bf6622`（`merge-agno-v2.8.6`） |
| Parent 2 | `03d2bf051bfdd3d4a04becce6977712070b30c4d`（`v2.8.7`） |
| Conflict files | 1（`models/base.py`，采纳上游完整简化版本） |
| Skipped | `v3.0.0a1`（alpha 预发布，按要求不纳入） |
| Push 状态 | 未 push，`merge-agno-v2.8.6`/`codex/agno-merge-v2.6.20` 原分支未受影响 |
