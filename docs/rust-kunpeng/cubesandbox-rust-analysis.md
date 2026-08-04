# CubeSandbox Rust 技术栈分析

CubeSandbox 是腾讯云开源的 AI Agent 安全沙箱服务（Apache 2.0），基于 RustVMM + KVM 构建 MicroVM，冷启动 <60ms，单实例内存开销 <5MB。Rust 代码占比 ~48%，是项目的核心语言。

- **GitHub**: [TencentCloud/CubeSandbox](https://github.com/TencentCloud/CubeSandbox) | ⭐ ~10.8K
- **Rust MSRV**: 1.77.0 (hypervisor workspace)
- **Workspaces**: 5 个独立 workspace，30+ crate
- **架构参考**: Cloud Hypervisor、Kata Containers、Firecracker

---

## Rust 组件全景

```
                    ┌──────────────────────────────┐
                    │       rust-vmm 生态            │
                    │  kvm-ioctls  kvm-bindings      │
                    │  vm-memory   vmm-sys-util      │
                    │  linux-loader  vfio-ioctls     │
                    │  vm-fdt  virtio-queue          │
                    └──────┬───────────────────────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    │                      │                      │
    ▼                      ▼                      ▼
┌──────────┐     ┌──────────────┐     ┌────────────────┐
│CubeAPI   │     │  Hypervisor  │     │   CubeShim      │
│          │     │  (Cloud      │◄────│   containerd-shim│
│ axum     │     │  Hypervisor  │     │   ttrpc          │
│ tower    │     │  fork, ~30   │     │   oci-spec       │
│ reqwest  │     │  crates)     │     │   nix            │
│ utoipa   │     └──────┬───────┘     └────────┬────────┘
└──────────┘            │                      │
                        │ KVM                  │ vsock
                        ▼                      ▼
                 ┌──────────────┐     ┌────────────────┐
                 │   MicroVM    │     │  cube-agent     │
                 │  (Guest)     │◄────│  tokio-vsock    │
                 └──────┬───────┘     │  ttrpc          │
                        │             │  rustjail       │
                        │             │  cgroups-rs     │
                        ▼             └────────────────┘
                 ┌──────────────┐
                 │   CubeCoW    │
                 │  xfs reflink │
                 │  FICLONE     │
                 └──────────────┘
```

---

## 一、CubeAPI — REST API 网关

独立的 Cargo 项目，构建产物为单一二进制 `cube-api`。兼容 E2B SDK 协议，替换 URL 即可从 E2B 迁移。

### 依赖清单

**Web 框架**
| Crate | 版本 | 用途 |
|-------|------|------|
| `axum` | 0.7 | Web 框架（macros + WebSocket） |
| `axum-extra` | 0.9 | 增强功能（typed-header） |
| `tower` | 0.4 | 中间件框架（full features） |
| `tower-http` | 0.5 | CORS、压缩、限流、请求 ID、超时 |
| `utoipa` | 5.4 | OpenAPI 文档（chrono/uuid/yaml features） |

**异步运行时**
| Crate | 版本 | 用途 |
|-------|------|------|
| `tokio` | 1.x（full） | 异步运行时 |
| `futures` | 0.3 | async 组合子 |
| `async-trait` | 0.1 | trait async fn |

**速率限制**
| Crate | 版本 | 用途 |
|-------|------|------|
| `governor` | 0.6 | 令牌桶算法，tower 兼容 |

**HTTP 客户端**
| Crate | 版本 | 用途 |
|-------|------|------|
| `reqwest` | 0.12 | 连接池 + rustls TLS |

**序列化/配置**
| Crate | 版本 | 用途 |
|-------|------|------|
| `serde` | 1.x | 序列化框架 |
| `serde_json` | 1 | JSON |
| `config` | 0.13 | 层级配置管理 |
| `dotenvy` | 0.15 | .env 加载 |
| `clap` | 4.x | CLI 参数 |

**并发/工具**
| Crate | 版本 | 用途 |
|-------|------|------|
| `dashmap` | 5 | 无锁并发 HashMap |
| `uuid` | 1.x（v4+serde） | ID 生成 |
| `chrono` | 0.4 | 时间处理 |
| `validator` | 0.16 | 请求校验（derive） |
| `thiserror` | 1 | 错误定义 |
| `anyhow` | 1 | 错误传播 |
| `tracing` | 0.1 | 结构化日志 |
| `tracing-subscriber` | 0.3 | 日志订阅（env-filter + JSON） |

### Release 配置

```toml
[profile.release]
opt-level = 3
lto = "fat"
codegen-units = 1
panic = "abort"
strip = "symbols"
```

---

## 二、Hypervisor 层 — 虚拟化核心

基于 **Cloud Hypervisor** fork（`cube-hypervisor` v28.0.0），含 ~30 个 crate 的 workspace。与 Firecracker、crosvm 共享 rust-vmm 生态。

### VMM 核心 crate

| Crate | 用途 | 上游 |
|-------|------|------|
| `kvm-bindings` 0.8.1 | KVM API Rust 绑定 | rust-vmm |
| `kvm-ioctls` 0.17 | KVM ioctl 安全封装 | rust-vmm |
| `vm-memory` 0.14.1 | Guest 内存抽象（mmap + atomic 后端） | rust-vmm |
| `vmm-sys-util` 0.12.1 | eventfd、timerfd、seccomp 等系统工具 | rust-vmm |
| `vfio-ioctls` | VFIO 设备直通 | rust-vmm/vfio |
| `vfio-bindings` 0.3.1 | VFIO 内核接口绑定 | - |
| `linux-loader` 0.13 | ELF/bzImage/PE 内核加载 | rust-vmm |
| `virtio-queue` 0.14 | virtio 队列抽象 | rust-vmm |
| `seccompiler` 0.3.0 | seccomp BPF 过滤器编译 | rust-vmm |

**可选后端**：支持 Microsoft Hyper-V（`mshv-bindings`/`mshv-ioctls` v0.2）和 Intel TDX。

### 设备模拟 crate

| Crate | 路径 | 用途 |
|-------|------|------|
| `devices` | `devices/` | virtio 设备管理（virtio-blk/net/console/fs 等） |
| `pci` | `pci/` | PCI 总线模拟 + VFIO 透传 |
| `vm-allocator` | `vm-allocator/` | 地址空间分配 |
| `vm-device` | `vm-device/` | 设备抽象层 |
| `vm-virtio` | `vm-virtio/` | virtio 设备框架 |
| `tpm` | `tpm/` | TPM 设备模拟 |
| `acpi_tables` | `acpi_tables/` | ACPI 表生成 |
| `arch` | `arch/` | 架构特定代码（x86_64 + aarch64） |
| `vm-migration` | `vm-migration/` | 热迁移支持 |
| `event_monitor` | `event_monitor/` | 事件监控 |
| `event_notifier` | `event_notifier/` | 事件通知 |

**关键依赖**：`phf` 0.11（编译期完美哈希表，设备查找），`bitflags` 2.6，`iced-x86` 1.17（x86 指令解码器，x86_64 only）。

### 设备后端 crate

| Crate | 用途 |
|-------|------|
| `virtiofsd` | virtio-fs 守护进程（文件系统共享） |
| `vhost_user_block` | vhost-user 块设备 |
| `vhost_user_net` | vhost-user 网络设备 |
| `qcow` | QCOW2 镜像支持 |
| `vhdx` | VHDX 镜像支持 |
| `rate_limiter` | IO 速率限制 |
| `block_util` / `net_util` | 块/网络工具 |

### 架构支持（ARM64）

| Crate | 用途 |
|-------|------|
| `vm-fdt` | ARM64 设备树（FDT）生成 | rust-vmm |
| `fdt` 0.1.4 | ARM64 FDT 解析（aarch64 only） |

### Workspace 全局依赖

在 workspace `Cargo.toml` 中统一管理版本：

```toml
[workspace.dependencies]
linux-loader = "0.13.0"
seccompiler = "0.3.0"
serde = "1.0.208"
vm-memory = "0.16.1"
vmm-sys-util = "0.12.1"
virtio-queue = "0.14.0"
# VFIO/vhost 使用 git 依赖（锁定到特定 rev）：
vfio-ioctls = { git = "https://github.com/rust-vmm/vfio", rev = "64171f3" }
vhost = { git = "https://github.com/rust-vmm/vhost", rev = "d983ae0" }
```

### MSRV 约束

```toml
rust-version = "1.77.0"  # hypervisor/hypervisor/Cargo.toml
```

实际约束来自 CubeShim 的 `rust-toolchain.toml = "1.77.2"`。`time 0.3.47` 因启用 `edition2024`（需 Rust ≥1.85）被回退到 `0.3.36`（见 [PR #286](https://github.com/TencentCloud/CubeSandbox/pull/286)）。

---

## 三、CubeShim — Containerd 集成层

独立的 workspace，含 3 个 crate：`shim`、`protoc`、`cube-runtime`。实现 containerd Shim v2 接口，将 MicroVM 接入容器运行时生态。

### 依赖清单

**containerd 协议**
| Crate | 版本 | 用途 |
|-------|------|------|
| `containerd-shim` | 0.9 | Shim v2 API |
| `containerd-shim-protos` | 0.9 | protobuf 定义 |
| `ttrpc` | 0.5.8 | TTRPC 协议（containerd 的 gRPC 变体） |
| `oci-spec` | 0.6.8 | OCI 运行时规范 |
| `protobuf` | 3.7 | protobuf 运行时 |

**Hypervisor 桥接**
| Crate | 版本 | 用途 |
|-------|------|------|
| `cube-hypervisor` | path = `../../hypervisor` | **直接依赖整个 hypervisor workspace** |

**系统调用**
| Crate | 版本 | 用途 |
|-------|------|------|
| `nix` | 0.29 | Unix 系统调用安全封装 |
| `kvm-bindings` | 0.8.1 | KVM API 直接访问 |
| `libc` | 0.2.158 | libc 绑定 |

**网络通信**
| Crate | 版本 | 用途 |
|-------|------|------|
| `hyper` | 1.x | HTTP 客户端（vsock 通信） |
| `hyper-util` | 0.1 | HTTP 工具 |
| `http-body-util` | 0.1 | HTTP body 处理 |

**基础工具**
| Crate | 版本 | 用途 |
|-------|------|------|
| `tokio` | 1.40（workspace） | 异步运行时 |
| `clap` | 4.5.20（workspace） | CLI 参数 |
| `serde` | 1.0.209 | 序列化 |
| `serde_json` | 1.0.128 | JSON |
| `chrono` | 0.4.38 | 时间 |
| `uuid` | 1.0（v4） | UUID |
| `time` | 0.3.36 | 时间格式化（仅 Rfc3339，不涉及 CVE-2026-25727 的 Rfc2822 路径） |
| `lazy_static` | 1.5 | 惰性初始化 |
| `home` | 0.5.9 | 用户目录 |

---

## 四、CubeCoW — Copy-on-Write 存储引擎

独立的 Cargo 项目，基于 XFS `FICLONE` ioctl 实现 O(1) 快照/克隆。构建产物同时输出 `lib` + `cdylib` + `staticlib`，供 Go 组件（Cubelet）通过 CGO 调用。

### 依赖清单

| Crate | 版本 | 用途 |
|-------|------|------|
| `libc` | 0.2 | `ioctl(fd, FICLONE, ...)` 系统调用 |
| `serde` | 1.x | 序列化 |
| `serde_json` | 1 | FFI JSON 输出 |
| `toml` | 0.8 | 配置解析 |
| `dashmap` | 6 | 并发元数据索引 |
| `uuid` | 1.x（v4） | 快照 ID 生成 |
| `chrono` | 0.4 | 快照时间戳 |
| `tracing` | 0.1 | 结构化日志 |
| `tracing-subscriber` | 0.3 | 日志订阅（JSON + env-filter） |
| `tracing-appender` | 0.2 | 日志文件滚动 |
| `thiserror` | 2 | 错误类型定义 |
| `anyhow` | 1 | 错误传播 |

### 设计特点

- **Flat Snapshot Model**：删除一个快照不影响其他快照（各自 `unlink`）
- **增量脏页跟踪**：快照仅保存匿名脏页，未修改页通过 reflink 共享
- **零数据拷贝**：`FICLONE` 是元数据级操作，不涉及实际数据搬运

### Benchmarks

自带手动编写的 benchmark（不使用 `criterion`，避免依赖膨胀），需要 root + XFS loop 挂载：

```bash
sudo cargo bench --bench reflink_ops
```

覆盖场景：单源串行展开、链式快照、多 worker 并发展开、脏 IO 交错快照（抖动检测）。

---

## 五、Agent — Guest 内代理

基于 **Kata Containers** agent fork 的 workspace，含 3 个 crate：`cube-agent`、`rustjail`、`cube`。运行在沙箱 Guest VM 内部，通过 vsock 与 CubeShim 通信。

### 依赖清单

**异步运行时 & 通信**
| Crate | 版本 | 用途 |
|-------|------|------|
| `tokio` | 1.45 | 异步运行时 |
| `tokio-vsock` | 0.7 | vsock 通信 |
| `ttrpc` | 0.8.4 | TTRPC 协议 |
| `protobuf` | 3.7 | protobuf 运行时 |
| `futures` | 0.3 | async 组合子 |
| `async-trait` | 0.1.42 | trait async fn |

**容器管理**
| Crate | 版本 | 用途 |
|-------|------|------|
| `rustjail` | 内部 | OCI 容器 jail（Kata Containers fork） |
| `oci` | 内部 | OCI spec 解析 |
| `cgroups-rs` | 0.3 | cgroup v1/v2 资源控制 |
| `nix` | 0.23 | Unix 系统调用 |

**网络**
| Crate | 版本 | 用途 |
|-------|------|------|
| `rtnetlink` | 0.14 | netlink 路由操作 |
| `netlink-packet-route` | 0.19 | 路由报文处理 |
| `netlink-packet-core` | 0.7 | netlink 核心 |
| `netlink-packet-utils` | 0.4 | netlink 工具 |
| `ipnetwork` | 0.17 | IP 网络类型 |

**监控**
| Crate | 版本 | 用途 |
|-------|------|------|
| `prometheus` | 0.14 | Metrics 暴露 |
| `procfs` | 0.12 | /proc 文件系统解析 |
| `sysinfo` | 0.23 | 系统信息 |
| `tracing-opentelemetry` | 0.13 | OTLP 导出 |
| `opentelemetry` | 0.14 | 分布式追踪 |

**基础工具**
| Crate | 版本 | 用途 |
|-------|------|------|
| `serde` | 1.0.129 | 序列化 |
| `serde_json` | 1.0.39 | JSON |
| `toml` | 0.5.8 | 配置 |
| `clap` | 3.0 | CLI |
| `slog` + `slog-scope` | 2.5/4.1 | 结构化日志 |
| `thiserror` | 1.0 | 错误 |
| `anyhow` | 1.0 | 错误传播 |
| `capctl` | 0.2 | capability 控制 |
| `libc` | 0.2.160 | libc 绑定 |
| `scopeguard` | 1.0 | RAII guard |
| `regex` | 1.5 | 正则 |
| `base64` | 0.22 | Base64 编解码 |
| `time` | 0.3.41 | 时间处理 |
| `x86_64` | 0.14 | x86 架构特定操作（CPUID/MSR/端口 IO，仅 x86_64） |

---

## 六、关键 Crate 家族与生态关系

### rust-vmm 生态

CubeSandbox 的虚拟化能力几乎完全建立在 `rust-vmm` 组织的 crate 之上，与 Firecracker、crosvm 共享同一套底层库。这是 Rust 在虚拟化领域的标准基础设施。

### Cloud Hypervisor fork

Hypervisor workspace 是 Cloud Hypervisor 的深度定制 fork：
- 自定义 `CubeHypervisor` VMM 实现
- `CubeShim` 通过 `lib_support` feature 将其作为库链接
- 保留了上游的 MSRV 约束和 CI 兼容性

### Kata Containers 继承

Agent workspace 基于 Kata Containers 的 agent 组件 fork：
- 继承了 `rustjail`（OCI 容器 jail）、`oci`（OCI spec 解析）
- 保留了完整的 cgroup 管理和容器生命周期能力

### FFI 桥接设计

CubeCoW 同时编译为 `cdylib` + `staticlib`，供 Go 的 Cubelet 通过 CGO 直接调用，避免进程间通信开销。

---

## 七、对鲲鹏/Rust 生态的启示

### 1. rust-vmm 生态的 ARM64 成熟度

CubeSandbox 在 v0.5 中实现了 ARM64 全栈支持（hypervisor、shim、agent、eBPF 网络），说明 rust-vmm 生态的 ARM64 支持已经达到生产可用水平。这对鲲鹏 Rust 虚拟化场景是积极信号。

### 2. 虚拟化基础设施的 Rust 化趋势

从 Firecracker → Cloud Hypervisor → CubeSandbox，MicroVM 领域正在从 C/QEMU 向 Rust 迁移。鲲鹏可以考虑：
- 为 rust-vmm 的 ARM64 后端贡献鲲鹏特定优化
- 在 `vm-memory`、`kvm-ioctls` 等基础 crate 中验证鲲鹏性能

### 3. MSRV 锁定的影响

项目因为 `time` crate 的 `edition2024` 被迫将 Rust 工具链锁在 1.77。类似问题在鲲鹏 Rust 工具链建设中也需注意——如果使用较新的 Rust 特性，需确保 MSRV 策略和下游兼容性。

### 4. FFI 跨语言调用模式

CubeCoW 的 `cdylib` + `staticlib` 模式是 Rust 服务 Go 生态的典型实践。鲲鹏的 KML（Kunpeng Math Library）Rust 绑定可参考这种设计：编译为 FFI 库供 C/Python/Go 多方调用。

### 5. 参考价值

CubeSandbox 是 Rust 在**高性能基础设施**领域的大型开源实践案例（~48% Rust、~30 crate、多 workspace 架构），其工程组织、依赖管理、MSRV 约束策略、FFI 设计等对鲲鹏 Rust 项目有直接参考意义。
