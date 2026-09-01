# Rust 生态 Kunpeng 亲和远期规划 - 大纲

## Daft & Lance

当前进度: 数据工程二期开发

### 背景 / 应用情况 / 商业价值

- Daft 是面向 AI / 多模态场景的高性能数据引擎，核心以 Rust 实现（约 46% Rust + 36% Python），
  提供 Python DataFrame / SQL 双接口，单机（Native）与分布式（Ray）模式自由切换。
- 由 Eventual-Inc 开发开源；字节以使用方为主，开源贡献在 Lance（27+ 特性），Daft 核心贡献少。
- 迭代活跃：~2-4 天/版本（2026 年 5-8 月），5.6k stars / 170 贡献者。
- 字节跳动火山引擎 LAS（Lake for AI Service）已采用 ；
- Lance：AI 原生列式湖存储格式（多模态列存、随机访问、版本管理）；与 Daft 互补——湖计算（Daft）+ 湖存储（Lance），经 Arrow 类型接口对接，以 row ID 替代 URL 关联多模态数据。
- Daft 可视为 Spark / Hive 工具的同生态位替代, Daft 适合多模态数据与 CPU/GPU 异构调度场景。
- 商业价值：字节 LAS 已生产使用；阿里云有集成（EMR Serverless Daft：100+ 多模态算子，PolarDB Lakebase：Daft on Ray）。

### 应用架构 / Rust 位置

- 架构：Python 接口 + Rust 内核（PyO3 绑定，Apache Arrow 内存格式）——逻辑计划/优化器/物理计划/执行引擎均在 Rust。
- Python 接口：Python 包（PyO3 绑定）——DataFrame / SQL 双入口（惰性执行）；调用外部数据源、接入 Ray。
- logical-plan：声明式算子树（Source/Project/Filter/GroupBy/Join），UDF 包装为 UDFProject 节点。
- optimization：执行优化 + 表达式代数规则优化（谓词/投影/limit 下推、表达式简化、UDF 拆分）+ 代价优化（join 重排）。
- local-plan：逻辑计划翻译为可执行物理计划（Pipeline 图）。
- runner：单机 （native 模式，Tokio 多线程流式）；分布式（Ray 调度 + Flight Shuffle）。
- UDF：Python UDF（batch_size / concurrency）原生 python 代码， 提供自定义逻辑，调用非预置功能桥梁。
- 支持的数据源：`daft-scan`（格式扫描）、`daft-io`（S3/GCS/HTTP IO）、`daft-catalog`（Iceberg/Delta/Hudi）。

### Kunpeng 亲和优化点

- ARM SVE / CRC32C 硬件指令加速：
  - hash 计算：CRC32C 指令加速 groupby/join/dedup 行 hash（目标 2x+ vs xxHash）；
  - 批量 filter 后重排：SVE gather-load 批量取数（目标 2x+ vs 标量）；
  - UTF-8 字符长度：SVE cntp 向量化（目标 3x+ vs 标量）+ length_bytes offset 差分快路径。
- UDF 执行效率：Arrow C Data Interface 零拷贝跨界、相邻 UDF 链融合、高频算子 Rust 重写（文本清洗链 11 算子、图片 blur）。
- 调度层：UDF 并发度自适应、Flight Shuffle NUMA-aware 优化。
- 视频转码：BoostKit x265 硬件加速（外部依赖）。
- 详见 `daft-kunpeng-overall-design.md`（IR-1/IR-2 需求分析）与 `daft-kunpeng-perf-design-spec.md`（性能设计）。

### 技术难点

- 多模态场景 mapper 大量使用 Python UDF（如视频抽帧、缩放等），当前bench 结果 rust < 1%。
- 上游不确定性：Daft arrow2 → arrow-rs 迁移（#5741）,字节使用 0.7.2(arrow2) 和社区版本 0.7.21(arrow-rs)不一致。

## Portable-Simd

当前进度: 软件生态二期立项

### 背景 / 应用情况 / 商业价值

