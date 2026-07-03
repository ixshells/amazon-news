"""
基础解析器
"""

import random
import time
from abc import ABC, abstractmethod
from typing import Optional

import requests
from loguru import logger


class BaseParser(ABC):
    """所有来源解析器的基类"""

    # 来源标识，子类覆盖
    source_key: str = ""
    source_name: str = ""

    def __init__(self, config):
        self.config = config
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        if self.config.PROXY_URL:
            session.proxies = {
                "http": self.config.PROXY_URL,
                "https": self.config.PROXY_URL,
            }
        return session

    def _random_delay(self):
        """请求间随机延迟"""
        delay = random.uniform(
            self.config.REQUEST_DELAY_MIN,
            self.config.REQUEST_DELAY_MAX,
        )
        time.sleep(delay)

    def fetch(self, url: str) -> Optional[str]:
        """发送 HTTP 请求获取页面内容"""
        try:
            resp = self.session.get(
                url,
                timeout=self.config.TIMEOUT,
                allow_redirects=True,
            )
            resp.encoding = resp.apparent_encoding
            if resp.status_code == 200:
                return resp.text
            else:
                logger.warning(f"⚠️ {url} 返回状态码: {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"❌ 请求失败 {url}: {e}")
            return None

    @abstractmethod
    def extract_article_list(self, html: str) -> list[dict]:
        """
        从列表页 HTML 中提取文章列表
        返回: [{"title": str, "url": str, "excerpt": str, "publish_date": str}, ...]
        """
        ...

    @abstractmethod
    def extract_content(self, html: str, url: str) -> str:
        """
        从文章详情页中提取正文内容（纯文本）
        """
        ...

    def crawl_list(self, url: str) -> list[dict]:
        """
        爬取列表页，返回文章列表
        """
        logger.info(f"🔍 [{self.source_name}] 爬取列表页: {url}")
        html = self.fetch(url)
        if not html:
            return []
        articles = self.extract_article_list(html)
        logger.info(f"   → 找到 {len(articles)} 篇文章")
        return articles[: self.config.MAX_ARTICLES_PER_SOURCE]

    def crawl_article(self, url: str) -> str:
        """
        爬取文章详情页，返回正文
        """
        self._random_delay()
        html = self.fetch(url)
        if not html:
            return ""
        return self.extract_content(html, url)
