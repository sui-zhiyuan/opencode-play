# ARM SME（Scalable Matrix Extension）

SME 是 ARMv9-A 引入的矩阵计算扩展，让 CPU 直接高效执行矩阵乘加运算，无需 GPU 或专用 NPU。

---

## 一、核心概念：ZA 存储

SME 的核心是一个叫 **ZA** 的独立寄存器阵列——它不在通用寄存器或向量寄存器中，也不是内存映射的。

```
ZA = SVL bits × SVL bits 的二维矩阵存储
     SVL ∈ {128, 256, 512, 1024, 2048} bits（硬件决定）

ZA 可以按元素精度寻址子视：
  ZA   = 整个矩阵
  ZA0  = 第 0 行（SVL bits）
  ZA0.H = 按 half-precision 寻址（SVL/16 个 f16）
  ZA0.S = 按 single-precision 寻址（SVL/32 个 f32）
```

ZA 大小随 SVL 变化：

| SVL | ZA 大小（byte） | 等效 tile（float32） |
|---|---|---|
| 128 bits | 256 B | 4×4 |
| 256 bits | 1 KB | 8×8 |
| 512 bits | 4 KB | 16×16 |
| 1024 bits | 16 KB | 32×32 |
| 2048 bits | 64 KB | 64×64 |

ZA 是高速寄存器阵列——和执行单元直连，数据路径不经过 Load/Store Unit，自然也不经过 L1/L2 缓存。这避免 C tile 与 A、B 数据争抢缓存。

---

## 二、核心运算：外积（Outer Product）

### 定义

```
对于 a ∈ R^M, b ∈ R^N:
C = a ⊗ b    (外积)
C[i][j] = a[i] * b[j]
```

输入两个向量，输出一个矩阵，每个元素 = 两向量对应元素的乘积。不求和（这和点积不同）。

### FMOPA 指令

```asm
FMOPA   ZA0.S, p0/M, p0/M, z0.h, z1.h
// ZA0  = ZA 行（SVL×SVL 矩阵）
// z0, z1 = SVE 谓词向量（每个 lane 是 f16）
// .S = 输出精度（single precision）
// .H = 输入精度（half precision）
// 操作：ZA0[i][j] += z0[i] × z1[j]  （FP16 × FP16 → FP32 累加）
```

一条 FMOPA 完成的乘加对数 = `(SVL/16) × (SVL/16)`：

| SVL | z 的 lane 数 | 每指令 FMA 数 |
|---|---|---|
| 128 | 8 | 8×8 = 64 |
| 256 | 16 | 16×16 = 256 |
| 512 | 32 | 32×32 = 1024 |
| 2048 | 128 | 128×128 = 16384 |

### 指令族

| 指令 | 输入类型 | 输出类型 | 用途 |
|---|---|---|---|
| `FMOPA` | bf16 / f16 | f32 | LLM 推理（BF16） |
| `SMOPA` | i8 | i32 | INT8 量化推理 |
| `UMOPA` | u8 | i32 | UINT8 量化推理 |
| `SMOPA` (wide) | i4 | i32 | INT4 量化 |
| `FMOPA` (FP8) | f8e4m3 / f8e5m2 | f32 | FP8 训练/推理 |

---

## 三、用外积计算矩阵乘

### 核心等式

```
C = A × B  (M×K × K×N = M×N)

等效为 K 个外积求和：
C = Σ_{k=0}^{K-1} A_col_k ⊗ B_row_k
```

其中 A_col_k 是 A 的第 k 列，B_row_k 是 B 的第 k 行。

### 逐元素验证

```
C[i][j] = Σ_k A[i][k] × B[k][j]          ← 传统点积
        = Σ_k (A_col_k ⊗ B_row_k)[i][j]   ← 外积累加
```

完全相同。

### 为什么 SME 用外积而不是点积

| | 点积（传统 SIMD） | 外积（SME） |
|---|---|---|
| 每次迭代产出 | C 中 1 个元素 | C 中 VL×VL 个元素 |
| 数据搬运量 | 高（A 行用完即弃） | 低（A 列常驻 ZA，只更新 B 行） |
| SIMD 宽度利用 | 受限于水平归约 | 每个乘法独立输出，无归约瓶颈 |

### 完整微内核伪代码

```asm
    SMSTART ZA
.L_m_loop:
    .L_n_loop:
        MOVAZ   ZA0                 // ZA = 0
        .L_k_loop:
            LDR z0, [A_ptr]         // 加载 A 的一列（m_tile 个元素）
            LDR z1, [B_ptr]         // 加载 B 的一行（n_tile 个元素）
            FMOPA ZA0.S, p0/M, p1/M, z0.h, z1.h
            // z0, z1 继续在 K 方向推进
        STR ZA0, [C_ptr]            // C tile 写回
    SMSTOP ZA
```

