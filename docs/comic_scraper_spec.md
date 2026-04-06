# 漫画采集系统 — 技术规格文档 v1.0

> 目标站点：`https://www.18jmttios01.com/`（Flutter Web 应用）
> 关联域名：`www.jmtt.vip`
> 技术栈：Python 3.11+

---

## 一、项目概述

### 1.1 采集目标

| 数据类型 | 说明 |
|---------|------|
| 每日更新漫画列表 | 标题、作者、封面图、更新时间、上架时间 |
| 章节列表 | 章节标题、章节序号、更新时间 |
| 章节图片 | 章节内所有图片、章节封面图 |

### 1.2 账号信息

通过 `.env` 文件管理（**禁止明文写入代码或配置文件**）：

```bash
# .env
COMIC_USERNAME=13384214400
COMIC_PASSWORD=123456
```

---

## 二、技术方案

### 2.1 站点特征分析

该站点为 **Flutter Web 应用**，具有以下特点：

- 页面内容由 `main.dart.js` 动态渲染，无法直接通过 HTML 解析
- 使用 CanvasKit 渲染引擎
- 数据通过内部 API 加载（JSON 接口）
- 追踪域名：`www.18jmttreport.xyz`

### 2.2 采集策略：API 抓包优先

**推荐方案：抓取 API 接口（优先）**

1. 使用浏览器 DevTools → Network 面板，筛选 XHR/Fetch 请求
2. 登录后操作页面，记录以下接口：
   - 登录接口（获取 Token / Cookie）
   - 每日更新列表接口
   - 漫画详情接口
   - 章节列表接口
   - 章节图片接口
3. 记录请求 Headers（Authorization、Cookie、User-Agent 等）
4. 用 Python `httpx` / `requests` 直接调用 API

**备选方案：Playwright 无头浏览器**

若 API 有加密签名或难以逆向，使用 Playwright 模拟浏览器操作：

```python
from playwright.async_api import async_playwright

async def scrape_with_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # 拦截 API 响应
        page.on("response", handle_response)
        await page.goto("https://www.18jmttios01.com/")
        # ...
```

### 2.3 API 抓包指引

开发前需要手动完成以下抓包工作，填入下方 `api_endpoints` 配置：

```
# 在浏览器中操作并记录以下接口：

1. 打开 DevTools → Network → 勾选 Preserve log
2. 访问首页，等待 Flutter 加载完成
3. 登录 → 记录登录接口 URL、请求体、响应体
4. 进入"每日更新"页面 → 记录列表接口
5. 点击某个漫画 → 记录详情接口
6. 点击某个章节 → 记录章节图片接口
7. 翻页 → 记录分页参数
```

---

## 三、项目结构

```
comic_scraper/
├── .env                        # 敏感信息（git忽略）
├── .gitignore
├── config.yaml                 # 非敏感配置
├── requirements.txt
├── main.py                     # 入口 + 调度
├── crawler/
│   ├── __init__.py
│   ├── auth.py                 # 登录 & Cookie/Token 管理
│   ├── client.py               # HTTP 客户端封装
│   ├── parser.py               # 数据解析
│   └── downloader.py           # 图片下载
├── db/
│   ├── __init__.py
│   ├── models.py               # 数据模型
│   └── database.py             # 数据库操作
├── utils/
│   ├── __init__.py
│   ├── logger.py               # 日志配置
│   └── time_parser.py          # 时间格式标准化
├── logs/                       # 日志目录
└── downloads/                  # 图片下载目录
    └── {comic_id}/
        └── {chapter_id}/
            ├── cover.jpg
            ├── 001.jpg
            ├── 002.jpg
            └── ...
```

---

## 四、配置文件

### 4.1 config.yaml

```yaml
# 站点配置
site:
  name: "jmtt"
  base_url: "https://www.18jmttios01.com"
  # API 端点（抓包后填入）
  api_endpoints:
    login: ""           # POST 登录
    daily_update: ""    # GET 每日更新列表
    comic_detail: ""    # GET 漫画详情 (参数: comic_id)
    chapter_list: ""    # GET 章节列表 (参数: comic_id)
    chapter_images: ""  # GET 章节图片 (参数: chapter_id)

# 采集配置
scraper:
  concurrent_downloads: 3         # 同域名并发数
  request_delay: [1.0, 3.0]      # 请求间隔（秒），随机取范围内值
  retry_max: 3                    # 失败重试次数
  retry_delay: 5                  # 重试等待（秒）
  download_timeout: 30            # 下载超时（秒）
  fail_rate_threshold: 0.3       # 失败率超过30%自动降速

# 存储配置
storage:
  download_dir: "./downloads"
  db_path: "./data/comics.db"     # SQLite

# 日志配置
logging:
  level: "INFO"
  dir: "./logs"
  max_days: 30
  max_size_mb: 50

# 调度配置
schedule:
  enabled: false
  cron: "0 8,20 * * *"           # 每天 8:00 和 20:00
```

