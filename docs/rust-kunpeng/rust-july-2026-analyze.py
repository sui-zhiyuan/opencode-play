#!/usr/bin/env python3
"""
Analyze rust-lang/rust repo activity for a given month — GraphQL edition.

Uses GitHub GraphQL API to batch-fetch reviews, comments, and metadata
in ~15 requests instead of ~1500.

Metrics:
  - PR count       — created in the month
  - Issue count    — created in the month
  - Review count   — all reviews on those PRs
  - Active contributors — unique users (authors, commenters, reviewers)
  - Avg issue response time — time to first non-author comment
  - Avg issue close time    — time from creation to closure (closed issues)

Usage:
  export GITHUB_TOKEN="ghp_xxx"   # required (GraphQL needs auth)
  python3 analyze_rust_repo.py

Dependencies: requests
"""

import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional
import requests

# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------
TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    print("Error: GITHUB_TOKEN env var is required for the GitHub GraphQL API.")
    print("  export GITHUB_TOKEN='ghp_xxx'")
    sys.exit(1)

REPO = "rust-lang/rust"
SINCE_DATE = "2026-07-01"
UNTIL_DATE = "2026-07-31"

GRAPHQL_URL = "https://api.github.com/graphql"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
    "User-Agent": "rust-repo-analyzer-graphql",
}

# ---------------------------------------------------------------------------
# GraphQL helper
# ---------------------------------------------------------------------------

def graphql(query: str, variables: dict = None) -> dict:
    """Execute a single GraphQL query, with retry on rate-limit."""
    payload = {"query": query, "variables": variables or {}}
    for attempt in range(5):
        resp = requests.post(GRAPHQL_URL, json=payload, headers=HEADERS, timeout=90)
        if resp.status_code in (403, 429):
            # Rate limit — check remaining points
            remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
            reset_at = int(resp.headers.get("X-RateLimit-Reset", 0))
            if remaining == 0 and reset_at:
                wait = max(reset_at - time.time(), 1) + 2
            else:
                wait = min(60, (attempt + 1) * 10)
            print(f"  ⚠ Rate limited. Waiting {wait:.0f}s...", flush=True)
            time.sleep(wait)
            continue
        if resp.status_code == 502:
            print(f"  ⚠ 502 Bad Gateway, retry {attempt+1}...", flush=True)
            time.sleep(5)
            continue
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            # Non-fatal errors (e.g. a single node failed) — log and continue
            for err in data["errors"]:
                print(f"  ⚠ GraphQL warning: {err.get('message', str(err))}", flush=True)
            if any(e.get("type") == "NOT_FOUND" for e in data["errors"]):
                # Likely a deleted PR — still return data if present
                pass
            else:
                raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data.get("data", {})
    raise RuntimeError("Exhausted GraphQL retries")


