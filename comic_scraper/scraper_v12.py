"""
漫画采集器 v12 - 登录 + 采集今日更新 + 详细元数据
策略: 先进一次漫画触发教程弹窗(不可关闭), 回来后再正式采集
文件结构: downloads/{comic_id}/info.json + chapter_1/page_xxx.png
"""
import asyncio
import json
import hashlib
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = "https://www.18jmttios01.com"
OUT_DIR = Path("/Users/hongtou/av_biu/comic_scraper")
DL_DIR = OUT_DIR / "downloads"
DL_DIR.mkdir(parents=True, exist_ok=True)

PHONE = "13384214400"
PASSWORD = "123456"
STEP = 0


async def click(page, x, y, delay=2000):
    await page.mouse.click(x, y)
    await page.wait_for_timeout(delay)


async def shot(page, name):
    global STEP; STEP += 1
    p = str(OUT_DIR / f"W{STEP:02d}_{name}.png")
    await page.screenshot(path=p)
    print(f"  📸 W{STEP:02d}_{name}")
    return p


async def close_popups(page):
    await click(page, 100, 495, 2000)
    await click(page, 195, 760, 2000)
    await click(page, 195, 760, 1500)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(2000)


async def login(page):
    print("[登录] #/login → 密码登录...")
    await page.goto(f"{BASE_URL}/#/login", timeout=30000)
    await page.wait_for_timeout(5000)
    await click(page, 275, 85, 2000)
    await click(page, 195, 145, 500)
    await page.keyboard.type(PHONE, delay=80)
    await click(page, 195, 200, 500)
    await page.keyboard.type(PASSWORD, delay=80)
    await click(page, 195, 320, 5000)
    ok = "login" not in page.url
    print(f"  {'✅ 成功' if ok else '❌ 失败'} → {page.url}")
    return ok


async def go_home_and_latest(page):
    """回首页 → 关弹窗 → 最新tab"""
    await page.goto(BASE_URL, timeout=60000)
    await page.wait_for_timeout(15000)
    await close_popups(page)
    await click(page, 154, 71, 3000)  # 最新tab


async def scrape_pages(page, save_dir, max_scroll=80):
    """截图采集漫画页面"""
    save_dir.mkdir(parents=True, exist_ok=True)
    page_num = 0
    prev_hash = ""
    stale = 0
    for _ in range(max_scroll):
        ss = await page.screenshot()
        h = hashlib.md5(ss).hexdigest()
        if h != prev_hash:
            prev_hash = h
            page_num += 1
            with open(str(save_dir / f"page_{page_num:03d}.png"), "wb") as f:
                f.write(ss)
            stale = 0
        else:
            stale += 1
            if stale >= 5:
                break
        await page.mouse.wheel(0, 700)
        await page.wait_for_timeout(1000)
    return page_num


async def scrape_detail_page(page):
    """在漫画详情页截图, 采集元数据截图"""
    # 截图详情页上部 (封面、标题、作者等)
    cover_path = await shot(page, "detail_top")

    # 滚动看更多信息
    await page.mouse.wheel(0, 300)
    await page.wait_for_timeout(1000)
    await shot(page, "detail_mid")

    # 滚回去
    await page.mouse.wheel(0, -300)
    await page.wait_for_timeout(500)

    return cover_path


