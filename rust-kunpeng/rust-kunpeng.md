# 针对标准库性能测试优化性能表现

目标：建立鲲鹏上的 Rust 标准库性能基线，识别 `std` / `alloc` / `core` 中在 AArch64 上表现不佳的热点，并将修复上游到 Rust / LLVM。

实现目标：

- 在鲲鹏服务器上运行 `rustc-perf`、标准库 micro-benchmark、同步原语 benchmark。
- 验证 `aarch64-unknown-linux-gnu` 默认 `+outline-atomics` 是否在鲲鹏上正确走 LSE。
- 检查 `-C target-cpu=native` 是否能正确识别鲲鹏 / TaiShan 微架构。
- 若 LLVM 缺少鲲鹏 CPU 识别或调度模型，提交 CPU target / scheduler model。
- 针对 `Arc`、`Mutex`、`HashMap`、字符串处理、memcpy/memcmp 等热点建立回归测试。

# portalable SIMD 仓库（highway的rust 版本）

目标：建设一个类似 Google Highway 的 Rust portable SIMD 抽象层，屏蔽 x86 AVX/AVX-512、AArch64 NEON/SVE/SVE2、WASM SIMD 等差异。

**2026 年环境变化**：
- Rust nightly 已有 SVE/SVE2 intrinsics（`stdarch` PR #2071，2026年4月合入，~33万行生成代码）
- `std::simd` 在 ARM 上表现分化严重：连续数值 4-9x 加速，但交错数据场景可退化到 0.13x（见 Finding #12）
- SVE 是华为鲲鹏区别于 Graviton（Neoverse N1）的硬件特色，应作为差异化竞争力重点投入

实现目标：

- 设计统一 trait/API：vector load/store、mask、compare、shuffle、dot product、popcount、crc 等。
- 优先补齐 NEON 后端，并在鲲鹏 SVE 硬件可用时构建 SVE/SVE2 后端。
- 对 Rust 生态常见 x86 SIMD 缺口做 ARM 等价实现，例如 `pmovmskb`。
- **关键设计决策**：不为 `std::simd` 可以完美覆盖的操作再写手写 intrinsics（避免冗余）；但为 `std::simd` 无法表达的 ARM 特有指令（`vld3`、`vhadd`、`vmovl`、`vqmovn`）保留手写路径。
- 在 `lance-linalg`、`simd-json`、`simdutf`、`arrow`、`polars` 等场景中验证收益。
- 建立跨架构 benchmark：scalar vs NEON vs SVE2 vs AVX2/AVX-512，重点覆盖 `std::simd` 的弱项场景（交错数据、类型转换）。

# 灵衢总线的 Rust SDK 封装

目标：为鲲鹏多路服务器提供 Rust 侧 NUMA / 跨 socket / 灵衢互连能力封装。

实现目标：

- 暴露 NUMA 拓扑：socket、NUMA node、核心分布、跨 socket 链路关系。
- 封装线程绑核、内存亲和、NUMA 本地分配等能力。
- 为 Rayon / Tokio / 数据工程任务提供 NUMA-aware 调度建议或适配层。
- 若硬件/内核暴露灵衢链路计数器，提供只读监控 API。
- 面向数据库、向量检索、流式 ETL 验证跨 socket 数据访问收益。

# 鲲鹏 专用功能 Rust  SDK 直接控制 L3 缓存能力

目标：封装鲲鹏平台可用的 L3 cache / 预取 等能力，服务数据库和数据工程热点路径。

实现目标：

需要和 Kunpeng 硬件团队对齐功能列表

# 鲲鹏 Rust 审计工具 	

脚本工具，无 LLM，判断一个 Rust 项目是否可以迁移到 Kunpeng 架构，覆盖功能完整性与性能风险。

可能问题：

1. （直接或者引用的库间接）使用 `std::arch` 等绑定 CPU 的实现。
2. 通过 FFI 封装了 C/C++ native 实现，但是没有 ARM 版本 / Kunpeng 优化版本。
3. 硬编码汇编。
4. 不兼容 ARM 的预编译 / 处理脚本。

