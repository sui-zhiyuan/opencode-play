# 数据工程二期：Daft Builtin 性能优化（Daft-Kunpeng 优化）系统需求分析文档

## 简介

### 目的
本系统需求分析文档旨在针对 Daft 数据引擎在华为鲲鹏（Kunpeng）ARM 服务器上的执行性能进行系统性优化。通过分析版本初始需求包中的所有需求，进行需求分类、场景分析和用例分析，输出结构化的系统需求（SR），为后续的设计与开发提供明确的指导。

### 范围
系统名称：数据工程二期，Daft Builtin 性能优化（Daft-Kunpeng 优化）

* **做什么**：优化 Daft v0.7.2 在鲲鹏 950、920B、920 上的执行性能。覆盖文本、图片、视频、音频、PDF、自动驾驶六种模态，分为两大方向：UDF 执行效率优化、Daft Rust 内核优化。
* **不做什么**：不修改 Daft 的 SQL 引擎、存储格式、分布式调度框架（Ray）的核心逻辑；不新增 Daft 原生功能。
* **目标产线（6 条）**：
  1. `pipeline_text_fineweb_full_min`（文本）
  2. `video_scene_split_etl`（视频）
  3. `pipeline_image_full_min`（图片）
  4. `audio_asr_prep_canonical`（音频）
  5. `pipeline_pdf_full_min`（PDF）
  6. `pipeline_ad_nuscenes_min`（自动驾驶）

### 假设和约束

#### 出口管制

本产品为纯软件性能优化项目，基于开源 Daft 数据引擎（Apache 2.0 协议）在华为鲲鹏 ARM 服务器上做代码级优化，不涉及硬件物料采购、不包含加密功能、不使用 TPM 芯片。各约束项确认如下：

| 序号 | 约束描述 | 产品确认 | 备注 |
|------|---------|---------|------|
| 1 | 如果使用了出口到中国受控的物料，需要提前申请许可证 | 不涉及 | 本产品为纯软件优化，不采购或使用任何受控硬件物料 |
| 2 | 供应商限制销往特定区域的外购件选型规避 | 不涉及 | 无外购硬件部件。软件依赖均为开源（Daft、Arrow、Ray 等），使用 Apache 2.0 / MIT 许可证，无区域销售限制 |
| 3 | 目标市场涉及欧亚地区部 A 类管理国家时，包含强加密功能的管控 | 不涉及 | 本产品不包含任何加密功能（IPSEC/MACSEC 等）。hash 算法（CRC32C、xxHash）为单向散列，不属于加密 |
| 4 | 使用 TPM 芯片（海外芯片禁国内销售，国内芯片禁海外销售） | 不涉及 | 本产品为纯软件，不使用任何 TPM 芯片 |
| 5 | 使用未公开加密算法（SSF33、SM1、SM7）在海外销售的限制 | 不涉及 | 本产品不包含任何加密算法，更未使用未公开商密算法 |
| 6 | 销往法属市场且包含 R226 管控特性（如短信中心转发接口） | 不涉及 | 本产品为数据处理引擎性能优化，不包含任何电信网络管控特性 |

#### 其它假设和约束
1. 基于 Daft v0.7.2（commit 3f5bdd1），UDF API 为 `@daft.udf`（v1，支持 concurrency/batch_size）。`@daft.func` v2 API 未引入。
2. 性能优化目标平台：Kunpeng 950；Kunpeng 920B/920 仅需保证代码正确执行。
3. 所有 ARM 优化通过 `cfg(target_arch = "aarch64")` 与运行时 CPU feature 检测（`is_aarch64_feature_detected!`）门控，不支持的平台回退通用路径。
4. 所有修改应具备上游合入 Daft mainline 的可行性。
5. 视频加速依赖鲲鹏 BoostKit x265 库，为外部依赖；其余优化均为 Daft 内置实现。
6. Daft 当前使用 arrow2（正讨论迁移到 arrow-rs，见 #5741），优化需考虑此迁移。
7. Daft 的 hash 算法选择必须在集群级保持一致——在 x86 与 ARM 混合集群中，不同节点使用不同 hash 算法会导致 groupby/join 路由不一致。

### 系统上下文
* **目标市场**：鲲鹏 ARM 服务器用户（国内数据中心、AI 数据管线场景）。
* **已有设计资产**：
  * `daft-kunpeng-perf-design-spec.md`（性能设计规格）
  * `daft-kunpeng-perf-design-input.md`（性能设计输入）
  * `daft-kunpeng-udf-inventory.md`（UDF 清单）
  * `rust-kunpeng.md`（Rust 鲲鹏战略）
* **场景清单**：6 条目标 pipeline 的定义见 volc_operator_sim 项目的 `tasks/*.json`。
* **Daft 源码位于**：`/home/suine/projects/Daft/src/`。
* **测试目标位于**：`/home/suine/projects/volc_operator_sim/`。

---

## 需求分析概述

### 需求分类

本版本共 2 个顶层 IR，覆盖文本、图片、视频、音频、PDF、自动驾驶全部六种模态：

| IR编号 | 优化方向 | 目标模态 | 需求类型 | 分析策略 |
|--------|---------|---------|---------|---------|
| IR-1 | UDF 执行效率优化 | 文本、图片、视频、音频、PDF、自动驾驶 | 功能性 | UseCase 分析（跨功能域） |
| IR-2 | Daft Rust 内核优化 | 文本、图片、视频、音频、PDF、自动驾驶 | 功能性 | UseCase 分析（跨功能域） |

