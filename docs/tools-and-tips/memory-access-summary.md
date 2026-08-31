# 内存访问性能：两篇经典文献内容总结

---

- [The Myth of RAM, part IV](https://www.ilikebigbits.com/2015_02_09_myth_of_ram_4.html) — Emil Ernerfeldt, 2015
- [What Every Programmer Should Know About Memory](https://akkadia.org/drepper/cpumemory.pdf) — Ulrich Drepper (Red Hat), 2007, v1.0, 114 页

两份资料从不同角度讲同一件事——**内存层次结构决定真实性能**。

---

## 一、The Myth of RAM

这是「The Myth of RAM」系列的第四篇，专门回答 Reddit/HN 上对前三篇的误解与批评。

### 1. 系列核心论点

**「随机内存访问是 O(1)」是错误的，实际上每次随机访问的耗时是 O(√N)**，其中 N 是算法常规访问的内存量。

- **Part I（实证）**：作者用打乱指针的链表遍历基准（GitHub: `emilk/ram_bench`）测量从 64 个节点到 4.2 亿个节点的随机访问延迟。对数坐标图显示：数据在 L1 内约 1ns/次，落到内存/SSD 后升至 1μs/次。曲线呈阶梯状——每增加 100 倍内存用量，延迟上升约 10 倍（即 √N 规律），与 L1=32KiB、L2=256KiB、L3=4MiB、RAM=6GiB 的缓存边界精确吻合。蓝色 √N 曲线拟合极好。
- **Part II（理论）**：用物理定律（光速限制 + Bekenstein bound）论证 O(√N) 是任何存储介质的物理下限，与具体硬件无关。
- **Part III（推论）**：探讨该结论对算法设计的影响。
- **Part IV（本文，FAQ）**：澄清概念。

### 2. Part IV 要点（FAQ）

| 问题 | 回答 |
|------|------|
| "RAM"指什么？ | 指**随机内存访问**，不特指某种硬件。标题应为「恒定时间内随机访问内存的神话」 |
| 什么是"随机访问"？ | 不可预测、能击败任何预取器（prefetcher）的访问；线性访问不算随机 |
| N 是什么？ | 算法常规访问的内存量，每次访问代价为 k√N |
| 是否硬件相关？ | 否。扑克牌类比：牌少可单手拿，牌多铺满桌子→房间→城市，取牌时间随牌数 N 以 √N 增长（二维平面展开导致） |
| Big-O 不是关于时间的？ | Big-O 是数学工具，可以分析**时间**而不只是指令数。关心执行速度/耗电时，分析时间更有用——现代 CPU 等待内存时只是在浪费时间和电量 |
| "RAM 是 O(1)，缓存只是掩盖" | 若数据装不进 RAM 就要换页到 SSD/HDD/远程存储，延迟继续上升——O(√N) 适用于**任意规模** |
| "我只关心能装进 RAM 的问题" | 反例：声称一个「对十亿以内任何元素都是常数时间」的排序算法是 O(1)——有界问题不能套用 Big-O |
| Bekenstein bound 与黑洞 | 为避免黑洞时间膨胀，应把存储放在空心球壳上；量子纠缠不能传信息，帮不上忙 |

**核心信息**：哈希表查找是 O(√N) 而非 O(1)，链表遍历是 O(N√N) 而非 O(N)——当 CPU 大量等待内存时，指令数复杂度会严重低估真实耗时。

---

## 二、What Every Programmer Should Know About Memory

系统程序员记忆子系统的经典「圣经」级文档，标题致敬 Goldberg 的浮点数论文。全文面向 **Linux 上的商品化硬件**。

### 1. 文档结构（9 章）

1. **Introduction** — CPU 速度远超内存，内存成为瓶颈；本文聚焦 CPU 缓存与内存控制器
2. **Commodity Hardware Today / RAM Types** — 硬件基础
3. **CPU Caches** — 核心章节
4. **Virtual Memory** — TLB 等
5. **NUMA Support** — 非一致内存访问
6. **What Programmers Can Do** — 实践建议（核心章节）
7. **Memory Performance Tools** — 剖析工具
8. **Upcoming Technology** — 未来展望（事务内存等）
9. 附录 — 基准代码（矩阵乘法等）

### 2. 各章要点

#### 第 2 章：RAM 类型

- **SRAM**：6 晶体管/位，快、贵、无需刷新 → 用作缓存
- **DRAM**：1 晶体管+电容/位，需周期刷新（recharging），访问分 **RAS/CAS/预充电** 阶段，随机访问开销大、顺序传输高效 → 由此催生了 64 字节缓存行
- 内存类型演进：FPM → EDO → **SDRAM/DDR**（利用突发传输匹配缓存行）

#### 第 3 章：CPU Caches（核心）

- **层次结构**：L1d/L1i（每核独立）→ L2 → L3（多核共享）；多核/超线程的缓存共享拓扑
- **缓存行（cache line）**：64 字节；地址拆分为 **Tag + Set + Offset** 三段
- **相联度（associativity）**：直接映射、全相联、组相联；直接映射的冲突失效是性能杀手
- **写入策略**：write-through vs write-back（dirty 位）；**write-combining** 缓冲
- **多处理器一致性**：**MESI 协议**（Modified/Exclusive/Shared/Invalid），缓存一致性与伪共享问题
- **实测数据**：缓存大小/步长对访问时间的影响图（3.3.2 节著名的阶梯图）
- **指令缓存**与自修改代码的代价

#### 第 4 章：虚拟内存

- 多级页表、**TLB**（Translation Lookaside Buffer）及其优化（大页/HugePage、页表布局）
- 虚拟化对内存的影响

#### 第 5 章：NUMA

- 本地内存 vs 远程内存的访问代价差异（NUMA factor）
- 拓扑：AMD Opteron 的 HyperTransport 超立方体互联、SGI Altix、IBM x445
- Linux 的 NUMA 支持：内存策略（绑定/优先/交错）、`numactl`、cpuset、显式优化 API

#### 第 6 章：程序员实践建议（最实用）

- **绕过缓存（non-temporal）**：`_mm_stream_si128` 等流式指令；大矩阵初始化用普通 store 会污染缓存，非临时写配合 write-combining 直接写内存（`memset` 大块即用此技术）；同一缓存行内的写入必须连续发出
- **缓存友好的访问**：矩阵按行主序遍历（i-j 顺序）；结构体字段按访问频率重排；避免 stride 等于缓存行倍数导致的缓存抖动
- **预取**：
  - 硬件预取：检测到 2+ 次连续 cache miss 才触发，支持步长识别，8-16 个独立流；**不能跨页边界**（4K 页限制，约 512 字节窗口）
  - 软件预取：`__builtin_prefetch`，用于硬件无法识别的模式
- **多线程**：伪共享（false sharing）→ 用 padding 隔离；原子操作的代价；带宽饱和问题
- **NUMA 编程**：内存策略 API、查询节点信息、把线程/内存绑定在同一节点

#### 第 7 章：工具

- oprofile 等剖析工具、**Valgrind cachegrind** 缓存模拟、内存用量测量、分支预测改进

#### 第 8 章：未来技术

- 原子操作在多核上的不可扩展性问题 → **事务内存（Transactional Memory）**，LL/SC 实现与总线协议
- 延迟上升趋势、向量操作（SSE 等）

---

## 三、两者的关联与价值

- **Myth of RAM** 是「挑衅性的理论框架」：把内存层次抽象为 O(√N)，从物理极限（光速、Bekenstein bound）论证随机访问延迟随数据规模增长是**不可避免的**，挑战教科书复杂度分析。
- **Drepper 的论文**是「工程实践手册」：详细解释为什么层次存在（DRAM 物理限制→缓存行→多级缓存→NUMA），并给出可操作的优化技术（非临时写、缓存行对齐、预取、MESI、NUMA 策略）。

互补关系：Drepper 解释了 Myth of RAM 图中那些「阶梯」从何而来；Myth of RAM 则回答了 Drepper 没有直接回答的问题——如果数据量持续增长，延迟曲线的**长期走向**是 √N 而非有界常数。
