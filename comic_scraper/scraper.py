"""
漫画采集器 v9 - 稳定版
不切tab，直接在推荐页点击漫画
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = "https://www.18jmttios01.com"
OUT_DIR = Path("/Users/hongtou/av_biu/comic_scraper")
DL_DIR = OUT_DIR / "downloads"
DL_DIR.mkdir(parents=True, exist_ok=True)


async def click(page, x, y, delay=2000):
    await page.mouse.click(x, y)
    await page.wait_for_timeout(delay)


async def shot(page, name):
    p = str(OUT_DIR / f"{name}.png")
    await page.screenshot(path=p)
    print(f"  📸 {name}.png")


async def scrape_chapter(page, save_dir):
    save_dir.mkdir(parents=True, exist_ok=True)
    page_num = 0
    prev = b""
    stale = 0
    for _ in range(50):
        ss = await page.screenshot()
        if ss != prev:
            prev = ss
            page_num += 1
            with open(str(save_dir / f"page_{page_num:03d}.png"), "wb") as f:
                f.write(ss)
            stale = 0
        else:
            stale += 1
            if stale >= 3:
                break
        await page.mouse.wheel(0, 700)
        await page.wait_for_timeout(800)
    return page_num


async def main():
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"{'='*50}")
    print(f"漫画采集 v9 — {now}")
    print(f"{'='*50}")

    results = {"time": now, "comics": []}

    async with async_playwright() as p:
        # 用新的 context 确保无阅读历史
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844}, has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15")
        page = await ctx.new_page()

        # 1. 加载
        print("\n[1] 加载首页...")
        await page.goto(BASE_URL, timeout=60000)
        await page.wait_for_timeout(28000)  # Flutter 加载
        await shot(page, "s1_loaded")

        # 2. 关弹窗1: "再想想"
        print("\n[2] 关弹窗...")
        await click(page, 100, 495, 3000)  # "再想想"
        await shot(page, "s2a")

        # 关弹窗2: 签到 → "点击空白处关闭" 在底部
        await click(page, 195, 760, 3000)
        await shot(page, "s2b")

        # 保险
        await click(page, 195, 760, 2000)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(2000)
        await shot(page, "s2c_clean")

        # 3. 验证首页干净
        print("\n[3] 验证首页...")
        # 多等一会让Flutter稳定
        await page.wait_for_timeout(3000)
        await shot(page, "s3_verify")

        # 4. 第1本漫画 — 点击第一排左侧缩略图
        print("\n[4] 第1本漫画...")
        # 从 s2c_clean 截图分析:
        # "精品" 区域, 第一个漫画缩略图大约在 x=100, y=330
        # 但要避免点到"排行/游戏/应用/会员"区域 (y≈190)
        # 漫画缩略图明确在 y=270-430 范围
        print("  点击第一排左侧漫画缩略图 (100, 330)")
        await click(page, 100, 330, 8000)  # 长等待
        url1 = page.url
        print(f"  URL: {url1}")
        await shot(page, "s4_comic1")

        if "read" in url1:
            # 进入了阅读器，先关"我知道啦"
            await click(page, 195, 718, 2000)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1000)
            await shot(page, "s4b_reader_clean")
            print("  采集中...")
            n1 = await scrape_chapter(page, DL_DIR / "comic_1")
            results["comics"].append({"title": "漫画1", "pages": n1})
            print(f"  ✓ {n1} 页截图")
        elif "detail" in url1 or "album" in url1:
            # 进入了详情页
            await shot(page, "s4b_detail")
            # 找到第一章/开始阅读 按钮
            await click(page, 195, 700, 5000)  # 通常在底部
            await click(page, 195, 718, 2000)  # "我知道啦"
            n1 = await scrape_chapter(page, DL_DIR / "comic_1")
            results["comics"].append({"title": "漫画1", "pages": n1})
            print(f"  ✓ {n1} 页截图")
        else:
            print(f"  没离开首页 ({url1})")
            # 可能点到了其他区域，或漫画通过路由hash变化了
            # 尝试点击更精确的位置
            print("  重试: 点击更上方 (100, 300)")
            await click(page, 100, 300, 8000)
            url1b = page.url
            print(f"  URL: {url1b}")
            await shot(page, "s4c_retry")
            if url1b != f"{BASE_URL}/#/home":
                await click(page, 195, 718, 2000)
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(1000)
                n1 = await scrape_chapter(page, DL_DIR / "comic_1")
                results["comics"].append({"title": "漫画1", "pages": n1})
                print(f"  ✓ {n1} 页截图")
            else:
                results["comics"].append({"title": "漫画1-失败", "pages": 0})

        # 5. 返回首页
        print("\n[5] 返回首页...")
        # 用 goto 直接回首页确保干净
        await page.goto(BASE_URL, timeout=60000)
        await page.wait_for_timeout(20000)
        # 关弹窗
        await click(page, 100, 495, 2000)
        await click(page, 195, 760, 2000)
        await click(page, 195, 760, 1500)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(3000)
        await shot(page, "s5_back")

        # 6. 第2本漫画 — 点击第一排右侧
        print("\n[6] 第2本漫画...")
        print("  点击第一排右侧漫画缩略图 (290, 330)")
        await click(page, 290, 330, 8000)
        url2 = page.url
        print(f"  URL: {url2}")
        await shot(page, "s6_comic2")

        if "read" in url2 or url2 != f"{BASE_URL}/#/home":
            await click(page, 195, 718, 2000)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1000)
            await shot(page, "s6b_reader")
            print("  采集中...")
            n2 = await scrape_chapter(page, DL_DIR / "comic_2")
            results["comics"].append({"title": "漫画2", "pages": n2})
            print(f"  ✓ {n2} 页截图")
        else:
            print(f"  没进入漫画 ({url2})")
            results["comics"].append({"title": "漫画2-失败", "pages": 0})

        await browser.close()

    # 保存
    with open(str(OUT_DIR / "scrape_record.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print("完成!")
    for i, c in enumerate(results["comics"]):
        d = DL_DIR / f"comic_{i+1}"
        files = list(d.glob("*.png")) if d.exists() else []
        sz = sum(f.stat().st_size for f in files)
        print(f"  📗 {c['title']}: {c.get('pages',0)}页 | {sz//1024}KB | downloads/comic_{i+1}/")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