扩展检测项：

- `is_x86_feature_detected!`、`target_feature = "avx2"`、`target_arch = "x86_64"` 等 x86-only 路径。
- `build.rs` 中硬编码 `gcc`, `clang`, `-mavx`, `-msse`, `-march=native`。
- 依赖树中的 `*-sys` crate 是否需要 native 库或预编译二进制。
- wheel / npm / docker 镜像是否只发布 x86_64 artifact。
- 是否已有 aarch64 CI、aarch64 release、aarch64 benchmark。

实现目标：

- 使用 `cargo_metadata` 解析依赖树。
- 使用文本扫描 + AST 扫描识别 arch-specific 代码。
- 输出 JSON / Markdown / HTML 报告。
- 核心工具不依赖 LLM；可选引入 LLM 生成修复建议。

解决方案建议：可以引入 LLM，给出解决方案。


## backlog

- Rust 热点路径向量化优化：补齐对 `pmovmskb` 的支持，通过手写 SIMD 指令优化热点函数接口性能。
- Rust CRC32 鲲鹏硬加速：多模态数据校验使能鲲鹏 CRC32 硬件加速。
- Rust 访存优化：读写数据局部化、内存预取等手段减少随机内存读写。
- Rust 前端编译 & LLVM 优化：面向数据工程场景，优化 ARM 低效指令；**新增**：将 openEuler LLVM 的 tsv110 调度模型上游化到 LLVM mainline。
- PyO3 性能优化。
- **新增**：SVE/SVE2 鲲鹏 nightly 验证——在鲲鹏硬件上运行 stdarch SVE 测试套件，验证生成代码正确性。
- **新增**：`rustc` openEuler LLVM toolchain 构建——发布鲲鹏优化的 Rust 编译器（基于 openEuler LLVM 而非 upstream LLVM）。


# Findings

## 1. CPU 厂商视角的 Rust 生态投入方向

Rust 在 ARM 服务器上的差距不主要来自语言本身，而来自硬件能力没有充分传递到编译器、标准库、构建系统和 crate 生态。

高价值投入方向：

| 优先级 | 方向 | 价值 |
|---|---|---|
| P0 | LLVM CPU 识别与调度模型（含 openEuler 优化上游化） | 影响所有 LLVM 语言，包括 Rust / C++ / Swift / Julia |
| P0 | CPU feature 定义正确性 | 避免 `target-cpu=native` 生成非法指令 |
| P0 | 构建指向 openEuler LLVM 的 Rust toolchain | 在上游化完成前补齐性能缺口 |
| P1 | ARM CI / benchmark runner（含 SVE nightly 测试） | 让上游项目长期发现 ARM 回归 |
| P1 | 关键 crate 优化 | 影响 LanceDB、Polars、DataFusion、Arrow 等下游 |
| P2 | 性能库 Rust 绑定（含 KML 官方绑定 License 优化） | 将硬件库能力导入 Rust 生态 |
| P2 | 性能分析工具 Rust 支持 | 类似 Intel VTune + `ittapi` 的开发者体验 |

## 2. Intel 在 Rust 方向的参考

Intel 没有维护单独的 Rust 编译器分支，而是通过 LLVM 上游化间接优化 Rust。

可参考做法：

- 每代 CPU 提交 LLVM x86 scheduling model，例如 Sapphire Rapids、Lunar Lake。
- 提供性能分析工具 VTune，并通过 `ittapi` crate 支持 Rust 程序标记任务、JIT 代码和采样区间。
- oneMKL / oneDNN 等性能库通过社区 Rust binding 进入生态，例如 `onemkl`。
- 对 Rust GPU/offload 方向，主要通过 LLVM / oneAPI / SYCL / Level Zero 路径影响。

对鲲鹏的启示：

