"""
Javrate 采集器 - 主爬虫模块
流程：
  1. javrate.com 首页获取番号列表（只采日本有码）
  2. avbase.net 获取完整元数据（标题/演员/片商/分类/日期/剧照）
  3. DMM CDN 下载封面 + 剧照
  4. jable.tv 下载完整视频 (HLS m3u8 → mp4)
"""
import asyncio
import json
import re
import os
import hashlib
import time
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
import httpx

from config import (
    BASE_URL, DATA_DIR, DOWNLOAD_DIR, STATE_FILE,
    HEADLESS, USER_AGENT, DOWNLOAD_TIMEOUT,
)
from metadata import enrich_video
from video_downloader import download_full_video


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scraped_codes": [], "last_run": None, "total_scraped": 0}


def save_state(state):
    state["last_run"] = datetime.now().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def ensure_dirs():
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


def parse_alt_text(alt_text):
    """从 img alt 解析番号和标题"""
    alt = re.sub(r'\s*封面\s*$', '', alt_text.strip())
    code_match = re.match(r'^([A-Z]{1,10}\d?-?\d{2,6}(?:-\d+)?)\s*(.*)', alt, re.I)
    if code_match:
        code = code_match.group(1).upper()
        title = code_match.group(2).strip()
        actress = ""
        actress_match = re.search(r'[~～]\s*(.+?)(?:\s*$)', title)
        if actress_match:
            actress = actress_match.group(1).strip()
        return code, title, actress
    return alt, alt, ""


def is_japanese_censored(code):
    """判断是否为日本有码视频（排除国产、无码等）"""
    code_upper = code.upper()
    # 常见无码前缀
    uncensored_prefixes = ["HEYZO", "1PON", "CARI", "PACO", "10MU", "GACHI"]
    for prefix in uncensored_prefixes:
        if code_upper.startswith(prefix):
            return False
    # 国产前缀
    chinese_prefixes = ["MM-", "MTVQ", "MD-", "MSD-", "PMC-", "MPG-", "RAS-", "SWAG"]
    for prefix in chinese_prefixes:
        if code_upper.startswith(prefix):
            return False
    # 有码视频通常是 2-5 个字母 + 3-5 个数字
    if re.match(r'^[A-Z]{2,5}-\d{3,5}$', code_upper):
        return True
    # 其他带 - 的也算
    if re.match(r'^[A-Z]{2,10}-\d{2,5}$', code_upper):
        return True
    return False


async def scrape_home_page(page):
    """从 javrate 首页提取视频番号列表"""
    videos = await page.evaluate("""
    () => {
        const cards = document.querySelectorAll('a[href*="Movie/Detail"]');
        const results = [];
        const seen = new Set();
        for (const card of cards) {
            const href = card.getAttribute('href') || '';
            if (seen.has(href)) continue;
            seen.add(href);
            const img = card.querySelector('img');
            if (!img) continue;
            results.push({
                detail_url: href,
                cover_url: img.src || img.dataset.src || img.dataset.original || '',
                alt_text: img.alt || '',
            });
        }
        return results;
    }
    """)

    parsed = []
    for v in videos:
        code, title, actress = parse_alt_text(v["alt_text"])
        if not code:
            continue
        detail_url = v["detail_url"]
        if not detail_url.startswith("http"):
            detail_url = BASE_URL + detail_url
        parsed.append({
            "code": code,
            "title": title or code,
            "actress": actress,
            "actresses": [actress] if actress else [],
            "detail_url": detail_url,
            "cover_url": v["cover_url"],
        })
    return parsed


