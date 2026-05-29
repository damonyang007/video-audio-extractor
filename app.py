import subprocess
import os
import sys
import re
import json
import shutil
import threading
import zipfile
import urllib.request
import tkinter as tk
from tkinter import filedialog
from flask import Flask, request, jsonify, render_template, Response

try:
    import requests as req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

app = Flask(__name__)

CODEC_MAP = {"mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac",
             "m4a": "aac", "ogg": "libvorbis", "flac": "flac"}
BITRATE_MAP = {"low": "128k", "medium": "192k", "high": "320k"}
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

progress_store = {"percent": 0, "status": "\u5f85\u547d", "output": ""}


def exe_dir():
    return os.path.dirname(os.path.abspath(sys.argv[0])) if getattr(sys, "frozen", False) \
        else os.path.dirname(os.path.abspath(__file__))


def get_tool(name):
    local = os.path.join(exe_dir(), name)
    return local if os.path.isfile(local) else shutil.which(name.replace(".exe", ""))


def ensure_ffmpeg():
    if get_tool("ffmpeg.exe"):
        return True
    progress_store["status"] = "\u4e0b\u8f7d ffmpeg ~50MB ..."
    d = exe_dir()
    zp = os.path.join(d, "ffmpeg-temp.zip")
    urllib.request.urlretrieve(FFMPEG_URL, zp)
    progress_store["status"] = "\u89e3\u538b ffmpeg ..."
    with zipfile.ZipFile(zp, "r") as zf:
        for m in zf.namelist():
            name = os.path.basename(m)
            if name in ("ffmpeg.exe", "ffprobe.exe"):
                with zf.open(m) as src, open(os.path.join(d, name), "wb") as dst:
                    dst.write(src.read())
    os.remove(zp)
    progress_store["status"] = "\u5c31\u7eea"
    return True


def ensure_ytdlp():
    p = get_tool("yt-dlp.exe")
    if p:
        return p
    local = os.path.join(exe_dir(), "yt-dlp.exe")
    progress_store["status"] = "\u4e0b\u8f7d yt-dlp ~10MB ..."
    urllib.request.urlretrieve(YTDLP_URL, local)
    return local


def get_duration(path):
    try:
        r = subprocess.run([get_tool("ffprobe.exe"), "-v", "error",
                            "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", path],
                           capture_output=True, text=True)
        return float(r.stdout.strip())
    except Exception:
        return None


def run_ffmpeg(cmd):
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    duration = None
    for line in process.stderr:
        if "time=" in line:
            try:
                h, m, s = line.split("time=")[1].split()[0].split(":")
                sec = float(h) * 3600 + float(m) * 60 + float(s)
                if duration:
                    progress_store["percent"] = min(sec / duration * 100, 100)
            except Exception:
                pass
        elif duration is None and "Duration:" in line:
            try:
                h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
                duration = float(h) * 3600 + float(m) * 60 + float(s)
            except Exception:
                pass
    process.wait()
    return process.returncode


def resolve_douyin(url):
    if not HAS_REQUESTS:
        return None, None
    s = req.Session()
    s.headers.update({"User-Agent": MOBILE_UA, "Accept": "text/html,application/xhtml+xml"})
    s.get("https://www.douyin.com", timeout=10)
    r = s.get(url, timeout=15)
    html = r.text
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        title = m.group(1).strip()
    vid = re.search(r"video_id=([a-zA-Z0-9]+)", html)
    if vid:
        return f"https://aweme.snssdk.com/aweme/v1/playwm/?video_id={vid.group(1)}", title or "video"
    return None, None


def extract_url(text):
    urls = re.findall(r"https?://[^\s]+", text)
    return urls[0].rstrip(".,;:!?\"'") if urls else None


# ==================== File dialog bridge ====================

dialog_root = None
dialog_queue = []
dialog_result = []


def get_dialog_root():
    global dialog_root
    if dialog_root is None:
        dialog_root = tk.Tk()
        dialog_root.withdraw()
    return dialog_root


@app.route("/api/select-file")
def api_select_file():
    dialog_queue.append("file")
    while not dialog_result:
        import time
        time.sleep(0.05)
    return jsonify({"path": dialog_result.pop(0)})


@app.route("/api/select-dir")
def api_select_dir():
    dialog_queue.append("dir")
    while not dialog_result:
        import time
        time.sleep(0.05)
    return jsonify({"path": dialog_result.pop(0)})


@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():
    p = request.json.get("path", "")
    if p and os.path.exists(os.path.dirname(p)):
        os.startfile(os.path.dirname(p))
    return jsonify({"ok": True})


# ==================== API ====================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/progress")
def progress():
    def stream():
        import time
        while True:
            yield f"data: {json.dumps(progress_store)}\n\n"
            time.sleep(0.5)
    return Response(stream(), mimetype="text/event-stream")