两个 IR 均涉及多个功能域（逻辑优化器、物理翻译、执行引擎、分布式调度），都需要跨功能域 IR 需求分析。

非功能性需求：性能（吞吐量目标）、兼容性（多平台支持）、可靠性（CPU feature 降级）。

### 文档策略
* 功能性需求按 2 个 IR 分别展开 UseCase 分析，每个 IR 内部按子项细分 SR。
* 非功能性需求独立输出到本文档第 4 章。

---

## 初始需求澄清

### 场景分析

本节对 IR-1 和 IR-2 进行场景分析，覆盖运行场景、操作维护场景，澄清需求信息、系统外部接口和兼容性约束。

#### 业务场景分析

本产品面向六种模态的数据处理产线，均以 Daft DataFrame pipeline 形式运行在 Ray 集群上。以组网为主线划分场景如下：

**场景 1：文本数据清洗与去重（pipeline_text_fineweb_full_min）**

| 维度 | 描述 |
|------|------|
| 数据流 | 文件源 → 11 步文本清洗链（clean_html → clean_links → clean_email → clean_copyright → fix_unicode → punctuation_normalization → whitespace_normalization → text_length_filter → alphanumeric_filter → language_id_score_filter → perplexity_filter）→ text_chunk_mapper → 输出 |
| 瓶颈特征 | 大量字符串处理（正则替换、Unicode 规范化、语种检测），Python UDF 逐行执行，11 次 Python↔Rust 边界往返 |
| IR-1 影响 | Rust 重写清洗链（消除 11 次边界）+ UDF 链融合（合并为单一节点） |
| IR-2 影响 | dedup 阶段 CRC32C hash 加速、`length_bytes` offset 快路径、filter 后 SVE gather |
| 外部依赖 | fastText 语种检测模型、KenLM 困惑度模型——不参与融合，保持独立 UDF |
| 配置 | `ray_num_cpus=4`，`dj_np=4` |

**场景 2：视频场景切分与帧抽取（video_scene_split_etl）**

| 维度 | 描述 |
|------|------|
| 数据流 | 视频文件源 → ffmpeg wrapped mapper（解码/转分辨率）→ resize_resolution_mapper → split_by_scene_mapper → duration_filter → split_by_duration_mapper → extract_frames_mapper → 输出 |
| 瓶颈特征 | ffmpeg 子进程开销（scene detection、frame extraction）、CPU 密集型转码（x264/x265） |
| IR-1 影响 | BoostKit x265 硬件加速转码（替代软件 x265），减少 CPU 开销 |
| IR-2 影响 | UDF 并发度自适应（视频 CPU 密集场景调整并发避免过载）、节点间数据调度（大视频文件跨 socket 传输优化） |
| 外部依赖 | ffmpeg + BoostKit x265 库，需在目标节点预装 |
| 配置 | `ray_num_cpus=16`，`dj_np=16`，`concurrency_limits.io=8` |

**场景 3：图片质量过滤与去重（pipeline_image_full_min）**

| 维度 | 描述 |
|------|------|
| 数据流 | 文件源 → download_file_mapper → image_shape_filter → aspect_ratio_filter → size_filter → blur_mapper → image_deduplicator → aesthetics_filter → text_similarity_filter → clip_vectorize_mapper → write_lance |
| 瓶颈特征 | OpenCV/PIL 图像处理（形状检测、Laplacian 方差）、aHash 图像去重 |
| IR-1 影响 | image_blur_mapper Rust 重写（Laplacian 方差计算替代 PIL/OpenCV） |
| IR-2 影响 | deduplicator CRC32C hash 加速 |
| 外部依赖 | OpenCV、CLIP 模型（GPU/stub）、图像审美模型（stub） |
| 配置 | `ray_num_cpus=4`，`dj_np=4` |

**场景 4：音频预处理（audio_asr_prep_canonical）**

| 维度 | 描述 |
|------|------|
| 数据流 | 音频文件源 → ffmpeg wrapped mapper（×3，格式转换/重采样/声道处理）→ duration_filter → nmf_snr_filter → 输出 |
| 瓶颈特征 | ffmpeg 子进程转码，IO 密集，CPU 利用率低 |
| IR-1 影响 | 跨界零拷贝（减少 Python↔Rust 边界开销） |
| IR-2 影响 | UDF 并发度自适应（IO 等待场景提升并发度利用空闲 CPU）、节点间数据调度 |
| 配置 | `ray_num_cpus=16`，`dj_np=16`，`concurrency_limits.io=8` |

**场景 5：PDF 解析与向量化（pipeline_pdf_full_min）**

| 维度 | 描述 |
|------|------|
| 数据流 | PDF 文件源 → pdf_parse_mapper → pdf_ocr_mapper → pdf_table_extract_mapper → text_chunk_mapper → bge_vectorize_mapper → write_lance |
| 瓶颈特征 | PDF 解析（pdfplumber/pdf2image/tesseract），大部分算子为 stub |
| IR-1 影响 | text_chunk_mapper 参与 Rust 重写（与文本场景共享） |
| IR-2 影响 | `length_bytes` offset 快路径、SVE cntp 字符长度计算 |
| 配置 | `ray_num_cpus=4`，`dj_np=4` |

**场景 6：自动驾驶传感器对齐（pipeline_ad_nuscenes_min）**

