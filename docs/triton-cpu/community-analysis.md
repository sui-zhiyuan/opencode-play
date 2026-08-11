# Triton-CPU 社区活跃度分析

> 分析时间：2026-08-11 | 数据来源：[gitcode.com/openeuler/triton-cpu](https://gitcode.com/openeuler/triton-cpu)

## 项目概况

| 指标 | 数值 |
|------|------|
| Stars | 3 |
| Forks | 20 |
| Members | 63 |
| Open Issues | 2 |
| Open PRs | 15 |

## 活跃开发者

**总计 30 名唯一活跃开发者**（参与 Issue / PR / Review）：

- Issue 作者：5 人 —— `chenzheng1030`, `gcw_KBBvCc3Q`, `Nujaa`, `lebu26`, `maijiahong2025`
- PR 作者：19 人 —— 核心贡献者包括 `huangkaiyao1`, `muneebkhan`, `guowanze`, `Nujaa`, `lebu26` 等
- Review Team：9 人 —— `SegFault`, `alexanderbill`, `cf-zhao`, `chenzheng1030`, `eastb233`, `kuenking111_admin`, `li-yancheng`, `wangqiang95`, `wd-gitcode`

> 注：Review Team 为项目级 CODEOWNERS，所有 PR 共享同一组审批人。实际 Merge 由 `openeuler-ci-bot` 执行。

## Issue 平均关闭时间

| 总计 | 8（Open: 2, Closed: 6） |
|------|--------------------------|
| 平均关闭时间 | **76.3 天** |
| 中位关闭时间 | **83.6 天** |

各 Issue 关闭耗时：

| Issue | 作者 | 创建时间 | 关闭时间 | 耗时 |
|-------|------|----------|----------|------|
| #1 | maijiahong2025 | 2025-10-27 | 2026-05-14 | 199.1 天 |
| #2 | lebu26 | 2026-02-17 | 2026-05-14 | 86.5 天 |
| #3 | lebu26 | 2026-02-20 | 2026-05-14 | 83.6 天 |
| #4 | lebu26 | 2026-02-21 | 2026-05-14 | 81.8 天 |
| #6 | Nujaa | 2026-05-13 | 2026-05-14 | 0.6 天 |
| #7 | gcw_KBBvCc3Q | 2026-06-27 | 2026-07-03 | 6.3 天 |

> ⚠️ #1~#4 于 2026-05-14 批量关闭，拉高了均值。排除最极端值 #1 后，平均约 51.7 天。

## PR 分析（2026年7月）

| 指标 | 数量 |
|------|------|
| 7月新创建 PR | **12** |
| 7月被合入 PR | **9**（含 4 个 7月前创建） |
| 7月活跃 PR 总数 | **16** |

7月 PR 详情：

| PR | 标题 | 作者 | 状态 | Notes |
|----|------|------|------|-------|
| !195 | Add accuracy test for dropout | daytrick | opened | 8 |
| !196 | Enable moe_align_block_size_triton benchmark | huangkaiyao1 | merged | 22 |
| !197 | Vendor ArmPL library under third_party/armpl | muneebkhan | merged | 36 |
| !198 | Enable flash_attn_varlen_func benchmark | huangkaiyao1 | merged | 15 |
| !199 | Add linalg level canonicalization | Nujaa | opened | 5 |
| !200 | silu_and_mul kernel optimization | NathanaelW | opened | 26 |
| !201 | Vendor ArmPL (Supersedes #197) | huangkaiyao1 | merged | 12 |
| !202 | Enable get_scheduler_metadata benchmark | huangkaiyao1 | merged | 12 |
| !203 | FlagGems bug fixes + fast path | guowanze | merged | 15 |
| !204 | Sync fused operator benchmark | gcw_KBBvCc3Q | closed | 12 |
| !205 | Fix ARMPL optimization pass | muneebkhan | opened | 142 |
| !206 | Fix ARMPL optimization pass (retry) | muneebkhan | merged | 19 |

## Review 分析（2026年7月）

| 指标 | 数值 |
|------|------|
| Review Team 规模 | 9 人 |
| 7月 Review 通过的 PR | 9 |
| 7月 Review 讨论量 | **456** notes/comments |

Review Team 全员：

`SegFault`, `alexanderbill`, `cf-zhao`, `chenzheng1030`, `eastb233`, `kuenking111_admin`, `li-yancheng`, `wangqiang95`, `wd-gitcode`

> 注：所有 PR 的 Approver 列表完全一致（9 人），说明这是项目级的 CODEOWNERS 配置。实际的 code review 讨论发生在每个 PR 的 notes/comments 中（7月共 456 条）。

---

*数据通过调用 GitCode API 获取，分析脚本见 [`analyze_repo.py`](analyze_repo.py)*
