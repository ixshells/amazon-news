"""
跨境魔方 (upkuajing.com) 新闻解析器

资讯页: https://www.upkuajing.com/blog
跨境魔方是外贸获客平台，其资讯频道涵盖大量亚马逊/跨境电商相关新闻。

注意：blog 页面分页是客户端渲染（Vue.js），只能拿到第一页 15 篇文章。
因此改用 sitemap 发现所有文章 URL，然后逐个爬取详情。
"""

import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from loguru import logger

from .base import BaseParser

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


class UpKuajingParser(BaseParser):
    """跨境魔方 解析器"""

    source_key = "upkuajing"
    source_name = "跨境魔方"

    def crawl_list(self, url: str) -> list[dict]:
        """
        从 sitemap 发现所有知识文章 URL
        """
        logger.info(f"🔍 [{self.source_name}] 从 sitemap 发现文章...")
        article_urls = self._discover_from_sitemap()

        if not article_urls:
            logger.warning(f"⚠️  sitemap 未发现文章，回退到列表页")
            html = self.fetch(url)
            if html:
                return self.extract_article_list(html)
            return []

        max_count = self.config.MAX_ARTICLES_PER_SOURCE
        article_urls = article_urls[:max_count]

        logger.info(f"  → 发现 {len(article_urls)} 篇文章")
        return [
            {"title": "", "url": article_url, "excerpt": "", "publish_date": ""}
            for article_url in article_urls
        ]

    def _discover_from_sitemap(self) -> list[str]:
        """从 sitemap 索引中发现所有知识文章 URL"""
        tag_loc = f"{{{SITEMAP_NS}}}loc"
        tag_sitemap = f"{{{SITEMAP_NS}}}sitemap"
        tag_url = f"{{{SITEMAP_NS}}}url"

        try:
            sess = requests.Session()
            sess.headers.update(
                {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36",
                }
            )

            # 1. 获取 sitemap 索引
            resp = sess.get(
                "https://www.upkuajing.com/sitemap.xml", timeout=self.config.TIMEOUT
            )
            root = ET.fromstring(resp.content)

            # 2. 找到所有 knowledge sitemap（直接 tag 名，不用命名空间映射）
            knowledge_sitemaps = []
            for child in root:
                if child.tag == tag_sitemap:
                    loc_el = child.find(tag_loc)
                    if loc_el is not None and "knowledge" in loc_el.text.lower():
                        knowledge_sitemaps.append(loc_el.text)

            if not knowledge_sitemaps:
                logger.warning("⚠️  未找到 knowledge sitemap")
                return []

            logger.info(f"  → 找到 {len(knowledge_sitemaps)} 个 knowledge sitemap")

            # 3. 解析每个 knowledge sitemap
            all_urls = []
            for sitemap_url in knowledge_sitemaps:
                try:
                    resp2 = sess.get(
                        sitemap_url, timeout=min(self.config.TIMEOUT * 2, 120)
                    )
                    root2 = ET.fromstring(resp2.content)
                    count_before = len(all_urls)
                    for child in root2:
                        if child.tag == tag_url:
                            loc_el = child.find(tag_loc)
                            if (
                                loc_el is not None
                                and "/knowledge/zixun/" in loc_el.text
                            ):
                                all_urls.append(loc_el.text)
                    count = len(all_urls) - count_before
                    logger.info(f"    → 解析到 {count} 篇文章")
                except Exception as e:
                    logger.warning(f"⚠️  解析 sitemap 失败: {e}")

            logger.info(f"  → 共发现 {len(all_urls)} 篇知识文章")
            # 返回最新的在前（sitemap 按 ID 升序排列，ID 越大越新）
            all_urls.reverse()
            return all_urls

        except Exception as e:
            logger.error(f"❌ 获取 sitemap 索引失败: {e}")
            return []

    def extract_article_list(self, html: str) -> list[dict]:
        """从列表页 HTML 提取文章（备用方案）"""
        articles = []
        soup = BeautifulSoup(html, "lxml")

        for a in soup.find_all("a", class_="videoItem", href=True):
            href = a["href"]
            if "/knowledge/zixun/" not in href:
                continue
            title_el = a.select_one(".postTitle")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 5:
                continue
            excerpt_el = a.select_one(".postExcerpt")
            excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""
            date_span = a.find("span")
            date_str = date_span.get_text(strip=True) if date_span else ""
            iso_date = self._cn_date_to_iso(date_str)
            full_url = self._resolve_url(href)
            articles.append(
                {
                    "title": title[:200],
                    "url": full_url,
                    "excerpt": excerpt[:300],
                    "publish_date": iso_date,
                }
            )

        seen = set()
        unique = []
        for a in articles:
            if a["url"] not in seen:
                seen.add(a["url"])
                unique.append(a)
        logger.info(f"  → 跨境魔方解析到 {len(unique)} 篇文章")
        return unique

    def crawl_article(self, url: str) -> str:
        """爬取文章详情页，返回正文（同时提取标题）"""
        self._random_delay()
        html = self.fetch(url)
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.find("h1")
        self._last_title = h1.get_text(strip=True) if h1 else ""
        return self.extract_content(html, url)

    def extract_content(self, html: str, url: str) -> str:
        """提取文章正文"""
        soup = BeautifulSoup(html, "lxml")
        for selector in [
            "div.markdown",
            "div.article-content",
            "article",
            "div.content",
            "div.post-content",
        ]:
            content_div = soup.select_one(selector)
            if content_div:
                for tag in content_div.select(
                    "script, style, iframe, .ad, .ads, .share"
                ):
                    tag.decompose()
                text = content_div.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return text
        body = soup.find("body")
        if body:
            for tag in body.select("script, style, nav, header, footer, iframe"):
                tag.decompose()
            text = body.get_text(separator="\n", strip=True)
            lines = [
                line.strip() for line in text.split("\n") if len(line.strip()) > 20
            ]
            return "\n".join(lines[:100])
        return ""

    @staticmethod
    def _resolve_url(href: str) -> str:
        if href.startswith("//"):
            return "https:" + href
        elif href.startswith("/"):
            return urljoin("https://www.upkuajing.com", href)
        elif href.startswith("http"):
            return href
        return urljoin("https://www.upkuajing.com", href)

    @staticmethod
    def _cn_date_to_iso(cn_date: str) -> str:
        if not cn_date:
            return ""
        m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", cn_date)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        return cn_date
