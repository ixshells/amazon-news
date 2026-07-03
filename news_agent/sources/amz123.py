"""
AMZ123 新闻解析器

首页: https://www.amz123.com/
新闻列表: https://www.amz123.com/t  (跨境头条)
          https://www.amz123.com/kx (跨境快讯)
          https://www.amz123.com/zb (跨境早报)

AMZ123 是亚马逊卖家一站式导航+新闻平台，文章内容与跨境电商高度相关。
"""

from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger

from .base import BaseParser


class AMZ123Parser(BaseParser):
    """AMZ123 解析器"""

    source_key = "amz123"
    source_name = "AMZ123"

    # 多个列表页 URL（覆盖不同类型的新闻）
    LIST_URLS = [
        "https://www.amz123.com/t",  # 跨境头条
        "https://www.amz123.com/kx",  # 跨境快讯
        "https://www.amz123.com/zb",  # 跨境早报
    ]

    def extract_article_list(self, html: str) -> list[dict]:
        """提取新闻列表页中的文章

        AMZ123 文章 HTML 结构:
            div.ugc-article-item
              └─ div.ugc-article-item__main
                   ├─ div.ugc-article-image (图片)
                   ├─ div.ugc-article-detail
                   │    ├─ a.ugc-article-title  (标题 + 链接)
                   │    ├─ section.ugc-article-description (摘要)
                   │    └─ div.ugc-article-bottom
                   │         ├─ span.ugc-title-color (发布时间)
                   │         ├─ div.ugc-tag-main > div.ugc-tag-item > a (标签)
                   │         └─ a.ugc-author-name > span (作者)
        """
        articles = []
        soup = BeautifulSoup(html, "lxml")

        # 主要选择器：文章卡片
        items = soup.select("div.ugc-article-item")
        if not items:
            # 兜底：找指向 /t/ 的链接
            logger.debug("  → 未找到 ugc-article-item，使用通用链接匹配")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/t/" in href and not href.endswith("/t/"):
                    title = a.get("title", "") or a.get_text(strip=True)
                    if title and len(title) > 5:
                        full_url = (
                            href
                            if href.startswith("http")
                            else urljoin("https://www.amz123.com", href)
                        )
                        articles.append(
                            {
                                "title": title[:200],
                                "url": full_url,
                                "excerpt": "",
                                "publish_date": "",
                            }
                        )

        for item in items:
            # 标题和链接
            title_el = item.select_one("a.ugc-article-title")
            if not title_el:
                continue
            title = title_el.get("title", "") or title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if not title or len(title) < 5:
                continue

            full_url = (
                href
                if href.startswith("http")
                else urljoin("https://www.amz123.com", href)
            )

            # 摘要
            excerpt = ""
            excerpt_el = item.select_one("section.ugc-article-description")
            if excerpt_el:
                excerpt = excerpt_el.get_text(strip=True)

            # 发布日期
            pub_date = ""
            date_el = item.select_one("span.ugc-title-color")
            if date_el:
                pub_date = date_el.get_text(strip=True)

            articles.append(
                {
                    "title": title[:200],
                    "url": full_url,
                    "excerpt": excerpt[:300],
                    "publish_date": pub_date,
                }
            )

        # 去重
        seen = set()
        unique = []
        for a in articles:
            if a["url"] not in seen:
                seen.add(a["url"])
                unique.append(a)

        logger.info(f"  → AMZ123 解析到 {len(unique)} 篇文章")
        return unique

    def extract_content(self, html: str, url: str) -> str:
        """提取文章正文

        AMZ123 文章详情页结构:
            article 标签包含正文内容
            或者 div.ugc-article-new-box / div.article-detail-main
            或者 div.article-content / div.post-content
        """
        soup = BeautifulSoup(html, "lxml")

        # 按优先级尝试多种选择器
        content_selectors = [
            "article",
            "div.ugc-article-new-box",
            "div.article-detail-main",
            "div.article-content",
            "div.post-content",
            "div.news-content",
            "div.content",
            "div.detail-content",
        ]

        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # 移除无用元素
                for tag in content_div.select(
                    "script, style, iframe, .ad, .ads, .share, nav, footer"
                ):
                    tag.decompose()
                text = content_div.get_text(separator="\n", strip=True)
                # 过滤过短的内容
                if len(text) > 100:
                    return text

        # 兜底：取 body 文本
        body = soup.find("body")
        if body:
            for tag in body.select(
                "script, style, nav, header, footer, iframe, .amz-header, .amz-footer"
            ):
                tag.decompose()
            text = body.get_text(separator="\n", strip=True)
            lines = [
                line.strip() for line in text.split("\n") if len(line.strip()) > 20
            ]
            return "\n".join(lines[:100])

        return ""

    def crawl_list(self, url: str) -> list[dict]:
        """覆盖父类方法，从多个列表页爬取"""
        all_articles = []
        seen_urls = set()

        # 使用配置的多个列表页 URL
        for list_url in self.LIST_URLS:
            logger.info(f"  → 爬取列表页: {list_url}")
            html = self.fetch(list_url)
            if not html:
                continue
            articles = self.extract_article_list(html)
            for a in articles:
                if a["url"] not in seen_urls:
                    seen_urls.add(a["url"])
                    all_articles.append(a)
            self._random_delay()

        logger.info(
            f"  → [{self.source_name}] 共找到 {len(all_articles)} 篇文章（来自 {len(self.LIST_URLS)} 个列表页）"
        )
        return all_articles[: self.config.MAX_ARTICLES_PER_SOURCE]
