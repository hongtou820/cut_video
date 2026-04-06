"""
自动发现 API：用 Playwright headless 模式加载页面，拦截所有网络请求。
"""
import asyncio
import json
from playwright.async_api import async_playwright

API_LOG = []
ALL_REQUESTS = []

async def on_response(response):
    url = response.url
    ct = response.headers.get("content-type", "")

    # 跳过静态资源
    skip_ext = ['.js', '.css', '.png', '.jpg', '.gif', '.woff', '.ttf', '.ico', '.svg', '.wasm', '.map']
    if any(url.endswith(ext) or f"{ext}?" in url for ext in skip_ext):
        return
    if "report" in url or "analytics" in url or "vconsole" in url:
        return

    entry = {"url": url, "status": response.status, "content_type": ct}
    try:
        body = await response.text()
        if len(body) > 0:
            try:
                data = json.loads(body)
                entry["is_json"] = True
                entry["body"] = data
            except:
                entry["is_json"] = False
                entry["body_preview"] = body[:300]
    except:
        pass

    ALL_REQUESTS.append(entry)
    print(f"[{response.status}] {ct[:30]:30s} {url[:120]}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()
        page.on("response", on_response)

        print("=== 加载首页 ===")
        try:
            await page.goto("https://www.18jmttios01.com/", timeout=60000)
            # 等待 Flutter 加载
            await page.wait_for_timeout(15000)
        except Exception as e:
            print(f"首页加载: {e}")

        # 打印页面内容概览
        try:
            title = await page.title()
            print(f"页面标题: {title}")
            # 获取页面上所有可见文字
            text = await page.evaluate("document.body?.innerText?.substring(0, 500) || 'no text'")
            print(f"页面文字: {text[:300]}")
        except Exception as e:
            print(f"获取内容失败: {e}")

        # 尝试获取当前URL（可能有重定向）
        print(f"当前URL: {page.url}")

        # 尝试点击一些元素
        try:
            # 等更长时间让Flutter完全加载
            await page.wait_for_timeout(10000)
            text2 = await page.evaluate("document.body?.innerText?.substring(0, 1000) || 'no text'")
            print(f"\n等待后页面文字: {text2[:500]}")
        except:
            pass

        # 保存所有请求
        output_path = "/Users/hongtou/av_biu/comic_scraper/all_requests.json"
        # 过滤掉太大的body
        for req in ALL_REQUESTS:
            if "body" in req and isinstance(req["body"], dict):
                req["body_str"] = json.dumps(req["body"], ensure_ascii=False)[:1000]
                del req["body"]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ALL_REQUESTS, f, ensure_ascii=False, indent=2)

        print(f"\n共捕获 {len(ALL_REQUESTS)} 条请求，已保存到 {output_path}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
