# GitHub Trending Weekly

每周一自动抓取 GitHub Trending 热门项目，生成 Markdown 周报。

## 文件结构

```
.
├── fetch_trending.py          # 爬虫脚本
├── .github/workflows/
│   └── trending.yml           # GitHub Actions 定时任务
└── docs/                      # 周报输出目录
    └── 2025-01-20-github-trending.md
```

## 本地运行

```bash
pip install requests beautifulsoup4
python fetch_trending.py
```

## 自定义

编辑 `fetch_trending.py` 顶部的 `LANGUAGES` 列表即可调整要抓取的语言：

```python
LANGUAGES = [
    "",              # 全语言
    "python",
    "typescript",
    "rust",
    "jupyter-notebook",  # 加这个能多捞研究类项目
]
```
