"""
用 Playwright 拦截网络请求，发现漫画站点的 API 接口。
非 headless 模式运行，手动登录后观察 API 调用。
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

API_LOG = []

async def handle_response(response):
    url = response.url
    content_type = response.headers.get("content-type", "")

    # 只关注 JSON API 请求，排除静态资源和追踪
    if "json" in content_type or "/api" in url or "comic" in url.lower() or "chapter" in url.lower() or "album" in url.lower() or "photo" in url.lower():
        if "report" in url or "analytics" in url or ".js" in url or ".css" in url:
            return

        status = response.status
        try:
            body = await response.text()
            # 尝试解析JSON
            try:
                data = json.loads(body)
                body_preview = json.dumps(data, ensure_ascii=False, indent=2)[:2000]
            except:
                body_preview = body[:500]
        except:
            body_preview = "(无法读取)"

        entry = {
            "url": url,
            "status": status,
            "content_type": content_type,
            "body_preview": body_preview
        }
        API_LOG.append(entry)
        print(f"\n{'='*80}")
        print(f"[API] {status} {url}")
        print(f"Content-Type: {content_type}")
        print(f"Body: {body_preview[:500]}")
        print(f"{'='*80}")

async def handle_request(route, request):
    """拦截所有请求，打印非静态资源请求"""
    url = request.url
    if not any(ext in url for ext in ['.js', '.css', '.png', '.jpg', '.gif', '.woff', '.ttf', '.ico', '.svg', '.wasm']):
        if 'report' not in url and 'analytics' not in url:
            print(f"[REQ] {request.method} {url}")
            headers = request.headers
            if 'authorization' in headers:
                print(f"  Auth: {headers['authorization'][:50]}...")
            if 'cookie' in headers:
                print(f"  Cookie: {headers['cookie'][:80]}...")
    await route.continue_()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()

        # 拦截请求和响应
        await page.route("**/*", handle_request)
        page.on("response", handle_response)

        print("正在打开网站...")
        await page.goto("https://www.18jmttios01.com/", wait_until="networkidle", timeout=60000)
        print("\n页面已加载。请在浏览器中手动操作：")
        print("1. 登录（账号：13384214400，密码：123456）")
        print("2. 浏览每日更新页面")
        print("3. 点击一个漫画查看详情")
        print("4. 点击一个章节查看图片")
        print("\n所有 API 请求会自动记录。操作完成后按 Ctrl+C 退出。")

        try:
            # 等待用户操作
            await asyncio.sleep(600)
        except KeyboardInterrupt:
            pass

        # 保存日志
        with open("/Users/hongtou/av_biu/comic_scraper/api_log.json", "w", encoding="utf-8") as f:
            json.dump(API_LOG, f, ensure_ascii=False, indent=2)
        print(f"\n已保存 {len(API_LOG)} 条 API 记录到 api_log.json")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
