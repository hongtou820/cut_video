# Javrate 采集器

采集 javrate.com 有码视频数据，下载图片/视频并上传至 FTP，通过 API 入库。

## 采集范围

- **网站**: https://www.javrate.com/menu/censored/5-2-1
- **目标**: 每日更新 + 回溯至 2024-01-01 上映视频
- **内容**: 封面图、预览图、预览视频

## 入库参数

| 字段 | 值 |
|------|-----|
| type | 日本 |
| source | javrate |
| rule | new视频 |
| username | UPnewAV |

## API 端点

- **入库**: `POST https://api.minggogogo.com/api/videoCustomImport`
- **审核状态**: `POST https://api.minggogogo.com/api/videoReviewInfo`
- **统计**: `POST https://api.minggogogo.com/api/videoStatistics`

## 安装

```bash
cd javrate_scraper
pip3 install -r requirements.txt
playwright install chromium
```

## 使用方式

### 每日采集（推荐 cron 运行）
```bash
python3 main.py daily --pages 5
```
采集前5页最新视频 → 下载媒体 → FTP上传 → API入库

### 回溯采集
```bash
python3 main.py backfill --pages 50
```
从上次断点继续向前采集，直到 2024-01-01

### 不限页数回溯
```bash
python3 main.py backfill
```
一直采集到 2024-01-01

### 仅上传（之前采集未上传的）
```bash
python3 main.py upload
```

### 查看状态
```bash
python3 main.py status
```

### 测试（采集1页）
```bash
python3 main.py test --page 1
```

## Crontab 每日定时

```bash
# 每天凌晨 3 点采集最新
0 3 * * * cd /Users/hongtou/av_biu/javrate_scraper && python3 main.py daily --pages 5 >> logs/cron.log 2>&1

# 每天凌晨 4 点回溯采集 20 页
0 4 * * * cd /Users/hongtou/av_biu/javrate_scraper && python3 main.py backfill --pages 20 >> logs/cron.log 2>&1
```

## 目录结构

```
javrate_scraper/
├── main.py              # 主入口（命令行）
├── config.py            # 配置文件
├── scraper.py           # 采集模块（Playwright）
├── uploader.py          # FTP上传 + API入库
├── requirements.txt     # Python 依赖
├── state.json           # 采集进度状态
├── data/                # 视频元数据 JSON
│   ├── ABW-001.json
│   └── ...
├── downloads/           # 下载的媒体文件
│   ├── ABW-001/
│   │   ├── cover.jpg
│   │   ├── preview_01.jpg
│   │   └── preview.mp4
│   └── ...
└── logs/                # 日志文件
```

## 工作流程

```
1. 列表页采集 → 获取番号/标题/封面URL/详情链接
2. 详情页采集 → 获取演员/标签/片商/预览图/预览视频URL
3. 下载媒体   → 封面图 + 预览图 + 预览视频
4. FTP上传    → 上传到 /{username}/{code}/ 目录
5. API入库    → 调用 videoCustomImport 接口
```

## 注意事项

- javrate.com 有 Cloudflare 保护，使用 Playwright 浏览器模拟访问
- 首次运行需要等待 Cloudflare 验证通过（约 10-30 秒）
- 如果 Cloudflare 持续拦截，可能需要在 config.py 中设置 `HEADLESS = False` 手动通过一次验证
- 采集器有断点续传功能，中断后再次运行会从上次位置继续
- FTP 密码在 config.py 中配置，生产环境建议使用环境变量
