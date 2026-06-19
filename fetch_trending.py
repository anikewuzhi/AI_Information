#!/usr/bin/env python3
"""
fetch_trending.py — 每周抓取 GitHub Trending 热门项目
用法: python fetch_trending.py
输出: docs/YYYY-MM-DD-github-trending.md
"""

import requests
import time
import re
import sys
from datetime import date
from bs4 import BeautifulSoup
from pathlib import Path

# ============================================================
# 配置区：在这里调整你要抓取的语言
# ============================================================
LANGUAGES = [
    "",              # 全语言
    "python",        # Python（模型/训练/数据）
    "typescript",    # TypeScript（Agent 框架/工具链）
    "rust",          # Rust（高性能推理）
]

BASE_URL = "https://github.com/trending"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
SINCE = "weekly"    # daily / weekly / monthly
OUTPUT_DIR = Path(__file__).parent / "docs"
MAX_RETRIES = 3
RETRY_DELAY = 3     # 秒，指数退避基数


# ============================================================
# 核心逻辑
# ============================================================
def parse_number(text: str) -> int:
    """从文本中提取数字，处理逗号、k 等"""
    text = text.strip()
    m = re.search(r'[\d,]+\.?\d*\s*k?', text, re.IGNORECASE)
    if not m:
        return 0
    num_str = m.group().replace(",", "").strip()
    if not num_str:
        return 0
    if "k" in num_str.lower():
        return int(float(num_str.lower().replace("k", "")) * 1000)
    try:
        return int(float(num_str))
    except ValueError:
        return 0


def fetch_page(url: str) -> str | None:
    """带重试的 HTTP 请求"""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 429:
                wait = RETRY_DELAY * (attempt + 2)
                print(f"  [429] rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.text
        except Exception as e:
            wait = RETRY_DELAY * (attempt + 1)
            print(f"  [error] {e}, retry {attempt + 1}/{MAX_RETRIES} in {wait}s...")
            time.sleep(wait)
    return None


def parse_trending(html: str) -> list[dict]:
    """解析 GitHub Trending 页面，返回结构化数据"""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    articles = soup.select("article.Box-row")

    for i, art in enumerate(articles, 1):
        h2 = art.h2
        if not h2 or not h2.a:
            continue
        repo_name = h2.get_text(strip=True).replace("\n", "").replace(" ", "")
        link = "https://github.com" + h2.a["href"]

        desc_tag = art.p
        desc = desc_tag.get_text(strip=True) if desc_tag else ""

        lang_tag = art.select_one("[itemprop='programmingLanguage']")
        lang = lang_tag.get_text(strip=True) if lang_tag else "N/A"

        # Star / Fork
        link_muted = art.select("a.Link--muted")
        total_stars = 0
        total_forks = 0
        weekly_stars = 0

        if len(link_muted) >= 2:
            total_stars = parse_number(link_muted[-2].get_text(strip=True))
            total_forks = parse_number(link_muted[-1].get_text(strip=True))

        # 周新增 star
        new_star_span = art.select_one("span.d-inline-block.float-sm-right")
        if new_star_span:
            weekly_stars = parse_number(new_star_span.get_text())

        rows.append({
            "rank": i,
            "repo": repo_name,
            "desc": desc,
            "lang": lang,
            "total_stars": total_stars,
            "weekly_stars": weekly_stars,
            "forks": total_forks,
            "link": link,
        })
    return rows


def dedup(rows: list[dict]) -> list[dict]:
    """跨语言去重：同一仓库保留 weekly_stars 更大的那条"""
    seen = {}
    for r in rows:
        key = r["repo"]
        if key not in seen or r["weekly_stars"] > seen[key]["weekly_stars"]:
            seen[key] = r
    return list(seen.values())


def sort_by_weekly(rows: list[dict]) -> list[dict]:
    """按周新增 Star 降序重排排名"""
    rows.sort(key=lambda x: x["weekly_stars"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def generate_markdown(rows: list[dict], today: str) -> str:
    """生成 Markdown 周报"""
    lines = [
        f"# GitHub Trending Weekly ({today})\n",
        f"> 共 {len(rows)} 个项目（已跨语言去重，按周新增 ⭐ 降序）",
        f"> 数据来源: github.com/trending?since=weekly\n",
        "| # | 仓库 | 描述 | 语言 | ⭐总星 | +周新增 | 🍴Fork | 链接 |",
        "|---|------|------|------|--------|---------|--------|------|",
    ]
    for r in rows:
        desc = r["desc"][:60] + "…" if len(r["desc"]) > 60 else r["desc"]
        lines.append(
            f"| {r['rank']} | `{r['repo']}` | {desc} | {r['lang']} | "
            f"{r['total_stars']:,} | +{r['weekly_stars']:,} | "
            f"{r['forks']:,} | [🔗]({r['link']}) |"
        )
    lines.append(f"\n---\n*自动抓取于 {today}，请人工判断哪些是 AI 相关项目。*")
    return "\n".join(lines)


def main():
    today = date.today().isoformat()
    print(f"📅 抓取日期: {today}")
    print(f"🔍 抓取语言: {[l or 'all' for l in LANGUAGES]}\n")

    all_rows = []
    for lang in LANGUAGES:
        lang_label = lang or "all"
        url = f"{BASE_URL}/{lang}?since={SINCE}" if lang else f"{BASE_URL}?since={SINCE}"
        print(f"  → 抓取 [{lang_label}] ...")

        html = fetch_page(url)
        if not html:
            print(f"  ❌ [{lang_label}] 抓取失败，跳过")
            continue

        rows = parse_trending(html)
        print(f"  ✅ [{lang_label}] 获取 {len(rows)} 个项目")

        # 标记来源语言
        for r in rows:
            r["source_lang"] = lang_label

        all_rows.extend(rows)
        time.sleep(2)  # 请求间隔，避免被封

    if not all_rows:
        print("\n❌ 所有语言抓取均失败，退出")
        sys.exit(1)

    # 去重 + 排序
    all_rows = dedup(all_rows)
    all_rows = sort_by_weekly(all_rows)
    print(f"\n📊 去重后共 {len(all_rows)} 个项目")

    # 生成 Markdown
    md = generate_markdown(all_rows, today)

    # 写文件
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{today}-github-trending.md"
    output_file.write_text(md, encoding="utf-8")
    print(f"\n✅ 周报已生成: {output_file}")
    print(f"📄 共 {len(all_rows)} 条，请人工筛选 AI 相关项目\n")


if __name__ == "__main__":
    main()
