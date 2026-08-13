# CANN 8.3.RC1 昇腾社区在线文档索引（Ascend C 算子开发）

昇腾社区在线版 CANN 8.3.RC1 Community Edition《Ascend C 算子开发》文档集索引。
与本地笔记 [Ascend NPU 架构索引](./asc-devkit-arch-index.md)（基于 asc-devkit git 仓库）互为对照。

## 源文档信息

| 项 | 值 |
| --- | --- |
| 文档集 URL | `https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/83RC1/opdevg/Ascendcopdevg` |
| 页面 URL 模式 | `https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/83RC1/opdevg/Ascendcopdevg/{nodeHtml}` |
| 重点章节 | `atlas_ascendc_10_0008.html`（基本架构） |
| 站点 | 昇腾社区（hiascend.com），页面为服务端渲染，可直接抓取 |

### 目录树 API（重建索引用）

目录树由前端 JS 从网关动态加载，页面 HTML 里没有目录：

```
GET https://developer.hiascend.com/ascendgateway/ascendservice/doc/node/tree/zh/CANNCommunityEdition/83RC1/opdevg/Ascendcopdevg
（需带 Referer: https://www.hiascend.com/ 与 Origin: https://www.hiascend.com/）
```

返回 JSON：`data.directory[]` 递归含 `nodeName` / `nodeHtml` / `children`。

### 重要编号规则

页面编号有 **4 位和 5 位两套**，是不同页面，不可混淆：

- `atlas_ascendc_10_0009.html`（4 位）= 架构规格（索引页，301 重定向到 0010）
- `atlas_ascendc_10_00009.html`（5 位）= 尾块Tiling
- `atlas_ascendc_10_00027.html`（5 位）= NPU架构版本300x

### 重要发现：83RC1 社区版不含 NPU架构版本3510

架构规格章节在 83RC1 社区版中只有 3 页（200x / 220x / 300x），**没有 3510（Ascend 950）**。
且版本命名已改为 **IP 核编号方案**：

> "本节介绍 `__NPU_ARCH__` 版本号为 200x 的硬件架构……其中 200 代表 IP 核编号，x 表示同一个 IP 核的配置版本号。"

| 83RC1 在线命名 | 本地 asc-devkit 旧命名 | 对应产品 |
| --- | --- | --- |
| NPU架构版本200x | NPU架构版本2002 | Atlas 推理系列（310P） |
| NPU架构版本220x | NPU架构版本2201 | Atlas A2 / A3 |
| NPU架构版本300x | NPU架构版本3002 | Atlas 200I/500 A2 推理（310B） |
| （无此页） | NPU架构版本3510 | Ascend 950PR/950DT |

