"""
新闻数据模型

使用 SQLite 存储已爬取的新闻，支持增量更新（避免重复爬取）。
"""

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

from loguru import logger

from news_agent.config import DB_PATH

# ============================================================
# 分类标签（AI 分类器的输出标准）
# ============================================================
CATEGORIES = {
    "policy": {
        "label": "政策法规",
        "emoji": "📜",
        "description": "亚马逊平台政策更新、关税政策、税务政策、合规认证要求等",
    },
    "platform": {
        "label": "平台动态",
        "emoji": "🛒",
        "description": "亚马逊新功能发布、费用调整、Prime Day/黑五等大促活动、服务变更",
    },
    "trends": {
        "label": "行业趋势",
        "emoji": "📈",
        "description": "市场数据报告、消费趋势分析、品类风向变化、竞争格局",
    },
    "operations": {
        "label": "运营干货",
        "emoji": "⚙️",
        "description": "选品策略、广告投放技巧、Listing优化、供应链管理实操经验",
    },
    "logistics": {
        "label": "物流仓储",
        "emoji": "🚚",
        "description": "FBA政策更新、物流渠道变化、仓储费用调整、头程物流",
    },
    "risk": {
        "label": "风险预警",
        "emoji": "⚠️",
        "description": "账号安全警告、侵权风险提示、虚假评论打击、封号潮动态",
    },
}

CATEGORY_KEYS = list(CATEGORIES.keys())


@dataclass
class Article:
    """一篇新闻文章"""

    # 基本信息
    title: str
    url: str
    source: str  # 来源标识，如 "amz123"
    source_name: str  # 来源显示名，如 "AMZ123"

    # 内容
    content: str  # 文章正文（纯文本）
    summary: str = ""  # AI 生成的摘要
    excerpt: str = ""  # 爬取时的摘要/描述

    # AI 分类结果
    category: str = ""  # 一级分类
    subcategory: str = ""  # 二级分类（AI 自由生成）
    tags: list[str] = field(default_factory=list)  # 标签
    importance: str = "medium"  # high / medium / low
    score: int = 50  # 综合评分 0-100（亚马逊相关性 + 政策重要性 + 卖家影响度）
    tldr: str = ""  # 一句话极简总结（TL;DR）

    # 元信息
    publish_date: Optional[str] = None  # 文章发布时间
    author: str = ""
    language: str = "zh"  # zh / en

    # 状态
    is_read: bool = False  # AI 是否已处理
    is_notified: bool = False  # 是否已推送通知

    # 时间
    crawled_at: str = ""  # 爬取时间
    read_at: str = ""  # AI 阅读分类时间

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ============================================================
# 数据库操作
# ============================================================


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                source_name TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                summary TEXT DEFAULT '',
                excerpt TEXT DEFAULT '',
                category TEXT DEFAULT '',
                subcategory TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                importance TEXT DEFAULT 'medium',
                publish_date TEXT DEFAULT '',
                author TEXT DEFAULT '',
                language TEXT DEFAULT 'zh',
                is_read INTEGER DEFAULT 0,
                is_notified INTEGER DEFAULT 0,
                score INTEGER DEFAULT 50,
                tldr TEXT DEFAULT '',
                crawled_at TEXT DEFAULT '',
                read_at TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 兼容旧表：先添加新列（若已存在则忽略）
        for col in [("score", "INTEGER DEFAULT 50"), ("tldr", "TEXT DEFAULT ''")]:
            try:
                conn.execute(f"ALTER TABLE articles ADD COLUMN {col[0]} {col[1]}")
            except sqlite3.OperationalError:
                pass  # 列已存在

        conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON articles(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_is_read ON articles(is_read)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_crawled_at ON articles(crawled_at)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_score ON articles(score)")
        conn.commit()
    finally:
        conn.close()
    logger.info(f"✅ 数据库初始化完成: {DB_PATH}")


def article_exists(url: str) -> bool:
    """检查文章是否已存在"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,)).fetchone()
        return row is not None
    finally:
        conn.close()


def save_article(article: Article) -> bool:
    """
    保存文章到数据库
    返回 True 表示新增，False 表示已存在跳过
    """
    if article_exists(article.url):
        return False

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO articles
                (url, title, source, source_name, content, summary, excerpt,
                 category, subcategory, tags, importance, score, tldr,
                 publish_date, author, language, is_read, is_notified,
                 crawled_at, read_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article.url,
                article.title,
                article.source,
                article.source_name,
                article.content,
                article.summary,
                article.excerpt,
                article.category,
                article.subcategory,
                json.dumps(article.tags, ensure_ascii=False),
                article.importance,
                article.score,
                article.tldr,
                article.publish_date or "",
                article.author,
                article.language,
                1 if article.is_read else 0,
                1 if article.is_notified else 0,
                article.crawled_at or datetime.now().isoformat(),
                article.read_at or "",
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_unread_articles(limit: int = 50) -> list[Article]:
    """获取未处理的文章"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM articles WHERE is_read = 0 ORDER BY crawled_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_article(row) for row in rows]
    finally:
        conn.close()


def get_articles_by_category(
    category: str, limit: int = 50, offset: int = 0
) -> list[Article]:
    """按分类获取文章"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM articles WHERE category = ? ORDER BY crawled_at DESC LIMIT ? OFFSET ?",
            (category, limit, offset),
        ).fetchall()
        return [_row_to_article(row) for row in rows]
    finally:
        conn.close()


def get_all_articles(limit: int = 100, offset: int = 0) -> list[Article]:
    """获取所有文章"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY crawled_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_article(row) for row in rows]
    finally:
        conn.close()


def mark_as_read(
    article_id: int,
    category: str = "",
    subcategory: str = "",
    tags: list[str] = None,
    importance: str = "medium",
    score: int = 50,
    tldr: str = "",
    summary: str = "",
):
    """标记文章为已处理"""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE articles SET
                is_read = 1, category = ?, subcategory = ?,
                tags = ?, importance = ?, score = ?, tldr = ?,
                summary = ?, read_at = ?
            WHERE id = ?
            """,
            (
                category,
                subcategory,
                json.dumps(tags or [], ensure_ascii=False),
                importance,
                score,
                tldr,
                summary,
                datetime.now().isoformat(),
                article_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_category_stats() -> dict:
    """获取各分类的文章数量统计"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT category, COUNT(*) as count FROM articles GROUP BY category ORDER BY count DESC"
        ).fetchall()
        return {row["category"]: row["count"] for row in rows}
    finally:
        conn.close()


def _row_to_article(row: sqlite3.Row) -> Article:
    """将数据库行转换为 Article 对象"""
    return Article(
        title=row["title"],
        url=row["url"],
        source=row["source"],
        source_name=row["source_name"],
        content=row["content"],
        summary=row["summary"],
        excerpt=row["excerpt"],
        category=row["category"],
        subcategory=row["subcategory"],
        tags=json.loads(row["tags"]) if row["tags"] else [],
        importance=row["importance"],
        score=row["score"] if "score" in row.keys() else 50,
        tldr=row["tldr"] if "tldr" in row.keys() else "",
        publish_date=row["publish_date"],
        author=row["author"],
        language=row["language"],
        is_read=bool(row["is_read"]),
        is_notified=bool(row["is_notified"]),
        crawled_at=row["crawled_at"],
        read_at=row["read_at"],
    )
