"""
新闻爬虫 - 协调多来源新闻爬取

工作流程:
  1. 遍历启用的新闻来源
  2. 爬取列表页，提取文章链接
  3. 去重（跳过数据库中已有的文章）
  4. 爬取文章详情页的正文
  5. 保存到数据库
"""

from datetime import datetime
from typing import Optional

from loguru import logger

from news_agent.config import Config
from news_agent.models import Article, init_db, save_article
from news_agent.sources.amz123 import AMZ123Parser
from news_agent.sources.mjzj import MJZJParser
from news_agent.sources.upkuajing import UpKuajingParser

# 解析器注册表
PARSER_REGISTRY = {
    "amz123": AMZ123Parser,
    "mjzj": MJZJParser,
    "upkuajing": UpKuajingParser,
}


class NewsCrawler:
    """新闻爬虫 - 主调度器"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.parsers = {}
        self._init_parsers()
        # 确保数据库已初始化
        init_db()

    def _init_parsers(self):
        """初始化启用的解析器"""
        for key, source_cfg in self.config.SOURCES.items():
            if not source_cfg["enabled"]:
                logger.info(f"⏭️  [{source_cfg['name']}] 已禁用，跳过")
                continue
            parser_cls = PARSER_REGISTRY.get(key)
            if parser_cls:
                parser = parser_cls(self.config)
                self.parsers[key] = parser
                logger.info(f"✅ 加载解析器: {parser.source_name}")
            else:
                logger.warning(f"⚠️  未找到解析器: {key}（可后续扩展）")

    def crawl_all(self) -> list[Article]:
        """
        爬取所有启用的来源
        返回新爬取的文章列表
        """
        all_new_articles = []
        for key, parser in self.parsers.items():
            source_cfg = self.config.SOURCES.get(key, {})
            try:
                articles = self._crawl_source(key, parser, source_cfg)
                all_new_articles.extend(articles)
            except Exception as e:
                logger.error(f"❌ 爬取 [{parser.source_name}] 失败: {e}")

        logger.info(f"\n📊 本轮爬取完成: 共新增 {len(all_new_articles)} 篇文章")
        return all_new_articles

    def crawl_source(self, source_key: str) -> list[Article]:
        """爬取指定来源"""
        parser = self.parsers.get(source_key)
        if not parser:
            logger.error(f"❌ 未找到来源: {source_key}")
            return []

        source_cfg = self.config.SOURCES.get(source_key, {})
        return self._crawl_source(source_key, parser, source_cfg)

    def _crawl_source(self, key: str, parser, source_cfg: dict) -> list[Article]:
        """爬取单个来源"""
        source_name = parser.source_name
        url = source_cfg.get("url", "")
        if not url:
            logger.warning(f"⚠️  [{source_name}] URL 为空，跳过")
            return []

        logger.info(f"\n{'=' * 50}")
        logger.info(f"📰 开始爬取: {source_name}")
        logger.info(f"{'=' * 50}")

        # 1. 爬取列表页
        article_list = parser.crawl_list(url)
        if not article_list:
            logger.warning(f"⚠️  [{source_name}] 列表页未提取到文章")
            return []

        # 2. 逐个爬取详情
        new_articles = []
        for i, item in enumerate(article_list, 1):
            title = item["title"]
            article_url = item["url"]

            # 检查是否已存在
            from news_agent.models import article_exists

            if article_exists(article_url):
                logger.debug(f"   ⏭️ [{i}/{len(article_list)}] 已存在: {title[:40]}...")
                continue

            logger.info(f"   📥 [{i}/{len(article_list)}] 爬取: {title[:50]}...")

            # 爬取正文
            content = parser.crawl_article(article_url)
            if not content or len(content) < 50:
                logger.warning(f"   ⚠️  正文过短或为空，跳过")
                continue

            # 构建文章对象
            article = Article(
                title=title,
                url=article_url,
                source=key,
                source_name=source_name,
                content=content,
                excerpt=item.get("excerpt", ""),
                publish_date=item.get("publish_date", ""),
                crawled_at=datetime.now().isoformat(),
            )

            # 保存到数据库
            if save_article(article):
                new_articles.append(article)
                logger.success(f"   ✅ 新增: {title[:50]}...")
            else:
                logger.debug(f"   ⏭️ 保存失败（可能重复）: {title[:40]}...")

        logger.info(f"\n📈 [{source_name}] 新增 {len(new_articles)} 篇文章")
        return new_articles

    def get_stats(self) -> dict:
        """获取当前统计数据"""
        from news_agent.models import get_category_stats

        return get_category_stats()