- 不建议 fork Rust 编译器，应优先 upstream LLVM / rustc。
- 重点不是“做一个 Rust 编译器”，而是提供 CPU target、调度模型、PMU 文档、benchmark runner 和高质量库绑定。

## 3. Rust LSE 支持结论

Rust 已经支持 ARM LSE 原子指令，并且 Linux AArch64 目标默认启用 `+outline-atomics`。

覆盖范围：

- `std::sync::atomic::*`
- `Arc<T>` 引用计数
- `Mutex` / `RwLock` 内部 CAS / futex 路径
- Tokio / crossbeam 等基于 atomic 的同步结构

模式：

| 模式 | 特点 |
|---|---|
| 默认 `outline-atomics` | 运行时检测 LSE，兼容 ARMv8.0 与 ARMv8.1+ |
| `-C target-feature=+lse` | 静态生成 LSE 指令，无运行时分发开销 |
| 禁用 outline atomics | 回退到 `ldaxr/stlxr` 循环 |

验证命令：

```bash
rustc --print cfg --target aarch64-unknown-linux-gnu | grep outline
lscpu | grep Features | grep atomics
```

## 4. LSE 指令功能概览

LSE 包含单指令原子读改写能力：

| 指令族 | 功能 | Rust 对应 |
|---|---|---|
| `CAS` / `CASP` | compare-and-swap / pair CAS | `compare_exchange` |
| `SWP` | 原子交换 | `swap` |
| `LDADD` | 原子加 | `fetch_add` / `fetch_sub` |
| `LDCLR` | 原子清 bit | `fetch_and` 变体 |
| `LDSET` | 原子置 bit | `fetch_or` |
| `LDEOR` | 原子 xor | `fetch_xor` |
| `LDSMAX/LDSMIN` | signed max/min | 部分场景 |
| `LDUMAX/LDUMIN` | unsigned max/min | 部分场景 |

收益来自避免 `ldaxr/stlxr` 在高竞争下反复失败。

## 5. LanceDB 架构发现

LanceDB 是嵌入式数据库，更接近 SQLite / DuckDB，而不是 MySQL 的 C/S 架构。

分层：

```text
Python API / integrations
  ↓ PyO3
Rust LanceDB SDK
  ↓
DataFusion SQL / query engine
  ↓
Lance storage engine
  ↓
Arrow columnar memory / object store
```

职责：

- Rust：存储格式、向量索引、查询执行、DataFusion、Arrow、I/O、对象存储。
- Python：用户 API、Pydantic、LangChain/LlamaIndex、embedding/reranker 生态集成。
- PyO3：桥接层，负责类型转换、async runtime 桥接、Arrow/PyArrow 互通。

开源协议：Apache 2.0。

## 6. PyO3 工作原理与性能损失点

PyO3 将 Rust 编译为 CPython extension module。调用路径：

```text
Python call
  → CPython PyObject / PyCFunction
  → PyO3 trampoline
  → 参数 extract: PyObject* → Rust type
  → Rust function
  → 返回值 IntoPy: Rust type → PyObject*
```

主要性能损失：

| 场景 | 原因 |
|---|---|
| Python list → Rust Vec | 逐元素 `extract`，每个元素一次 Python C API 调用 |
| Rust Vec → Python list | 每个元素分配 Python object |
| `Vec<u8>` / `String` 转换 | 可能发生 memcpy / UTF-8 转换 |
| 未释放 GIL | Rust 长计算仍阻塞其他 Python 线程 |
| 异常路径 | `PyErr` 与 traceback 分配 |
| async 桥接 | Tokio future ↔ Python awaitable 转换 |

优化原则：

- 避免逐元素跨边界。
- 大数据用 Arrow / buffer protocol / numpy 零拷贝。
- 长计算用 `Python::allow_threads` 释放 GIL。
- 批量传递，减少 Python↔Rust 来回调用次数。

## 7. PyO3 在鲲鹏上的优化可行性

