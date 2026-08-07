# Rust 当前应用形式分析

基于 **Daft、CubeSandbox、sglang、tokio、pyo3、pingora、axum、lance、TiKV** 九个有代表性的 Rust 项目的架构特征和选型理由，提炼 Rust 当前主流应用形式的 5 条结论。

---

## 结论 1：Python 是界面，Rust 是引擎 — ML/数据工具的标准双栈范式

这是九个项目中最普遍的模式。

| 项目 | Python 层做什么 | Rust 层做什么 |
|------|-----------------|---------------|
| [**Daft**](https://github.com/Eventual-Inc/Daft) | DataFrame API、DSL、交互式查询 | 物理计划执行、分布式 shuffle、列式运算、UDF 链融合 |
| [**sglang**](https://github.com/sgl-project/sglang) | 模型加载、tokenizer、调度策略定义 | 推理引擎运行时、batching 调度器、token 级内存管理 |
| [**lance**](https://github.com/lance-format/lance) | DataFrame 接口、向量检索入口 | 列存格式引擎、索引构建、零拷贝读取 |

### 共同特征

- Python 是**用户体验层**和**生态接入层**（NumPy/Pandas/Arrow 互通）
- Rust 是**性能核心**——所有计算密集、延迟敏感的路径都在 Rust
- [**PyO3**](https://github.com/PyO3/pyo3) 统一承担 FFI 桥接角色
- Arrow C Data Interface 实现**零拷贝**跨越语言边界

### 调用链

```
Python call → PyO3 trampoline → Rust 类型转换 → Rust function → 返回值转换 → Python
```

关键优化方向：
- 零拷贝传递 Arrow 数据（避免逐元素转换）
- 批量操作而非逐元素调用（减少 FFI 跨边界次数）
- 异步桥接（避免 GIL 阻塞）

> **趋势判断**：新的大数据/ML 工具几乎不再用 C/C++ 做扩展层，**Rust + PyO3 + Arrow** 已成为事实标准栈。

---

## 结论 2：系统基础设施从 C/C++ 向 Rust 迁移已不可逆

这四个项目代表了 Rust 在操作系统之下、硬件之上的"深水区"竞争力。

| 项目 | 替代/对标的 C/C++ 方案 | Rust 的核心优势 |
|------|------------------------|-----------------|
| [**CubeSandbox**](https://github.com/TencentCloud/CubeSandbox) | QEMU (C)、Firecracker (Rust) | KVM 控制面不能有内存 bug——UAF 或 double free 直接导致宿主机崩溃 |
| [**pingora**](https://github.com/cloudflare/pingora) | Nginx (C)、Envoy (C++) | 处理全球 10%+ HTTP 流量，C 的内存安全问题可能被远程触发 |
| [**TiKV**](https://github.com/tikv/tikv) | HBase (Java)、CockroachDB (Go) | Raft 状态机 + RocksDB 存储引擎，C/C++ 的内存 bug 直接导致数据损坏 |
| [**tokio**](https://github.com/tokio-rs/tokio) | libuv (C)、libevent (C) | 事件循环和调度器自身的安全性是异步栈的根基 |

### 共同特征

- 不是"Rust 和 C/C++ 竞争"——新项目**直接选 Rust**，存量项目**逐步用 Rust 重写热路径**
- 切入点都是**"出 bug 后果严重且 C/C++ 无法保证安全"**的场景
- Rust 带来的不仅是安全性，还有：
  - **Cargo**：优于 CMake/Makefile 的依赖管理
  - **编译器替代 sanitizer**：borrow checker 在编译期发现内存问题
  - **更短的新人上手周期**：不会踩到 UAF/double free/data race

### 安全性对比

| 语言 | 内存安全 | 数据竞争 | GC 停顿 |
|------|---------|---------|--------|
| C/C++ | ❌ 手动管理 | ❌ 无保障 | ✅ 无 GC |
| Go | ✅ GC 管理 | ✅ race detector | ❌ STW |
| Java | ✅ GC 管理 | ✅ synchronized | ❌ STW/GC |
| **Rust** | **✅ 编译期** | **✅ 编译期** | **✅ 无 GC** |

> **趋势判断**：虚拟化、代理、分布式存储——这些"基础设施铁三角"的下一代实现几乎全部是 Rust。

---

## 结论 3：异步是 Rust 网络服务的空气和水，且选择了"可组合"而非"大一统"

tokio 不是"被选中的运行时"——它是**默认的空气**。

```
                    tokio (异步运行时)
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       axum           pingora        CubeSandbox
    (HTTP 框架)    (代理框架)      (API/shim/agent)
    + tower         + HTTP/1/2      + tokio-vsock
    + hyper         + TLS           + ttrpc
```

### 可组合 vs 大一统

**Rust 的选择：层层可组合的异步栈**

```
tokio (异步运行时 + IO)
  └── hyper (HTTP 协议实现)
        └── tower (中间件抽象层)
              └── axum (路由 + 提取器 + 响应，薄层)
```

**Go 的选择：标准库一体式**

```
net/http (标准库，全功能，直接可用)
```

### 两种路径的取舍

| 维度 | Rust (可组合) | Go (大一统) |
|------|--------------|------------|
| 学习曲线 | 需理解 tower service 概念 | 标准库开箱即用 |
| 灵活性 | 每层可独立替换 | 标准库之外需第三方 |
| 演进速度 | 各层独立迭代 | 依赖 Go 版本发布 |
| 生态聚焦 | 社区围绕核心 crate 协作 | Google 主导 |

### 九个项目中的异步使用

| 项目 | 异步运行时 | 应用场景 |
|------|-----------|---------|
| **axum** | tokio | HTTP 路由 + 中间件 |
| **pingora** | tokio | HTTP/1/2 代理、TLS 终端、负载均衡 |
| **CubeSandbox** | tokio | CubeAPI (axum)、CubeShim (containerd-shim)、cube-agent (tokio-vsock) |
| **sglang** | tokio | 推理服务 HTTP/gRPC 接口 |
| **TiKV** | tokio (部分) | gRPC 服务层 |

> **趋势判断**：tokio 已成为 Rust 网络服务的**操作系统级基础设施**，所有需要异步 IO 的 Rust 项目要么直接用 tokio，要么在 tokio 之上构建。

---

## 结论 4：Rust 承担"安全边界封装层"角色

这个模式最能体现 Rust 的**独特价值**——不是取代所有代码，而是在不安全的世界和安全的世界之间建立边界。

```
不安全的世界                  ← Rust 安全边界 →      安全的世界
─────────────────────────────────────────────────────────────
Python C-API (CPython)        pyo3                  Python 用户代码
KVM ioctl (内核接口)          kvm-ioctls            CubeSandbox 控制逻辑
infinity/UD 网卡 (硬件寄存器)  FFI wrapper           网络数据面
C++ RocksDB (FFI 调用)        rust-rocksdb          TiKV 存储层
```

### 设计原则

1. **只在边界处写 `unsafe`**——把裸指针、FFI、系统调用封装在薄层里
2. 上面的所有业务逻辑（调度、状态管理、协议处理）都是纯 safe Rust
3. 这一层的 crate 通常**独立维护**且有严格的 API 契约

### 九个项目中的安全边界实例

| 项目 | 不安全边界 | 封装层 Crate |
|------|-----------|-------------|
| **pyo3** | Python C-API (PyObject, GIL) | pyo3 自身 |
| **CubeSandbox** | KVM ioctl、virtio、VFIO | kvm-ioctls, kvm-bindings, vfio-ioctls |
| **CubeSandbox** | seccomp BPF | seccompiler (rust-vmm) |
| **TiKV** | C++ RocksDB | rust-rocksdb |
| **TiKV** | Raft 网络/磁盘 IO | raft-rs (纯 Rust, safe API) |
| **Daft/lance** | Arrow C Data Interface | arrow-rs |

### 为什么这个模式重要

传统 C/C++ 项目：
```
业务代码 ──── 直接调用 ──── unsafe OS API
              (整层不安全)
```

Rust 项目：
```
业务代码 ──── safe API ──── unsafe wrapper ──── OS API
(纯 safe)    ↑ 安全边界     (最小 unsafe)      (不可控)
```

> **模式本质**：Rust 作为**"安全装甲"**包裹住所有不可信的 FFI 和系统调用边界。C/C++ 代码仍然可以在边界之外存在，但不会再污染上层。这就是为什么 Rust 可以只重写项目的 10-30% 最关键的 `unsafe` 部分，而不是全量重写。

---

## 结论 5：Arrow/Parquet/Lance → Rust 是列式数据工程的"默认实现语言"

数据工程领域正在形成一个稳定的技术栈三角：

```
数据格式层          →  Arrow (内存列式) + Parquet (落盘列式) + Lance (向量/版本化列式)
查询/计算层         →  DataFusion (Rust SQL 引擎) + arrow-rs (Rust Arrow 实现)
语言接入层          →  Python/R/Java ↔ PyO3/FFI ↔ Rust engine
```

### 九个项目中的五个深度依赖这一栈

| 项目 | 使用的组件 | 为什么需要 Rust |
|------|-----------|-----------------|
| **lance** | arrow-rs、自研列存引擎 | 随机读取、向量检索需要精细控制内存布局 |
| **Daft** | DataFusion、arrow-rs、lance | 零拷贝跨 Python↔Rust 传递 Arrow 数据 |
| **TiKV** | 自研 Coprocessor（类 DataFusion） | 谓词/聚合下推到存储节点，减少数据传输 |
| **sglang** | Tokenizer（Rust 实现） | 训练中 tokenization 不能成为瓶颈 |
| **CubeSandbox** | —（独立赛道） | — |

### 核心驱动力

1. **Arrow C Data Interface**：Rust 到 Python 的数据传递是**纯指针操作**，无拷贝
2. **SIMD 原语**：Rust 的 `std::simd`、NEON/SVE intrinsics 直接作用于列式数据
3. **编译期生命周期**：保证 buffer 生命周期正确——不会出现 Python/C 混合代码中常见的 UAF
4. **零成本抽象**：用纯 safe Rust 写列式算子，生成的机器码与手写 C 相当

### 对比其他语言

| 能力 | C/C++ | Java | Go | Rust |
|------|-------|------|----|----|
| 零拷贝 Arrow 交互 | ✅ 但 unsafe | ❌ GC 隔离 | ❌ 拷贝开销 | ✅ 编译期保证 |
| SIMD 向量化 | ✅ intrinsics | ❌ 受限 JIT | ❌ 不原生支持 | ✅ `std::simd` + intrinsics |
| 内存安全 | ❌ | ✅ GC | ✅ GC | ✅ 编译期 |
| 原生列式运算 | ✅ | ❌ 装箱开销 | ❌ 无 SIMD | ✅ |
| Python FFI 性能 | ✅ C-API | ❌ JNI 开销 | ❌ cgo 开销 | ✅ PyO3 零拷贝 |

> **趋势判断**：如果你想创建一个新的列式格式、存储引擎、或者查询引擎，**Rust 是目前唯一能同时提供"零拷贝 + 内存安全 + SIMD 向量化"**的选择。

---

## 全景总结

三条核心趋势概括五个结论：

| 趋势 | 代表项目 | 关键词 |
|------|---------|--------|
| **Python 生态的 Rust 化** | Daft, sglang, lance | PyO3, Arrow 零拷贝, 双栈范式 |
| **基础设施的 C/C++ → Rust 迁移** | CubeSandbox, pingora, TiKV, tokio | KVM, Raft, 代理, 安全性不可妥协 |
| **数据工程的 Rust 栈标准化** | lance, Daft, TiKV | DataFusion, 列式, SIMD, 零拷贝 |

### 底层逻辑

每条趋势背后有一个共同的底层逻辑：

> **当场景需要同时满足"极致性能 + 内存安全 + 复杂并发"时，Rust 是目前唯一能同时做到三者、且生态已成熟到可工程化落地的语言。**

### 项目选型速查

| 项目 | 所属趋势 | Rust 应用形态 |
|------|---------|--------------|
| Daft | Python 生态 Rust 化 + 数据工程 | Python 面 + Rust 数据引擎核 |
| CubeSandbox | 基础设施迁移 | 全栈 Rust 微虚拟机服务 |
| sglang | Python 生态 Rust 化 | LLM 推理服务，Rust 重写热路径 |
| tokio | 基础设施迁移 + 可组合网络栈 | 异步运行时基础设施 |
| pyo3 | Python 生态 Rust 化 | 安全 FFI 边界封装层 |
| pingora | 基础设施迁移 + 可组合网络栈 | 可复用代理框架 |
| axum | 可组合网络栈 | HTTP 框架（薄层，组合 tower/hyper） |
| lance | 数据工程标准化 | 列式存储格式引擎 |
| TiKV | 基础设施迁移 + 数据工程 | 全栈 Rust 分布式 KV 数据库 |
