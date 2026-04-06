"""
拦截所有 API 请求和响应，记录完整的请求头、请求体和响应体。
"""
import asyncio
import json
from playwright.async_api import async_playwright

CAPTURED = []

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()

        # 使用 CDP 拦截网络
        client = await context.new_cdp_session(page)
        await client.send("Network.enable")

        responses_body = {}

        def on_request(params):
            url = params.get("request", {}).get("url", "")
            method = params.get("request", {}).get("method", "")
            headers = params.get("request", {}).get("headers", {})
            post_data = params.get("request", {}).get("postData", "")

            skip = ['.js', '.css', '.png', '.jpg', '.gif', '.woff', '.ttf', '.ico', '.svg', '.wasm', '.otf', '.map',
                    'cloudflare', 'beacon', 'cdn-cgi', 'FontManifest', 'AssetManifest', 'canvaskit']
            if any(s in url for s in skip):
                return

            req_id = params.get("requestId")
            entry = {
                "request_id": req_id,
                "method": method,
                "url": url,
                "headers": dict(headers),
                "post_data": post_data
            }
            CAPTURED.append(entry)
            print(f"[REQ] {method} {url[:120]}")
            if post_data:
                print(f"  POST: {post_data[:300]}")

        async def on_response(params):
            req_id = params.get("requestId")
            url = params.get("response", {}).get("url", "")
            status = params.get("response", {}).get("status", 0)
            ct = params.get("response", {}).get("headers", {}).get("content-type", "")

            skip = ['.js', '.css', '.png', '.jpg', '.gif', '.woff', '.ttf', '.ico', '.svg', '.wasm', '.otf', '.map',
                    'cloudflare', 'beacon', 'cdn-cgi', 'FontManifest', 'AssetManifest', 'canvaskit', 'image/']
            if any(s in url for s in skip):
                return
            if 'image' in ct:
                return

            # 尝试获取响应体
            try:
                result = await client.send("Network.getResponseBody", {"requestId": req_id})
                body = result.get("body", "")
                # 找到对应的请求
                for entry in CAPTURED:
                    if entry.get("request_id") == req_id:
                        entry["response_status"] = status
                        entry["response_content_type"] = ct
                        try:
                            entry["response_body"] = json.loads(body)
                        except:
                            entry["response_body_text"] = body[:2000]
                        break

                print(f"[RES] {status} {url[:120]}")
                print(f"  Body: {body[:300]}")
            except Exception as e:
                pass

        client.on("Network.requestWillBeSent", on_request)
        client.on("Network.responseReceived", lambda params: asyncio.ensure_future(on_response(params)))

        print("=== 加载首页 ===")
        await page.goto("https://www.18jmttios01.com/", timeout=60000)
        await page.wait_for_timeout(20000)

        print(f"\n当前URL: {page.url}")

        # 保存
        output = "/Users/hongtou/av_biu/comic_scraper/api_captured.json"
        # 清理不可序列化的内容
        for entry in CAPTURED:
            if "response_body" in entry:
                body = entry["response_body"]
                if isinstance(body, (dict, list)):
                    entry["response_body_str"] = json.dumps(body, ensure_ascii=False)[:3000]

        with open(output, "w", encoding="utf-8") as f:
            json.dump(CAPTURED, f, ensure_ascii=False, indent=2, default=str)

        print(f"\n共捕获 {len(CAPTURED)} 条请求")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
