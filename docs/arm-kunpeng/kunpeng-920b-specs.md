# Kunpeng 920B 硬件信息

> 采集时间: 2026-08-03 | 主机: `wheel@192.168.41.50`

## 概述

| 参数 | 值 |
|------|-----|
| 架构 | aarch64 (ARMv8) |
| 厂商 | HiSilicon |
| Implementer / Part | 0x48 / 0xd02 |
| 内核版本 | 6.6.0-132 (openEuler 24.03 SP3) |

## 核心配置

| 参数 | 值 |
|------|-----|
| 总逻辑核心 | 320 (2 sockets × 80 cores × 2 threads) |
| Socket 数 | 2 |
| 每 Socket 核心数 | 80 |
| 每核心线程数 | 2 (SMT) |
| 最大频率 | 2.9 GHz |
| 最小频率 | 400 MHz |

## 缓存层级

| 缓存 | 大小/实例 | 实例数 | 共享范围 | 总大小 |
|------|----------|--------|---------|--------|
| L1d | 64 KB | 160 | 每 2 线程 | 10 MiB |
| L1i | 64 KB | 160 | 每 2 线程 | 10 MiB |
| L2 | 1280 KB (1.25 MB) | 160 | 每 2 线程 | 200 MiB |
| L3 | 71680 KB (70 MB) | 4 | 每 NUMA node (80 核) | 280 MiB |

## NUMA 拓扑

| NUMA Node | CPU 范围 | 内存 | 当前空闲 |
|-----------|---------|------|---------|
| Node 0 | 0–79 | 128 GB | ~4 GB |
| Node 1 | 80–159 | 128 GB | ~7 GB |
| Node 2 | 160–239 | 128 GB | ~46 GB |
| Node 3 | 240–319 | 129 GB | ~7 GB |
| **总计** | — | **502 GB** | — |

NUMA 距离矩阵：

| | Node 0 | Node 1 | Node 2 | Node 3 |
|---|--------|--------|--------|--------|
| **Node 0** | 10 | 12 | 35 | 37 |
| **Node 1** | 12 | 10 | 37 | 40 |
| **Node 2** | 35 | 37 | 10 | 12 |
| **Node 3** | 37 | 40 | 12 | 10 |

Node 0↔1 和 Node 2↔3 为 socket 内部通信（距离 ~12），跨 socket 通信（距离 35–40）。

## CPU 指令集特性 (Flags)

### 基础
`fp asimd evtstrm aes pmull sha1 sha2 crc32 atomics`

### SIMD / 向量
| Flag | 含义 |
|------|------|
| `asimd` | NEON (Advanced SIMD) |
| `asimdhp` | NEON half-precision (f16) |
| `asimddp` | NEON dot product |
| `asimdfhm` | NEON FMLAL/FMLSL (f16 multiply-add) |
| `sve` | Scalable Vector Extension |
| `svei8mm` | SVE Int8 matrix multiply |
| `svef32mm` | SVE f32 matrix multiply |
| `svef64mm` | SVE f64 matrix multiply |
| `svebf16` | SVE bfloat16 |
| `i8mm` | Int8 matrix multiply |
| `bf16` | Bfloat16 |

### 加密 / Hash
| Flag | 含义 |
|------|------|
| `aes` | AES 加密 |
| `pmull` | 多项式乘法 (GHASH) |
| `sha1 sha2 sha3 sha512` | SHA 系列硬件加速 |
| `sm3 sm4` | 国密 SM3/SM4 |
| `crc32` | CRC32C 硬件指令 ⭐ |

### 原子操作
| Flag | 含义 |
|------|------|
| `atomics` | LSE (Large System Extensions) 原子指令 |
| `lrcpc` | LRCPC (Release Consistent processor consistent) |
| `ilrcpc` | 增强版 LRCPC |

### 其他
`cpuid jscvt fcma dcpop ssbs sb dcpodp flagm flagm2 frint dit uscat dgh rng ecv`

## SVE 参数

| 参数 | 值 |
|------|-----|
| SVE 向量宽度 | **256 bits (32 bytes)** |
| 每向量 f32 lane 数 | 8 |
| 每向量 f64 lane 数 | 4 |
| 每向量 i8 lane 数 | 32 |

## 对 Daft 优化的影响

| 优化项 | 920B 可用 | 说明 |
|--------|---------|------|
| B6/B11 CRC32C hash | ✅ | `crc32` flag 已确认 |
| C7 SVE UTF-8 length | ✅ | `sve` + 256-bit 宽度 |
| C9 SVE gather | ✅ | `sve` + `svei8mm` |
| E3 BoostKit x265 | ✅ | SVE 已确认，需确认 BoostKit 安装 |
| A5 UDF NUMA 调度 | ✅ | 4 NUMA nodes，跨 socket 延迟 3-4x |
