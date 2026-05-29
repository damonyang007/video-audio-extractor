import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import sys
import shutil
import threading
import re
import json
import zipfile
import urllib.request

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


T = {
    "bg":          "#000000",
    "card":        "#161823",
    "border":      "#2a2b3d",
    "input":       "#1e1f2c",
    "primary":     "#fe2c55",
    "primary_h":   "#e0264c",
    "secondary":   "#20d5ec",
    "text":        "#ffffff",
    "text_sub":    "#a8a9b4",
    "text_dim":    "#5a5b6a",
    "success":     "#20d5ec",
    "error":       "#fe2c55",
    "warning":     "#ffba0a",
    "gradient_1":  "#fe2c55",
    "gradient_2":  "#ff6b6b",
    "highlight":   "rgba(254,44,85,0.15)",
}


class AudioExtractorApp:
    CODEC_MAP = {"mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac",
                 "m4a": "aac", "ogg": "libvorbis", "flac": "flac", "wma": "wmav2"}
    BITRATE_MAP = {"low": "128k", "medium": "192k", "high": "320k"}
    FORMATS = ["mp3", "wav", "aac", "m4a", "ogg", "flac", "wma"]
    MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
    FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

    def __init__(self):
        self.window = tk.Tk()
        self.window.title("AudioExtract")
        self.window.geometry("520x600")
        self.window.minsize(480, 560)
        self.window.configure(bg=T["bg"])
        self.center_window()

        self._init_styles()
        self._load_config()

        self.file_input = tk.StringVar()
        self.file_output = tk.StringVar()
        self.file_format = tk.StringVar(value="mp3")
        self.file_quality = tk.StringVar(value="medium")
        self.url_input = tk.StringVar()
        self.url_output_dir = tk.StringVar(
            value=self.config.get("last_dir", os.path.join(os.path.expanduser("~"), "Downloads")))
        self.url_format = tk.StringVar(value="mp3")
        self.url_quality = tk.StringVar(value="medium")
        self.status = tk.StringVar(value="AudioExtract")
        self.progress = tk.DoubleVar(value=0)
        self.process = None
        self.cancelled = False
        self.last_output = ""
        self.ytdlp_path = None

        self.build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

    def center_window(self):
        self.window.update_idletasks()
        w, h = 520, 600
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _init_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=T["bg"], foreground=T["text"],
                    fieldbackground=T["input"], troughcolor=T["border"],
                    bordercolor=T["border"], selectbackground=T["primary"],
                    selectforeground="#ffffff", arrowcolor=T["text_sub"])
        s.configure("TNotebook", background=T["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", font=("", 11), padding=[26, 12], borderwidth=0,
                    background=T["bg"], foreground=T["text_sub"])
        s.map("TNotebook.Tab", foreground=[("selected", T["text"])])
        s.configure("TLabel", background=T["bg"], foreground=T["text_sub"], font=("", 9))
        s.configure("TEntry", font=("", 10), fieldbackground=T["input"],
                    foreground=T["text"], borderwidth=0, relief="flat", padding=10,
                    insertcolor=T["text"])
        s.map("TEntry", fieldbackground=[("readonly", T["card"])])
        s.configure("TCombobox", font=("", 10), fieldbackground=T["input"],
                    foreground=T["text"], padding=8, borderwidth=0, relief="flat", arrowsize=14)
        s.configure("TButton", font=("", 9), padding=[16, 6], borderwidth=0,
                    background=T["card"], foreground=T["text_sub"])
        s.map("TButton", background=[("active", T["border"])])
        s.configure("Small.TButton", font=("", 9), padding=[10, 4])
        s.configure("TProgressbar", troughcolor=T["border"], background=T["primary"],
                    borderwidth=0, thickness=3)

    def _config_path(self):
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                           "audioextract", "config.json")

    def _load_config(self):
        self.config = {}
        try:
            p = self._config_path()
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
        except Exception:
            pass

    def _save_config(self):
        try:
            p = self._config_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False)
        except Exception:
            pass

    # ==================== Build UI ====================

    def build_ui(self):
        # ---- Logo / Header ----
        header = tk.Frame(self.window, bg=T["bg"], height=80)
        header.pack(fill="x", padx=24, pady=(18, 0))
        header.pack_propagate(False)

        logo = tk.Canvas(header, bg=T["bg"], width=44, height=44, highlightthickness=0)
        logo.pack(side="left", padx=(0, 14))
        self._draw_logo(logo)

        texts = tk.Frame(header, bg=T["bg"])
        texts.pack(side="left")
        tk.Label(texts, text="AudioExtract", font=("", 20, "bold"),
                 bg=T["bg"], fg=T["text"]).pack(anchor="w")
        tk.Label(texts, text="\u63d0\u53d6\u89c6\u9891\u97f3\u9891\uff0c\u4e00\u952e\u641e\u5b9a",
                 font=("", 10), bg=T["bg"], fg=T["text_sub"]).pack(anchor="w", pady=(0, 0))

        # ---- Tabs ----
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(8, 0))
        self.build_local_tab()
        self.build_url_tab()

        # ---- Bottom bar ----
        self._build_bottom_bar()

    def _draw_logo(self, canvas):
        base = 10
        for i, (w, h) in enumerate([(6, 14), (6, 22), (6, 30), (6, 20)]):
            x = base + i * 8
            y = 34 - h
            canvas.create_rounded_rect = lambda *a, **kw: canvas.create_rectangle(*a, **kw)
            canvas.create_rectangle(x, y, x + 6, 34, fill=T["primary"], outline="", width=0)

    def build_local_tab(self):
        tab = tk.Frame(self.notebook, bg=T["bg"])
        self.notebook.add(tab, text="\u00a0\u672c\u5730\u6587\u4ef6\u00a0")

        body = self._card(tab, inner_pad=(18, 16))
        tk.Label(body, text="\u9009\u62e9\u89c6\u9891\u6587\u4ef6", font=("", 10),
                 bg=T["card"], fg=T["text_sub"]).pack(anchor="w")
        row = tk.Frame(body, bg=T["card"])
        row.pack(fill="x", pady=(10, 0))
        ttk.Entry(row, textvariable=self.file_input, state="readonly", width=30).pack(side="left", fill="x", expand=True)
        self._btn(row, "\u6d4f\u89c8", self.select_file, small=True).pack(side="left", padx=(8, 0))

        self._spacer(tab)

        body2 = self._card(tab, inner_pad=(18, 16))
        tk.Label(body2, text="\u8f93\u51fa\u8bbe\u7f6e", font=("", 11, "bold"),
                 bg=T["card"], fg=T["text"]).pack(anchor="w", pady=(0, 10))
        r1 = tk.Frame(body2, bg=T["card"])
        r1.pack(fill="x")
        self._chip(r1, "\u683c\u5f0f", self.file_format, ["mp3", "wav", "aac", "m4a", "ogg", "flac", "wma"])
        tk.Frame(r1, bg=T["card"], width=16).pack(side="left")
        self._chip(r1, "\u97f3\u8d28", self.file_quality, ["\u4f4e (128k)", "\u4e2d (192k)", "\u9ad8 (320k)"], default="\u4e2d (192k)")
        r2 = tk.Frame(body2, bg=T["card"])
        r2.pack(fill="x", pady=(12, 0))
        tk.Label(r2, text="\u4fdd\u5b58\u81f3", font=("", 9), bg=T["card"], fg=T["text_sub"]).pack(side="left")
        ttk.Entry(r2, textvariable=self.file_output, width=32).pack(side="left", fill="x", expand=True, padx=(10, 0))
        ttk.Button(r2, text="...", style="Small.TButton", command=self.select_file_output).pack(side="left", padx=(8, 0))

        self._action_area(tab, self._start_file_extract, show_progress=True)

    def build_url_tab(self):
        tab = tk.Frame(self.notebook, bg=T["bg"])
        self.notebook.add(tab, text="\u00a0\u5728\u7ebf\u94fe\u63a5\u00a0")

        body = self._card(tab, inner_pad=(18, 16))
        tk.Label(body, text="\u7c98\u8d34\u89c6\u9891\u94fe\u63a5", font=("", 10),
                 bg=T["card"], fg=T["text_sub"]).pack(anchor="w")
        tk.Label(body, text="\u652f\u6301\u6296\u97f3\u3001B \u7ad9\uff0c\u81ea\u52a8\u4ece\u590d\u5236\u6587\u5b57\u4e2d\u8bc6\u522b",
                 font=("", 8), bg=T["card"], fg=T["text_dim"]).pack(anchor="w", pady=(2, 0))
        ef = tk.Frame(body, bg=T["border"], highlightthickness=1)
        ef.pack(fill="x", pady=(10, 0))
        ttk.Entry(ef, textvariable=self.url_input, width=36).pack(fill="x", padx=1, pady=1)

        self._spacer(tab)

        body2 = self._card(tab, inner_pad=(18, 16))
        tk.Label(body2, text="\u8f93\u51fa\u8bbe\u7f6e", font=("", 11, "bold"),
                 bg=T["card"], fg=T["text"]).pack(anchor="w", pady=(0, 10))
        r1 = tk.Frame(body2, bg=T["card"])
        r1.pack(fill="x")
        self._chip(r1, "\u683c\u5f0f", self.url_format, ["mp3", "wav", "aac", "m4a", "ogg", "flac"])
        tk.Frame(r1, bg=T["card"], width=16).pack(side="left")
        self._chip(r1, "\u97f3\u8d28", self.url_quality, ["\u4f4e (128k)", "\u4e2d (192k)", "\u9ad8 (320k)"], default="\u4e2d (192k)")
        r2 = tk.Frame(body2, bg=T["card"])
        r2.pack(fill="x", pady=(12, 0))
        tk.Label(r2, text="\u4fdd\u5b58\u81f3", font=("", 9), bg=T["card"], fg=T["text_sub"]).pack(side="left")
        ttk.Entry(r2, textvariable=self.url_output_dir, width=28).pack(side="left", fill="x", expand=True, padx=(10, 0))
        ttk.Button(r2, text="...", style="Small.TButton", command=self.select_dir).pack(side="left", padx=(8, 0))

        self._action_area(tab, self._start_url_extract, show_progress=True)

    def _card(self, parent, inner_pad=(18, 16)):
        outer = tk.Frame(parent, bg=T["border"])
        outer.pack(fill="x")
        inner = tk.Frame(outer, bg=T["card"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        body = tk.Frame(inner, bg=T["card"])
        body.pack(fill="both", expand=True, padx=inner_pad[0], pady=inner_pad[1])
        return body

    def _spacer(self, parent, h=10):
        tk.Frame(parent, bg=T["bg"], height=h).pack(fill="x")

    def _chip(self, parent, label, var, values, default=None):
        c = tk.Frame(parent, bg=T["card"])
        c.pack(side="left")
        tk.Label(c, text=label, font=("", 9), bg=T["card"], fg=T["text_dim"]).pack(anchor="w", pady=(0, 4))
        cb = ttk.Combobox(c, textvariable=var, width=8, state="readonly", values=values)
        cb.pack(side="left")
        if default:
            cb.set(default)

    def _action_area(self, parent, cmd, show_progress=False):
        area = tk.Frame(parent, bg=T["bg"])
        area.pack(fill="x", padx=0, pady=(20, 0))

        if show_progress:
            self.progress_bar = ttk.Progressbar(area, variable=self.progress, maximum=100)
            self.progress_bar.pack(fill="x", padx=4, pady=(0, 14))

        self.result_frame = tk.Frame(area, bg=T["bg"])
        self.result_label = tk.Label(self.result_frame, text="", font=("", 10, "underline"),
                                     bg=T["bg"], fg=T["secondary"], cursor="hand2")
        self.result_label.pack()
        self.result_label.bind("<Button-1>", lambda e: self._open_folder(self.last_output))

        self.extract_btn = tk.Button(
            area, text="\u63d0\u53d6\u97f3\u9891", command=cmd,
            font=("", 14, "bold"),
            bg=T["primary"], fg="#ffffff",
            activebackground=T["primary_h"], activeforeground="#ffffff",
            relief="flat", padx=0, pady=14, cursor="hand2",
            borderwidth=0, highlightthickness=0, width=28
        )
        self.extract_btn.pack()

    def _btn(self, parent, text, cmd, small=False):
        btn = tk.Button(parent, text=text, command=cmd,
                        font=("", 10),
                        bg=T["primary"] if not small else T["card"],
                        fg="#ffffff" if not small else T["text_sub"],
                        activebackground=T["primary_h"] if not small else T["border"],
                        activeforeground="#ffffff" if not small else T["text"],
                        relief="flat", padx=14, pady=5, cursor="hand2",
                        borderwidth=0, highlightthickness=0)
        return btn

    def _build_bottom_bar(self):
        bar = tk.Frame(self.window, bg=T["bg"], height=32)
        bar.pack(fill="x", side="bottom", padx=24, pady=(0, 12))
        bar.pack_propagate(False)
        self.status_dot = tk.Canvas(bar, bg=T["bg"], width=6, height=6, highlightthickness=0)
        self.status_dot.pack(side="left", pady=13)
        self.status_dot.create_oval(0, 0, 6, 6, fill=T["text_dim"], outline="")
        tk.Label(bar, textvariable=self.status, font=("", 9),
                 bg=T["bg"], fg=T["text_sub"]).pack(side="left", padx=(8, 0))

    # ==================== Actions ====================

    def select_file(self):
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.rmvb *.3gp"),
                       ("所有文件", "*.*")]
        )
        if path:
            self.file_input.set(path)
            self.file_output.set(f"{os.path.splitext(path)[0]}.{self.file_format.get()}")

    def select_file_output(self):
        path = filedialog.asksaveasfilename(
            title="保存音频",
            initialdir=os.path.dirname(self.file_output.get() or self.file_input.get()),
            defaultextension=f".{self.file_format.get()}",
            filetypes=[("音频", f"*.{self.file_format.get()}"), ("所有文件", "*.*")]
        )
        if path:
            self.file_output.set(path)

    def select_dir(self):
        path = filedialog.askdirectory(title="选择保存目录", initialdir=self.url_output_dir.get())
        if path:
            self.url_output_dir.set(path)
            self.config["last_dir"] = path
            self._save_config()

    def _open_folder(self, filepath):
        if filepath and os.path.exists(os.path.dirname(filepath)):
            os.startfile(os.path.dirname(filepath))

    def _show_result(self, path):
        self.last_output = path
        d = os.path.dirname(path)
        short = d if len(d) < 46 else d[:21] + "..." + d[-22:]
        self.result_label.config(text=f"{short} \u2197")
        self.result_frame.pack(fill="x", padx=4, pady=(12, 0), before=self.extract_btn)

    def _set_status(self, text, color=None):
        self.status.set(text)
        c = color or T["text_dim"]
        if hasattr(self, "status_dot"):
            self.status_dot.delete("all")
            self.status_dot.create_oval(0, 0, 6, 6, fill=c, outline="")

    def _btn_working(self):
        self.extract_btn.config(
            text="\u00b7\u00b7\u00b7 \u63d0\u53d6\u4e2d",
            state="disabled", bg=T["border"], activebackground=T["border"],
            fg=T["text_sub"])

    def _btn_idle(self):
        self.extract_btn.config(
            text="\u63d0\u53d6\u97f3\u9891",
            state="normal", bg=T["primary"], activebackground=T["primary_h"],
            fg="#ffffff")

    # ==================== File ====================

    def _start_file_extract(self):
        inp = self.file_input.get()
        if not inp:
            messagebox.showwarning("\u63d0\u793a", "\u8bf7\u5148\u9009\u62e9\u89c6\u9891\u6587\u4ef6")
            return
        if not os.path.isfile(inp):
            messagebox.showerror("\u9519\u8bef", "\u6587\u4ef6\u4e0d\u5b58\u5728")
            return
        if not self._ensure_ffmpeg():
            return
        out = self.file_output.get()
        fmt = self.file_format.get()
        qual = self.file_quality.get()
        if not out:
            out = f"{os.path.splitext(inp)[0]}.{fmt}"
            self.file_output.set(out)
        self._start_job(lambda: self._extract_file(inp, out, fmt, qual))

    def _extract_file(self, inp, out, fmt, qual):
        codec = self.CODEC_MAP.get(fmt, "libmp3lame")
        br = self._bitrate(qual)
        dur = self._get_duration(inp)
        self.window.after(0, lambda: self._set_status(
            f"\u63d0\u53d6\u4e2d ... {dur:.0f}s" if dur else "\u63d0\u53d0\u53d6\u4e2d ...", T["warning"]))
        ffmpeg = self._get_tool_path("ffmpeg.exe")
        self._run_ffmpeg([ffmpeg, "-i", inp, "-vn", "-acodec", codec, "-b:a", br, "-y", out], dur)
        if not self.cancelled:
            self.window.after(0, lambda: self._show_result(out))
            self.window.after(0, lambda: self._set_status("\u2714 \u5df2\u5b8c\u6210", T["success"]))
            self.window.after(0, self._done)

    # ==================== URL ====================

    def _start_url_extract(self):
        raw = self.url_input.get().strip()
        if not raw:
            messagebox.showwarning("\u63d0\u793a", "\u8bf7\u8f93\u5165\u89c6\u9891\u94fe\u63a5")
            return
        url = self._extract_url(raw)
        if not url:
            messagebox.showwarning("\u63d0\u793a", "\u672a\u68c0\u6d4b\u5230\u94fe\u63a5")
            return
        self.url_input.set(url)
        if not self._ensure_ffmpeg():
            return
        self.config["last_dir"] = self.url_output_dir.get()
        self._save_config()
        self._start_job(lambda: self._extract_url_job(url))

    def _extract_url_job(self, url):
        if "douyin.com" in url or "iesdouyin.com" in url:
            if not HAS_REQUESTS:
                self.window.after(0, lambda: self._set_status("need requests lib", T["error"]))
                self.window.after(0, self._done)
                return
            try:
                vurl, title = self._resolve_douyin(url)
                if vurl:
                    self._douyin_download(vurl, title)
                    return
            except Exception:
                pass
        self._ytdlp_fallback(url)

    def _douyin_download(self, vurl, title):
        self.window.after(0, lambda: self._set_status(f"\u4e0b\u8f7d: {(title or 'video')[:30]}...", T["warning"]))
        fmt = self.url_format.get()
        codec = self.CODEC_MAP.get(fmt, "libmp3lame")
        br = self._bitrate(self.url_quality.get())
        safe = re.sub(r'[\\/:*?"<>|]', '_', title or "audio")
        out = os.path.join(self.url_output_dir.get(), f"{safe}.{fmt}")
        ffmpeg = self._get_tool_path("ffmpeg.exe")
        self._run_ffmpeg([ffmpeg, "-headers",
                          f"User-Agent: {self.MOBILE_UA}\r\nReferer: https://www.iesdouyin.com/",
                          "-i", vurl, "-vn", "-acodec", codec, "-b:a", br, "-y", out], None)
        if not self.cancelled:
            self.window.after(0, lambda: self._show_result(out))
            self.window.after(0, lambda: self._set_status("\u2714 \u5df2\u5b8c\u6210", T["success"]))
            self.window.after(0, self._done)

    def _resolve_douyin(self, url):
        s = requests.Session()
        s.headers.update({"User-Agent": self.MOBILE_UA,
                          "Accept": "text/html,application/xhtml+xml"})
        s.get("https://www.douyin.com", timeout=10)
        r = s.get(url, timeout=15)
        html = r.text
        title = self._extract_title(html)
        m = re.search(r"video_id=([a-zA-Z0-9]+)", html)
        if m:
            return f"https://aweme.snssdk.com/aweme/v1/playwm/?video_id={m.group(1)}", title
        for pat in [r'window\._ROUTER_DATA\s*=\s*({.*?});\s*</script>',
                     r'"url_list":\["(https?://[^"]+\.mp4[^"]*)"\]']:
            m = re.search(pat, html, re.DOTALL)
            if m:
                found = m.group(1)
                if found.startswith("http"):
                    return found, title
                try:
                    data = json.loads(found)
                    items = data.get("loaderData", {}).get("video_(id)_page", {}).get(
                        "videoInfoRes", {}).get("item_list", [])
                    if not items:
                        items = self._deep_find(data, "item_list")
                    if items and isinstance(items, list):
                        urls = items[0].get("video", {}).get("play_addr", {}).get("url_list", [])
                        if urls:
                            return urls[0], items[0].get("desc", title) or title
                except Exception:
                    pass
        return None, None

    def _extract_title(self, html):
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""

    def _deep_find(self, obj, key):
        if isinstance(obj, dict):
            if key in obj:
                return obj[key]
            for v in obj.values():
                r = self._deep_find(v, key)
                if r is not None:
                    return r
        elif isinstance(obj, list):
            for v in obj:
                r = self._deep_find(v, key)
                if r is not None:
                    return r
        return None

    def _ytdlp_fallback(self, url):
        try:
            self._ensure_ytdlp()
        except Exception:
            self.window.after(0, lambda: self._set_status("\u4e0b\u8f7d\u5931\u8d25", T["error"]))
            self.window.after(0, self._done)
            return
        fmt = self.url_format.get()
        out_dir = self.url_output_dir.get()
        br = self._bitrate(self.url_quality.get()).replace("k", "")
        cmd = [self.ytdlp_path, "-x", "--audio-format", fmt, "--audio-quality", br,
               "-o", os.path.join(out_dir, "%(title)s.%(ext)s"), "--no-playlist", url]
        self.window.after(0, lambda: self._set_status("\u4e0b\u8f7d\u4e2d ...", T["warning"]))
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace")
        for line in self.process.stdout:
            if self.cancelled:
                self.process.terminate()
                break
            if "%" in line:
                try:
                    pct = float(line.split("%")[0].split()[-1])
                    self.window.after(0, lambda p=pct: self.progress.set(p))
                except Exception:
                    pass
            if s := line.strip():
                self.window.after(0, lambda l=s[:50]: self._set_status(l))
            if "[download] Destination:" in line:
                self.window.after(0, lambda d=line.split("Destination:")[-1].strip(): self._show_result(d))
        self.process.wait()
        ok = self.process.returncode == 0
        self.window.after(0, lambda: self._set_status(
            "\u2714 \u5df2\u5b8c\u6210" if ok else "\u4e0b\u8f7d\u5931\u8d25",
            T["success"] if ok else T["error"]))
        self.window.after(0, self._done)

    # ==================== Helpers ====================

    def _start_job(self, fn):
        self.cancelled = False
        self.result_frame.pack_forget()
        self.progress.set(0)
        self._btn_working()
        self._set_status("\u51c6\u5907\u4e2d ...", T["warning"])
        threading.Thread(target=fn, daemon=True).start()

    def _done(self):
        self._btn_idle()
        self.progress.set(100)

    def _extract_url(self, text):
        urls = re.findall(r"https?://[^\s]+", text)
        return urls[0].rstrip(".,;:!?\"'") if urls else None

    def _bitrate(self, q):
        return self.BITRATE_MAP.get(q.split("(")[0].strip() if "(" in q else q, "192k")

    def _get_duration(self, path):
        try:
            r = subprocess.run([self._get_tool_path("ffprobe.exe"), "-v", "error",
                                "-show_entries", "format=duration",
                                "-of", "default=noprint_wrappers=1:nokey=1", path],
                               capture_output=True, text=True)
            return float(r.stdout.strip())
        except Exception:
            return None

    def _ensure_ffmpeg(self):
        if self._get_tool_path("ffmpeg.exe"):
            return True
        threading.Thread(target=self._download_ffmpeg, daemon=True).start()
        self._set_status("\u4e0b\u8f7d ffmpeg ... (~50MB)", T["warning"])
        return False

    def _ensure_ytdlp(self):
        p = self._get_tool_path("yt-dlp.exe")
        if p:
            self.ytdlp_path = p
        else:
            self._download_ytdlp()

    def _download_ytdlp(self):
        local = os.path.join(self._exe_dir(), "yt-dlp.exe")
        self.window.after(0, lambda: self._set_status("\u4e0b\u8f7d yt-dlp ... (~10MB)"))
        urllib.request.urlretrieve(self.YTDLP_URL, local)
        self.ytdlp_path = local

    def _download_ffmpeg(self):
        d = self._exe_dir()
        zp = os.path.join(d, "ffmpeg-temp.zip")
        self.window.after(0, lambda: self._set_status("\u4e0b\u8f7d ffmpeg ... (~50MB)"))
        urllib.request.urlretrieve(self.FFMPEG_URL, zp)
        self.window.after(0, lambda: self._set_status("\u89e3\u538b ffmpeg ..."))
        with zipfile.ZipFile(zp, "r") as zf:
            for m in zf.namelist():
                name = os.path.basename(m)
                if name in ("ffmpeg.exe", "ffprobe.exe"):
                    with zf.open(m) as src, open(os.path.join(d, name), "wb") as dst:
                        dst.write(src.read())
        os.remove(zp)
        self.window.after(0, lambda: self._set_status("AudioExtract"))

    def _exe_dir(self):
        return os.path.dirname(os.path.abspath(sys.argv[0])) if getattr(sys, "frozen", False) \
            else os.path.dirname(os.path.abspath(__file__))

    def _get_tool_path(self, name):
        local = os.path.join(self._exe_dir(), name)
        return local if os.path.isfile(local) else shutil.which(name.replace(".exe", ""))

    def _run_ffmpeg(self, cmd, dur):
        self.process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        for line in self.process.stderr:
            if self.cancelled:
                self.process.terminate()
                break
            if "time=" in line:
                try:
                    h, m, s = line.split("time=")[1].split()[0].split(":")
                    sec = float(h) * 3600 + float(m) * 60 + float(s)
                    if dur:
                        self.window.after(0, lambda p=min(sec / dur * 100, 100): self.progress.set(p))
                except Exception:
                    pass
            elif dur is None and "Duration:" in line:
                try:
                    h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
                    dur = float(h) * 3600 + float(m) * 60 + float(s)
                except Exception:
                    pass
        self.process.wait()

    def on_close(self):
        self.cancelled = True
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.window.destroy()

    def run(self):
        self.window.mainloop()


def main():
    AudioExtractorApp().run()


if __name__ == "__main__":
    main()
