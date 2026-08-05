# 升级日志: v2.6.20 -> v2.8.6

> 分支: `merge-agno-v2.8.6`（基于 `codex/agno-merge-v2.6.20`，非 push 的 trial merge 分支）
> 上游版本: agno v2.8.6
> 合并提交: `173ad49a7ee59901dc4b74e1d639a26312919124`
> Parent 1: `ce4f473262e4f4aa99028ee0761370a8816ff7c4`（`codex/agno-merge-v2.6.20` + WIP checkpoint）
> Parent 2: `7c68873c1357321a5152397c8ab4fb8b3f587bba`（`v2.8.6`）
> 合并范围: v2.6.21, v2.6.22, v2.7.0~v2.7.4, v2.8.0~v2.8.6 全部传递吸收（一次性合并，未分阶段）
> 上游提交数: 171 commits（`v2.6.20..v2.8.6`），117 个涉及 `libs/agno/agno/` 核心代码
> 核心库变更量: 510 files changed, +73727/−6845（上游区间）；本次合并落地 1630 files changed, +129486/−41375（含本 fork 历史全量文件、agnoctl 新子项目等）
> 冲突文件: 13 个（1 个 `.gitignore` + 4 个 modify/delete + 8 个内容冲突）
> 验证状态: `ruff check` 全部通过；`mypy` 从 30 个发现修复到 1 个（确认为纯上游存量问题）；`ruff format` 通过；1216/1218 相关单测通过（2 个失败均确认为合并前已存在、与本次无关）

**执行偏差说明**：计划批准后、开始执行前，工作目录 HEAD 被（非本会话）从 `codex/agentcom-config-ref-isolation` 切到了 `codex/agno-merge-v2.6.20`（落后 2 个提交：RapidOCR Python 3.13 支持修复 `f40ae8ba6`、config_ref 隔离修复 `9e81917ae`）。已就此询问用户并确认以 `codex/agno-merge-v2.6.20` 为本次合并基点，上述两个提交不包含在这条合并线里，需要另行合并回来。

---

## 一、新增功能与必要性评估

| 新功能 | 一句话说明 | 对本项目的必要性 |
|---|---|---|
| Service Accounts（`agno_service_accounts` 表 + API） | 给 AgentOS 发放不依赖用户登录的、可控生命周期的 API token，用于机器对机器调用 | 本项目 271 个文件重度使用 AgentOS，**0 处实际使用**，不紧急但未来做 M2M 集成时用得上 |
| MCP OAuth v2 + `agnoctl` 命令行 | 让 AgentOS 暴露的 MCP server 支持标准 OAuth 授权（对接 Claude.ai/ChatGPT 等外部 MCP 客户端） | 4 个 cookbook 用了 `enable_mcp_server=True`（合并后已被上游自己的 cookbook 重写为新结构，见四.2）；agnoctl 是独立子项目，不影响主库运行 |
| Entity Memory / "second brain" 重写（`agno/learn/`，内部改动 +5251/− 行） | 重写实体记忆的存储与召回实现（用户画像、决策日志、已学知识） | **高相关**：`cookbook/08_learning/`（CLAUDE.md 指定的黄金标准）与 `03_teams/12_learning/` 全目录依赖它；对外 `stores/protocol.py` 只变 16 行，接口基本稳定；单测 `tests/unit/learn/` 全部通过（合并前该目录与我们 fork 完全无本地改动，纯净吸收） |
| FileSystem（`agno/fs/`，全新目录 +6050/−0） | 给 agent 一个持久化文件系统抽象 | **0 处引用**，不需要为它做任何事 |
| `agno.scorer` + rollout engine | 新的评测打分子系统 | **0 处引用**，不需要管 |
| Valkey / OpenSearch 支持 | 新增存储/向量库后端 | **0 处引用**，本项目是 PGVector 深度定制路线，不受影响 |
| AgentOS 认证中间件重构（`_add_jwt_middleware` → `_add_auth_middleware`） | 内部私有方法重构，为同时支持 JWT 与 Service Account token 铺路 | 私有方法，非公开 API；已确认我们的 `os/routers/storage/` 未直接引用旧方法名，无影响 |

