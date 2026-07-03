"""
新闻情报系统 - 命令行入口

用法:
    # 爬取所有启用的新闻来源
    python -m news_agent.main crawl

    # 爬取指定来源
    python -m news_agent.main crawl --source amz123

    # AI 分析所有未分类文章
    python -m news_agent.main analyze

    # 完整流程：爬取 + AI 分析
    python -m news_agent.main run

    # 查看分类统计
    python -m news_agent.main stats

    # 查看每日简报
    python -m news_agent.main digest

    # 导出 Markdown 报告
    python -m news_agent.main export --output report.md

    # 列出可用新闻来源
    python -m news_agent.main list-sources
"""

import argparse
import sys
from pathlib import Path

# 确保项目路径正确
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from news_agent.classifier import NewsClassifier
from news_agent.config import Config
from news_agent.crawler import NewsCrawler
from news_agent.models import CATEGORIES
from news_agent.reporter import NewsReporter

# 日志配置
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO",
)


def cmd_crawl(args):
    """爬取新闻"""
    config = Config()
    crawler = NewsCrawler(config)

    if args.source:
        if args.source not in config.SOURCES:
            logger.error(f"❌ 未知来源: {args.source}")
            logger.info(f"可用来源: {', '.join(config.SOURCES.keys())}")
            return
        articles = crawler.crawl_source(args.source)
    else:
        articles = crawler.crawl_all()

    logger.info(f"\n📊 本次爬取新增 {len(articles)} 篇文章")


def cmd_analyze(args):
    """AI 分析未分类文章"""
    config = Config()
    classifier = NewsClassifier(config)

    if args.all:
        # 分析所有（包括已分类的，重新分类）
        from news_agent.models import get_all_articles

        articles = get_all_articles(limit=100)
        logger.info(f"🔄 重新分析 {len(articles)} 篇文章")
        classifier.classify_and_save_batch(articles)
    else:
        stats = classifier.process_all_unread()

    # 打印统计
    reporter = NewsReporter(config)
    reporter.print_category_summary()


def cmd_run(args):
    """完整流程：爬取 + AI 分析"""
    config = Config()

    # 1. 爬取
    logger.info("🕷️ === 阶段 1: 爬取新闻 ===")
    crawler = NewsCrawler(config)
    new_articles = crawler.crawl_all()

    # 2. AI 分析
    if new_articles or args.force_analyze:
        logger.info("\n🤖 === 阶段 2: AI 分析 ===")
        classifier = NewsClassifier(config)
        classifier.classify_and_save_batch(new_articles)

        # 3. 打印报告
        reporter = NewsReporter(config)
        reporter.print_category_summary()
    else:
        # 分析所有未读的
        logger.info("\n🤖 === 阶段 2: AI 分析未分类文章 ===")
        classifier = NewsClassifier(config)
        classifier.process_all_unread()

    logger.info("✅ 完整流程执行完毕")


def cmd_stats(args):
    """查看分类统计"""
    config = Config()
    reporter = NewsReporter(config)
    reporter.print_category_summary()


def cmd_digest(args):
    """查看简报"""
    config = Config()
    reporter = NewsReporter(config)
    reporter.print_daily_digest(days=args.days)


def cmd_export(args):
    """导出报告"""
    config = Config()
    reporter = NewsReporter(config)

    if args.format == "html":
        reporter.export_to_html(args.output, days=args.days)
    else:
        content = reporter.export_to_markdown(args.output)
        if not args.output:
            print(content)


def cmd_list_sources(args):
    """列出可用来源"""
    config = Config()

    print(f"\n{'=' * 50}")
    print("📰 可用新闻来源")
    print(f"{'=' * 50}")

    for key, cfg in config.SOURCES.items():
        status = "✅ 已启用" if cfg["enabled"] else "⏸️  已禁用"
        print(f"\n  {status} | {cfg['name']} ({key})")
        print(f"        URL: {cfg['url']}")

    print(f"\n💡 提示: 通过 .env 文件或环境变量控制启用/禁用")
    print(f"   如: ENABLE_AMZ123=true  ENABLE_YUGUO=false")


def cmd_categories(args):
    """列出分类体系"""
    print(f"\n{'=' * 50}")
    print("🏷️  新闻分类体系")
    print(f"{'=' * 50}")

    for key, info in CATEGORIES.items():
        print(f"\n  {info['emoji']} {info['label']} ({key})")
        print(f"     {info['description']}")


def main():
    parser = argparse.ArgumentParser(
        description="📰 亚马逊新闻情报系统 - 爬取 + AI 分类",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 一键运行：爬取 + 分析
  python -m news_agent.main run

  # 仅爬取
  python -m news_agent.main crawl

  # 仅 AI 分析
  python -m news_agent.main analyze

  # 查看今天的简报
  python -m news_agent.main digest

  # 查看分类统计
  python -m news_agent.main stats

  # 导出完整报告
  python -m news_agent.main export -o report.md
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ---- crawl ----
    crawl_parser = subparsers.add_parser("crawl", help="爬取新闻")
    crawl_parser.add_argument(
        "-s", "--source", default="", help="指定来源 (amz123 / yuguo / ebrun)"
    )

    # ---- analyze ----
    analyze_parser = subparsers.add_parser("analyze", help="AI 分析未分类文章")
    analyze_parser.add_argument(
        "--all", action="store_true", help="重新分析所有文章（包括已分类的）"
    )

    # ---- run ----
    run_parser = subparsers.add_parser("run", help="完整流程：爬取 + AI 分析")
    run_parser.add_argument(
        "--force-analyze", action="store_true", help="即使没有新文章也强制分析"
    )

    # ---- stats ----
    subparsers.add_parser("stats", help="查看分类统计")

    # ---- digest ----
    digest_parser = subparsers.add_parser("digest", help="查看简报")
    digest_parser.add_argument(
        "-d", "--days", type=int, default=1, help="最近几天（默认 1 天）"
    )

    # ---- export ----
    export_parser = subparsers.add_parser("export", help="导出报告 (Markdown / HTML)")
    export_parser.add_argument("-o", "--output", default="", help="输出文件路径")
    export_parser.add_argument(
        "-f", "--format", default="html", choices=["html", "markdown"], help="输出格式"
    )
    export_parser.add_argument("-d", "--days", type=int, default=7, help="覆盖最近几天")
    export_parser.add_argument(
        "--md",
        action="store_const",
        dest="format",
        const="markdown",
        help="等同于 --format markdown",
    )

    # ---- list-sources ----
    subparsers.add_parser("list-sources", help="列出可用新闻来源")

    # ---- categories ----
    subparsers.add_parser("categories", help="查看分类体系说明")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "crawl": cmd_crawl,
        "analyze": cmd_analyze,
        "run": cmd_run,
        "stats": cmd_stats,
        "digest": cmd_digest,
        "export": cmd_export,
        "list-sources": cmd_list_sources,
        "categories": cmd_categories,
    }

    func = commands.get(args.command)
    if func:
        func(args)


if __name__ == "__main__":
    main()