| 维度 | 描述 |
|------|------|
| 数据流 | nuScenes 数据集 → sensor_align_mapper → ad_index_mapper → write_lance |
| 瓶颈特征 | JSON 元数据解析（calibrated_sensor/sensor/ego_pose）、文件索引构建，CPU 负载低 |
| IR-1 影响 | 跨界零拷贝 |
| IR-2 影响 | UDF 并发度自适应（低负载场景避免过度并发） |
| 配置 | `ray_num_cpus=4`，`dj_np=4` |

**场景兼容性分析**：
* 所有场景均兼容 Kunpeng 920（无 SVE）和 x86_64 平台——SVE 相关优化通过运行时检测自动降级
* 跨架构集群（x86 + ARM 混合）中，hash 算法需集群级配置保持一致，避免 groupby/join 路由错误
* BoostKit x265 为可选依赖——未安装时自动回退软件 x265

**场景覆盖总结**：

| 场景 | 模态 | IR-1 子项 | IR-2 子项 | 外部依赖 |
|------|------|----------|----------|---------|
| 场景 1 | 文本 | 1.3 链融合、1.4 Rust 重写（11 算子） | 2.1 并发自适应、2.3 CRC32C、2.4 SVE、2.5 Offset | fastText, KenLM |
| 场景 2 | 视频 | 1.1 零拷贝、1.5 BoostKit | 2.1 并发自适应、2.2 数据调度 | ffmpeg, BoostKit x265 |
| 场景 3 | 图片 | 1.1 零拷贝、1.4 Rust 重写（blur） | 2.3 CRC32C | OpenCV |
| 场景 4 | 音频 | 1.1 零拷贝 | 2.1 并发自适应、2.2 数据调度 | ffmpeg |
| 场景 5 | PDF | 1.1 零拷贝、1.4 Rust 重写（text_chunk） | 2.4 SVE、2.5 Offset | pdfplumber, tesseract |
| 场景 6 | 自动驾驶 | 1.1 零拷贝 | 2.1 并发自适应 | — |

#### 操作场景分析

本节描述数据工程师与系统的交互，以及优化功能的配置与控制。

**操作场景 1：UDF 定义与注册**

| 维度 | 描述 |
|------|------|
| Actor | 数据工程师 |
| 前置条件 | volc_operator_sim 项目已部署，Ray 集群已启动 |
| 交互流程 | 1. 数据工程师在 `ops/*.py` 中定义 UDF 函数 2. 通过 `registry.py` 注册算子名称 3. 在 `tasks/*.json` 中编排 pipeline 步骤 4. 执行 runner 启动 pipeline |
| 系统行为 | Daft 根据 `@daft.udf` 装饰器参数（batch_size、concurrency）配置 UDF 执行模式 |
| 异常处理 | UDF 定义中缺少必需参数时，Daft 在逻辑计划构建阶段报错 |

**操作场景 2：优化功能开关控制**

| 维度 | 描述 |
|------|------|
| Actor | 数据工程师、运维人员 |
| 前置条件 | Daft-Kunpeng 优化已部署 |
| 交互方式 | 环境变量控制各优化子项的启用/禁用 |

| 环境变量 | 控制子项 | 默认值 | 说明 |
|----------|---------|--------|------|
| `DAFT_ARM_ENABLE_CRC32C_ROW_HASH` | 2.3 CRC32C | 0 | 设为 1 启用 ARM CRC32C hash 加速 |
| `DAFT_FUSE_UDFS` | 1.3 链融合 | 1 | 设为 0 关闭 UDF 链融合 |
| `DAFT_RUST_TEXT_KERNEL` | 1.4 Rust 重写 | 1 | 设为 0 回退 Python UDF 路径 |
| `DAFT_SVE_ENABLE` | 2.4 SVE 向量化 | 1 | 设为 0 禁用 SVE 路径（降级 NEON/标量） |
| `VOLC_UDF_CONCURRENCY` | 2.1 并发自适应 | auto | 设为具体数值覆盖自适应，固定并发度 |
| `VOLC_UDF_BATCH_SIZE` | 1.1 批大小 | auto | 批处理行数 |

| 异常处理 | 无效值静默回退默认值；CRC32C/SVE 运行时检测失败时自动降级 |
| Buildrun 验证 | 部署后运行 `cargo test --features aarch64` 确认 ARM 路径编译正确；在 920B 上运行 benchmark 确认优化路径正常触发 |

**操作场景 3：跨架构集群部署**

| 维度 | 描述 |
|------|------|
| Actor | 运维人员 |
| 前置条件 | Ray 集群包含 x86_64 和 aarch64 混合节点 |
| 交互流程 | 1. 运维人员确认各节点 CPU feature 2. 配置集群级 `hash_algorithm` 参数（集群内所有节点必须一致）3. 部署统一 wheel 包至所有节点 |
| 系统行为 | 各节点运行时检测 CPU feature，独立选择优化路径（hash 除外——hash 算法由集群级配置统一决定） |
| 兼容性约束 | 不支持 SVE 的 ARM 节点（Kunpeng 920）自动降级 NEON；x86 节点仅走通用路径 |

#### 维护场景分析

**维护场景 1：性能回归与故障定位**