---

## 五、数据库设计（SQLite）

### 5.1 漫画表 `comic`

```sql
CREATE TABLE comic (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    comic_id        VARCHAR(100) UNIQUE NOT NULL,   -- 站点漫画ID
    title           VARCHAR(500) NOT NULL,           -- 漫画标题
    author          VARCHAR(200),                    -- 作者（原始字符串）
    authors         TEXT,                            -- 结构化作者 JSON
    description     TEXT,                            -- 简介
    cover_url       VARCHAR(1000),                   -- 封面URL
    cover_local     VARCHAR(500),                    -- 封面本地路径
    tags            TEXT,                            -- 标签 JSON数组
    status          VARCHAR(50),                     -- 连载状态（连载中/已完结）
    publish_time    VARCHAR(100),                    -- 上架时间（原始值）
    update_time     VARCHAR(100),                    -- 更新时间（原始值）
    publish_time_std DATETIME,                       -- 上架时间（标准化）
    update_time_std  DATETIME,                       -- 更新时间（标准化）
    source_url      VARCHAR(1000),                   -- 原始页面URL
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 5.2 章节表 `chapter`

```sql
CREATE TABLE chapter (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id      VARCHAR(100) UNIQUE NOT NULL,    -- 站点章节ID
    comic_id        VARCHAR(100) NOT NULL,            -- 关联漫画ID
    title           VARCHAR(500),                     -- 章节标题
    chapter_order   INTEGER,                          -- 章节序号
    cover_url       VARCHAR(1000),                    -- 章节封面URL
    cover_local     VARCHAR(500),                     -- 章节封面本地路径
    image_count     INTEGER DEFAULT 0,                -- 图片总数
    update_time     VARCHAR(100),                     -- 更新时间（原始值）
    update_time_std DATETIME,                         -- 更新时间（标准化）
    crawl_status    VARCHAR(50) DEFAULT 'pending',   -- pending/images_fetched/completed
    source_url      VARCHAR(1000),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comic_id) REFERENCES comic(comic_id)
);

CREATE INDEX idx_chapter_comic ON chapter(comic_id);
CREATE INDEX idx_chapter_status ON chapter(crawl_status);
```

### 5.3 图片表 `image`

```sql
CREATE TABLE image (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id      VARCHAR(100) NOT NULL,
    image_order     INTEGER NOT NULL,                 -- 图片序号
    image_url       VARCHAR(1000) NOT NULL,           -- 原始URL
    local_path      VARCHAR(500),                     -- 本地保存路径
    file_size       INTEGER,                          -- 文件大小（bytes）
    download_status VARCHAR(50) DEFAULT 'pending',   -- pending/success/failed/skipped
    retry_count     INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapter(chapter_id)
);

CREATE INDEX idx_image_chapter ON image(chapter_id);
CREATE INDEX idx_image_status ON image(download_status);
```

### 5.4 运行日志表 `run_log`

```sql
CREATE TABLE run_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_time        DATETIME DEFAULT CURRENT_TIMESTAMP,
    comics_found    INTEGER DEFAULT 0,
    chapters_found  INTEGER DEFAULT 0,
    images_downloaded INTEGER DEFAULT 0,
    images_failed   INTEGER DEFAULT 0,
    duration_seconds REAL,
    status          VARCHAR(50),                     -- success/partial/failed
    error_message   TEXT
);
```

---

## 六、核心模块设计

### 6.1 auth.py — 登录与认证

```python
"""
职责：
- 登录获取 Token/Cookie
- Token 缓存与过期检测
- 自动续期
"""

class AuthManager:
    def __init__(self, config):
        self.username = os.getenv("COMIC_USERNAME")
        self.password = os.getenv("COMIC_PASSWORD")
        self.token = None
        self.token_expires_at = None

    async def login(self) -> str:
        """登录并返回 token/cookie"""
        ...

    def is_token_valid(self) -> bool:
        """检查 token 是否有效"""
        ...

    async def ensure_auth(self) -> str:
        """确保已登录，过期则重新登录"""
        ...
```

### 6.2 client.py — HTTP 客户端

```python
"""
职责：
- 统一管理请求头（UA轮换、Referer）
- 请求限速（Semaphore + delay）
- 失败重试（指数退避）
- 失败率监控与自动降速
"""

class HttpClient:
    def __init__(self, config, auth_manager):
        self.semaphore = asyncio.Semaphore(config["concurrent_downloads"])
        self.session = httpx.AsyncClient(timeout=config["download_timeout"])
        self.ua_pool = [...]  # 10+ User-Agent

    async def get(self, url, **kwargs) -> httpx.Response:
        """带限速、重试的 GET 请求"""
        ...

    async def download_image(self, url, save_path) -> bool:
        """下载图片并校验完整性"""
        ...
```

### 6.3 parser.py — 数据解析

```python
"""
职责：
- 解析 API JSON 响应
- 提取漫画列表、详情、章节、图片URL
- 时间字段标准化
"""

