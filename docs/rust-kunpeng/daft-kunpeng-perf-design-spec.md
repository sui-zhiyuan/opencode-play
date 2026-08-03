# 1. 功能域概述

## 1.1 功能域定位

本功能域名为 **Daft-Builtin 性能优化**，目标是针对 Daft 数据引擎在华为鲲鹏（Kunpeng）950 ARM 服务器（对标 AMD EPYC 9755）上的执行性能进行系统性优化。优化范围涵盖 UDF 执行效率、编译层算子下沉、硬件指令加速、物理计划融合和调度策略改进。

## 1.2 平台兼容性

| 平台 | 目标 | SVE 支持 | 说明 |
|------|------|---------|------|
| **Kunpeng 950** | 性能优化目标 | 待确认 | 对标 AMD EPYC 9755，新一代鲲鹏 |
| **Kunpeng 920B** | 兼容（可执行、不 core） | ✅ SVE/SVE2/SVEi8mm/SVEf32mm/SVEf64mm/SVEbf16 | 详见 `lscpu` Flags |
| **Kunpeng 920** | 兼容（可执行、不 core） | ❌ | 鲲鹏社区 FAQ 确认不支持 SVE |

所有 ARM 优化代码需通过运行时 CPU feature 检测（`is_aarch64_feature_detected!`）确保在不支持的平台上正确回退到通用路径，不触发 SIGILL。

## 1.3 目标产线

基于 `volc_operator_sim` 测试库，目标 pipeline 为：

- `pipeline_text_fineweb_full_min`
- `video_scene_split_etl`
- `pipeline_image_full_min`
- `audio_asr_prep_canonical`
- `pipeline_pdf_full_min`
- `pipeline_ad_nuscenes_min`

初步分析表明：所有 pipeline 存在大量 UDF 调用，join/filter/groupby 等关系代数操作占比较低。**UDF 执行效率是核心瓶颈**。

## 1.4 约束

- 性能优化目标平台：Kunpeng 950；Kunpeng 920/920B 仅需保证代码可正确执行（不触发 core dump）
- 优化通过 `cfg(target_arch = "aarch64")` 条件编译 + 运行时 CPU feature 检测（`is_aarch64_feature_detected!`）门控，不支持时回退通用路径
- 所有修改应具备上游合入 Daft mainline 的可行性
- 视频加速依赖鲲鹏 BoostKit 库，为外部依赖；其余优化均为 Daft 内置实现

---

# 2. 功能域总体方案

## 2.1 优化分类

11 个优化点按技术路线归为五大类：

| 类别 | 编号 | 优化点 | 修改层 |
|------|------|--------|--------|
| **A. UDF 跨边界优化** | 1, 2, 4, 5, 8 | 减少跨界损耗、Rust 重写算子、结构体转换、UDF 调度、UDF 链物理融合 | Logical Optimizer + Physical Plan + Execution |
| **B. Hash/CRC 加速** | 6, 11 | CRC32C 行哈希、ARM CRC 通用 hash | `daft-core::kernels::hashing` |
| **C. SVE 向量化** | 7, 9 | UTF-8 length SVE cntp、SVE gather 批量取数 | `daft-functions-utf8` + `daft-core::array::ops::take` |
| **D. Text 快路径** | 10 | 文本字节长度 Offset 快路径 | `daft-functions-utf8::length_bytes` |
| **E. 视频加速** | 3 | 鲲鹏 BoostKit x264/x265 | Python UDF 层（外部依赖） |

## 2.2 Daft 架构与插入点