---

## 四、B 矩阵不需要转置

在外积分解 `C = Σ A_col_k ⊗ B_row_k` 中，取的是 B 的**行**（不是列）。

B 在 row-major 下，行是连续存储的：
```
B 在内存中：row_0: [7, 8], row_1: [9, 10], row_2: [11, 12]
取 B_row_k → 直接向量加载，stride-1，零转置。
```

**需要转置的是 A**（A 的列在 row-major 下 stride = K，不连续）。通过 pack 阶段将 A 重排为 column-major 布局即可。

---

## 五、流模式（Streaming Mode）

### 为什么需要

ZA 在非流模式下**不存在**——硬件懒惰分配，访存 ZA 触发未定义指令异常。

```
// 非流模式
FMOPA ZA0.S, ...      // ❌ UNDEFINED

SMSTART ZA             // 进入流模式，启用 ZA
FMOPA ZA0.S, ...       // ✅
SMSTOP ZA              // 退出，ZA 清零
```

### 流模式提供的能力

| 能力 | 非流模式 | 流模式 |
|---|---|---|
| 通用 SVE2 | ✓ | ✓ |
| ZA 存储 | ✗ | ✓ |
| FMOPA / SME 矩阵指令 | ✗ | ✓ |
| Multi-vector（SME2） | ✗ | ✓ |
| 谓词隔离 | 无 | ✓ |
| ZA 惰性保存 | 无 | OS 可延迟 |
| z 寄存器保护 | z8-z23 callee-saved | 全部 caller-saved |
| ZA store 可能绕过 L1 | N/A | 实现可选 |

### 调用约定（PCS_SME）

流模式的调用约定比标准 AAPCS64 激进：

- **z0-z31：全部 caller-saved**（标准中 z8-z23 是 callee-saved）
- p0-p15：caller-saved
- ZA：由调用者管理
- 设计意图：ZA 已经很昂贵，不愿再额外保护 z 寄存器，把计算集中封装在单个流模式函数内

### 进入/退出指令

| 指令 | 行为 |
|---|---|
| `SMSTART ZA` | 进入流模式，启用 ZA。若 ZA 有惰性脏数据，触发 OS 恢复 |
| `SMSTOP ZA` | 退出流模式，ZA 清零，谓词状态恢复 |
| `SMSTART SM` | 进入流模式但不启用 ZA（仅流式 SVE，开销更小） |

### 惰性保存

OS 可以在上下文切换时不立即保存 ZA：

```
1. 线程 A 在流模式 → ZA 标记为"脏"
2. 切换到线程 B
3. 线程 B 如果尝试 SMSTART → 触发 trap → OS 此时才保存/恢复 ZA
```

大量线程不进流模式 → ZA 代价为零。

---

## 六、ZA Tile 大小与 Tail 处理

### SME 不规定固定 tile 大小

ZA 大小 = SVL×SVL，SVL 由硬件决定。同一二进制在不同 SVL 上不需重编译。

运行时查询：
```asm
RDSVL   x0, #1        // x0 = SVL in bytes
```

### Tail 处理

**M 方向、N 方向**：用谓词掩码处理余数，不必为 SVL 的倍数：

```asm
// 完整 8×8
PTRUE   p0.s, p1.s
FMOPA   ZA0.S, p0/M, p1/M, z0.s, z1.s

// Tail 5×7
WHILELT p0.s, x0, x5        // 前 5 个 lane 活跃
WHILELT p1.s, x1, x7        // 前 7 个 lane 活跃
FMOPA   ZA0.S, p0/M, p1/M, z0.s, z1.s
// ZA0[0:5, 0:7] 被更新，其余保持不变
```

**K 方向**：完全任意——K 是外积累加次数，与 ZA 维度无关：

```asm
    MOV     xk, #0
.Lk:
    LDR z0, [A_ptr, xk, LSL #2]
    LDR z1, [B_ptr, xk, LSL #2]
    FMOPA ZA0.S, p0/M, p1/M, z0.s, z1.s
    ADD xk, xk, #1
    CMP xk, K
    B.LT .Lk
```

K 可以是任意值，不受 ZA 大小限制。

### 实际 tiling 策略

主 tile 选 SVL 的整数倍 → 充分利用 ZA，谓词全开。Tail 部分量少，仅用谓词掩码降级处理。

---

## 七、ZA Store 的缓存行为

`STR ZA[n], [addr]` 走 LSU → 缓存层级：

```
ZA 行 → 执行单元 → LSU → L1 数据缓存 → L2 → ...
```

但流模式下**架构允许实现改变策略**：

| 策略 | 行为 | 目的 |
|---|---|---|
| 普通缓存 | 写 L1，可能挤掉 A/B 数据 | — |
| 绕过 L1 | 直接写 L2/L3 流式缓冲区 | 保护 L1 中 A、B tile 复用 |
| 非 temporal | 配合 NT hint | 减少缓存污染 |

