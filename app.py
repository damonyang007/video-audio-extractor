from __future__ import annotations
import subprocess
import os
import sys
import re
import json
import shutil
import threading
import zipfile
import urllib.request
import time as _time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from typing import Optional, Tuple
from flask import Flask, request, jsonify, render_template, Response

try:
    import requests as req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

app = Flask(__name__)

# ---- Config ----
CODEC_MAP = {"mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac",
             "m4a": "aac", "ogg": "libvorbis", "flac": "flac"}
BITRATE = {"low": "128k", "medium": "192k", "high": "320k"}
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
FFMPEG_ZIP = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
YTDLP_EXE  = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

# ---- Global state ----
store = {"pct": 0, "status": "\u5f85\u547d", "output": "", "done": False,
         "file_i": 0, "file_n": 0}
_cache = {}
_cancel = False
_proc = None
_root = None
_dialogs: list[str] = []
_results: list[str] = []


def exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parent


def tool(name: str) -> Optional[str]:
    if name in _cache:
        return _cache[name]
    local = exe_dir() / name
    if local.is_file():
        _cache[name] = str(local)
        return _cache[name]
    p = shutil.which(name.replace(".exe", ""))
    if p:
        _cache[name] = p
    return p


def ensure_ffmpeg() -> bool:
    if tool("ffmpeg.exe"):
        return True
    store["status"] = "下载 ffmpeg ~50MB ..."
    d = exe_dir()
    zp = d / "ffmpeg-temp.zip"
    urllib.request.urlretrieve(FFMPEG_ZIP, zp)
    store["status"] = "解压 ffmpeg ..."
    import zipfile as zf
    with zf.ZipFile(zp, "r") as z:
        for m in z.namelist():
            name = Path(m).name
            if name in ("ffmpeg.exe", "ffprobe.exe"):
                (d / name).write_bytes(z.read(m))
    zp.unlink()
    store["status"] = "就绪"
    return True


def ensure_ytdlp() -> str:
    p = tool("yt-dlp.exe")
    if p:
        return p
    local = exe_dir() / "yt-dlp.exe"
    store["status"] = "下载 yt-dlp ~10MB ..."
    urllib.request.urlretrieve(YTDLP_EXE, local)
    _cache["yt-dlp.exe"] = str(local)
    return str(local)


def can_pass_through(in_path: str, fmt: str) -> bool:
    """Check if input audio codec matches target format for lossless copy."""
    mapping = {"mp3": "mp3", "aac": "aac", "m4a": "aac", "flac": "flac", "wav": "pcm"}
    try:
        r = subprocess.run(
            [tool("ffprobe.exe"), "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", in_path],
            capture_output=True, text=True, timeout=10
        )
        codec = r.stdout.strip()
        return codec and mapping.get(fmt) in codec.lower()
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


def run_ffmpeg(cmd: list[str]) -> int:
    global _proc
    _proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    duration = None
    for line in _proc.stderr:
        if _cancel:
            _proc.terminate()
            break
        if "time=" in line:
            try:
                h, m, s = line.split("time=")[1].split()[0].split(":")
                sec = float(h) * 3600 + float(m) * 60 + float(s)
                if duration and sec > 0:
                    store["pct"] = min(sec / duration * 100, 100)
            except Exception:
                pass
        elif duration is None and "Duration:" in line:
            try:
                h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
                duration = float(h) * 3600 + float(m) * 60 + float(s)
            except Exception:
                pass
    _proc.wait()
    return _proc.returncode


def resolve_douyin(url: str) -> Tuple[Optional[str], str]:
    if not HAS_REQUESTS:
        return None, ""
    s = req.Session()
    s.headers.update({"User-Agent": MOBILE_UA, "Accept": "text/html,application/xhtml+xml"})
    try:
        s.get("https://www.douyin.com", timeout=10)
        r = s.get(url, timeout=15)
    except Exception:
        return None, ""
    html = r.text
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        title = m.group(1).strip()
    vid = re.search(r"video_id=([a-zA-Z0-9]+)", html)
    if vid:
        return f"https://aweme.snssdk.com/aweme/v1/playwm/?video_id={vid.group(1)}", title or "video"
    return None, title


def extract_url(text: str) -> Optional[str]:
    urls = re.findall(r"https?://[^\s]+", text)
    return urls[0].rstrip(".,;:!?\"'") if urls else None


# ---- History ----