| 维度 | 描述 |
|------|------|
| 故障模型 | 优化路径输出与通用路径不一致、SVE/CRC32C 指令在非支持平台触发 SIGILL |
| 定位手段 | 1. 通过环境变量逐子项关闭优化，二分定位问题子项 2. `RUSTFLAGS="-C remark=all" cargo build` 查看 LLVM 向量化 remark 3. `cargo asm` 检查生成代码是否包含预期 ARM 指令 |
| 恢复手段 | 关闭问题子项的环境变量开关，回退通用路径后重新执行 |
| 预防措施 | CI 流程：每次 PR 在 920B 硬件上运行 stdarch SVE 测试套件 + 全量 benchmark 对比 |

**维护场景 2：业务统计与监控**

| 维度 | 描述 |
|------|------|
| 关键指标 | 每条 pipeline 中 UDF 执行耗时占比、hash 计算耗时、Python↔Rust 边界转换次数 |
| 展现方式 | Daft Dashboard（v0.7.20 已支持）显示 pipeline 各阶段耗时分布；日志输出当前启用的优化路径 |
| 统计命令 | `daft.sql("SELECT * FROM daft_query_history")` 查询历史执行指标 |

### 结构化 IR 刷新

根据上述场景分析，补充 IR-1 和 IR-2 的结构化信息：

| IR标识 | IR-1 | IR-2 |
|--------|------|------|
| 名称 | UDF 执行效率优化 | Daft Rust 内核优化 |
| 描述 | 减少 Python↔Rust 跨界损耗、Rust 重写高频 UDF 算子、UDF 链物理融合、BoostKit 视频加速 | UDF 并发度自适应、节点间数据调度、ARM CRC32C/SVE 硬件加速、文本处理快路径 |
| 优先级 | 高 | 高 |
| 5W2H: who | 数据工程师 | 数据工程师、Ray 集群运维人员 |
| 5W2H: what | 降低 UDF 执行路径中的序列化与调度开销 | 利用鲲鹏硬件特性和调度策略优化 Rust 内核性能 |
| 5W2H: where | Daft Python↔Rust 边界、逻辑优化器、执行引擎 | Daft Rust 计算内核、分布式调度层 |
| 5W2H: when | UDF 定义与执行阶段 | 查询编译与运行时 |
| 5W2H: why | 6 条 pipeline 中 UDF 调用占主导（31/44 算子为 CPU UDF），跨界开销是核心瓶颈 | 鲲鹏硬件能力（CRC32C/SVE/NUMA）未传递到 Daft 计算层 |
| 5W2H: how | Arrow C Data Interface 零拷贝传输 + Rust kernel 下沉 + 逻辑计划层链融合 | 条件编译 + 运行时 CPU feature 检测 + 环境变量门控 |
| 类别 | 功能性 | 功能性 |
| 场景列表 | 场景 1-6（全部） | 场景 1-6（全部） |
| 系统接口定义 | Python `@daft.udf` API；环境变量配置接口 | 环境变量配置接口；集群级 `hash_algorithm` 配置 |

---

## 功能性需求分析

### 跨功能域分析：IR-1 UDF 执行效率优化

#### 优化范围

IR-1 针对 Daft UDF 执行引擎中 Python ↔ Rust 边界及 UDF 链路的系统性优化，涉及以下功能域：

```
┌─ Python 层 ──────────────────────────────────────────────┐
│  @daft.udf UDF 定义  +  BoostKit x264/x265 视频转码      │
│     │                          │                          │
│     │ ① 跨界零拷贝           │ 外部依赖（ffmpeg）         │
│     ▼                          ▼                          │
├─ Rust 边界层 ────────────────────────────────────────────┤
│  daft-dsl/src/python.rs  →  UDF 注册与参数提取           │
│  daft-dsl/src/functions/python/  →  UDF 属性解析         │
│     │                                                     │
│     │ ② 结构体转换优化                                    │
│     ▼                                                     │
├─ 逻辑计划层 ─────────────────────────────────────────────┤
│  daft-logical-plan/src/ops/udf.rs  →  UDFProject 节点    │
│  daft-logical-plan/src/optimization/rules/split_udfs.rs   │
│     │                                                     │
│     │ ③ UDF 链物理融合                                    │
│     ▼                                                     │
├─ 物理翻译层 ─────────────────────────────────────────────┤
│  daft-local-plan/src/translate.rs  →  逻辑→物理映射      │
│     │                                                     │
│     ▼                                                     │
├─ 执行引擎层 ─────────────────────────────────────────────┤
│  daft-local-execution/src/intermediate_ops/udf.rs         │
│  → UdfOperator（Thread/Process 模式）                     │
│                                                           │
│  daft-distributed/src/pipeline_node/                     │
│  → actor_udf.rs（Actor Pool 分布式执行）                  │
└───────────────────────────────────────────────────────────┘
```

**源码探索确认**：当前所有关键路径均无 ARM 特化。UDF 数据传递走 PyArrow 序列化路径（daft-dsl/src/functions/python/udf.rs；daft-dsl/src/python_udf/batch.rs），非零拷贝。

#### 子项分解

