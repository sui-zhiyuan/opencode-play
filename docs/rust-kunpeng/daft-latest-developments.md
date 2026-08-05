# Daft 项目最新动态

> 采集时间: 2026-08-05 | 来源: GitHub, eventual.ai, daft.ai

---

## 一、版本节奏

Daft 正处于高速迭代期，2026 年 5-8 月保持 ~2-4 天一个版本的发布频率。

| 版本 | 日期 | 核心主题 |
|------|------|---------|
| v0.7.22 | 2026-08-03 | 多湖格式扫描重构（Iceberg/Delta/Hudi → 统一 DataSource trait）、Gravitino REST Catalog、HDFS 支持、SQL CREATE TABLE |
| v0.7.21 | 2026-07-17 | Physical AI 示例（手部追踪 + 奖励评分 benchmark） |
| v0.7.20 | 2026-07-14 | Iceberg filter pushdown（starts_with/is_nan）、shuffle 后端枚举统一 |
| v0.7.19 | 2026-07-10 | MCAP 机器人数据格式支持、write_parquet single_file、GooseFS 文档 |
| v0.7.18 | 2026-07-08 | LeRobot 批量视频解码（按 shard）、双列字符串 FNV 分组加速、Delta Lake S3 免 DynamoDB |
| v0.7.17 | 2026-07-06 | LeRobot v3 数据集、HDF5 文件支持、本地 LLM 推理（Transformers provider）、分布式 ASOF aligned join |
| v0.7.16 | 2026-06-30 | DROID 机器人数据集 API、PyTorch DataLoader、ignore_corrupt_files、字符串距离函数 |
| v0.7.15 | 2026-06-07 | try_cast 安全类型转换、Flight Shuffle LZ4 默认压缩、UUIDv7、PostgreSQL via Gravitino |

---

## 二、2026 核心战略方向

### 2.1 性能（Performance）

| 子项 | 状态 | 关键 PR / 讨论 |
|------|------|---------------|
| **Arrow Flight Shuffle** | ✅ 已落地 | #6123 (初始实现) → #6519 (Rust 化) → #7071 (LZ4 默认压缩，EBS gp3 上 2.3x 加速) |
| 100TB 级大规模 Shuffle | 🚧 进行中 | #6472 (设计讨论) |
| 动态任务调度 + Worker 启动优化 | 🚧 进行中 | #6562 (Roadmap) |
| 内存管理（OOM 追踪/反压/动态批处理） | 🚧 进行中 | #6562 |
| Hash 算子优化（低基数 groupby/join） | 🚧 规划中 | #6562 |

