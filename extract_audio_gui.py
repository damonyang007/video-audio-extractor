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


THEME = {
    "surface":    "#1e1e2e",
    "card":       "#252536",
    "card_hover": "#2a2a3d",
    "border":     "#313148",
    "primary":    "#7c3aed",
    "primary_h":  "#6d28d9",
    "primary_fg": "#a78bfa",
    "text":       "#cdd6f4",
    "text_sub":   "#9399b2",
    "text_dim":   "#585b70",
    "success":    "#a6e3a1",
    "error":      "#f38ba8",
    "warning":    "#f9e2af",
    "input_bg":   "#1e1e2e",
    "input_fg":   "#cdd6f4",
    "header":     "#181825",
    "scrollbar":  "#45475a",
}


def make_icon():
    from tkinter import Canvas
    root = tk.Tk()
    root.withdraw()
    c = Canvas(root, width=48, height=48, bg=THEME["primary"], highlightthickness=0)
    bars = [(10, 20, 16, 28), (18, 12, 24, 36), (26, 6, 32, 42), (34, 15, 40, 33)]
    for x1, y1, x2, y2 in bars:
        c.create_rectangle(x1, y1, x2, y2, fill="#ffffff", outline="", width=0)
    c.create_oval(8, 38, 44, 48, fill="#c4b5fd", outline="")
    c.postscript(file=os.path.join(os.environ["TEMP"], "_icon.ps"), colormode="color",
                 x=0, y=0, width=48, height=48)
    root.destroy()
    try:
        from PIL import Image
        img = Image.open(os.path.join(os.environ["TEMP"], "_icon.ps"))
        ico = os.path.join(os.environ["TEMP"], "_icon.ico")
        img.save(ico, format="ICO", sizes=[(48, 48)])
        return ico
    except ImportError:
        return None


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
        self.window.geometry("620x560")
        self.window.minsize(560, 480)
        self.window.configure(bg=THEME["surface"])
        self._set_icon()

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
        self.status = tk.StringVar()
        self.progress = tk.DoubleVar(value=0)
        self.process = None
        self.cancelled = False
        self.last_output = ""
        self.ytdlp_path = None
        self._idle_status()

        self.build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

    def _set_icon(self):
        self.window.tk.call("wm", "iconphoto", self.window._w, tk.PhotoImage(width=1, height=1))
        try:
            ico = make_icon()
            if ico and os.path.exists(ico):
                self.window.iconbitmap(ico)
        except Exception:
            pass

    def _init_styles(self):
        s = ttk.Style()
        s.theme_use("clam")

        s.configure(".", background=THEME["surface"], foreground=THEME["text"],
                    fieldbackground=THEME["input_bg"], troughcolor=THEME["border"],
                    bordercolor=THEME["border"], selectbackground=THEME["primary"],
                    selectforeground="#ffffff", arrowcolor=THEME["text_sub"])

        s.configure("TNotebook", background=THEME["surface"], borderwidth=0, tabmargins=[0, 0, 0, 0])
        s.configure("TNotebook.Tab", font=("Segoe UI", 10), padding=[22, 10],
                    background=THEME["surface"], foreground=THEME["text_sub"], borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", THEME["primary"])],
              foreground=[("selected", "#ffffff")])

        s.configure("Card.TLabelframe", background=THEME["card"], borderwidth=0, relief="flat")
        s.configure("Card.TLabelframe.Label", font=("Segoe UI", 10, "bold"),
                    background=THEME["card"], foreground=THEME["text"], padding=(0, 2))

        s.configure("TLabel", background=THEME["surface"], foreground=THEME["text_sub"],
                    font=("Segoe UI", 9))
        s.configure("Title.TLabel", font=("Segoe UI", 18, "bold"),
                    background=THEME["surface"], foreground=THEME["text"])
        s.configure("Sub.TLabel", font=("Segoe UI", 10),
                    background=THEME["surface"], foreground=THEME["text_sub"])
        s.configure("Hint.TLabel", font=("Segoe UI", 8), foreground=THEME["text_dim"])

        s.configure("TEntry", font=("Segoe UI", 10), fieldbackground=THEME["input_bg"],
                    foreground=THEME["input_fg"], borderwidth=0, relief="flat", padding=8,
                    insertcolor=THEME["text"])
        s.map("TEntry", fieldbackground=[("readonly", THEME["card"])])

        s.configure("TCombobox", font=("Segoe UI", 10), fieldbackground=THEME["input_bg"],
                    foreground=THEME["text"], padding=6, borderwidth=0, relief="flat",
                    arrowsize=14)
        s.map("TCombobox", fieldbackground=[("readonly", THEME["input_bg"])])

        s.configure("TButton", font=("Segoe UI", 9), padding=[14, 6], borderwidth=0,
                    background=THEME["card"], foreground=THEME["text"])
        s.map("TButton", background=[("active", THEME["border"]), ("disabled", THEME["card"])],
              foreground=[("disabled", THEME["text_dim"])])

        s.configure("Small.TButton", font=("Segoe UI", 9), padding=[8, 4])
        s.map("Small.TButton", background=[("active", THEME["border"])])

        s.configure("TProgressbar", troughcolor=THEME["border"], background=THEME["primary"],
                    borderwidth=0, thickness=5)

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

    def _idle_status(self):
        self.status.set(" \u25cf  就绪")
        if hasattr(self, "status_dot"):
            self.status_dot.config(bg=THEME["text_dim"])

    # ==================== UI ====================

    def build_ui(self):
        # Window chrome area
        chrome = tk.Frame(self.window, bg=THEME["header"], height=44)
        chrome.pack(fill="x")
        chrome.pack_propagate(False)
        tk.Label(chrome, text="\u266a  AudioExtract", font=("Segoe UI", 12, "bold"),
                 bg=THEME["header"], fg=THEME["primary_fg"]).pack(side="left", padx=20, pady=10)
        tk.Label(chrome, text="v1.1", font=("Segoe UI", 9),
                 bg=THEME["header"], fg=THEME["text_dim"]).pack(side="right", padx=20, pady=10)

        # Tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(12, 0))
        self.build_local_tab()
        self.build_url_tab()

        # Status bar
        bar = tk.Frame(self.window, bg=THEME["header"])
        bar.pack(fill="x", side="bottom")
        self.status_dot = tk.Frame(bar, bg=THEME["text_dim"], width=6, height=6)
        self.status_dot.pack(side="left", padx=(16, 6), pady=8)
        self.status_dot.pack_propagate(False)
        tk.Label(bar, textvariable=self.status, font=("Segoe UI", 9),
                 bg=THEME["header"], fg=THEME["text_sub"]).pack(side="left")

    def build_local_tab(self):
        tab = tk.Frame(self.notebook, bg=THEME["surface"])
        self.notebook.add(tab, text="  本地文件  ")

        c1 = self._section(tab, "视频文件", "选择要提取音频的本地视频")
        row = tk.Frame(c1, bg=THEME["card"])
        row.pack(fill="x", padx=18, pady=(12, 16))
        ttk.Entry(row, textvariable=self.file_input, state="readonly",
                  width=38).pack(side="left", fill="x", expand=True)
        btn = tk.Button(row, text="浏览", command=self.select_file,
                        font=("Segoe UI", 10), bg=THEME["primary"], fg="#ffffff",
                        activebackground=THEME["primary_h"], activeforeground="#ffffff",
                        relief="flat", padx=14, pady=4, cursor="hand2",
                        borderwidth=0, highlightthickness=0)
        btn.pack(side="left", padx=(8, 0))
        self._bind_hover(btn, THEME["primary"], THEME["primary_h"])

        c2 = self._section(tab, "输出设置")
        self._output_row(c2, self.file_format, self.file_quality, self.file_output, self.select_file_output)
        self._action_bar(tab, self._start_file_extract)

    def build_url_tab(self):
        tab = tk.Frame(self.notebook, bg=THEME["surface"])
        self.notebook.add(tab, text="  在线链接  ")

        c1 = self._section(tab, "视频链接", "支持抖音、B 站，自动从复制文本中识别")
        entry_frame = tk.Frame(c1, bg=THEME["border"])
        entry_frame.pack(fill="x", padx=18, pady=(12, 16))
        ttk.Entry(entry_frame, textvariable=self.url_input, width=44).pack(fill="x", padx=1, pady=1)

        c2 = self._section(tab, "输出设置")
        self._output_row(c2, self.url_format, self.url_quality)
        dir_row = tk.Frame(c2, bg=THEME["card"])
        dir_row.pack(fill="x", padx=18, pady=(0, 14))
        ttk.Label(dir_row, text="保存至", background=THEME["card"]).pack(side="left")
        ttk.Entry(dir_row, textvariable=self.url_output_dir).pack(side="left", fill="x", expand=True, padx=(10, 0))
        ttk.Button(dir_row, text="...", style="Small.TButton", command=self.select_dir).pack(side="left", padx=(8, 0))

        self._action_bar(tab, self._start_url_extract)

    def _section(self, parent, title, subtitle=None):
        frame = ttk.LabelFrame(parent, text=f"  {title}  ", style="Card.TLabelframe")
        frame.pack(fill="x", padx=0, pady=(0, 10))
        if subtitle:
            tk.Label(frame, text=subtitle, font=("Segoe UI", 9),
                     bg=THEME["card"], fg=THEME["text_sub"]).pack(anchor="w", padx=18, pady=(0, 0))
        return frame

    def _output_row(self, parent, fmt_var, q_var, out_var=None, out_cmd=None):
        row = tk.Frame(parent, bg=THEME["card"])
        row.pack(fill="x", padx=18, pady=(14, 10))
        ttk.Label(row, text="格式", background=THEME["card"]).pack(side="left")
        ttk.Combobox(row, textvariable=fmt_var, width=5, state="readonly",
                     values=self.FORMATS).pack(side="left", padx=(6, 20))
        ttk.Label(row, text="音质", background=THEME["card"]).pack(side="left")
        q = ttk.Combobox(row, textvariable=q_var, width=10, state="readonly",
                         values=["\u4f4e (128k)", "\u4e2d (192k)", "\u9ad8 (320k)"])
        q.pack(side="left", padx=(6, 0))
        q.set("\u4e2d (192k)")

        if out_var is not None:
            row2 = tk.Frame(parent, bg=THEME["card"])
            row2.pack(fill="x", padx=18, pady=(0, 14))
            ttk.Label(row2, text="保存至", background=THEME["card"]).pack(side="left")
            ttk.Entry(row2, textvariable=out_var).pack(side="left", fill="x", expand=True, padx=(10, 0))
            ttk.Button(row2, text="...", style="Small.TButton", command=out_cmd).pack(side="left", padx=(8, 0))

    def _action_bar(self, parent, extract_cmd):
        bar = tk.Frame(parent, bg=THEME["surface"])
        bar.pack(fill="x", padx=0, pady=(6, 0))

        # Progress
        self.progress_bar = ttk.Progressbar(bar, variable=self.progress, maximum=100)
        self.progress_bar.pack(fill="x", padx=14, pady=(0, 12))

        # Result link (hidden initially)
        self.result_frame = tk.Frame(bar, bg=THEME["surface"])
        self.result_label = tk.Label(self.result_frame, text="", font=("Segoe UI", 9, "underline"),
                                     bg=THEME["surface"], fg=THEME["primary_fg"], cursor="hand2")
        self.result_label.pack(anchor="center")
        self.result_label.bind("<Button-1>", lambda e: self._open_folder(self.last_output))

        # Extract button
        self.extract_btn = tk.Button(
            bar, text="\u25b6  提取音频", command=extract_cmd,
            font=("Segoe UI", 12, "bold"),
            bg=THEME["primary"], fg="#ffffff",
            activebackground=THEME["primary_h"], activeforeground="#ffffff",
            relief="flat", padx=32, pady=10, cursor="hand2",
            borderwidth=0, highlightthickness=0
        )
        self.extract_btn.pack()
        self._bind_hover(self.extract_btn, THEME["primary"], THEME["primary_h"])

    def _bind_hover(self, widget, normal, hover):
        widget.bind("<Enter>", lambda e: widget.config(bg=hover))
        widget.bind("<Leave>", lambda e: widget.config(bg=normal))

    # ==================== Actions ====================

    def select_file(self):
        initial = os.path.dirname(self.file_input.get()) if self.file_input.get() else None
        path = filedialog.askopenfilename(
            title="选择视频文件", initialdir=initial,
            filetypes=[("视频文件", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.rmvb *.3gp"),
                       ("所有文件", "*.*")]
        )
        if path:
            self.file_input.set(path)
            base, _ = os.path.splitext(path)
            self.file_output.set(f"{base}.{self.file_format.get()}")

    def select_file_output(self):
        initial = self.file_output.get() or os.path.dirname(self.file_input.get())
        path = filedialog.asksaveasfilename(
            title="保存音频文件", initialdir=os.path.dirname(initial),
            defaultextension=f".{self.file_format.get()}",
            filetypes=[("音频文件", f"*.{self.file_format.get()}"), ("所有文件", "*.*")]
        )
        if path:
            self.file_output.set(path)

    def select_dir(self):
        initial = self.url_output_dir.get()
        path = filedialog.askdirectory(title="选择保存目录", initialdir=initial)
        if path:
            self.url_output_dir.set(path)
            self.config["last_dir"] = path
            self._save_config()

    def _open_folder(self, filepath):
        if filepath and os.path.exists(os.path.dirname(filepath)):
            os.startfile(os.path.dirname(filepath))

    def _show_result(self, path):
        self.last_output = path
        short = os.path.dirname(path)
        if len(short) > 50:
            short = short[:23] + "..." + short[-24:]
        self.result_label.config(text=f"\u2197 \u6253\u5f00\u6587\u4ef6\u5939: {short}")
        self.result_frame.pack(fill="x", padx=14, pady=(0, 8), before=self.extract_btn)

    def _set_status(self, text, color=None):
        self.status.set(f" \u25cf  {text}")
        if hasattr(self, "status_dot"):
            self.status_dot.config(bg=color or THEME["text_dim"])

    def _btn_working(self):
        self.extract_btn.config(text="\u25cf\u25cf\u25cf  提取中 ...", state="disabled",
                                bg=THEME["border"], activebackground=THEME["border"])

    def _btn_idle(self):
        self.extract_btn.config(text="\u25b6  提取音频", state="normal",
                                bg=THEME["primary"], activebackground=THEME["primary_h"])

    # ==================== File extraction ====================

    def _start_file_extract(self):
        input_path = self.file_input.get()
        if not input_path:
            messagebox.showwarning("提示", "请先选择视频文件")
            return
        if not os.path.isfile(input_path):
            messagebox.showerror("错误", "文件不存在")
            return
        if not self._ensure_ffmpeg():
            return
        output_path = self.file_output.get()
        fmt = self.file_format.get()
        quality = self.file_quality.get()
        if not output_path:
            base, _ = os.path.splitext(input_path)
            output_path = f"{base}.{fmt}"
            self.file_output.set(output_path)
        self._start_job(lambda: self._extract_file(input_path, output_path, fmt, quality))

    def _extract_file(self, input_path, output_path, fmt, quality):
        codec = self.CODEC_MAP.get(fmt, "libmp3lame")
        bitrate = self._get_quality_bitrate(quality)
        duration = self._get_duration(input_path)
        s = f"正在提取 ... {duration:.0f}s" if duration else "正在提取 ..."
        self.window.after(0, lambda: self._set_status(s, THEME["warning"]))
        ffmpeg = self._get_tool_path("ffmpeg.exe")
        cmd = [ffmpeg, "-i", input_path, "-vn", "-acodec", codec, "-b:a", bitrate, "-y", output_path]
        self._run_ffmpeg(cmd, duration)
        if not self.cancelled:
            self.window.after(0, lambda: self._set_status("\u2714 提取完成", THEME["success"]))
            self.window.after(0, lambda: self._show_result(output_path))
            self.window.after(0, self._done)

    # ==================== URL extraction ====================

    def _start_url_extract(self):
        raw = self.url_input.get().strip()
        if not raw:
            messagebox.showwarning("提示", "请先输入视频链接")
            return
        url = self._extract_url_from_text(raw)
        if not url:
            messagebox.showwarning("提示", "未检测到有效链接")
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
                self._set_status("缺少 requests 库", THEME["error"])
                self.window.after(0, self._done)
                return
            try:
                video_url, title = self._resolve_douyin(url)
                if video_url:
                    self._douyin_download(video_url, title)
                    return
                self.window.after(0, lambda: self._set_status("解析失败，尝试 yt-dlp ..."))
            except Exception:
                self.window.after(0, lambda: self._set_status("解析失败，尝试 yt-dlp ..."))
        self._ytdlp_fallback(url)

    def _douyin_download(self, video_url, title):
        self.window.after(0, lambda t=title or "": self._set_status(
            f"下载: {t[:40]}..." if t else "下载中 ...", THEME["warning"]))
        fmt = self.url_format.get()
        codec = self.CODEC_MAP.get(fmt, "libmp3lame")
        bitrate = self._get_quality_bitrate(self.url_quality.get())
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', title or "audio")
        output_path = os.path.join(self.url_output_dir.get(), f"{safe_title}.{fmt}")
        ffmpeg = self._get_tool_path("ffmpeg.exe")
        cmd = [ffmpeg, "-headers", f"User-Agent: {self.MOBILE_UA}\r\nReferer: https://www.iesdouyin.com/",
               "-i", video_url, "-vn", "-acodec", codec, "-b:a", bitrate, "-y", output_path]
        self._run_ffmpeg(cmd, None)
        if not self.cancelled:
            self.window.after(0, lambda: self._set_status("\u2714 提取完成", THEME["success"]))
            self.window.after(0, lambda: self._show_result(output_path))
            self.window.after(0, self._done)

    def _resolve_douyin(self, url):
        s = requests.Session()
        s.headers.update({
            "User-Agent": self.MOBILE_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        s.get("https://www.douyin.com", timeout=10)
        r = s.get(url, timeout=15)
        html = r.text
        title = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if m:
            title = m.group(1).strip()
        vid_match = re.search(r"video_id=([a-zA-Z0-9]+)", html)
        if vid_match:
            return f"https://aweme.snssdk.com/aweme/v1/playwm/?video_id={vid_match.group(1)}", title or "video"
        for pat in [r'window\._ROUTER_DATA\s*=\s*({.*?});\s*</script>',
                     r'"url_list":\["(https?://[^"]+\.mp4[^"]*)"\]']:
            m = re.search(pat, html, re.DOTALL)
            if m:
                found = m.group(1)
                if found.startswith("http"):
                    return found, title or "video"
                try:
                    data = json.loads(found)
                    items = data.get("loaderData", {}).get("video_(id)_page", {}).get("videoInfoRes", {}).get("item_list", [])
                    if not items:
                        items = self._deep_search(data, "item_list")
                    if items and isinstance(items, list):
                        urls = items[0].get("video", {}).get("play_addr", {}).get("url_list", [])
                        if urls:
                            return urls[0], items[0].get("desc", title) or title
                except Exception:
                    pass
        return None, None

    def _deep_search(self, obj, key):
        if isinstance(obj, dict):
            if key in obj:
                return obj[key]
            for v in obj.values():
                r = self._deep_search(v, key)
                if r is not None:
                    return r
        elif isinstance(obj, list):
            for v in obj:
                r = self._deep_search(v, key)
                if r is not None:
                    return r
        return None

    def _ytdlp_fallback(self, url):
        try:
            self._ensure_ytdlp()
        except Exception:
            self.window.after(0, lambda: self._set_status("yt-dlp 下载失败", THEME["error"]))
            self.window.after(0, self._done)
            return
        fmt = self.url_format.get()
        output_dir = self.url_output_dir.get()
        bitrate = self._get_quality_bitrate(self.url_quality.get()).replace("k", "")
        cmd = [self.ytdlp_path, "-x", "--audio-format", fmt, "--audio-quality", bitrate,
               "-o", os.path.join(output_dir, "%(title)s.%(ext)s"), "--no-playlist", url]
        self.window.after(0, lambda: self._set_status("yt-dlp 下载中 ...", THEME["warning"]))
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace")
        for line in self.process.stdout:
            if self.cancelled:
                self.process.terminate()
                break
            if "%" in line:
                try:
                    self.window.after(0, lambda p=float(line.split("%")[0].split()[-1]):
                                      self.progress.set(p))
                except Exception:
                    pass
            if line_stripped := line.strip():
                self.window.after(0, lambda l=line_stripped[:50]: self._set_status(l))
            if "[download] Destination:" in line:
                dest = line.split("Destination:")[-1].strip()
                self.window.after(0, lambda d=dest: self._show_result(d))
        self.process.wait()
        ok = self.process.returncode == 0
        self.window.after(0, lambda: self._set_status(
            "\u2714 提取完成" if ok else "下载失败", THEME["success"] if ok else THEME["error"]))
        self.window.after(0, self._done)

    # ==================== Helpers ====================

    def _start_job(self, fn):
        self.cancelled = False
        self.result_frame.pack_forget()
        self.progress.set(0)
        self._btn_working()
        self._set_status("准备中 ...", THEME["warning"])
        threading.Thread(target=fn, daemon=True).start()

    def _done(self):
        self._btn_idle()
        self.progress.set(100)

    def _extract_url_from_text(self, text):
        urls = re.findall(r"https?://[^\s]+", text)
        return urls[0].rstrip(".,;:!?\"'") if urls else None

    def _get_quality_bitrate(self, q):
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
        self._set_status("下载 ffmpeg 中 (~50MB) ...", THEME["warning"])
        return False

    def _ensure_ytdlp(self):
        p = self._get_tool_path("yt-dlp.exe")
        if p:
            self.ytdlp_path = p
        else:
            self._download_ytdlp()

    def _download_ytdlp(self):
        local = os.path.join(self._exe_dir(), "yt-dlp.exe")
        self.window.after(0, lambda: self._set_status("下载 yt-dlp (~10MB) ..."))
        urllib.request.urlretrieve(self.YTDLP_URL, local)
        self.ytdlp_path = local

    def _download_ffmpeg(self):
        d = self._exe_dir()
        self.window.after(0, lambda: self._set_status("下载 ffmpeg (~50MB) ..."))
        zp = os.path.join(d, "ffmpeg-temp.zip")
        urllib.request.urlretrieve(self.FFMPEG_URL, zp)
        self.window.after(0, lambda: self._set_status("解压 ffmpeg ..."))
        with zipfile.ZipFile(zp, "r") as zf:
            for m in zf.namelist():
                name = os.path.basename(m)
                if name in ("ffmpeg.exe", "ffprobe.exe"):
                    with zf.open(m) as src, open(os.path.join(d, name), "wb") as dst:
                        dst.write(src.read())
        os.remove(zp)
        self.window.after(0, self._idle_status)

    def _exe_dir(self):
        return os.path.dirname(os.path.abspath(sys.argv[0])) if getattr(sys, "frozen", False) \
            else os.path.dirname(os.path.abspath(__file__))

    def _get_tool_path(self, name):
        local = os.path.join(self._exe_dir(), name)
        return local if os.path.isfile(local) else shutil.which(name.replace(".exe", ""))

    def _run_ffmpeg(self, cmd, duration):
        self.process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        for line in self.process.stderr:
            if self.cancelled:
                self.process.terminate()
                break
            if "time=" in line:
                try:
                    h, m, s = line.split("time=")[1].split()[0].split(":")
                    sec = float(h) * 3600 + float(m) * 60 + float(s)
                    if duration:
                        self.window.after(0, lambda p=min(sec / duration * 100, 100): self.progress.set(p))
                except Exception:
                    pass
            elif duration is None and "Duration:" in line:
                try:
                    h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
                    duration = float(h) * 3600 + float(m) * 60 + float(s)
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
    app = AudioExtractorApp()
    app.run()


if __name__ == "__main__":
    main()