async def main():
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"{'='*50}")
    print(f"漫画采集 v12 — {now}")
    print(f"{'='*50}")

    all_comics = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844}, has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15")
        page = await ctx.new_page()

        # === 1. 加载 ===
        print("\n[1] 加载首页...")
        await page.goto(BASE_URL, timeout=60000)
        await page.wait_for_timeout(28000)
        await close_popups(page)

        # === 2. 登录 ===
        print("\n[2] 登录...")
        await login(page)

        # === 3. 触发教程弹窗 (牺牲一次进入) ===
        print("\n[3] 触发教程弹窗...")
        await go_home_and_latest(page)
        await click(page, 70, 220, 5000)  # 随便进一本
        print(f"  触发URL: {page.url}")
        await shot(page, "tutorial_trigger")
        # 不尝试关闭, 直接回去, 让app记住教程已显示

        # === 4. 最新tab截图 ===
        print("\n[4] 最新tab...")
        await go_home_and_latest(page)
        await shot(page, "latest_page")

        # 最新tab 3列布局:
        # 第一排 y≈220: x=70, 195, 320
        # 第二排 y≈370: x=70, 195, 320
        comics_to_scrape = [
            {"pos": (70, 220), "name": "comic_1"},
            {"pos": (195, 220), "name": "comic_2"},
        ]

        for ci, comic_cfg in enumerate(comics_to_scrape):
            cx, cy = comic_cfg["pos"]
            print(f"\n[{5+ci}] 漫画{ci+1} — 点击 ({cx}, {cy})...")

            # 进最新tab
            if ci > 0:
                await go_home_and_latest(page)

            # 点击漫画缩略图
            await click(page, cx, cy, 8000)
            url = page.url
            print(f"  URL: {url}")

            # 生成 comic_id
            comic_id = f"jm_{today}_{ci+1}"
            comic_dir = DL_DIR / comic_id
            comic_dir.mkdir(parents=True, exist_ok=True)

            comic_info = {
                "comic_id": comic_id,
                "url": url,
                "scraped_at": now,
                "source": "禁漫天堂",
                "source_url": BASE_URL,
                "cover_screenshot": None,
                "detail_screenshots": [],
                "chapters": [],
            }

            if "read" in url:
                # 直接进了阅读器 (没有详情页)
                await shot(page, f"c{ci+1}_reader")
                print(f"  采集中...")
                chapter_dir = comic_dir / "chapter_1"
                n = await scrape_pages(page, chapter_dir)
                comic_info["chapters"].append({
                    "chapter_num": 1,
                    "pages": n,
                    "path": "chapter_1/",
                })
                print(f"  ✓ {n} 页")
            elif url != f"{BASE_URL}/#/home":
                # 详情页
                print(f"  进入详情页, 截图元数据...")
                cover = await scrape_detail_page(page)
                comic_info["cover_screenshot"] = str(Path(cover).name)

                # 截取封面图单独保存
                cover_ss = await page.screenshot()
                cover_path = str(comic_dir / "cover.png")
                with open(cover_path, "wb") as f:
                    f.write(cover_ss)
                comic_info["cover_screenshot"] = "cover.png"

                # 点"开始阅读"按钮 (通常在底部)
                await click(page, 195, 750, 5000)
                read_url = page.url
                print(f"  阅读器URL: {read_url}")

                if "read" in read_url:
                    await shot(page, f"c{ci+1}_reader")
                    print(f"  采集中...")
                    chapter_dir = comic_dir / "chapter_1"
                    n = await scrape_pages(page, chapter_dir)
                    comic_info["chapters"].append({
                        "chapter_num": 1,
                        "pages": n,
                        "path": "chapter_1/",
                    })
                    print(f"  ✓ {n} 页")
                else:
                    await shot(page, f"c{ci+1}_no_reader")
                    print(f"  未进入阅读器")
            else:
                print(f"  未进入漫画")

            # 保存 info.json
            with open(str(comic_dir / "info.json"), "w", encoding="utf-8") as f:
                json.dump(comic_info, f, ensure_ascii=False, indent=2)
            print(f"  → {comic_dir}/info.json")

            all_comics.append(comic_info)

        # === 最终验证 ===
        print(f"\n[{5+len(comics_to_scrape)}] 验证...")
        await page.goto(BASE_URL, timeout=60000)
        await page.wait_for_timeout(10000)
        await close_popups(page)
        await click(page, 357, 815, 3000)
        await shot(page, "final_mine")

        await browser.close()

    # 保存总记录
    record = {
        "scrape_time": now,
        "account": PHONE,
        "total_comics": len(all_comics),
        "comics": all_comics,
    }
    record_path = str(OUT_DIR / "scrape_record_v12.json")
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"完成! → scrape_record_v12.json")
    for c in all_comics:
        cdir = DL_DIR / c["comic_id"]
        total_pages = sum(ch["pages"] for ch in c["chapters"])
        ch_dirs = [d for d in cdir.iterdir() if d.is_dir()] if cdir.exists() else []
        total_files = sum(len(list(d.glob("*.png"))) for d in ch_dirs)
        total_sz = sum(f.stat().st_size for d in ch_dirs for f in d.glob("*.png"))
        print(f"  📗 {c['comic_id']}: {total_pages}页 | {total_sz//1024}KB | {len(c['chapters'])}章")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
