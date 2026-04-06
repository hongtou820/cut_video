"""
完整视频下载模块
从 jable.tv 获取完整视频 (HLS m3u8 → mp4)
"""
import re
import os
import subprocess
import httpx
from pathlib import Path

from config import DOWNLOAD_DIR, DOWNLOAD_TIMEOUT

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
JABLE_URL = "https://jable.tv/videos/{code}/"


def get_m3u8_url(code):
    """
    从 jable.tv 页面提取 HLS m3u8 视频地址
    返回 m3u8 URL 或 None
    """
    url = JABLE_URL.format(code=code.lower())
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": UA, "Referer": "https://jable.tv/"},
            follow_redirects=True,
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"    jable.tv 返回 {resp.status_code}: {code}")
            return None

        html = resp.text
        # 提取 hlsUrl 变量
        match = re.search(r"var\s+hlsUrl\s*=\s*['\"](.+?\.m3u8)['\"]", html)
        if match:
            return match.group(1)

        # 备用：搜索任何 m3u8 URL
        match = re.search(r'(https?://[^\s"\']+\.m3u8)', html)
        if match:
            return match.group(1)

        print(f"    jable.tv 未找到视频地址: {code}")
        return None

    except Exception as e:
        print(f"    jable.tv 请求失败 {code}: {e}")
        return None


def _add_faststart(filepath):
    """下载完成后添加 faststart（moov atom 前置），方便在线播放"""
    tmp = filepath + ".faststart.mp4"
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", filepath, "-c", "copy", "-movflags", "+faststart", tmp],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 1024 * 1024:
            os.replace(tmp, filepath)
            print(f"    faststart 优化完成")
        else:
            if os.path.exists(tmp):
                os.remove(tmp)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)


def download_full_video(code, m3u8_url=None, output_dir=None):
    """
    下载完整视频
    1. 从 jable.tv 获取 m3u8 地址
    2. 用 ffmpeg 下载并转为 mp4
    返回 (成功, 文件路径, 文件大小)
    """
    if output_dir is None:
        output_dir = os.path.join(DOWNLOAD_DIR, code)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    output_path = os.path.join(output_dir, f"{code}.mp4")

    # 如果已下载且大于 50MB，跳过
    if os.path.exists(output_path) and os.path.getsize(output_path) > 50 * 1024 * 1024:
        size = os.path.getsize(output_path)
        print(f"    视频已存在: {size // (1024*1024)}MB")
        return True, output_path, size

    # 获取 m3u8 地址
    if not m3u8_url:
        m3u8_url = get_m3u8_url(code)
    if not m3u8_url:
        return False, "", 0

    print(f"    m3u8: {m3u8_url[:80]}...")

    # 用 ffmpeg 下载 HLS 流并转为 mp4
    # 使用 frag_keyframe+empty_moov: moov atom 在文件开头写入，
    # 即使下载中断文件也能正常播放
    tmp_path = output_path + ".downloading.mp4"
    cmd = [
        "ffmpeg",
        "-y",  # 覆盖
        "-headers", f"User-Agent: {UA}\r\nReferer: https://jable.tv/\r\n",
        "-i", m3u8_url,
        "-c", "copy",  # 不重新编码，直接复制流
        "-bsf:a", "aac_adtstoasc",  # AAC 格式修复
        "-movflags", "frag_keyframe+empty_moov",  # fragmented MP4，中断也能播
        tmp_path,
    ]

    try:
        print(f"    ffmpeg 下载中...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=None,  # 不限时，等下载完成
        )

        if result.returncode != 0:
            # 检查是否有有效输出
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 50 * 1024 * 1024:
                os.rename(tmp_path, output_path)
                size = os.path.getsize(output_path)
                print(f"    ffmpeg 有警告但文件有效: {size // (1024*1024)}MB")
                return True, output_path, size

            stderr_tail = result.stderr[-500:] if result.stderr else "无错误输出"
            print(f"    ffmpeg 失败: {stderr_tail}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return False, "", 0

        # 成功
        if os.path.exists(tmp_path):
            os.rename(tmp_path, output_path)
            size = os.path.getsize(output_path)
            if size > 1024 * 1024:  # 至少 1MB
                print(f"    完整视频下载成功: {size // (1024*1024)}MB")
                # 添加 faststart（将 moov atom 移到文件头，方便在线播放）
                _add_faststart(output_path)
                return True, output_path, os.path.getsize(output_path)
            else:
                print(f"    文件太小 ({size} bytes)，下载可能失败")
                os.remove(output_path)
                return False, "", 0

        return False, "", 0

    except subprocess.TimeoutExpired:
        print(f"    ffmpeg 超时 (2小时)")
        if os.path.exists(tmp_path):
            size = os.path.getsize(tmp_path)
            if size > 50 * 1024 * 1024:
                os.rename(tmp_path, output_path)
                print(f"    超时但已下载 {size // (1024*1024)}MB，保留")
                _add_faststart(output_path)
                return True, output_path, os.path.getsize(output_path)
            os.remove(tmp_path)
        return False, "", 0

    except Exception as e:
        print(f"    下载异常: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False, "", 0


def download_video_for_entry(video_data):
    """
    为采集条目下载完整视频，更新 video_data 中的 local_files
    """
    code = video_data.get("code", "")
    if not code:
        return False

    ok, path, size = download_full_video(code)
    if ok:
        # 更新 local_files
        local_files = video_data.get("local_files", [])
        # 移除旧的 preview video 记录
        local_files = [f for f in local_files if f.get("type") != "video"]
        local_files.append({"type": "video", "path": path, "size": size})
        video_data["local_files"] = local_files
        return True

    return False


if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "FFT-038"
    print(f"测试下载完整视频: {code}")
    ok, path, size = download_full_video(code)
    if ok:
        print(f"\n成功! {path} ({size // (1024*1024)}MB)")
    else:
        print(f"\n失败")
