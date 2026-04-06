#!/bin/bash
# 将字幕烧录到视频中（可指定起止时间截取片段）
# 用法: ./burn_subtitle.sh <视频文件> <字幕文件> <开始时间> <结束时间>
# 时间格式: HH:MM:SS 或 HH:MM:SS.mmm
# 例子: ./burn_subtitle.sh input.mp4 sub.srt 00:01:30 00:05:00

if [ $# -lt 4 ]; then
    echo "用法: $0 <视频文件> <字幕文件> <开始时间> <结束时间>"
    echo "时间格式: HH:MM:SS 或 HH:MM:SS.mmm"
    echo "例子: $0 input.mp4 sub.srt 00:01:30 00:05:00"
    exit 1
fi

VIDEO="$1"
SUBTITLE="$2"
START="$3"
END="$4"

# 检查文件是否存在
if [ ! -f "$VIDEO" ]; then
    echo "错误: 视频文件不存在: $VIDEO"
    exit 1
fi

if [ ! -f "$SUBTITLE" ]; then
    echo "错误: 字幕文件不存在: $SUBTITLE"
    exit 1
fi

# 生成输出文件名
BASENAME=$(basename "$VIDEO")
NAME="${BASENAME%.*}"
EXT="${BASENAME##*.}"
OUTPUT="${NAME}_subtitled.${EXT}"

# 获取字幕文件的绝对路径并转义特殊字符（ffmpeg subtitles filter 需要）
SUB_PATH=$(cd "$(dirname "$SUBTITLE")" && pwd)/$(basename "$SUBTITLE")
# ffmpeg subtitles filter 需要转义 : 和 \
SUB_ESCAPED=$(echo "$SUB_PATH" | sed "s/'/\\\\'/g" | sed 's/:/\\:/g')

echo "视频: $VIDEO"
echo "字幕: $SUBTITLE"
echo "时间: $START -> $END"
echo "输出: $OUTPUT"
echo ""

ffmpeg -y -i "$VIDEO" \
    -ss "$START" -to "$END" \
    -vf "subtitles='${SUB_ESCAPED}'" \
    -c:a copy \
    "$OUTPUT"

if [ $? -eq 0 ]; then
    echo ""
    echo "完成! 输出文件: $OUTPUT"
else
    echo ""
    echo "处理失败"
    exit 1
fi
