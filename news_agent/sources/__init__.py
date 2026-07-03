"""
新闻来源解析器 - 各平台特定解析逻辑

每个解析器继承 BaseParser，实现 parse_list 方法（从列表页提取文章链接）
和 fetch_content 方法（从详情页提取正文）。
"""
