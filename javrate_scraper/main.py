"""
Javrate 采集器 - 主入口
每日运行：采集首页最新 → 下载封面 → FTP上传 → API入库
"""
import asyncio
import argparse
import json
import os
import logging
from datetime import datetime
from pathlib import Path

from config import LOG_DIR, STATE_FILE, DATA_DIR
from scraper import run_scraper
from uploader import run_upload


def setup_logging():
    """配置日志"""
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ]
    )
    return log_file


def show_status():
    """显示当前采集状态"""
    if not os.path.exists(STATE_FILE):
        print("尚未开始采集")
        return

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    total = len(state.get("scraped_codes", []))
    last_run = state.get("last_run", "从未运行")

    # 统计上传情况
    uploaded = 0
    pending = 0
    if os.path.exists(DATA_DIR):
        for fname in os.listdir(DATA_DIR):
            if fname.endswith(".json"):
                with open(os.path.join(DATA_DIR, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("uploaded"):
                    uploaded += 1
                else:
                    pending += 1

    print(f"{'=' * 40}")
    print(f"Javrate 采集器状态")
    print(f"{'=' * 40}")
    print(f"  总采集数: {total}")
    print(f"  已上传:   {uploaded}")
    print(f"  待上传:   {pending}")
    print(f"  上次运行: {last_run}")
    print(f"{'=' * 40}")


async def daily_run(scroll=10):
    """
    每日运行:
    1. 采集首页最新视频
    2. 上传 + 入库
    """
    print(f"\n{'=' * 60}")
    print(f"每日采集 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'=' * 60}")

    # 采集
    print("\n[步骤 1/2] 采集视频...")
    new_count = await run_scraper(try_detail=True, scroll_times=scroll)

    # 上传入库
    if new_count and new_count > 0:
        print("\n[步骤 2/2] 上传并入库...")
        run_upload()
    else:
        print("\n没有新视频，跳过上传")


def main():
    parser = argparse.ArgumentParser(description="Javrate 采集器")
    subparsers = parser.add_subparsers(dest="command", help="运行模式")

    # 每日采集
    daily_parser = subparsers.add_parser("daily", help="每日采集最新视频")
    daily_parser.add_argument("--scroll", type=int, default=10,
                              help="首页滚动次数，越多加载越多视频 (默认10)")

    # 仅采集（不上传）
    scrape_parser = subparsers.add_parser("scrape", help="仅采集（不上传）")
    scrape_parser.add_argument("--scroll", type=int, default=10, help="滚动次数")
    scrape_parser.add_argument("--no-detail", action="store_true", help="不尝试访问详情页")

    # 仅上传
    subparsers.add_parser("upload", help="上传未入库的视频")

    # 状态
    subparsers.add_parser("status", help="查看采集状态")

    args = parser.parse_args()

    if args.command == "daily":
        log_file = setup_logging()
        print(f"日志: {log_file}")
        asyncio.run(daily_run(scroll=args.scroll))

    elif args.command == "scrape":
        log_file = setup_logging()
        print(f"日志: {log_file}")
        asyncio.run(run_scraper(
            try_detail=not args.no_detail,
            scroll_times=args.scroll,
        ))

    elif args.command == "upload":
        run_upload()

    elif args.command == "status":
        show_status()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
