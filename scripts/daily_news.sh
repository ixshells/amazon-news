#!/bin/bash
# ============================================================
# 亚马逊新闻情报系统 - 每日定时运行脚本
#
# 功能:
#   1. 爬取最新新闻
#   2. AI 分析分类
#   3. 生成 HTML 报告
#   4. 存档旧报告 + 发布到 GitHub Pages
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

# ---- 4a. 存档旧报告 ----
ARCHIVE_DIR="${PROJECT_DIR}/docs/reports"
mkdir -p "$ARCHIVE_DIR"
if [ -f "${PROJECT_DIR}/docs/report-daily.html" ]; then
    # 从旧报告中提取生成日期
    ARCHIVE_DATE=$(/usr/bin/python3 -c "
import re
with open('${PROJECT_DIR}/docs/report-daily.html') as f:
    m = re.search(r'generation-date\" content=\"(\d{4}-\d{2}-\d{2})', f.read())
    print(m.group(1) if m else '')
" 2>/dev/null)
    if [ -n "$ARCHIVE_DATE" ]; then
        # 避免重复归档（如果当天已运行过）
        if [ ! -f "${ARCHIVE_DIR}/${ARCHIVE_DATE}.html" ]; then
            cp "${PROJECT_DIR}/docs/report-daily.html" "${ARCHIVE_DIR}/${ARCHIVE_DATE}.html"
            log "📦 已归档旧报告: ${ARCHIVE_DATE}.html"
        else
            log "⏭️  今日已归档，跳过重复归档"
        fi
    else
        log "⚠️  无法提取旧报告日期，跳过归档"
    fi
fi

# ---- 4b. 复制新报告 ----
cp "$REPORT_FILE" "${PROJECT_DIR}/docs/report-daily.html"

# ---- 4c. 生成 reports.json（历史列表用）----
/usr/bin/python3 -c "
import json, glob, os
reports_dir = '${ARCHIVE_DIR}'
files = sorted(
    [{'date': os.path.basename(f).replace('.html', '')} for f in glob.glob(os.path.join(reports_dir, '*.html'))],
    key=lambda x: x['date'],
    reverse=True
)
with open(os.path.join('${PROJECT_DIR}/docs', 'reports.json'), 'w') as f:
    json.dump({'reports': files}, f, ensure_ascii=False)
" 2>&1 | tee -a "$LOG_FILE"

cd "$PROJECT_DIR"

git add docs/report-daily.html docs/index.html docs/reports.json docs/reports/ 2>&1 | tee -a "$LOG_FILE"

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
