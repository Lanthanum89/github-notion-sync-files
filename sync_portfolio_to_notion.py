#!/usr/bin/env python3
"""
Sync GitHub repos (tagged with a topic, default 'portfolio') into a Notion database.
- Upserts pages by Repo URL
- Sets/updates: Name, Repo URL, Summary, Tech (multi-select), Date Added
- Optional: Archive Notion pages not present in GitHub search results
Requires env vars:
  NOTION_TOKEN, NOTION_DATABASE_ID, GH_USERNAME
Optional env vars:
  GH_TOKEN, GH_TOPIC=portfolio, ARCHIVE_MISSING=true/false,
  DEFAULT_STATUS, DEFAULT_PRIORITY, DEFAULT_IG_STATUS
"""
import os, sys, time, datetime, json
from typing import Dict, List, Any, Optional
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
GH_USERNAME = os.environ.get("GH_USERNAME")
GH_TOKEN = os.environ.get("GH_TOKEN")
GH_TOPIC = os.environ.get("GH_TOPIC", "portfolio")
ARCHIVE_MISSING = os.environ.get("ARCHIVE_MISSING", "true").lower() == "true"

DEFAULT_STATUS = os.environ.get("DEFAULT_STATUS", "In Portfolio")
DEFAULT_PRIORITY = os.environ.get("DEFAULT_PRIORITY", "Medium")
DEFAULT_IG_STATUS = os.environ.get("DEFAULT_IG_STATUS", "Not posted")

HEADERS_GH = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if GH_TOKEN:
    HEADERS_GH["Authorization"] = f"Bearer {GH_TOKEN}"

HEADERS_NOTION = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

def ensure_env():
    missing = [k for k in ["NOTION_TOKEN", "NOTION_DATABASE_ID", "GH_USERNAME"] if not os.environ.get(k)]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

def gh_search_repos_with_topic(user: str, topic: str) -> List[Dict[str, Any]]:
    """Use GitHub search to find repos owned by user with topic"""
    url = "https://api.github.com/search/repositories"
    q = f"user:{user} topic:{topic}"
    out = []
    page = 1
    per_page = 100
    while True:
        params = {"q": q, "per_page": per_page, "page": page}
        r = requests.get(url, headers=HEADERS_GH, params=params, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"GitHub search failed: {r.status_code} {r.text}")
        data = r.json()
        items = data.get("items", [])
        out.extend(items)
        if len(items) < per_page:
            break
        page += 1
    return out

def gh_repo_languages(owner: str, repo: str) -> List[str]:
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    r = requests.get(url, headers=HEADERS_GH, timeout=30)
    if r.status_code != 200:
        return []
    langs = r.json() or {}
    # sort languages by bytes desc, take top 3
    return [k for k, _ in sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:3]]

def gh_repo_topics(owner: str, repo: str) -> List[str]:
    url = f"https://api.github.com/repos/{owner}/{repo}/topics"
    r = requests.get(url, headers={**HEADERS_GH, "Accept": "application/vnd.github.mercy-preview+json"}, timeout=30)
    if r.status_code != 200:
        return []
    data = r.json() or {}
    return data.get("names", [])

def guess_category(name: str, desc: str, topics: List[str], langs: List[str]) -> str:
    n = (name or "").lower()
    d = (desc or "").lower()
    t = " ".join(topics).lower()
    if "api" in n or "api" in d or "backend" in t:
        return "API / Backend"
    if "asp" in d or "razor" in d or "asp.net" in d or "aspnet" in n:
        return "Web App"
    if "tkinter" in d or "gui" in d:
        return "GUI App"
    if "pygame" in d or "snake" in n:
        return "Game"
    if "eda" in d or "analysis" in d:
        return "EDA / Visualisation"
    if "ml" in d or "machine learning" in d or "scikit" in d:
        return "Data Science / ML"
    if any(l in ["C#", "CSharp", "C Sharp"] for l in langs):
        return "Web App"
    return "App / Misc"

