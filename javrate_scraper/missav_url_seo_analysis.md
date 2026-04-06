# MissAV 网址 SEO 结构分析

> 分析对象：`https://missav.ws`
> 分析日期：2026-03-17
> 数据来源：robots.txt、sitemap.xml、sitemap 子文件

---

## 1. URL 整体架构

网站采用 **三层 URL 结构**，核心设计围绕 **多语言 + 版本号（dm前缀）+ 语义化路径**：

```
https://missav.ws / [dm{版本号}] / [语言代码] / [内容路径]
```

---

## 2. `dm{N}` 前缀解析

URL 中的 `dm203`、`dm265` 等并非内容分类，而是 **镜像/版本标识符**，每个语言对应不同的 dm 编号：

| 语言 | hreflang | 首页 dm 编号 | 示例 |
|------|----------|-------------|------|
| 繁體中文 (默认) | zh-Hant | dm265 | `missav.ws/dm265` |
| 简体中文 | zh-Hans | dm194 | `missav.ws/dm194/cn` |
| English | en | dm223 | `missav.ws/dm223/en` |
| 日本語 | ja | dm221 | `missav.ws/dm221/ja` |
| 한국어 | ko | dm210 | `missav.ws/dm210/ko` |
| Bahasa Melayu | ms | dm203 | `missav.ws/dm203/ms` |
| ภาษาไทย | th | dm190 | `missav.ws/dm190/th` |
| Deutsch | de | dm210 | `missav.ws/dm210/de` |
| Français | fr | dm204 | `missav.ws/dm204/fr` |
| Tiếng Việt | vi | dm193 | `missav.ws/dm193/vi` |
| Bahasa Indonesia | id | dm210 | `missav.ws/dm210/id` |
| Filipino | fil | dm215 | `missav.ws/dm215/fil` |
| Português | pt | dm204 | `missav.ws/dm204/pt` |

> **注意**：`dm` 前缀仅用于首页和内容详情页，分类列表页不使用 dm 前缀。

---

## 3. URL 模式分类

### 3.1 首页

| 类型 | URL 模式 | 示例 |
|------|---------|------|
| 默认(繁中) | `/dm{N}` | `/dm265` |
| 其他语言 | `/dm{N}/{lang}` | `/dm203/ms` |

### 3.2 分类列表页（无 dm 前缀）

| 页面 | 默认语言 URL | 多语言 URL |
|------|-------------|-----------|
| 类型/标签 | `/genres` | `/{lang}/genres` |
| 片商 | `/makers` | `/{lang}/makers` |
| 演员列表 | `/actresses` | `/{lang}/actresses` |
| 演员排行 | `/actresses/ranking` | `/{lang}/actresses/ranking` |
| 最新 | `/new` | `/{lang}/new` |
| 发行日 | `/release` | `/{lang}/release` |
| 无码流出 | `/uncensored-leak` | `/{lang}/uncensored-leak` |
| 中文字幕 | `/chinese-subtitle` | `/{lang}/chinese-subtitle` |
| 英文字幕 | `/english-subtitle` | `/{lang}/english-subtitle` |

### 3.3 品牌/来源频道页

这些频道页 URL 直接使用品牌名称作为路径 slug：

```
/siro, /luxu, /gana, /maan, /scute, /ara
/fc2, /heyzo, /tokyohot, /1pondo
/caribbeancom, /caribbeancompr, /10musume
/pacopacomama, /gachinco, /xxxav
/marriedslash, /naughty4610, /naughty0930
/madou, /twav, /furuke, /klive, /clive
```

多语言格式：`/{lang}/{brand-slug}`，如 `/cn/fc2`、`/en/heyzo`

### 3.4 内容详情页（使用 dm 前缀）

```
/{dm{N}}/{item-code}          ← 默认语言(繁中)
/{dm{N}}/{lang}/{item-code}   ← 其他语言
```

**示例**：
- `/dm19/qmill-001` — 繁中版
- `/dm18/cn/emoi-020` — 简中版
- `/dm18/en/mxgs-1151` — 英文版
- `/dm18/ja/nttr-051` — 日文版

> item-code 格式：`{系列前缀}-{编号}`（小写，连字符分隔）

### 3.5 演员详情页（使用 dm 前缀）

```
/{dm{N}}/actresses/{演员名}          ← 默认语言
/{dm{N}}/{lang}/actresses/{演员名}   ← 其他语言
```

**示例**：
- `/dm19/actresses/COCOLO`
- `/dm13/cn/actresses/あいだもも`（URL 编码）
- `/dm13/en/actresses/あづき美由`

> 演员名支持日文原名，URL 中使用 percent-encoding

### 3.6 演员动态/新闻页

```
/actresses/{演员名}/news
```

