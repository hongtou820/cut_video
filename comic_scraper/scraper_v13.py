"""
漫画采集器 v13 - 漫画名文件夹 + 详情页元数据 + 底部文字裁剪
流程:
  1. 加载 → 关弹窗 → 登录 → 触发教程(牺牲进入)
  2. 最新tab → 点击漫画 → 进入阅读器
  3. 唤醒菜单 → OCR提取标题 → 点详情图标(320,25) → 进入详情页
  4. 截图详情页(封面+元数据) → 用标题命名文件夹
  5. 点"立即阅读" → 回阅读器 → 截图采集(裁剪底部灰色文字条)
  6. 保存 downloads/{漫画名}/info.json + chapter_N/page_xxx.png

修复:
  - 导航: 用 page.go_back() 代替 page.goto(BASE_URL)
  - 标题: OCR 阅读器菜单栏标题 (y=5-35, x=35-180)
  - 裁剪: 底部灰色文字条 (y≈828-844)
  - 详情页滚动: 用 mouse drag 代替 mouse.wheel (Flutter不响应wheel)
  - 展开标签: 点击 ▼ 展开按钮显示完整标签/人物/作品
"""
import asyncio
import json
import hashlib
import re
import io
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright
from PIL import Image
import pytesseract

BASE_URL = "https://www.18jmttios01.com"
OUT_DIR = Path("/Users/hongtou/av_biu/comic_scraper")
DL_DIR = OUT_DIR / "downloads"
DL_DIR.mkdir(parents=True, exist_ok=True)

PHONE = "13384214400"
PASSWORD = "123456"
STEP = 0
MAX_CHAPTERS = 91

# 底部灰色文字条裁剪高度
# device_scale_factor=2 时截图为 780x1688, 文字条从 ~1656px 开始
SCALE = 2
CROP_BOTTOM = 828 * SCALE  # 1656


async def click(page, x, y, delay=2000):
    await page.mouse.click(x, y)
    await page.wait_for_timeout(delay)


async def shot(page, name):
    global STEP; STEP += 1
    p = str(OUT_DIR / f"V{STEP:02d}_{name}.png")
    await page.screenshot(path=p)
    print(f"  📸 V{STEP:02d}_{name}")
    return p


async def close_splash(page):
    """关闭全屏闪屏广告"""
    # "关闭" 按钮在右侧, 用 touchscreen.tap (Flutter更响应触摸事件)
    for x, y in [(357, 300), (360, 305), (355, 310), (350, 295), (365, 300),
                  (357, 315), (340, 300), (360, 290)]:
        try:
            await page.touchscreen.tap(x, y)
        except Exception:
            await page.mouse.click(x, y)
        await page.wait_for_timeout(300)
    await page.wait_for_timeout(1500)


async def close_popups(page):
    # 1. 全屏闪屏广告
    await close_splash(page)
    # 2. 赌场弹窗广告 X 按钮 (底部中央)
    await click(page, 195, 570, 1500)
    # 3. "再想想" 按钮
    await click(page, 100, 495, 1500)
    # 4. 签到 - "点击空白处关闭"
    await click(page, 195, 760, 1500)
    await click(page, 195, 760, 1000)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(1500)
    # 5. 可能还有弹窗
    await close_splash(page)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(1000)