async def download_file(client, url, save_path, timeout=None):
    """下载文件，返回 (成功, 大小)"""
    headers = {"User-Agent": UA, "Referer": "https://www.dmm.co.jp/"}
    t = timeout or DOWNLOAD_TIMEOUT
    for attempt in range(2):
        try:
            async with client.stream("GET", url, headers=headers, follow_redirects=True, timeout=t) as resp:
                if resp.status_code != 200:
                    return False, 0
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                total = 0
                with open(save_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        total += len(chunk)
                if total > 500:
                    return True, total
                else:
                    os.remove(save_path)
                    return False, 0
        except Exception as e:
            if attempt == 0:
                await asyncio.sleep(1)
            else:
                pass  # 静默失败，不刷屏
        # 清理失败的文件
        if os.path.exists(save_path):
            os.remove(save_path)
    return False, 0


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


async def download_all_media(video_data):
    """下载封面 + 剧照 + 预览视频"""
    code = video_data["code"]
    code_dir = os.path.join(DOWNLOAD_DIR, code)
    Path(code_dir).mkdir(parents=True, exist_ok=True)
    downloaded = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=300)) as client:
        # 1. 高清封面 (优先 DMM，失败回退 avking)
        cover_urls = []
        if video_data.get("cover_hd_url"):
            cover_urls.append(video_data["cover_hd_url"])
        if video_data.get("cover_url") and video_data["cover_url"] not in cover_urls:
            cover_urls.append(video_data["cover_url"])

        for cover_url in cover_urls:
            ext = "jpg" if ".jpg" in cover_url else "webp"
            cover_path = os.path.join(code_dir, f"cover.{ext}")
            if not os.path.exists(cover_path):
                ok, size = await download_file(client, cover_url, cover_path)
                if ok:
                    downloaded.append(("cover", cover_path, size))
                    print(f"      封面: {size // 1024}KB")
                    break

        # 2. 剧照
        screenshots = video_data.get("screenshots", [])
        for i, img_url in enumerate(screenshots):
            ext = "jpg"
            img_path = os.path.join(code_dir, f"screenshot_{i + 1:02d}.{ext}")
            if not os.path.exists(img_path):
                ok, size = await download_file(client, img_url, img_path)
                if ok:
                    downloaded.append(("screenshot", img_path, size))
                await asyncio.sleep(0.2)
        if screenshots:
            print(f"      剧照: {sum(1 for d in downloaded if d[0] == 'screenshot')} / {len(screenshots)} 张")

        # 3. 完整视频 (jable.tv HLS → mp4)
        full_vid_path = os.path.join(code_dir, f"{code}.mp4")
        if not os.path.exists(full_vid_path) or os.path.getsize(full_vid_path) < 50 * 1024 * 1024:
            print(f"      下载完整视频 (jable.tv)...")
            ok, vid_path, size = download_full_video(code, output_dir=code_dir)
            if ok:
                downloaded.append(("video", vid_path, size))
            else:
                # 回退：下载 DMM 预览视频
                print(f"      完整视频失败，尝试 DMM 预览...")
                preview_path = os.path.join(code_dir, "preview.mp4")
                if not os.path.exists(preview_path):
                    candidates = video_data.get("preview_video_candidates", [])
                    if not candidates and video_data.get("preview_video"):
                        candidates = [video_data["preview_video"]]
                    for vid_url in candidates:
                        ok, size = await download_file(client, vid_url, preview_path, timeout=300)
                        if ok:
                            downloaded.append(("video", preview_path, size))
                            print(f"      预览视频: {size // 1024}KB")
                            break
        else:
            size = os.path.getsize(full_vid_path)
            downloaded.append(("video", full_vid_path, size))

    return downloaded


def compute_md5(filepath):
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def save_video_data(video_data):
    code = video_data["code"]
    # 保存到 data/ 目录
    data_path = os.path.join(DATA_DIR, f"{code}.json")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(video_data, f, ensure_ascii=False, indent=2)
    # 同时保存一份到 downloads/{code}/ 目录（方便跟进）
    code_dir = os.path.join(DOWNLOAD_DIR, code)
    Path(code_dir).mkdir(parents=True, exist_ok=True)
    with open(os.path.join(code_dir, "info.json"), "w", encoding="utf-8") as f:
        json.dump(video_data, f, ensure_ascii=False, indent=2)


