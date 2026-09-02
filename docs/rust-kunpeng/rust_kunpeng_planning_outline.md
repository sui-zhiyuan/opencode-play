<!--
### 本文件编辑约定（本 session，勿删）

1. 工作流：AI 每轮修改写入工作区；用户 review 后 `git add` AI 的内容入 index；
   用户自己的批注保留在工作区（未暂存）。每轮修改前，AI 必须先通过
   `git status` / `git diff` / `git diff --cached` 读取用户批注，按其意见调整后再动手。
2. 语言风格：参照 Daft 章节「背景 / 应用情况 / 商业价值」——仅列举关键点与关键数据，
   省略为连贯性补全的非重点信息；行文简洁，多要点、少铺垫。
3. 不重复：相同信息不得在不同章节重复出现；已被其他章节覆盖的内容在此处省略或仅引用。
4. 除特殊要求外，每个对话 round 仅能能修改单个 3 级章节，例如（Daft & Lance）/ （背景 / 应用情况 / 商业价值）
   可以参考其他章节，但不得修改其他章节。
-->

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
- rust-std/core/alloc：Rust 全生态热路径底座。
- 商业价值：上游杠杆点，一次修复覆盖 Polars / DataFusion / Arrow / Daft 等 Python+Rust 数据栈。
- 团队价值（PyO3）：技能点难度合适，涉及内存布局，memcpy（DMA），FFI 等技术点（技术点应用广泛）。方便验证，快速给出结论。

### 应用架构 / Rust 位置

- PyO3：CPython extension module——Python call → PyObject/PyCFunction → trampoline → extract → Rust fn → IntoPy。
- 性能损失点：list↔Vec 逐元素 extract；Vec<u8>/String memcpy/UTF-8；长计算未 allow_threads；PyErr/traceback；async 桥接。
- rust-std 热路径：atomic/Arc/Mutex/RwLock（LSE）、memcpy/memcmp、HashMap、字符串处理。

### Kunpeng 亲和优化点

- memcpy：bytes/string/buffer 转换优先 zero-copy（Arrow / buffer protocol），拷贝路径验证 libc AArch64 memcpy。
- rust-std: TODO

### 技术难点

- rust std 性能优化合入需要 社区 commitor 等同意，性能相关优化破坏可读性。
- PyO3 和 Rust std 均为单线程场景，950 难以发挥众核优势，主频劣势暴漏明显。 

## AgentEnv & CubeSandbox

当前进度: 调研

### 背景 / 应用情况 / 商业价值

- CubeSandbox：腾讯云 AI Agent 安全沙箱（Apache-2.0），rust-vmm + KVM MicroVM，E2B 兼容；冷启动 <60ms、单实例内存 <5MB、Rust 占比 ~48%、~11.5k stars。
- AgentENV（AENV）：清华 MADSys + 月之暗面（aka Kimi） 2026-07 开源（MIT），Firecracker MicroVM Agentic RL 平台；宣称 boot/resume <50ms、pause <100ms（阿里云 ecs.g9i 推测为 Xeon 6xxx）、成本降 88.6-96.8%。
- 商业价值：Harness 环境 / 代码解释器 / 工具调用需强隔离高密度沙箱；竞争点在启动/恢复时延、单实例内存、快照/fork 成本。

### 应用架构 / Rust 位置

- AgentENV（主体 Rust；本节聚焦单节点数据面）
  - API（Axum）：调用入口，鉴权 / E2B 兼容协议
  - Orchestrator：生命周期状态机（create/pause/resume/snapshot/fork/delete + auto-pause/resume）
  - sandbox（FirecrackerBackend）：Firecracker VM 管理（spawn / 网络 / 块设备挂载）；每 VM = VMM 线程 + vCPU 线程 + API 线程
  - warm-pool：Firecracker 进程预热池（跳过 spawn + socket 轮询）
  - snapshot / template：快照 / fork / 模板（内存恢复 + 基页内存 CoW，单机核心）
  - overlaybd + ublk（+ ublk-daemon）：分层镜像 + 用户态块设备（io_uring）
  - envd：guest 内 daemon（E2B 开源，Go）的 Rust 客户端
