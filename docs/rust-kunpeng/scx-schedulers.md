# sched_ext (scx) 调度器全景分析

> 分析对象：[sched-ext/scx](https://github.com/sched-ext/scx) 仓库（2026-08 快照）
> 内核要求：Linux 6.12+，`CONFIG_SCHED_CLASS_EXT=y`

## 1. 背景

`sched_ext`（scx = sched + ext，可扩展调度器类）是 Linux 6.12 合入主线的内核特性，允许用 **BPF 程序实现 CPU 调度器并动态加载**。`sched-ext/scx` 是其官方用户态仓库：所有调度器均采用 **Rust 用户态（生命周期管理、CLI、监控）+ C/BPF 内核态（调度决策热路径）** 的架构。

C 语言示例调度器（scx_simple、scx_qmap 等）已移出本仓库，权威版本在内核树 `tools/sched_ext`，镜像在 [scx-c-examples](https://github.com/sched-ext/scx-c-examples)。

## 2. 总览

| 调度器 | 核心策略 | 目标负载 | 生产就绪 | 一句话特点 |
|---|---|---|---|---|
| **scx_bpfland** | 优先级调度（主要消费吞吐/延迟） | 延迟敏感、通用 | ✅ 是 | 按任务性质分类并分配优先级 |
| **scx_lavd** | 延迟关键性感知虚拟截止时间 | 游戏、延迟敏感、服务器 | ✅ 是 | Valve Steam Deck 出身，Meta 新默认机群调度器 |
| **scx_rusty** | vtime + NUMA 感知负载均衡 | 通用多 NUMA 服务器 | ✅ 是 | 最早的 Rust 参考实现，带能耗偏好 |
| **scx_layered** | 分层 + CPU 分配 | 大型线上服务（Meta） | ✅ 是 | 按 cgroup/进程匹配分层，典型案例研究 |
| **scx_rustland** | 用户态 Rust 决策 | 灵活性优先 | ✅ 是 | 绝大多数调度决策在用户态完成 |



| **scx_beerland** | 每核 deadline 队列 + 局部性 | 缓存密集、多核大系统 | ✅ 是 | 非饱和期零迁移，饱和期拉最小 deadline |
| **scx_p2dq** | pick-2 负载均衡 + 多层队列 | 通用、游戏、大小核 | ✅ 是 | 支持 BPF arena，Meta 实测 ≈ EEVDF |
| **scx_flash** | EDF + 动态延迟权重 | 多媒体、实时音频 | ✅ 是 | 提前让出 CPU 的任务获得更高优先级 |
| **scx_cake** | 帧感知 + 中断感知 + vtime | 游戏 | ✅ 是 | 零可调参数、零每任务状态，可半天审完 |
| **scx_mitosis** | cgroup 单元隔离（cells） | 数据中心超售 | ⚠️ 演进中 | 每个 cgroup 子组独占 CPU 集 |
| **scx_tickless** | primary CPU 池 + 无限时间片 | 云/虚拟化/HPC | ❌ 实验 | 把调度噪音隔离到少数核，其余无 tick |
| **scx_pandemonium** | 分层 + 阻尼谐振子 + 电阻亲和 | 交互/延迟敏感 | ⚠️ 新 | 混沌理论自适应，实测 p99 大幅优于 EEVDF |
| **scx_chaos** | 故意制造混乱 | 测试/调试 | ❌ 禁用生产 | 暴露 race condition 的混沌工程工具 |
| **scx_forge** | 可定制基础策略 | AI 调度器开发 | ❌ 基座 | 供 scx_forge_agent 就地演化策略 |
| *experimental/* | scx_flow / scx_mlfq / scx_rlfifo | 实验 | ❌ | 多级反馈队列、限速 FIFO 等原型 |

## 3. 分组详解

### 3.1 通用生产级

#### scx_bpfland — 优先级调度

- **开发者**：Andrea Righi（Canonical）
- **策略**：按任务性质（交互式/批处理等）分类，分配不同优先级和调度域；拓扑感知（LLC/SMT）；支持抢占
- **适用**：延迟敏感负载与批处理混合的系统
- **监控**：`scx_bpfland --monitor 0.5` 可实时查看任务运行/派发统计

#### scx_lavd — 延迟关键性感知虚拟截止时间

- **开发者**：Igalia（Changwoo Min），Valve 委托
- **策略**：启发式估计任务"延迟关键性"，关键任务获得更早的虚拟截止时间（deadline），从而被优先派发
- **战绩**：Steam Deck 默认调度器之一（CachyOS Handheld、Bazzite 采用）；**Meta 在 LPC 2025 宣布将其作为服务器机群"新默认调度器"**（替代内部 layered 配置作为通用兜底）
- **适用**：游戏、交互式桌面、对延迟敏感的大规模服务器

#### scx_rusty — NUMA 感知负载均衡

- **策略**：vtime 公平 + 调度域（domain）负载均衡，域间迁移按成本权衡；支持能耗偏好（performance/powersave）
- **地位**：scx 仓库最早的 Rust 参考实现之一，架构模板被后续调度器广泛借鉴
- **适用**：多 NUMA 节点服务器、混合负载

#### scx_cosmos — 局部性优先的自适应调度

- **策略**：**不饱和时**任务留在本地 DSQ（保缓存局部性、降锁竞争、扩展性好）；**饱和时**切换为 deadline 策略 + 共享 DSQ（NUMA 感知则 per-node DSQ），让交互任务优先于 CPU 密集任务
- **技巧**：用 BPF 定时器批量推迟 CPU 唤醒，降低入队开销，从而能用 **10µs 超短时间片** 提升响应性
- **适用**：服务器与桌面通吃

#### scx_beerland — 局部性与可扩展性优先

- **策略**：每 CPU 一个 deadline 排序 DSQ；**非饱和**时任务只在唤醒时迁移；**饱和**时 CPU 从远端 DSQ 拉取 deadline 最小的任务
- **适用**：缓存密集负载、大规模 CPU 系统

#### scx_flash — EDF + 动态延迟权重

- **策略**：最早截止时间优先（EDF），每个任务有"延迟权重"，**提前让出 CPU**（未用完时间片即阻塞）的任务权重上调，优先于吃满时间片的 CPU 密集任务
- **适用**：多媒体、实时音频等对延迟一致性要求高的负载，超售系统表现稳定

#### scx_p2dq — pick-2 负载均衡 + 多层队列

- **策略**：每个 LLC 三层队列（LLC DSQ / 每 CPU DSQ / 迁移 mig_dsq）；CPU 空闲时按 vtime 找最优任务；找不到则 **pick-2**：随机选两个 LLC 比较负载，从较忙者拉迁移任务
- **特性**：大核/小核调度模式（`--sched-mode`）、游戏调优参数丰富（`--autoslice`/`--cpu-priority`/`--freq-control`）、基于 BPF arena 的任务跟踪
- **战绩**：Meta 内部多服务测试，性能与 EEVDF 相当、零事故；scx_chaos 的基础
- **注意**：100% 饱和场景开销偏大；不支持热插拔；无 cgroup 带宽节流

### 3.2 特定场景

#### scx_layered — 分层调度（Meta 案例）

- **策略**：任务按匹配规则（cgroup、进程名等）分入 layer，每个 layer 有 CPU 分配策略：
  - **Confined**：限制在分配 CPU 内
  - **Grouped**：有分配额度，空闲可溢出
  - **Open**：可运行于任意 CPU
- **战绩**：官方 case study（`case-studies/scx_layered.md`）——Meta 最大 web 负载之一，两周写调度器 + 一周生产调优，吞吐 +5%；生产部署的广告调度策略（p99 -28%、省电 3.28MW）即分层思想
- **适用**：明确知道哪些线程在关键路径的大型服务

#### scx_rustland — 用户态调度

- **策略**：内核只留极薄的 BPF 转发层，任务派发到用户态 Rust 进程做决策（选任务、算优先级、时间片），再回写内核
- **代价**：用户态往返延迟（微秒级），换取**无限灵活性**（可用任意复杂算法、日志、ML 模型）
- **适用**：快速原型、复杂策略实验、教学

#### scx_cake — 为游戏而生的极简调度器

- **命名**：致敬网络 CAKE 队列管理（治 bufferbloat）：队列短、关键流量有天然快路径、其余公平共享
- **设计哲学**：**零每任务状态、零可调参数**，一个算法小到半天审完；二进制无参数（`-v`/`-V` 之外什么都没有）
- **核心机制**：
  - **帧时钟**：从显示刷新率实测（60/144/240Hz/VRR 自适应），时间片上限对齐帧
  - **中断感知放置（sink 检测）**：识别内核把设备中断（GPU/NVMe/网卡）导向的"沉没核"，三级时间尺度否决（均值/即时/tick 前瞻）
  - **缓存热核优先**：渲染线程优先回自己的旧核而非全新空闲核
  - 公平性来自按 nice 加权的 vtime
- **适用**：游戏、低输入延迟场景

#### scx_mitosis — cgroup 单元隔离

- **策略**：`--cell-parent-cgroup` 的直接子 cgroup 各得一个 cell（独立 CPU 集 + 共享 DSQ）；cell 内用加权 vtime；CPU 固定任务走 per-CPU 队列；可开启 LLC 感知
- **目标**：数据中心服务器安全超售
- **适用**：容器/工作负载隔离

#### scx_tickless — 无 tick 服务器调度

- **策略**：所有唤醒路由到 primary CPU 池（默认最慢 1 核），由 **BPF 定时器**统一派发到空闲 tickless CPU；tickless CPU 上任务拿**无限时间片**静默运行，仅在检测到竞争时按需开启抢占
- **要求**：内核启动参数 `nohz_full`
- **适用**：云/虚拟化/HPC，减少 OS 噪音；不适合延迟敏感负载

### 3.3 工具与教学

#### scx_chaos — 混沌工程调度器

- **基于**：scx_p2dq
- **特性**：随机延迟、CPU 频率随机缩放、性能分数降级、kprobe 注入延迟（最危险）
- **用途**：暴露应用 race condition 与时间敏感 bug；可限定目标进程、失败/成功自动重启、CI 集成
- **警告**：刻意降低性能，禁止生产使用

#### scx_forge — AI 调度器开发基座

- **用途**：为 `scx_forge_agent`（LLM 驱动的调度器优化器）提供完整可构建的起点：默认策略为 per-CPU DSQ + 工作窃取 + vtime 排序
- **工作流**：agent 就地修改策略 → 构建 → 挂载 → 跑负载 → 提取指标 → 保留/回退

#### scx_pandemonium — 混沌理论自适应调度器

- **策略亮点**：
  - 任务按调度角色分三层（LAT_CRITICAL / INTERACTIVE / BATCH）
  - **阻尼谐振子**实现 CoDel 风格停滞检测（RFC 8289 sojourn 指标）
  - **电阻亲和**：CPU 拓扑建模为电路图，拉普拉斯伪逆求有效电阻 R_eff，指导放置
  - **迁移势 Φ = R_eff − β·sojourn**：跨缓存边界迁移只在"队列收益 > 缓存代价"时发生
  - Rust 自适应控制环：混沌信号（HVG 度、排列熵、RQA 确定性）实时推导所有旋钮
- **实测**（12C AMD，vs EEVDF）：唤醒 p99 降 2~30 倍，deadline miss 率 12% → 0.2%；但 fork/exec 风暴迁移数 ×15.7、IPC 配对尾延迟弱于 EEVDF
- **适用**：交互式/延迟敏感负载；IPC 密集负载慎用

### 3.4 实验性（experimental/）

| 调度器 | 说明 |
|---|---|
| scx_mlfq | 多级反馈队列（经典 OS 算法）原型 |
| scx_rlfifo | 限速 FIFO |
| scx_flow | 流/数据流导向原型 |

⚠️ 实验目录不推荐生产使用。

## 4. 共同架构特点

1. **双层结构**：Rust 用户态（加载/CLI/监控/拓扑）+ C BPF 内核态（`struct sched_ext_ops` 回调：select_cpu/enqueue/dispatch/running/stopping/tick）
2. **DSQ（派发队列）是核心原语**：每 CPU 本地队列 + 自定义共享队列，调度器本质是"把任务放进对的队列、按对的顺序取出"
3. **公平性双主流**：vtime（加权虚拟时间）vs deadline（虚拟截止时间），多数调度器二选一或组合
4. **安全兜底**：watchdog（默认 30s）+ SysRq-S + 进程退出，任何故障自动回退 EEVDF
5. **共享库**：`rust/scx_utils`（拓扑/Cpumask/统计）+ `lib/*.bpf.c`（btree/rbtree/topology/ravg/cgroup_bw 等 BPF 侧通用组件）

## 5. 选型指南

| 场景 | 推荐 |
|---|---|
| 桌面/通用（不确定选什么） | scx_bpfland 或 scx_cosmos |
| 游戏 / 低输入延迟 | scx_lavd（成熟）或 scx_cake（激进极简） |
| 多 NUMA 服务器 | scx_rusty |
| 明确关键路径的线上服务 | scx_layered（自配 layer） |
| 云/虚拟化/HPC 降噪 | scx_tickless（需 nohz_full） |
| 交互与批处理混合、追求极限 p99 | scx_pandemonium（IPC 密集慎用） |
| 缓存密集 / 超多核 | scx_beerland |
| 容器超售隔离 | scx_mitosis |
| 快速原型 / 复杂策略 | scx_rustland |
| 压测找 race condition | scx_chaos |
| AI 调度器研究 | scx_forge + scx_forge_agent |
| 学习 sched_ext 入门 | 内核树 tools/sched_ext 的 scx_simple（最小示例） |

## 6. 参考

- [sched-ext/scx 仓库](https://github.com/sched-ext/scx)
- [sched_ext 内核文档](https://docs.kernel.org/scheduler/sched-ext.html)
- [Meta 广告服务 sched_ext 实践](https://engineering.fb.com/2026/07/13/ml-applications/modernizing-the-meta-ads-service-with-an-open-source-kernel-scheduler/)
- [Meta × scx_lavd（LPC 2025）](https://www.phoronix.com/news/Meta-SCX-LAVD-Steam-Deck-Server)