async def run_scraper(scroll_times=10):
    """
    运行采集器
    scroll_times: 首页滚动次数
    """
    ensure_dirs()
    state = load_state()
    scraped_codes = set(state.get("scraped_codes", []))
    total_new = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=USER_AGENT,
            locale="zh-TW",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)
        page = await context.new_page()

        # 1. 访问首页
        print(f"\n{'=' * 60}")
        print(f"Javrate 采集器 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'=' * 60}")
        print("\n[1/4] 访问 javrate.com 首页...")
        await page.goto(BASE_URL, timeout=60000)
        await page.wait_for_timeout(12000)

        title = await page.title()
        if "Cloudflare" in title or "Just a moment" in title:
            print("  等待 Cloudflare...")
            for _ in range(20):
                await page.wait_for_timeout(2000)
                title = await page.title()
                if "Cloudflare" not in title:
                    break
            else:
                print("  Cloudflare 验证失败，退出")
                await browser.close()
                return 0

        print(f"  首页加载成功: {await page.title()}")

        # 2. 滚动加载
        print(f"\n[2/4] 滚动加载 ({scroll_times} 次)...")
        for i in range(scroll_times):
            await page.mouse.wheel(0, 1000)
            await page.wait_for_timeout(2000)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(2000)

        # 3. 提取番号
        print("\n[3/4] 提取视频列表...")
        videos = await scrape_home_page(page)
        await browser.close()

        # 只保留日本有码
        censored = [v for v in videos if is_japanese_censored(v["code"])]
        skipped = len(videos) - len(censored)
        print(f"  总计 {len(videos)} 个视频, 日本有码 {len(censored)} 个, 跳过 {skipped} 个")

        # 去掉已采集
        new_videos = [v for v in censored if v["code"] not in scraped_codes]
        print(f"  新视频: {len(new_videos)}, 已采集: {len(censored) - len(new_videos)}")

        if not new_videos:
            print("\n没有新视频")
            return 0

        # 4. 补全元数据 + 下载
        print(f"\n[4/4] 采集 {len(new_videos)} 个新视频...")

        for i, v in enumerate(new_videos):
            print(f"\n  [{i + 1}/{len(new_videos)}] {v['code']}")

            # 从 avbase 获取完整元数据
            print(f"    查询 avbase.net...")
            enriched = enrich_video(v)

            # 打印关键信息
            print(f"    标题: {enriched.get('title', '')[:50]}")
            print(f"    演员: {', '.join(enriched.get('actresses', []))}")
            print(f"    片商: {enriched.get('studio', '')}")
            print(f"    日期: {enriched.get('date', '')}")
            print(f"    分类: {', '.join(enriched.get('tags', [])[:5])}")
            print(f"    剧照: {len(enriched.get('screenshots', []))} 张")
            print(f"    视频: {'有' if enriched.get('preview_video') else '无'}")

            # 下载所有媒体
            print(f"    下载媒体文件...")
            files = await download_all_media(enriched)
            enriched["local_files"] = [{"type": t, "path": p, "size": s} for t, p, s in files]

            # 保存
            save_video_data(enriched)
            scraped_codes.add(enriched["code"])
            total_new += 1

            file_summary = f"封面={sum(1 for f in files if f[0]=='cover')}"
            file_summary += f" 剧照={sum(1 for f in files if f[0]=='screenshot')}"
            file_summary += f" 视频={sum(1 for f in files if f[0]=='video')}"
            print(f"    ✓ 完成 ({file_summary})")

            # 保存状态
            state["scraped_codes"] = list(scraped_codes)
            state["total_scraped"] = len(scraped_codes)
            save_state(state)

            time.sleep(1)  # 礼貌延迟

    print(f"\n{'=' * 60}")
    print(f"采集完成!")
    print(f"  本次新增: {total_new} 个日本有码视频")
    print(f"  总计: {len(scraped_codes)} 个")
    print(f"{'=' * 60}")

    return total_new


if __name__ == "__main__":
    asyncio.run(run_scraper(scroll_times=5))