```
┌─ Python DataFrame API ───────────────────────────────────────────┐
│  df.with_column("out", my_udf(col("x")))                         │
└─────────────────────────────┬────────────────────────────────────┘
                              ▼
┌─ Logical Plan ───────────────────────────────────────────────────┐
│  Project ─── SplitUDFs ─── UDFProject ─── ... ─── UDFProject     │
│    │                         │                                    │
│    │  ← A8 UDF链物理融合     │  ← A1/A2/A4 优化（表达式层）      │
└────┼─────────────────────────┼───────────────────────────────────┘
     ▼                         ▼
┌─ Physical Plan ──────────────────────────────────────────────────┐
│  LocalPhysicalPlan::UDFProject  ← A5 UDF调度优化                  │
│  DistributedActorPoolProject   ← 资源管理                         │
└─────────────────────────────┬────────────────────────────────────┘
                              ▼
┌─ Execution ──────────────────────────────────────────────────────┐
│  UdfOperator / AsyncUdfSink  ← UDF 执行（跨界、结构体）          │
│  hashing.rs                 ← B6/B11 CRC32C hash                 │
│  take.rs                    ← C9 SVE gather                       │
│  length_bytes.rs            ← C7 SVE cntp / D10 offset fastpath   │
│  arithmetic.rs               ← 潜在 SVE 加速点                    │
└──────────────────────────────────────────────────────────────────┘
```

关键模块路径（基于 Daft mainline commit `3f5bdd1`）：

| 模块 | 路径 |
|------|------|
| Hash 内核 | `src/daft-core/src/kernels/hashing.rs` |
| Hash 表达式 | `src/daft-functions/src/hash.rs` |
| Row hash 链 | `src/daft-recordbatch/src/ops/hash.rs` |
| Take/Gather | `src/daft-core/src/array/ops/take.rs` |
| UTF-8 length | `src/daft-functions-utf8/src/length_bytes.rs` |
| UTF-8 char length | `src/daft-functions/src/length.rs` |
| UDF 逻辑算子 | `src/daft-logical-plan/src/ops/udf.rs` |
| SplitUDFs 规则 | `src/daft-logical-plan/src/optimization/rules/split_udfs.rs` |
| 物理翻译 | `src/daft-local-plan/src/translate.rs` |
| UDF 执行算子 | `src/daft-local-execution/src/intermediate_ops/udf.rs` |
| 分布式 UDF | `src/daft-distributed/src/pipeline_node/udf.rs` |
| Actor Pool | `src/daft-distributed/src/pipeline_node/actor_udf.rs` |
| 逻辑优化器 | `src/daft-logical-plan/src/optimization/optimizer.rs` |

## 2.3 领域数据模型

核心实体及其关系：

```
Pipeline
  └── LogicalPlan (DAG of operators)
        ├── Source (文件/对象存储读写)
        ├── Project (列变换，含 UDF 表达式)
        │     └── Expr tree (UDF, Function, Column, Literal)
        ├── Filter
        ├── GroupBy → hash_rows() → CRC32C 加速点
        └── Join → hash_rows() → CRC32C 加速点

UDFProject (逻辑)
  ├── UDFProperties { concurrency, batch_size, num_cpus, memory_bytes... }
  └── expr: Expr (Python UDF / Rust kernel)

MicroPartition (执行期数据单元)
  ├── Columns (Arrow arrays)
  │     ├── PrimitiveArray → take/gather → SVE 加速点
  │     ├── Utf8Array → length/length_bytes → SVE/Offset 加速点
  │     └── BinaryArray → hash → CRC32C 加速点
  └── RecordBatch → hash_rows() → CRC32C 加速点
```

## 2.4 设计原则

1. **门控可回退**：每个 ARM 优化点都需提供非 ARM 的通用 fallback 路径，不破坏跨平台兼容性
2. **渐进式集成**：优先实现收益明确、风险低的优化（CRC32C hash > Offset 快路径 > SVE 向量化 > UDF 融合）
3. **可上游合入**：代码风格与模块结构遵循 Daft 现有规范，每个优化点作为独立 PR 提交
4. **实测驱动**：每个优化点完成后需在目标 pipeline 上做 benchmark 对比

---

# 3. 功能域规格设计

## 3.1 平台特性门控规格

### 3.1.1 CPU Feature 检测与降级

所有 ARM 特定优化路径必须通过编译期 + 运行时双重门控，在不支持的平台上自动回退通用路径，**不得触发 SIGILL**。

| 特性 | 编译期门控 | 运行时门控 | 降级路径 |
|------|-----------|-----------|---------|
| CRC32C | `cfg(target_arch = "aarch64")` | `is_aarch64_feature_detected!("crc")` | xxHash3_64 (NEON) |
| SVE | `cfg(target_arch = "aarch64")` | `is_aarch64_feature_detected!("sve")` | NEON (128-bit) |
| SVE2 | `cfg(target_arch = "aarch64")` | `is_aarch64_feature_detected!("sve2")` | NEON (128-bit) |
| NEON | `cfg(target_arch = "aarch64")` | N/A（AArch64 强制支持） | 标量循环 |

