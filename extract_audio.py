import argparse
import subprocess
import sys
import os
import shutil


def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        print("错误: 未找到 ffmpeg，请先安装 ffmpeg 并添加到 PATH")
        print("下载地址: https://ffmpeg.org/download.html")
        sys.exit(1)


def get_output_path(input_path, output_path, output_format):
    if output_path:
        return output_path
    base, _ = os.path.splitext(input_path)
    return f"{base}.{output_format}"


def get_duration(input_path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except Exception:
        return None


def extract_audio(input_path, output_path, output_format, quality):
    codec_map = {
        "mp3": "libmp3lame",
        "wav": "pcm_s16le",
        "aac": "aac",
        "m4a": "aac",
        "ogg": "libvorbis",
        "flac": "flac",
        "wma": "wmav2",
    }

    audio_codec = codec_map.get(output_format, "libmp3lame")

    bitrate_map = {"low": "128k", "medium": "192k", "high": "320k"}
    bitrate = bitrate_map.get(quality, "192k")

    cmd = [
        "ffmpeg", "-i", input_path,
        "-vn",
        "-acodec", audio_codec,
        "-b:a", bitrate,
        "-y",
        output_path
    ]

    duration = get_duration(input_path)

    print(f"输入: {input_path}")
    print(f"输出: {output_path}")
    print(f"格式: {output_format} | 音质: {quality} ({bitrate})")
    if duration:
        print(f"视频时长: {duration:.1f}s")
    print("-" * 40)

    process = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    for line in process.stderr:
        if "time=" in line:
            try:
                time_str = line.split("time=")[1].split()[0]
                h, m, s = time_str.split(":")
                seconds = float(h) * 3600 + float(m) * 60 + float(s)
                if duration:
                    pct = min(seconds / duration * 100, 100)
                    bar_len = 30
                    filled = int(bar_len * pct / 100)
                    bar = "█" * filled + "░" * (bar_len - filled)
                    print(f"\r进度: [{bar}] {pct:.0f}%", end="", flush=True)
            except (ValueError, IndexError):
                pass

    process.wait()
    print()

    if process.returncode == 0:
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"完成! 输出文件: {output_path} ({size_mb:.1f} MB)")
    else:
        print("提取失败，请检查输入文件是否有效")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="从视频文件中提取音频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python extract_audio.py video.mp4
  python extract_audio.py video.mp4 -f wav
  python extract_audio.py video.mp4 -o audio.mp3 -q high
  python extract_audio.py video.mkv -f aac -q low
        """
    )

    parser.add_argument("input", help="输入视频文件路径")
    parser.add_argument(
        "-o", "--output",
        help="输出音频文件路径 (默认: 与输入同名, 扩展名为输出格式)"
    )
    parser.add_argument(
        "-f", "--format",
        default="mp3",
        choices=["mp3", "wav", "aac", "m4a", "ogg", "flac", "wma"],
        help="输出音频格式 (默认: mp3)"
    )
    parser.add_argument(
        "-q", "--quality",
        default="medium",
        choices=["low", "medium", "high"],
        help="音质 (low=128k, medium=192k, high=320k, 默认: medium)"
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"错误: 文件不存在 - {args.input}")
        sys.exit(1)

    check_ffmpeg()

    output_path = get_output_path(args.input, args.output, args.format)

    extract_audio(args.input, output_path, args.format, args.quality)


if __name__ == "__main__":
    main()