- 目标：Rust 便携 SIMD 库，类似 Google Highway / std::simd 的抽象层——屏蔽 x86 AVX/AVX-512、AArch64 NEON/SVE/SVE2、WASM SIMD 差异。
- 不用 std::simd：仍为 nightly 实验特性（tracking #86656，稳定化无时间表）；且 ARM 表现分化——连续数值 4-9x，交错数据退化至 0.13x（M4 benchmark）。
- 生态现状：Rust 无 Highway 等价物——packed_simd 已弃用、wide 覆盖面窄；Highway 为 C++ 库（现作为 Chromium third_party 依赖），不服务 Rust。
- 实现：按 target 区分架构，调用 std::arch intrinsics 或直接汇编；SVE/SVE2 intrinsics 2026-04 才入 nightly stdarch（PR #2071），仍 unstable。
- 优势：对外 safe API，用户免写 unsafe；运行时特性检测 + 降级路径，避免调用不支持的指令导致 SIGILL/core。
- 定位：SVE 是鲲鹏差异化硬件（vs Graviton N1），SVE/SVE2优先(如果支持）、 NEON Fallback 。

### 应用架构 / Rust 位置

- 上层应用：Lance / Daft / arrow-rs / polars（DataFrame 引擎）/ memchr（字节搜索）/ blake3（哈希）/ simdutf8（UTF-8 校验）/ lz4_flex（LZ4 压缩）/ zune-jpeg（JPEG 解码）
- Portable-Simd（safe API 抽象层）
- 依赖层：std::arch intrinsics / 内嵌汇编 asm!
- 硬件：Kunpeng 优先（NEON/SVE/SVE2）/ 其他 ARM / x86 (AVX2/AVX-512)

### Kunpeng 亲和优化点

性能优化时同时推进 x86 和 Arm, 避免 x86 单边优化

### 技术难点

- 多架构统一：同时适配 SVE（可变宽度 128-2048-bit + 谓词）与 AVX-512（固定 512-bit + 掩码），编程模型差异大。
- 运行时分发：特性检测 + 降级路径（920 无 SVE → NEON），避免 SIGILL。
- 应用推广：推荐到依赖仓库使用，需要社区认可读。

## PyO3 & rust-std

当前进度: 软件生态二期立项

### 背景 / 应用情况 / 商业价值

- PyO3：Rust↔Pythojinn FFI 主流方案（crates.io ~2.37 亿下载、2,116 reverse dependents）；Polars / LanceDB / Daft 等用其发布 Python API，替代传统 C/C++ 扩展层。
- rust-std/core/alloc：Rust 全生态热路径底座；鲲鹏缺口在 LSE 原子、memcpy/memcmp、LLVM tsv110 识别/调度模型。
- 商业价值：上游杠杆点，一次修复覆盖 Polars / DataFusion / Arrow / Daft 等 Python+Rust 数据栈。

### 应用架构 / Rust 位置

- PyO3：CPython extension module——Python call → PyObject/PyCFunction → trampoline → extract → Rust fn → IntoPy。
- 性能损失点：list↔Vec 逐元素 extract；Vec<u8>/String memcpy/UTF-8；长计算未 allow_threads；PyErr/traceback；async 桥接。
- rust-std 热路径：atomic/Arc/Mutex/RwLock（LSE）、memcpy/memcmp、HashMap、字符串处理。

### Kunpeng 亲和优化点

- memcpy：bytes/string/buffer 转换优先 zero-copy（Arrow / buffer protocol），拷贝路径验证 libc AArch64 memcpy。
- TODO

### 技术难点

- PyO3 热点在 FFI/GIL/memcpy/atomic，非 SIMD-heavy；intrinsics 直接收益有限。
- openEuler LLVM tsv110 优化未上游（ldp/stp-noq、预取、ICP 仅 openEuler 分支），rustc 默认 upstream LLVM 拿不到。

## AgentEnv & CubeSandbox

当前进度: 调研

### 背景 / 应用情况 / 商业价值

- CubeSandbox：腾讯云 AI Agent 安全沙箱（Apache-2.0），rust-vmm + KVM MicroVM，E2B 兼容；冷启动 <60ms、单实例内存 <5MB、Rust 占比 ~48%、~11.5k stars。
- AgentENV（AENV）：清华 MADSys + 月之暗面 2026-07 开源（MIT），Firecracker MicroVM Agentic RL 平台（Kimi K3）；boot/resume <50ms、pause <100ms、成本降 88.6-96.8%。
- 商业价值：Agentic RL / 代码解释器 / 工具调用需强隔离高密度沙箱；竞争点在启动/恢复时延、单实例内存、快照/fork 成本。

### 应用架构 / Rust 位置

- CubeSandbox：CubeAPI（axum）/ Hypervisor（Cloud Hypervisor fork + rust-vmm）/ CubeShim（containerd-shim）/ cube-agent（tokio-vsock）。
- AgentENV：Rust server / orchestrator / FirecrackerBackend / warm-pool / snapshot / overlaybd+ublk；多节点 gateway/scheduler 为 Go。
- 共性：MicroVM 控制面 Rust 化（KVM / Firecracker / rust-vmm），热点在启动、快照、fork、镜像层、内存回收。

### Kunpeng 亲和优化点

- 启动链路：鲲鹏实测 cold start 与 snapshot boot/resume/pause 分段耗时（KVM vCPU 创建、guest kernel、vsock/envd）。
- 密度/I/O：MicroVM RSS、page-cache 共享、overcommit、overlaybd+ublk 本地缓存命中率（AENV 1.5M images 生产规模）。
- ARM64 适配：CubeSandbox v0.5 ARM64 全栈；验证 Firecracker/rust-vmm 在 Kunpeng + EulerOS 的 KVM/virtio/vsock/eBPF 路径。

### 技术难点

- Firecracker 已支持 aarch64；鲲鹏 + EulerOS 组合缺实测基线（KVM capability、guest kernel 配置）。
- 镜像层依赖：ublk 需 Linux 6.0+；overlaybd 当前依赖 TCMU（target_core_user），EulerOS 是否启用需实测。
- 兼容性：guest kernel 最小配置、virtio-mmio/FDT、页大小（4K/64K）与 Firecracker/CubeSandbox 适配。

## Sched-ext

当前进度: 调研

### 背景 / 应用情况 / 商业价值

- sched_ext：Linux 6.12 主线 BPF 可编程调度类；scx 官方调度器集采用 Rust 用户态 + C/BPF 内核态。
- 落地：Meta 生产（LAVD 通用默认候选；ads 分层策略 p99 -28%、省电 3.28MW、+1.1% ads ranked）；Steam Deck（CachyOS Handheld、Bazzite）。
- 价值：无需 fork 内核即可按业务线程/NUMA/中断/GPU 协同定制调度，适合 AI 训练/推理与多路 ARM 服务器。

### 应用架构 / Rust 位置

- 双层结构：Rust 用户态（加载/CLI/监控/拓扑）+ C BPF 内核态（struct sched_ext_ops 回调：select_cpu/enqueue/dispatch/running/stopping/tick）。
- 核心原语：DSQ（每 CPU 本地队列 + 自定义共享队列）；公平性 vtime / deadline 二选一或组合。
- 安全兜底：watchdog（30s）/ SysRq-S / 进程退出 → 任何故障回退 EEVDF。

### Kunpeng 亲和优化点

- 现状：24.03 LTS SP4 / OLK-6.6 未启用 `CONFIG_SCHED_CLASS_EXT`；sched_ext 已在 6.12 主线，OLK-6.6 backport 见 PR !15063。
- 内核前置：`CONFIG_SCHED_CLASS_EXT` + `BPF_SYSCALL`/`BPF_JIT`/`DEBUG_INFO_BTF`；确认 openEuler BPF JIT/BTF/pahole 在 aarch64 可用。
- Kunpeng 适配：优先 scx_rusty / scx_layered；验证多路 NUMA 跨 socket 迁移、绑核/内存亲和，联动灵衢链路计数器（若暴露）。

### 技术难点

- 内核侧：OLK-6.6 backport 6.12 sched_ext（`CONFIG_SCHED_CLASS_EXT` + BPF JIT + BTF）。
- BPF/拓扑侧：BPF 程序 x86/ARM 可移植；scx_rusty / scx_utils 多 NUMA 适配，鲲鹏多路/灵衢跨 socket 成本建模。
- 验证：AI 训练/推理 p99/吞吐/迁移率；watchdog/SysRq/退出回退 EEVDF 压测。

## SGLang & vLLM

当前进度: 调研

### 背景 / 应用情况 / 商业价值

- vLLM：LLM serving 默认开源基座（~90k stars，PagedAttention/连续批处理）；SGLang：~33k stars，RadixAttention + 结构化生成 + agent 工作流。
- 两者 Python 调度/模型执行为主，GPU/NPU 内核依赖 CUDA/HIP/Triton/FlashInfer；高并发解码下 CPU 侧调度、KV/prefix-cache 管理成瓶颈。
- 商业价值：LLM 推理服务层决定 Ascend 集群吞吐/p99/成本，是鲲鹏 + 昇腾交付入口；vLLM 偏通用覆盖，SGLang 偏 prefix/结构化/agent 场景。

### 应用架构 / Rust 位置

- vLLM：Rust frontend 已入主线（rust/，`VLLM_USE_RUST_FRONTEND=1`，实验性）；#40459 vllm_rs 为 draft PoC——Rust BlockPool opt-in，Qwen3-0.6B/H100 E2E +4.4%。
- SGLang：rust/sglang-server——API server + tokenizer/detokenizer 池（tokio + 绑核）；dynamo-tokenizers Rust tokenizer。
- 社区：rvllm / vllm.rs 为纯 Rust serving 探索，非官方主线。
- 结论：Rust 切入点集中在 API frontend、tokenizer/detokenizer、KV/调度控制面；模型执行/算子仍由 Python + CUDA/Triton 主导。

### Kunpeng 亲和优化点

- 编译/图缓存：torch.compile/Inductor 在 AArch64 已可用（Graviton3 NLP geomean ~2x）但需鲲鹏实测；vLLM vllm/ir + 编译缓存降低下发前开销。
- CPU 侧亲和：tokenizer/detokenizer、调度器、KV block 绑核 + NUMA，验证 ARM 多核控制面 p99。
- Ascend 后端：vllm-ascend 社区插件；SGLang 依赖 CANN/TorchNPU/Triton-Ascend/sgl-kernel-npu（--attention-backend ascend）。

### 技术难点

- vLLM Rust 控制面（vllm_rs）为 draft PoC 未合入，依赖上游决策。
- Triton-CPU：推理关键算子（flash_attention/rms_norm/softmax）已有测试，但社区规模小（Stars 3、7月合入 PR 9），鲲鹏性能待实测。
- 多后端（CUDA/Ascend/CPU）调度、打包、CI 矩阵复杂；Ascend 算子覆盖需跟随 CANN。

