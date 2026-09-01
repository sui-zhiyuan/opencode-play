# vLLM 与 SGLang：背景、Rust 角色、ARM 亲和性及无 NPU 测试方案

> 调研日期：2026-09-01  
> 口径：本文所称“ARM 亲和”**仅指性能亲和**，即能否充分利用 ARM 的 NEON/BF16/SVE、NUMA 和内存带宽，取得有竞争力的吞吐、延迟和单位成本；不讨论能否在 ARM64 上编译或安装。

## 1. 执行摘要

- **vLLM** 是面向大模型推理与在线服务的高吞吐引擎，起源于 UC Berkeley。其代表性创新是 PagedAttention：用类似操作系统分页、写时复制的方式管理 KV Cache，减少显存碎片并提高连续批处理容量。原始论文在其测试条件下报告了相对 FasterTransformer、Orca 等系统 **2–4 倍吞吐提升**。
- **SGLang** 最初同时提供结构化语言模型程序的前端语言和高性能运行时，起源于 LMSYS/学术团队。其代表性机制是 RadixAttention，以基数树自动复用请求间的公共前缀 KV Cache，尤其适合多轮对话、RAG、few-shot、Agent 和结构化输出。原始论文在多类任务上报告最高 **6.4 倍吞吐提升**；该数字是论文特定硬件、模型和基线下的结果，不宜当作今天两框架的通用对比。
- 二者现在都已超出“单机 GPU 推理库”：支持 OpenAI 兼容接口、动态批处理、张量/数据并行、量化、投机解码、前缀缓存，以及多种 GPU/NPU/CPU 后端。它们的核心业务价值是提高昂贵加速器利用率、降低每 token 成本，并把模型变成可观测、可扩缩、可治理的在线服务。
- **Rust 不是两者矩阵乘、Attention、量化 kernel 的主体语言**。张量热路径仍主要依赖 PyTorch、CUDA/ROCm、Triton、C/C++ 及厂商算子库。Rust 的价值主要在控制面和 I/O 热路径：HTTP/gRPC、路由、并发、流式传输、分词、结构化解析及 benchmark 客户端。
- **vLLM 的 ARM 性能亲和基础明显更完整**：已有 NEON、ARM BF16、Arm Compute Library/oneDNN 路径、OpenMP 核绑定和 Graviton3 验证；但不同 ARM 代际的 ISA 分发、量化 kernel 覆盖及 SVE/SVE2 利用仍需实测，不能仅凭“支持 ARM”推断性能。
- **SGLang 的 ARM 性能优化成熟度较低**。其公开 CPU 优化路线明确以 Intel Xeon/AMX 为性能目标，对无 AMX CPU 主要保证功能而非性能。因此现阶段更适合作为性能预研对象，尤其应验证高前缀复用带来的收益能否覆盖其 ARM kernel 短板。
- **没有 NPU 完全可以测试**。若有 NVIDIA/AMD GPU，可测试主流生产路径；ARM CPU 真机也可测试调度、HTTP/Rust 前端、分词、缓存逻辑、端到端吞吐及 NEON/BF16/SVE、NUMA、内存带宽表现。纯 x86 主机和 QEMU 都不能证明 ARM 性能亲和。

## 2. 背景与应用价值

### 2.1 vLLM

vLLM 最初最重要的创新之一就是 **PagedAttention**。

它解决的是：

> LLM 的 KV Cache 非常大，而且每个请求的 KV Cache 长度不同，如何高效管理 GPU 显存？

传统方式：

```text
Request A
████████████████████

Request B
██████████

Request C
████████████████
```

由于每个请求长度不同、创建和结束时间也不同，KV Cache 需要不同大小的连续空间，容易产生显存碎片。

PagedAttention 类似操作系统的虚拟内存分页机制：

```text
虚拟内存
    ↓
Page
    ↓
物理内存
```

它把 KV Cache 分成固定大小的 block，并通过块表建立逻辑 KV Cache 到物理块的映射：

