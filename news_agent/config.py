"""
新闻爬虫 & AI 分类器 - 配置管理
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env 文件（优先使用项目根目录的，其次使用本模块的）
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = Path(os.getenv("NEWS_OUTPUT_DIR", BASE_DIR / "output" / "news"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 数据库路径
DB_PATH = OUTPUT_DIR / "news.db"


class Config:
    """全局配置"""

    # ============================================================
    # AI 模型配置（用于新闻分类和摘要）
    # 支持 OpenAI、Anthropic，或本地 Ollama
    # ============================================================
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")  # openai / anthropic / ollama
    AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")

    # -- OpenAI --
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    # -- Anthropic --
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

    # -- Ollama（本地模型）--
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    # ============================================================
    # 爬虫配置
    # ============================================================
    REQUEST_DELAY_MIN = float(os.getenv("NEWS_DELAY_MIN", "1"))
    REQUEST_DELAY_MAX = float(os.getenv("NEWS_DELAY_MAX", "3"))
    MAX_ARTICLES_PER_SOURCE = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "80"))
    PROXY_URL = os.getenv("PROXY_URL", "")
    TIMEOUT = int(os.getenv("NEWS_TIMEOUT", "30"))

    # ============================================================
    # 新闻来源开关
    # ============================================================
    ENABLE_AMZ123 = os.getenv("ENABLE_AMZ123", "true").lower() == "true"
    ENABLE_MJZJ = os.getenv("ENABLE_MJZJ", "true").lower() == "true"  # 卖家之家
    ENABLE_IKJZD = os.getenv("ENABLE_IKJZD", "true").lower() == "true"  # 跨境知道
    ENABLE_WEARESELLERS = os.getenv("ENABLE_WEARESELLERS", "false").lower() == "true"
    ENABLE_UPKUAJING = (
        os.getenv("ENABLE_UPKUAJING", "true").lower() == "true"
    )  # 跨境魔方

    # ============================================================
    # 新闻来源列表
    # ============================================================
    SOURCES = {
        "amz123": {
            "name": "AMZ123",
            "enabled": ENABLE_AMZ123,
            "url": "https://www.amz123.com/t",
        },
        "mjzj": {
            "name": "卖家之家",
            "enabled": ENABLE_MJZJ,
            "url": "https://mjzj.com/",
        },
        "ikjzd": {
            "name": "跨境知道",
            "enabled": ENABLE_IKJZD,
            "url": "https://www.ikjzd.com/",
        },
        "wearesellers": {
            "name": "知无不言",
            "enabled": ENABLE_WEARESELLERS,
            "url": "https://www.wearesellers.com/",
        },
        "upkuajing": {
            "name": "跨境魔方",
            "enabled": ENABLE_UPKUAJING,
            "url": "https://www.upkuajing.com/blog",
        },
    }