- CubeSandbox（Rust 控制面；忽略 Go 开发集权交互面）
  - CubeAPI（axum）：调用入口，E2B 兼容 REST
  - CubeHypervisor / CubeShim：KVM microVM（Cloud Hypervisor fork，自带 snapshot/restore）
  - cube-agent：guest 侧 agent（tokio-vsock）
  - CubeCoW：快照引擎（XFS FICLONE reflink，磁盘 CoW；供节点侧 Go 组件 CGO 调用）
- Common
  - 都基于 rust-vmm + KVM
  - CoW 路径差异：内存 CoW / template fork（AgentENV）vs 磁盘 CoW / XFS reflink（CubeSandbox）

### Kunpeng 亲和优化点

**评估指标**（背景节竞争点的鲲鹏化；上游数据为 Xeon g9i，需先在 950/950 v200 复测）

- 启动时间：本地已有解析 OCI 缓存时的启动（OCI 复用高，冷启动降权）
- 活跃 microVM 数量：单实例内存占用 + 线程调度/NUMA 放置（每 VM = VMM+vCPU+API 三线程，高密度数千线程；见 Sched-ext 章）
- pause/resume 时间：主指标（harness 大多等待 LLM 生成，沙箱空闲占比高）
- 镜像解析速度：待分析，需要输入

**优化方向**

- 页大小 4K/64K：CoW 粒度 vs 缺页次数 trade-off，贯穿恢复速度与内存密度（鲲鹏常用 64K，需实测拐点）
- CubeSandbox：CubeCoW XFS reflink（FICLONE）在鲲鹏 NVMe/64K 页下开销验证
- overlaybd + ublk 数据路径：lazy-load 解压（lz4/zstd）+ CRC32C 校验在运行时 IO 热路径（920B+?）
- image 模块 下载/解压/映射，非重点路径，性能不关键（待确认，跨节点？）
- 跨 microVM cow 内存共享，热点指令强制保留在L3缓存（仅 950 支持）
- TODO more

### 技术难点 / 团队能力 / 项目推进

- 需要提升团队对OS内核理解
- 需要提升团队对 ARM 硬件虚拟化理解
- microVM 不可跨架构迁移，因此无法 Kunpeng 50% + x86 50% 组件集群

## Sched-ext

当前进度: 调研

### 背景 / 应用情况 / 商业价值

- sched_ext（scx，可扩展调度器）：Linux 6.12 合入主线的内核特性，允许用 BPF 程序实现 CPU 调度器并动态加载/热更新。
- eBPF（extended BPF）：内核内置的沙箱化字节码执行环境，用户态程序编译为 eBPF 字节码，经 verifier 静态校验 + JIT 编译后在内核态安全运行；可实现（网络 XDP / 可观测性 / 安全 / 调度）。
- 商业价值：针对 AI 训练和推理场景，当前 Kunpeng CPU 无法满足 NPU / GPU 训练数据推入，导致 NPU / GPU 调度有空闲，降低训练效率。

### 应用架构 / Rust 位置

- Rust 用户态公用模块 (11,934 行)
  - scx_utils 核心共享库：拓扑、cpumask、cgroup、energy_model、CLI、GPU/netdev/perf 等通用工具
  - scx_stats 指标传输库（+ scx_stats_derive 派生宏）
  - scx_rustland_core 用户态调度框架（scx_rustland 的决策核心）
  - scx_arena 初始化 BPF arena（内存分配器）
  - scx_userspace_arena 用户态与 BPF arena 交互
  - scx_raw_pmu PMU 计数器访问
  - scx_cargo 构建期工具：BpfBuilder 在 build.rs 里编译 BPF C → 生成 skeleton
  - scx_bpf_compat BPF 兼容性探测工具-跨内核版本用
- eBPF 内核态公用模块（9,535 行）
  - collection （堆 ，红黑树，位图，队列，B树）
  - allocator
  - os操作工具 （CPU 掩码，cgroup 带宽控制 CPU 拓扑 BPF arena）

