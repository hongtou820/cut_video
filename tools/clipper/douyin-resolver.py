#!/usr/bin/env python3
"""Resolve Douyin video info using Playwright browser automation.
Usage: python3 douyin-resolver.py <douyin_url>
Output: JSON with title, duration, videoUrl, thumbnail
"""
import sys, json, re, time
from urllib.parse import unquote

def resolve(url):
    from playwright.sync_api import sync_playwright

    result = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            locale='zh-CN',
            extra_http_headers={
                'Accept-Language': 'zh-CN,zh;q=0.9',
            }
        )
        page = ctx.new_page()

        video_urls = []
        api_data = None

        def on_response(response):
            nonlocal api_data
            u = response.url
            try:
                # Intercept the detail API call
                if '/aweme/v1/' in u and 'detail' in u:
                    data = response.json()
                    detail = data.get('aweme_detail')
                    if detail:
                        api_data = detail
                # Intercept video stream URLs
                ct = response.headers.get('content-type', '')
                if 'video' in ct or '.mp4' in u:
                    video_urls.append(u)
            except:
                pass

        page.on('response', on_response)

        # First resolve share URL to get video ID
        vid_match = re.search(r'video/(\d+)', url)
        if not vid_match:
            # Follow redirect to get video ID
            try:
                page.goto(url, wait_until='commit', timeout=30000)
                time.sleep(2)
                current = page.url
                vid_match = re.search(r'video/(\d+)', current)
            except:
                current = page.url
                vid_match = re.search(r'video/(\d+)', current)

        if vid_match:
            vid = vid_match.group(1)
            target = f'https://www.douyin.com/video/{vid}'
        else:
            target = url

        try:
            page.goto(target, wait_until='commit', timeout=60000)
        except:
            pass

        # Wait for API response or video element
        for i in range(60):
            time.sleep(1)
            if api_data:
                break
            # Also try to find video in page
            if i == 15 or i == 30 or i == 45:
                try:
                    html = page.content()
                    m = re.search(r'<script id="RENDER_DATA"[^>]*>([^<]+)</script>', html)
                    if m:
                        data = json.loads(unquote(m.group(1)))
                        raw = json.dumps(data)
                        # Extract from SSR data
                        desc_m = re.findall(r'"desc":"([^"]{1,200})"', raw)
                        dur_m = re.findall(r'"duration":(\d+)', raw)
                        play_m = re.findall(r'"playApi":"([^"]+)"', raw)
                        cover_m = re.findall(r'"coverUrlList":\["([^"]+)"', raw)
                        if play_m:
                            result = {
                                'title': desc_m[0] if desc_m else '',
                                'duration': int(dur_m[0]) / 1000 if dur_m else 0,
                                'videoUrl': play_m[0].replace('\\u002F', '/'),
                                'thumbnail': cover_m[0].replace('\\u002F', '/') if cover_m else '',
                            }
                            break
                except:
                    pass

        if api_data and not result:
            v = api_data.get('video', {})
            play_list = v.get('play_addr', {}).get('url_list', [])
            cover_list = v.get('cover', {}).get('url_list', [])
            result = {
                'title': api_data.get('desc', ''),
                'duration': (v.get('duration', 0) or 0) / 1000,
                'videoUrl': play_list[0] if play_list else '',
                'thumbnail': cover_list[0] if cover_list else '',
            }

        if not result and video_urls:
            result = {
                'title': '',
                'duration': 0,
                'videoUrl': video_urls[0],
                'thumbnail': '',
            }

        browser.close()

    return result

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'error': '请提供抖音链接'}))
        sys.exit(1)

    url = sys.argv[1]
    try:
        data = resolve(url)
        if data and data.get('videoUrl'):
            print(json.dumps({**data, 'ok': True}, ensure_ascii=False))
        else:
            print(json.dumps({'error': '无法解析视频，可能受地域限制', 'ok': False}))
            sys.exit(1)
    except Exception as e:
        print(json.dumps({'error': str(e), 'ok': False}))
        sys.exit(1)