# ----- Notion helpers -----
def notion_query_all_pages(database_id: str) -> List[Dict[str, Any]]:
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    pages = []
    start_cursor = None
    while True:
        payload: Dict[str, Any] = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        r = requests.post(url, headers=HEADERS_NOTION, json=payload, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Notion query failed: {r.status_code} {r.text}")
        data = r.json()
        pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")
    return pages

def get_prop(props: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    return props.get(name)

def extract_repo_url(page: Dict[str, Any]) -> Optional[str]:
    props = page.get("properties", {})
    p = props.get("Repo URL")
    if not p:
        return None
    if p["type"] == "url":
        return p.get("url")
    return None

def make_select(name: str) -> Dict[str, Any]:
    return {"select": {"name": name}} if name else {"select": None}

def make_multi_select(values: List[str]) -> Dict[str, Any]:
    return {"multi_select": [{"name": v} for v in values if v]}

def make_title(text: str) -> Dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": text[:200]}}]}

def make_rich_text(text: str) -> Dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}

def make_date(iso_date: str) -> Dict[str, Any]:
    return {"date": {"start": iso_date}}

def build_properties(item: Dict[str, Any]) -> Dict[str, Any]:
    props = {
        "Name": make_title(item["name"]),
        "Repo URL": {"url": item["html_url"]},
        "Category": make_select(item.get("category", "")),
        "Tech": make_multi_select(item.get("tech", [])),
        "Summary": make_rich_text(item.get("summary", "")),
        "Status": make_select(DEFAULT_STATUS),
        "IG Status": make_select(DEFAULT_IG_STATUS),
        "Priority": make_select(DEFAULT_PRIORITY),
        "Date Added": make_date(item["created_at"].split("T")[0]),
        "Demo Link": {"url": item.get("demo_link") or None},
        "Next Post Hook": make_rich_text(item.get("next_hook", "")),
    }
    return props

def notion_create_page(database_id: str, props: Dict[str, Any]) -> str:
    url = "https://api.notion.com/v1/pages"
    payload = {"parent": {"database_id": database_id}, "properties": props}
    r = requests.post(url, headers=HEADERS_NOTION, json=payload, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Notion create failed: {r.status_code} {r.text}")
    return r.json()["id"]

def notion_update_page(page_id: str, props: Dict[str, Any]) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": props}
    r = requests.patch(url, headers=HEADERS_NOTION, json=payload, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Notion update failed: {r.status_code} {r.text}")

def notion_archive_page(page_id: str) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"archived": True}
    r = requests.patch(url, headers=HEADERS_NOTION, json=payload, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Notion archive failed: {r.status_code} {r.text}")

def main():
    ensure_env()

    # 1) Pull GH repos with topic
    gh_items = gh_search_repos_with_topic(GH_USERNAME, GH_TOPIC)

    # Build minimal dict for each repo
    repos = []
    slugs = set()
    for it in gh_items:
        owner = it["owner"]["login"]
        name = it["name"]
        html_url = it["html_url"]
        desc = it.get("description") or ""
        created_at = it.get("created_at") or it.get("pushed_at") or datetime.datetime.utcnow().isoformat()
        langs = gh_repo_languages(owner, name)
        topics = gh_repo_topics(owner, name)  # optional, extra hints

        category = guess_category(name, desc, topics, langs)
        summary = desc or f"{name} project."
        repos.append({
            "name": name,
            "html_url": html_url,
            "summary": summary,
            "created_at": created_at,
            "tech": langs,
            "category": category,
            "demo_link": "",
            "next_hook": "",
        })
        slugs.add(html_url)

    # 2) Map existing Notion pages by Repo URL
    pages = notion_query_all_pages(NOTION_DATABASE_ID)
    existing_map = {}  # repo_url -> page_id
    for pg in pages:
        url = extract_repo_url(pg)
        if url:
            existing_map[url] = pg["id"]

    # 3) Upsert
    created, updated = 0, 0
    for repo in repos:
        props = build_properties(repo)
        if repo["html_url"] in existing_map:
            notion_update_page(existing_map[repo["html_url"]], props)
            updated += 1
        else:
            notion_create_page(NOTION_DATABASE_ID, props)
            created += 1

    # 4) Archive missing (optional)
    archived = 0
    if ARCHIVE_MISSING:
        gh_urls = {r["html_url"] for r in repos}
        for url, page_id in existing_map.items():
            if url not in gh_urls:
                notion_archive_page(page_id)
                archived += 1

    print(json.dumps({
        "created": created,
        "updated": updated,
        "archived": archived,
        "total_github": len(repos),
        "total_notion_before": len(existing_map),
    }, indent=2))

if __name__ == "__main__":
    main()
