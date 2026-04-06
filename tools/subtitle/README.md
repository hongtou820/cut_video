# 字幕烧录工具

将字幕文件烧录（硬编码）到视频中，生成带字幕的视频片段。

## 访问地址

http://23.224.82.34:1233/subtitle

## 使用方式

### 模式一：上传视频文件

1. 点击「上传文件」模式
2. 上传视频文件（mp4, mkv, avi 等）
3. 上传字幕文件
4. （可选）勾选「去水印」，选择水印位置
5. 输入开始时间和结束时间
6. 点击「开始烧录」

### 模式二：视频链接

1. 点击「视频链接」模式
2. 粘贴视频的直链 URL，点击「预览」可先播放检查
3. 粘贴字幕链接（支持 srt/ass/vtt 等格式的直链）
4. （可选）勾选「去水印」，选择水印位置
5. 输入开始时间和结束时间
6. 点击「开始烧录」

## 去水印

默认勾选「去水印」，可选择水印位置：

- **左上角 + 右上角**（默认）：同时去除两个角的水印（如 JAVRATE.COM + IPPA 标志）
- **仅左上角** / **仅右上角** / **左下角** / **右下角**：去除单个角落水印
- **自定义坐标**：手动输入 X、Y、宽、高（像素值）

使用 ffmpeg 的 `delogo` 滤镜，自动按视频分辨率计算覆盖区域。

## AIJAV Logo

生成的视频会自动在**右上角**叠加 AIJAV logo 水印（`AIJAV LOGO_SQUARE_BLACK.png`），大小约为视频宽度的 6%，距右上角 10 像素，圆角显示（圆角半径约 15%）。无需手动操作，每次烧录自动添加。

## 生成历史

页面底部显示历史生成记录（最近 50 条），支持：

- **播放**：在新标签页打开播放
- **下载**：下载生成的视频文件
- **删除**：删除不需要的记录

每条记录显示：
- 生成时间、文件大小
- 时间范围（如 `00:10:00 ~ 00:11:00`）
- 视频链接（截断显示）
- 字幕链接（截断显示）
- 语言（如有）

元数据自动保存到 `db.json`，无需手动操作。自动过滤损坏文件（< 10KB），仅显示正常生成的视频。

## 支持的格式

| 类型 | 支持格式 |
|------|----------|
| 视频 | mp4, mkv, avi, mov, flv, wmv 等 |
| 字幕 | `.srt`, `.ass`, `.ssa`, `.vtt`, `.sub` |

> **注意：** 不支持 `.rtf`、`.txt`、`.doc` 等非字幕格式。

## 时间格式

- 格式：`HH:MM:SS`（例如 `00:03:00`）
- 支持小数秒：`HH:MM:SS.xxx`（例如 `00:03:00.500`）

## 限制

- 文件大小上限：4GB
- 处理超时：10 分钟
- 字体：Noto Sans（支持中日韩、泰语、俄语、西班牙语、越南语、印尼语等多语言字符）

## API

### POST `/subtitle/api/burn-subtitle`

上传视频 + 字幕文件烧录。

**参数（multipart/form-data）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| video | file | 视频文件 |
| subtitle | file | 字幕文件 |
| start | string | 开始时间 HH:MM:SS |
| end | string | 结束时间 HH:MM:SS |
| delogo | string (JSON) | 可选，去水印参数，如 `{"preset":"top-left"}` 或 `{"x":0,"y":0,"w":200,"h":36}` |

### POST `/subtitle/api/burn-subtitle-url`

通过视频链接 + 字幕文件烧录。

**参数（multipart/form-data）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| videoUrl | string | 视频直链 URL |
| subtitle | file | 可选，字幕文件（与 subtitleUrl 二选一） |
| subtitleUrl | string | 可选，字幕文件直链 URL（与 subtitle 二选一） |
| start | string | 开始时间 HH:MM:SS |
| end | string | 结束时间 HH:MM:SS |
| delogo | string (JSON) | 可选，去水印参数，同上 |

### 返回

```json
{ "ok": true, "url": "/subtitle/output/output_xxx.mp4", "filename": "output_xxx.mp4" }
```

### GET `/subtitle/api/history`

获取生成历史列表（最近 50 条，自动过滤损坏文件）。

```json
{ "ok": true, "files": [{ "filename": "output_xxx.mp4", "size": 1234567, "created": 1773929080564 }] }
```

### DELETE `/subtitle/api/history/:filename`

删除指定的生成文件。

### GET `/subtitle/api/burn-subtitle/download/:filename`

下载生成的视频文件。
