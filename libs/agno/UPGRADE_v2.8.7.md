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

## 总览：v2.6.20 → v2.8.7 整体变更与注意事项

这是两轮合并的最终状态（`codex/agno-merge-v2.6.20` → `merge-agno-v2.8.6` → `merge-agno-v2.8.7`），分支链完整、逐段可追溯。下面是给要接手这条分支的人（review / 合并进 main / 通知下游）的摘要，细节分别在 `UPGRADE_v2.8.6.md`（v2.6.20→v2.8.6，主体工作量）和本文件（v2.8.6→v2.8.7，小补丁）里。

### 变更点（做了什么）

- 跨 3 个 minor 版本、171+14=185 个上游提交，一次性合并到位（未分阶段停靠）。
- 全部 13+1=14 处合并冲突逐一手工核实解决，不是机械 accept-theirs/ours；过程中发现并修了 **3 个真实 bug**（2 个在 `knowledge.py` 的 reader-not-found 崩溃路径、1 个是上游自己 `arxiv_reader.py` 的缩进 bug）。
- 主动做了 2 处比上游更保守的下游兼容性加固：恢复 `DEFAULT_OPENAI_MODEL_ID` 常量（上游删除但我们自己代码在用）、把 `get_team_history`/`get_team_history_context` 的新增参数改成关键字专用（防止下游位置传参静默拿错数据）。
- 10 个存量 cookbook 做了同步修改（弃用写法迁移、CLAUDE.md 规范违规清理），另发现并修了 16 处本次合并新增/改动文件里的 `gpt-4o` 违规。
- `mypy` 1.18→2.1 大版本跳跃触发的 30 个新告警，逐条核实归因后修到 **0 个**（最后 1 个"确认纯上游存量"的问题在 v2.8.7 那轮被上游自己的重构顺带消掉了）。
- 全部 13 项已知定制特性（lean_references / user_message_prefix / 多云存储 / 页面图片 / Doubao Embedder / MCP 清理 / PGVector 重试 / OpenAI 图片注入 / 中文 JSON 等）逐一验证保留，另外发现并补充记录了 2 项此前未被文档记录的定制（`InfinityReranker.score_threshold`、`WebSearchReader` 的 raise-on-error 约定）。
- 用真实下游消费者（`/home/friend/local_code/AgentCom-las-feature`）验证过下游兼容性，不是纸上谈兵：它跑的是我们私有 fork 的 v2.6.4（比这次的起点还老），核实了它对 `agno.agent._storage.aread_or_create_session`（私有模块）、`agno_knowledge` 表原生 SQL、自定义 Reader 子类等几处深度依赖，在 v2.8.7 下全部安全。

### 注意事项（合并进 main / 通知下游前必须过一遍）

1. **发布流程要跟上，不只是改版本号**——`AgentCom-las-feature` 那类下游项目是"打 wheel 包 + Docker 里强制覆盖安装"的模式，不走正常依赖解析。真要下游用上这次升级，需要重新打一个基于 `merge-agno-v2.8.7`（或合并进 main 后的最终态）的 wheel，替换他们 `Dockerfile.base`/`Dockerfile.slim` 里的文件名。
2. **`libs/agno/UPGRADE_v2.8.6.md` 第七节的"下游依赖破坏性变更 + 澄清清单"仍然有效**——6 个问题里已经用 AgentCom 项目验证掉了大半，但"到底还有哪些内部项目依赖这个包、它们的 Python 版本是不是都 ≥3.9"这类跨项目的问题，还是需要人工去问一圈，不是这次合并能替你确认的。
3. **`OpenAIChat` → `OpenAIResponses` 是个已发现但故意没动的问题**——`UPGRADE_v2.8.6.md` 第八节记录过，15 个文件里用的是 CLAUDE.md 建议弃用的 `OpenAIChat`，因为换成 `OpenAIResponses` 是模型类切换（工具调用 ID 格式都不一样），没有真实 API key 没法验证，留给了专门的后续任务。
4. **entity memory（`agno/learn/`）内部重写了 5251 行**，虽然单测全绿、接口没大改，但涉及记忆抽取效果这种"跑起来才知道对不对"的东西，合并进 main 前建议找个有 API key 的环境把 `cookbook/08_learning/` 真跑一遍，别只信单测。
5. 本次合并分支**只做到 push**，没有开 PR、没有合并进 `main`、没有通知任何下游团队——这几步需要你自己决定时机。

### 快速定位

- 完整必要性评估、破坏性审计、新功能怎么用：`UPGRADE_v2.8.6.md`
- 这次 v2.8.7 小版本的具体改动：本文件下面几节

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