具体行为**实现定义**，趋势是流模式下 ZA store 尽量不污染 L1。

---

## 八、SME2 增强

| SME | SME2 (ARMv9.3+) | 效果 |
|---|---|---|
| 一次外积 2 个向量 | 一次 4 个向量（multi-vector）| 吞吐翻倍 |
| 无量化 | 原生 INT4 / FP8 | 更高压缩比 |
| 逐元素操作 | 矩阵-向量乘积指令 | 减少数据搬运 |
| 行/列加载 | 结构化 tile load/store | 高效矩阵块搬运 |

SME2 multi-vector 示例：
```asm
FMOPA   ZA2.S, p0/M, p1/M, {z0.s-z1.s}, {z2.s-z3.s}
// 同时操作 ZA0..ZA3，一次指令处理 2×SVL × 2×SVL 的块
```

---

## 九、与 Intel AMX 对比

| | ARM SME | Intel AMX |
|---|---|---|
| tile 存储 | ZA（SVL×SVL，可变） | TMM0-7（固定 16×64 bytes） |
| 向量宽度 | SVL（运行时可变）| AVX-512（固定 512 bits）|
| 跨代兼容 | 同一二进制，不需重编译 | 固定尺寸，每代可能不同 |
| tile store 缓存 | 流模式可选绕过 L1 | 正常经 L1（需显式 NT hint）|
| 状态保存 | 惰性，不进流模式即零开销 | xsave，8KB regardless |

---

## 十、矩阵乘中的循环顺序与缓存分析

### 三层 tiling 循环

```python
for m in 0..M step m_tile:
    for n in 0..N step n_tile:
        ZA = 0                          # C tile 在 ZA 中
        for k in 0..K step k_tile:
            load A[m:m+m_tile, k:k+k_tile]
            load B[k:k+k_tile, n:n+n_tile]
            # K 块内用 FMOPA 外积累加
        store ZA → C[m:m+m_tile, n:n+n_tile]
```

### m→n→k（GotoBLAS 策略）——最优

| 数据 | 所在位置 | 跨轴复用 | 复用因子 |
|---|---|---|---|
| C tile | ZA（寄存器阵列） | 跨 K | K_tiles |
| A panel (m×K) | L2 缓存 | 跨 N | N_tiles |
| B block (k_tile×n_tile) | L1/流式 | — | 1 |

C 的累加在 ZA 中最内层（K 循环）完成，离开 (m,n) tile 前只写回一次。

### k→m→n——C 会被反复加载

K 在最外层时，ZA 在一次 K 迭代内被覆盖，C 的部分和必须通过内存周转：每个 k_block 都要 load C tile → 累加 → store。C 的 load/store 次数 = K_tiles，效率远不如 m→n→k。

### tiling 的正确性

```
C[2:4, 4:8] 的计算只用：
  A 的第 2-3 行（m_tile 大小）
  B 的第 4-7 列（n_tile 大小）

K 轴索引必须对齐：
  A[i][k=3] 只能和 B[k=3][j] 相乘，不能和 B[k=7][j] 相乘
→ K 分块只是把求和分段，A 和 B 的 K 范围必须对应
→ 块之间是加法合并，不是矩阵乘
```

---

## 十一、极限缓存约束分析

### 问题

假设缓存仅能容纳一个 A tile + 一个 B tile + 一个 C tile（ZA 不占缓存），M_tiles = N_tiles = K_tiles = 10，tile 大小 t。

### m→n→k 的缓存需求

```
所需缓存 = m_tile × K + k_tile × n_tile（B 流式加载）
         = t × 10t + t × t = 11t²
```

缓存 Miss 总计（元素）：

| 数据 | 加载次数 | 总量 |
|---|---|---|
| A | 1 | 100t² |
| B | M_tiles（k→m→n 中丢失复用） | 1000t² |
| C（写）| 1 | 100t² |
| **总计** | | **1200t²** |

如果有 ≥ 11t² 缓存，B 也能一次加载复用：
```
B = 1 次加载 = 100t²
总计 = 300t²（理论最优）
```

ZA 作为独立寄存器阵列，让 C tile 不占缓存，等于在不增加缓存要求的情况下释放出 1/3 的缓存空间给 A、B。

---

## 参考资料

- [ARM A-Profile Architecture Developments 2025 (ARMv9.7-A)](https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/arm-a-profile-architecture-developments-2025)
- [What is new in LLVM 22 (ARM SME/SME2 support)](https://developer.arm.com/community/arm-community-blogs/b/tools-software-ides-blog/posts/what-is-new-in-llvm-22)
- [Introducing Armv9 Scalable Matrix Extension](https://newsroom.arm.com/blog/armv9-cpus-consumer-devices)