SVE 指令使用 `core::arch::asm!` 内联汇编实现，不依赖 `std::simd` 或 `stdarch` SVE intrinsics（避免 nightly 依赖）。

### 3.1.2 平台兼容矩阵

| 平台 | 定位 | CRC32C | SVE | SVE2 | NEON |
|------|------|--------|-----|------|------|
| **Kunpeng 950** | 性能目标 | 待确认 | 待确认 | 待确认 | ✅ |
| **Kunpeng 920B** | 兼容（可执行） | ✅ | ✅（256-bit） | ✅ | ✅ |
| **Kunpeng 920** | 兼容（可执行） | ✅ | ❌ | ❌ | ✅ |
| x86_64 | 不受影响 | ❌ | ❌ | ❌ | ✅ |

## 3.2 UDF 执行规格

### 3.2.1 Mapper 链融合条件

连续多个 mapper UDF 调用可融合为单次 `df.with_column()` 调用，当且仅当满足：

- 中间无 Filter、Join、GroupBy、Deduplicator 等非 Project 算子
- 所有 mappers 为纯字符串变换（`str → str`），无外部 I/O 依赖
- 输出列仅被下游 UDF 消费或作为最终输出
- 官方 Data-Juicer 算子（`use_official_text_ops=true`）不可参与融合（作为边界）

### 3.2.2 UDF 并发度自适应规格

UDF 并发度采用 TCP 试探回退机制自适应调优：

- 初始并发度 = 当前 worker 核心数
- 递增期：每次提升并发度后测量吞吐量，若提升则继续递增（步长待定）
- 回退期：若吞吐量下降或持平，回退到上一个最优值
- 稳定期：连续 N 次确认无增益后锁定并发度

适用范围：`@daft.func` / `@daft.udf` mapper 和 filter，不含 sink、deduplicator、join 等全局 barrier 算子。

### 3.2.3 Rust 重写算子清单

以下 12 个 Python UDF 算子确认为 Rust 重写候选（详见 `daft-kunpeng-udf-inventory.md`）：

**P0 文本链（11 个，可融合为 1 个 Rust kernel）**：
`clean_html_mapper`、`clean_links_mapper`、`clean_email_mapper`、`clean_copyright_mapper`、`fix_unicode_mapper`、`punctuation_normalization_mapper`、`whitespace_normalization_mapper`、`text_length_filter`、`alphanumeric_filter`、`language_id_score_filter`、`text_chunk_mapper`

**P4 图像（1 个）**：`image_blur_mapper`

### 3.2.4 Arrow 零拷贝传输规格

UDF 输入输出在 Python ↔ Rust 间使用 Arrow C Data Interface 传递，约束：

- 零拷贝仅适用于 batch mode UDF（`@daft.udf`）
- 输入和输出的 Arrow 数据类型必须完全匹配 Daft 内部列类型，否则降级为 PyArrow 序列化路径
- Ray 集群通过统一 wheel 分发保证各 worker pyarrow 版本一致

## 3.3 Hash 算法规格

### 3.3.1 算法选择规则

| 平台 | 默认算法 | 说明 |
|------|---------|------|
| aarch64 + CRC32C 可用 | CRC32C | 硬件加速，需验证分布均匀性 |
| aarch64 + CRC32C 不可用 | xxHash3_64（NEON） | Daft 已支持 NEON 加速路径 |
| x86_64 | xxHash3_64（AVX2） | 现有路径 |
| 安全敏感场景 | SHA1 / MurmurHash3 | HashDoS 防护 |

### 3.3.2 CRC32C 准入条件

CRC32C 作为默认 hash 仅在同时满足以下条件时启用：

1. `is_aarch64_feature_detected!("crc")` 返回 true
2. 环境变量 `DAFT_ARM_ENABLE_CRC32C_ROW_HASH=1` 显式启用
3. 数据类型为 integer（i8–u64）、float（f32/f64 reinterpret）、utf8、binary、boolean 之一

不满足时静默回退 xxHash3_64。

