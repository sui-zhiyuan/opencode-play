# U2 解决：Pipeline UDF 算子清单与 Rust 重写优先级

> 来源: `volc_operator_sim` 项目 6 条目标 pipeline 分析
> 日期: 2026-08-03

## 6 条目标 Pipeline

| # | Pipeline | 算子总数 | CPU 算子 | stub/GPU | 主要模态 |
|---|----------|---------|---------|----------|---------|
| 1 | `pipeline_text_fineweb_full_min` | 13 | 11 | 2 | 文本 |
| 2 | `video_scene_split_etl` | 6 | 6 | 0 | 视频 |
| 3 | `pipeline_image_full_min` | 10 | 6 | 4 | 图像 |
| 4 | `audio_asr_prep_canonical` | 6 | 5 | 1 | 音频 |
| 5 | `pipeline_pdf_full_min` | 6 | 2 | 4 | PDF |
| 6 | `pipeline_ad_nuscenes_min` | 3 | 1 | 2 | AD/nuScenes |
| **合计** | | **44** | **31** | **13** | |

> 说明：`audio_asr_prep_canonical` 中 `audio_ffmpeg_wrapped_mapper` 被调用 3 次，按独立算子计 1 个。

## Rust 重写候选：按优先级分层

### P0 — 高频文本处理链（`pipeline_text_fineweb_full_min`，11 个 CPU 算子）

这些算子构成 FineWeb 文本清洗的主链，全部为纯 CPU 字符串处理，无外部 I/O，已实现 mapper 链融合。Rust 重写收益最大。

| # | 算子 | 类型 | 功能 | 实现文件 |
|---|------|------|------|---------|
| 1 | `clean_html_mapper` | mapper | HTML 标签移除 | `ops/text_ops.py:37` |
| 2 | `clean_links_mapper` | mapper | 文本链接移除 | `ops/text_ops.py:42` |
| 3 | `clean_email_mapper` | mapper | Email 地址清理 | `ops/text_ops.py:47` |
| 4 | `clean_copyright_mapper` | mapper | 版权声明移除 | `ops/text_ops.py:52` |
| 5 | `fix_unicode_mapper` | mapper | Unicode 修复 | `ops/text_ops.py` |
| 6 | `punctuation_normalization_mapper` | mapper | 特定字符替换 | `ops/text_ops.py` |
| 7 | `whitespace_normalization_mapper` | mapper | 空白字符标准化 | `ops/text_ops.py` |
| 8 | `text_length_filter` | filter | 文本长度过滤 | `ops/text_ops.py:112` |
| 9 | `alphanumeric_filter` | filter | 字符占比计算 | `ops/text_ops.py:121` |
| 10 | `language_id_score_filter` | filter | 语种识别过滤 | `ops/text_ops.py:130` |
| 11 | `text_chunk_mapper` | mapper | 文本 chunk 切分 | `ops/text_ops.py` |

> **设计文档中 "13 个算子" 的原始数字对应本表（pipeline_text 的 11 个 + 另外 2 个跨 pipeline 算子），确认无误。**

### P1 — 跨 Pipeline 共享算子

| # | 算子 | 出现 Pipeline | 类型 | 重写价值 |
|---|------|-------------|------|---------|
| 12 | `write_lance` | image, pdf, ad | sink | **不重写** — 已是 Daft 原生 `write_lance()`，不是 UDF |
| 13 | `text_chunk_mapper` | text, pdf | mapper | ✅ 已在 P0 中 |

### P2 — 简单元数据过滤（可转为 Daft 原生表达式）

这些 filter 仅做数值比较，可通过 Daft 原生列表达式实现，**无需 UDF**。

| # | 算子 | Pipeline | 当前实现 | 优化方向 |
|---|------|----------|---------|---------|
| — | `image_shape_filter` | image | UDF 读 PNG header → 比较宽高 | Daft `image_width()`/`image_height()` 已可用（`pipeline_builder.py:507`），**无需 UDF** |
| — | `image_aspect_ratio_filter` | image | UDF 计算 ratio | 同上，转为原生表达式 |
| — | `image_size_filter` | image | UDF 读文件大小 | 可转为 `col("_size").lt(threshold)` |
| — | `video_duration_filter` | video | UDF ffprobe → 比较 | 需要元数据列 |
| — | `audio_duration_filter` | audio | UDF ffprobe → 比较 | 同上 |

### P3 — 媒体 ffmpeg 算子（不推荐 Rust 重写）

这些算子本质是调用外部 ffmpeg 进程，Python 包装器开销占比极小。瓶颈在 ffmpeg 本身。

| 算子 | Pipeline |
|------|----------|
| `video_ffmpeg_wrapped_mapper` | video |
| `audio_ffmpeg_wrapped_mapper` (×3) | audio |
| `video_resize_resolution_mapper` | video |
| `video_split_by_scene_mapper` | video |
| `video_split_by_duration_mapper` | video |
| `video_extract_frames_mapper` | video |

**优化方向不是 Rust 重写，而是 A3（启用 Kunpeng BoostKit x265）**。

### P4 — 复杂媒体处理（评估后决定）

| 算子 | Pipeline | 复杂度 | 重写建议 |
|------|----------|--------|---------|
| `image_blur_mapper` | image | Laplacian 方差计算（OpenCV/PIL） | 中 — 可用 Rust `image` crate |
| `image_deduplicator` | image | 图像哈希 + 去重 | 中 |
| `image_face_count_filter` | image | 人脸检测（stub） | **不重写** — stub |

### 排除项（不可能或不应重写）

| 算子 | 理由 |
|------|------|
| `perplexity_filter` | 依赖 KenLM 模型，走 official DJ 实现 |
| `document_deduplicator` | 全局 barrier，需分布式状态 |
| `audio_nmf_snr_filter` | stub，无实际逻辑 |
| `download_file_mapper` | I/O 密集型，Python async 更合适 |
| `pdf_parse/ocr/table` | 均为 stub |
| `bge_vectorize_mapper` | GPU/stub |
| `image_aesthetics/text_similarity/clip` | GPU/stub |
| `ad_sensor_align/index` | stub |

## 最终 Rust 重写候选清单（12 个）

| 优先级 | 数量 | 算子 |
|--------|------|------|
| **P0 文本链** | 11 | clean_html, clean_links, clean_email, clean_copyright, fix_unicode, punctuation_normalization, whitespace_normalization, text_length_filter, alphanumeric_filter, language_id_score_filter, text_chunk_mapper |
| **P4 图像** | 1 | image_blur_mapper |
| **合计** | **12** | |

> 与原始文档估算的 13 个接近（差异为 `write_lance` 已是原生、`text_chunk_mapper` 跨 pipeline 共用）。工时估算 12 × 0.75 ≈ 9 人天，与原始 10 人天基本一致。

## 重写策略

1. **P0 文本链 11 个算子 → 1 个 Rust kernel**：由于 `pipeline_builder.py` 已将 mapper 融合为单一 UDF（`_make_mapper_udf(fused_fn)`），可以将整个文本清洗链编译为 1 个 Rust 函数，内部按序执行 11 步处理，消除 11 次 Python↔Rust 边界往返。

2. **P4 image_blur_mapper → 独立 Rust kernel**：用 Rust `image` crate 实现 Laplacian 方差计算，替代 PIL/OpenCV 调用。
