"""
AI 新闻分类器

使用 LLM 自主阅读新闻内容，进行:
  1. 内容分类（一级分类：policy / platform / trends / operations / logistics / risk）
  2. 二级分类（自由标签）
  3. 重要性评估（high / medium / low）
  4. 摘要生成

支持多种 AI 后端:
  - OpenAI (GPT-4o, GPT-4o-mini, 等)
  - Anthropic (Claude 3.5, Claude 3, 等)
  - Ollama (本地模型，如 qwen2.5, deepseek-r1 等)
"""

import json
import sqlite3
from datetime import datetime
from typing import Optional

from loguru import logger

from news_agent.config import Config
from news_agent.models import (
    CATEGORIES,
    CATEGORY_KEYS,
    Article,
    get_connection,
    get_unread_articles,
    mark_as_read,
)

# ============================================================
# 分类 prompt 模板
# ============================================================

CLASSIFY_SYSTEM_PROMPT = """你是一位亚马逊跨境电商领域的资深情报分析师。

你的任务是从亚马逊卖家的视角，阅读新闻文章并给出专业的分类、评分和总结。

## 分类体系
请从以下六大类别中选择最合适的一个：

1. **政策法规** (policy): 亚马逊平台政策更新、关税/贸易政策、税务政策、合规认证要求
2. **平台动态** (platform): 新功能发布、费用调整、Prime Day/黑五等大促、亚马逊服务变更
3. **行业趋势** (trends): 市场数据报告、消费趋势分析、品类风向变化、竞争格局
4. **运营干货** (operations): 选品策略、广告投放技巧、Listing优化、供应链管理
5. **物流仓储** (logistics): FBA政策更新、物流渠道变化、仓储费用调整
6. **风险预警** (risk): 账号安全、侵权风险、虚假评论打击、封号潮、合规风险

## 综合评分（0-100）
请根据以下维度综合打分，**只给整数**：

| 维度 | 权重 | 评分标准 |
|------|------|---------|
| **亚马逊相关性** | 40分 | 是否直接关于亚马逊平台？40=核心亚马逊政策/功能，20=间接相关(多平台对比)，0=完全不相关 |
| **政策重要性** | 30分 | 是否涉及政策法规变化？30=重大政策更新，15=一般性政策，0=无政策内容 |
| **卖家影响度** | 20分 | 对亚马逊卖家的直接影响？20=直接影响运营/利润，10=间接参考价值，0=无影响 |
| **时效紧迫性** | 10分 | 是否需要立即行动？10=必须马上关注，5=值得了解，0=纯背景信息 |

> 打分示例：亚马逊FBA费用调整公告 → 95分（亚马逊直接相关40+政策20+卖家影响25+时效10）
> 打分示例：某品类海外市场需求增长 → 55分（亚马逊相关20+政策0+卖家影响25+时效10）
> 打分示例： unrelated general tech news → 10分

## TL;DR 一句话总结
用**10-30个字**写一句极简总结，让卖家一眼判断是否值得阅读。
格式："[核心要点]"

示例："亚马逊FBA仓储费7月上调15%"
示例："TikTok Shop美区向中国卖家开放入驻"
示例："亚马逊标题新规限制75字符"

## 输出格式
只输出 JSON 格式，不要包含任何其他文字：

```json
{{
    "category": "policy|platform|trends|operations|logistics|risk",
    "subcategory": "更具体的二级分类（中文，如'FBA费用调整'或'账号审核政策'）",
    "tags": ["标签1", "标签2", "标签3（最多5个，中英文均可）"],
    "importance": "high|medium|low",
    "score": 85,
    "tldr": "10-30字的一句话极简总结",
    "summary": "用 2-3 句话客观总结文章的核心内容（中文），突出对亚马逊卖家的影响",
    "impact": "这篇文章对亚马逊卖家的影响分析（一句话，中文）"
}}
```"""


