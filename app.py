import os
import re
import subprocess
import threading
import json
from pathlib import Path
from flask import Flask, request, jsonify, render_template, Response

import audioextract as ae
from audioextract import engine, douyin, bilibili, youtube, history, dialogs

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/progress")
def progress():
    def stream():
        import time
        while True:
            yield f"data: {json.dumps(ae.store)}\n\n"
            time.sleep(0.3)
    return Response(stream(), mimetype="text/event-stream")


@app.route("/api/video")
def api_video():
    p = request.args.get("path", "")
    if not p or not Path(p).is_file():
        return "not found", 404
    return Response(_stream_file(p), mimetype="video/mp4",
                    headers={"Accept-Ranges": "bytes",
                             "Content-Length": str(Path(p).stat().st_size)})


def _stream_file(path: str):
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            yield chunk


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify(history.load())
    history.save(request.json or {})
    return jsonify({"ok": True})


@app.route("/api/select-file")
def api_select_file():
    dialogs._dialogs.put("file")
    return jsonify({"path": dialogs._results.get()})


@app.route("/api/select-save")
def api_select_save():
    dialogs._dialogs.put("save")
    return jsonify({"path": dialogs._results.get()})


@app.route("/api/select-dir")
def api_select_dir():
    dialogs._dialogs.put("dir")
    return jsonify({"path": dialogs._results.get()})


@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    ae._cancel = True
    if ae._proc and ae._proc.poll() is None:
        ae._proc.terminate()
    ae.store.update({"status": "\u5df2\u53d6\u6d88", "pct": 0, "done": True})
    return jsonify({"ok": True})


@app.route("/api/history")
def api_history():
    return jsonify(history.load())


@app.route("/api/history/clear", methods=["POST"])
def api_history_clear():
    history.save([])
    return jsonify({"ok": True})


@app.route("/api/extract-file", methods=["POST"])
def api_extract_file():
    d = request.json
    files = d.get("files")
    if files and isinstance(files, list):
        return _batch(files, d.get("format", "mp3"), d.get("quality", "medium"))

    in_path = d.get("input", "")
    out_path = d.get("output", "")
    fmt = d.get("format", "mp3")
    qual = d.get("quality", "medium")
    t_start = d.get("start", "")
    t_end = d.get("end", "")

    if not in_path or not Path(in_path).is_file():
        return jsonify({"ok": False, "error": "\u6587\u4ef6\u4e0d\u5b58\u5728"})
    if not engine.ensure_ffmpeg():
        return jsonify({"ok": False, "error": "ffmpeg \u5931\u8d25"})

    if not out_path:
        out_path = str(Path(in_path).with_suffix(f".{fmt}"))

    codec = engine.CODEC_MAP.get(fmt, "libmp3lame")
    br = engine.BITRATE.get(qual, "192k")
    has_time = bool(t_start or t_end)
    dur = engine.get_duration(in_path)
    ae.store["status"] = f"\u63d0\u53d6\u4e2d ... {dur:.0f}s" if dur else "\u63d0\u53d6\u4e2d ..."

    def job():
        c = [engine.tool("ffmpeg.exe"), "-nostdin", "-threads", "0"]
        if t_start: c += ["-ss", t_start]
        c += ["-i", in_path]
        if t_end: c += ["-to", t_end]
        if engine.can_pass_through(in_path, fmt) and not has_time:
            c += ["-vn", "-acodec", "copy"]
        else:
            c += ["-vn", "-acodec", codec, "-b:a", br]
        c += ["-y", out_path]
        rc = engine.run_ffmpeg(c)
        ae.store.update({"pct": 100, "output": out_path,
                        "status": "\u2714 \u5df2\u5b8c\u6210" if rc == 0 else "\u5931\u8d25", "done": True})
        if rc == 0:
            history.add(in_path, "file", out_path)

    engine.start_job(job)
    return jsonify({"ok": True})


def _batch(files, fmt, qual):
    valid = [f for f in files if isinstance(f, str) and Path(f).is_file()]
    if not valid:
        return jsonify({"ok": False, "error": "\u65e0\u6709\u6548\u6587\u4ef6"})
    if not engine.ensure_ffmpeg():
        return jsonify({"ok": False, "error": "ffmpeg \u5931\u8d25"})
    ae.store["file_n"] = len(valid)
    ae.store["file_i"] = 0

    def job():
        ok = engine.batch_extract(valid, fmt, qual)
        ae.store.update({"pct": 100, "output": valid[-1] if valid else "",
                        "status": f"\u2714 {ok}/{len(valid)} \u5b8c\u6210" if ok else "\u5931\u8d25", "done": True})
        for f in valid:
            if (Path(f).with_suffix(f".{fmt}")).exists():
                history.add(f, "file", str(Path(f).with_suffix(f".{fmt}")))

    engine.start_job(job)
    return jsonify({"ok": True})