## 3.4 文本处理规格

### 3.4.1 UTF-8 字节长度计算

`length_bytes` 函数保证 O(rows) 时间复杂度，通过 Arrow offset buffer 差计算，不访问字符串内容。Daft 仅使用 `Utf8Array`（Arrow i32 offset），无 `LargeUtf8Array` 变体。

### 3.4.2 UTF-8 字符长度计算

`col.length()`（Unicode 字符数）在 SVE 可用时使用 256-bit SVE `cntp` 指令加速（`char_count = byte_count − 续接字节数`），SVE 不可用时降级为 NEON 128-bit 路径。

## 3.5 视频处理规格

### 3.5.1 UDF 粒度契约

视频 UDF 以整段文件为处理单元（`input_path: str`），非逐帧。UDF 接收视频文件路径，完成处理后返回结果路径或数据。帧级操作由 Daft 原生 `read_video_frames()` 负责。

### 3.5.2 BoostKit x265 集成契约

视频转码使用鲲鹏 BoostKit x265 加速库，通过 ffmpeg 命令行调用（`-c:v libx265`）。前提：目标节点已安装 BoostKit x265 并链接 ffmpeg。BoostKit 为自研产品，可随项目发布。

## 3.6 Gather/Take 规格

### 3.6.1 向量化加载

在 Daft 的 `take` / `gather` 路径中，对 primitive 数组（i32、i64、f32、f64）在 SVE 可用时使用 SVE2 gather-load 指令批量取数。SVE 宽度由硬件决定，tail 部分用 WHILELT 谓词掩码处理。SVE 不可用时降级为 Arrow `compute::take` 标量路径。

---

# 附录 A：不确定项清单

| # | 状态 | 问题 | 解决方式 |
|---|------|------|---------|
| U1 | ✅ | Kunpeng 920B SVE 支持 | `lscpu` 验证：Flags 含 `sve svei8mm svef32mm svef64mm svebf16` |
| U1.1 | ⏳ | Kunpeng 950 SVE 向量宽度和微架构参数 | 获取 950 硬件规格文档 |
| U2 | ✅ | 12 个 Rust 重写候选算子 | 分析 volc_operator_sim 6 条 pipeline，见 `daft-kunpeng-udf-inventory.md` |
| U3 | ⏸️ | CRC32C 作为 groupby hash 的分布均匀性 | 待 benchmark（实现细节，非规格层面） |
| U4 | ✅ | BoostKit x265 许可证 | 自研产品，可随项目发布 |
| U5 | ✅ | UDF 链融合条件 | 连续 UDF、中间无其他算子、输出仅下游消费 |
| U6 | ✅ | Arrow C Data Interface 版本兼容 | Ray 统一 wheel 分发保证版本一致 |
| U7 | ✅ | SVE 实现方式 | `core::arch::asm!` 内联汇编，不依赖 nightly |
| U8 | ✅ | Daft 字符串类型 | Daft 仅使用 Utf8（i32 offset），无 LargeUtf8 |
| U9 | ✅ | 视频 UDF 粒度 | 整段文件（`input_path: str`），非逐帧 |
| U10 | ✅ | UDF 并发度调优 | TCP 试探回退自适应机制 |

# 附录 B：优先级建议

| 优先级 | 类别 | 依据 |
|--------|------|------|
| P0 | B: Hash/CRC 加速 | 改动集中，hash 密集型产线（dedup/groupby/join）收益大 |
| P0 | D: Text Offset 快路径 | 改动最小（单函数）、零风险、FineWeb/PDF 文本产线直接受益 |
| P1 | A: P0 文本链 Rust 重写 | 11 个算子融合为 1 个 kernel，消除 Python 边界，收益最高 |
| P1 | A: UDF 链融合 | 减少调度/物化边界，对长 UDF 链效果显著 |
| P2 | C: SVE 向量化（cntp/gather） | 依赖 950 硬件确认，920B 已可用 |
| P2 | A: UDF 自适应并发 | TCP 试探回退，需 runtime 基础设施 |
| P2 | A: Arrow 零拷贝传输 | 需 batch mode UDF 支持 |
| P3 | E: BoostKit 视频加速 | 依赖外部库安装 + 目标节点配置 |
