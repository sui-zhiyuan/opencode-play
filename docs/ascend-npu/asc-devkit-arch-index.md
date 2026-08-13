# Ascend NPU 架构索引

华为昇腾 NPU 硬件架构笔记索引。源文档来自 [asc-devkit](https://gitcode.com/cann/asc-devkit)（Ascend C 开发文档），
本文是面向"架构问答"的检索入口：按主题定位到源文件 + 行号，快速找到答案。

## 源文档地图

源仓库根目录：`/home/suine/projects/asc-devkit`，本文所有相对路径均以 `docs/zh/` 为基准。

### 架构规格（重点）

```
docs/zh/guide/编程指南/高级编程/硬件实现/架构规格/
├── NPU架构版本2002.md   (128 行)  Atlas 推理系列（310P）
├── NPU架构版本2201.md   (225 行)  Atlas A2 / A3（910B / A3）
├── NPU架构版本3002.md   (184 行)  Atlas 200I/500 A2 推理（310B）
├── NPU架构版本3510.md   (343 行)  Ascend 950PR / 950DT  ← 重点
└── 架构规格.md           (3 行)   纯索引页，无内容
```

### 相邻文档

| 文档 | 路径 | 内容 |
| --- | --- | --- |
| 基本架构 | `guide/编程指南/高级编程/硬件实现/基本架构.md` (245 行) | 概念术语、耦合/分离工作模式、存储/搬运单元、数据流、指令流 |
| 硬件约束 2201 | `guide/编程指南/高级编程/硬件实现/硬件约束/NPU架构版本2201.md` (178 行) | 对齐、bank 冲突、GM/ICache/DCache 限制等约束与解法 |
| 硬件约束 2002 | `guide/编程指南/高级编程/硬件实现/硬件约束/NPU架构版本2002.md` (37 行) | 仅全局变量 / Generic Addressing 约束 |
| 数据排布格式 | `guide/技术附录/概念原理和术语/神经网络和算子/数据排布格式.md` | FRACTAL_NZ / ZN / ZZ 分形格式定义 |
| 避免 UB bank 冲突 | `guide/算子实践参考/SIMD算子性能优化/内存访问/避免UB的bank冲突/` | 含 `avoid_bank_conflict_npu_arch_2201.md` 和 `avoid_bank_conflict_npu_arch_3510.md` |

## __NPU_ARCH__ 版本号 → 产品映射

来源：`guide/编程指南/语言扩展层/SIMD-BuiltIn关键字.md` L7-24

| 版本号 | 产品 |
| --- | --- |
| 3510 | Ascend 950PR / Ascend 950DT |
| 2201 | Atlas A3 训练/推理系列、Atlas A2 训练/推理系列 |
| 3002 | Atlas 200I/500 A2 推理产品 |
| 2002 | Atlas 推理系列（310P） |

## 四代架构总览对比

| 维度 | 2002 (310P) | 2201 (A2/A3) | 3002 (310B) | 3510 (950) |
| --- | --- | --- | --- | --- |
| Cube/Vector 部署 | 耦合（同核） | 分离，AIC:AIV=1:2 | 耦合（同核） | 分离，AIC:AIV=1:2 |
| Vector 数据来源 | UB | UB | UB | **Register（新增 SIMD Register File）** |
| 各核 Scalar | 共享 | 各自独立 | 共享 | 各自独立 |
| L0A 分形 | FRACTAL_ZZ | FRACTAL_ZZ | FRACTAL_ZZ | **FRACTAL_NZ** |
| UB 容量 | 未列出 | 192KB | 未列出 | **256KB** |
| L0C 容量 | 未列出 | 128KB | 未列出 | **256KB** |
| 核间通信 | 不支持 | 经 GM | 不支持 | **SSBuf**（经 SSBuffer） |
| SIMT 硬件 | 无 | 无 | 无 | **有**（DCache/Warp Scheduler/Register File） |
| 核间同步模式 | 不支持 | 0 / 1 / 2 | 不支持 | 0 / 1 / 2 / **4** |
| 特有约束 | L0C→UB 须经 Vector 中转 | - | 可耦合可分离（Ascend C 仅耦合） | 删除 GM→L0A/L0B、L1→GM 通路 |

## NPU架构版本3510 主题索引（重点）

源文件：`guide/编程指南/高级编程/硬件实现/架构规格/NPU架构版本3510.md`

| 主题 | 行号 | 关键内容 |
| --- | --- | --- |
| 硬件架构总览 | L5-17 | AIC/AIV 分离、配比 1:2、各自独立 Scalar；关键特点清单 |
| 数据通路变化 | L13-16 | 新增 L0C→UB、UB↔L1 通路；删除 GM→L0A/L0B、L1→GM；SSBuffer 核间通信 |
| SIMT DCache | L27-30 | 最大 128KB，复用 UB 作 cacheline，128B 粒度访存 |
| Warp Scheduler | L32-36 | 每个 AIV 有 4 个 |
| SIMT Register File | L38-43 | 总 128KB；1025~2048 线程→16 寄存器，513~1024→32，257~512→64，1~256→127 |
| Vector 单元 | L53-64 | 支持 U8~FP32；256B/拍；数据来自 Register；掩码→MaskReg |
| Cube 单元 | L66-69 | 支持 FP32/FP16/BF16/HiF8/FP8_E4M3/FP8_E5M2/U8/S8；fp16 一拍 16x16x16x16；int8 一拍 16x32x32x16 |
| Scalar 单元 | L71-74 | U16/S16/U32/S32/U64/S64/FP64；Aux Scalar 处理 SIMD_VF 内计算 |
| 存储单元规格表 | L86-95 | UB 256KB、L1 512KB、L0A/L0B 64KB(512B对齐)、L0C 256KB(64B对齐)、BT 4KB、FP 4KB；含 Kernel 常量名 |
| UB 可用空间计算 | L109-125 | 默认 248KB；`--cce-disable-vf-stack-reserved-ubuf` +6KB；`--cce-disable-asc-reserved-ubuf` +2KB；SIMD+SIMT 混合再 −32KB(DCache) |
| 寄存器规格表 | L99-105 | 矢量数据寄存器 256B×32、掩码寄存器 32B×8、地址寄存器 4B×8、非对齐搬入/出寄存器 32B×4 |
| 带宽表 | L129-136 | L1→L0A/L0B 256B/cycle；L1→UB、UB→L1 128；L0C→UB、L0C→L1 128 |
| 分形格式 | L140-149 | L0A=NZ、L0B=ZN、L0C=NZ、L1 推荐 NZ、UB 无要求 |
| UB bank 冲突 | L151-160 | 每 bank group 两组读写口：最多 2读0写 或 1读1写（2201 只有一组） |
| 寄存器类型 | L162-178 | RegTensor(256B/VL)、MaskReg(VL/8)、UnalignRegForLoad/Store、AddrReg |
| 搬运对齐 | L182-184 | UB 按 DataBlock 对齐，其余按分形对齐 |
| GM↔UB Loop 模式 | L186-208 | Normal/Compact 两种，32B 对齐规则 |
| Fixpipe | L210-246 | 量化反量化、ReLu/PReLu/LeakyReLu、Channel merge/split、NZ2ND/NZ2DN |
| 指令序列深度 | L248-259 | Vector 0/32、Cube 16/0、MTE1 32/0、MTE2 16/16、MTE3 0/16、FixPipe 32/0（AIC/AIV） |
| 核间通信 | L261-265 | 经 SSBuf；支持 1:1 和 1:2（2201 经 GM） |
| 核内同步 | L269-298 | SetFlag/WaitFlag、EventID 管理（Alloc/Fetch/Release）、TEventID 6/7 禁止 |
| 核间同步 | L300-343 | CrossCoreSetFlag/WaitFlag、模式 0/1/2/4、flagId 计数器上限 15、默认 PIPE_S |

## 2201 主题索引（对照参考）

源文件：`guide/编程指南/高级编程/硬件实现/架构规格/NPU架构版本2201.md`

| 主题 | 行号 |
| --- | --- |
| 架构图（AIV↔AIC 经 GM） | L12-16 |
| 存储规格表（UB 192KB、L0C 128KB） | L42-51 |
| 带宽（仅 L1→L0A 256、L1→L0B 128） | L65-68 |
| 跨卡搬运（Hccs 物理链路） | L93-95 |
| 指令序列深度（Vector 0/64、MTE2 32/16、MTE3 32/16） | L141-148 |
| 核间同步模式 0/1/2 | L187-225 |

## 3002 / 2002 主题索引（对照参考）

| 主题 | 位置 |
| --- | --- |
| 3002 对齐要求表 | `NPU架构版本3002.md` L35-84 |
| 3002 分形（L0A=ZZ） | L88-97 |
| 2002 Vector 经中转取 L0C 数据 | `NPU架构版本2002.md` L22 |
| 2002 对齐要求表 | L35-69 |
| 两者均不支持核间同步 | 3002 L184、2002 L128 |

## 硬件约束主题索引

源文件：`guide/编程指南/高级编程/硬件实现/硬件约束/NPU架构版本2201.md`（178 行）

| 主题 | 行号 |
| --- | --- |
| 各存储单元对齐要求 | L25-32 |
| UB bank 冲突解法 | L37-42 |
| GM 多核同地址串行化 | L44-51 |
| 单次搬运 16KB 以上带宽最优 | L54-59 |
| GM→L1 块间隔 ≤65535 DataBlock | L62-66 |
| 搬运按 128/256/512B 拆分、GM 512B 对齐 | L69-74 |
| ICache 32KB / 多核同地址访问 | L85-97 |
| DCache 32KB / Scalar 写 GM 一致性 | L100-111 |
| L0C 128KB、BT 1KB、float 算力为 half 1/4 | L114-132 |
| flagId 计数器超 15 次需反向同步 | L162-167 |
| API 源/目的地址重叠约束 | L169-176 |

## 基本架构主题索引

源文件：`guide/编程指南/高级编程/硬件实现/基本架构.md`（245 行）

| 主题 | 行号 |
| --- | --- |
| 关键概念（Core/AI Core/Cube Core/Vector Core/AIC/AIV） | L19-43 |
| 分离模式 / 耦合模式定义 | L47-59 |
| 各产品工作模式对照 | L61-81（310P 耦合、910 耦合、910B/A3 分离、950 分离、310B 仅耦合） |
| Cube 单元（16x16 fp16 矩阵乘） | L87-92 |
| Vector 单元（SIMD、32B 对齐） | L94-101 |
| Scalar 单元（ICache 16K/32K、DCache 16K、Cache Line 64B） | L103-113 |
| 存储单元表（L1/L0A/L0B/L0C/UB/BT/FP） | L126-166 |
| 搬运单元表（MTE1/MTE2/MTE3/FixPipe 职责） | L168-202 |
| Vector 数据流 GM→UB→Vector→UB→GM | L210-214 |
| Cube 数据流 GM→L1→L0A/L0B→Cube→L0C→FixPipe→GM/L1 | L216-221 |
| 指令流与队列深度 | L223-244 |

## 常用交叉引用（API 等）

| 用途 | 路径 |
| --- | --- |
| 查询存储单元大小 | `docs/zh/api/Utils-API/platform_info/GetCoreMemSize.md`（或 `platform_info.md`） |
| EventID 管理 | `docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/`（AllocEventID / FetchEventID） |
| 核间同步 | `docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/`（CrossCoreSetFlag / CrossCoreWaitFlag） |
| 非对齐搬运 | `docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md` |
| 编译选项 | `guide/编程指南/编译与运行/算子编译/AI-Core算子编译基本用法.md` |
| 什么时候手动插入同步 | `docs/zh/api/SIMD-API/basic_api/sync_control/intra_core_sync/intra_core_sync_overview.md` |
