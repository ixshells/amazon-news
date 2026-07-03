"""
卖家之家 (mjzj.com) 新闻解析器

首页: https://mjzj.com/
卖家之家是亚马逊卖家社区 + 新闻资讯平台，有大量亚马逊相关的政策解读和运营干货。
"""

from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger

from .base import BaseParser


class MJZJParser(BaseParser):
    """卖家之家 解析器"""

    source_key = "mjzj"
    source_name = "卖家之家"

    def extract_article_list(self, html: str) -> list[dict]:
        """提取首页文章列表

        卖家之家 HTML 结构:
            div.main-minddle-col1  (主内容区)
              └─ div.article-wrap (文章卡片容器)
                   └─ a[href*='/article/']  (文章链接)
        """
        articles = []
        soup = BeautifulSoup(html, "lxml")

        # 主要选择器：找所有链接到文章详情页的链接
        # 卖家之家的文章链接格式: //mjzj.com/article/XXXXXXXX 或 https://mjzj.com/article/XXXXXXXX
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/article/" not in href:
                continue

            title = a.get("title", "") or a.get_text(strip=True)
            if not title or len(title) < 8:
                continue

            # 补全 URL
            if href.startswith("//"):
                full_url = "https:" + href
            elif href.startswith("/"):
                full_url = urljoin("https://mjzj.com", href)
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = urljoin("https://mjzj.com", href)

            # 摘要：通常标题后面跟着的描述文本
            excerpt = ""
            # 看 a 标签的父级是否包含描述
            parent = a.parent
            if parent:
                desc_el = parent.select_one("p.desc, span.desc, div.desc, p.summary")
                if desc_el:
                    excerpt = desc_el.get_text(strip=True)

            articles.append(
                {
                    "title": title[:200],
                    "url": full_url,
                    "excerpt": excerpt[:300],
                    "publish_date": "",
                }
            )

        # 去重
        seen = set()
        unique = []
        for a in articles:
            if a["url"] not in seen:
                seen.add(a["url"])
                unique.append(a)

        logger.info(f"  → 卖家之家解析到 {len(unique)} 篇文章")
        return unique

    def extract_content(self, html: str, url: str) -> str:
        """提取文章正文

        卖家之家文章详情页结构:
            h1.fw-bold.fs-2.text-black.mb-3  (标题)
            div.d-flex.mb-3                   (作者/日期)
            h5.fs-6.fw-bold                   (摘要)
            div.article-content               (正文)
        """
        soup = BeautifulSoup(html, "lxml")

        # 主要正文容器
        content_selectors = [
            "div.article-content",
            "article",
            "div.article-detail",
            "div.content",
            "div.post-content",
            "div.main-content",
        ]

        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                for tag in content_div.select(
                    "script, style, iframe, .ad, .ads, .share, .article-tags, .article-praise"
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