class ComicParser:
    def parse_daily_updates(self, data: dict) -> list[dict]:
        """解析每日更新列表"""
        ...

    def parse_comic_detail(self, data: dict) -> dict:
        """解析漫画详情（标题、作者、标签、简介等）"""
        ...

    def parse_chapter_list(self, data: dict) -> list[dict]:
        """解析章节列表"""
        ...

    def parse_chapter_images(self, data: dict) -> list[str]:
        """解析章节图片URL列表"""
        ...
```

### 6.4 downloader.py — 图片下载

```python
"""
职责：
- 并发下载图片（asyncio.Semaphore 控制）
- 图片完整性校验（Pillow verify）
- 失败重试
- 下载进度跟踪
"""

class ImageDownloader:
    async def download_chapter_images(self, chapter_id, image_urls, save_dir):
        """下载一个章节的所有图片"""
        ...

    def verify_image(self, path: str) -> bool:
        """校验图片文件是否完整"""
        try:
            from PIL import Image
            with Image.open(path) as img:
                img.verify()
            return True
        except Exception:
            return False
```

### 6.5 database.py — 数据库操作

```python
"""
职责：
- SQLite 连接管理
- CRUD 操作
- 事务保护（章节+图片同事务写入）
- 中断恢复查询
"""

class Database:
    def get_pending_chapters(self) -> list:
        """获取未完成的章节（用于中断恢复）"""
        ...

    def save_chapter_with_images(self, chapter, images):
        """事务写入章节及其图片记录"""
        with self.conn:  # 自动事务
            self.conn.execute("INSERT OR REPLACE INTO chapter ...", chapter)
            self.conn.executemany("INSERT OR REPLACE INTO image ...", images)

    def is_chapter_completed(self, chapter_id) -> bool:
        """判断章节是否已采集完成"""
        ...
```

---

## 七、采集流程

```
main.py 入口流程：

1. 加载配置 & 初始化日志
2. 初始化数据库（建表）
3. 登录获取 Token
4. 请求每日更新列表接口
5. 遍历更新列表：
   ├── 5.1 检查 comic 是否已存在
   │   ├── 不存在 → 请求详情接口 → 入库
   │   └── 已存在 → 跳过详情（按需补全缺失字段）
   ├── 5.2 请求章节列表
   ├── 5.3 遍历新章节（跳过已 completed 的）：
   │   ├── 请求章节图片接口 → 入库（crawl_status = images_fetched）
   │   ├── 并发下载图片 → 校验完整性
   │   └── 全部成功 → 更新 crawl_status = completed
   └── 5.4 记录运行日志
6. 输出采集统计
```

---

## 八、开发步骤

### Phase 1：基础搭建

1. 初始化项目结构、`requirements.txt`、`.env`、`.gitignore`
2. 实现 `config.yaml` 加载
3. 实现日志模块（`TimedRotatingFileHandler`，保留30天）
4. 实现数据库模块（建表、基础 CRUD）

### Phase 2：API 抓包与登录

5. **手动抓包**：用浏览器 DevTools 记录所有 API 端点和参数格式
6. 实现 `auth.py` 登录逻辑
7. 实现 `client.py` HTTP 客户端（UA轮换、限速、重试）

### Phase 3：采集核心

8. 实现每日更新列表采集
9. 实现漫画详情采集
10. 实现章节列表采集
11. 实现章节图片 URL 采集
12. 实现图片下载 + 完整性校验

### Phase 4：稳定性

13. 中断恢复（基于 `crawl_status`）
14. 数据库事务保护
15. 失败率监控与自动降速
16. 定时任务集成

---

## 九、依赖清单

```txt
# requirements.txt
httpx>=0.27.0           # 异步HTTP客户端
Pillow>=10.0.0          # 图片校验
pyyaml>=6.0             # 配置文件
python-dotenv>=1.0.0    # 环境变量
aiosqlite>=0.20.0       # 异步SQLite
apscheduler>=3.10.0     # 定时任务（可选）
fake-useragent>=1.5.0   # UA生成（可选）
playwright>=1.40.0      # 无头浏览器（备选方案）
```

---

## 十、.gitignore

```gitignore
.env
*.pyc
__pycache__/
logs/
downloads/
data/*.db
.venv/
```

---

## 十一、关键注意事项

1. **API 抓包是第一步**：在写任何采集代码之前，必须先用浏览器 DevTools 抓到真实 API 接口
2. **Flutter 站点特殊性**：该站点是 Flutter Web 应用，所有数据通过 JSON API 加载，HTML 中没有任何漫画数据
3. **限速保护**：同域名并发不超过 3，请求间隔 1-3 秒随机，避免触发风控
4. **图片下载后必须校验**：使用 `Pillow.Image.verify()` 确认文件完整
5. **每处理完一个章节立即写库**：不要批量缓存，防止中断丢数据
6. **Token/Cookie 过期处理**：请求返回 401 时自动重新登录