```text
KV Cache

A → [0][1][2][3]
B → [4][5]
C → [6][7][8]
```

这些编号用于说明逻辑映射；物理块不必连续。这样可以：

- 减少显存碎片
- 提高 KV Cache 利用率
- 支持更大的 batch
- 提高吞吐量

vLLM 目前已经发展成较完整的生产级推理框架，支持多种模型、GPU、并行方式以及 OpenAI-compatible API。其 V1 架构采用多进程设计，把 API Server、Engine Core、GPU Worker 等职责分开。


这带来三类价值：

1. **基础设施价值**：同样硬件承载更多并发，降低 GPU 空闲和 KV Cache 浪费。
2. **产品接入价值**：提供 OpenAI 兼容服务接口，便于把 Hugging Face 模型接入现有应用。
3. **平台价值**：支持量化、LoRA、多 GPU/多节点、投机解码、prefix caching 和多种硬件后端，减少团队自研 serving runtime 的成本。

原始依据：[PagedAttention/vLLM 论文](https://arxiv.org/abs/2309.06180)、[vLLM 官方仓库](https://github.com/vllm-project/vllm)。

### 2.2 SGLang

SGLang 面向的起点更偏“复杂 LLM 程序”：一个请求可能包含多次生成、分支、并行、工具调用和共享长前缀。RadixAttention 将已计算的 KV Cache 组织成基数树，根据 token 前缀匹配自动复用，因而在多轮对话、Agent、RAG、few-shot 和共享系统提示词的流量中价值更突出。结构化输出还结合约束解码和有限状态机优化。

#### RadixAttention 示例

例如：

```text
用户 A：

请分析下面这篇文章……
[非常长的文章]
问题 1

用户 B：

请分析下面这篇文章……
[同一篇文章]
问题 2
```

如果直接运行：

```text
Prompt A
   ↓
Attention
   ↓
KV Cache

Prompt B
   ↓
Attention
   ↓
KV Cache
```

两个请求会分别处理相同的长文章，产生大量重复计算。

RadixAttention 可以把公共前缀组织成基数树：

```text
                Root
                 │
          ┌──────┴──────┐
          │             │
      Common Prompt
          │
       ┌──┴───┐
       │      │
      Q1     Q2
```

也就是： **不同请求共享相同的 prefix KV Cache。**

请求 A 计算并缓存公共提示词和文章的 KV Cache 后，请求 B 可以命中这段公共前缀，只需继续计算自己的问题部分。前缀越长、重复率越高，节省的 prefill 计算通常越多；如果请求之间几乎没有相同前缀，则复用收益有限。

其应用价值集中在：

1. **高前缀复用场景**：减少重复 prefill，改善 TTFT 和整体吞吐。
2. **复杂生成流程**：把并行生成、约束输出、工具调用、多模态流程纳入统一 runtime。
3. **大规模服务治理**：Model Gateway 支持 HTTP/gRPC、缓存感知负载均衡、Prefill/Decode 解耦、重试、熔断、限流和服务发现。

原始依据：[SGLang 论文](https://arxiv.org/abs/2312.07104)、[SGLang Model Gateway 文档](https://github.com/sgl-project/sglang/blob/main/docs/advanced_features/sgl_model_gateway.md)、[SGLang 官方仓库](https://github.com/sgl-project/sglang)。

### 2.3 如何选择

| 维度 | vLLM | SGLang |
|---|---|---|
| 传统优势 | 通用、高吞吐、生态广的模型服务 | 前缀复用、结构化生成和复杂/Agent 工作负载 |
| 核心缓存思想 | 分页式 KV Cache 管理 | 基数树式公共前缀复用 |
| ARM 性能亲和 | 较高：NEON/BF16、ACL/oneDNN、绑核路径较明确 | 较弱：CPU 性能优化重心偏 Intel AMX，ARM 专项数据有限 |
| Rust 当前定位 | 新兴、可选的 Rust 前端和 benchmark；仍处早期 | Model Gateway/Router 已是重要 Rust 子系统，另有 PyO3 gRPC 组件 |
| 适合优先验证 | 通用模型兼容、吞吐和并发 | 高 cache hit、多轮、RAG、结构化输出及 PD 解耦 |

## 3. Rust 的作用与“占比”

### 3.1 vLLM 中的 Rust

vLLM 已有 `rust/` workspace、`vllm-rs` 二进制和独立构建流程。官方代码说明把它定义为“替代 Python 前端的 Rust 实现”，且明确标注仍处于很早期；当前典型架构是 **Rust OpenAI 兼容前端 + 受管的 Python headless engine**。另外，Rust benchmark client 可替代 Python `vllm bench serve`，降低启动时间和高并发压测客户端自身的 GIL/内存干扰。

因此 Rust 目前主要承担：

- API、协议、请求解析、流式传输等前端工作；
- 高并发 benchmark 流量生成；
- 未来降低 Python 控制面开销的演进方向。

它**不等于用 Rust 重写了 vLLM 推理内核**。模型执行、Attention 与算子仍主要在 Python/PyTorch 调度及 C++/CUDA/Triton/厂商库中完成。

按第三方 SLOC 快照，vLLM 仓库约为 Python 70.7%、Rust 7.4%、CUDA 4% 等；这只能表示某一时点的源码行/文件统计，不能代表运行时间占比或核心程度。[SLOC 快照](https://octocounts.com/github/vllm-project/vllm)、[Rust 前端说明](https://github.com/vllm-project/vllm/blob/main/rust/AGENTS.md)、[Rust benchmark](https://github.com/vllm-project/vllm/blob/main/rust/src/bench/README.md)。

### 3.2 SGLang 中的 Rust

SGLang 的 Rust 角色更集中、更生产化：`sgl-model-gateway` 是 Rust 网关/路由器，负责 worker 注册、HTTP/gRPC、缓存感知负载均衡、PD 协调、服务发现、重试、熔断、限流和可观测性；gRPC 路径还可在 Rust 进程内完成 tokenizer、reasoning parser 和 tool-call parser。`rust/sglang-grpc` 则通过 PyO3 作为 Python wheel 内的扩展模块。

但 SGLang 的模型 runtime、调度和大量 glue code 仍主要是 Python，kernel 仍主要是 CUDA/C++/Triton/相关库。故可作如下区分：

- **对整个仓库/张量计算**：Rust 是少数部分，不是算子主体；
- **对网关和数据面**：Rust 占比很高，甚至可以作为完整 Rust 二进制运行；
- **对端到端 CPU/GPU 时间**：模型较大时，绝大多数时间仍在矩阵运算和 Attention kernel；模型较小、并发很高或请求很短时，Rust 控制面的收益才更容易显现。

不建议给 SGLang 一个静态百分比：当前仓库同时包含大量生成配置、kernel、Python 与独立 Rust gateway，GitHub 字节占比既快速变化，也会严重低估/高估功能重要性。更有意义的是按组件判断。依据：[Model Gateway README](https://github.com/sgl-project/sglang/blob/main/sgl-model-gateway/README.md)、[Rust gRPC Cargo 配置](https://github.com/sgl-project/sglang/blob/main/rust/sglang-grpc/Cargo.toml)。

### 3.3 Rust 与 ARM 的关系

Rust 本身对 `aarch64-unknown-linux-gnu`/musl 支持良好，网络服务代码通常比含手写 SIMD 的 kernel 更容易跨架构。Rust 可以改善 ARM 上的控制面效率、并发安全和部署形态，但**不能自动解决 ARM 推理性能**：主要瓶颈仍是 GEMM、Attention、量化、内存带宽和 NUMA。真正决定 ARM 性能的是 PyTorch/oneDNN/Arm Compute Library、编译器、ISA 分发和针对模型结构的融合 kernel。

## 4. ARM 亲和性现状

### 4.1 vLLM：有较完整的 ARM 性能优化基础

与性能直接相关的现有能力包括：

- ARMv8/NEON，数据类型 FP32、FP16、BF16；
- 对 ARM BF16 指令的检测与专用路径；
- ARMv8.6-A 及以上的 FEAT_BF16 路径，文档列出 Graviton3/4、AmpereOne；
- `VLLM_CPU_OMP_THREADS_BIND`、`VLLM_CPU_KVCACHE_SPACE`，以及容器 cpuset/NUMA 绑定；
- AArch64 上以 Arm Compute Library 作为 oneDNN backend；
- 在 AWS Graviton3 上有实际验证基础。

因此结论是：**vLLM 已具备 ARM 性能亲和的基本构件，但是否“有竞争力”仍依赖具体 CPU 代际、内存通道、模型、dtype、量化方式和算子覆盖率。** 当前公开材料不能证明它在所有 ARM CPU 上都达到与同价位 x86 或专用 GPU 相当的单位成本。

参考：[官方 ARM CPU 安装文档](https://github.com/vllm-project/vllm/blob/main/docs/getting_started/installation/cpu.arm.inc.md)、[CPU 后端硬件列表](https://docs.vllm.ai/en/stable/getting_started/installation/cpu/index.html)、[CPU CMake 配置](https://github.com/vllm-project/vllm/blob/main/cmake/cpu_extension.cmake)。

### 4.2 SGLang：ARM 性能成熟度有限

SGLang 已具备 CPU engine、NUMA/TBB 依赖和 Rust Model Gateway 等可用于 ARM 优化的组件；Rust 控制面通常也更容易避免 Python/GIL 在高并发短请求下成为瓶颈。

限制在于：公开 CPU server 文档和优化路线主要围绕 Intel Xeon、AMX、sub-NUMA cluster 和 W8A8 INT8。项目路线说明对没有 AMX 的 CPU 主要保证功能而非性能。ARM 上依赖项还存在条件排除或替代，例如部分多媒体/扩散依赖按 `aarch64/arm64` 单独处理。这意味着：

- Server 与网关层有优化空间，但它们并非大模型张量计算的主要耗时；
- 纯 ARM CPU 的模型计算路径未显示出与 vLLM 同等程度的专项 kernel 和性能验证；
- 若目标是 ARM host + NVIDIA GPU，模型计算主要由 GPU 承担；ARM 性能亲和的重点转为控制面单核效率、NUMA/PCIe 拓扑、host-device 数据路径，以及 CUDA、PyTorch、FlashAttention/FlashInfer 是否真正命中高性能实现。

参考：[SGLang ARM64 Dockerfile](https://github.com/sgl-project/sglang/blob/main/docker/arm64.Dockerfile)、[CPU server 文档](https://github.com/sgl-project/sglang/blob/main/docs/platforms/cpu_server.md)、[CPU 优化路线](https://github.com/sgl-project/sglang/issues/8281)、[Python 依赖的 ARM 条件](https://github.com/sgl-project/sglang/blob/main/python/pyproject.toml)。

## 5. 优化 ARM 亲和的主要技术难点

### 5.1 ISA 与动态分发

ARM64 不是单一性能档位。Neoverse N1、V1、V2，Graviton2/3/4 和 AmpereOne 对 FP16、BF16、dot product、I8MM、SVE/SVE2 的支持不同。若只使用最低公分母 NEON，会浪费新 CPU 能力；只优化某一代 ISA，又会缩小可获得性能收益的机器范围。需要：

- 运行时能力探测与多版本 kernel 分发；
- NEON、BF16、I8MM、SVE/SVE2 的正确 fallback；
- 按实际算子形状选择 NEON 或 SVE 向量宽度、展开和预取策略。

vLLM 已有 ARM BF16 分发相关案例，说明 ISA 探测和 fallback 不仅影响正确性，也直接决定能否启用高性能路径。[ISA 测试讨论](https://github.com/vllm-project/vllm/issues/35300)。

### 5.2 高性能 kernel 与量化生态不对称

x86 有 AVX2/AVX-512/AMX 和成熟 oneDNN 路径，NVIDIA 有 CUDA/Tensor Core/FlashAttention。ARM 需要重新覆盖：

- GEMM、RMSNorm、RoPE、softmax、paged/radix attention；
- INT8/INT4、weight-only、KV cache quantization；
- MoE dispatch、top-k、专家矩阵乘；
- 小 batch decode 与大 batch prefill 两种不同形状。

通用算子实现通常无法获得理想 tokens/s。ACLE intrinsics、Arm Compute Library、oneDNN AArch64 backend、KleidiAI 等组件之间还要处理算子覆盖、布局转换和版本兼容。

### 5.3 NUMA、线程和内存带宽

LLM CPU inference 常受内存带宽限制。多 socket/多 NUMA 节点下，KV Cache、权重、OpenMP 线程和网络进程若跨节点，会造成远端内存访问。需要联合调优：

- `numactl`/cpuset、物理核而非 SMT 线程绑定；
- 权重和 KV Cache 的 first-touch/复制策略；
- tensor parallel 与 NUMA 节点的映射；
- tokenizer、HTTP/Rust gateway 与模型线程隔离，避免争抢核心。

这也是“CPU affinity（绑核）”意义上的 ARM 亲和：vLLM 已提供 `VLLM_CPU_OMP_THREADS_BIND`，SGLang ARM 镜像包含 `libnuma`/`numactl`，但最佳拓扑仍需按机器实测。

### 5.4 Python 控制面与 CPU 调度开销

GPU 很快、模型较小或并发很高时，tokenizer、detokenizer、JSON、sampling 和 scheduler 可能成为瓶颈。ARM 单核性能与 x86 不同，Python/GIL 路径更容易暴露。SGLang 已有 detokenizer 负载不均导致单核瓶颈的公开案例；Rust 前端/网关可缓解协议和解析开销，但必须保证与 Python 语义、流式输出和错误处理完全一致。[SGLang detokenizer 问题](https://github.com/sgl-project/sglang/issues/29366)。

### 5.5 性能依赖与 CI 矩阵

最终性能由 PyTorch、Triton、FlashAttention、FlashInfer、oneDNN/ACL、编译器和运行库共同决定，任一依赖回退到通用实现都可能吞掉框架层优化。性能 CI 需要覆盖：

- ARM CPU-only；ARM host + NVIDIA GPU；不同内核、内存与 NUMA 拓扑；
- 新旧 ARM ISA，以及 NEON/BF16/SVE/SVE2 各路径；
- 正确性、数值容差、性能回归。

持续性能 CI 必须使用 Graviton/Ampere/Grace 等 ARM 真机；QEMU 的计时不能用于判断性能亲和。

## 6. 无 NPU 条件下可用的 UT 与 benchmark

### 6.1 测试能力矩阵

| 环境 | 能测什么 | 不能得出什么结论 |
|---|---|---|
| x86 CPU-only | API、调度、tokenizer、缓存数据结构、Rust gateway/frontend、低成本端到端功能 | ARM kernel 性能、ARM ISA 正确性 |
| ARM64 CPU-only | NEON/BF16/SVE、NUMA/绑核、内存带宽、纯 CPU tokens/s 与延迟 | ARM host + GPU 的 PCIe/CUDA 路径 |
| ARM64 + NVIDIA GPU，无 NPU | 最接近 ARM GPU serving 生产形态，可测端到端吞吐和控制面瓶颈 | Ascend 等 NPU 后端性能 |
| x86 + NVIDIA/AMD GPU，无 NPU | 两框架成熟主路径，适合比较调度/cache/kernel | ARM host 影响 |

### 6.2 vLLM 现成工具

1. **在线服务 benchmark：`vllm bench serve`**  
   可测 request throughput、output token throughput、TTFT、ITL、TPOT、端到端延迟和各分位数；支持 random/ShareGPT 等数据。当前脚本入口位于 `vllm/benchmarks/serve.py`，官方 CI 性能说明也使用它。

   ```bash
   vllm serve Qwen/Qwen2.5-0.5B-Instruct --device cpu --dtype float32

   vllm bench serve \
     --backend vllm \
     --model Qwen/Qwen2.5-0.5B-Instruct \
     --dataset-name random \
     --random-input-len 128 \
     --random-output-len 64 \
     --num-prompts 100
   ```

2. **Rust benchmark client**  
   `vllm-bench` 可在没有 NPU/GPU 的客户端运行，只需目标 server 可访问。它适合高并发压测，避免 Python 压测端先成为瓶颈；官方 README 声称与 Python benchmark 的 JSON schema 和计时语义对齐。

3. **CPU UT/集成测试**  
   CPU Dockerfile 有 `vllm-test`/开发测试依赖路径，可运行标记或目录级 pytest。实际应先用 `pytest --collect-only` 查看当前版本测试集合，再选择平台、attention、quantization、entrypoints 等 CPU 可执行测试，避免把 CUDA-only skip 当成成功覆盖。

4. **微基准**  
   对 ARM 优化最有价值的是把端到端结果与 kernel microbenchmark、`perf stat`、内存带宽和 NUMA 数据结合。只看总 tokens/s 很难区分是 GEMM、KV Cache、scheduler 还是 HTTP 前端导致。

参考：[vLLM benchmark 目录](https://github.com/vllm-project/vllm/blob/main/benchmarks/README.md)、[性能 CI 说明](https://github.com/vllm-project/vllm/blob/main/.buildkite/performance-benchmarks/README.md)、[Rust benchmark client](https://github.com/vllm-project/vllm/blob/main/rust/src/bench/README.md)。

### 6.3 SGLang 现成工具

1. **在线服务 benchmark：`python -m sglang.bench_serving`**  
   支持 random/dataset 请求、速率和并发控制，可输出 throughput、TTFT、ITL 和端到端延迟；还可用 `--backend vllm` 压 vLLM，从而用同一个客户端做较公平的服务层对比。

   ```bash
   SGLANG_USE_CPU_ENGINE=1 python -m sglang.launch_server \
     --model-path Qwen/Qwen2.5-0.5B-Instruct \
     --device cpu --host 127.0.0.1

   python -m sglang.bench_serving \
     --backend sglang \
     --dataset-name random \
     --random-input-len 128 \
     --random-output-len 64 \
     --num-prompts 100 \
     --request-rate inf
   ```

2. **CPU server benchmark 路径**  
   官方 CPU server 文档明确给出 `--device cpu` 和 `bench_serving` 用法；但当前示例及优化主要面向 Intel Xeon。ARM 上应先从小模型、FP32/FP16 开始，再验证 BF16 和量化，不能直接套用 AMX/W8A8 结论。

3. **UT**  
   仓库有 `test/` 和 Rust CI/单元测试。无 GPU 时可优先执行 router/gateway、parser、tokenizer、API schema、sampling 辅助逻辑和纯 CPU 测试；大量 SRT/kernel 测试会要求 CUDA，需按 marker 或目录筛选，并检查 skip 清单。

参考：[bench_serving 指南](https://github.com/sgl-project/sglang/blob/main/docs/developer_guide/bench_serving.md)、[CPU server 文档](https://github.com/sgl-project/sglang/blob/main/docs/platforms/cpu_server.md)、[benchmark 实现](https://github.com/sgl-project/sglang/blob/main/python/sglang/benchmark/serving.py)。

## 7. 建议的可复现实验方案

### 7.1 最小正确性门槛

- 固定 git commit、模型 revision、tokenizer revision、PyTorch 和编译器版本；
- 使用 0.5B–1B 小模型，固定 seed、输入 token 数、输出 token 数；
- 比较 greedy 输出 token 是否一致或在明确容差内；
- 记录被 skip 的 UT，特别是 CPU/ARM/kernel 相关测试；
- 分别验证 FP32、FP16、BF16，量化另建测试组。

### 7.2 性能实验变量

- 并发：1、4、16、64；请求率：低负载到饱和；
- prompt/output：128/128、1K/128、4K/128，区分 prefill 与 decode；
- cache：关闭/开启，另做高共享前缀数据集；
- CPU：线程数、物理核绑定、NUMA 节点、SMT 开关；
- 指标：TTFT、TPOT/ITL、p50/p95/p99 E2E、input/output tokens/s、CPU 利用率、RSS、内存带宽、远端 NUMA 访问；
- 每组 warm-up 后至少重复 5 次，报告中位数和离散程度。

### 7.3 公平比较注意事项

- 两框架必须使用同一模型权重、dtype、最大上下文、输入输出长度和请求到达过程；
- 不要用各自默认配置直接对比：prefix cache、chunked prefill、torch.compile、quantization 和 tokenizer worker 默认值可能不同；
- 压测客户端与 server 最好分机或至少隔离 CPU 核；
- 随机数据可测调度上限，但不能代表真实 cache hit；需额外构造共享 system prompt、多轮会话和 RAG 数据；
- 同时用一个中立客户端压两者。SGLang `bench_serving` 原生支持 vLLM backend，是简单可行方案；再用各自客户端交叉复核客户端开销。

## 8. 结论与建议

1. 若近期目标是**纯 ARM CPU 推理落地**，优先以 vLLM 建立 baseline。它已有 NEON/BF16、ACL/oneDNN 和绑核路径。SGLang 可作为第二阶段验证，重点观察 RadixAttention 是否能通过高前缀复用抵消其 ARM kernel 成熟度不足。
2. 若目标是**ARM host + NVIDIA GPU**，两者都值得验证；主要性能风险从纯 CPU kernel 转向控制面单核能力、NUMA/PCIe 拓扑、host-device 数据路径，以及相关算子是否命中优化实现。
3. 若目标是**用 Rust 改善 ARM 亲和**，最现实的切入点是 tokenizer/detokenizer、HTTP/gRPC、JSON/结构化解析、路由和 benchmark client，而不是直接用 Rust 重写 GEMM。算子性能应优先投入 ARM ISA 分发、ACL/oneDNN/KleidiAI、量化 kernel 和 NUMA。
4. 无 NPU 不妨碍开展大部分工程工作：可完成 UT、API/路由 benchmark、CPU 端到端 benchmark，以及有 GPU 时的主流推理 benchmark。只有 NPU 后端专属 kernel、runtime 和通信性能必须在相应 NPU 上验证。
5. 建议把“ARM 性能亲和”验收拆成四道门：**确认高性能 ISA 路径实际命中 → NUMA/绑核与内存带宽达到预期 → 端到端吞吐和尾延迟稳定 → 相对同价位 x86/其他引擎具有可接受的每 token 成本**。

## 9. 资料索引

- [vLLM / PagedAttention 论文](https://arxiv.org/abs/2309.06180)
- [vLLM GitHub](https://github.com/vllm-project/vllm)
- [vLLM ARM CPU 安装说明](https://github.com/vllm-project/vllm/blob/main/docs/getting_started/installation/cpu.arm.inc.md)
- [vLLM CPU backend](https://docs.vllm.ai/en/stable/getting_started/installation/cpu/index.html)
- [vLLM Rust frontend](https://github.com/vllm-project/vllm/blob/main/rust/AGENTS.md)
- [vLLM Rust benchmark](https://github.com/vllm-project/vllm/blob/main/rust/src/bench/README.md)
- [SGLang 论文](https://arxiv.org/abs/2312.07104)
- [SGLang GitHub](https://github.com/sgl-project/sglang)
- [SGLang ARM64 Dockerfile](https://github.com/sgl-project/sglang/blob/main/docker/arm64.Dockerfile)
- [SGLang CPU server](https://github.com/sgl-project/sglang/blob/main/docs/platforms/cpu_server.md)
- [SGLang Model Gateway](https://github.com/sgl-project/sglang/blob/main/sgl-model-gateway/README.md)
- [SGLang bench_serving 指南](https://github.com/sgl-project/sglang/blob/main/docs/developer_guide/bench_serving.md)
