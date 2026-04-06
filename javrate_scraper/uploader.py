"""
FTP 上传 + API 入库模块
"""
import os
import json
import ftplib
import hashlib
from pathlib import Path
from datetime import datetime

import httpx

from config import (
    FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_BASE_DIR,
    API_IMPORT, VIDEO_TYPE, VIDEO_SOURCE, VIDEO_RULE, VIDEO_USERNAME,
    DATA_DIR, DOWNLOAD_DIR, STATE_FILE,
)


def compute_md5(filepath):
    """计算文件 MD5"""
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


class FTPUploader:
    """FTP 文件上传器"""

    def __init__(self):
        self.ftp = None

    def connect(self):
        """连接 FTP"""
        print(f"连接 FTP: {FTP_HOST}:{FTP_PORT}")
        self.ftp = ftplib.FTP()
        self.ftp.connect(FTP_HOST, FTP_PORT, timeout=30)
        self.ftp.login(FTP_USER, FTP_PASS)
        self.ftp.encoding = "utf-8"
        print(f"  FTP 登录成功: {self.ftp.getwelcome()}")

    def ensure_dir(self, remote_dir):
        """递归创建远程目录"""
        parts = remote_dir.strip("/").split("/")
        current = ""
        for part in parts:
            current += "/" + part
            try:
                self.ftp.cwd(current)
            except ftplib.error_perm:
                try:
                    self.ftp.mkd(current)
                except ftplib.error_perm:
                    pass

    def upload_file(self, local_path, remote_path):
        """上传单个文件"""
        remote_dir = os.path.dirname(remote_path)
        self.ensure_dir(remote_dir)

        file_size = os.path.getsize(local_path)
        uploaded = [0]

        def callback(data):
            uploaded[0] += len(data)

        try:
            with open(local_path, "rb") as f:
                self.ftp.storbinary(f"STOR {remote_path}", f, callback=callback)
            print(f"    FTP: {remote_path} ({file_size // 1024}KB)")
            return True
        except Exception as e:
            print(f"    FTP 上传失败 {remote_path}: {e}")
            return False

    def upload_video_files(self, code, local_dir):
        """上传视频相关的所有文件"""
        remote_base = f"{FTP_BASE_DIR}/{code}"
        uploaded_files = []

        if not os.path.exists(local_dir):
            return uploaded_files

        for root, dirs, files in os.walk(local_dir):
            for fname in files:
                local_path = os.path.join(root, fname)
                rel_path = os.path.relpath(local_path, local_dir)
                remote_path = f"{remote_base}/{rel_path}"

                if self.upload_file(local_path, remote_path):
                    uploaded_files.append({
                        "local": local_path,
                        "remote": remote_path,
                        "size": os.path.getsize(local_path),
                    })

        return uploaded_files

    def close(self):
        """关闭连接"""
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                self.ftp.close()


def call_import_api(video_detail, uploaded_files):
    """
    调用入库 API
    """
    code = video_detail["code"]

    # 找到封面和视频的远程路径
    cover_remote = ""
    video_remote = ""
    video_md5 = ""

    for f in uploaded_files:
        remote = f["remote"]
        if "cover" in os.path.basename(remote):
            cover_remote = remote
        elif remote.endswith((".mp4", ".m3u8", ".webm")):
            video_remote = remote
            video_md5 = compute_md5(f["local"])

    # 如果没有视频文件，用封面代替（有些只有预览图）
    if not video_remote and cover_remote:
        video_remote = cover_remote
        for f in uploaded_files:
            if f["remote"] == cover_remote:
                video_md5 = compute_md5(f["local"])

    if not video_remote:
        print(f"  {code}: 没有可入库的文件")
        return None

    # 构建标题和描述
    title = video_detail.get("title", code)
    actresses = video_detail.get("actresses", [])
    tags = video_detail.get("tags", [])
    description = video_detail.get("description", "")
    if not description:
        parts = [code]
        if actresses:
            parts.append(" ".join(actresses))
        if video_detail.get("studio"):
            parts.append(video_detail["studio"])
        description = " | ".join(parts)

    # API 请求体
    payload = {
        "title": title,
        "description": description,
        "video": video_remote,
        "md5": video_md5,
        "image": cover_remote,
        "tag": tags if tags else [],
        "type": VIDEO_TYPE,
        "source": VIDEO_SOURCE,
        "code": code,
        "author": " ".join(actresses) if actresses else "",
        "username": VIDEO_USERNAME,
        "rule": VIDEO_RULE,
    }

    # 可选字段
    if video_detail.get("studio"):
        payload["remark"] = f"片商: {video_detail['studio']}"

    print(f"  入库 API: {code}")
    print(f"    title: {title[:50]}")
    print(f"    video: {video_remote}")
    print(f"    tags: {tags[:5]}")

    try:
        resp = httpx.post(API_IMPORT, json=payload, timeout=30)
        result = resp.json()
        print(f"    响应: {result}")
        if result.get("code") == 1:
            return result.get("data", {}).get("video_id")
        else:
            print(f"    入库失败: {result.get('message', '未知错误')}")
            return None
    except Exception as e:
        print(f"    API 调用失败: {e}")
        return None


def process_video(ftp_uploader, code):
    """处理单个视频：上传 + 入库"""
    data_path = os.path.join(DATA_DIR, f"{code}.json")
    local_dir = os.path.join(DOWNLOAD_DIR, code)

    if not os.path.exists(data_path):
        print(f"  {code}: 数据文件不存在")
        return False

    with open(data_path, "r", encoding="utf-8") as f:
        video_detail = json.load(f)

    # 上传到 FTP
    uploaded = ftp_uploader.upload_video_files(code, local_dir)
    if not uploaded:
        print(f"  {code}: 没有文件可上传")
        return False

    # 调用入库 API
    video_id = call_import_api(video_detail, uploaded)

    # 更新数据文件
    video_detail["uploaded"] = True
    video_detail["upload_time"] = datetime.now().isoformat()
    video_detail["video_id"] = video_id
    video_detail["ftp_files"] = uploaded

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(video_detail, f, ensure_ascii=False, indent=2)

    return video_id is not None


def run_upload():
    """批量上传所有未上传的视频"""
    if not os.path.exists(DATA_DIR):
        print("没有数据可上传")
        return

    # 找出所有未上传的视频
    pending = []
    for fname in os.listdir(DATA_DIR):
        if not fname.endswith(".json"):
            continue
        data_path = os.path.join(DATA_DIR, fname)
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("uploaded"):
            pending.append(data["code"])

    if not pending:
        print("所有视频已上传")
        return

    print(f"待上传: {len(pending)} 个视频")
    print(f"{'='*60}")

    ftp = FTPUploader()
    ftp.connect()

    success = 0
    for code in pending:
        print(f"\n处理: {code}")
        if process_video(ftp, code):
            success += 1

    ftp.close()

    print(f"\n{'='*60}")
    print(f"上传完成: 成功 {success}/{len(pending)}")


if __name__ == "__main__":
    run_upload()