**示例**：`/actresses/加山夏子/news`

### 3.7 文章页

```
/articles                    ← 文章列表
/articles/{MongoDB ObjectID} ← 文章详情
```

**示例**：`/articles/6921d8d37316da000145d272`

---

## 4. 多语言 SEO 策略

### 4.1 hreflang 实现

每个页面在 sitemap 中通过 `xhtml:link` 声明 13 种语言的 alternate URL：

```xml
<xhtml:link rel="alternate" hreflang="zh-Hant" href="https://missav.ws/dm265" />
<xhtml:link rel="alternate" hreflang="zh-Hans" href="https://missav.ws/dm194/cn" />
<xhtml:link rel="alternate" hreflang="en" href="https://missav.ws/dm223/en" />
<xhtml:link rel="alternate" hreflang="ja" href="https://missav.ws/dm221/ja" />
<!-- ... 共13种语言 -->
```

### 4.2 两套多语言路由

网站对**不同类型页面**使用了不同的多语言路由方案：

| 页面类型 | 路由方案 | 示例 |
|---------|---------|------|
| 首页 | `dm{N}/{lang}` | `/dm203/ms` |
| 内容详情 | `dm{N}/{lang}/{code}` | `/dm18/en/emoi-020` |
| 演员详情 | `dm{N}/{lang}/actresses/{name}` | `/dm19/ko/actresses/COCOLO` |
| 列表/分类页 | `{lang}/{path}` | `/en/genres`、`/cn/new` |

> 繁体中文作为默认语言，URL 中不带语言代码前缀。

---

## 5. Sitemap 架构

### 5.1 Sitemap Index

```
sitemap.xml
├── sitemap_pages.xml        ← 所有静态页面（首页、分类、品牌频道）× 13语言
├── sitemap_articles.xml     ← 文章
├── sitemap_tweets.xml       ← 演员动态/新闻
├── sitemap_actresses_1~35.xml   ← 演员详情页（35个分片）
└── sitemap_items_1~486.xml      ← 内容详情页（486个分片）
```

### 5.2 规模估算

- 演员：35 个 sitemap 分片
- 内容：486 个 sitemap 分片（按每个 sitemap 约 1000 条 URL 计算，约 48.6 万条内容）
- 每条内容 × 13 种语言 = 理论上约 630 万个内容 URL

---

## 6. robots.txt 规则

```
User-agent: *
Disallow: /logout
Disallow: /*/logout
Disallow: /saved
Disallow: /*/saved

Sitemap: https://missav.ws/sitemap.xml
```

仅屏蔽了用户私有页面（登出、收藏），其余全部开放爬取。

---

## 7. SEO 要点总结

| SEO 要素 | 实现方式 |
|---------|---------|
| **URL 语义化** | 内容用 `{系列}-{编号}` 作为 slug，分类用英文词汇（genres/makers/new） |
| **多语言** | hreflang 标签 + 子目录方案（`/{lang}/`），覆盖 13 种语言 |
| **版本/镜像管理** | `dm{N}` 前缀区分不同部署版本，每个语言有独立编号 |
| **Sitemap** | 分片式 sitemap index，按内容类型和数量拆分 |
| **Crawl 控制** | robots.txt 极简配置，仅屏蔽用户态页面 |
| **URL 层级** | 扁平化设计，详情页最多 3-4 层路径 |
| **品牌 SEO** | 每个品牌拥有独立频道页（`/fc2`、`/heyzo` 等），可独立获取品牌词排名 |
| **关键词布局** | 分类页使用语义化英文 slug 作为关键词锚点（如 `uncensored-leak`、`chinese-subtitle`） |

---

## 8. URL 模式速查表

```
# 首页
https://missav.ws/dm{N}
https://missav.ws/dm{N}/{lang}

# 分类列表
https://missav.ws/[{lang}/]genres
https://missav.ws/[{lang}/]makers
https://missav.ws/[{lang}/]actresses
https://missav.ws/[{lang}/]actresses/ranking
https://missav.ws/[{lang}/]new
https://missav.ws/[{lang}/]release
https://missav.ws/[{lang}/]uncensored-leak
https://missav.ws/[{lang}/]chinese-subtitle
https://missav.ws/[{lang}/]english-subtitle

# 品牌频道
https://missav.ws/[{lang}/]{brand-slug}

# 内容详情
https://missav.ws/dm{N}/[{lang}/]{item-code}

# 演员详情
https://missav.ws/dm{N}/[{lang}/]actresses/{name}

# 演员新闻
https://missav.ws/actresses/{name}/news

# 文章
https://missav.ws/articles/{objectId}

# 语言代码: cn, en, ja, ko, ms, th, de, fr, vi, id, fil, pt
# (默认繁中不需要语言前缀)
```