PyO3 本身不是典型 SIMD-heavy 项目，直接写 ARM intrinsics 的空间有限。更有价值的是验证底层系统路径：

| 优先级 | 方向 | 预期收益 |
|---|---|---|
| P0 | 确认 CPython / Rust 都启用 LSE 原子路径 | `Py_INCREF` / `Py_DECREF` / 临界区更快 |
| P1 | 确认大块数据转换走 glibc NEON memcpy | bytes / string / buffer 传输更快 |
| P1 | 在 LanceDB / Polars 等项目推广 Arrow 零拷贝 | 避免 PyO3 逐元素转换 |
| P2 | 增加 ARM CI benchmark | 持续发现 PyO3 ARM 回归 |

## 8. PyO3 Benchmark 发现

PyO3 仓库自带 benchmark：`pyo3-benches/benches/`，使用 Criterion / CodSpeed。

关键 benchmark：

| 文件 | 衡量内容 | 鲲鹏敏感点 |
|---|---|---|
| `bench_py.rs` | `Py<T>` clone/drop、引用计数 | LSE 原子 |
| `bench_extract.rs` | Python → Rust 类型转换 | memcpy / Python C API |
| `bench_intopyobject.rs` | Rust → Python 类型转换 | Python object 分配 |
| `bench_call.rs` | Python 调 Rust 函数开销 | FFI trampoline |
| `bench_critical_sections.rs` | GIL / critical section | 原子 CAS / free-threaded Python |
| `bench_dict/list/set/tuple.rs` | Python 容器操作 | 对象分配、哈希 |

建议在鲲鹏上运行：

```bash
git clone https://github.com/PyO3/pyo3
cd pyo3/pyo3-benches
cargo bench --bench bench_py
cargo bench --bench bench_extract
cargo bench --bench bench_critical_sections

# 对比 LSE / LL-SC
RUSTFLAGS="-C target-feature=-outline-atomics" cargo bench --bench bench_py
```

## 9. 近期优先行动建议

1. 先做 `kunpeng-audit`，快速扩大生态影响面。
2. 同时搭建 PyO3 / LanceDB / Polars / Arrow 在鲲鹏上的 benchmark baseline。
3. 验证 LLVM 是否已有鲲鹏正确 CPU target；若缺失，优先补。
4. 对 `crc32fast`、`simdutf`、`simd-json`、`lance-linalg` 找小而明确的 ARM 优化 PR。
5. 将结果沉淀为公开文档：类似 AWS Graviton Getting Started 的 Rust 版。

## 10. openEuler LLVM 鲲鹏专用优化选项（关键缺口）

openEuler 维护了一个 LLVM 分支，包含针对鲲鹏（tsv110）的专用后端优化。这些优化**不在 upstream LLVM** 中，而 Rust 使用的是 upstream LLVM —— 这意味着 Rust 在鲲鹏上**默认无法获得这些优化**。

已知的 openEuler LLVM 鲲鹏专用选项：

| `-mllvm` 选项 | 功能 | 默认 | 影响 |
|---|---|---|---|
| `-aarch64-ldp-stp-noq=true` | 禁止生成 `stp/ldp q1, q2` 指令（tsv110 上性能不佳） | 启用 | 特定指令选择 |
| `-enable-aggressive-inline=true` | 忽略 `__attribute__((noinline))`，强制激进内联 | 关闭 | 代码大小/性能权衡 |
| `-no-sink-prtadd-post-load=true` | 防止 MachineSink pass 将 GEP 下沉到循环末尾 | 关闭 | 循环内 load 延迟 |
| `-aarch64-endianness-opts=true` | 大小端字节序转换优化（MySQL 等 big-endian 场景） | 关闭 | 数据库场景 |
| ICP 阈值调整 | 间接调用提升（indirect call promotion）优化 | — | 大型软件调用链 |
| 自动预取增强 | 识别多层间接嵌套访存，自动插入预取指令 | — | 数据 cache miss |

