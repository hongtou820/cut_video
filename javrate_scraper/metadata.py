"""
元数据补全模块
通过 avbase.net 获取视频完整信息：标题、番号、演员、片商、分类、上映时间、剧照
"""
import re
import json
import httpx

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
AVBASE_URL = "https://www.avbase.net/works/{code}"


def fetch_metadata(code):
    """
    从 avbase.net 获取视频完整元数据
    返回 dict 或 None
    """
    url = AVBASE_URL.format(code=code)
    try:
        resp = httpx.get(url, headers={"User-Agent": UA}, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            print(f"    avbase 返回 {resp.status_code}: {code}")
            return None

        html = resp.text
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html,
        )
        if not match:
            print(f"    avbase 无 __NEXT_DATA__: {code}")
            return None

        data = json.loads(match.group(1))
        props = data.get("props", {}).get("pageProps", {})
        work = props.get("work")
        if not work:
            print(f"    avbase 无 work 数据: {code}")
            return None

        return _parse_work(work, props)

    except Exception as e:
        print(f"    avbase 请求失败 {code}: {e}")
        return None


def _parse_work(work, props):
    """解析 avbase work 数据"""
    result = {
        "code": work.get("work_id", ""),
        "title": work.get("title", ""),
        "title_ja": work.get("title", ""),
    }

    # 分类/标签
    genres = work.get("genres", [])
    result["tags"] = [g["name"] for g in genres if g.get("name")]

    # 演员 - 从 casts 和 comments 中提取
    casts = work.get("casts", [])
    actresses = [c.get("name", "") for c in casts if c.get("name")]

    # 评论中有时有演员名
    comments = props.get("comments", [])
    for comment in comments:
        body = comment.get("body", "").strip()
        # 评论中的短文本可能是演员名
        if body and len(body) < 30 and not any(c in body for c in ["http", "www", "。", "、", "！"]):
            if body not in actresses:
                actresses.append(body)

    result["actresses"] = actresses

    # 从 products 中提取详细信息 (优先 fanza，其次 mgstage)
    products = work.get("products", [])
    fanza = next((p for p in products if p.get("source") == "fanza"), None)
    mgstage = next((p for p in products if p.get("source") == "mgstage"), None)
    product = fanza or mgstage or (products[0] if products else None)

    if product:
        # 片商
        maker = product.get("maker", {})
        result["studio"] = maker.get("name", "") if maker else ""

        # 厂牌
        label = product.get("label", {})
        result["label"] = label.get("name", "") if label else ""

        # 系列
        series = product.get("series", {})
        result["series"] = series.get("name", "") if series else ""

        # 发行日期
        date_str = product.get("date", "")
        date_match = re.search(r'(\w{3})\s+(\w{3})\s+(\d{1,2})\s+(\d{4})', date_str)
        if date_match:
            from datetime import datetime
            try:
                dt = datetime.strptime(
                    f"{date_match.group(4)} {date_match.group(2)} {date_match.group(3)}",
                    "%Y %b %d"
                )
                result["date"] = dt.strftime("%Y-%m-%d")
            except ValueError:
                result["date"] = ""
        else:
            result["date"] = ""

        # 导演
        iteminfo = product.get("iteminfo", {})
        result["director"] = iteminfo.get("director", "")
        result["duration"] = iteminfo.get("volume", "").replace("分", "").strip()
        result["description"] = iteminfo.get("description", "")

        # 封面图 (高清)
        result["cover_url"] = product.get("image_url", "")
        result["cover_thumb_url"] = product.get("thumbnail_url", "")

        # 剧照
        sample_images = product.get("sample_image_urls", [])
        result["screenshots"] = [img.get("l", img.get("s", "")) for img in sample_images]
        result["screenshots_small"] = [img.get("s", "") for img in sample_images]

        # 商品URL (可能包含预览视频线索)
        result["product_url"] = product.get("url", "")
        result["product_id"] = product.get("product_id", "")

    else:
        result["studio"] = ""
        result["label"] = ""
        result["series"] = ""
        result["date"] = ""
        result["director"] = ""
        result["duration"] = ""
        result["description"] = ""
        result["cover_url"] = ""
        result["cover_thumb_url"] = ""
        result["screenshots"] = []
        result["screenshots_small"] = []

    # 预览视频 - 从 DMM 的 product_id 推导，尝试多种 URL 格式
    if result.get("product_id"):
        pid = result["product_id"]
        # DMM 预览视频有多种路径格式，都存下来，下载时逐个试
        result["preview_video_candidates"] = [
            f"https://cc3001.dmm.co.jp/litevideo/freepv/{pid[0]}/{pid[:3]}/{pid}/{pid}_mhb_w.mp4",
            f"https://cc3001.dmm.co.jp/litevideo/freepv/{pid[0]}/{pid[:3]}/{pid}/{pid}_dmb_w.mp4",
            f"https://cc3001.dmm.co.jp/litevideo/freepv/{pid[0]}/{pid[:3]}/{pid}/{pid}_sm_w.mp4",
        ]
        result["preview_video"] = result["preview_video_candidates"][0]

    return result


def enrich_video(video_data):
    """
    用 avbase 数据补全视频信息
    保留 javrate 的 detail_url 和原始封面
    """
    code = video_data.get("code", "")
    if not code:
        return video_data

    meta = fetch_metadata(code)
    if not meta:
        return video_data

    # 合并数据，avbase 数据优先（更完整）
    enriched = {**video_data}

    # 标题：用 avbase 的日文标题
    if meta.get("title"):
        enriched["title"] = meta["title"]
        enriched["title_ja"] = meta.get("title_ja", "")

    # 演员
    if meta.get("actresses"):
        enriched["actresses"] = meta["actresses"]
        enriched["actress"] = ", ".join(meta["actresses"])

    # 分类标签
    if meta.get("tags"):
        enriched["tags"] = meta["tags"]

    # 片商
    if meta.get("studio"):
        enriched["studio"] = meta["studio"]
    if meta.get("label"):
        enriched["label"] = meta["label"]
    if meta.get("series"):
        enriched["series"] = meta["series"]

    # 日期
    if meta.get("date"):
        enriched["date"] = meta["date"]

    # 导演、时长、描述
    if meta.get("director"):
        enriched["director"] = meta["director"]
    if meta.get("duration"):
        enriched["duration"] = meta["duration"]
    if meta.get("description"):
        enriched["description"] = meta["description"]

    # 高清封面 (DMM)
    if meta.get("cover_url"):
        enriched["cover_hd_url"] = meta["cover_url"]
    if meta.get("cover_thumb_url"):
        enriched["cover_thumb_url"] = meta["cover_thumb_url"]

    # 剧照
    if meta.get("screenshots"):
        enriched["screenshots"] = meta["screenshots"]
        enriched["screenshots_small"] = meta.get("screenshots_small", [])

    # 预览视频
    if meta.get("preview_video"):
        enriched["preview_video"] = meta["preview_video"]

    # product 信息
    if meta.get("product_id"):
        enriched["product_id"] = meta["product_id"]

    return enriched


if __name__ == "__main__":
    # 测试
    result = fetch_metadata("FFT-038")
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