| 子项 | 内容 | 涉及模态 | 影响功能域 |
|------|------|---------|-----------|
| 1.1 跨界零拷贝 | Arrow C Data Interface 替代 PyArrow 序列化，消除 Python↔Rust 数据拷贝 | 全部六种 | daft-dsl Python runtime、daft-local-execution UdfOperator |
| 1.2 结构体转换优化 | 减少 Rust struct → Python object 的中间分配，批量传递列数据 | 全部六种 | daft-dsl/functions/python/ |
| 1.3 UDF 链物理融合 | 相邻 UDFProject 节点合并为单个节点，消除中间调度与物化边界 | 文本（11 算子链）、图片 | daft-logical-plan optimizer、daft-local-plan translate |
| 1.4 Rust 重写高频算子 | 文本清洗链 11 个算子 + image_blur_mapper 用 Rust 重写，消除 Python 解释器开销 | 文本、图片 | daft-functions-utf8（或新增 daft-functions-text） |
| 1.5 BoostKit 视频加速 | 鲲鹏 BoostKit x265 替代软件 x265 转码 | 视频 | Python UDF 层（外部依赖，不修改 Daft 源码） |

#### IR-1 UseCase 分析

【简要说明】
Daft 产线中 UDF 调用占主导（6 条 pipeline 合计 44 个算子中 31 个为 CPU UDF），UDF 执行效率是整体性能瓶颈。当前执行路径存在多次 Python↔Rust 边界跨越：Rust 列数据 → PyArrow 序列化 → Python UDF → PyArrow 反序列化 → Rust 列数据。每条 pipeline 可能经历 10+ 次此类往返。优化方向：用 Arrow C Data Interface 实现零拷贝传输、将高频 Python UDF 下沉为 Rust 原生 kernel、融合连续 UDF 节点减少调度开销。

【Actor】数据工程师（通过 Python DataFrame API 定义和调用 UDF）

【前置条件】
* UDF 使用 `@daft.udf` 装饰器注册，运行在 Ray 集群上
* 目标节点为鲲鹏 ARM 服务器（Kunpeng 950/920B/920）
* volc_operator_sim 项目的 `pipeline_builder.py` 已实现 mapper 链融合（`compose_mapper_chain()`）

【最小保证】任一优化路径不可用时，回退到当前 PyArrow 序列化路径和 Python UDF 执行，功能行为不变。

【成功保证】
* 子项 1.1/1.2：batch mode UDF 的输入输出通过 Arrow C FFI 零拷贝传递，消除 PyArrow 转换开销
* 子项 1.3：连续 mapper UDF 链合并为单一 UDFProject 节点，减少 N−1 次中间调度和物化
* 子项 1.4：11 个文本清洗算子编译为单个 Rust 函数，内部按序执行，消除 11 次 Python↔Rust 边界往返
* 子项 1.5：视频转码使用 BoostKit x265 硬件加速，降低 CPU 开销

【触发事件】数据工程师执行任一条目标 pipeline

【主成功场景】
1. 数据工程师定义 UDF 并通过 `@daft.udf` 注册（支持 batch_size、concurrency 参数）
2. Daft 逻辑计划将 UDF 表达式包装为 UDFProject 节点
3. 逻辑优化器检测可融合的相邻 UDFProject 节点，合并为单一节点
4. 物理翻译时检测 batch mode UDF，启用 Arrow C Data Interface 零拷贝路径
5. 若已提供 Rust kernel 实现（子项 1.4），执行引擎直接调用 Rust kernel，跳过 Python 运行时
6. 视频产线中，BoostKit x265 通过 ffmpeg `-c:v libx265` 命令行调用加速转码
7. 数据流水线继续执行下游算子

【扩展场景】
* **1a. Arrow 类型不匹配**：降级为 PyArrow 序列化路径
* **2a. 依赖外部模型的算子（fastText/KenLM/sentencepiece）**：不参与 Rust 重写和链融合，保持独立 Python UDF
* **3a. UDF 链中存在 Filter/Join/GroupBy 等非 Project 算子**：以此为融合边界，不跨 barrier 融合
* **4a. 目标节点未安装 BoostKit x265**：回退到软件 x265 编码

【DFX 属性】
* Rust kernel 需处理 null 列值和空字符串边界情况
* 每个优化子项需提供 feature flag 或环境变量开关，支持独立启用/禁用

【功能影响列表】是。影响 daft-dsl、daft-logical-plan（优化器）、daft-local-plan（物理翻译）、daft-local-execution（UdfOperator）、daft-distributed（Actor Pool）五个功能域。

【需求分解列表】

| SR编号 | 关联功能 | 描述 |
|--------|---------|------|
| SR-1-01 | Python UDF runtime | Arrow C Data Interface 零拷贝传输路径，类型不匹配时自动降级 |
| SR-1-02 | UDF 执行算子 | 结构体序列化路径优化，批量传递列数据 |
| SR-1-03 | 逻辑优化器 | FuseUDFs 规则——检测并合并相邻 UDFProject 节点 |
| SR-1-04 | Rust kernel（文本） | 11 个文本清洗算子的 Rust 实现，算子级 feature flag 调试开关 |
| SR-1-05 | Rust kernel（图片） | image_blur_mapper 的 Rust 实现（Laplacian 方差计算） |
| SR-1-06 | 视频 UDF | BoostKit x265 集成路径——ffmpeg 命令行配置与环境检测 |

---

### 跨功能域分析：IR-2 Daft Rust 内核优化

#### 优化范围

IR-2 针对 Daft Rust 内核层进行性能优化，涵盖三个方向：调度策略改进（UDF 并发度自适应、节点间数据调度）、硬件指令加速（CRC32C hash、SVE 向量化）、热路径算法优化（Text Offset 快路径）。涉及以下功能域：