class NewsClassifier:
    """AI 新闻分类器"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.client = self._init_client()
        self.model = self._get_model_name()

    def _init_client(self):
        """初始化 AI 客户端"""
        provider = self.config.AI_PROVIDER

        if provider == "openai":
            return self._init_openai()
        elif provider == "anthropic":
            return self._init_anthropic()
        elif provider == "ollama":
            return self._init_ollama()
        else:
            raise ValueError(
                f"不支持的 AI 提供商: {provider}，可选: openai / anthropic / ollama"
            )

    def _init_openai(self):
        from openai import OpenAI

        if not self.config.OPENAI_API_KEY:
            logger.warning("⚠️ OPENAI_API_KEY 未设置，使用 Ollama 作为降级方案")
            return self._init_ollama()
        return OpenAI(
            api_key=self.config.OPENAI_API_KEY,
            base_url=self.config.OPENAI_BASE_URL,
        )

    def _init_anthropic(self):
        try:
            from anthropic import Anthropic
        except ImportError:
            logger.warning("⚠️ anthropic 包未安装。运行: pip install anthropic")
            raise

        if not self.config.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY 未设置")
        return Anthropic(api_key=self.config.ANTHROPIC_API_KEY)

    def _init_ollama(self):
        from openai import OpenAI

        return OpenAI(
            api_key="ollama",
            base_url=f"{self.config.OLLAMA_BASE_URL}/v1",
        )

    def _get_model_name(self) -> str:
        provider = self.config.AI_PROVIDER
        if provider == "openai":
            return self.config.AI_MODEL
        elif provider == "anthropic":
            return self.config.ANTHROPIC_MODEL
        elif provider == "ollama":
            return self.config.OLLAMA_MODEL
        return self.config.AI_MODEL

    def classify(self, article: Article) -> dict:
        """
        对一篇文章进行分类
        返回: {"category": str, "subcategory": str, "tags": list, "importance": str, "summary": str}
        """
        # 截取内容避免超出 token 限制（取前 4000 字符）
        content = article.content[:4000]
        title = article.title

        user_message = f"""## 文章标题
{title}