def _hist_path() -> Path:
    p = Path(os.environ.get("APPDATA", str(Path.home()))) / "audioextract" / "history.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_history() -> list:
    try:
        if _hist_path().is_file():
            return json.loads(_hist_path().read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save_history(entries: list):
    try:
        _hist_path().write_text(json.dumps(entries[-50:], ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def add_history(source: str, kind: str, output: str):
    h = load_history()
    h.insert(0, {
        "source": str(Path(source).name) if kind == "file" else source[:60],
        "kind": kind,
        "output": output,
        "time": datetime.now().strftime("%m-%d %H:%M")
    })
    save_history(h)


# ---- Routes ----

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/progress")
def progress():
    def stream():
        import time
        while True:
            yield f"data: {json.dumps(store)}\n\n"
            time.sleep(0.3)
    return Response(stream(), mimetype="text/event-stream")


@app.route("/api/video")
def api_video():
    p = request.args.get("path", "")
    if not p or not Path(p).is_file():
        return "not found", 404
    return Response(
        _stream_file(p),
        mimetype="video/mp4",
        headers={"Accept-Ranges": "bytes", "Content-Length": str(Path(p).stat().st_size)}
    )


def _stream_file(path: str):
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            yield chunk


@app.route("/api/select-file")
def api_select_file():
    _dialogs.append("file")
    while not _results:
        import time; time.sleep(0.05)
    return jsonify({"path": _results.pop(0)})


@app.route("/api/select-dir")
def api_select_dir():
    _dialogs.append("dir")
    while not _results:
        import time; time.sleep(0.05)
    return jsonify({"path": _results.pop(0)})


@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    global _cancel
    _cancel = True
    if _proc and _proc.poll() is None:
        _proc.terminate()
    store["status"] = "已取消"
    store["pct"] = 0
    store["done"] = True
    return jsonify({"ok": True})


@app.route("/api/history")
def api_history():
    return jsonify(load_history())


@app.route("/api/history/clear", methods=["POST"])
def api_history_clear():
    save_history([])
    return jsonify({"ok": True})


def _start_job(fn):
    global _cancel
    _cancel = False
    store["pct"] = 0
    store["done"] = False
    store["output"] = ""
    threading.Thread(target=fn, daemon=True).start()


@app.route("/api/extract-file", methods=["POST"])
def api_extract_file():
    d = request.json
    files = d.get("files")  # batch mode
    in_path = d.get("input", "")
    out_path = d.get("output", "")
    fmt = d.get("format", "mp3")
    qual = d.get("quality", "medium")
    t_start = d.get("start", "")
    t_end = d.get("end", "")

    # Batch mode
    if files and isinstance(files, list):
        return _api_extract_batch(files, fmt, qual)

    if not in_path or not Path(in_path).is_file():
        return jsonify({"ok": False, "error": "文件不存在"})
    if not ensure_ffmpeg():
        return jsonify({"ok": False, "error": "ffmpeg 失败"})
    if not out_path:
        out_path = str(Path(in_path).with_suffix(f".{fmt}"))

    codec = CODEC_MAP.get(fmt, "libmp3lame")
    br = BITRATE.get(qual, "192k")
    has_time = bool(t_start or t_end)
    dur = get_duration(in_path)
    store["status"] = f"提取中 ... {dur:.0f}s" if dur else "提取中 ..."

    def job():
        ffmpeg = tool("ffmpeg.exe")
        cmd = [ffmpeg, "-nostdin", "-threads", "0"]
        if t_start:
            cmd += ["-ss", t_start]
        cmd += ["-i", in_path]
        if t_end:
            cmd += ["-to", t_end]
        if can_pass_through(in_path, fmt) and not has_time:
            cmd += ["-vn", "-acodec", "copy"]
        else:
            cmd += ["-vn", "-acodec", codec, "-b:a", br]
        cmd += ["-y", out_path]

        rc = run_ffmpeg(cmd)
        store["pct"] = 100
        store["output"] = out_path
        store["status"] = "\u2714 已完成" if rc == 0 else "失败"
        store["done"] = True
        if rc == 0:
            add_history(in_path, "file", out_path)

    _start_job(job)
    return jsonify({"ok": True})


def _api_extract_batch(files: list, fmt: str, qual: str):
    valid = [f for f in files if isinstance(f, str) and Path(f).is_file()]
    if not valid:
        return jsonify({"ok": False, "error": "无有效文件"})
    if not ensure_ffmpeg():
        return jsonify({"ok": False, "error": "ffmpeg 失败"})

    store["file_n"] = len(valid)
    store["file_i"] = 0

    codec = CODEC_MAP.get(fmt, "libmp3lame")
    br = BITRATE.get(qual, "192k")

    def job():
        ok_count = 0
        for i, f in enumerate(valid):
            if _cancel:
                break
            store["file_i"] = i + 1
            store["pct"] = 0
            store["status"] = f"提取 {i+1}/{len(valid)}: {Path(f).name[:30]}..."
            ffmpeg = tool("ffmpeg.exe")
            out = str(Path(f).with_suffix(f".{fmt}"))
            if can_pass_through(f, fmt):
                cmd = [ffmpeg, "-nostdin", "-threads", "0", "-i", f, "-vn", "-acodec", "copy", "-y", out]
            else:
                cmd = [ffmpeg, "-nostdin", "-threads", "0", "-i", f, "-vn", "-acodec", codec, "-b:a", br, "-y", out]
            rc = run_ffmpeg(cmd)
            if rc == 0 and not _cancel:
                ok_count += 1
                add_history(f, "file", out)
        store["pct"] = 100
        store["output"] = valid[-1] if valid else ""
        store["status"] = f"\u2714 {ok_count}/{len(valid)} 完成" if ok_count else "失败"
        store["done"] = True

    _start_job(job)
    return jsonify({"ok": True})


@app.route("/api/extract-url", methods=["POST"])
def api_extract_url():
    d = request.json
    raw = d.get("url", "")
    out_dir = d.get("output_dir", "")
    fmt = d.get("format", "mp3")
    qual = d.get("quality", "medium")

    url = extract_url(raw)
    if not url:
        return jsonify({"ok": False, "error": "未检测到链接"})
    if not ensure_ffmpeg():
        return jsonify({"ok": False, "error": "ffmpeg 失败"})
    if not out_dir:
        out_dir = str(Path.home() / "Downloads")

    def job():
        global _cancel

        if "douyin.com" in url or "iesdouyin.com" in url and HAS_REQUESTS:
            try:
                vurl, title = resolve_douyin(url)
                if vurl:
                    codec = CODEC_MAP.get(fmt, "libmp3lame")
                    br = BITRATE.get(qual, "192k")
                    safe = re.sub(r'[\\/:*?"<>|]', '_', title or "audio")
                    out = str(Path(out_dir) / f"{safe}.{fmt}")
                    store["status"] = f"下载: {(title or 'video')[:30]}..."
                    ffmpeg = tool("ffmpeg.exe")
                    rc = run_ffmpeg([ffmpeg, "-nostdin", "-threads", "0", "-headers",
                                     f"User-Agent: {MOBILE_UA}\r\nReferer: https://www.iesdouyin.com/",
                                     "-i", vurl, "-vn", "-acodec", codec, "-b:a", br, "-y", out])
                    if rc == 0:
                        store["output"] = out
                        store["status"] = "\u2714 已完成"
                        store["pct"] = 100
                        store["done"] = True
                        add_history(url, "url", out)
                        return
            except Exception:
                pass

        ytdlp = ensure_ytdlp()
        br = BITRATE.get(qual, "192k").replace("k", "")
        store["status"] = "yt-dlp 下载中 ..."
        global _proc
        _proc = subprocess.Popen(
            [ytdlp, "-x", "--audio-format", fmt, "--audio-quality", br,
             "-o", str(Path(out_dir) / "%(title)s.%(ext)s"), "--no-playlist", url],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace"
        )
        for line in _proc.stdout:
            if _cancel:
                _proc.terminate()
                break
            if "%" in line:
                try:
                    store["pct"] = float(line.split("%")[0].split()[-1])
                except Exception:
                    pass
            if s := line.strip():
                store["status"] = s[:60]
            if "[download] Destination:" in line:
                store["output"] = line.split("Destination:")[-1].strip()
        _proc.wait()
        ok = _proc.returncode == 0
        if ok and store["output"]:
            add_history(url, "url", store["output"])
        store["status"] = "\u2714 已完成" if ok else "失败"
        store["pct"] = 100
        store["done"] = True

    _start_job(job)
    return jsonify({"ok": True})


@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():
    p = request.json.get("path", "")
    if p and Path(p).parent.exists():
        os.startfile(str(Path(p).parent))
    return jsonify({"ok": True})


# ---- Main ----

def main():
    import webbrowser
    port = 17777
    threading.Thread(target=lambda: app.run(host="127.0.0.1", port=port, debug=False), daemon=True).start()
    import time; time.sleep(1)
    webbrowser.open(f"http://127.0.0.1:{port}")

    global _root
    _root = tk.Tk()
    _root.withdraw()
    while True:
        if _dialogs:
            act = _dialogs.pop(0)
            if act == "file":
                p = filedialog.askopenfilename(
                    parent=_root, title="选择视频文件",
                    filetypes=[("视频", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.rmvb *.3gp"),
                               ("所有", "*.*")]
                )
                _results.append(p or "")
            elif act == "dir":
                p = filedialog.askdirectory(parent=_root, title="选择保存目录")
                _results.append(p or "")
        try:
            _root.update()
        except Exception:
            break


if __name__ == "__main__":
    main()