```
├─ 调度层 ─────────────────────────────────────────────────┐
│  daft-distributed/src/pipeline_node/actor_udf.rs          │
│  → Actor Pool 并发管理                                    │
│                                                           │
│  daft-local-execution/src/run.rs                          │
│  → Pipeline 图 → Tokio 本地执行                           │
│     │                                                     │
│     │ ① UDF 并发度自适应                                   │
│     │ ② 节点间数据调度（Flight Shuffle / NUMA-aware）       │
│     ▼                                                     │
├─ 计算内核层 ──────────────────────────────────────────────┤
│  daft-hash/src/lib.rs  →  HashFunctionKind                │
│  daft-core/src/kernels/hashing.rs  →  per-type hash       │
│  daft-recordbatch/src/ops/hash.rs  →  row-hash chaining   │
│     │                                                     │
│     │ ③ CRC32C 硬件 hash 加速                              │
│     ▼                                                     │
│  daft-core/src/array/ops/take.rs  →  gather/scatter       │
│     │                                                     │
│     │ ④ SVE gather-load 批量取数                           │
│     ▼                                                     │
│  daft-functions-utf8/src/length_bytes.rs                  │
│  daft-functions/src/length.rs                             │
│     │                                                     │
│     │ ⑤ SVE cntp UTF-8 字符长度                            │
│     │ ⑥ Offset 差分快路径（文本字节长度）                   │
│     ▼                                                     │
└───────────────────────────────────────────────────────────┘
```

**源码探索确认**：
* Daft hash 当前支持 5 种算法（MurmurHash3、XxHash32、XxHash64、XxHash3_64、Sha1），无 CRC32C。`DAFT_ARM` 环境变量不存在。
* `length_bytes` 为标量迭代（`val.len()`），`length` 为 `chars().count()`，`take` 委托给 `arrow::compute::take`。均无 SIMD/SVE。
* Daft 全代码库无 `cfg(target_arch = "aarch64")` 条件编译。

#### 子项分解

| 子项 | 内容 | 涉及模态 | 影响功能域 |
|------|------|---------|-----------|
| 2.1 UDF 并发度自适应 | 试探回退自适应算法，自动收敛到最优并发度 | 全部六种 | daft-distributed、daft-local-execution |
| 2.2 节点间数据调度 | Flight Shuffle NUMA-aware 优化，跨 socket 数据传输优化 | 全部六种 | daft-distributed（数据平面） |
| 2.3 CRC32C Hash 加速 | ARM CRC32C 硬件指令替代 xxHash 用于 groupby/join/dedup | 文本（dedup）、图片（image_deduplicator） | daft-hash、daft-core/kernels/hashing.rs |
| 2.4 SVE 向量化 | SVE cntp UTF-8 长度 + SVE gather-load 批量取数 | 文本（length/filter 后重排）、PDF | daft-functions-utf8、daft-core/array/ops/take.rs |
| 2.5 Text Offset 快路径 | Arrow offset buffer 差分替代逐元素 `val.len()` | 文本、PDF | daft-functions-utf8/length_bytes.rs |

#### IR-2 UseCase 分析

【简要说明】
IR-2 聚焦 Daft Rust 侧的调度策略和计算内核优化。调度策略方面：当前 UDF 固定并发度无法适应不同产线负载特征（视频 CPU 密集型 vs 文本 I/O 等待外部模型），且分布式环境下跨 socket 数据传输未做 NUMA 亲和优化。计算内核方面：鲲鹏 920B 的 CRC32C 和 SVE 硬件指令未被利用，hash 计算和字符串处理走通用软件路径。

【Actor】数据工程师、Ray 集群调度器

【前置条件】
* 运行在鲲鹏 ARM 服务器上，920B 支持 CRC32C + SVE（256-bit），920 仅支持 CRC32C
* 子项 2.3 需要环境变量 `DAFT_ARM_ENABLE_CRC32C_ROW_HASH=1` 显式启用
* 子项 2.4 需要 SVE feature 运行时检测通过（`is_aarch64_feature_detected!("sve")`）

【最小保证】
* 子项 2.1：自适应机制失败时回退到固定并发度
* 子项 2.3：CRC32C 不可用时静默回退 XxHash3_64
* 子项 2.4：SVE 不可用时降级为 NEON 128-bit 或标量循环；x86_64 平台功能行为不变
* 子项 2.5：无条件可用（Arrow offset buffer 始终存在）

【成功保证】
* 子项 2.1：UDF 并发度自动收敛到当前产线和硬件环境的最优值
* 子项 2.2：跨 socket 数据 shuffle 利用 NUMA 拓扑降低延迟，LZ4 压缩减少传输量
* 子项 2.3：groupby/join/dedup 的 hash 计算使用 ARM CRC32C 指令加速（目标 2x+ vs xxHash）
* 子项 2.4：UTF-8 字符长度 SVE 256-bit 向量化（目标 3x+ vs 标量）；primitive 数组 gather SVE 批量取数（目标 2x+ vs 标量）
* 子项 2.5：`col.str.length_bytes()` 直接从 offset buffer 计算，O(1) per row

【触发事件】数据工程师执行 `df.groupby("col").agg(...)`、`df.join(other, on="key")`、`col.str.length()` 或 filter 后重排操作

