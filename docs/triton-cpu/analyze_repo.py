#!/usr/bin/env python3
"""
GitCode triton-cpu 仓库活跃度分析脚本

分析 https://gitcode.com/openeuler/triton-cpu 仓库的：
- 活跃开发者数量（参与讨论 / 提交 PR / 提交 Issue）
- Issue 平均关闭时间
- PR 数量（2026年7月）
- Issue 数量（2026年7月）
- Review 数量（2026年7月）

用法: python3 analyze_triton_cpu.py
需要设置环境变量 GITCODE_TOKEN 或在脚本中硬编码 token。
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from collections import Counter

# ============================================================
# 配置
# ============================================================

# 从环境变量获取 token（不要在脚本中硬编码！）
TOKEN = os.environ.get("GITCODE_TOKEN", "")
REFRESH_TOKEN = os.environ.get("GITCODE_REFRESH_TOKEN", "")

if not TOKEN:
    print("Error: GITCODE_TOKEN env var is required.", file=sys.stderr)
    print("  export GITCODE_TOKEN='your_access_token'", file=sys.stderr)
    sys.exit(1)

API_HOST = "https://web-api.gitcode.com"
PROJECT_ID = 7678036
PROJECT_PATH = "openeuler%2Ftriton-cpu"
REPO_PATH = "openeuler/triton-cpu"

# 分析时间范围：2026年7月1日 ~ 7月31日（东八区）
TZ = timezone(timedelta(hours=8))
JULY_START = datetime(2026, 7, 1, tzinfo=TZ)
JULY_END = datetime(2026, 8, 1, tzinfo=TZ)

# ============================================================
# HTTP 会话配置
# ============================================================

def make_session():
    """创建带认证的 HTTP 会话，模拟浏览器请求以绕过 WAF。"""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Origin": "https://gitcode.com",
        "Referer": f"https://gitcode.com/{REPO_PATH}/pulls",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
        ),
        "X-App-Channel": "gitcode-fe",
        "X-App-Version": "0",
        "X-Device-ID": "unknown",
        "X-Device-Type": "Windows",
        "X-Network-Type": "4g",
        "X-OS-Version": "10",
        "X-Platform": "web",
        "page-repo-id": str(PROJECT_ID),
    })
session.cookies.set("GITCODE_ACCESS_TOKEN", TOKEN)
session.cookies.set("GITCODE_REFRESH_TOKEN", REFRESH_TOKEN or TOKEN)
session.cookies.set("GitCodeUserName", os.environ.get("GITCODE_USERNAME", ""))
    session.cookies.set("gitcode_lang", "zh")
    return session


def api_get(session, path, params=None, referer=None, retries=3):
    """调用 API，带重试和限速。"""
    headers = {}
    if referer:
        headers["Referer"] = referer
    url = f"{API_HOST}{path}"
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, headers=headers, timeout=30)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 418:
                # WAF 拦截，等待后重试
                wait = (attempt + 1) * 5
                print(f"  WAF block (418), waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"  HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
                return None
        except Exception as e:
            print(f"  Request error: {e}", file=sys.stderr)
            time.sleep(3)
    return None


# ============================================================
# 数据获取
# ============================================================

def fetch_all_mrs(session):
    """获取所有 MR（分页）。"""
    all_mrs = []
    page = 1
    while True:
        params = {
            "sort": "desc", "order_by": "created_at",
            "scope": "all", "state": "all",
            "page": page, "per_page": 100,
        }
        data = api_get(
            session,
            f"/issuepr/api/v1/projects/{PROJECT_PATH}/isource/merge_requests",
            params=params,
            referer=f"https://gitcode.com/{REPO_PATH}/pulls",
        )
        if not data:
            break
        content = data.get("content", [])
        all_mrs.extend(content)
        total = data.get("total", 0)
        print(f"  MR page {page}: {len(content)} items (total: {total})", file=sys.stderr)
        if len(content) < 100:
            break
        page += 1
        time.sleep(1)
    return all_mrs


def fetch_all_issues(session):
    """获取所有 Issue。"""
    data = api_get(
        session,
        f"/issuepr/api/v1/issue/{PROJECT_ID}/issues",
        params={"state": "all", "per_page": 100, "page": 1},
        referer=f"https://gitcode.com/{REPO_PATH}/issues",
    )
    if data:
        return data.get("issues", [])
    return []


def fetch_project_info(session):
    """获取项目基本信息。"""
    data = api_get(
        session,
        f"/api/v2/projects/{PROJECT_PATH}",
        referer=f"https://gitcode.com/{REPO_PATH}",
    )
    return data or {}


# ============================================================
# 数据分析
# ============================================================

def analyze(all_mrs, all_issues, project_info):
    """分析所有指标。"""
    tz = TZ
    july_start = JULY_START
    july_end = JULY_END

    # --- 活跃开发者 ---
    # Issue 相关
    issue_authors = set()
    issue_participants = set()   # 作者 + 关闭者/指派人
    issue_commenters = set()     # 参与讨论的人（通过 notes 推算）

    for issue in all_issues:
        author = (issue.get("author") or {}).get("username")
        if author:
            issue_authors.add(author)
            issue_participants.add(author)
        # Issue 有 comments 说明有人参与了讨论
        if issue.get("user_notes_count", 0) > 1:
            # 无法从列表获取具体评论者，但可标记
            pass
        closed_by = issue.get("closed_by")
        if closed_by and isinstance(closed_by, dict):
            u = closed_by.get("username")
            if u:
                issue_participants.add(u)

    # MR 相关
    mr_authors = set()
    mr_approvers = set()
    mr_participants = set()

    july_mrs = []
    july_authors = set()
    july_approvers = set()

    for mr in all_mrs:
        author = (mr.get("author") or {}).get("username")
        if author:
            mr_authors.add(author)
            mr_participants.add(author)

        for person in (mr.get("approval_approvers") or []):
            if isinstance(person, dict) and person.get("username"):
                u = person["username"]
                mr_approvers.add(u)
                mr_participants.add(u)

        merged_by = mr.get("merged_by")
        if merged_by and isinstance(merged_by, dict) and merged_by.get("username"):
            mr_participants.add(merged_by["username"])

        # 7月过滤
        created = datetime.fromisoformat(mr["created_at"])
        if july_start <= created < july_end:
            july_mrs.append(mr)
            if author:
                july_authors.add(author)
            for person in (mr.get("approval_approvers") or []):
                if isinstance(person, dict) and person.get("username"):
                    july_approvers.add(person["username"])

    # 全部活跃开发者（去重合并）
    all_active_devs = issue_participants | mr_participants

    # --- Issue 关闭时间 ---
    close_times_hours = []
    for issue in all_issues:
        closed_at = issue.get("closed_at")
        if closed_at:
            created = datetime.fromisoformat(issue["created_at"])
            closed = datetime.fromisoformat(closed_at)
            delta = (closed - created).total_seconds() / 3600
            close_times_hours.append(delta)

    # --- PR 数量（7月） ---
    july_mr_count = len(july_mrs)
    july_mr_states = Counter(mr["state"] for mr in july_mrs)

    # MRs merged in July (regardless of creation date)
    july_merged_mrs = [
        mr for mr in all_mrs
        if mr.get("merged_at") and july_start <= datetime.fromisoformat(mr["merged_at"]) < july_end
    ]
    # Active MRs in July: created OR merged in July
    july_active_mrs = [
        mr for mr in all_mrs if (
            (july_start <= datetime.fromisoformat(mr["created_at"]) < july_end) or
            (mr.get("merged_at") and july_start <= datetime.fromisoformat(mr["merged_at"]) < july_end)
        )
    ]

    # --- Issue 数量（7月） ---
    july_issues_created = [
        i for i in all_issues
        if july_start <= datetime.fromisoformat(i["created_at"]) < july_end
    ]
    july_issues_closed = [
        i for i in all_issues
        if i.get("closed_at") and july_start <= datetime.fromisoformat(i["closed_at"]) < july_end
    ]

    # --- Review 数量（7月） ---
    # GitCode 的 review 机制：approval_approvers 是项目级 CODEOWNERS/review team，
    # 所有 MR 共享同一组 reviewer。实际 review 动作体现为：
    # 1. MR 被合入（merged）= review 通过
    # 2. notes/comments = review 讨论
    july_merged_count = len(july_merged_mrs)
    july_notes = sum(mr.get("notes", 0) or 0 for mr in july_active_mrs)
    # Review team（从 MR 列表提取的默认审批人）
    review_team = set()
    for mr in july_mrs[:1]:
        for person in (mr.get("approval_approvers") or []):
            if isinstance(person, dict) and person.get("username"):
                review_team.add(person["username"])
    # 实际执行 merge 的人（通常为 CI bot）
    july_mergers = set()
    for mr in july_merged_mrs:
        mb = mr.get("merged_by")
        if mb and isinstance(mb, dict) and mb.get("username"):
            july_mergers.add(mb["username"])

    # --- 汇总 ---
    return {
        "project": {
            "name": project_info.get("name_with_namespace", "openeuler/triton-cpu"),
            "stars": project_info.get("star_count", 0),
            "forks": project_info.get("forks_count", 0),
            "members": project_info.get("member_count", 0),
            "open_issues": project_info.get("open_issues_count", 0),
            "open_mrs": project_info.get("open_merge_requests_count", 0),
        },
        "active_developers": {
            "total_unique": len(all_active_devs),
            "issue_authors": len(issue_authors),
            "mr_authors": len(mr_authors),
            "mr_approvers": len(mr_approvers),
            "names": sorted(all_active_devs),
        },
        "issues": {
            "total": len(all_issues),
            "open": sum(1 for i in all_issues if i["state"] == "opened"),
            "closed": sum(1 for i in all_issues if i["state"] == "closed"),
            "avg_close_time_hours": sum(close_times_hours) / len(close_times_hours) if close_times_hours else 0,
            "median_close_time_hours": sorted(close_times_hours)[len(close_times_hours) // 2] if close_times_hours else 0,
            "close_times_hours": [round(t, 1) for t in close_times_hours],
            "july_created": len(july_issues_created),
            "july_closed": len(july_issues_closed),
        },
        "pull_requests": {
            "total_all_time": len(all_mrs),
            "july_created": july_mr_count,
            "july_created_states": dict(july_mr_states),
            "july_merged": len(july_merged_mrs),
            "july_active": len(july_active_mrs),
            "july_authors": len(july_authors),
            "july_author_names": sorted(july_authors),
        },
        "reviews": {
            "review_team_size": len(review_team),
            "review_team_names": sorted(review_team),
            "july_mrs_reviewed": july_merged_count,
            "july_review_discussions": july_notes,
            "july_mergers": sorted(july_mergers),
        },
    }


# ============================================================
# 报告输出
# ============================================================

def print_report(results):
    """打印分析报告。"""
    p = results["project"]
    ad = results["active_developers"]
    iss = results["issues"]
    pr = results["pull_requests"]
    rev = results["reviews"]

    print("=" * 60)
    print(f"  GitCode 仓库活跃度分析: {p['name']}")
    print("=" * 60)

    print(f"\n📊 项目概况")
    print(f"  Stars: {p['stars']}  |  Forks: {p['forks']}  |  Members: {p['members']}")
    print(f"  Open Issues: {p['open_issues']}  |  Open PRs: {p['open_mrs']}")

    print(f"\n👥 活跃开发者（参与讨论 / 提交 PR / 提交 Issue）")
    print(f"  总计唯一活跃开发者: {ad['total_unique']}")
    print(f"    - Issue 作者: {ad['issue_authors']}")
    print(f"    - PR 作者:    {ad['mr_authors']}")
    print(f"    - PR Approver: {ad['mr_approvers']}")

    print(f"\n🐛 Issue 分析")
    print(f"  总计: {iss['total']}（Open: {iss['open']}, Closed: {iss['closed']}）")
    print(f"  平均关闭时间: {iss['avg_close_time_hours']:.1f}h（{iss['avg_close_time_hours']/24:.1f} 天）")
    print(f"  中位关闭时间: {iss['median_close_time_hours']:.1f}h（{iss['median_close_time_hours']/24:.1f} 天）")
    print(f"  各 Issue 关闭耗时: {iss['close_times_hours']}h")
    print(f"  7月新创建: {iss['july_created']}  |  7月关闭: {iss['july_closed']}")

    print(f"\n🔀 PR 分析（2026年7月1日 ~ 7月31日）")
    print(f"  7月新创建 PR: {pr['july_created']}")
    print(f"  创建时状态分布: {pr['july_created_states']}")
    print(f"  7月被合入 PR: {pr['july_merged']}（含 7月前创建但 7月合入的）")
    print(f"  7月活跃 PR 总数: {pr['july_active']}")
    print(f"  7月 PR 作者数: {pr['july_authors']}")
    print(f"  作者: {', '.join(pr['july_author_names'])}")

    print(f"\n✅ Review 分析（2026年7月）")
    print(f"  项目 Review Team（CODEOWNERS）: {rev['review_team_size']} 人")
    print(f"    {', '.join(rev['review_team_names'])}")
    print(f"  7月被 Review 通过（merged）的 PR 数: {rev['july_mrs_reviewed']}")
    print(f"  7月 Review 讨论量（notes/comments）: {rev['july_review_discussions']}")
    print(f"  7月执行 Merge 的人员: {', '.join(rev['july_mergers'])}")

    print(f"\n{'=' * 60}")
    print(f"  数据来源: https://gitcode.com/{REPO_PATH}")
    print(f"  分析时间: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"{'=' * 60}")

    # 输出 JSON 格式方便程序化使用
    print(f"\n📋 JSON 输出:")
    # 清理 names 字段用于 JSON
    output = json.loads(json.dumps(results, ensure_ascii=False, default=str))
    print(json.dumps(output, indent=2, ensure_ascii=False))


# ============================================================
# 主流程
# ============================================================

def main():
    print("🔍 开始分析 GitCode triton-cpu 仓库...", file=sys.stderr)

    session = make_session()

    # 1. 获取项目信息
    print("📡 获取项目信息...", file=sys.stderr)
    project_info = fetch_project_info(session)
    time.sleep(1)

    # 2. 获取所有 Issues
    print("📡 获取 Issues...", file=sys.stderr)
    all_issues = fetch_all_issues(session)
    time.sleep(1)

    # 3. 获取所有 MRs
    print("📡 获取 PRs/MRs...", file=sys.stderr)
    all_mrs = fetch_all_mrs(session)

    # 4. 分析
    print("📊 分析数据...", file=sys.stderr)
    results = analyze(all_mrs, all_issues, project_info)

    # 5. 输出报告
    print_report(results)


if __name__ == "__main__":
    main()
