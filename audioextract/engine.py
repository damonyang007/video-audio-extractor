import subprocess
import sys
import shutil
import re
import threading
import zipfile
import urllib.request
from pathlib import Path
from typing import Optional

import audioextract as ae

CODEC_MAP = {"mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac",
             "m4a": "aac", "ogg": "libvorbis", "flac": "flac"}
BITRATE = {"low": "128k", "medium": "192k", "high": "320k"}
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
FFMPEG_ZIP = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
YTDLP_EXE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"


def exe_dir() -> Path:
    return Path(sys.argv[0]).resolve().parent if getattr(sys, "frozen", False) \
        else Path(__file__).resolve().parent.parent


def tool(name: str) -> Optional[str]:
    if name in ae._cache:
        return ae._cache[name]
    local = exe_dir() / name
    if local.is_file():
        ae._cache[name] = str(local)
        return ae._cache[name]
    p = shutil.which(name.replace(".exe", ""))
    if p:
        ae._cache[name] = p
    return p


def ensure_ffmpeg() -> bool:
    if tool("ffmpeg.exe"):
        return True
    try:
        ae.store["status"] = "下载 ffmpeg ~50MB ..."
        d = exe_dir()
        zp = d / "ffmpeg-temp.zip"
        urllib.request.urlretrieve(FFMPEG_ZIP, zp)
        ae.store["status"] = "解压 ffmpeg ..."
        with zipfile.ZipFile(zp, "r") as z:
            for m in z.namelist():
                name = Path(m).name
                if name in ("ffmpeg.exe", "ffprobe.exe"):
                    (d / name).write_bytes(z.read(m))
        zp.unlink()
        ae.store["status"] = "就绪"
        return True
    except Exception as e:
        ae.store["status"] = f"ffmpeg 下载失败: {e}"
        return False


def ensure_ytdlp() -> str:
    p = tool("yt-dlp.exe")
    if p:
        return p
    try:
        local = exe_dir() / "yt-dlp.exe"
        ae.store["status"] = "下载 yt-dlp ~10MB ..."
        urllib.request.urlretrieve(YTDLP_EXE, local)
        ae._cache["yt-dlp.exe"] = str(local)
        return str(local)
    except Exception as e:
        raise RuntimeError(f"yt-dlp download failed: {e}")


def can_pass_through(in_path: str, fmt: str) -> bool:
    mapping = {"mp3": "mp3", "aac": "aac", "m4a": "aac", "flac": "flac", "wav": "pcm"}
    try:
        r = subprocess.run(
            [tool("ffprobe.exe"), "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name",
             "-of", "default=noprint_wrappers=1:nokey=1", in_path],
            capture_output=True, text=True, timeout=10
        )
        return mapping.get(fmt) in r.stdout.strip().lower()
    except Exception:
        return False


def get_duration(in_path: str) -> Optional[float]:
    try:
        r = subprocess.run(
            [tool("ffprobe.exe"), "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", in_path],
            capture_output=True, text=True, timeout=10
        )
        return float(r.stdout.strip())
    except Exception:
        return None


def run_ffmpeg(cmd: list) -> int:
    ae._proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    duration = None
    for line in ae._proc.stderr:
        if ae._cancel:
            ae._proc.terminate()
            break
    ae._proc.wait()
    if ae._cancel:
        return -1
    return ae._proc.returncode


def extract_url(text: str) -> Optional[str]:
    urls = re.findall(r"https?://[^\s]+", text)
    return urls[0].rstrip(".,;:!?\"'") if urls else None


def start_job(fn):
    ae._cancel = False
    ae.store["pct"] = 0
    ae.store["done"] = False
    ae.store["output"] = ""
    ae.store["done_seq"] += 1
    threading.Thread(target=fn, daemon=True).start()


def batch_extract(files: list[str], fmt: str, qual: str) -> int:
    """Extract audio from multiple files. Returns count of successful extractions."""
    codec = CODEC_MAP.get(fmt, "libmp3lame")
    br = BITRATE.get(qual, "192k")
    ok = 0
    for i, f in enumerate(files):
        if ae._cancel: break
        ae.store["file_i"] = i + 1
        ae.store["pct"] = 0
        ae.store["status"] = f"\u63d0\u53d6 {i+1}/{len(files)}: {Path(f).name[:30]}..."
        out = str(Path(f).with_suffix(f".{fmt}"))
        c = [tool("ffmpeg.exe"), "-nostdin", "-threads", "0", "-i", f,
             "-vn", "-acodec", "copy" if can_pass_through(f, fmt) else codec,
             "-b:a", br, "-y", out]
        if run_ffmpeg(c) == 0 and not ae._cancel:
            ok += 1
    return ok
