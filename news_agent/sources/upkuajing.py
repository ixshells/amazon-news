"""
跨境魔方 (upkuajing.com) 新闻解析器

资讯页: https://www.upkuajing.com/blog
跨境魔方是外贸获客平台，其资讯频道涵盖大量亚马逊/跨境电商相关新闻。
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger

from .base import BaseParser


class UpKuajingParser(BaseParser):
    """跨境魔方 解析器"""

    source_key = "upkuajing"
    source_name = "跨境魔方"

    def extract_article_list(self, html: str) -> list[dict]:
        """
        提取资讯列表

        跨境魔方 HTML 结构:
            a.videoItem                            (文章卡片)
              └─ div.postTitle                     (标题)
              └─ div.postExcerpt                   (摘要)
              └─ span                              (日期: 2026年7月4日)
        """
        articles = []
        soup = BeautifulSoup(html, "lxml")

        for a in soup.find_all("a", class_="videoItem", href=True):
            href = a["href"]
            if "/knowledge/zixun/" not in href:
                continue

            # 标题
            title_el = a.select_one(".postTitle")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 5:
                continue

            # 摘要
            excerpt_el = a.select_one(".postExcerpt")
            excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""

            # 日期（中文格式: 2026年7月4日）
            date_span = a.find("span")
            date_str = date_span.get_text(strip=True) if date_span else ""
            # 转换为 ISO 格式 YYYY-MM-DD
            iso_date = self._cn_date_to_iso(date_str)

            # 补全 URL
            if href.startswith("//"):
                full_url = "https:" + href
            elif href.startswith("/"):
                full_url = urljoin("https://www.upkuajing.com", href)
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = urljoin("https://www.upkuajing.com", href)

            articles.append(
                {
                    "title": title[:200],
                    "url": full_url,
                    "excerpt": excerpt[:300],
                    "publish_date": iso_date,
                }
            )

        # 去重
        seen = set()
        unique = []
        for a in articles:
            if a["url"] not in seen:
                seen.add(a["url"])
                unique.append(a)

        logger.info(f"  → 跨境魔方解析到 {len(unique)} 篇文章")
        return unique

    def extract_content(self, html: str, url: str) -> str:
        """提取文章正文

        跨境魔方文章详情页结构:
            div.markdown  (正文 Markdown 渲染区)
        """
        soup = BeautifulSoup(html, "lxml")

        content_selectors = [
            "div.markdown",
            "div.article-content",
            "article",
            "div.content",
            "div.post-content",
        ]

        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                for tag in content_div.select(
                    "script, style, iframe, .ad, .ads, .share"
                ):
                    tag.decompose()
                text = content_div.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return text

        # 兜底
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
    def _cn_date_to_iso(cn_date: str) -> str:
        """将中文日期转为 ISO 格式

        '2026年7月4日' -> '2026-07-04'
        '2026年12月31日' -> '2026-12-31'
        """
        if not cn_date:
            return ""
        m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", cn_date)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        return cn_date
