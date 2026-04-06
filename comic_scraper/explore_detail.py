"""
探索阅读器右上角图标 → 找详情页
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE_URL = "https://www.18jmttios01.com"
OUT = Path("/Users/hongtou/av_biu/comic_scraper")
N = 0

async def click(page, x, y, delay=2000):
    await page.mouse.click(x, y)
    await page.wait_for_timeout(delay)

async def shot(page, name):
    global N; N += 1
    p = str(OUT / f"E{N:02d}_{name}.png")
    await page.screenshot(path=p)
    print(f"  📸 E{N:02d}_{name}")

async def close_popups(page):
    await click(page, 100, 495, 2000)
    await click(page, 195, 760, 2000)
    await click(page, 195, 760, 1500)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(2000)

async def login(page):
    await page.goto(f"{BASE_URL}/#/login", timeout=30000)
    await page.wait_for_timeout(5000)
    await click(page, 275, 85, 2000)
    await click(page, 195, 145, 500)
    await page.keyboard.type("13384214400", delay=80)
    await click(page, 195, 200, 500)
    await page.keyboard.type("123456", delay=80)
    await click(page, 195, 320, 5000)
    print(f"  登录: {page.url}")

async def main():
    print("=== 探索详情页 ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844}, has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15")
        page = await ctx.new_page()

        # 加载 + 关弹窗 + 登录
        print("[1] 加载+登录...")
        await page.goto(BASE_URL, timeout=60000)
        await page.wait_for_timeout(28000)
        await close_popups(page)
        await login(page)

        # 触发教程弹窗
        print("[2] 触发教程...")
        await page.goto(BASE_URL, timeout=60000)
        await page.wait_for_timeout(15000)
        await close_popups(page)
        await click(page, 154, 71, 3000)  # 最新tab
        await click(page, 70, 220, 5000)  # 进入漫画(触发教程)

        # 回来正式进入
        print("[3] 正式进入漫画...")
        await page.goto(BASE_URL, timeout=60000)
        await page.wait_for_timeout(15000)
        await close_popups(page)
        await click(page, 154, 71, 3000)  # 最新tab
        await click(page, 70, 220, 8000)  # 进入漫画
        await shot(page, "reader")
        print(f"  URL: {page.url}")

        # 点击屏幕中央唤醒菜单
        print("[4] 唤醒菜单...")
        await click(page, 195, 420, 2000)  # 点中央
        await shot(page, "menu_shown")

        # 查看顶部和底部菜单栏
        # 顶部: < 标题  [图标1] [图标2] [图标3] [图标4]
        # 底部: 设置 | 横屏 | 目录 | 选集

        # 尝试点右上角各个图标
        print("[5] 点击右上角图标...")

        # 先唤醒菜单
        await click(page, 195, 420, 1500)

        # 图标大约在 x=290, 310, 340, 370, y=25
        # 第一个图标
        await click(page, 290, 25, 2000)
        await shot(page, "icon1_290")
        print(f"  icon1 URL: {page.url}")

        # 回去
        if page.url != f"{BASE_URL}/#/read":
            await page.go_back()
            await page.wait_for_timeout(2000)

        # 唤醒菜单再试第二个
        await click(page, 195, 420, 1500)
        await click(page, 320, 25, 2000)
        await shot(page, "icon2_320")
        print(f"  icon2 URL: {page.url}")

        if page.url != f"{BASE_URL}/#/read":
            await page.go_back()
            await page.wait_for_timeout(2000)

        # 第三个
        await click(page, 195, 420, 1500)
        await click(page, 350, 25, 2000)
        await shot(page, "icon3_350")
        print(f"  icon3 URL: {page.url}")

        if page.url != f"{BASE_URL}/#/read":
            await page.go_back()
            await page.wait_for_timeout(2000)

        # 第四个
        await click(page, 195, 420, 1500)
        await click(page, 375, 25, 2000)
        await shot(page, "icon4_375")
        print(f"  icon4 URL: {page.url}")

        if page.url != f"{BASE_URL}/#/read":
            await shot(page, "detail_page")
            # 滚动看完整详情
            await page.mouse.wheel(0, 300)
            await page.wait_for_timeout(1000)
            await shot(page, "detail_scroll1")
            await page.mouse.wheel(0, 300)
            await page.wait_for_timeout(1000)
            await shot(page, "detail_scroll2")
            await page.go_back()
            await page.wait_for_timeout(2000)

        # 试试底部菜单: 目录
        print("[6] 底部菜单 - 目录...")
        await click(page, 195, 420, 1500)  # 唤醒
        await shot(page, "menu_bottom")

        # 底部: 设置(50,815) 横屏(140,815) 目录(250,815) 选集(340,815)
        await click(page, 250, 815, 2000)  # 目录
        await shot(page, "catalog")

        # 选集
        print("[7] 底部菜单 - 选集...")
        await click(page, 195, 420, 1500)
        await click(page, 340, 815, 2000)
        await shot(page, "episodes")

        await shot(page, "final")
        await browser.close()
    print("\n=== 完成, 查看 E*.png ===")

if __name__ == "__main__":
    asyncio.run(main())
