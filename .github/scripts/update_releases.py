#!/usr/bin/env python3
"""Refresh the `recent releases` block in README.md.

Queries the GitHub GraphQL API for the newest release of every repository owned
by GITHUB_LOGIN, keeps the most recent ones and rewrites the text between
<!--START_SECTION:releases--> and <!--END_SECTION:releases-->.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

README = "README.md"
START = "<!--START_SECTION:releases-->"
END = "<!--END_SECTION:releases-->"
LIMIT = 6

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(
      first: 100
      ownerAffiliations: OWNER
      isFork: false
      orderBy: {field: PUSHED_AT, direction: DESC}
    ) {
      nodes {
        nameWithOwner
        releases(first: 1, orderBy: {field: CREATED_AT, direction: DESC}) {
          nodes {
            name
            tagName
            publishedAt
            url
            isDraft
          }
        }
      }
    }
  }
}
"""


def graphql(token: str, query: str, variables: dict) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-release-updater",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def collect(data: dict) -> list[tuple[str, str, str, str]]:
    entries = []
    for repo in data["user"]["repositories"]["nodes"]:
        for release in repo["releases"]["nodes"]:
            if release["isDraft"] or not release["publishedAt"]:
                continue
            entries.append(
                (
                    release["publishedAt"],
                    repo["nameWithOwner"],
                    release["name"] or release["tagName"],
                    release["url"],
                )
            )
    entries.sort(reverse=True)
    return entries[:LIMIT]


def render(entries: list[tuple[str, str, str, str]]) -> str:
    if not entries:
        return "- 暂无 release"
    lines = []
    for published, repo, name, url in entries:
        short_repo = repo.split("/", 1)[1]
        lines.append(f"- [{name}]({url}) · **{short_repo}** · {published[:10]}")
    return "\n".join(lines)


def main() -> int:
    token = os.environ.get("GH_TOKEN")
    login = os.environ.get("GITHUB_LOGIN")
    if not token or not login:
        print("GH_TOKEN and GITHUB_LOGIN are required", file=sys.stderr)
        return 1

    with open(README, encoding="utf-8") as fh:
        readme = fh.read()

    if START not in readme or END not in readme:
        print(f"Section markers not found in {README}", file=sys.stderr)
        return 1

    body = render(collect(graphql(token, QUERY, {"login": login})))
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)

    with open(README, "w", encoding="utf-8") as fh:
        fh.write(f"{head}{START}\n{body}\n{END}{tail}")
    print(f"Updated recent releases ({len(body.splitlines())} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