## 文章正文
{content}"""

        try:
            result = self._call_llm(user_message)
            parsed = self._parse_result(result, title)
            return parsed
        except Exception as e:
            logger.error(f"❌ AI 分类失败 [{title[:30]}...]: {e}")
            return {
                "category": "trends",
                "subcategory": "未分类",
                "tags": [],
                "importance": "medium",
                "score": 30,
                "tldr": "",
                "summary": f"AI 分类失败: {e}",
                "impact": "",
            }

    def _call_llm(self, user_message: str) -> str:
        """调用 LLM"""
        provider = self.config.AI_PROVIDER

        if provider == "anthropic":
            return self._call_anthropic(user_message)
        else:
            # OpenAI 和 Ollama 都兼容 OpenAI SDK
            return self._call_openai_compat(user_message)

    def _call_openai_compat(self, user_message: str) -> str:
        """调用 OpenAI 兼容 API（包括 Ollama）"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    def _call_anthropic(self, user_message: str) -> str:
        """调用 Anthropic Claude"""
        response = self.client.messages.create(
            model=self.model,
            system=CLASSIFY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            temperature=0.1,
            max_tokens=800,
        )
        return response.content[0].text

    def _parse_result(self, result: str, title: str) -> dict:
        """解析 LLM 返回的 JSON"""
        # 尝试从 markdown 代码块中提取 JSON
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0].strip()
        elif "```" in result:
            result = result.split("```")[1].split("```")[0].strip()

        data = json.loads(result)

        # 验证并修正分类
        category = data.get("category", "trends")
        if category not in CATEGORY_KEYS:
            logger.warning(f"  ⚠️ 未知分类 '{category}'，默认设为 'trends'")
            category = "trends"

        # 提取并校验分数
        score = data.get("score", 50)
        try:
            score = int(score)
        except (ValueError, TypeError):
            score = 50
        score = max(0, min(100, score))

        return {
            "category": category,
            "subcategory": data.get("subcategory", "")[:50],
            "tags": [str(t) for t in data.get("tags", [])][:5],
            "importance": data.get("importance", "medium"),
            "score": score,
            "tldr": data.get("tldr", "")[:60],
            "summary": data.get("summary", "")[:500],
            "impact": data.get("impact", "")[:200],
        }

    def process_all_unread(self) -> dict:
        """
        处理所有未分类的文章
        返回处理统计
        """
        articles = get_unread_articles(limit=100)
        if not articles:
            logger.info("📭 没有待处理的文章")
            return {"total": 0, "by_category": {}}

        logger.info(f"\n{'=' * 50}")
        logger.info(f"🤖 AI 开始分析 {len(articles)} 篇文章")
        logger.info(f"{'=' * 50}")

        stats = {"total": 0, "by_category": {}}

        for i, article in enumerate(articles, 1):
            logger.info(f"   [{i}/{len(articles)}] 分析: {article.title[:50]}...")

            # 先获取数据库 ID
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT id FROM articles WHERE url = ?", (article.url,)
                ).fetchone()
                db_id = row["id"] if row else None
            finally:
                conn.close()

            if not db_id:
                logger.warning(f"   ⚠️ 未找到数据库记录: {article.title[:40]}...")
                continue

            # AI 分类（只调用一次 LLM）
            result = self.classify(article)

            # 用真实 ID 更新数据库
            mark_as_read(
                article_id=db_id,
                category=result["category"],
                subcategory=result["subcategory"],
                tags=result["tags"],
                importance=result["importance"],
                score=result["score"],
                tldr=result["tldr"],
                summary=result["summary"],
            )

            # 显示结果（含分数和 TL;DR）
            cat_info = CATEGORIES.get(result["category"], {})
            score_str = f"{'🔴' if result['score'] >= 75 else '🟡' if result['score'] >= 50 else '🟢'} {result['score']}分"
            tldr = result.get("tldr", "")
            logger.info(
                f"     {score_str} | {cat_info.get('emoji', '📄')} {cat_info.get('label', result['category'])}"
                f" | 🏷️ {', '.join(result['tags'][:3])}"
            )
            if tldr:
                logger.info(f"     💬 {tldr}")

            # 统计
            stats["total"] += 1
            cat = result["category"]
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

        logger.info(f"\n✅ AI 分析完成: 共处理 {stats['total']} 篇文章")
        for cat, count in sorted(stats["by_category"].items()):
            cat_info = CATEGORIES.get(cat, {})
            logger.info(
                f"   {cat_info.get('emoji', '📄')} {cat_info.get('label', cat)}: {count} 篇"
            )

        return stats

    def classify_and_save_batch(self, articles: list[Article]) -> list[Article]:
        """对一批文章进行分类，更新到数据库中（批量处理版本）"""
        import sqlite3

        from news_agent.models import get_connection

        for article in articles:
            try:
                result = self.classify(article)
                conn = get_connection()
                try:
                    row = conn.execute(
                        "SELECT id FROM articles WHERE url = ?", (article.url,)
                    ).fetchone()
                    if row:
                        mark_as_read(
                            article_id=row["id"],
                            category=result["category"],
                            subcategory=result["subcategory"],
                            tags=result["tags"],
                            importance=result["importance"],
                            score=result["score"],
                            tldr=result["tldr"],
                            summary=result["summary"],
                        )
                        article.category = result["category"]
                        article.subcategory = result["subcategory"]
                        article.tags = result["tags"]
                        article.importance = result["importance"]
                        article.score = result["score"]
                        article.tldr = result["tldr"]
                        article.is_read = True
                finally:
                    conn.close()
            except Exception as e:
                logger.error(f"❌ 分类失败 [{article.title[:30]}...]: {e}")

        return articles

    def get_category_label(self, key: str) -> str:
        """获取分类的中文标签"""
        info = CATEGORIES.get(key, {})
        return info.get("label", key)