- scx_cosmos (NIVIDIA 开发 Rust-用户态 1960 c-内核态 1614)
  - 非饱和模式 / Local DSQ （各个CPU 维护自己的队列， 简单 round-robin）
  - 饱和模式 / Share DSQ （若当前cpu 利用率超过阈值，则进入 share DSQ，则按 deadline （累计运行时间+上次睡眠以来运行时间）排序分发到其他CPU 执行）
  - 优先 GPU Numa 亲和（用户态感知，传递给内核）优先安排到对应 numa 的 cpu 上
  - 用户态功能  CLI 参数解析 / 拓扑发现与初始化 /  GPU 感知 / 动态阈值自调 / 指标监控 / 装载卸载调度器
- scx_layered (Meta 使用 Rust-用户态 14679 c-内核态 5604)
  - CPU 归属某个 Layer ，Layer 根据自己资源决定占用的 CPU ，没有归属自动属于 open layer，超分时按 weight 分配
  - 三种 layer ：Confined（限专属 CPU）/ Grouped（可溢出）/ Open（无专属，填空隙）
  - CPU 优先处理归属 layer 任务， 空闲时处理其他 layer 任务 ， 有 preempt（抢占层）配置的层可以抢占 CPU 调度
  - 线程会归属到某个 Layer，规则匹配，根据 os 事件刷新
- 默认策略
  - 分优先级 DL(deadline) > RT(realtime) > FAIR(CFS/EEVDF) > IDLE
  - 高优先级无条件高于低优先级，每层按运行时间平衡，有 NUMA 时，按 NUMA 域管理，如果 NUMA 内资源不足，则其他 NUMA 分配，

- 双层结构：Rust 用户态（加载/CLI/监控/拓扑）+ C/BPF 内核态（`struct sched_ext_ops` 回调：select_cpu/enqueue/dispatch/running/stopping/tick）。

### Kunpeng 亲和优化点

**评估指标**

- KuenPeng CPU 是否适合当前已经实现调度选型。
- 算子下发场景 NPU 空闲时间


**优化任务**

**选型**（本质是"NPU 喂数线程优先级/隔离"，非通用负载均衡）

- scx_layered 为主（训练+推理统一）：Confined/Grouped + util_range 划弹性专属 CPU 分区 + preempt + per-layer per-LLC DSQ + prox_map 读 NUMA distance；唯一能表达"喂数线程专属可抢占分区"。
- scx_rusty 降级为通路验证：不读 NUMA distance，跨灵衢代价靠固定阈值，无法表达喂数优先级。
- scx_cosmos 暂不适用：GPU 亲和依赖 NVML，Ascend 上 Nvml::init 失败 → 静默退化；备选 scx_bpfland（轻量推理）、scx_mitosis（混部隔离）。

**实现优化点**（改代码）

- Ascend NPU 拓扑感知（核心缺口）：scx_utils/gpu.rs 加 Ascend 分支（DCMI / PCI 0x19e5 / npu-smi）；layered kprobe/nvidia_* 换 davinci 入口。
- 64K 页 arena：lib/alloc/userapi.h、asan.h 硬编码 PAGE_SIZE=4K，64K 内核下偏移错乱 → sysconf(_SC_PAGESIZE)。
- 同构核语义：topology.rs 全判 Big{turbo:false} → --primary-domain powersave 空集，需 fallback。

**配置优化点**（现有旋钮）

- layered 三层 JSON：npu-feeder（Confined + util_range[0.6,0.85] + cpus_range[8,32] + preempt + nodes 钉 NPU node）+ infer-tokenizer（短 slice_us）+ catch-all（Open）。
- 零代码 NPU 亲和：nodes 手工钉 NPU 本地 node（npu-smi info -t topo 查 numa_node）。
- --virt-llc=4-8 对齐 CCL；xllc_mig_min_us 抑制跨灵衢迁移；--antistall-sec 防饿死；勿开 --enable-gpu-support。
- rusty：--greedy-threshold-x-numa 0、--mempolicy-affinity；勿用 --cpumasks。

**前置 / 现状**

- 24.03 LTS SP4 / OLK-6.6 未启用 `CONFIG_SCHED_CLASS_EXT`，backport 见 PR !15063。
- 前置：`CONFIG_SCHED_CLASS_EXT` + `BPF_SYSCALL`/`BPF_JIT`/`DEBUG_INFO_BTF`；aarch64 JIT/BTF/pahole 可用性待确认。

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