@app.route("/api/extract-file", methods=["POST"])
def api_extract_file():
    data = request.json
    input_path = data.get("input", "")
    output_path = data.get("output", "")
    fmt = data.get("format", "mp3")
    quality = data.get("quality", "medium")

    if not input_path or not os.path.isfile(input_path):
        return jsonify({"ok": False, "error": "\u6587\u4ef6\u4e0d\u5b58\u5728"})

    if not ensure_ffmpeg():
        return jsonify({"ok": False, "error": "ffmpeg \u4e0b\u8f7d\u5931\u8d25"})

    if not output_path:
        output_path = f"{os.path.splitext(input_path)[0]}.{fmt}"

    codec = CODEC_MAP.get(fmt, "libmp3lame")
    br = BITRATE_MAP.get(quality, "192k")
    dur = get_duration(input_path)
    progress_store["status"] = f"\u63d0\u53d6\u4e2d ... {dur:.0f}s" if dur else "\u63d0\u53d6\u4e2d ..."
    progress_store["percent"] = 0

    def job():
        ffmpeg = get_tool("ffmpeg.exe")
        rc = run_ffmpeg([ffmpeg, "-i", input_path, "-vn", "-acodec", codec, "-b:a", br, "-y", output_path])
        progress_store["percent"] = 100
        progress_store["output"] = output_path
        progress_store["status"] = "\u2714 \u5df2\u5b8c\u6210" if rc == 0 else "\u5931\u8d25"

    threading.Thread(target=job, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/extract-url", methods=["POST"])
def api_extract_url():
    data = request.json
    raw = data.get("url", "")
    output_dir = data.get("output_dir", "")
    fmt = data.get("format", "mp3")
    quality = data.get("quality", "medium")

    url = extract_url(raw)
    if not url:
        return jsonify({"ok": False, "error": "\u672a\u68c0\u6d4b\u5230\u94fe\u63a5"})

    if not ensure_ffmpeg():
        return jsonify({"ok": False, "error": "ffmpeg \u4e0b\u8f7d\u5931\u8d25"})

    if not output_dir:
        output_dir = os.path.join(os.path.expanduser("~"), "Downloads")

    def job():
        if "douyin.com" in url or "iesdouyin.com" in url and HAS_REQUESTS:
            try:
                vurl, title = resolve_douyin(url)
                if vurl:
                    codec = CODEC_MAP.get(fmt, "libmp3lame")
                    br = BITRATE_MAP.get(quality, "192k")
                    safe = re.sub(r'[\\/:*?"<>|]', '_', title or "audio")
                    out = os.path.join(output_dir, f"{safe}.{fmt}")
                    progress_store["status"] = f"\u4e0b\u8f7d: {(title or 'video')[:30]}..."
                    ffmpeg = get_tool("ffmpeg.exe")
                    rc = run_ffmpeg([ffmpeg, "-headers",
                                     f"User-Agent: {MOBILE_UA}\r\nReferer: https://www.iesdouyin.com/",
                                     "-i", vurl, "-vn", "-acodec", codec, "-b:a", br, "-y", out])
                    if rc == 0:
                        progress_store["output"] = out
                        progress_store["status"] = "\u2714 \u5df2\u5b8c\u6210"
                        progress_store["percent"] = 100
                        return
            except Exception:
                pass

        ytdlp = ensure_ytdlp()
        br = BITRATE_MAP.get(quality, "192k").replace("k", "")
        progress_store["status"] = "yt-dlp \u4e0b\u8f7d\u4e2d ..."
        cmd = [ytdlp, "-x", "--audio-format", fmt, "--audio-quality", br,
               "-o", os.path.join(output_dir, "%(title)s.%(ext)s"), "--no-playlist", url]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace")
        for line in process.stdout:
            if "%" in line:
                try:
                    progress_store["percent"] = float(line.split("%")[0].split()[-1])
                except Exception:
                    pass
            if line.strip():
                progress_store["status"] = line.strip()[:60]
            if "[download] Destination:" in line:
                progress_store["output"] = line.split("Destination:")[-1].strip()
        process.wait()
        ok = process.returncode == 0
        progress_store["status"] = "\u2714 \u5df2\u5b8c\u6210" if ok else "\u5931\u8d25"
        progress_store["percent"] = 100

    threading.Thread(target=job, daemon=True).start()
    return jsonify({"ok": True})


def main():
    import webbrowser
    port = 17777

    threading.Thread(target=lambda: app.run(host="127.0.0.1", port=port, debug=False), daemon=True).start()

    import time
    time.sleep(1)
    webbrowser.open(f"http://127.0.0.1:{port}")

    root = get_dialog_root()
    while True:
        if dialog_queue:
            action = dialog_queue.pop(0)
            if action == "file":
                p = filedialog.askopenfilename(
                    parent=root, title="\u9009\u62e9\u89c6\u9891\u6587\u4ef6",
                    filetypes=[("\u89c6\u9891", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.rmvb *.3gp"),
                               ("\u6240\u6709", "*.*")]
                )
                dialog_result.append(p or "")
            elif action == "dir":
                p = filedialog.askdirectory(parent=root, title="\u9009\u62e9\u4fdd\u5b58\u76ee\u5f55")
                dialog_result.append(p or "")
        try:
            root.update()
        except Exception:
            break


if __name__ == "__main__":
    main()
