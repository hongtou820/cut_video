"""
Javrate 采集器配置
"""

# 采集目标
BASE_URL = "https://www.javrate.com"
LIST_URL = f"{BASE_URL}/menu/censored/5-2-{{page}}"  # 页码占位符
START_PAGE = 1

# 采集范围：回溯到 2024-01-01
CUTOFF_DATE = "2024-01-01"

# 入库 API
API_BASE = "https://api.minggogogo.com"
API_IMPORT = f"{API_BASE}/api/videoCustomImport"
API_REVIEW = f"{API_BASE}/api/videoReviewInfo"
API_STATS = f"{API_BASE}/api/videoStatistics"

# 入库固定参数
VIDEO_TYPE = "日本"
VIDEO_SOURCE = "javrate"
VIDEO_RULE = "new视频"
VIDEO_USERNAME = "UPnewAV"

# FTP 配置
FTP_HOST = "api.minggogogo.com"  # 需要确认实际 FTP 地址
FTP_PORT = 21
FTP_USER = "UPnewAV"
FTP_PASS = "s7nbGFe5Vc"
FTP_BASE_DIR = "/UPnewAV"

# 本地存储
import os
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WORK_DIR, "data")
DOWNLOAD_DIR = os.path.join(WORK_DIR, "downloads")
STATE_FILE = os.path.join(WORK_DIR, "state.json")
LOG_DIR = os.path.join(WORK_DIR, "logs")

# 并发控制
MAX_CONCURRENT_DOWNLOADS = 3
DOWNLOAD_TIMEOUT = 120
PAGE_LOAD_TIMEOUT = 30000
CLOUDFLARE_WAIT = 10000  # Cloudflare 验证等待时间(ms)

# 浏览器配置
HEADLESS = True
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
