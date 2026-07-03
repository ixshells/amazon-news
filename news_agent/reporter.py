"""
新闻报告生成器 - 按分类整理并生成简洁报告
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from news_agent.config import Config
from news_agent.models import (
    CATEGORIES,
    CATEGORY_KEYS,
    get_all_articles,
    get_articles_by_category,
    get_category_stats,
)


class NewsReporter:
    """新闻报告生成器"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

    def print_daily_digest(self, days: int = 1):
        """打印每日简报"""
        from news_agent.models import get_all_articles

        articles = get_all_articles(limit=200)
        # 筛选最近 N 天
        from datetime import datetime, timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        recent = [a for a in articles if a.crawled_at >= cutoff]

        if not recent:
            logger.info(f"📭 最近 {days} 天没有文章")
            return

        print(f"\n{'=' * 60}")
        print(f"📰 亚马逊情报简报 - 最近 {days} 天 ({len(recent)} 篇)")
        print(f"{'=' * 60}")

        # 按分类分组
        by_cat: dict[str, list] = {}
        for a in recent:
            cat = a.category or "uncategorized"
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(a)

        for cat_key in [
            "policy",
            "platform",
            "trends",
            "operations",
            "logistics",
            "risk",
            "uncategorized",
        ]:
            cat_articles = by_cat.pop(cat_key, [])
            if not cat_articles:
                continue

            cat_info = CATEGORIES.get(cat_key, {"label": "未分类", "emoji": "📄"})
            print(f"\n{'─' * 50}")
            print(f"{cat_info['emoji']} {cat_info['label']} ({len(cat_articles)} 篇)")
            print(f"{'─' * 50}")

            for a in sorted(
                cat_articles, key=lambda x: x.importance == "high", reverse=True
            ):
                imp = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    a.importance, "⚪"
                )
                src = a.source_name
                title = a.title[:70]
                summary = (a.summary or a.excerpt or "")[:120]
                print(f"\n  {imp} [{src}] {title}")
                if summary:
                    print(f"     {summary}")
                print(f"     🔗 {a.url}")

        # 剩余分类
        for cat_key, cat_articles in by_cat.items():
            print(f"\n  📄 {cat_key} ({len(cat_articles)} 篇)")
            for a in cat_articles[:3]:
                print(f"     • {a.title[:60]}")

    def print_category_summary(self):
        """打印分类统计"""
        stats = get_category_stats()
        total = sum(stats.values())

        print(f"\n{'=' * 50}")
        print(f"📊 文章分类统计 (共 {total} 篇)")
        print(f"{'=' * 50}")

        for cat_key in CATEGORY_KEYS:
            count = stats.get(cat_key, 0)
            cat_info = CATEGORIES[cat_key]
            bar = "█" * (count // 2) if count > 0 else ""
            print(f"  {cat_info['emoji']} {cat_info['label']:8s} │ {count:3d} 篇 {bar}")

        uncounted = total - sum(stats.get(k, 0) for k in CATEGORY_KEYS)
        if uncounted > 0:
            print(f"  📄 未分类     │ {uncounted:3d} 篇")

    def export_to_markdown(self, filepath: Optional[str] = None) -> str:
        """导出为 Markdown 报告"""
        from news_agent.models import get_all_articles

        articles = get_all_articles(limit=500)
        if not articles:
            return "# 暂无文章\n"

        lines = []
        lines.append(f"# 亚马逊情报报告\n")
        lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        lines.append(f"> 文章总数: {len(articles)} 篇\n")
        lines.append("---\n")

        # 按分类分组
        by_cat: dict[str, list] = {}
        for a in articles:
            cat = a.category or "uncategorized"
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(a)

        for cat_key in CATEGORY_KEYS:
            cat_articles = by_cat.pop(cat_key, [])
            if not cat_articles:
                continue

            cat_info = CATEGORIES[cat_key]
            lines.append(
                f"\n## {cat_info['emoji']} {cat_info['label']} ({len(cat_articles)} 篇)\n"
            )

            for a in sorted(
                cat_articles, key=lambda x: x.importance == "high", reverse=True
            ):
                imp = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    a.importance, "⚪"
                )
                source = a.source_name
                tags = " | ".join(f"`{t}`" for t in a.tags[:3]) if a.tags else ""
                summary = (a.summary or a.excerpt or "")[:200]

                lines.append(f"### {imp} [{source}] {a.title}\n")
                if tags:
                    lines.append(f"**标签**: {tags}\n")
                if summary:
                    lines.append(f"{summary}\n")
                lines.append(f"[🔗 阅读原文]({a.url})\n")
                lines.append("---\n")

        # 剩余未分类
        for cat_key, cat_articles in by_cat.items():
            lines.append(f"\n## 📄 {cat_key} ({len(cat_articles)} 篇)\n")
            for a in cat_articles[:10]:
                lines.append(f"- {a.title}\n")

        content = "\n".join(lines)

        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"✅ Markdown 报告已导出: {filepath}")

        return content

    def export_to_html(self, filepath: Optional[str] = None, days: int = 7) -> str:
        """导出为 HTML 报告（带样式）"""
        from news_agent.models import get_all_articles

        articles = get_all_articles(limit=500)
        if not articles:
            html = "<html><body><h1>暂无文章</h1></body></html>"
            if filepath:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html)
            return html

        # 筛选最近 N 天
        from datetime import datetime, timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        recent = [a for a in articles if a.crawled_at >= cutoff]
        if not recent:
            recent = articles[-50:]  # 如果近期的没有，取最近 50 篇

        # 分类统计
        stats = get_category_stats()
        total = len(recent)

        # 按分类分组
        by_cat: dict[str, list] = {}
        for a in recent:
            cat = a.category or "uncategorized"
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(a)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        # ======== 构建 HTML ========
        def _score_color(s: int) -> str:
            if s >= 80:
                return "#ef4444"
            if s >= 60:
                return "#f59e0b"
            return "#22c55e"

        def _score_label(s: int) -> str:
            if s >= 80:
                return "必读"
            if s >= 60:
                return "推荐"
            return "浏览"

        def _score_emoji(s: int) -> str:
            if s >= 80:
                return "🔴"
            if s >= 60:
                return "🟡"
            return "🟢"

        # Top Picks: 高评分文章 Top 5
        top_picks = sorted(recent, key=lambda x: x.score, reverse=True)[:5]
        top_picks_html = ""
        if top_picks:
            picks = ""
            for i, a in enumerate(top_picks, 1):
                s = a.score
                picks += f'''
                <div class="top-pick">
                    <span class="top-rank">#{i}</span>
                    <div class="top-content">
                        <span class="score-badge" style="background:{_score_color(s)}">{_score_label(s)} {s}</span>
                        <a class="top-title" href="{a.url}" target="_blank">{a.title[:80]}</a>
                    </div>
                    <div class="top-tldr">💬 {a.tldr}</div>
                </div>'''
            top_picks_html = f"""
            <div class="stats-section">
                <h3 style="margin-bottom:12px;font-size:14px;color:#6b7280;">🏆 今日必读 Top 5</h3>
                {picks}
            </div>"""

        sections_html = top_picks_html

        # 按 CATEGORY_KEYS 顺序输出
        for cat_key in CATEGORY_KEYS:
            cat_articles = by_cat.pop(cat_key, [])
            if not cat_articles:
                continue

            cat_info = CATEGORIES[cat_key]
            cat_articles.sort(key=lambda x: x.score, reverse=True)

            cards = ""
            for a in cat_articles:
                tags_html = (
                    "".join(f'<span class="tag">{t}</span>' for t in a.tags[:4])
                    if a.tags
                    else ""
                )
                summary = (a.summary or a.excerpt or "")[:250]
                tldr_text = a.tldr or ""
                s = a.score

                cards += f'''
                <div class="article-card">
                    <div class="article-header">
                        <span class="score-badge" style="background:{_score_color(s)}">{_score_label(s)} {s}</span>
                        <span class="source">{a.source_name}</span>
                        <span class="date">{a.publish_date or a.crawled_at[:10]}</span>
                    </div>
                    <a class="article-title" href="{a.url}" target="_blank" rel="noopener">
                        {a.title[:120]}
                    </a>
                    <div class="article-tldr">💬 {tldr_text}</div>
                    <div class="article-summary">{summary}</div>
                    <div class="article-tags">{tags_html}</div>
                </div>'''

            sections_html += f"""
            <div class="category-section">
                <h2 class="category-title">{cat_info["emoji"]} {cat_info["label"]}
                    <span class="count-badge">{len(cat_articles)} 篇</span>
                </h2>
                <div class="card-grid">{cards}</div>
            </div>"""

        # 未分类
        for cat_key, cat_articles in by_cat.items():
            cards = "".join(
                f'<div class="article-card"><a class="article-title" href="{a.url}">{a.title[:80]}</a></div>'
                for a in cat_articles[:5]
            )
            sections_html += f"""
            <div class="category-section">
                <h2 class="category-title">📄 {cat_key} <span class="count-badge">{len(cat_articles)} 篇</span></h2>
                <div class="card-grid">{cards}</div>
            </div>"""

        # 统计条
        stats_bars = ""
        for cat_key in CATEGORY_KEYS:
            count = stats.get(cat_key, 0)
            cat_info = CATEGORIES[cat_key]
            pct = (count / total * 100) if total > 0 else 0
            stats_bars += f"""
            <div class="stat-row">
                <span class="stat-label">{cat_info["emoji"]} {cat_info["label"]}</span>
                <div class="stat-bar-bg"><div class="stat-bar-fill" style="width:{pct}%"></div></div>
                <span class="stat-count">{count}</span>
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="generation-date" content="{now_str}">
<title>亚马逊情报日报</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: #f0f2f5; color: #1a1a2e; line-height: 1.6;
}}
.container {{ max-width: 960px; margin: 0 auto; padding: 20px; }}

/* Header */
.header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    color: white; border-radius: 16px; padding: 32px; margin-bottom: 24px;
}}
.header h1 {{ font-size: 24px; margin-bottom: 8px; }}
.header .subtitle {{ color: #a0aec0; font-size: 14px; }}
.header .stats-row {{ display: flex; margin-top: 16px; flex-wrap: wrap; }}
.header .stat-box {{
    background: rgba(255,255,255,0.1); border-radius: 12px; padding: 12px 20px;
    text-align: center; min-width: 80px; margin-right: 12px; margin-bottom: 6px;
}}
.header .stat-box:last-child {{ margin-right: 0; }}
.header .stat-box .num {{ font-size: 24px; font-weight: 700; }}
.header .stat-box .label {{ font-size: 12px; color: #a0aec0; }}

/* Stats */
.stats-section {{
    background: white; border-radius: 12px; padding: 24px; margin-bottom: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
.stat-row {{ display: flex; align-items: center; margin-bottom: 8px; }}
.stat-label {{ width: 100px; font-size: 14px; flex-shrink: 0; }}
.stat-bar-bg {{ flex: 1; height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden; margin: 0 8px; }}
.stat-bar-fill {{ height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); border-radius: 4px; transition: width 0.6s; }}
.stat-count {{ width: 40px; text-align: right; font-weight: 600; font-size: 14px; color: #6b7280; flex-shrink: 0; }}

/* Category */
.category-section {{ margin-bottom: 24px; }}
.category-title {{
    font-size: 18px; font-weight: 700; margin-bottom: 12px;
    display: flex; align-items: center;
}}
.category-title .count-badge {{
    background: #e5e7eb; color: #374151; font-size: 12px;
    padding: 2px 10px; border-radius: 10px; font-weight: 500; margin-left: 8px;
}}

/* Card Grid */
.card-grid {{ display: grid; gap: 12px; }}
.article-card {{
    background: white; border-radius: 12px; padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: box-shadow 0.2s, transform 0.2s;
}}
.article-card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.1); transform: translateY(-1px); }}

.article-header {{ margin-bottom: 6px; font-size: 12px; }}
.article-header .score-badge {{
    display: inline-block; padding: 1px 8px; border-radius: 4px;
    color: white; font-weight: 700; font-size: 11px; margin-right: 6px;
}}
.article-header .source {{ color: #6b7280; margin-right: 6px; }}
.article-header .date {{ color: #9ca3af; }}

.article-title {{
    display: block; font-size: 16px; font-weight: 600; color: #1a1a2e;
    text-decoration: none; margin-bottom: 6px; line-height: 1.4;
    overflow-wrap: break-word; word-break: break-all;
}}
.article-title:hover {{ color: #3b82f6; }}

.article-tldr {{
    font-size: 13px; color: #1a1a2e; font-weight: 500; margin-bottom: 6px;
    padding: 4px 8px; background: #fef9c3; border-radius: 4px; display: inline-block;
    overflow-wrap: break-word; word-break: break-all;
}}

.article-summary {{ font-size: 14px; color: #6b7280; margin-bottom: 8px; overflow-wrap: break-word; word-break: break-all; }}

.article-tags {{
    font-size: 0;
}}
.article-tags .tag {{
    background: #f3f4f6; color: #374151; font-size: 11px;
    padding: 2px 8px; border-radius: 4px; display: inline-block; margin-right: 6px; margin-bottom: 4px;
}}

/* Top Picks */
.top-pick {{
    display: flex; align-items: flex-start; padding: 10px 0;
    border-bottom: 1px solid #f3f4f6;
}}
.top-pick:last-child {{ border-bottom: none; }}
.top-rank {{
    font-size: 18px; font-weight: 800; color: #d1d5db; width: 32px; text-align: center; flex-shrink: 0; padding-top: 2px;
}}
.top-content {{ flex: 1; }}
.top-content .score-badge {{
    display: inline-block; padding: 1px 8px; border-radius: 4px;
    color: white; font-weight: 700; font-size: 11px; margin-right: 6px; vertical-align: middle;
}}
.top-title {{
    font-size: 14px; font-weight: 600; color: #1a1a2e;
    text-decoration: none; overflow-wrap: break-word; word-break: break-all;
}}
.top-title:hover {{ color: #3b82f6; }}
.top-tldr {{
    font-size: 12px; color: #6b7280; margin-left: 32px; padding: 2px 0 0 4px;
    overflow-wrap: break-word; word-break: break-all;
}}

/* Footer */
.footer {{
    text-align: center; color: #9ca3af; font-size: 12px;
    padding: 24px 0; border-top: 1px solid #e5e7eb; margin-top: 32px;
}}

@media (max-width: 640px) {{
    .container {{ padding: 10px; }}
    .header {{ padding: 16px; }}
    .header h1 {{ font-size: 18px; }}
    .header .subtitle {{ font-size: 12px; }}
    .header .stats-row {{ margin-top: 12px; }}
    .header .stat-box {{ padding: 6px 8px; margin-right: 6px; margin-bottom: 4px; min-width: 0; flex: 1; }}
    .header .stat-box .num {{ font-size: 16px; }}
    .header .stat-box .label {{ font-size: 10px; }}
    .stat-label {{ width: 60px; font-size: 11px; }}
    .stat-bar-bg {{ height: 6px; margin: 0 6px; }}
    .stat-count {{ font-size: 11px; width: 24px; }}

    /* ===== Top Picks: 完全纵向堆叠 ===== */
    .top-pick {{
        flex-direction: column;
        padding: 10px 0;
    }}
    .top-rank {{
        font-size: 12px;
        width: auto;
        color: #9ca3af;
        text-align: left;
        padding-top: 0;
    }}
    .top-content .score-badge {{
        margin-bottom: 4px;
    }}
    .top-title {{
        font-size: 14px;
        line-height: 1.5;
    }}
    .top-tldr {{
        margin-left: 0;
        font-size: 12px;
        line-height: 1.4;
    }}

    /* ===== 文章卡片: 紧凑 + 防溢出 ===== */
    .article-card {{ padding: 10px 12px; }}
    .article-header .date {{
        font-size: 11px;
        color: #9ca3af;
    }}
    .article-title {{
        font-size: 14px;
    }}
    .article-tldr {{
        font-size: 12px;
        white-space: normal;
        display: block;
    }}
    .article-summary {{
        font-size: 13px;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }}

    /* 分类标题紧凑 */
    .category-section {{ margin-bottom: 16px; }}
    .category-title {{ font-size: 15px; margin-bottom: 8px; }}
    .card-grid {{ gap: 8px; }}

    /* 统计区 */
    .stats-section {{ padding: 14px; margin-bottom: 14px; }}
    .stat-row {{ margin-bottom: 6px; }}

    /* Footer */
    .footer {{ font-size: 11px; padding: 16px 0; margin-top: 16px; }}
}}
</style>
</head>
<body>
<div class="container">

<div class="header">
    <h1>📰 亚马逊情报日报</h1>
    <div class="subtitle">生成时间: {now_str} ｜ 覆盖最近 {days} 天 ｜ 共 {total} 篇文章</div>
    <div class="stats-row">
        <div class="stat-box"><div class="num">{total}</div><div class="label">总文章</div></div>
        <div class="stat-box"><div class="num">{len([a for a in recent if a.score >= 75])}</div><div class="label">高分文章</div></div>
        <div class="stat-box"><div class="num">{len(set(a.source for a in recent))}</div><div class="label">信息来源</div></div>
    </div>
</div>

<div class="stats-section">
    <h3 style="margin-bottom:12px;font-size:14px;color:#6b7280;">📊 分类分布</h3>
    {stats_bars}
</div>

{sections_html}

<div class="footer">
    由 Amazon News Agent 自动生成 ｜ <a href="https://github.com/" style="color:#6b7280;">GitHub</a>
</div>

</div>
</body>
</html>"""

        if filepath:
            filepath = Path(filepath) if isinstance(filepath, str) else filepath
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"✅ HTML 报告已导出: {filepath}")

        return html