这些选项需要 `-mcpu=tsv110` 才能激活。当前 Rust 通过 `-C target-cpu=tsv110` 可以指定 CPU，但**如果 upstream LLVM 缺少 tsv110 的完整调度模型和 target feature 定义，这些优化根本不会触发**。

**对鲲鹏的战略含义**：
- 短期：建议在鲲鹏上使用 openEuler LLVM 而非 upstream LLVM 编译 Rust 程序（需自行构建 `rustc` 指向 openEuler LLVM）
- 中长期：将 openEuler 的鲲鹏优化上游到 LLVM mainline，使所有 LLVM 语言（Rust/C++/Swift）默认受益

参考：[openEuler LLVM Optimization Options](https://docs.openeuler.org/en/docs/24.03_LTS_SP4/server/compiler/llvm/llvm_for_openeuler_option_list.html)

## 11. SVE/SVE2 Rust 支持 —— 2026 年重大进展

Rust 的 SVE 支持自文档初稿以来取得了实质性突破：

**已合入（2026 Q1-Q2）**：
- **SVE intrinsics 已合入 `stdarch`**（[PR #2071](https://github.com/rust-lang/stdarch/pull/2071)，2026年4月15日合并）：约 33 万行生成代码，覆盖 SVE 和 SVE2 全部 intrinsics
- SVE 可扩展向量类型定义：`svuint8_t`、`svint16_t`、`svfloat32_t` 等
- `std::intrinsics::simd::scalable` 模块可用（nightly）
- `Sized` trait 层级 Part I 已合入（[rust#137944](https://github.com/rust-lang/rust/issues/137944)），`#[rustc_scalable_vector(N)]` 属性可用
- SVE2 BitPerm intrinsics：`svbext`、`svbgrp`、`svbdep` 等（[PR #2069](https://github.com/rust-lang/stdarch/pull/2069)）

**进行中**：
- 可扩展向量跟踪 issue [#145052](https://github.com/rust-lang/rust/issues/145052)（David Wood 主导）
- RFC #3838（Scalable Vectors）尚未正式接受，但实验性实现已合并
- `const Sized`（Part II of RFC #3729）因依赖 const traits 被推迟

**对鲲鹏的意义**：
- 华为（Huawei）被明确列为推动 SVE Rust 支持的关键利益方（与 Google、Microsoft 并列）
- SVE intrinsics 现已在 nightly 上可用，需要 `#![feature(stdarch_aarch64_sve)]` + `target_feature = "sve,sve2"`
- SVE 是鲲鹏的硬件特色（鲲鹏 920 支持 SVE），这是鲲鹏在 Rust 生态中的**差异化竞争力**
- SVE 后续是 SME（Scalable Matrix Extensions），华为可以提前介入设计

**关键限制**：
- SVE 仍在 nightly，稳定化时间线不明确
- `intrinsic-test` 工具尚不支持 SVE 测试（stdarch 维护者已知）
- 静态 `+sve` 编译 vs 运行时 `is_aarch64_feature_detected!("sve")` 的分发策略待定

## 12. `std::simd` 在 ARM 上的真实 Benchmark —— 不是万能药

2026 年 2 月发布的 Apple M4 实测数据揭示了 `std::simd` 在 ARM 上的真实表现（[Erio-Harrison/simd_benchmark](https://github.com/Erio-Harrison/simd_benchmark)）：

| 场景 | scalar | std::simd | NEON | std::simd vs scalar |
|---|---|---|---|---|
| RGB→灰度 | 6.16ms | 18.51ms | 1.45ms | **0.33x（慢 3 倍）** |
| 音量调整 | 1.39ms | 3.42ms | 0.82ms | **0.40x** |
| 音频混合 | 0.63ms | 4.84ms | 0.53ms | **0.13x（慢 7.7 倍）** |
| 点积 f32x8 | 51.20ms | 10.99ms | 20.14ms | **4.66x（快）** |
| 矩阵-向量乘 | 4.48ms | 0.69ms | 1.35ms | **6.53x** |
| 找字节 | 24.07ms | 2.61ms | 2.68ms | **9.23x** |

**结论**：
- `std::simd` 在连续 f32/i32 数组上表现优异（甚至优于手写 NEON，因为编译器自动选择 256-bit 宽度）
- `std::simd` 在交错数据（RGB、音频）、需要类型转换、需要特殊指令（`vhadd`、`vld3`）的场景下**严重退化**，因为可移植抽象无法表达 ARM 特有指令
- 对鲲鹏的 portable SIMD 仓库设计的启示：**不能仅依赖 `std::simd`**。必须保留 NEON 手写路径用于交错数据和类型转换场景，`std::simd` 仅用于连续数值计算

## 13. `rstsr-kml-ffi` —— 社区已有的 KML Rust 绑定

[crates.io 上的 `rstsr-kml-ffi`](https://crates.io/crates/rstsr-kml-ffi)（v0.2.1，2026年2月更新，3120 下载量）提供了 KML（Kunpeng Math Library）v24.0.0 的 Rust FFI 绑定。

特点：
- 覆盖 BLAS、KBLAS（CBLAS）、LAPACK
- 支持静态链接和动态加载（`dynamic_loading` feature）
- 自动从 `LD_LIBRARY_PATH` 查找 KML 库
- 非华为官方项目（作者声明）

**关键限制（BoostKit License）**：
- 禁止未经华为书面同意的商业分发
- 禁止未经华为书面同意的性能 benchmark 发布
- 这意味着 `rstsr-kml-ffi` **不能直接用于公开 benchmark 或商业产品**，限制了生态推广

**对鲲鹏的启示**：
- KML 的 Rust 绑定已经存在但生态影响力有限——部分原因是 License 限制
- 若希望 KML 在 Rust 数据科学生态（Polars/DataFusion/Arrow）中广泛使用，**建议发布 Apache 2.0/MIT 授权的官方绑定或放宽 benchmark 条款**
- 作为对照，Intel oneMKL 也有社区绑定（`rstsr-mkl-ffi`），Intel Simplified Software License 相对开放

## 14. 鲲鹏 920 / TaiShan v110 微架构深度分析（ChipsAndCheese, 2025）

[ChipsAndCheese 的分析](https://chipsandcheese.com/p/huaweis-kunpeng-920-and-taishan-v110)揭示了鲲鹏 920 的强项与弱点，对 LLVM 调度模型设计有直接指导：

**TaiShan v110 核心参数**：
| 参数 | 值 |
|---|---|
| 发射宽度 | 4-wide OOO |
| 整数端口 | 3 ALU + 1 多周期（乘除） |
| FP/向量端口 | 双流水线 FPU，128-bit NEON |
| 内存 | 2 mem ops/cycle |
| ROB | ~128 条目（与 Goldmont Plus 相当） |
| L1D/L1I | 64KB 4-way / 64KB 2-way |
| L2 | 512KB 私有，16-way |
| L3 | 48MB 共享（slice-based），tag 在 CPU cluster 侧 |

**关键瓶颈**：
1. **L3 设计独特但性能不一致**：L3 支持 Shared / Private / Partition 三种模式动态切换，但当单核需要大部分 L3 容量或跨 cluster 共享数据时性能显著下降
2. **SPEC CPU2017 int 落后 Neoverse N1 52.2%**——在同等 7nm 工艺下，Arm 的公版设计利用效率更高
3. **FP/向量寄存器文件偏小**：AArch64 有 32 个 FP/向量寄存器（vs x86-64 的 16 个），但 TaiShan v110 的重命名寄存器池偏小，FP/向量密集型负载瓶颈突出

**对 LLVM 调度模型的影响**：
- 向量指令选择应倾向于 128-bit NEON，避免发射宽度浪费
- `stp/ldp q` 指令在 tsv110 上性能不佳（openEuler LLVM 默认禁用），应在调度模型中降低其权重
- L3 Private 模式下局部性更好，NUMA-aware 代码生成应考虑 L3 partition 策略
- FP/向量压力大时应优先 spill 标量寄存器

## 15. LLVM 调度模型上游模板 —— C1-Ultra 案例

2026 年 2 月提交的 [C1-Ultra 调度模型 PR](https://github.com/llvm/llvm-project/pull/182251)（LLVM PR #182251）为鲲鹏 tsv110 调度模型提供了**直接可参照的上游模板**：

- 基于 Neoverse V3 调度模型改写
- 定义了 17 种流水线资源类型、各指令的延迟和端口使用
- 包含全面的 `llvm-mca` 测试覆盖（NEON、SVE、MTE、BF16 等）
- 引用 ARM Software Optimization Guide 作为数据来源

**对应策略**：
- 鲲鹏应将 tsv110 调度模型以上述 PR 为模板提交到 upstream LLVM
- 需要准备的数据：指令延迟表、端口使用表、微架构资源约束
- 华为已公开的 Programming Tuning Guide 和 Kunpeng 社区文档可作为信息来源
- 2025 年 LLVM Dev Meeting 专门讨论了 "Scheduling Model in LLVM: Past, Present, and Future"——可关注社区动态

**注意**：openEuler LLVM 已有 tsv110 后端代码，但从未被上游化到 LLVM mainline。上游化的第一步就是提交调度模型。

## 16. Rust AArch64 向量化诊断工具链

当 Rust 代码在 AArch64 上未能向量化时，可采用以下诊断流程（来源：[When Rust Won't Vectorize](https://medium.com/@trivajay259/when-rust-wont-vectorize-how-to-see-why-prove-whose-fault-it-is-rustc-vs-llvm-and-fix-it-x86-98e6831f9be2)）：

```bash
# 1. 启用 LLVM 优化 remark
RUSTFLAGS="-C remark=all -C target-cpu=native" cargo build --release 2>&1 | grep "not vectorized\|vectorized"

# 2. 查看汇编确认
cargo asm --rust <crate>::<function>

# 3. 用 llvm-mca 分析内核循环的调度效率
# （需先提取汇编循环体）
```

AArch64 常见向量化障碍：
- **Gather/scatter**：NEON 不支持通用 gather，LLVM 会放弃向量化
- **Store-load aliasing**：`&mut [u64]` 是 noalias 但 `&[u8]` 不是，LLVM 保守假设别名
- **交错数据**：`vld3` 等交错加载指令在 LLVM IR 层面无法表达
- **类型转换**：`vmovl`（widen）、`vqmovn`（narrow）在可移植 IR 中需要多条指令，成本模型判定不利

**对审计工具的启示**：`kunpeng-audit` 可加入 "检测可能无法向量化的热点循环模式" 作为增强检测项。

## 17. 更新的近期优先行动建议

基于上述新发现，调整优先级：

1. **P0**：将 openEuler LLVM 的 tsv110 调度模型和优化选项上游化到 LLVM mainline（以 C1-Ultra PR 为模板）——这是一次性投入，影响所有 LLVM 语言
2. **P0**：在鲲鹏上构建指向 openEuler LLVM 的 Rust toolchain，补齐上游化前的能力缺口
3. **P0**：在鲲鹏 CI 上启用 SVE nightly intrinsics 测试，验证 stdarch 合入的 SVE 代码在真实硬件上正确运行
4. **P1**：基于 `std::simd` benchmark 数据，重新评估 portable SIMD 仓库的设计——明确 `std::simd` 的适用边界
5. **P1**：评估 `rstsr-kml-ffi` 是否可替代或补充自建 KML 绑定；若 License 是瓶颈，推动官方发布更宽松授权的绑定
6. **P2**：在审计工具中加入 AArch64 向量化障碍检测（gather/store-load alias/x86 feature 误用）
7. **P2**：发布鲲鹏 SVE + Rust 的公开技术博客或 demo，建立华为在 Rust/SVE 社区的可见度