**近期落地优化**:
- v0.7.22: repartition 迁移到共享后端，统一 pipeline 分发 (#7275)
- v0.7.18: 双列字符串 key pack 进 u64 做 FNV 分组 (#6924)
- v0.7.15: 多列 groupby 字符串符号化 (#6748)
- v0.7.15: Flight Shuffle coordinator 内存 O(map_tasks + partitions) (#7056)
- v0.7.14: shuffle 文件每 task 一个（代替 N 个分区文件）(#6948)
- v0.7.6: Swordfish 物理计划指纹缓存 (#6278)

### 2.2 关键特性（Key Features）

| 子项 | 状态 | 进展 |
|------|------|------|
| **Checkpointing** | 🚧 设计中 | #6446 讨论中，v0.7.15 加入分布式可观测计数器 (#7026) |
| **ASOF Join** | ✅ 基本完成 | v0.7.13 双向 ASOF（forward + backward）、v0.7.17 分布式 aligned 路径 |
| **Kubernetes 支持** | 🚧 设计中 | #6639 设计文档，Flight Shuffle 作为 Pod-to-Pod 数据平面 |
| **多分布式后端** | 🚧 进行中 | 通用 Worker/WorkerManager trait + 持续 Ray 支持 |

### 2.3 可观测性（Observability）

| 子项 | 状态 | 进展 |
|------|------|------|
| **Daft Dashboard** | 🚧 进行中 | v0.7.20 修复跨文件系统 OUT_DIR 支持 (#7246) |
| 结构化事件日志 (JSONL) | ✅ 已落地 | v0.7.6 per-query 目录 + 生命周期事件 |
| 内存/CPU 可观测 | ✅ 已落地 | v0.7.6 jemalloc 采样 + OS 进程指标 |
| 媒体文件读取追踪 | ✅ 已落地 | v0.7.22 trace media file reads (#7312) + video frame decoding (#7313) |

### 2.4 可扩展性（Extensibility）

| 子项 | 状态 | 进展 |
|------|------|------|
| **Arrow2 废弃** | 🚧 讨论中 | #5741，转向原生 arrow-rs |
| 数据源重构 | 🚧 大规模进行中 | v0.7.22: Iceberg/Hudi/Delta Lake 扫描全部迁移到统一 DataSource trait |
| 原生扩展 | ✅ 已落地 | v0.7.15 Ray 上原生扩展支持 + Arrow C 接口 |
| 社区扩展机制 | ✅ 已落地 | GooseFS、HDFS、MCAP 均由社区提交 |

---

## 三、Arrow Flight Shuffle 专题

### 3.1 架构演进时间线

| 时间 | 事件 | 链接 |
|------|------|------|
| 2025-10 | Flotilla 发布，Flight Shuffle 作为 Beta 特性 | [Introducing Flotilla](https://www.eventual.ai/blog/introducing-flotilla-simplifying-multimodal-data-processing-at-scale) |
| 2026-02-05 | 初始 PR 合入（+1258/-517 行，35 文件） | [#6123](https://github.com/Eventual-Inc/Daft/pull/6123) |
| 2026-03-24 | 正式设计讨论发布 | [#6472](https://github.com/Eventual-Inc/Daft/discussions/6472) |
| 2026-03-27 | Flight Server 从 Python 迁移到 Rust | [#6519](https://github.com/Eventual-Inc/Daft/pull/6519) |
| 2026-03-31 | 流式 Flight shuffle read 上线 | [#6269](https://github.com/Eventual-Inc/Daft/pull/6269) |
| 2026-04 | 本地磁盘直读、into_partitions/gather 实现、RandomShuffle 泛化 | #6436, #6764, #6751, #6808 |
| 2026-06-05 | **核心架构博客 "Disk is the data plane"** | [Blog](https://www.eventual.ai/blog/disk-is-the-data-plane) |
| 2026-06-07 | LZ4 默认压缩 + 可配置压缩算法 | [#6979](https://github.com/Eventual-Inc/Daft/pull/6979), [#7071](https://github.com/Eventual-Inc/Daft/pull/7071) |
| 2026-08-03 | Shuffle 后端统一重构 (repartition → 共享后端) | [#7275](https://github.com/Eventual-Inc/Daft/pull/7275) |

### 3.2 五大设计决策

1. **Disk is the data plane** — map task 直接写 Arrow IPC 到本地磁盘（不走 Ray object store）
2. **One file per mapper** — 每个 mapper 写一个合并的 Arrow IPC 文件（非 M×N 文件），含所有 reduce 分区的 byte range 索引
3. **Arrow Flight serves shuffle data** — 每个 worker 运行 Flight server，通过 `DoGet` 暴露分区数据
4. **Everything streams** — 数据以连续 Arrow IPC stream 走 disk → Flight → executor，不在内存中物化整个分区
5. **Metadata stays distributed** — reduce task 只持有轻量逻辑 PartitionRef（地址+shuffle_id+partition_idx），物理文件路径和 byte range 留在写数据的 worker 本地

### 3.3 性能数据

| 场景 | 数据 | 效果 |
|------|------|------|
| 1TB TPC-H repartition, 本地 NVMe | LZ4 vs 无压缩 | ~10% 加速 |
| 1TB TPC-H repartition, EBS gp3 | LZ4 vs 无压缩 | **~2.3x 加速** |
| Time-to-first-batch | 流式 vs 旧物化模式 | 从 "等整个分区" 降到 "等第一行" |

### 3.4 运维配置

```python
daft.set_execution_config(
    shuffle_algorithm="flight_shuffle",
    flight_shuffle_compression="lz4",      # "lz4" | "zstd" | "none"
    flight_shuffle_dirs=["/mnt/nvme0"],    # 指向最快本地磁盘，多盘可并行
)
```

---

## 四、Physical AI 方向（机器人数据管线）

这是 2026 年最大的战略转向——从通用 DataFrame 逐步聚焦机器人/AI 数据。

| 版本 | 能力 | 说明 |
|------|------|------|
| v0.7.16 | `daft.datasets.droid` | DROID 机器人数据集（7.6 万演示轨迹，8.7TB），含相机 extrinsics、自然语言标注 |
| v0.7.17 | `daft.datasets.lerobot` | LeRobot v3 数据集（HuggingFace 机器人学习标准格式），episode 元数据 + 传感器数据 + 视频帧自动 join |
| v0.7.17 | `daft.Hdf5File` | HDF5 原生支持（DROID 底层存储格式），typed accessors（hdf5_keys/metadata/attrs） |
| v0.7.17 | `prompt(provider="transformers")` | 本地 LLM 推理（HuggingFace pipeline），无 API key 依赖 |
| v0.7.17 | `df.to_torch_dataloader()` | 直接对接 PyTorch DataLoader，消除 Dataset wrapper 胶水代码 |
| v0.7.18 | LeRobot 批量视频解码优化 | 按 shard 批量解码，**15x 加速**（见[工程博客](https://www.eventual.ai/blog)） |
| v0.7.21 | Physical AI 示例 notebook | 手部追踪 + 奖励评分 UDF 的完整示例 |
| v0.7.22 | 媒体文件追踪 | trace media file reads + video frame decoding |

---

## 五、社区活跃度

### 5.1 贡献者增长（v0.7.15 - v0.7.22）

| 版本 | 新贡献者 | 社区 PR 亮点 |
|------|---------|-------------|
| v0.7.22 | @jiangxt2, @ihopenre-eng, @shreynath | Gravitino REST catalog (#7245)、HDFS (#7202)、SQL CREATE TABLE (#7186)、Delta/Hudi 扫描 DataSource 化 |
| v0.7.20 | @alejandro-soto-franco, @zhouwenjiajia | Dashboard OUT_DIR 跨文件系统、文件操作 GIL 释放 |
| v0.7.19 | @DieselZhang, @FANNG1, @AnayGarodia | MCAP 格式、write_parquet single_file、OSS write_lance 路由 |
| v0.7.17 | @lhoestq (HF datasets 维护者) | Common Crawl HuggingFace 镜像（免 AWS 账号访问） |
| v0.7.16 | @Liusixuuu, @nish2292 | daft.concat()、字符串距离/相似度函数 |
| v0.7.15 | @qingfeng-occ, @daiping8 | PostgreSQL via Gravitino、GCS delete |

### 5.2 核心维护者

| 维护者 | 主要领域 |
|--------|---------|
| @srilman | 机器人数据集（DROID/LeRobot）、HDF5、数据源重构、CI |
| @colin-ho | Flotilla 引擎、Flight Shuffle、Parquet reader 重写 |
| @everettVT | MCAP、HDF5、视频文件、Roadmap 管理 |
| @euanlimzx | ASOF joins（双向 + 分布式 + aligned）、窗口函数 |
| @jaychia | 分区、clustering spec、UUIDv7 |
| @rohitkulshreshtha | Checkpointing |
| @rchowell | 原生扩展、Gravitino catalog |
| @BABTUNA | inline aggregation、Spark 兼容函数、shuffle 后端重构 |

---

## 六、主要讨论与设计文档索引

| 讨论 | 链接 | 发起日期 | 说明 |
|------|------|---------|------|
| Arrow Flight for Distributed Shuffles | [#6472](https://github.com/Eventual-Inc/Daft/discussions/6472) | 2026-03-24 | Flight Shuffle 三阶段设计 |
| Daft 2026 Roadmap | [#6562](https://github.com/Eventual-Inc/Daft/discussions/6562) | 2026-03-31 | 年度路线图 |
| Observability Roadmap | [#6560](https://github.com/Eventual-Inc/Daft/discussions/6560) | 2026-03-31 | Dashboard/调试/内存可观测 |
| Design: Point-in-Time (AsOf) Joins | [#6498](https://github.com/Eventual-Inc/Daft/discussions/6498) | 2026-03-26 | ASOF 四阶段实现路径 |
| Design: Daft Native Kubernetes Support | [#6639](https://github.com/Eventual-Inc/Daft/discussions/6639) | 2026-04 | K8s 原生支持架构 |
| Checkpoint V2 — Design Proposal | [#6446](https://github.com/Eventual-Inc/Daft/discussions/6446) | 2026-03 | 长时间运行工作负载恢复 |
| New UDFs Roadmap | [Roadmaps](https://github.com/Eventual-Inc/Daft/discussions/categories/roadmaps) | — | UDF 路线图 |
| Arrow2 Deprecation | [#5741](https://github.com/Eventual-Inc/Daft/discussions/5741) | — | arrow2 → arrow-rs 迁移 |

---

## 七、对鲲鹏优化的关联分析

### 7.1 Flight Shuffle → NUMA 优化机会

v0.7.15 的 Flight Shuffle LZ4 压缩在 EBS gp3 上取得 2.3x 加速。在 Kunpeng 920B 上：
- 跨 socket shuffle 延迟 35-40（vs socket 内 12），LZ4 压缩可减少跨 socket 传输数据量
- 920B 有 CRC32 硬件加速，可探索压缩/解压路径的进一步收益

### 7.2 DataSource trait 重构 → UDF 注入点

v0.7.22 将 Iceberg/Delta/Hudi 扫描统一到 DataSource trait，扫描层做 ARM 优化（预取、向量化）有了单一注入点。

### 7.3 Physical AI 方向 → SVE/SVE2 加速

LeRobot/DROID 的视频解码和 tensor 列操作（相机 extrinsics 矩阵、传感器融合）在 SVE 256-bit 上有向量化空间。

### 7.4 Checkpointing → L3 Cache 利用

Checkpoint 设计涉及大量序列化/反序列化。920B 的 L3 cache partition 模式（Shared/Private/Partition 动态切换）可显著影响 checkpoint 性能，值得在设计评审中提出。

### 7.5 相关本地文档

- `daft-kunpeng-udf-inventory.md` — UDF 鲲鹏优化清单
- `daft-kunpeng-perf-design-spec.md` — 性能设计规格
- `daft-kunpeng-perf-design-input.md` — 性能设计输入
- `kunpeng-920b-specs.md` — 920B 硬件规格