【主成功场景】
1. 数据工程师启动 pipeline
2. Daft 为每个 UDF 阶段初始化并发度 = worker 核心数，开启试探回退自适应模式
3. 递增期：每次提升并发度后测量吞吐量，若提升则继续递增；若下降则回退到最优值
4. 稳定期：连续 N 次确认无增益后锁定并发度
5. 分布式 shuffle 阶段，worker 利用 NUMA 拓扑就近访问本地 socket 内存
6. groupby/join 执行时，hash 内核检测 ARM CRC32C 可用性，启用硬件加速路径
7. 文本处理时，`length_bytes` 走 offset 差分快路径；`col.str.length()` 走 SVE cntp 向量化路径
8. filter 后重排时，take/gather 走 SVE gather-load 批量取数路径

【扩展场景】
* **1a. 节点间数据调度——跨架构集群（x86 + ARM 混合）**：不同节点使用不同 hash 算法导致 groupby/join 路由不一致，需集群级一致决策
* **2a. CRC32C 性能未必优于 SVE2 加速的 xxHash**：xxHash 已有 SVE 实现（PR #683/#752），需 benchmark 验证后选择最优算法
* **3a. 数组长度不足 SVE 向量宽度**：tail 部分用 WHILELT 谓词掩码处理
* **4a. 非 primitive 类型（Utf8、Binary、List）的 take/gather**：回退到通用 arrow::compute::take 路径
* **5a. 调度自适应在产线规模较小时收敛慢**：设置最小样本数阈值，不足时使用固定并发度

【DFX 属性】
* CPU feature 检测失败时静默回退通用路径，不得 panic 或 core dump
* CRC32C/SVE 门控通过环境变量 + 运行时检测双重保障

【功能影响列表】是。影响 daft-distributed（调度）、daft-hash（CRC 算法）、daft-core（hashing、take）、daft-functions-utf8（length_bytes）四个功能域。

【需求分解列表】

| SR编号 | 关联功能 | 描述 |
|--------|---------|------|
| SR-2-01 | UDF 并发管理 | 试探回退自适应并发度算法 + 运行时指标采集 |
| SR-2-02 | 分布式数据平面 | Flight Shuffle NUMA-aware 优化——利用 920B 灵衢总线拓扑就近调度 |
| SR-2-03 | daft-hash | Crc32Hasher + HashFunctionKind::Crc32c 新增 |
| SR-2-04 | daft-core hashing | ARM CRC32C per-type hash 分发 + `DAFT_ARM_ENABLE_CRC32C_ROW_HASH` 门控 |
| SR-2-05 | daft-functions-utf8 | SVE cntp UTF-8 字符长度计算 |
| SR-2-06 | daft-core take | SVE gather-load 批量取数（i32/i64/f32/f64 primitive 数组） |
| SR-2-07 | daft-functions-utf8 | length_bytes offset 差分快路径——Arrow offset buffer 直接计算 |

---

## 非功能性需求分析

### 性能需求

| 需求编号 | 描述 | 关联 IR | 度量指标 |
|---------|------|--------|---------|
| NF-P01 | UDF 跨边界传输延迟降低（全部六种模态） | IR-1 | Python↔Rust 单次转换延迟（目标 < 10μs） |
| NF-P02 | 视频转码吞吐量提升 | IR-1 | 转码 fps（目标 1.5x+ vs 软件 x265） |
| NF-P03 | UDF 并发度自适应收敛 | IR-2 | 收敛后吞吐量不低于固定并发度最优值的 95% |
| NF-P04 | Hash 计算吞吐量提升（dedup/groupby/join） | IR-2 | 行 hash 吞吐量（目标 2x+ vs xxHash） |
| NF-P05 | UTF-8 文本处理加速 | IR-2 | `col.str.length()` 延迟（目标 3x+ vs 标量） |
| NF-P06 | Gather 批量取数加速（filter 后重排） | IR-2 | take 操作延迟（目标 2x+ vs 标量） |

### 平台兼容性需求

| 需求编号 | 描述 | 实现方式 |
|---------|------|---------|
| NF-C01 | 所有 ARM 优化必须在非 ARM 平台正确回退（不触发 SIGILL） | `cfg(target_arch = "aarch64")` + `is_aarch64_feature_detected!` |
| NF-C02 | SVE 优化必须在无 SVE 的 ARM 平台（Kunpeng 920）降级 | 运行时 SVE feature 检测，降级至 NEON/标量 |
| NF-C03 | x86_64 平台功能行为不变 | 条件编译隔离 ARM 代码 |
| NF-C04 | 跨架构集群（x86 + ARM）hash 算法须一致 | 集群级 hash 算法配置，非 per-node 运行时选择 |

### 可靠性需求

| 需求编号 | 描述 |
|---------|------|
| NF-R01 | CPU feature 检测失败时静默回退通用路径，不得 panic 或 core dump |
| NF-R02 | CRC32C/SVE 门控通过环境变量 + 运行时检测双重保障，避免错误启用 |
| NF-R03 | 优化路径与通用路径的输出结果必须 bitwise 一致（hash 除外——不同算法结果不同是预期行为） |
| NF-R04 | Rust 重写算子（子项 1.4）的输出必须与原始 Python 算子一致，通过 golden test 验证 |

### 可测试性需求

| 需求编号 | 描述 |
|---------|------|
| NF-T01 | 每个优化子项需提供独立 benchmark（对比优化前后吞吐量） |
| NF-T02 | 需在 Kunpeng 920B 上建立 CI runner，持续检测 ARM 回归 |
| NF-T03 | SVE 代码需在真实 920B 硬件上运行 stdarch SVE 测试套件 |
| NF-T04 | Rust 重写算子需提供与 Python 原始算子的 golden 对比测试 |

---

## 附录 A：系统上下文详述

