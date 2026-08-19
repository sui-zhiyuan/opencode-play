# AI Agent 向量知识库方案调研（opencode / DeepSeek Harness）

> 调研结论速览：**可行且 opencode 生态已有成熟方案**；两条核心原则——存储层**只存文本与向量、不存 token id**（跨模型无障碍）；git **管内容不管理索引**（索引是构建产物）。

---

## 一、可行性

### opencode（可行，生态已成熟）

三种接入途径，成本从低到高：

| 途径 | 方式 | 备注 |
|------|------|------|
| MCP server | 在 `opencode.json` 的 `mcp` 里挂 stdio MCP（Milvus/Qdrant/sqlite-vec 的 MCP wrapper），所有 agent 通过 `mcp_*` 命名空间调用 | 最通用，LLM 驱动调用 |
| Plugin | npm 插件注册自定义 tool（`tool()` API）+ 生命周期 hooks（自动注入上下文） | 可做到自动召回，不只靠模型主动搜索 |
| 现成插件 | 直接安装，无需自研 | 见第七节方案清单 |

### DeepSeek Harness（可行，需自写插件）

`deepseek-ai/deepseek-harness` 是 DeepSeek 2026 年 8 月开源的**智能体 harness**（非训练框架），基于 Cordis，哲学是 "everything is a plugin"：工具注册表、agent loop、session log 全部是插件。

- 接入方式：写一个 Cordis 插件，往 `ctx.tools` 注册 `knowledge_search` 工具（底层接向量库）
- 也自带 MCP client，可直接挂现成向量库 MCP
- 不同 profile（Standard/Code/Minimal/Creator）可挂不同工具集
- ⚠️ 目前是 developer preview，核心插件与 API 仍在演进

---

## 二、优势（相对 grep / AGENTS.md 静态文件）

1. **语义检索**：grep 只能命中字面关键词；向量检索能跨语言（中英混排、同义改写、概念匹配）命中，中文技术笔记收益尤其明显
2. **不挤占上下文窗口**：按需注入 top-k chunk，而不是把整个知识库塞进 system prompt（大库会压爆上下文或稀释注意力）
3. **跨会话持久记忆**：agent 会话之间默认零记忆，向量记忆解决"每次重新解释约定"的问题
4. **混合检索兜底**：BM25/精确匹配 + 向量融合（RRF），代码标识符、函数名这类精确 token 不会丢
5. **增量索引 + 本地隐私**：文件 hash 增量建索引；本地 embedding（Ollama/ONNX）时数据不出机器
6. **可评测**：RAG on/off 的 token 消耗与准确率可对比

---

## 三、是否限制 Agent 使用

**不构成硬限制，但有几类实际约束：**

1. **工具可按 agent 配置（这是控制，不是限制）**：opencode 里 MCP/插件工具默认对所有 agent 可用，但可用 per-agent `tools` 通配符（`"mymcp_*": false` 全局关、某个 agent 开）精细控制；deepseek harness 则按 profile 挂工具集
2. **真正的约束在模型侧**：向量检索是 LLM 驱动的工具调用——模型必须主动判断"该搜了"并调用工具。工具调用能力弱的小模型会失效；而 grep 类检索是确定性机制，不依赖模型
3. **embedding 依赖额外组件**：需要单独的 embedding 模型（本地 Ollama/Qwen3-Embedding/bge-m3 或 API），中文内容务必选多语言模型
4. **索引新鲜度**：文档更新后需重新索引；分块质量（尤其技术文档的代码块边界）直接影响召回率
5. **不替代 grep**：符号级精确查找、引用追踪仍是 LSP/grep 的强项。正确姿势是 hybrid，而非二选一

---

## 四、跨模型支持（tokenizer 差异问题）

### 核心结论：向量知识库里不存 token id，tokenizer 差异不构成问题

数据流：

```
文档 → 分块 → 嵌入模型 → 向量（存盘）
检索：query → 同一嵌入模型 → 向量 → 相似度搜索 → 返回【文本 chunk】→ 注入 prompt → 各自模型自己 tokenize
```

存储层只有**原始文本**和**浮点向量**。检索结果是文本，注入 prompt 时由当前对话模型的 tokenizer 现场编码。token id 只在"最后一公里"临时产生，从未被持久化。**文本是跨模型的通用货币**。

### 真正与"模型绑定"的东西只有 embedding 模型

| 层面 | 绑定关系 | 换模型的影响 |
|------|----------|--------------|
| 对话模型（LLM） | **完全无关** | 随便换（deepseek ↔ claude ↔ qwen），零成本 |
| 嵌入模型（embedding） | **向量维度由它决定** | 换嵌入模型 = 维度变化（bge-m3 1024 / text-embedding-3-small 1536 / Qwen3-Embedding-4B 2560），必须重建索引或存多套 |

跨模型支持的本质：**用同一个 embedding 模型服务所有对话模型**。这正是 MCP 方案天然支持 Claude Code / opencode / Codex 共用同一记忆库的原因。

### token id 不一致真正会造成问题的场景（避开即可）

1. **按某模型的 token 数分块**：chunk 边界 tokenizer 相关，换模型后漂移 → 用模型无关边界分块（Markdown 结构、AST、字符数）
2. **把 token id 序列当检索特征存**：错误做法，文本/向量检索都不需要
3. **Prompt 缓存跨模型复用**：服务端前缀缓存按 token 前缀算，换模型失效——只影响成本/延迟，不影响知识库正确性
4. **精确 token 计数/预算控制**：运行时用当前模型的 tokenizer 现算的近似，绝不持久化为索引键

