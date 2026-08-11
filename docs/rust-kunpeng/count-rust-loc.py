#!/usr/bin/env python3
"""统计 rust-lang/rust 代码行数，按编译器/标准库/测试/其他分类，按语言细分。

用法: python3 count-rust-loc.py [RUST_REPO] [OUTPUT_MD]
依赖: tokei (cargo install tokei)
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_tokei(path: Path, exclude: list[str] | None = None) -> dict:
    """运行 tokei 并返回 JSON 统计结果"""
    cmd = ["tokei", "--output", "json"]
    if exclude:
        for d in exclude:
            cmd.extend(["--exclude", d])
    cmd.append(str(path))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"tokei 错误: {result.stderr}", file=sys.stderr)
        return {}
    return json.loads(result.stdout)


def git_info(repo: Path) -> dict:
    """获取 git 仓库元信息"""
    def git(args: list[str]) -> str:
        return subprocess.run(
            ["git", "-C", str(repo)] + args,
            capture_output=True, text=True
        ).stdout.strip()

    return {
        "url": git(["remote", "get-url", "origin"]),
        "branch": git(["branch", "--show-current"]),
        "commit_full": git(["rev-parse", "HEAD"]),
        "commit_short": git(["rev-parse", "--short", "HEAD"]),
        "commit_date": git(["log", "-1", "--format=%ad", "--date=short", "HEAD"]),
        "commit_subject": git(["log", "-1", "--format=%s", "HEAD"]),
    }


def extract_langs(data: dict) -> dict[str, dict]:
    """提取每种语言的 code 行数，排除 code=0 的类型（如 Markdown）"""
    result = {}
    for lang, stats in sorted(data.items(), key=lambda x: x[1]["code"], reverse=True):
        if lang == "Total":
            continue
        if stats["code"] > 0:
            result[lang] = {
                "code": stats["code"],
                "blanks": stats["blanks"],
                "comments": stats["comments"],
            }
    return result


def fmt(n: int) -> str:
    return f"{n:,}"


def render_category_table(title: str, data: dict, total: int) -> str:
    """渲染单个分类的 Markdown 表格"""
    lines = [f"### {title}（共 {fmt(total)} 行）\n"]
    lines.append("| 语言 | 代码行数 | 空行 | 注释行 | 占比 |")
    lines.append("|------|---------|------|--------|------|")
    for lang, stats in sorted(data.items(), key=lambda x: x[1]["code"], reverse=True):
        pct = stats["code"] / total * 100 if total > 0 else 0
        lines.append(
            f"| {lang} | {fmt(stats['code'])} | {fmt(stats['blanks'])} "
            f"| {fmt(stats['comments'])} | {pct:.1f}% |"
        )
    lines.append("")
    return "\n".join(lines)


def main():
    rust_repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/suine/projects/rust")
    output_md = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("rust-loc-report.md")

    if not (rust_repo / ".git").exists():
        print(f"错误: {rust_repo} 不是有效的 git 仓库", file=sys.stderr)
        sys.exit(1)

    # 获取 git 信息
    info = git_info(rust_repo)
    print(f"仓库: {info['url']}")
    print(f"分支: {info['branch']}  Commit: {info['commit_short']}  ({info['commit_date']})")

    # 四个分类运行 tokei
    print("统计 compiler/ ...")
    compiler_raw = run_tokei(rust_repo / "compiler")
    print("统计 library/ ...")
    library_raw = run_tokei(rust_repo / "library")
    print("统计 tests/ ...")
    tests_raw = run_tokei(rust_repo / "tests")
    print("统计 其他 ...")
    other_raw = run_tokei(
        rust_repo,
        exclude=["compiler", "library", "tests", "target", ".git"],
    )

    def dir_loc(subpath: str) -> int:
        raw = run_tokei(rust_repo / subpath)
        return raw.get("Total", {}).get("code", 0)

    print("统计 src/ 子目录 ...")
    src_breakdown = {}
    for d in sorted((rust_repo / "src").iterdir()):
        if d.is_dir() and d.name not in ("llvm-project", "gcc"):
            src_breakdown[d.name] = dir_loc(f"src/{d.name}")

    print("统计主要工具 ...")
    tools_detail = {
        "rust-analyzer": dir_loc("src/tools/rust-analyzer"),
        "clippy": dir_loc("src/tools/clippy"),
        "miri": dir_loc("src/tools/miri"),
        "rustfmt": dir_loc("src/tools/rustfmt"),
    }

    # 提取语言统计数据
    categories = {
        "编译器 — compiler/": extract_langs(compiler_raw),
        "标准库 — library/": extract_langs(library_raw),
        "测试 — tests/": extract_langs(tests_raw),
        "其他（src/, 工具链, 文档, CI 等）": extract_langs(other_raw),
    }

    totals = {k: sum(v["code"] for v in d.values()) for k, d in categories.items()}
    grand_total = sum(totals.values())

    # 构建语言 × 分类总览表
    all_langs: dict[str, dict[str, int]] = {}
    for cat_name, cat_data in categories.items():
        for lang, stats in cat_data.items():
            if lang not in all_langs:
                all_langs[lang] = dict.fromkeys(categories.keys(), 0)
            all_langs[lang][cat_name] = stats["code"]

    lang_order = sorted(all_langs.keys(), key=lambda x: sum(all_langs[x].values()), reverse=True)

    # ---- 生成 Markdown 报告 ----
    report = f"""# Rust 编译器代码统计报告

> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 仓库信息

| 项目 | 内容 |
|------|------|
| 代码仓 | [{info['url']}]({info['url']}) |
| 分支 | `{info['branch']}` |
| Commit | `{info['commit_short']}` |
| Commit 完整 ID | `{info['commit_full']}` |
| 提交日期 | {info['commit_date']} |
| 提交说明 | {info['commit_subject']} |

## 总览

| 分类 | 代码行数 | 占比 |
|------|---------|------|
| 编译器 (compiler/) | {fmt(totals['编译器 — compiler/'])} | {totals['编译器 — compiler/']/grand_total*100:.1f}% |
| 标准库 (library/) | {fmt(totals['标准库 — library/'])} | {totals['标准库 — library/']/grand_total*100:.1f}% |
| 测试 (tests/) | {fmt(totals['测试 — tests/'])} | {totals['测试 — tests/']/grand_total*100:.1f}% |
| 其他 | {fmt(totals['其他（src/, 工具链, 文档, CI 等）'])} | {totals['其他（src/, 工具链, 文档, CI 等）']/grand_total*100:.1f}% |
| **合计** | **{fmt(grand_total)}** | **100.0%** |

## 按语言 × 分类总览

| 语言 | 编译器 | 标准库 | 测试 | 其他 | 合计 | 占比 |
|------|--------|--------|------|------|------|------|
"""

    # 取短的分类名用于表头
    short_names = {
        "编译器 — compiler/": "编译器",
        "标准库 — library/": "标准库",
        "测试 — tests/": "测试",
        "其他（src/, 工具链, 文档, CI 等）": "其他",
    }

    for lang in lang_order:
        row = all_langs[lang]
        lang_total = sum(row.values())
        cells = [fmt(row[cat]) for cat in categories.keys()]
        report += (
            f"| {lang} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} "
            f"| {fmt(lang_total)} | {lang_total/grand_total*100:.1f}% |\n"
        )

    report += f"""
## 详细分类

{render_category_table('编译器 — compiler/', categories['编译器 — compiler/'], totals['编译器 — compiler/'])}
{render_category_table('标准库 — library/', categories['标准库 — library/'], totals['标准库 — library/'])}
{render_category_table('测试 — tests/', categories['测试 — tests/'], totals['测试 — tests/'])}
{render_category_table('其他（src/, 工具链, 文档, CI 等）', categories['其他（src/, 工具链, 文档, CI 等）'], totals['其他（src/, 工具链, 文档, CI 等）'])}
"""

    report += """---
*本报告由脚本自动生成，统计工具：[tokei](https://github.com/XAMPPRocky/tokei)*
"""

    output_md.write_text(report, encoding="utf-8")
    print(f"\n报告已生成: {output_md}")
    print(f"总计 {fmt(grand_total)} 行代码")


if __name__ == "__main__":
    main()