@app.route("/api/extract-url", methods=["POST"])
def api_extract_url():
    d = request.json
    raw = d.get("url", "")
    out_dir = d.get("output_dir", "") or str(Path.home() / "Downloads")
    fmt = d.get("format", "mp3")
    qual = d.get("quality", "medium")

    url = engine.extract_url(raw)
    if not url:
        return jsonify({"ok": False, "error": "\u672a\u68c0\u6d4b\u5230\u94fe\u63a5"})
    if not engine.ensure_ffmpeg():
        return jsonify({"ok": False, "error": "ffmpeg \u5931\u8d25"})

    def job():
        # Try platform-specific parsers before yt-dlp
        parsers = [
            ("douyin", douyin.resolve),
            ("bilibili", bilibili.resolve),
            ("youtube", youtube.resolve),
        ]

        for name, resolve_fn in parsers:
            is_target = (
                (name == "douyin" and ("douyin.com" in url or "iesdouyin.com" in url)) or
                (name == "bilibili" and "bilibili.com" in url) or
                (name == "youtube" and ("youtube.com" in url or "youtu.be" in url))
            )
            if is_target:
                try:
                    vurl, title = resolve_fn(url)
                    if vurl:
                        codec = engine.CODEC_MAP.get(fmt, "libmp3lame")
                        br = engine.BITRATE.get(qual, "192k")
                        safe = re.sub(r'[\\/:*?"<>|]', '_', title or "audio")
                        out = str(Path(out_dir) / f"{safe}.{fmt}")
                        ae.store["status"] = f"\u4e0b\u8f7d: {(title or 'video')[:30]}..."
                        c = [engine.tool("ffmpeg.exe"), "-nostdin", "-threads", "0", "-headers",
                             f"User-Agent: {engine.MOBILE_UA}\r\nReferer: https://www.iesdouyin.com/",
                             "-i", vurl, "-vn", "-acodec", codec, "-b:a", br, "-y", out]
                        if engine.run_ffmpeg(c) == 0:
                            ae.store.update({"output": out, "status": "\u2714 \u5df2\u5b8c\u6210", "pct": 100, "done": True})
                            history.add(url, "url", out)
                            return
                except Exception:
                    pass

        ytdlp = engine.ensure_ytdlp()
        br = engine.BITRATE.get(qual, "192k").replace("k", "")
        ae.store["status"] = "yt-dlp \u4e0b\u8f7d\u4e2d ..."
        ae._proc = subprocess.Popen(
            [ytdlp, "-x", "--audio-format", fmt, "--audio-quality", br,
                "-o", str(Path(out_dir) / "%(title)s.%(ext)s"),
                "--no-playlist" if not d.get("playlist") else "--yes-playlist", url],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace"
        )
        for line in ae._proc.stdout:
            if ae._cancel:
                ae._proc.terminate(); break
            if "%" in line:
                try:
                    ae.store["pct"] = float(line.split("%")[0].split()[-1])
                except Exception: pass
            if s := line.strip():
                ae.store["status"] = s[:60]
            if "[download] Destination:" in line:
                ae.store["output"] = line.split("Destination:")[-1].strip()
            if "has already been downloaded" in line:
                ae.store["output"] = line.split("] ")[-1].split(" has already")[0].strip()
            if "already in target format" in line:
                ae.store["output"] = line.split("] Not converting")[0].split("] ")[-1].strip()
        ae._proc.wait()
        ok = ae._proc.returncode == 0
        if ok and ae.store["output"]:
            history.add(url, "url", ae.store["output"])
        ae.store.update({"status": "\u2714 \u5df2\u5b8c\u6210" if ok else "\u5931\u8d25", "pct": 100, "done": True})

    engine.start_job(job)
    return jsonify({"ok": True})


@app.route("/api/convert-audio", methods=["POST"])
def api_convert_audio():
    d = request.json
    in_path = d.get("input", "")
    out_fmt = d.get("format", "mp3")
    if not in_path or not Path(in_path).is_file():
        return jsonify({"ok": False, "error": "\u6587\u4ef6\u4e0d\u5b58\u5728"})
    if not engine.ensure_ffmpeg():
        return jsonify({"ok": False, "error": "ffmpeg \u5931\u8d25"})
    out = d.get("output") or str(Path(in_path).with_suffix(f".{out_fmt}"))
    codec = engine.CODEC_MAP.get(out_fmt, "libmp3lame")
    br = engine.BITRATE.get(d.get("quality", "medium"), "192k")
    ae.store["status"] = "\u8f6c\u6362\u4e2d ..."

    def job():
        c = [engine.tool("ffmpeg.exe"), "-nostdin", "-threads", "0", "-i", in_path,
             "-acodec", codec, "-b:a", br, "-y", out]
        rc = engine.run_ffmpeg(c)
        ae.store.update({"pct": 100, "output": out,
                        "status": "\u2714 \u5df2\u5b8c\u6210" if rc == 0 else "\u5931\u8d25", "done": True})
        if rc == 0:
            history.add(in_path, "file", out)

    engine.start_job(job)
    return jsonify({"ok": True})


@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():
    p = request.json.get("path", "")
    if p and Path(p).parent.exists():
        os.startfile(str(Path(p).parent))
    return jsonify({"ok": True})


def main():
    import webbrowser
    port = 17777
    threading.Thread(target=lambda: app.run(host="127.0.0.1", port=port, debug=False), daemon=True).start()
    import time; time.sleep(1)
    webbrowser.open(f"http://127.0.0.1:{port}")
    dialogs.start()


if __name__ == "__main__":
    main()