### Daft 架构概览（源码探索确认）

Daft 源码位于 `/home/suine/projects/Daft/src/`，workspace 含 40+ crate。关键模块：

| 模块 | 路径 | 职责 | 关联 IR |
|------|------|------|--------|
| daft-core | src/daft-core/ | 核心数据类型（Array、Series）、操作内核（hashing、take、arithmetic） | IR-2 |
| daft-dsl | src/daft-dsl/ | 表达式系统、UDF 定义、函数注册 | IR-1 |
| daft-logical-plan | src/daft-logical-plan/ | 逻辑计划树、优化器规则（SplitUDFs 等） | IR-1 |
| daft-local-plan | src/daft-local-plan/ | 逻辑计划 → 物理计划翻译 | IR-1 |
| daft-local-execution | src/daft-local-execution/ | 本地执行引擎（Swordfish），UdfOperator | IR-1、IR-2 |
| daft-distributed | src/daft-distributed/ | 分布式执行（Ray），Actor Pool UDF，Flight Shuffle | IR-1、IR-2 |
| daft-hash | src/daft-hash/ | 共享 hash 算法枚举和 Hasher 实现 | IR-2 |
| daft-recordbatch | src/daft-recordbatch/ | RecordBatch 操作、hash_rows、groups、joins | IR-2 |
| daft-functions | src/daft-functions/ | 内置函数（length、hash 等） | IR-2 |
| daft-functions-utf8 | src/daft-functions-utf8/ | UTF-8 专用函数（length_bytes 等） | IR-2 |
| daft-micropartition | src/daft-micropartition/ | MicroPartition 数据单元 | IR-1、IR-2 |

查询执行流程：Python API → LogicalPlan → Optimizer（SplitUDFs 等规则）→ PhysicalPlan → Pipeline 图 → 本地执行或 Ray 分布式执行。

### 目标产线 UDF 特征（volc_operator_sim 探索确认）

6 条 pipeline 的 JSON 任务定义位于 `/home/suine/projects/volc_operator_sim/tasks/*.json`：

| Pipeline | 模态 | 算子总数 | CPU UDF 数 | 关键 UDF 类型 |
|----------|------|---------|-----------|-------------|
| pipeline_text_fineweb_full_min | 文本 | 13 | 11 | 清洗链（8 mapper）+ 过滤（3 filter）+ 切分（1 mapper） |
| video_scene_split_etl | 视频 | 6 | 6 | ffmpeg mapper（场景切分、抽帧、转分辨率）+ duration filter |
| pipeline_image_full_min | 图片 | 10 | 6 | 形状/比例/大小 filter + blur mapper + deduplicator |
| audio_asr_prep_canonical | 音频 | 6 | 5 | ffmpeg wrapped mapper（×3）+ duration filter |
| pipeline_pdf_full_min | PDF | 6 | 2 | PDF 解析/OCR mapper + text_chunk mapper |
| pipeline_ad_nuscenes_min | 自动驾驶 | 3 | 1 | sensor_align mapper + index mapper |

UDF 并发度与批大小通过环境变量控制：`VOLC_UDF_CONCURRENCY`、`VOLC_UDF_BATCH_SIZE`、`VOLC_UDF_USE_PROCESS`。

### 关键源码路径速查

| 功能 | 路径 |
|------|------|
| Hash 内核 | `src/daft-core/src/kernels/hashing.rs` |
| Hash 算法枚举 | `src/daft-hash/src/lib.rs` |
| Hash 表达式 | `src/daft-functions/src/hash.rs` |
| Row hash 链 | `src/daft-recordbatch/src/ops/hash.rs` |
| Take/Gather | `src/daft-core/src/array/ops/take.rs` |
| UTF-8 byte length | `src/daft-functions-utf8/src/length_bytes.rs` |
| UTF-8 char length | `src/daft-functions/src/length.rs` |
| UDF 逻辑算子 | `src/daft-logical-plan/src/ops/udf.rs` |
| SplitUDFs 规则 | `src/daft-logical-plan/src/optimization/rules/split_udfs.rs` |
| 逻辑优化器入口 | `src/daft-logical-plan/src/optimization/optimizer.rs` |
| 物理翻译 | `src/daft-local-plan/src/translate.rs` |
| UDF 执行算子 | `src/daft-local-execution/src/intermediate_ops/udf.rs` |
| Actor Pool UDF | `src/daft-distributed/src/pipeline_node/actor_udf.rs` |

---

## 附录 B：不确定性清单

| # | 问题 | 影响 | 关联 |
|---|------|------|------|
| U1 | Kunpeng 950 SVE 向量宽度和微架构参数 | 子项 2.4 SVE 优化需确认 950 的 SVE 能力（向量宽度、指令延迟） | IR-2 |
| U2 | CRC32C vs SVE2 xxHash 在鲲鹏上的性能对比 | 决定子项 2.3 是否值得实现，或应优先采用 SVE2 加速的 xxHash | IR-2 |
| U3 | Daft arrow2 → arrow-rs 迁移时间线 | 影响 Rust kernel（子项 1.4）和 SVE 代码（子项 2.4）的依赖选择 | IR-1、IR-2 |
| U4 | BoostKit x265 在目标节点的安装与兼容性 | 影响子项 1.5 的部署策略 | IR-1 |
| U5 | 跨 socket 数据调度在灵衢总线上的实际收益 | 影响子项 2.2 的优先级和实现深度 | IR-2 |
