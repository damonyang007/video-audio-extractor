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
    ae.store["status"] = "\u4e0b\u8f7d ffmpeg ~50MB ..."
    d = exe_dir()
    zp = d / "ffmpeg-temp.zip"
    urllib.request.urlretrieve(FFMPEG_ZIP, zp)
    ae.store["status"] = "\u89e3\u538b ffmpeg ..."
    with zipfile.ZipFile(zp, "r") as z:
        for m in z.namelist():
            name = Path(m).name
            if name in ("ffmpeg.exe", "ffprobe.exe"):
                (d / name).write_bytes(z.read(m))
    zp.unlink()
    ae.store["status"] = "\u5c31\u7eea"
    return True


def ensure_ytdlp() -> str:
    p = tool("yt-dlp.exe")
    if p:
        return p
    local = exe_dir() / "yt-dlp.exe"
    ae.store["status"] = "\u4e0b\u8f7d yt-dlp ~10MB ..."
    urllib.request.urlretrieve(YTDLP_EXE, local)
    ae._cache["yt-dlp.exe"] = str(local)
    return str(local)


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
        if "time=" in line:
            try:
                h, m, s = line.split("time=")[1].split()[0].split(":")
                sec = float(h) * 3600 + float(m) * 60 + float(s)
                if duration and sec > 0:
                    ae.store["pct"] = min(sec / duration * 100, 100)
            except Exception:
                pass
        elif duration is None and "Duration:" in line:
            try:
                h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
                duration = float(h) * 3600 + float(m) * 60 + float(s)
            except Exception:
                pass
    ae._proc.wait()
    return ae._proc.returncode


def extract_url(text: str) -> Optional[str]:
    urls = re.findall(r"https?://[^\s]+", text)
    return urls[0].rstrip(".,;:!?\"'") if urls else None


def start_job(fn):
    ae._cancel = False
    ae.store["pct"] = 0
    ae.store["done"] = False
    ae.store["output"] = ""
    threading.Thread(target=fn, daemon=True).start()