**结论**：真正"有用"的新东西是 Service Accounts 与 MCP OAuth（跟本项目重度使用的 AgentOS 相关），entity memory 重写虽不是"新功能"但影响面最大、已验证测试通过。FileSystem / scorer / Valkey / OpenSearch 对当前项目没有直接帮助，合并只是顺带带入代码，不需要额外投入。

---

## 二、上游修复的关键 Bug

| # | 修复 | 影响范围 |
|---|------|----------|
| 1 | ClickHouse `delete_by_metadata` SQL 注入 (#7883) | 安全 |
| 2 | 3 处路径穿越漏洞：本地文件写入 (#8514)、Airflow DAG 文件 (#8638)、FileSystemKnowledge (#8624/#8726) | 安全 |
| 3 | CustomApiTools 认证头泄露 (#8582) | 安全 |
| 4 | Google Drive 下载文件名未约束 (#8704) | 安全 |
| 5 | `FixedSizeChunking` 短文档在 overlap ≥ 内容长度时被静默丢弃成 0 chunk (#8943) | 知识库摄入数据质量 |
| 6 | CSVReader/ExcelReader 可变默认参数（多实例共享同一个 `RowChunking` 对象）(#8922) | 知识库摄入 |
| 7 | `Message.get_content_string()` 空列表返回字面量 `"[]"` 而非空字符串 (#6122) | 工具调用后的模型输出格式 |
| 8 | `Reader(chunk=False)` 从未被真正遵守（Knowledge 层有个错误的兜底会强制 chunk）(#8708/#8882) | 知识库摄入行为——见第六节 |
| 9 | 嵌套 team 历史丢失、`get_team_history` 缺少 `team_id` 过滤 (#8956) | Team 历史记录 |
| 10 | AgentOS `POST /sessions` 对已存在 session_id 补上幂等 (#8646) | AgentOS API |
| 11 | `enable_mcp_server` → `mcp_server` 重命名，完全向后兼容 (#8812) | AgentOS 配置 |

---

## 三、定制功能保留状态

| 定制功能 | 涉及文件 | 验证结果 |
|---|---|---|
| lean_references | `agent.py`, `_utils.py`, `_default_tools.py`, `team.py`, `team/_utils.py` | `agent.py` 命中 3 处 |
| user_message_prefix | `agent.py`, `agent/_run.py` | `_run.py` 中 `with _user_message_prefix` 命中 9 处（较 v2.6.20 时期多 1 处，为上游新增流式路径带来） |
| 多云存储后端 | `knowledge/storage/` | 上游无同名目录，零冲突，完整保留 |
| 知识库页面图片 | `knowledge.py`, `knowledge/utils.py`, `knowledge/reader/` | `page_image_storage` 命中 34 处 |
| Doubao Embedder | `knowledge/embedder/doubao.py` | 上游无同名文件，完整保留 |
| AgentOS Storage Router | `os/routers/storage/` | 完整保留，`os/app.py` 合并后 `storages`/`storage_ids` 构造参数与两处 `get_storage_router()` 注册均确认完整 |
| MCP 异步清理 | `tools/mcp/mcp.py` | `_safe_cleanup`/`asyncio.shield` 保留；上游收窄了 2 处**跟清理无关**的 `except BaseException` 为 `except Exception`（`ping`/`initialize`），已采纳，我们清理路径的 `except BaseException` 未受影响 |
| PGVector retry | `vectordb/pgvector/pgvector.py` | 上游该区间未改动此文件，指数退避重试逻辑完整保留 |
| OpenAI image injection | `models/openai/chat.py` | 上游未改动，完整保留 |
| 中文 JSON 支持 | `agent/_utils.py`, `client/os.py`, `models/base.py` | `ensure_ascii=False` 全部保留；上游同期在 `client/os.py`（`.to_dict()`+`files→input_files`重命名）与 `models/base.py`（`encoding="utf-8"`）分别做了独立修复，均已与我们的定制合并，见四.6/四.7 |

**本次发现的两个此前未被文档记录的定制**（建议后续补进 `agno-merge` 技能的保护清单）：
- `knowledge/reranker/infinity.py`：`score_threshold` 分数阈值过滤 + `url` 自定义配置项（来自历史分支 `feature/2.4.3`）
- `knowledge/reader/web_search_reader.py`：搜索失败/空结果时 `raise ValueError` 而非静默 `return []`（与 skill 里记录的 "Reader error handling" 模式一致，但该文件本身未被列出）

---

## 四、冲突解决详情

### 4.1 `.gitignore`
两侧各自新增了互不相关的忽略规则，直接合并保留双方。

### 4.2 4 个 modify/delete 冲突（cookbook）
`cookbook/05_agent_os/skills/sample_skills/system-info/scripts/{get_system_info.py,list_directory.py}`、`cookbook/05_agent_os/studio_tool/README.md`、`cookbook/levels_of_agentic_software/generate_requirements.sh` —— 上游用 `cookbook: rewrite the AgentOS cookbook (284 files -> 132, 24 lessons) (#9153)` 做了大重组。核实这几个文件在我们这边的"本地修改"只是文件权限位（755→644）和一处尾随空行，**没有实质内容**；且确认内容已迁移到新的 `cookbook/05_agent_os/23_skills/`、`22_studio/` 结构下（新文件由合并自动带入）。**采纳上游删除**。

### 4.3 `libs/agno/agno/agent/_messages.py`（2 处，sync + async 双胞胎）
上游把"learnings 拼进 system prompt"的逻辑从只拼 `learning_context`（数据）改成同时拼 `learning_guidance`（工具使用说明）+ `learning_context`，理由是紧邻的注释明确写了"要让自动挂载渲染出和手动挂载一致的效果"。但上游这处改动用的变量名是 `system_message_content +=`，而这个函数从头到尾用的都是 `parts.append(...)` 累加器模式——直接采纳会产生 `NameError`（未定义变量）。**保留上游的语义改进（补上 learning_guidance），改用 `parts.append(...)` 写法**，避免引入 bug。

### 4.4 `libs/agno/agno/client/os.py`（6 处，agent/team/workflow 的 run + run_stream）
上游把媒体序列化从 `.model_dump()`/裸传对象改成 `.to_dict()`，并把 `files` 字段改名成 `input_files`（附注释：run 端点的 `files` 字段已经被 multipart 上传占用，两者同名会冲突）。核实其中 4 处（`run_team`/`run_team_stream`）在我们这边甚至**从未调用任何序列化方法**、直接把 `Image`/`Audio`/`Video`/`MediaFile` 对象扔给 `json.dumps()`——这是我们自己代码里的一个潜在崩溃 bug（非空媒体参数会直接抛 `TypeError`）。**采纳上游的 `.to_dict()` + `input_files` 重命名（顺带修掉这个潜在崩溃），补回 `ensure_ascii=False`**。

### 4.5 `libs/agno/agno/knowledge/reader/arxiv_reader.py`
上游给 `ArxivReader` 补上了 `if self.chunk:` 的正确处理（之前从未 chunk 过，属于第六节提到的架构缺口），但**这次合并进来的上游代码本身有个缩进 bug**：`document = Document(...)` 那一段被意外挪到了 `if result.summary:` 判断之外，会导致摘要为空的论文触发 `NameError`（`links` 未定义）或者复用上一篇论文的 `links` 值。**采纳上游的 chunk 处理逻辑，同时修正缩进，把整段重新收回 `if result.summary:` 内部**。

### 4.6 `libs/agno/agno/knowledge/reader/pdf_reader.py`（2 处，`_decrypt_pdf` + `_create_documents`）
逐字比对了双方完整实现：
- `_decrypt_pdf`：我们的版本（无条件先试空密码、再试传入密码，每次尝试独立 try/except）比上游版本（仅当未传密码时才试空密码）更宽松、更贴近 WPS 等主流 PDF 阅读器的行为，且有明确注释说明设计意图。核实了上游对应的 PR (`#5160`) 背景，是"user password 与 owner password 分离"的场景，我们的"始终先试空密码"策略能覆盖更多场景，无安全顾虑。**保留我方版本**。
- `_create_documents`：我方版本比上游多了 `page_images` 页面图片分支（核心定制）、更完整的 `total_pages`/`raw_page_num` 元数据、以及空内容页面的过滤。**保留我方版本**。
- `_pdf_reader_to_documents`/`_async_pdf_reader_to_documents`（未冲突，核实无误）：我方版本额外带有 pypdf `KeyError: 'bbox'` 防御性处理和 OCR 异常保护，上游没有，**予以保留**。

### 4.7 `libs/agno/agno/models/base.py`（2 处，模型响应缓存读写）
上游给 `open()` 补上 `encoding="utf-8"`（Windows 平台默认编码可能不是 UTF-8，写入非 ASCII 内容会静默损坏），我们这边加的是 `json.dump(..., ensure_ascii=False)`——两者解决的是同一个"中文/非 ASCII 内容落盘正确性"问题的两个互补半面，缺一不可。**合并双方**。

### 4.8 `libs/agno/agno/os/app.py`
双方在 `AgentOS.__init__` 的同一处新增了不同的关键字参数：我方 `storages`/`storage_ids`（页面图片存储路由用）、上游 `enable_mcp_server`/`mcp_config`（`mcp_server` 参数的弃用兼容别名）。**参数互不冲突，直接合并保留双方**。

### 4.9 `libs/agno/agno/tools/mcp/mcp.py`（3 处）
均为上游把 `except (RuntimeError, BaseException):` 收窄为 `except Exception:`（`ping()`/`build_tools()` 异常处理/`initialize()`），且确认这 3 处都不在我们的 `_safe_cleanup`/`asyncio.shield` 定制路径上。**采纳上游收窄**。

### 4.10 `libs/agno/agno/tools/pubmed.py`
`max_results` 参数补上默认值 `None`，与紧邻的文档字符串（"Defaults to the value set on the toolkit, or 10"）保持一致。**采纳上游**。

---

## 五、mypy 2.1 修复清单（本次合并触发的重要副产品）

`dev[dev]` 里的 mypy 从 1.18.2 升到 2.1.0（大版本跳跃），`validate.sh` 首次运行发现 30 个新增告警。逐条核实归因后：29 个属于我们自己维护的代码（含 2 个真实可复现的运行时 bug），已修复；1 个确认是纯上游、未被本 fork 触碰过的存量代码问题，记录如下、不在本次范围内处理。

| 文件 | 问题 | 处理 |
|---|---|---|
| `knowledge/knowledge.py`（FileData 摄入路径，sync+async） | `_select_reader_by_extension` 找不到匹配 reader 时返回 `None`，但后续代码无判空直接调用 `.read()`/`.async_read()` | **真实 bug，已修复**：补上 `reader is None` 判空分支，走既有的 `ContentStatus.FAILED` 流程 |
| `knowledge/knowledge.py`（4 处 `if content.reader: reader = ... else: reader, _ = ...`） | mypy 从首个分支误推出 `reader: Reader`（非 Optional），导致后续赋值报"类型不兼容"而非真正该报的"可能为 None" | 显式标注 `reader: Optional[Reader]`，让类型声明与真实语义一致 |
| `knowledge/knowledge.py`（`file_source`，2 处） | 声明为 `Optional[Union[Path, BytesIO]]`，但该函数内实际只会赋值 `Path` | 收窄为 `Optional[Path]`，纠正过宽的历史标注 |
| `knowledge/knowledge.py`（`_async_sign_reference_urls`/`_resolve_page_image`） | 嵌套闭包/内部函数里引用 `self.page_image_storage`，mypy 不会把外层的判空结果带进闭包 | 在外层捕获成局部变量（`page_image_storage = self.page_image_storage`）供闭包引用；`_resolve_page_image._sign` 额外补上判空提前返回 |
| `knowledge/knowledge.py`（`async_upsert` 调用） | 已有的 `# type: ignore[arg-type]` 注释位置不对（挂在收尾括号行，mypy 实际锚定在参数行） | 挪到参数行 |
| `knowledge/reranker/infinity.py`（sync+async 各 1 处，共 4 处告警） | `self.score_threshold` 是 `Optional[float]`，判空重置的逻辑对 `self.xxx` 属性不生效（只对局部变量生效），且后续在 list comprehension 里使用又踩了 mypy 对闭包/推导式作用域的已知限制 | 捕获成局部变量 `score_threshold`；比较逻辑由列表推导式改写为显式 for 循环，并顺带给 `doc.reranking_score is None` 的极端情况加了防御 |
| `knowledge/reader/web_search_reader.py` | `document` 变量先后被赋值为 `Document`、又赋值为 `Document | None`，与首次推断类型冲突 | 显式标注为 `Optional[Document]` |
| `knowledge/storage/base.py` | `_build_credential_response()` 调用 `self._base_url(...)`，但抽象基类从未声明这个方法（4 个子类都各自实现了，只是基类没声明契约） | 补上 `@abstractmethod def _base_url(...)` 声明，纯新增、零行为变化 |
| `knowledge/reader/image_reader.py` | `raw_name = name or getattr(file, "name", "image.png")` 在 `name`/`file.name` 都为 `None` 的边界情况下可能整体为 `None`，传给 `os.path.basename()` 会崩 | 重写为显式判空 + 兜底默认值，杜绝这个边界情况 |
| `agent/_default_tools.py`（4 处，两两一组） | `all_docs` 先声明为非 Optional 的 `List[...]`，后面又被重新赋值成 `... if all_docs else None` | 引入新变量 `deduped_docs: Optional[List[...]]` 承接去重后的结果，`all_docs` 保持非 Optional 只做累加，语义更清晰 |
| `vectordb/pgvector/pgvector.py` | `doc.meta_data.get("page_image_url")` 被独立调用两次（一次判空、一次传参），两次调用之间的窄化对 mypy 不透明 | 只调用一次、赋值给局部变量后复用 |
| `libs/agno/pyproject.toml`（mypy `ignore_missing_imports` 名单） | `fitz`(PyMuPDF)、`volcenginesdkarkruntime`、`qcloud_cos`、`qiniu`、`tos`、`oss2`、`magic` 这 7 个我们自定义集成用到的第三方 SDK 从未被加入忽略名单——这不是本次合并引入的问题，`v2.6.20` 基线里就已缺失，只是这次干净环境搭建才第一次真正跑出来 | 按现有名单风格逐一补齐 7 个条目 |
| `models/base.py:3070`（`media_source_contents.append(result_message.content)`） | `Message.content` 可能是 `list[Any] \| str`，无条件当 `str` 追加 | **确认为纯上游代码，与 v2.8.6 tag 逐字节一致，本 fork 从未触碰**。不在本次范围内处理，留给上游或后续专门的类型清理 |

---

## 六、存量功能影响清单

| 存量功能 | 影响判定 | 说明 |
|---|---|---|
| Entity Memory / LearningMachine（`cookbook/08_learning/` 等） | ✅ 已验证 | `agno/learn/` 内部重写 5251 行，但该目录相对我们 v2.6.20 基线**零本地定制**（纯净合并）；`tests/unit/learn/` 全量通过。建议后续用真实模型跑一遍 `cookbook/08_learning/` 做端到端确认（本沙箱环境无 API key，无法执行） |
| `enable_agentic_memory` + 配了 `user_memory` store 的 `LearningMachine` 同时使用会导致 `update_user_memory` 工具名冲突（上游新增的警告） | ✅ 已排查，非本项目问题 | 检查过项目里唯一同时出现这两种写法的 3 个文件（`gemini_3/18_memory.py`、`level_3_memory_learning.py`、`level_5_api.py`），它们的 `LearningMachine` 都只配了 `learned_knowledge` store，未配 `user_memory` store，不会触发这个冲突 |
| Reader `self.chunk` 契约变化（Knowledge 层删除了"reader 没 chunk 就强制兜底 chunk"的逻辑） | ✅ 已验证兼容，且顺带修了一个真实 bug | 我们全部 9 个 stock reader 早已在内部正确实现 `if self.chunk:`；唯一的例外是 `arxiv_reader.py`（上游这次带的修复本身有缩进 bug，已一并修正，见 4.5） |
| workflow `Condition`/`Router` 的 `session_state` 参数弃用（改用 `run_context`） | ✅ 已随上游自动解决 | 之前定位到的 3 个用旧写法的 cookbook（`state_in_condition.py`/`state_in_router.py`/`cel_session_state.py`）在合并后**已经是上游自己重写过的 `run_context` 新写法**，无需手工改。且确认弃用告警走的是 `log_warning()`，不是 Python `DeprecationWarning`，不会让测试失败 |
| Gemini 默认模型静默切换（`gemini-flash-latest` → `gemini-3.5-flash`） | ✅ 已处理 | `cookbook/02_agents/14_advanced/interchange_model/{claude_gemini,openai_gemini,all_providers}.py` 3 个文件的裸 `Gemini()` 调用已补上显式 `id="gemini-3.5-flash"`；顺手把 2 个文件里违反 CLAUDE.md 规则的 `gpt-4o` 也换成了 `gpt-5.5` |
| AgentOS 认证中间件重构 | ✅ 已验证无影响 | 私有方法重命名（`_add_jwt_middleware`→`_add_auth_middleware`），确认我们的 `os/routers/storage/` 未直接引用旧名 |
| `TeamSession.get_team_history`/`get_team_history_context` 新增 `team_id` 参数插在 `num_runs` 前面 | ✅ 已加固 | 见第七节 Tier D，本 fork 所有内部调用点确认都用关键字传参，未受影响；额外把这两个方法的 `team_id` 做成关键字专用，防止外部下游位置传参时静默拿错结果 |

---

## 七、对"历史存量依赖项目"的破坏性审计 + 澄清清单

"存量依赖项目"指依赖这个 agno 私有包的其他内部项目/服务（不是本仓库自己的 cookbook）。这一层能在本仓库内部核实的，和只能列出来需要人工确认的，分开说明。

### 7.1 已核实、已处理或已确认无需处理的项

| # | 变更 | 风险等级 | 处理状态 |
|---|---|---|---|
| 1 | `agno.models.defaults.DEFAULT_OPENAI_MODEL_ID` 被上游删除 | High（`ImportError`） | **已处理**：恢复为一行向后兼容 shim（`libs/agno/agno/models/defaults.py`），理由是这个常量在合并前一刻还在被本仓库自己的 `knowledge/chunking/agentic.py` 实际导入使用，属于有真实使用先例的公开符号 |
| 2 | `TeamSession.get_team_history()`/`get_team_history_context()` 新增 `team_id` 参数插在 `num_runs` 前面 | High（静默返回错误结果） | **已处理**：改成关键字专用参数，位置传参会立即报 `TypeError` 而不是静默返回空历史 |
| 3 | `requires-python` 从 `>=3.7` 提升到 `>=3.9` | 中（安装期失败） | 本仓库 CI 已在 3.10/3.12，无影响；其他下游项目需自行确认，见 7.2 |
| 4 | pyproject extras 改名（`async_postgres`→`async-postgres` 等 4 处） | 中（安装期失败） | 已确认本仓库自己的 pyproject.toml 没有额外自定义 extras，改名已随上游版本原样合并 |
| 5 | `agno[mcp]` 新增强制依赖 `fastmcp>=3.4.3,<4` | 低（依赖树变化） | 需下游项目自行核实锁文件是否有冲突版本 |
| 6 | 新增 `agno` CLI 命令（`agnoctl.main:app`） | 低（环境命名冲突） | v2.6.20 没有这个入口，部署到有 CLI 使用场景的环境前建议确认 PATH 无冲突 |

### 7.2 无法在本仓库内部证实、需要人工确认的澄清清单

1. 现在有哪些内部项目/服务实际依赖这个 agno 包？通过什么方式引用（私有源 `pip install`、git URL 指定 tag/commit、还是 monorepo 路径依赖）？
2. 这些下游项目的 Python 版本是否都 ≥ 3.9？
3. 有没有下游项目绕过 `agno.db.*` 接口、自己直接读 Postgres/SQLite 里的 agno 表？（本次是纯增表，风险很低，但建议过一遍改动清单）
4. 有没有下游项目基于 `agno.knowledge.reader.Reader` 写过自己的自定义 Reader？如果有，需要检查是否正确处理了 `self.chunk`（本仓库自己的全部 reader 已核实无问题）
5. 有没有下游项目 import 过 `agno.models.defaults.DEFAULT_OPENAI_MODEL_ID`？
6. 有没有下游项目位置传参调用过 `get_team_history`/`get_team_history_context`？

---

## 八、老项目升级 SDK 注意事项 + 兼容性矩阵

| 场景 | v2.6.20 -> v2.8.6 | 是否需要代码调整 |
|---|---|---|
| 基础 Agent/Team 对话 | 兼容 | 否 |
| 知识库引用与页面图片 | 兼容，本 fork 定制保留 | 否 |
| 多云图片存储 | 兼容 | 否 |
| Entity Memory / LearningMachine | 内部重写，接口兼容 | 建议用真实模型跑一遍 `cookbook/08_learning/` |
| AgentOS Service Accounts / MCP OAuth | 新增能力 | 按需启用 |
| `enable_mcp_server` | 向后兼容别名 | 否（cookbook 示例已被上游重写为新写法） |
| Workflow `session_state` in Condition/Router | 弃用但仍可用 | 否（仅打日志，不影响功能） |
| Gemini 默认模型 | 静默变化 | 显式传 `id` 的调用方不受影响 |
| `get_team_history`/`get_team_history_context` | 新增关键字专用参数 | 位置传参的下游调用需要改成关键字传参 |
| `DEFAULT_OPENAI_MODEL_ID` | 已恢复 shim | 否 |

---

## 九、验证与测试结果

已运行（本沙箱环境）：

```bash
./scripts/dev_setup.sh                          # 通过
./scripts/format.sh                             # 通过（2 处 CRLF 规范化）
./scripts/validate.sh                           # ruff 全通过；mypy 30→1（见第五节）
```

定制功能验证：

```bash
grep -c "lean_references" libs/agno/agno/agent/agent.py         # 3
grep -c "_user_message_prefix" libs/agno/agno/agent/_run.py     # 9
grep -c "page_image_storage" libs/agno/agno/knowledge/knowledge.py  # 34
```

单元测试（`.venv` 补装 `pgvector`, `chonkie`, `xlrd`, `openpyxl` 后）：

| 测试目录 | 结果 |
|---|---|
| `tests/unit/knowledge/` | 全部通过（含补装依赖后的 excel `.xls` 用例） |
| `tests/unit/vectordb/test_pgvector.py`, `test_pgvector_strict_search.py` | 2 个失败（`test_async_insert`/`test_async_upsert`），**确认为合并前已存在**：`test_pgvector.py` 与 v2.8.6 tag 逐字节一致，mock fixture 用的是同步 `MagicMock()` 而非 `AsyncMock`，与本次合并无关 |
| `tests/unit/agent/` | 1216 个中 2 个失败（`test_knowledge_retriever_tool_priority.py` 两个用例），**确认为合并前已存在**：测试文件与实现文件均和 v2.8.6 tag 逐字节一致 |
| `tests/unit/workflow/` | 全部通过 |
| `tests/unit/learn/` | **全部通过**（entity memory 重写的最高优先级回归项） |

**未能在本环境执行、需要交给你或 CI 执行的收尾项**：
- `cookbook/08_learning/`、`cookbook/05_agent_os/` 等需要真实模型 API key（部分还需 `./cookbook/scripts/run_pgvector.sh` 起数据库）的端到端 cookbook 验证
- 第七节的 6 项澄清清单，需要跟其他依赖此包的团队确认

---

## 十、版本对比

| 维度 | v2.6.20 | v2.8.6 |
|---|---|---|
| AgentOS 鉴权 | JWT/PAT | + Service Accounts、MCP OAuth v2、内置 auth server |
| Entity Memory | 已有 `agno/learn/` | 内部存储/召回实现重写 |
| Agent 文件系统 | 无 | 新增 `agno/fs/` |
| 评测 | 无独立子系统 | 新增 `agno.scorer` + rollout engine |
| 存储/向量库后端 | 不含 Valkey/OpenSearch | 新增 Valkey（db+vectordb）、OpenSearch |
| DB schema | — | 纯增量：`service_accounts`、`mcp_oauth_*` 共 6 张新表，无迁移脚本，自动建表 |
| Python 版本下限 | `>=3.7` | `>=3.9` |
| mypy | 1.18.2 | 2.1.0 |
| CLI | 无 | 新增 `agno`/`agnoctl` 命令 |
| Reader chunk 契约 | Knowledge 层有兜底（且有 bug：`chunk=False` 从未被真正遵守） | 兜底移除，reader 自行负责，`chunk=False` 才是真正生效的 |

---

## 十一、上游关键提交摘要

（171 个提交中的代表性子集，完整列表见 `git log v2.6.20..v2.8.6 -- libs/agno/agno/`）

| Commit | PR | 标题 |
|---|---|---|
| `5baeb410d` | #8747 | feat: v2.7 — service accounts, MCP interface v2, agnoctl, and eval suites |
| `6aa13e8f8` | #9177 | feat: revamp entity memory for the second brain |
| `8a2379011` | #9142 | feat: FileSystem — durable agent filesystem |
| `ff867b466`/`607436a17` | #9050/#9049 | feat: rollout engine and Case.scorer seam / agno.scorer and the judge prompt fence |
| `e0dd35188` | #8141 | feat: add Valkey support (storage db + vector db) |
| `e65762d52` | #3611 | feat: support opensearch db |
| `8f0ac57f1` | #8812 | feat: rename AgentOS enable_mcp_server to mcp_server, fold in mcp_config |
| `50add8a91` | #9018 | chore: deprecate session_state in condition/router workflow in favour of run_context |
| `bbf3a98939` | #9153 | cookbook: rewrite the AgentOS cookbook (284 files -> 132, 24 lessons) |
| `678051366` | #7883 | fix: eliminate SQL injection in ClickHouse delete_by_metadata |
| `93ce6c009`/`0c15d3b4c`/`7698f640c` | #8514/#8638/#8624 | 3 处路径穿越修复 |
| `f1a5354f0` | #8582 | fix: Prevent CustomApiTools auth header leakage |
| `26c28352f` | #8943 | fix: FixedSizeChunking silently drops short documents when overlap >= content length |
| `0e1ff96eb` | #8922 | fix: CSVReader/ExcelReader no longer share one mutable default RowChunking instance |
| `2594f206c` | #6122 | fix: Return empty string for empty content list in get_content_string() |
| `b44acee84`/`9562931fd` | #8708/#8882 | fix: Reader(chunk=False) 未被遵守的两处修复 |
| `f80f687fe` | #8617 | fix: change Gemini default model from gemini-flash-latest to gemini-3.5-flash |
| `e145ba394` | #8384 | chore: remove shared default OpenAI model util and refresh example model ids |
| `1e03b4ef3`/`54891f7f9`/`dffd0930b` | #8956/#8968/#9011 | Team 历史记录相关修复 |

---

## 十二、合并提交信息

| 项目 | 值 |
|---|---|
| Merge commit | `173ad49a7ee59901dc4b74e1d639a26312919124` |
| Parent 1 | `ce4f473262e4f4aa99028ee0761370a8816ff7c4`（`codex/agno-merge-v2.6.20` + WIP checkpoint commit） |
| Parent 2 | `7c68873c1357321a5152397c8ab4fb8b3f587bba`（`v2.8.6`） |
| Conflict files | 13（1 `.gitignore` + 4 modify/delete + 8 内容冲突） |
| Verification | `ruff check` 通过；`mypy` 30→1（1 项确认纯上游存量问题）；`ruff format` 通过；1216/1218 相关单测通过 |
| Push 状态 | **未 push**，仅本地 `merge-agno-v2.8.6` 分支，`codex/agno-merge-v2.6.20` 原分支未被修改 |