async def login(page):
    print("[登录] #/login → 密码登录...")
    await page.goto(f"{BASE_URL}/#/login", wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(8000)
    await close_splash(page)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(2000)
    await click(page, 275, 85, 2000)    # 密码登录 tab
    await click(page, 195, 145, 500)    # 手机号框
    await page.keyboard.type(PHONE, delay=80)
    await click(page, 195, 200, 500)    # 密码框
    await page.keyboard.type(PASSWORD, delay=80)
    await click(page, 195, 320, 5000)   # 登录
    ok = "login" not in page.url
    print(f"  {'✅ 成功' if ok else '❌ 失败'} → {page.url}")
    return ok


async def go_home(page):
    """回首页: 用 go_back 回到 #/home"""
    # 多次 go_back 直到回到首页
    for _ in range(5):
        if "home" in page.url:
            break
        await page.go_back()
        await page.wait_for_timeout(2000)

    if "home" not in page.url:
        # fallback: 直接导航到 #/home
        await page.goto(f"{BASE_URL}/#/home", timeout=90000)
        await page.wait_for_timeout(20000)
        await close_popups(page)


async def go_home_and_latest(page):
    """回首页 → 最新tab"""
    await go_home(page)
    await page.wait_for_timeout(2000)
    await click(page, 154, 71, 3000)  # 最新tab


def sanitize_name(name):
    """清理文件名: 去掉不合法字符"""
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', '', name)
    name = name.strip()
    return name or "unknown"


def crop_bottom_bar(screenshot_bytes):
    """裁剪底部灰色文字条"""
    img = Image.open(io.BytesIO(screenshot_bytes))
    w, h = img.size
    if h > CROP_BOTTOM:
        img = img.crop((0, 0, w, CROP_BOTTOM))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def ocr_title_from_menu(screenshot_bytes):
    """从阅读器菜单栏截图中 OCR 提取标题
    菜单栏标题位置: y=5-35, x=35-180 (390x844 viewport)
    """
    img = Image.open(io.BytesIO(screenshot_bytes))
    # 裁剪菜单栏标题区域 (坐标 × SCALE)
    title_crop = img.crop((35*SCALE, 5*SCALE, 180*SCALE, 35*SCALE))
    text = pytesseract.image_to_string(title_crop, lang="chi_sim+chi_tra").strip()
    # 清理 OCR 结果
    text = re.sub(r'[\s\n\r]+', '', text)
    return text if len(text) >= 2 else None


def ocr_region(img, box, lang="chi_sim+chi_tra+eng"):
    """OCR 指定区域"""
    crop = img.crop(box)
    text = pytesseract.image_to_string(crop, lang=lang).strip()
    return re.sub(r'\n+', ' ', text)


def ocr_image(img, lang="chi_sim+chi_tra+eng", scale=2):
    """对图片做 OCR, 先放大提高识别率"""
    if scale > 1:
        w, h = img.size
        img = img.resize((w * scale, h * scale), Image.LANCZOS)
    text = pytesseract.image_to_string(img, lang=lang)
    return text


def ocr_all_detail_pages(screenshots_bytes_list):
    """从多张详情页截图中 OCR 提取全部元数据"""
    metadata = {}

    # 对每张截图做 OCR (放大2x提高识别率), 合并文本
    all_text = ""
    for i, ss_bytes in enumerate(screenshots_bytes_list):
        img = Image.open(io.BytesIO(ss_bytes))
        text = ocr_image(img, scale=2)
        all_text += text + "\n---\n"
        print(f"  [OCR] 截图{i+1} ({len(text)} chars)")

    print(f"  [OCR] 合并文本 ({len(all_text)} chars):")
    # 打印调试 (每页前200字)
    for line in all_text[:800].split('\n'):
        if line.strip():
            print(f"    {line.strip()}")

    # === 提取描述 ===
    desc_match = re.search(r'[叙敘][述迹]\s*[:：]?\s*(.+?)(?=\n\s*四|\n\s*\d{3,}\s|作者)', all_text, re.DOTALL)
    if desc_match:
        desc = re.sub(r'\s+', '', desc_match.group(1).strip())
        if len(desc) >= 5:
            metadata["description"] = desc

    # === 提取日期 ===
    dates = re.findall(r'(\d{4}[/\-]\d{2}[/\-]\d{2})', all_text)
    seen_dates = list(dict.fromkeys(dates))
    if len(seen_dates) >= 1:
        metadata["update_date"] = seen_dates[0]
    if len(seen_dates) >= 2:
        metadata["publish_date"] = seen_dates[1]

    # === 提取 views ===
    views_match = re.search(r'[四回图]\s*(\d{3,})', all_text)
    if not views_match:
        views_match = re.search(r'(\d{3,})\s*[。.．]\s*更新', all_text)
    if views_match:
        metadata["views"] = int(views_match.group(1))

    # === 提取作者 ===
    author_match = re.search(r'作者\s*[:：]?\s*(.+?)(?:\n|人物|作品|[标標][签簽])', all_text)
    if author_match:
        author = re.sub(r'\s+', ' ', author_match.group(1).strip())
        author = re.sub(r'[^\u4e00-\u9fff\w\s/·]', '', author).strip()
        if len(author) >= 1:
            metadata["author"] = author

    # === 提取人物 ===
    char_match = re.search(r'人物\s*[:：]?\s*(.+?)(?:\n\s*作品|[标標][签簽])', all_text, re.DOTALL)
    if char_match:
        chars_text = char_match.group(1).strip()
        chars = re.findall(r'[\u4e00-\u9fff\w]{2,}', chars_text)
        skip = {'人物', '作品', '作者', '标签', '標籤'}
        chars = [c for c in chars if c not in skip]
        if chars:
            metadata["characters"] = chars

    # === 提取作品 ===
    works_match = re.search(r'作品\s*[:：]?\s*(.+?)(?:\n\s*[标標][签簽])', all_text, re.DOTALL)
    if works_match:
        works_text = works_match.group(1).strip()
        works = re.findall(r'[\u4e00-\u9fff\w]{2,}', works_text)
        skip = {'作品', '作者', '标签', '標籤', '人物'}
        works = [w for w in works if w not in skip]
        if works:
            metadata["works"] = works

    # === 提取标签 ===
    tags_match = re.search(r'[标標][签簽]\s*[:：]?\s*\n?(.*?)(?:目[录錄]|---|\Z)', all_text, re.DOTALL)
    if tags_match:
        tags_text = tags_match.group(1)
    else:
        # fallback: 寻找已知标签关键词
        tags_text = all_text

    tag_patterns = re.findall(
        r'\d+[\u4e00-\u9fff]|[\u4e00-\u9fff]{2,}|NTR|3D|daughter|not|the|cosplay|BL|GL|SM',
        tags_text
    )
    skip_words = {'目录', '目錄', '更新', '查看', '更多', '标签', '標籤',
                  '人物', '作品', '作者', '收藏', '立即', '阅读', '正在',
                  '查看更多', '正在看'}
    tags = [t for t in tag_patterns if t not in skip_words and not re.match(r'^\d+万?$', t)]
    tags = list(dict.fromkeys(tags))
    if tags and tags_match:
        metadata["tags"] = tags

    # === 提取章节总数 ===
    ch_match = re.search(r'(?:更新到|共)\s*(\d+)\s*[話话]', all_text)
    if ch_match:
        metadata["total_chapters"] = int(ch_match.group(1))

    # === 提取收藏数 ===
    fav_match = re.search(r'(\d+\.?\d*)\s*[万萬]', all_text)
    if fav_match:
        metadata["favorites"] = fav_match.group(1) + "万"

    # === 提取人气 ===
    pop_match = re.search(r'(\d+)\s*人[气氣]', all_text)
    if pop_match:
        metadata["popularity"] = int(pop_match.group(1))

    return metadata


async def touch_scroll(page, distance, x=195):
    """用鼠标拖拽模拟触摸滚动 (Flutter Web 不响应 mouse.wheel)"""
    start_y = 600
    end_y = start_y - distance
    await page.mouse.move(x, start_y)
    await page.mouse.down()
    # 分步移动模拟真实拖拽
    steps = 10
    for i in range(1, steps + 1):
        y = start_y + (end_y - start_y) * i / steps
        await page.mouse.move(x, y)
        await page.wait_for_timeout(30)
    await page.mouse.up()
    await page.wait_for_timeout(800)


async def scrape_detail(page, comic_dir):
    """在详情页多次滚动截图 + OCR 提取全部元数据"""
    detail_screenshots = []
    screenshots_data = []

    # 第一张: 顶部 (封面+标题+描述+作者+标签)
    await page.wait_for_timeout(2000)
    ss = await page.screenshot()
    screenshots_data.append(ss)
    with open(str(comic_dir / "detail_top.png"), "wb") as f:
        f.write(ss)
    detail_screenshots.append("detail_top.png")
    await shot(page, "detail_top")

    # 点击展开按钮 ▼ (标签行右侧的橙色下箭头)
    print(f"  点击展开标签...")
    await click(page, 340, 420, 2000)
    ss = await page.screenshot()
    screenshots_data.append(ss)
    with open(str(comic_dir / "detail_expanded.png"), "wb") as f:
        f.write(ss)
    detail_screenshots.append("detail_expanded.png")
    await shot(page, "detail_expanded")

    # 用触摸拖拽滚动, 截图更多内容
    scroll_steps = [
        ("detail_scroll1", 350),
        ("detail_scroll2", 350),
        ("detail_scroll3", 350),
    ]

    for name, scroll_px in scroll_steps:
        await touch_scroll(page, scroll_px)
        ss = await page.screenshot()
        screenshots_data.append(ss)
        with open(str(comic_dir / f"{name}.png"), "wb") as f:
            f.write(ss)
        detail_screenshots.append(f"{name}.png")
        await shot(page, name)

    # 第一张也保存为 cover
    with open(str(comic_dir / "cover.png"), "wb") as f:
        f.write(screenshots_data[0])

    # OCR 提取元数据
    metadata = ocr_all_detail_pages(screenshots_data)

    # 对展开后的截图(第2张)做分区域 OCR, 补充缺失字段
    if len(screenshots_data) >= 2:
        expanded_img = Image.open(io.BytesIO(screenshots_data[1]))
        # 分区 OCR (坐标 × SCALE 因为 device_scale_factor=2)
        S = SCALE

        # 作者区域 (viewport y=360-390)
        # 需要至少包含中文字符才算有效
        has_cjk_author = bool(re.search(r'[\u4e00-\u9fff]', metadata.get("author", "")))
        if not has_cjk_author:
            author_crop = expanded_img.crop((50*S, 360*S, 350*S, 390*S))
            from PIL import ImageOps
            # 二值化 (threshold=128) + 3x 放大效果最好
            gray = ImageOps.grayscale(author_crop)
            big = gray.resize((gray.width*3, gray.height*3), Image.LANCZOS)
            bw = big.point(lambda x: 0 if x < 128 else 255)
            # 尝试多个阈值, 取CJK字符最多的结果
            best_author = ""
            best_cjk_count = 0
            for thresh in [128, 140, 160]:
                bw_t = big.point(lambda x, t=thresh: 0 if x < t else 255)
                text = pytesseract.image_to_string(bw_t, lang='chi_sim+chi_tra').strip()
                # 去掉"作者"标签
                text = re.sub(r'作者\s*[:：]?\s*', '', text)
                # 去掉所有非CJK字符, 保留空格做分隔
                cleaned = re.sub(r'[^\u4e00-\u9fff\s]', '', text).strip()
                # 合并相邻CJK (去掉单个空格分隔)
                cleaned = re.sub(r'(\S)\s(\S)', r'\1\2', cleaned)
                # 再按多空格分割为名字
                parts = cleaned.split()
                # 作者名通常2-3个字, 截断过长的名字
                parts = [p[:3] if len(p) > 3 else p for p in parts]
                noise = {'有人', '人', '上', '和', '二', '一', '条', '有'}
                parts = [p for p in parts if p not in noise and len(p) >= 2]
                cjk_count = sum(len(p) for p in parts)
                if cjk_count > best_cjk_count:
                    best_cjk_count = cjk_count
                    best_author = ' '.join(parts)
                print(f"  [分区OCR] 作者 bw{thresh}: {text[:40]} → {parts}")
            if best_author:
                metadata["author"] = best_author
                print(f"  [分区OCR] 作者结果: {metadata['author']}")

        # 人物区域 (viewport y=395-450)
        if "characters" not in metadata:
            char_crop = expanded_img.crop((20*S, 395*S, 380*S, 450*S))
            char_text = ocr_image(char_crop, scale=2)
            print(f"  [分区OCR] 人物区域: {char_text.strip()}")
            char_text = re.sub(r'[人A][物te][：:]?\s*', '', char_text)
            chars = re.findall(r'[\u4e00-\u9fff\w]{2,}', char_text)
            skip = {'人物', '作品', '作者', '标签'}
            chars = [c for c in chars if c not in skip]
            if chars:
                metadata["characters"] = chars

        # 收藏区域 (viewport y=770-810)
        if "favorites" not in metadata:
            fav_crop = expanded_img.crop((20*S, 770*S, 130*S, 810*S))
            fav_text = ocr_image(fav_crop, scale=2)
            print(f"  [分区OCR] 收藏区域: {fav_text.strip()}")
            fav_m = re.search(r'(\d+\.?\d*)\s*([万萬])?', fav_text)
            if fav_m:
                if fav_m.group(2):
                    metadata["favorites"] = fav_m.group(1) + "万"
                else:
                    metadata["favorites"] = fav_m.group(1)

    if metadata:
        print(f"  元数据: {json.dumps(metadata, ensure_ascii=False)}")

    return detail_screenshots, metadata


async def scrape_pages(page, save_dir, max_scroll=80):
    """截图采集单章漫画页面, 裁剪底部灰色文字条"""
    save_dir.mkdir(parents=True, exist_ok=True)
    page_num = 0
    prev_hash = ""
    stale = 0

    # 先滚动一下确保菜单消失
    await page.mouse.wheel(0, 100)
    await page.wait_for_timeout(1500)

    for _ in range(max_scroll):
        ss = await page.screenshot()
        cropped = crop_bottom_bar(ss)
        h = hashlib.md5(cropped).hexdigest()
        if h != prev_hash:
            prev_hash = h
            page_num += 1
            with open(str(save_dir / f"page_{page_num:03d}.png"), "wb") as f:
                f.write(cropped)
            stale = 0
        else:
            stale += 1
            if stale >= 5:
                break
        await page.mouse.wheel(0, 700)
        await page.wait_for_timeout(500)
    return page_num


async def goto_next_chapter(page):
    """通过进度面板跳到后一话"""
    # 点中央唤醒菜单
    await click(page, 195, 420, 1500)
    # 点"进度"按钮 (底部右侧)
    await click(page, 340, 815, 1500)
    # 点"后一话" (右下角)
    await click(page, 365, 830, 3000)
    # 关闭进度面板 — 点中央
    await click(page, 195, 400, 2000)
    # 滚动一下确保菜单消失 + 内容加载
    await page.mouse.wheel(0, 100)
    await page.wait_for_timeout(2000)


async def main():
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"{'='*50}")
    print(f"漫画采集 v13 — {now}")
    print(f"{'='*50}")

    all_comics = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844}, has_touch=True,
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15")
        page = await ctx.new_page()

        # === 1. 加载 ===
        print("\n[1] 加载首页...")
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(35000)
        await close_popups(page)

        # === 2. 登录 ===
        print("\n[2] 登录...")
        await login(page)

        # === 3. 触发教程弹窗 (牺牲一次进入) ===
        print("\n[3] 触发教程弹窗...")
        # 直接导航到 #/home (避免 BASE_URL 跳转到 #/lad 广告页)
        await page.goto(f"{BASE_URL}/#/home", timeout=90000)
        await page.wait_for_timeout(20000)
        await close_popups(page)
        await shot(page, "home_after_login")
        await click(page, 154, 71, 3000)  # 最新tab
        await shot(page, "latest_before_sacrifice")
        await click(page, 70, 220, 8000)  # 随便进一本
        print(f"  触发URL: {page.url}")

        # === 4. 采集漫画 ===
        print("\n[4] 开始采集...")
        await go_home_and_latest(page)
        await shot(page, "latest_page")

        # 最新tab 3列: x=70/195/320, 第一排 y≈220, 第二排 y≈370
        comics_to_scrape = [
            {"pos": (70, 220), "idx": 1},
            # {"pos": (195, 220), "idx": 2},  # 测试时先只采1本
        ]

        for ci, comic_cfg in enumerate(comics_to_scrape):
            cx, cy = comic_cfg["pos"]
            print(f"\n{'='*40}")
            print(f"[漫画{ci+1}] 点击 ({cx}, {cy})...")

            if ci > 0:
                await go_home_and_latest(page)

            # 点击漫画进入阅读器
            await click(page, cx, cy, 10000)
            url = page.url
            print(f"  阅读器URL: {url}")

            if "read" not in url:
                print(f"  ⚠ 未进入阅读器, 跳过")
                continue

            # --- 菜单默认已显示, 直接截图 OCR 标题 ---
            # 进入阅读器后菜单默认显示, 不需要额外点击
            # 如果菜单没显示, 点中央唤醒
            menu_ss = await page.screenshot()
            title = ocr_title_from_menu(menu_ss)
            if not title:
                # 菜单可能没显示, 点中央唤醒
                print(f"  唤醒菜单...")
                await click(page, 195, 420, 2000)
                menu_ss = await page.screenshot()
                title = ocr_title_from_menu(menu_ss)
            await shot(page, f"c{ci+1}_menu")
            print(f"  OCR标题: {title}")

            # --- 进详情页 (点右上角详情图标) ---
            print(f"  进详情页...")
            await click(page, 320, 25, 5000)  # 详情图标
            detail_url = page.url
            print(f"  详情URL: {detail_url}")

            # 确定文件夹名
            if title:
                folder_name = sanitize_name(title)
            else:
                folder_name = f"comic_{today}_{ci+1}"
                print(f"  ⚠ OCR失败, 使用 {folder_name}")

            # 检查重名
            comic_dir = DL_DIR / folder_name
            if comic_dir.exists():
                folder_name = f"{folder_name}_{today}"
                comic_dir = DL_DIR / folder_name
            comic_dir.mkdir(parents=True, exist_ok=True)

            comic_info = {
                "comic_id": folder_name,
                "title": title,
                "url": detail_url,
                "reader_url": url,
                "scraped_at": now,
                "source": "禁漫天堂",
                "source_url": BASE_URL,
                "cover_screenshot": "cover.png",
                "detail_screenshots": [],
                "chapters": [],
            }

            if "detail" in detail_url:
                # 在详情页截图 + OCR元数据
                detail_screenshots, metadata = await scrape_detail(page, comic_dir)
                comic_info["detail_screenshots"] = detail_screenshots
                comic_info.update(metadata)

                # 滚回顶部再点"立即阅读"
                print(f"  点击 '立即阅读'...")
                await touch_scroll(page, -1500)
                await page.wait_for_timeout(1000)
                await click(page, 270, 780, 8000)  # "立即阅读"按钮
                read_url = page.url
                print(f"  阅读器URL: {read_url}")
            else:
                print(f"  ⚠ 未进入详情页, 直接在阅读器采集")
                # 保存菜单截图作为封面
                with open(str(comic_dir / "cover.png"), "wb") as f:
                    f.write(menu_ss)
                read_url = url

            if "read" in read_url:
                await shot(page, f"c{ci+1}_reader")
                for ch_num in range(1, MAX_CHAPTERS + 1):
                    print(f"  --- 第{ch_num}章 ---")
                    chapter_dir = comic_dir / f"chapter_{ch_num}"
                    n = await scrape_pages(page, chapter_dir)
                    comic_info["chapters"].append({
                        "chapter_num": ch_num, "pages": n,
                        "path": f"chapter_{ch_num}/"
                    })
                    print(f"  ✓ 第{ch_num}章 {n}页")

                    # 保存中间进度
                    with open(str(comic_dir / "info.json"), "w", encoding="utf-8") as f:
                        json.dump(comic_info, f, ensure_ascii=False, indent=2)

                    if ch_num < MAX_CHAPTERS:
                        print(f"  跳转后一话...")
                        await goto_next_chapter(page)
            else:
                await shot(page, f"c{ci+1}_no_reader")
                print(f"  ⚠ 未进入阅读器: {read_url}")

            # 保存 info.json
            with open(str(comic_dir / "info.json"), "w", encoding="utf-8") as f:
                json.dump(comic_info, f, ensure_ascii=False, indent=2)
            print(f"  → {comic_dir}/info.json")
            all_comics.append(comic_info)

        # === 最终验证 ===
        print(f"\n[验证] 我的页面...")
        await go_home(page)
        await click(page, 357, 815, 3000)  # 底部"我的"
        await shot(page, "final_mine")

        await browser.close()

    # 保存总记录
    record = {
        "version": "v13",
        "scrape_time": now,
        "account": PHONE,
        "total_comics": len(all_comics),
        "comics": all_comics,
    }
    record_path = str(OUT_DIR / "scrape_record_v13.json")
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"完成! → scrape_record_v13.json")
    for c in all_comics:
        cdir = DL_DIR / c["comic_id"]
        total_pages = sum(ch["pages"] for ch in c["chapters"])
        ch_dirs = [d for d in cdir.iterdir() if d.is_dir()] if cdir.exists() else []
        total_sz = sum(f.stat().st_size for d in ch_dirs for f in d.glob("*.png"))
        print(f"  📗 {c['title'] or c['comic_id']}: {total_pages}页 | {total_sz//1024}KB | {len(c['chapters'])}章")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
