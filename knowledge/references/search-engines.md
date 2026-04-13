# 搜索引擎速查表

> 位置：~/.claude/global-memory/knowledge/references/search-engines.md
> 用途：AI 需要搜索时按需读取此文件，不再作为独立 Skill

## 国内搜索引擎 (8)

| 引擎 | URL 模板 |
|------|---------|
| 百度 | `https://www.baidu.com/s?wd={keyword}` |
| 必应中国 | `https://cn.bing.com/search?q={keyword}&ensearch=0` |
| 必应国际 | `https://cn.bing.com/search?q={keyword}&ensearch=1` |
| 360 | `https://www.so.com/s?q={keyword}` |
| 搜狗 | `https://sogou.com/web?query={keyword}` |
| 微信搜索 | `https://wx.sogou.com/weixin?type=2&query={keyword}` |
| 头条 | `https://so.toutiao.com/search?keyword={keyword}` |
| 集思录 | `https://www.jisilu.cn/explore/?keyword={keyword}` |

## 国际搜索引擎 (9)

| 引擎 | URL 模板 | 特点 |
|------|---------|------|
| Google | `https://www.google.com/search?q={keyword}` | 综合最优 |
| Google HK | `https://www.google.com.hk/search?q={keyword}` | 中文优化 |
| DuckDuckGo | `https://duckduckgo.com/html/?q={keyword}` | 隐私优先 |
| Yahoo | `https://search.yahoo.com/search?p={keyword}` | |
| Startpage | `https://www.startpage.com/sp/search?query={keyword}` | Google 结果+隐私 |
| Brave | `https://search.brave.com/search?q={keyword}` | 独立索引 |
| Ecosia | `https://www.ecosia.org/search?q={keyword}` | |
| Qwant | `https://www.qwant.com/?q={keyword}` | EU GDPR |
| WolframAlpha | `https://www.wolframalpha.com/input?i={keyword}` | 知识计算 |

## 高级搜索操作符

| 操作符 | 示例 | 说明 |
|--------|------|------|
| `site:` | `site:github.com python` | 站内搜索 |
| `filetype:` | `filetype:pdf report` | 文件类型 |
| `""` | `"machine learning"` | 精确匹配 |
| `-` | `python -snake` | 排除词 |
| `OR` | `cat OR dog` | 或 |

## Google 时间过滤

| 参数 | 说明 |
|------|------|
| `tbs=qdr:h` | 过去 1 小时 |
| `tbs=qdr:d` | 过去 1 天 |
| `tbs=qdr:w` | 过去 1 周 |
| `tbs=qdr:m` | 过去 1 月 |
| `tbs=qdr:y` | 过去 1 年 |

## DuckDuckGo Bangs 快捷键

| Bang | 目标 |
|------|------|
| `!g` | Google |
| `!gh` | GitHub |
| `!so` | Stack Overflow |
| `!w` | Wikipedia |
| `!yt` | YouTube |
