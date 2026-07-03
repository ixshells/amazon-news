#!/bin/bash
# ============================================================
# 亚马逊新闻情报系统 - 每日定时运行脚本
#
# 功能:
#   1. 爬取最新新闻
#   2. AI 分析分类
#   3. 生成 HTML 报告
# ============================================================

# 项目路径
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

# 输出路径
OUTPUT_DIR="${PROJECT_DIR}/output/news"
REPORT_FILE="${OUTPUT_DIR}/report-daily.html"
LOG_FILE="${OUTPUT_DIR}/daily-run.log"

# 确保目录存在
mkdir -p "$OUTPUT_DIR"

# 记录日志
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "📰 亚马逊情报日报 - 开始运行"
log "========================================"

# 1. 爬取新闻
log "🕷️  阶段 1/3: 爬取新闻..."
/usr/bin/python3 -m news_agent.main crawl 2>&1 | tee -a "$LOG_FILE"

# 2. AI 分析
log "🤖  阶段 2/3: AI 分析..."
/usr/bin/python3 -m news_agent.main analyze 2>&1 | tee -a "$LOG_FILE"

# 3. 生成 HTML 报告
log "📄  阶段 3/3: 生成 HTML 报告..."
/usr/bin/python3 -m news_agent.main export -o "$REPORT_FILE" -f html -d 1 2>&1 | tee -a "$LOG_FILE"

# 4. 发布到 GitHub Pages（docs/ 目录）
log "🚀  阶段 4/4: 发布到 GitHub Pages..."
cp "$REPORT_FILE" "${PROJECT_DIR}/docs/report-daily.html"
cd "$PROJECT_DIR"

git add docs/report-daily.html docs/index.html 2>&1 | tee -a "$LOG_FILE"

# 检查是否有新文章（有变化才提交）
if git diff --cached --quiet; then
    log "⏭️  没有新内容，跳过提交"
else
    git commit -m "📰 日报自动更新 $(date '+%Y-%m-%d %H:%M')" 2>&1 | tee -a "$LOG_FILE"
    git push origin main 2>&1 | tee -a "$LOG_FILE"
    log "✅ 已发布到 GitHub Pages"
fi

log "✅ 完成！报告已生成: $REPORT_FILE"
log "🌐 在线访问: https://ixshells.github.io/amazon/"
log "========================================"