→ 3510 架构规格只存在于本地 [asc-devkit](https://gitcode.com/cann/asc-devkit) 仓库（`docs/zh/guide/编程指南/高级编程/硬件实现/架构规格/NPU架构版本3510.md`），详见 [Ascend NPU 架构索引](./asc-devkit-arch-index.md)。

## 文档集章节结构

URL 前缀：`https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/83RC1/opdevg/Ascendcopdevg/`

```
Ascend C算子开发
├── Ascend C简介                        atlas_ascendc_10_0001.html
├── 环境准备                            atlas_ascendc_10_0002.html
├── 快速入门                            atlas_ascendc_10_0003.html
│   ├── HelloWorld                      atlas_ascendc_10_0004.html
│   └── Add自定义算子开发               atlas_ascendc_10_0005.html
├── 抽象硬件架构                        atlas_ascendc_10_0015.html
├── 编程模型                            atlas_ascendc_10_0012.html
│   ├── 异构并行编程模型                atlas_ascendc_10_00028.html
│   ├── SPMD模型                        atlas_ascendc_10_0013.html
│   ├── 核函数                          atlas_ascendc_10_0014.html
│   ├── 编程范式                        atlas_ascendc_10_0016.html
│   │   ├── 基于TPipe和TQue的编程范式   atlas_ascendc_10_00032.html
│   │   │   └── 典型算子的编程范式      atlas_ascendc_10_00033.html
│   │   └── 静态Tensor编程范式          atlas_ascendc_10_00019.html
│   └── 编程接口概述                    atlas_ascendc_10_0018.html
├── 算子实现                            atlas_ascendc_10_0030.html
│   ├── 概述                            atlas_ascendc_10_0031.html
│   ├── 矢量编程                        atlas_ascendc_10_0032.html
│   │   ├── 概述                        atlas_ascendc_10_10001.html
│   │   ├── 基础矢量算子                atlas_ascendc_10_0033.html
│   │   ├── TBuf的使用                  atlas_ascendc_10_10003.html
│   │   ├── 多核&Tiling切分             atlas_ascendc_10_10004.html
│   │   │   ├── 概述                    atlas_ascendc_10_10005.html
│   │   │   ├── 多核Tiling              atlas_ascendc_10_0035.html
│   │   │   ├── 尾块Tiling              atlas_ascendc_10_00009.html  ← 5位编号
│   │   │   ├── 尾核Tiling              atlas_ascendc_10_10008.html
│   │   │   └── 尾核&尾块               atlas_ascendc_10_10009.html
│   │   ├── DoubleBuffer场景            atlas_ascendc_10_10010.html
│   │   ├── Broadcast场景               atlas_ascendc_10_10011.html
│   │   └── 非对齐场景                  atlas_ascendc_10_0034.html
│   ├── 矩阵编程（高阶API）             atlas_ascendc_10_0036.html
│   │   ├── 基础知识                    atlas_ascendc_10_0037.html
│   │   ├── 算子实现                    atlas_ascendc_10_0038.html
│   │   └── 特性场景                    atlas_ascendc_10_10025.html
│   │       ├── Matmul特性介绍          atlas_ascendc_10_10012.html
│   │       ├── 多核对齐切分            atlas_ascendc_10_10013.html
│   │       ├── 多核非对齐切分          atlas_ascendc_10_10014.html
│   │       ├── 异步场景处理            atlas_ascendc_10_10015.html
│   │       ├── 矩阵乘输出的量化/反量化 atlas_ascendc_10_10017.html
│   │       ├── 矩阵乘输出的Channel拆分 atlas_ascendc_10_10018.html
│   │       ├── 矩阵向量乘              atlas_ascendc_10_10019.html
│   │       ├── 4:2稀疏矩阵乘           atlas_ascendc_10_10021.html
│   │       ├── TSCM输入的矩阵乘        atlas_ascendc_10_10024.html
│   │       ├── 矩阵乘输出的N方向对齐   atlas_ascendc_10_10026.html
│   │       ├── 单次矩阵乘局部输出      atlas_ascendc_10_10027.html
│   │       ├── AIC和AIV独立运行机制    atlas_ascendc_10_10028.html
│   │       ├── Batch Matmul基础功能    atlas_ascendc_10_0041.html
│   │       └── Batch Matmul复用Bias矩阵 atlas_ascendc_10_10030.html
│   ├── 矩阵编程（基础API）             atlas_ascendc_10_0042.html
│   │   ├── 耦合模式                    atlas_ascendc_10_00006.html
│   │   └── 分离模式                    atlas_ascendc_10_00007.html
│   ├── 融合算子编程                    atlas_ascendc_10_0048.html
│   │   ├── CV融合                      atlas_ascendc_10_10031.html
│   │   └── 通算融合                    atlas_ascendc_10_10032.html
│   ├── Kernel直调算子开发              atlas_ascendc_10_0051.html
│   │   ├── 概述                        atlas_ascendc_10_0052.html
│   │   ├── Kernel直调                  atlas_ascendc_10_0056.html
│   │   └── Pybind调用                  atlas_ascendc_10_0057.html
│   └── 工程化算子开发                  atlas_ascendc_10_0058.html
│       ├── 概述                        atlas_ascendc_10_0059.html
│       ├── 创建算子工程                atlas_ascendc_10_0060.html
│       ├── 算子原型定义                atlas_ascendc_10_0062.html
│       ├── Kernel侧算子实现            atlas_ascendc_10_0063.html
│       ├── Host侧Tiling实现            atlas_ascendc_10_0064.html
│       │   ├── 基本流程                atlas_ascendc_10_00021.html
│       │   ├── 通过TilingData传递属性信息 atlas_ascendc_10_00022.html
│       │   ├── 使用高阶API时配套的Tiling实现 atlas_ascendc_10_00023.html
│       │   ├── 使用标准C++语法定义Tiling结构体 atlas_ascendc_10_00024.html
│       │   └── Tiling模板编程          atlas_ascendc_10_00025.html
│       ├── 算子包编译                  atlas_ascendc_10_00011.html
│       │   ├── 算子工程编译            atlas_ascendc_10_0068.html
│       │   └── 算子包部署              atlas_ascendc_10_0069.html
│       ├── 算子动态库和静态库编译      atlas_ascendc_10_00012.html
│       ├── 算子工程编译拓展            atlas_ascendc_10_00035.html
│       └── 单算子API调用               atlas_ascendc_10_0070.html
├── 算子编译                            atlas_ascendc_10_00036.html
│   ├── 算子编译简介                    atlas_ascendc_10_00041.html
│   ├── 通过bisheng命令行编译           atlas_ascendc_10_00037.html
│   ├── 常用的编译选项                  atlas_ascendc_10_00038.html
│   ├── 通过CMake编译                   atlas_ascendc_10_00039.html
│   └── RTC                             atlas_ascendc_10_00040.html
├── 算子调试调优                        atlas_ascendc_10_0071.html
│   ├── 孪生调试简介                    atlas_ascendc_10_0072.html
│   ├── CPU域调试                       atlas_ascendc_10_0073.html
│   └── NPU域调试调优                   atlas_ascendc_10_0075.html
├── 算子入图（GE图）开发                atlas_ascendc_10_0076.html
│   ├── 概述                            atlas_ascendc_10_0077.html
│   ├── 基本开发流程                    atlas_ascendc_10_0078.html
│   ├── 使能Tiling下沉                  atlas_ascendc_10_00014.html
│   ├── SuperKernel开发                 atlas_ascendc_10_00029.html
│   └── 图编译和图执行                  atlas_ascendc_10_0079.html
├── AI框架算子适配                      atlas_ascendc_10_0080.html
│   ├── 概述                            atlas_ascendc_10_0081.html
│   ├── PyTorch框架                     atlas_ascendc_10_0082.html
│   ├── ONNX框架                        atlas_ascendc_10_0085.html
│   │   ├── 适配插件开发                atlas_ascendc_10_0086.html
│   │   └── 调用样例                    atlas_ascendc_10_0087.html
│   └── TensorFlow框架                  atlas_ascendc_10_0088.html
├── 概念原理和术语                      atlas_ascendc_10_00017.html
│   ├── 术语表                          atlas_ascendc_10_00013.html
│   ├── 神经网络和算子                  atlas_ascendc_10_0097.html
│   │   ├── 算子基本概念                atlas_ascendc_10_0098.html
│   │   └── 数据排布格式                atlas_ascendc_10_0099.html
│   ├── 硬件架构与数据处理原理          atlas_ascendc_10_0007.html
│   │   ├── 基本架构                    atlas_ascendc_10_0008.html  ← 重点
│   │   └── 架构规格                    atlas_ascendc_10_0009.html  （重定向→0010）
│   │       ├── NPU架构版本200x         atlas_ascendc_10_0010.html  （≈本地2002）
│   │       ├── NPU架构版本220x         atlas_ascendc_10_0011.html  （≈本地2201）
│   │       └── NPU架构版本300x         atlas_ascendc_10_00027.html （≈本地3002，5位编号）
│   ├── 编程模型设计原理                atlas_ascendc_10_00015.html
│   ├── 内存访问原理                    atlas_ascendc_10_00030.html
│   │   └── Scalar读写数据              atlas_ascendc_10_00031.html
│   └── 性能优化技术原理                atlas_ascendc_10_00016.html
│       └── DoubleBuffer                atlas_ascendc_10_0090.html
├── 常用操作                            atlas_ascendc_10_0089.html
│   ├── 如何开发动态输入算子            atlas_ascendc_10_00005.html
│   ├── 如何在矢量编程时使能Vector Core atlas_ascendc_10_0100.html
│   ├── 如何使用Tensor高维切分计算API   atlas_ascendc_10_0022.html
│   ├── 如何使用归约指令                atlas_ascendc_10_0023.html
│   ├── 如何使用掩码操作API             atlas_ascendc_10_0024.html
│   ├── 如何使用workspace               atlas_ascendc_10_0092.html
│   ├── 如何进行Tiling调测              atlas_ascendc_10_00018.html
│   ├── 如何使用SPM Buffer              atlas_ascendc_10_0093.html
│   └── 如何使用Tensor原地操作提升算子性能 atlas_ascendc_10_00020.html
├── 附录                                atlas_ascendc_10_0096.html
│   ├── C++语言拓展                     atlas_ascendc_10_00026.html
│   ├── 简易自定义算子工程              atlas_ascendc_10_0101.html
│   ├── show_kernel_debug_data工具      atlas_ascendc_10_0102.html
│   └── msobjdump工具                   atlas_ascendc_10_0103.html
└── FAQ                                 atlas_ascendc_10_0105.html
    └── （0106~0112、00003、00004 共 10 页，见原树）
```

## 重点章节：基本架构（atlas_ascendc_10_0008.html）

页面 URL：`https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/83RC1/opdevg/Ascendcopdevg/atlas_ascendc_10_0008.html`

### 内容结构（按页面小节顺序）

| 小节 | 关键内容 | 页内锚点（深度链接） |
| --- | --- | --- |
| 概述 | AI Core 三组成：计算单元 / 存储单元 / 搬运单元 | - |
| 关键概念和术语 | Core、AI Core、Cube Core、Vector Core、AIC、AIV | - |
| AI Core的工作模式 | 分离模式 / 耦合模式 | `#ZH-CN_TOPIC_0000002446516602__li188191010204418`（分离模式） |
| 各产品工作模式 | 310P 耦合、910 耦合、A2/A3 分离、310B 仅耦合（Ascend C 场景） | - |
| 计算单元 | Cube（fp16 16x16 矩阵乘/拍）、Vector（SIMD、32B 对齐）、Scalar（ICache 16K/32K、DCache 16K、Cache Line 64B） | - |
| 存储单元和搬运单元 | 表1 存储单元（L1/L0A/L0B/L0C/UB/BT/FP）、表2 搬运单元（MTE1/MTE2/MTE3/FixPipe 职责与通路） | `#ZH-CN_TOPIC_0000002446516602__table1692510612218`（表1）、`#ZH-CN_TOPIC_0000002446516602__table288493152012`（表2） |
| 典型的数据流 | Vector：GM→UB→Vector→UB→GM；Cube：GM→L1→L0A/L0B→Cube→L0C→FixPipe→GM/L1 | - |
| 典型的指令流 | Scalar 直执行；其余入分类序列；PipeBarrier、SetFlag/WaitFlag 同步机制 | - |

### 本页与本地版差异

内容与本地 `asc-devkit/docs/zh/guide/编程指南/高级编程/硬件实现/基本架构.md` **几乎逐字一致**（同一文档的不同发布版本）。
差异点：

- 在线版工作模式列表**没有** "Ascend 950PR/950DT：分离模式" 条目（本地版有）；
- 在线版指令流小节**没有**提及各指令序列队列深度的具体链接段落（本地版含 2201/3510 队列深度链接）；
- 在线版以 Atlas A2 为例的架构图/数据流图，引用 `doc_center/source/.../figure/` 路径图片。

## 架构规格三页要点（在线版）

| 页面 | 命名 | 产品 | 模式 | 内容要点 |
| --- | --- | --- | --- | --- |
| 0010 | NPU架构版本200x | Atlas 推理系列（310P） | 耦合 | Cube+Vector 同核共享 Scalar；L0A ZZ / L0B ZN / L0C NZ 分形；无核间同步 |
| 0011 | NPU架构版本220x | Atlas A2 / A3 | 分离 1:2 | AIC/AIV 经 GM 通信；UB 192KB、L0C 128KB；指令队列深度；核间同步模式 0/1/2 |
| 00027 | NPU架构版本300x | Atlas 200I/500 A2（310B） | 耦合 | 各存储单元对齐要求表；L0A ZZ 分形；Fixpipe 量化反量化（S32→FP16 等） |

> 对应本地 asc-devkit 的 NPU架构版本2002 / 2201 / 3002 章节，内容同源，细节差异未逐行比对。
> 3510 详情见 [Ascend NPU 架构索引](./asc-devkit-arch-index.md) 的 3510 主题索引（本地仓库专属）。

## 与本地笔记的关系

| 本地笔记 | 覆盖范围 |
| --- | --- |
| [Ascend NPU 架构索引](./asc-devkit-arch-index.md) | asc-devkit git 仓库全量（含 3510），行号级索引 |
| 本文 | 昇腾社区 83RC1 在线文档集，页面级目录 + 基本架构详解 |

两套文档同源：在线版 = 发布版本（命名已改为 IP 核编号、无 3510）；本地 git 版 = 较新/全量版本（旧命名、含 3510）。