### 实践准则（自建时）

- 落盘只存：`原始文本 + embedding 向量 + 来源元数据（文件、行号、hash）`
- embedding 模型单独固定，记录 name + 维度；对话模型随意换
- 换 embedding 模型时：多索引并存或一次性重建（hash 增量索引让重建便宜）
- token 相关计算一律运行时按当前 provider 计算，不留盘

---

## 五、Git 版本管理

### 核心原则：版本化源文件，不版本化索引

| 层 | 是否进 git | 理由 |
|----|------------|------|
| 知识库内容（Markdown、PDF、图片） | ✅ 进 | 文本可 diff、可 review、可回滚、可 blame |
| 向量索引 / embedding | ❌ gitignore | 二进制、体积大、churn 高、不可 diff；可由内容 + 配置**确定性重建** |
| 分块/嵌入配置（模型、维度、chunk 策略） | ✅ 进 | "构建配方"，锁定了它索引才可复现 |

索引与 embedding 的关系如同源码与编译产物：`源码 + 编译器版本 + 构建配置` 都在 git 里，产物随时可再生。

### 已有的成熟模式

1. **@mathew-cf/opencode-memory**：`~/opencode-memory/` 是 git 仓库（Markdown 笔记），`memory_save` = `git commit` + 后台重建语义索引。git 是事实源，向量索引是从事实源重算的缓存
2. **git-backed 知识管理**（个人知识库领域最成熟模式）：Obsidian + obsidian-git、Foam、Quartz、Logseq——跨机器同步、历史版本、协作
3. **大文件补充工具**：Git LFS（大二进制）、git-annex（超大/多机）；纯文本知识库通常不需要

> 反模式：没有"git 版本化向量数据库"的成熟方案，也不该有——Qdrant 快照、Milvus backup 是运维备份手段，不是版本管理手段。

### 可追溯性：用 commit sha 打通内容与索引

- 索引时给每个 chunk 记录：源文件路径 + 内容 hash + **git commit sha**
- 检索命中后能知道"这条知识来自 commit `a3f2c1` 的 `docs/xxx.md`"
- 配合增量索引（文件 hash 清单），只有变更文件重新嵌入

### 本仓库落地建议

```gitignore
target/          # mdBook 构建产物
.index/          # 向量索引
.memsearch/
```

工作流：`docs/` 内容照常 git 管理 → 索引目录 gitignore → CI 或 hook 里 `mdbook build` + 重建索引 → embedding 配置（模型名 + 维度 + 分块策略）提交入库。换机器：`git clone` + 装 embedding 依赖 + 跑一次索引构建 = 完整环境。

---

## 六、选型建议（针对本仓库）

本仓库是 mdBook 中文技术笔记，做向量知识库 ROI 高，内容检索与代码搜索是两种场景：

| 场景 | 建议 |
|------|------|
| 快速验证（索引 `docs/`） | `opencode-rag-plugin`：`opencode-rag init` 即用；中文场景配置 bge-m3 / multilingual-e5 embedding |
| Agent 长期记忆 | `@mathew-cf/opencode-memory`：keyword + semantic 双后端，适合既有精确术语又有概念检索的需求 |
| 自研（deepseek harness） | 写 Cordis 插件注册检索工具或挂现成 MCP；注意 developer preview 阶段 API 仍在变 |

mdBook 自带 mdbook-search 是给人用的客户端全文检索；给 Agent 用的知识库才需要向量化，两者不冲突。

---

## 七、参考方案清单

| 方案 | 存储/检索 | 特点 |
|------|-----------|------|
| [opencode-rag-plugin](https://www.npmjs.com/package/opencode-rag-plugin) | 本地向量库 + TF-IDF 混合 | tree-sitter AST 分块（26 语言 + Markdown/PDF）、自动注入上下文、RAG on/off token 评测、`/wiki` 模式 |
| [@mathew-cf/opencode-memory](https://github.com/mathew-cf/opencode-memory) | git 仓库 + rg 关键词 + 本地 embedding | 跨会话记忆、hook 提醒先搜记忆、内存模型 ~90MB |
| [rajarshighoshal/opencode-memory](https://github.com/rajarshighoshal/opencode-memory) | SQLite + sqlite-vec + FTS5 | 单 Rust 二进制、RRF 混合检索、关联图、llama.cpp 本地 embedding |
| opencode-memsearch | Milvus Lite | 每轮对话自动摘要入库、冷启动上下文注入、daemon 模式 ~50ms 延迟 |
| mnemory | 自建服务 | 插件 + 16 个记忆工具、hook 全自动召回、服务离线时优雅降级 |
| [@lotargo/memory_plugin](https://www.npmjs.com/package/@lotargo/memory_plugin) | SQLite FTS5 + ONNX E5 + RRF | 零 Docker、3 层分块、多语言（含中文）、PDF/DOCX/XLSX 解析 |
| OpenViking | 云服务 | 跨项目跨会话记忆 + 索引仓库上下文，多 harness 统一 |

### 相关官方资料

- opencode 插件与自定义工具：<https://opencode.ai/docs/plugins/>
- opencode MCP 与工具权限：<https://opencode.ai/docs/mcp-servers/>
- DeepSeek Harness：<https://deepseek.com/harness/en/>