def paginated_search(query_str: str, item_type_name: str) -> list:
    """
    Run a paginated GraphQL search query for PRs or Issues.
    Returns list of node dicts (flattened from all pages).
    """
    label = f"search/{item_type_name}"
    all_nodes = []
    cursor = None
    has_next = True
    page = 0
    total_count = 0

    while has_next:
        page += 1
        after = f'after: "{cursor}"' if cursor else ""
        gql = f"""
        query {{
          search(
            query: "{query_str}"
            type: ISSUE
            first: 100
            {after}
          ) {{
            issueCount
            pageInfo {{ hasNextPage endCursor }}
            edges {{
              node {{
                __typename
                ... on PullRequest {{
                  number
                  author {{ login }}
                  reviews(first: 100) {{
                    totalCount
                    nodes {{ author {{ login }} }}
                  }}
                  comments(first: 100) {{
                    totalCount
                    nodes {{ author {{ login }} }}
                  }}
                }}
                ... on Issue {{
                  number
                  author {{ login }}
                  createdAt
                  closedAt
                  comments(first: 10) {{
                    nodes {{
                      author {{ login }}
                      createdAt
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """

        data = graphql(gql)
        search_data = data.get("search", {})
        if page == 1:
            total_count = search_data.get("issueCount", 0)
            if total_count > 1000:
                print(f"  ⚠ [{label}] API reports {total_count} results but only 1000 fetchable.", flush=True)

        edges = search_data.get("edges", [])
        for edge in edges:
            node = edge.get("node")
            if node:
                all_nodes.append(node)

        page_info = search_data.get("pageInfo", {})
        has_next = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")

        print(f"    [{label}] page {page}: fetched {len(all_nodes)}/{min(total_count, 1000)} items "
              f"(API total: {total_count})", flush=True)

        if total_count > 1000 and len(all_nodes) >= 1000:
            print(f"  ⚠ [{label}] Hit 1000-result search cap. Some items may be missing.", flush=True)
            break

    # Filter out deleted/empty nodes
    nodes = [n for n in all_nodes if n is not None]
    print(f"    [{label}] complete: {len(nodes)} valid nodes.", flush=True)
    return nodes


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def parse_dt(s: str) -> Optional[datetime]:
    """Parse ISO 8601 string to UTC datetime."""
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print(f"  rust-lang/rust — Activity Report (GraphQL)")
    print(f"  Period: {SINCE_DATE} → {UNTIL_DATE}")
    print(f"  Requests: ~15 (vs ~1500 with REST)")
    print("=" * 60)

    # ---- 1. Fetch PRs (split into two halves to avoid 1000-result cap) ----
    print("\n[1/2] Fetching PRs (split into 1-15 and 16-31 to avoid 1000 cap)...")

    # First half
    pr_query_1 = f"repo:{REPO} type:pr created:2026-07-01..2026-07-15"
    pr_nodes_1 = paginated_search(pr_query_1, "pr (1-15)")

    # Second half
    pr_query_2 = f"repo:{REPO} type:pr created:2026-07-16..2026-07-31"
    pr_nodes_2 = paginated_search(pr_query_2, "pr (16-31)")

    # Merge, deduplicate by PR number
    seen_numbers = set()
    pr_nodes = []
    for n in pr_nodes_1 + pr_nodes_2:
        num = n.get("number")
        if num and num not in seen_numbers:
            seen_numbers.add(num)
            pr_nodes.append(n)
    pr_count = len(pr_nodes)
    print(f"    [pr] merged & deduplicated: {pr_count} unique PRs.", flush=True)

    # ---- 2. Fetch Issues ----
    print("\n[2/2] Fetching Issues (with comments, close time)...")
    issue_query = f"repo:{REPO} type:issue created:{SINCE_DATE}..{UNTIL_DATE}"
    issue_nodes = paginated_search(issue_query, "issue")
    issue_count = len(issue_nodes)

    # ---- Aggregate metrics ----
    contributors: set = set()
    review_count = 0

    # --- PR metrics ---
    for pr in pr_nodes:
        author = (pr.get("author") or {}).get("login")
        if author:
            contributors.add(author)

        # Reviews
        reviews_data = pr.get("reviews") or {}
        review_count += reviews_data.get("totalCount", 0)
        for rv in (reviews_data.get("nodes") or []):
            rv_user = (rv.get("author") or {}).get("login")
            if rv_user:
                contributors.add(rv_user)

        # PR comments (top-level)
        comments_data = pr.get("comments") or {}
        for cmt in (comments_data.get("nodes") or []):
            cmt_user = (cmt.get("author") or {}).get("login")
            if cmt_user:
                contributors.add(cmt_user)

    # --- Issue metrics ---
    response_hours: list = []
    close_hours: list = []
    issues_no_response = 0
    issues_no_comment = 0
    issues_open = 0
    issues_closed = 0

    for iss in issue_nodes:
        author = (iss.get("author") or {}).get("login")
        if author:
            contributors.add(author)

        created_at = parse_dt(iss.get("createdAt"))
        closed_at = parse_dt(iss.get("closedAt"))

        # Close time
        if closed_at and created_at:
            close_hours.append((closed_at - created_at).total_seconds() / 3600)
            issues_closed += 1
        elif not closed_at:
            issues_open += 1

        # Response time: first non-author comment
        comments_data = iss.get("comments") or {}
        comment_nodes = comments_data.get("nodes") or []
        if not comment_nodes:
            issues_no_comment += 1
        else:
            first_responder_at = None
            for cmt in comment_nodes:
                cmt_user = (cmt.get("author") or {}).get("login")
                if cmt_user:
                    contributors.add(cmt_user)
                cmt_created = parse_dt(cmt.get("createdAt"))
                if cmt_user and cmt_user != author and first_responder_at is None and cmt_created:
                    first_responder_at = cmt_created
            if first_responder_at and created_at:
                response_hours.append((first_responder_at - created_at).total_seconds() / 3600)
            else:
                issues_no_response += 1

    # ---- Display results ----
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)

    print(f"\n  📊 PR count:             {pr_count}")
    print(f"  📊 Issue count:          {issue_count}")
    print(f"  📊 Review count:         {review_count}")
    print(f"  👥 Active contributors:   {len(contributors)}")

    if response_hours:
        avg_r = sum(response_hours) / len(response_hours)
        med_r = sorted(response_hours)[len(response_hours) // 2]
        print(f"\n  ⏱  Issue avg response time: {avg_r:.1f}h ({avg_r/24:.1f}d)")
        print(f"       median: {med_r:.1f}h,  samples: {len(response_hours)}")
    else:
        print(f"\n  ⏱  Issue avg response time: N/A")

    if close_hours:
        avg_c = sum(close_hours) / len(close_hours)
        med_c = sorted(close_hours)[len(close_hours) // 2]
        print(f"\n  🔒 Issue avg close time:   {avg_c:.1f}h ({avg_c/24:.1f}d)")
        print(f"       median: {med_c:.1f}h,  samples: {len(close_hours)}")
    else:
        print(f"\n  🔒 Issue avg close time:   N/A")

    print(f"\n  ── Breakdown ──")
    print(f"  Issues closed:             {issues_closed}")
    print(f"  Issues still open:         {issues_open}")
    print(f"  Issues with no comments:   {issues_no_comment}")
    print(f"  Issues with no response:   {issues_no_response}")

    print("\n" + "=" * 60)
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
