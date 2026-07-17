# Transformer 架构学习路线：从 minGPT 到纯标量运算

## 目录

1. [推荐资源](#推荐资源)
2. [算力需求估算](#算力需求估算)
3. [减少数据量、节约算力的策略](#减少数据量节约算力的策略)
4. [四层深度学习方法论](#四层深度学习方法论)
5. [时间估算](#时间估算)
6. [各层级接口与依赖关系](#各层级接口与依赖关系)
7. [L4 → L3 接口：纯标量原语 → 矩阵运算](#l4--l3-接口纯标量原语--矩阵运算)
8. [L3 → L2 接口：矩阵运算 → 手写正向/反向传播](#l3--l2-接口矩阵运算--手写正向反向传播)
9. [L2 → L1 接口：手写正向/反向 → minGPT 层](#l2--l1-接口手写正向反向--mingpt-层)
10. [各层验证方法](#各层验证方法)
11. [推荐学习节奏](#推荐学习节奏)

---

## 推荐资源

### 代码层面（从简到难）

| 资源 | 说明 | 代码量 |
|------|------|--------|
| **Andrej Karpathy - minGPT** | ~300 行 Python，纯 PyTorch，不含任何废话 | 推荐起步 |
| **Andrej Karpathy - nanoGPT** | minGPT 的演进，附带训练脚本，可训莎士比亚文本 | ~400 行 |
| **The Annotated Transformer (Harvard NLP)** | 原论文逐行注释版，带详细解释 | ~500 行 |
| **Let's Build GPT from Scratch (Karpathy 视频)** | 2 小时从头写 GPT，YouTube 搜索即可 | 视频教程 |

**最推荐路线**：先看 Karpathy 的视频，再自己跑 nanoGPT。

### 理论层面

- **原论文 "Attention Is All You Need"** — 读一遍即可，不用死磕
- **Jay Alammar 的 The Illustrated Transformer** — 图解文章，非常直观
- **3Blue1Brown 的深度学习系列** — 建立直觉

---

## 算力需求估算

| 场景 | GPU | 训练时间 | 说明 |
|------|-----|---------|------|
| **纯理解架构、跑前向/反向验证梯度** | **不需要 GPU**，CPU 足够 | 秒级 | `batch_size=2, seq_len=64, d_model=128, 2层` |
| **训练一个能输出连贯文本的小 GPT** | 任意 NVIDIA GPU（RTX 2060 以上，或 Colab 免费 T4） | 几分钟到几小时 | 莎士比亚级别数据集 |
| **训练到能看的程度** | RTX 3060+（12GB 显存） | 数小时 | 更大的 WikiText |

**关键结论：理解 Transformer 架构本身不需要 GPU。** 用 CPU 跑一个 `(batch=4, seq=128, hidden=256)` 的小模型，前向和反向都秒出结果。只有当你真正训练它生成文本时才需要 GPU。

---

## 减少数据量、节约算力的策略

### 1. 用过拟合验证架构正确性（最核心技巧）

学习阶段最重要的理念——**你不需要大量数据来验证模型是否正确实现**。

```python
# 只用 100 个字符，让它过拟合
text = "abcdefghijklmnopqrstuvwxyz "  # 循环复制到 100 字符
# 如果 Transformer 写对了，loss 会降到 0
```

任何正确的 Transformer 实现都应该能够将 100 字符的小语料过拟合到 loss ≈ 0。如果做不到，说明代码有 bug。

### 2. 具体缩减策略

| 策略 | 效果 | 做法 |
|------|------|------|
| **极小数据集验证** | 最快 | 100~1000 个字符，确保能过拟合 |
| **莎士比亚 tiny** | 有意义输出 | Karpathy 提供的 `input.txt`（~1MB） |
| **短序列训练** | 平方级降低注意力计算 | `block_size=64` 而非 512 |
| **小模型尺寸** | 内存/算力指数级降低 | `n_layer=4, n_head=4, n_embd=128` |
| **增大 batch size** | 更快收敛，用更少 step | `batch_size=64`（在硬件允许范围内） |
| **混合精度 (AMP)** | ~2x 加速 | PyTorch `torch.cuda.amp` |

### 3. 推荐的极简实验流程

```
阶段1 (CPU, 1分钟): model = GPT(vocab_size=27, block_size=8, n_layer=1, n_head=2, n_embd=32)
                     数据 = "abc...xyz" × 100
                     目标: loss 降到 0.01 以下 → 验证架构正确

阶段2 (GPU/Colab, 10分钟): model = GPT(block_size=128, n_layer=4, n_head=4, n_embd=128)
                           数据 = tiny Shakespeare
                           目标: 生成看起来像英文的胡言乱语

阶段3 (GPU, 1小时): 同上模型，多训几轮，调参
                     目标: 生成可读的莎士比亚风格文本
```

---

## 四层深度学习方法论

这是经典的"向下挖掘"学习路径：

```
L1 (minGPT)          nn.MultiheadAttention, nn.Linear — PyTorch 高层 API
  ↓ 拆掉
L2 (手写反向传播)      手写 forward + backward，保留 torch.matmul / torch.softmax
  ↓ 拆掉
L3 (手写矩阵运算)      自己实现 matmul, softmax, layer_norm
  ↓ 拆掉
L4 (纯标量运算)        纯 Python 循环 + 算术，无 tensor、无 numpy
```

| 层 | 内容 | 代表操作 |
|---|------|---------|
| L1 | minGPT 读懂跑通 | `nn.MultiheadAttention` |
| L2 | 拆掉 nn 封装，手写前向+反向 | `torch.matmul` + 手动链式法则 |
| L3 | 拆掉 BLAS，手写矩阵运算 | 三重循环 `matmul`、`softmax` |
| L4 | 拆到标量，纯循环+算术 | 无 tensor、无 numpy、纯 Python |

---

## 时间估算

### 总览

| 层 | 内容 | 时间（全职） | 时间（业余） |
|---|------|------------|------------|
| L1 | minGPT 读懂跑通 | 1-2 天 | 3-5 天 |
| L2 | 拆掉 nn 封装，手写前向+反向 | 3-5 天 | 1-2 周 |
| L3 | 拆掉 BLAS，手写矩阵运算 | 4-7 天 | 2-3 周 |
| L4 | 拆到标量，纯循环+算术 | 3-5 天 | 1-2 周 |
| **合计** | | **11-19 天** | **1-2 个月** |

### 逐层拆解

#### L1 — minGPT（~300 行 PyTorch）: 1-2 天

读代码、跑起来、改参数。关键是理清**数据流**：

```
[token ids] → Embedding → [TransformerBlock × N] → LM Head → logits → cross_entropy
                              │
                    ┌─────────┼──────────┐
                    │  LayerNorm         │
                    │  MultiHeadAttention│
                    │  + residual        │
                    │  LayerNorm         │
                    │  MLP (Linear→GELU→Linear) │
                    │  + residual        │
                    └────────────────────┘
```

**产出**：能用 `gpt.generate()` 出文本，理解 `(B, T, C)` 张量在各层间的形状变化。

#### L2 — 拆 PyTorch nn 封装，手写反向传播: 3-5 天

这一层**不用** `nn.Linear`、`nn.LayerNorm`、`nn.MultiheadAttention`，但**保留** `torch.matmul`、`torch.softmax`、`torch.exp` 等基础张量操作。同时关闭 autograd，手动实现反向传播。

```python
# ❌ L1 写法
self.attn = nn.MultiheadAttention(embed_dim, num_heads, batch_first=True)

# ✅ L2 写法 — 用基础 tensor ops 手写 attention forward + backward
def attention_forward(Q, K, V, mask=None):
    # Q, K, V: (B, n_head, T, head_dim)
    scale = head_dim ** -0.5
    attn_scores = torch.matmul(Q, K.transpose(-2, -1)) * scale   # 保留 matmul
    if mask is not None:
        attn_scores = attn_scores.masked_fill(mask == 0, -1e9)
    attn_weights = torch.softmax(attn_scores, dim=-1)            # 保留 softmax
    out = torch.matmul(attn_weights, V)
    return out, attn_weights

def attention_backward(d_out, attn_weights, Q, K, V):
    # 手动实现链式法则，推导 softmax + matmul 的梯度
    # d_attn_weights = d_out @ V^T
    # d_attn_scores = softmax_backward(d_attn_weights, attn_scores)
    # d_Q = rescale(d_attn_scores @ K)
    # d_K = rescale(d_attn_scores^T @ Q)
    # d_V = attn_weights^T @ d_out
    ...
```

**你要做的**：
- 手写 `layer_norm_forward` / `layer_norm_backward`（前向：减均值除标准差乘 γ 加 β）
- 手写 `linear_forward` / `linear_backward`（前向：`X @ W + b`，反向：对 X、W、b 分别求导）
- 手写 `softmax_forward` / `softmax_backward`（数值稳定版）
- 手写完整的 `transformer_block_forward` / `transformer_block_backward`
- **用 `torch.autograd.gradcheck` 验梯度**，这是 L2 的核心验收手段

**学习密度最高的部分**：反向传播推导。你会真正理解为什么 attention 的 QKV 梯度各长什么样，什么是 "梯度流过 softmax"。

#### L3 — 用自己的矩阵乘法替换 torch.matmul: 4-7 天

这一层你的代码里不再出现 `torch.matmul`、`torch.softmax`。用**自己的矩阵运算**替代。

```python
# ❌ L2 写法
scores = torch.matmul(Q, K.transpose(-2, -1))

# ✅ L3 写法 — 自己实现 matmul
def matmul_forward(A, B):
    # A: (M, K), B: (K, N) → C: (M, N)
    C = [[0.0] * N for _ in range(M)]
    for i in range(M):
        for j in range(N):
            s = 0.0
            for k in range(K):
                s += A[i][k] * B[k][j]
            C[i][j] = s
    return C
```

但这只是**朴素 O(n³)**。要真的理解性能，你还应该：

| 要做的事 | 难度 | 收获 |
|---------|------|------|
| 朴素三重循环 matmul | 低 | 理解内存访问模式 |
| 分块 (tiled) matmul | 中 | 理解 cache locality，连接 L4 |
| 自己实现 softmax（exp + sum + div） | 低 | 理解数值稳定技巧（减 max） |
| 自己实现 layer norm（mean + var + normalize） | 低 | — |
| **自己实现 batch matmul** | **高** | 这是最难的——你要在四维张量 `(B, H, T, D)` 上做乘法 |

**验收标准**：不依赖任何 `torch.matmul`/`torch.softmax`，但可以继续用 `torch.tensor` 做存储和基础算术（`+`、`*`、`/`）。前向结果与 PyTorch 一致，loss 能降。

#### L4 — 拆到标量，纯 Python 循环+算术: 3-5 天

这一层**连 `torch.tensor` 都不用**（或者只用它做存储容器，运算全部手写 Python 循环）。本质上你在实现一个**极简版的 numpy**。

```python
# 你的"张量"就是嵌套 list
tensor_2d = [[1.0, 2.0, 3.0],
             [4.0, 5.0, 6.0]]

# add: element-wise
def add(A, B):
    return [[A[i][j] + B[i][j] for j in range(cols)] for i in range(rows)]

# multiply: element-wise  
def mul(A, B):
    return [[A[i][j] * B[i][j] for j in range(cols)] for i in range(rows)]

# sum over axis
def sum_axis(X, axis):
    # axis=0 → 按列求和, axis=1 → 按行求和
    ...

# exp, sqrt — element-wise math
import math
def exp(X):
    return [[math.exp(x) for x in row] for row in X]
```

这一层的核心挑战是**维度管理**——你不再有 `tensor.view()`、`tensor.transpose()`、broadcasting，所有东西都要用循环和索引手动完成。一个 `attention(Q, K, V)` 的前向传播可能变成 200+ 行嵌套循环。

**这一层最耗时的是调试**——一个维度错，结果全错，而且纯 Python 三重循环极慢，验证一个 epoch 可能就要几分钟。

**合理的折中**：只对**一个极小模型**做 L4（`vocab=27, seq=8, hidden=16, layers=1`），验证前向+反向数值正确即可。不需要训练出有意义的结果。

### L2 之后的关键拐点

L2 完成后你已经理解了 Transformer 的**数学本质**。L3/L4 更多是**系统/性能理解**而非架构理解。很多优秀工程师停在了 L2——知道每步梯度怎么流，但不一定需要知道自己写 matmul。

如果你真的想 L3 → L4，一个高效的做法是：**只针对 Attention 这一个模块往下挖**，而不是整个 GPT。Attention 是 Transformer 的灵魂，对它的 QKV 投影、score 计算、softmax、加权求和做 L3/L4 的完整实现，你已经掌握了最核心的部分。FFN 和 LayerNorm 在 L3/L4 层面没有新概念。

---

## 各层级接口与依赖关系

每一层的接口关系本质上是 **"下层提供原语，上层做组合"**。

### 整体层级关系

```
L1 (minGPT)     GPT.forward(), GPT.generate()
    │           ┌─ CausalSelfAttention.forward()
    │           └─ MLP.forward(), Block.forward()
    ▼           依赖: 下层提供 tensor 级别的 matmul, softmax, layer_norm
L2 (手写反向)   attention_forward(Q,K,V), linear_forward(X,W,b)
    │           softmax_forward(X), layer_norm_forward(X,g,b)
    │           依赖: 下层提供矩阵乘法、逐元素 exp/sqrt
    ▼
L3 (手写矩阵)   matmul(A,B), batch_matmul(A,B), softmax(X), layernorm(X)
    │           依赖: 下层提供标量加法、乘法、exp、sqrt、循环
    ▼
L4 (纯标量)     add(A,B), mul(A,B), sum_axis(X,axis), exp(X), sqrt(X), transpose(X)
                依赖: Python +, *, /, math.exp, math.sqrt
```

---

## L4 → L3 接口：纯标量原语 → 矩阵运算

### L4 提供的原语（纯 Python list + 循环 + 算术）

```python
# ===== L4 原语：只依赖 Python 内置运算 =====
import math

def full(rows, cols, val):
    """创建填充矩阵"""
    return [[val for _ in range(cols)] for _ in range(rows)]

def zeros(rows, cols):
    return full(rows, cols, 0.0)

def add(A, B):
    """逐元素加法，支持 broadcasting（标量）"""
    if isinstance(B, (int, float)):
        return [[A[i][j] + B for j in range(len(A[0]))] for i in range(len(A))]
    return [[A[i][j] + B[i][j] for j in range(len(A[0]))] for i in range(len(A))]

def mul(A, B):
    """逐元素乘法"""
    if isinstance(B, (int, float)):
        return [[A[i][j] * B for j in range(len(A[0]))] for i in range(len(A))]
    return [[A[i][j] * B[i][j] for j in range(len(A[0]))] for i in range(len(A))]

def sub(A, B):
    return add(A, mul(B, -1.0))

def div(A, B):
    if isinstance(B, (int, float)):
        return mul(A, 1.0 / B)
    return [[A[i][j] / B[i][j] for j in range(len(A[0]))] for i in range(len(A))]

def exp(X):
    return [[math.exp(x) for x in row] for row in X]

def sqrt_(X):
    return [[math.sqrt(x) for x in row] for row in X]

def sum_axis(X, axis):
    """沿指定轴求和"""
    if axis == 0:  # 列方向求和 → 得到一行
        return [[sum(X[i][j] for i in range(len(X)))] for j in range(len(X[0]))]
    elif axis == 1:  # 行方向求和 → 得到一列
        return [[sum(row)] for row in X]

def mean_axis(X, axis):
    n = len(X) if axis == 1 else len(X[0])
    s = sum_axis(X, axis)
    return div(s, float(n))

def max_axis(X, axis):
    """沿指定轴取最大值"""
    if axis == 1:  # 每行取最大值
        return [[max(row)] for row in X]
    # axis == 0
    return [[max(X[i][j] for i in range(len(X)))] for j in range(len(X[0]))]

def transpose(X):
    return [[X[j][i] for j in range(len(X))] for i in range(len(X[0]))]

def tile_row(X, n):
    """将行向量复制 n 次: (1, C) → (n, C)"""
    return [X[0][:] for _ in range(n)]

def print_shape(name, X):
    print(f"{name}: ({len(X)}, {len(X[0])})")
```

### L3 如何使用 L4 原语构建矩阵运算

```python
# ===== L3: 用 L4 原语构建 matmul =====
def matmul(A, B):
    """A: (M, K), B: (K, N) → (M, N)"""
    M, K = len(A), len(A[0])
    Kb, N = len(B), len(B[0])
    assert K == Kb
    C = zeros(M, N)
    for i in range(M):
        Ai = A[i]  # 第 i 行
        for j in range(N):
            s = 0.0
            for k in range(K):
                s += Ai[k] * B[k][j]
            C[i][j] = s
    return C

def matmul_transpose_A(A, B):
    """A^T @ B: A (K, M), B (K, N) → (M, N)"""
    K, M = len(A), len(A[0])
    Kb, N = len(B), len(B[0])
    assert K == Kb
    C = zeros(M, N)
    for i in range(M):
        for j in range(N):
            s = 0.0
            for k in range(K):
                s += A[k][i] * B[k][j]
            C[i][j] = s
    return C

def matmul_transpose_B(A, B):
    """A @ B^T: A (M, K), B (N, K) → (M, N)"""
    M, K = len(A), len(A[0])
    N, Kb = len(B), len(B[0])
    assert K == Kb
    C = zeros(M, N)
    for i in range(M):
        for j in range(N):
            s = 0.0
            for k in range(K):
                s += A[i][k] * B[j][k]
            C[i][j] = s
    return C

def softmax(X, axis=-1):
    """X: (M, N) → (M, N)，沿最后一维做 softmax"""
    # 1. 数值稳定：每行减最大值
    max_vals = max_axis(X, 1)              # (M, 1)
    X_stable = sub(X, tile_row(max_vals, len(X)))  # (M, N)
    # 2. exp
    E = exp(X_stable)                      # (M, N)
    # 3. sum + normalize
    sums = sum_axis(E, 1)                  # (M, 1)
    return div(E, tile_row(sums, len(E)))  # (M, N)

def layer_norm(X, gamma, beta, eps=1e-5):
    """X: (M, C), gamma: (1, C), beta: (1, C) → (M, C)"""
    mean = mean_axis(X, 1)                # (M, 1)
    centered = sub(X, tile_row(mean, len(X)))  # (M, C)
    var = mean_axis(mul(centered, centered), 1)  # (M, 1)
    std = sqrt_(add(tile_row(var, len(X)), eps)) # (M, C)
    normalized = div(centered, std)         # (M, C)
    return add(mul(tile_row(gamma, len(X)), normalized),
               tile_row(beta, len(X)))

def gelu(X):
    """
    GELU activation: x * 0.5 * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
    用 L4 原语实现
    """
    coeff = math.sqrt(2.0 / math.pi)
    # x^3
    X3 = mul(mul(X, X), X)
    # inner = coeff * (x + 0.044715 * x^3)
    inner = mul_scalar(add(X, mul_scalar(X3, 0.044715)), coeff)
    # tanh approximation or math.tanh
    tanh_inner = apply_math(inner, math.tanh)
    # 0.5 * x * (1 + tanh)
    return mul(mul_scalar(X, 0.5), add_scalar(tanh_inner, 1.0))
```

**L3 向上层 L2 暴露的接口**：`matmul`, `softmax`, `layer_norm`, `transpose`, `gelu`

---

## L3 → L2 接口：矩阵运算 → 手写正向/反向传播

### L2 如何使用 L3 原语构建 Attention + 反向传播

```python
# ===== L2: 用 L3 原语构建 Attention forward + backward =====

def attention_forward(Q, K, V, mask=None):
    """
    Q, K, V: (B, n_head, T, head_dim)
    返回: output (B, n_head, T, head_dim), cache (中间值供 backward 用)
    """
    B, H, Tq, D = len(Q), len(Q[0]), len(Q[0][0]), len(Q[0][0][0])
    Tk = len(K[0][0])
    scale = 1.0 / math.sqrt(D)
    
    # 对每个 batch 和 head，做 Q @ K^T → (T, T)
    scores = zeros_4d(B, H, Tq, Tk)
    for b in range(B):
        for h in range(H):
            Kt = transpose(K[b][h])         # L3: (D, T)
            s = matmul(Q[b][h], Kt)         # L3: (T, D) @ (D, T) → (T, T)
            scores[b][h] = mul_scalar(s, scale)
    
    # Mask (causal)
    if mask is not None:
        for b in range(B):
            for h in range(H):
                for i in range(Tq):
                    for j in range(Tk):
                        if mask[i][j] == 0:
                            scores[b][h][i][j] = -1e9
    
    # Softmax
    attn_weights = zeros_4d(B, H, Tq, Tk)
    for b in range(B):
        for h in range(H):
            attn_weights[b][h] = softmax(scores[b][h])  # L3 原语
    
    # Weighted sum: attn @ V → (T, D)
    output = zeros_4d(B, H, Tq, D)
    for b in range(B):
        for h in range(H):
            output[b][h] = matmul(attn_weights[b][h], V[b][h])  # L3 原语
    
    cache = (Q, K, V, scores, attn_weights, mask)
    return output, cache


def attention_backward(d_output, cache):
    """
    d_output: (B, n_head, T, head_dim) — 上游传来的梯度
    返回: d_Q, d_K, d_V — 各 (B, n_head, T, head_dim)
    """
    Q, K, V, scores, attn_weights, mask = cache
    B, H, Tq, D = len(Q), len(Q[0]), len(Q[0][0]), len(Q[0][0][0])
    
    d_Q = zeros_4d(B, H, Tq, D)
    d_K = zeros_4d(B, H, len(K[0][0]), D)
    d_V = zeros_4d(B, H, len(V[0][0]), D)
    
    for b in range(B):
        for h in range(H):
            attn = attn_weights[b][h]  # (Tq, Tk)
            
            # 1. d(attn_weights) = d_output @ V^T
            # (Tq, D) @ (D, Tk) → (Tq, Tk)
            d_attn = matmul(d_output[b][h], transpose(V[b][h]))
            
            # 2. softmax backward: d_s = attn * (d_attn - sum(d_attn * attn))
            d_attn_dot_attn = sum_axis(mul(d_attn, attn), 1)    # (Tq, 1)
            d_scores = mul(attn, sub(d_attn, tile_row(d_attn_dot_attn, Tq)))
            
            scale = 1.0 / math.sqrt(D)
            d_scores = mul_scalar(d_scores, scale)
            
            # 3. Q, K, V 的梯度
            # d_Q = d_scores @ K  → (Tq, Tk) @ (Tk, D) → (Tq, D)
            d_Q[b][h] = matmul(d_scores, K[b][h])
            
            # d_K = d_scores^T @ Q  → (Tk, Tq) @ (Tq, D) → (Tk, D)
            d_K[b][h] = matmul(transpose(d_scores), Q[b][h])
            
            # d_V = attn^T @ d_output  → (Tk, Tq) @ (Tq, D) → (Tk, D)
            d_V[b][h] = matmul(transpose(attn), d_output[b][h])
    
    return d_Q, d_K, d_V


def linear_forward(X, W, b):
    """X: (M, in_f), W: (in_f, out_f), b: (1, out_f) → (M, out_f)"""
    return add(matmul(X, W), tile_row(b, len(X)))

def linear_backward(d_out, cache):
    """
    d_out: (M, out_f)
    返回: d_X (M, in_f), d_W (in_f, out_f), d_b (1, out_f)
    """
    X, W, b = cache
    # d_X = d_out @ W^T
    d_X = matmul(d_out, transpose(W))
    # d_W = X^T @ d_out
    d_W = matmul(transpose(X), d_out)
    # d_b = sum over batch dim → (1, out_f)
    d_b = sum_axis(d_out, 0)  # axis=0: 沿行方向求和
    return d_X, d_W, d_b

# ===== L2 向上提供给 L1 的接口 =====
def transformer_block_forward(X, attn_params, mlp_params, ln1_gamma, ln1_beta, ln2_gamma, ln2_beta):
    """
    L2 的最终封装——对 L1 来说，这就是 TransformerBlock 的内部实现
    X: (B, T, C)
    """
    # --- 1. Self-Attention ---
    # Project Q, K, V: X → Q, K, V
    Q, attn_cache_q = linear_forward_with_cache(
        reshape_3d_to_2d(X),             # (B*T, C)
        attn_params['W_q'],
        attn_params['b_q']
    )
    K, attn_cache_k = linear_forward_with_cache(
        reshape_3d_to_2d(X), attn_params['W_k'], attn_params['b_k']
    )
    V, attn_cache_v = linear_forward_with_cache(
        reshape_3d_to_2d(X), attn_params['W_v'], attn_params['b_v']
    )
    # Reshape to multi-head: (B, T, C) → (B, n_head, T, head_dim)
    Q_4d = reshape_to_4d(Q, B, n_head, T, head_dim)
    K_4d = reshape_to_4d(K, B, n_head, T, head_dim)
    V_4d = reshape_to_4d(V, B, n_head, T, head_dim)
    
    # Compute attention
    attn_out_4d, attn_cache = attention_forward(Q_4d, K_4d, V_4d)
    attn_out = reshape_4d_to_3d(attn_out_4d)  # (B, T, C)
    
    # Output projection
    attn_proj, proj_cache = linear_forward_with_cache(
        reshape_3d_to_2d(attn_out),
        attn_params['W_proj'],
        attn_params['b_proj']
    )
    attn_proj = reshape_2d_to_3d(attn_proj, B, T, C)
    X_attn = add(X, attn_proj)  # residual connection
    
    # --- 2. LayerNorm 1 ---
    X_ln1, ln1_cache = layer_norm_forward_with_cache(
        reshape_3d_to_2d(X_attn),  # (B*T, C)
        ln1_gamma, ln1_beta
    )
    X_ln1 = reshape_2d_to_3d(X_ln1, B, T, C)
    
    # --- 3. MLP ---
    h, fc1_cache = linear_forward_with_cache(
        reshape_3d_to_2d(X_ln1),
        mlp_params['fc1']['W'],
        mlp_params['fc1']['b']
    )
    h = gelu(h)
    mlp_out, fc2_cache = linear_forward_with_cache(
        h,
        mlp_params['fc2']['W'],
        mlp_params['fc2']['b']
    )
    mlp_out = reshape_2d_to_3d(mlp_out, B, T, C)
    X_mlp = add(X_attn, mlp_out)  # residual connection
    
    # --- 4. LayerNorm 2 ---
    X_out, ln2_cache = layer_norm_forward_with_cache(
        reshape_3d_to_2d(X_mlp),
        ln2_gamma, ln2_beta
    )
    X_out = reshape_2d_to_3d(X_out, B, T, C)
    
    cache = {
        'attn_q': attn_cache_q, 'attn_k': attn_cache_k, 'attn_v': attn_cache_v,
        'attn': attn_cache, 'proj': proj_cache,
        'ln1': ln1_cache, 'fc1': fc1_cache, 'fc2': fc2_cache, 'ln2': ln2_cache,
        'X': X, 'X_attn': X_attn, 'X_ln1': X_ln1, 'h': h, 'X_mlp': X_mlp
    }
    return X_out, cache

def transformer_block_backward(d_out, cache):
    """
    反向传播：利用 attention_backward + linear_backward 组合
    返回各参数的梯度
    """
    # ... 逐步反向传播，与 forward 的顺序相反 ...
    # d(mlp) → d(fc2) → d(fc1) → d(attention) → d(Q_proj) → d(QKV)
    # 利用 L2 各模块的 backward 接口
    pass
```

---

## L2 → L1 接口：手写正向/反向 → minGPT 层

### L1 如何使用 L2 原语构建完整 GPT 模型

```python
# ===== L1: minGPT 层 — 用 L2 原语构建完整的 GPT 模型 =====

class GPT:
    """
    L1 只关心：组合模块、管理参数、训练循环、生成
    内部计算全部委托给 L2 的 forward/backward 接口
    """
    def __init__(self, vocab_size, block_size, n_layer, n_head, n_embd):
        self.vocab_size = vocab_size
        self.block_size = block_size
        self.n_layer = n_layer
        self.n_head = n_head
        self.n_embd = n_embd
        self.params = self._init_params()
    
    def _init_params(self):
        """初始化所有权重（随机初始化）"""
        # Token embedding: (vocab_size, n_embd)
        wte = init_normal(self.vocab_size, self.n_embd, std=0.02)
        # Position embedding: (block_size, n_embd)
        wpe = init_normal(self.block_size, self.n_embd, std=0.02)
        # ... attention weights, MLP weights, layer norm params ...
        return {...}
    
    def forward(self, idx, targets=None):
        """
        idx: (B, T) token ids
        返回: logits (B, T, vocab_size), loss (optional), cache
        """
        B, T = len(idx), len(idx[0])
        assert T <= self.block_size
        
        # 1. Token + Position Embedding (用 L2 embed 接口)
        tok_emb = gather_rows(self.params['wte'], idx)  # (B, T, C)
        pos_ids = [list(range(T)) for _ in range(B)]
        pos_emb = gather_rows(self.params['wpe'], pos_ids)  # (B, T, C)
        X = add(tok_emb, pos_emb)  # (B, T, C)
        
        # 2. 堆叠 Transformer Blocks（调用 L2 接口）
        all_block_caches = []
        for l in range(self.n_layer):
            blk = self.params['blocks'][l]
            ln = self.params['ln'][l]
            X, block_cache = transformer_block_forward(
                X,
                blk['attn'],    # {W_q, b_q, W_k, b_k, W_v, b_v, W_proj, b_proj}
                blk['mlp'],     # {fc1: {W, b}, fc2: {W, b}}
                ln[0], ln[1],   # ln1 gamma, beta
                ln[2], ln[3]    # ln2 gamma, beta
            )
            all_block_caches.append(block_cache)
        
        # 3. Final LayerNorm
        X_flat = reshape_3d_to_2d(X)  # (B*T, C)
        X_norm = layer_norm(X_flat, self.params['ln_f_gamma'], self.params['ln_f_beta'])
        
        # 4. LM Head: (B*T, C) @ (C, V) → (B*T, V)
        logits, lm_cache = linear_forward_with_cache(
            X_norm,
            self.params['lm_head_W'],  # (C, V)
            self.params['lm_head_b']   # (1, V)
        )
        logits = reshape_2d_to_3d(logits, B, T, self.vocab_size)  # (B, T, V)
        
        # 5. Loss
        loss = None
        if targets is not None:
            loss = cross_entropy(logits, targets)  # L2/L3 原语
        
        cache = {
            'idx': idx, 'tok_emb': tok_emb, 'pos_emb': pos_emb,
            'X_flat': X_flat, 'X_norm': X_norm, 'lm_cache': lm_cache,
            'block_caches': all_block_caches, 'logits': logits
        }
        return logits, loss, cache
    
    def backward(self, loss, cache):
        """完整反向传播：从 loss 一直反传到 embedding"""
        # 1. Cross entropy backward → d_logits
        d_logits = cross_entropy_backward(loss, self.params, cache)
        
        # 2. LM Head backward
        d_X_norm, d_W_lm, d_b_lm = linear_backward(
            reshape_3d_to_2d(d_logits),
            cache['lm_cache']
        )
        
        # 3. Final LayerNorm backward
        d_X_flat = layer_norm_backward(d_X_norm, cache['ln_f_cache'])
        d_X = reshape_2d_to_3d(d_X_flat, B, T, self.n_embd)
        
        # 4. 反向遍历 Transformer Blocks
        d_params = {}
        for l in reversed(range(self.n_layer)):
            d_X, block_grads = transformer_block_backward(
                d_X, cache['block_caches'][l]
            )
            for k, v in block_grads.items():
                d_params[f'block_{l}_{k}'] = v
        
        # 5. Embedding backward
        d_wte, d_wpe = embedding_backward(d_X, cache['idx'], cache['tok_emb'], cache['pos_emb'])
        d_params['wte'] = d_wte
        d_params['wpe'] = d_wpe
        
        return d_params
    
    def update_params(self, grads, lr):
        """SGD: param -= lr * grad"""
        for name in self.params:
            self.params[name] = sub(self.params[name], mul_scalar(grads[name], lr))
    
    def generate(self, idx, max_new_tokens, temperature=1.0):
        """
        L1 纯上层逻辑：自回归采样
        """
        for _ in range(max_new_tokens):
            # 截断到 block_size
            if len(idx[0]) > self.block_size:
                idx_cond = [row[-self.block_size:] for row in idx]
            else:
                idx_cond = idx
            
            logits, _, _ = self.forward(idx_cond)  # 调用 forward → L2
            
            # 取最后一个位置的 logits
            logits_last = [row[-1:] for row in logits]  # (B, 1, V)
            logits_last = reshape_3d_to_2d(logits_last)  # (B, V)
            
            # Temperature scaling + softmax
            scaled = div(logits_last, temperature)
            probs = softmax(scaled)
            
            # 采样
            next_token = sample_multinomial(probs)  # (B, 1)
            
            # 拼接
            idx = concat_2d(idx, next_token)
        
        return idx
```

### L1 训练循环

```python
def train(gpt, data, epochs, lr, batch_size, sequence_length):
    """
    完整的训练循环
    """
    for epoch in range(epochs):
        # 1. 采样一个 batch
        idx, targets = sample_batch(data, batch_size, sequence_length)
        
        # 2. 前向传播（调用 L1 → L2）
        logits, loss, cache = gpt.forward(idx, targets)
        
        # 3. 反向传播（L1 → L2）
        grads = gpt.backward(loss, cache)
        
        # 4. 参数更新
        gpt.update_params(grads, lr)
        
        # 5. 日志
        print(f"Epoch {epoch}, Loss: {loss}")
```

---

## 各层验证方法

每完成一层，用**下一层已验证通过的实现**或**PyTorch 官方实现**来交叉验证当前层：

### L4 验证

```python
# L4 完成后:
result = L4.add(A, B)
expected = [[A[i][j] + B[i][j] for j ...]]
assert result == expected  # 100% 等价 ✓
```

### L3 验证

```python
import numpy as np
import torch

# L3.matmul(A, B) vs np.matmul(A, B) → allclose ✓
# L3.softmax(X)   vs torch.softmax(X)  → 数值相同 ✓
```

### L2 验证

```python
# L2.attention_forward(Q, K, V) vs torch.nn.functional.scaled_dot_product_attention
# → 数值一致 ✓

# L2.linear_backward(d_out) vs torch.autograd.grad
# → 梯度一致（用 gradcheck） ✓
```

### L1 验证

```python
# GPT.forward(idx) vs minGPT.forward(idx) → 输出一致 ✓
# GPT.generate() → 输出可读莎士比亚风格文本 ✓
```

### 终极验证

**L1 的训练过程中 loss 曲线，L1+L2+L3+L4 全栈实现与纯 PyTorch 实现完全重合。** 做到这一步，你对 Transformer 的理解就是骨骼级别的了。

---

## 推荐学习节奏

如果业余时间学：

```
Week 1:   L1 — minGPT 读懂跑通，理解每个张量的形状 (B, T, C)
Week 2-3: L2 — 手写 forward+backward，用 autograd.gradcheck 验证
Week 4-5: L3 — 实现自己的 matmul 和 batch matmul
Week 6-7: L4 — 纯 Python 标量实现（极小型验证即可）
```

**总计 6-8 周业余时间**。全职的话 3-4 周足够。

---

## 一句话总结

**nanoGPT + Colab 免费 T4 + tiny Shakespeare = 零成本入门 Transformer，几小时就能看到自己的模型生成文本。**

验证架构用 CPU + 100 字符过拟合，5 分钟就能确认你的 Attention、Multi-Head、FFN、LayerNorm 全部写对。

四层深度的关键觉悟：**L2 完成后你已经理解了 Transformer 的数学本质。L3/L4 更多是系统/性能理解。** 如果想继续深入，只对 Attention 模块做 L3/L4 即可——FFN 和 LayerNorm 在这一层面没有新概念。
