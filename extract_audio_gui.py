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

C = {
    "bg":         "#f8fafc",
    "surface":    "#ffffff",
    "border":     "#e2e8f0",
    "primary":    "#6366f1",
    "primary_h":  "#4f46e5",
    "text":       "#1e293b",
    "text_sub":   "#64748b",
    "text_light": "#94a3b8",
    "success":    "#22c55e",
    "error":      "#ef4444",
    "warning":    "#f59e0b",
}


class ModernFrame(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["surface"], highlightbackground=C["border"], highlightthickness=1, **kw)


class RoundedEntry(ttk.Entry):
    pass


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
        self.window.title("AudioExtract  \u2014  视频提取音频")
        self.window.geometry("600x540")
        self.window.resizable(False, False)
        self.window.configure(bg=C["bg"])

        self._init_styles()
        self._load_config()

        self.file_input = tk.StringVar()
        self.file_output = tk.StringVar()
        self.file_format = tk.StringVar(value="mp3")
        self.file_quality = tk.StringVar(value="medium")
        self.url_input = tk.StringVar()
        self.url_output_dir = tk.StringVar(value=self.config.get("last_dir", os.path.join(os.path.expanduser("~"), "Downloads")))
        self.url_format = tk.StringVar(value="mp3")
        self.url_quality = tk.StringVar(value="medium")
        self.status = tk.StringVar(value="\u25cf  就绪")
        self.progress = tk.DoubleVar(value=0)
        self.progress_text = tk.StringVar(value="")
        self.process = None
        self.cancelled = False
        self.last_output = ""
        self.ytdlp_path = None

        self.build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=C["bg"], foreground=C["text"])
        s.configure("TNotebook", background=C["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", font=("Microsoft YaHei UI", 11), padding=[18, 8],
                    background=C["surface"], foreground=C["text_sub"])
        s.map("TNotebook.Tab", background=[("selected", C["primary"])], foreground=[("selected", C["surface"])])
        s.configure("Card.TFrame", background=C["surface"], borderwidth=0)
        s.configure("Card.TLabelframe", background=C["surface"], borderwidth=0)
        s.configure("Card.TLabelframe.Label", font=("Microsoft YaHei UI", 11, "bold"),
                    background=C["surface"], foreground=C["text"], padding=(0, 4))
        s.configure("TLabel", background=C["bg"], foreground=C["text_sub"], font=("Microsoft YaHei UI", 10))
        s.configure("Bold.TLabel", font=("Microsoft YaHei UI", 10, "bold"), foreground=C["text"])
        s.configure("Title.TLabel", font=("Microsoft YaHei UI", 20, "bold"), background=C["bg"], foreground=C["text"])
        s.configure("TEntry", font=("Microsoft YaHei UI", 10), fieldbackground=C["surface"],
                    borderwidth=1, relief="solid", padding=6)
        s.configure("TCombobox", font=("Microsoft YaHei UI", 10), fieldbackground=C["surface"], padding=4)
        s.configure("TButton", font=("Microsoft YaHei UI", 10), padding=[12, 5])
        s.configure("Small.TButton", font=("Microsoft YaHei UI", 9), padding=[8, 3])
        s.configure("TProgressbar", troughcolor=C["border"], background=C["primary"], bordercolor=C["border"],
                    lightcolor=C["primary"], darkcolor=C["primary"], thickness=6)
        s.configure("Link.TLabel", font=("Microsoft YaHei UI", 9, "underline"),
                    foreground=C["primary"], background=C["bg"], cursor="hand2")
        s.configure("Chip.TLabel", font=("Microsoft YaHei UI", 10), background=C["bg"],
                    foreground=C["text_sub"], padding=(4, 2))

    def _config_path(self):
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                           "video-audio-extractor", "config.json")

    def _load_config(self):
        self.config = {}
        try:
            p = self._config_path()
            if os.path.isfile(p):
                with open(p, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
        except Exception:
            pass

    def _save_config(self):
        try:
            p = self._config_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False)
        except Exception:
            pass

    # ==================== UI ====================

    def build_ui(self):
        # Header bar
        header = tk.Frame(self.window, bg=C["primary"], height=6)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Title area
        title_area = tk.Frame(self.window, bg=C["bg"])
        title_area.pack(fill="x", padx=28, pady=(18, 0))
        ttk.Label(title_area, text="Audio Extract", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_area, text="本地文件与在线链接，一键提取音频",
                  style="Chip.TLabel").pack(anchor="w", pady=(2, 0))

        # Tabs
        tab_bar = tk.Frame(self.window, bg=C["bg"])
        tab_bar.pack(fill="x", padx=28, pady=(16, 0))
        self.notebook = ttk.Notebook(tab_bar)
        self.notebook.pack(fill="both", expand=True)
        self.build_local_tab()
        self.build_url_tab()

        # Bottom bar
        footer = tk.Frame(self.window, bg=C["bg"])
        footer.pack(fill="x", padx=28, pady=(0, 12))
        ttk.Label(footer, text="\u00a9 AudioExtract v1.1  \u00b7  ffmpeg \u00b7  yt-dlp",
                  style="Chip.TLabel").pack(side="left")

    def _card(self, parent, title=None, **pack_kw):
        outer = tk.Frame(parent, bg=C["border"])
        outer.pack(**pack_kw)
        inner = tk.Frame(outer, bg=C["surface"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        inner.pack_configure(padx=1, pady=1)
        if title:
            lbl = tk.Label(inner, text=title, font=("Microsoft YaHei UI", 11, "bold"),
                           bg=C["surface"], fg=C["text"], anchor="w")
            lbl.pack(fill="x", padx=16, pady=(14, 0))
        return inner

    def build_local_tab(self):
        tab = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab, text="  本地文件  ")

        c = self._card(tab, fill="x", padx=0, pady=(12, 10))
        ttk.Label(c, text="选择要提取音频的视频文件", font=("Microsoft YaHei UI", 10),
                  background=C["surface"], foreground=C["text_sub"]).pack(anchor="w", padx=16, pady=(4 if False else 0))
        row = tk.Frame(c, bg=C["surface"])
        row.pack(fill="x", padx=16, pady=(10, 14))
        self.file_entry = ttk.Entry(row, textvariable=self.file_input, state="readonly", width=42)
        self.file_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="+ 选择文件", command=self.select_file).pack(side="left", padx=(8, 0))

        c2 = self._card(tab, "输出设置", fill="x", padx=0, pady=(0, 10))
        row1 = tk.Frame(c2, bg=C["surface"])
        row1.pack(fill="x", padx=16, pady=(10, 8))
        ttk.Label(row1, text="格式", background=C["surface"]).pack(side="left")
        ttk.Combobox(row1, textvariable=self.file_format, width=5, state="readonly",
                     values=self.FORMATS).pack(side="left", padx=(6, 18))
        ttk.Label(row1, text="音质", background=C["surface"]).pack(side="left")
        q = ttk.Combobox(row1, textvariable=self.file_quality, width=10, state="readonly",
                         values=["\u4f4e (128k)", "\u4e2d (192k)", "\u9ad8 (320k)"])
        q.pack(side="left", padx=(6, 0))
        q.set("\u4e2d (192k)")

        row2 = tk.Frame(c2, bg=C["surface"])
        row2.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Label(row2, text="保存至", background=C["surface"]).pack(side="left")
        ttk.Entry(row2, textvariable=self.file_output, width=44).pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Button(row2, text="\u2026", style="Small.TButton", command=self.select_file_output).pack(side="left", padx=(6, 0))

        self._build_bottom(tab, self._start_file_extract)

    def build_url_tab(self):
        tab = tk.Frame(self.notebook, bg=C["bg"])
        self.notebook.add(tab, text="  在线链接  ")

        c = self._card(tab, fill="x", padx=0, pady=(12, 10))
        ttk.Label(c, text="粘贴抖音或 B 站分享链接", font=("Microsoft YaHei UI", 10),
                  background=C["surface"], foreground=C["text_sub"]).pack(anchor="w", padx=16, pady=(14, 0))
        ttk.Label(c, text="支持从复制的整段文字中自动识别链接",
                  font=("Microsoft YaHei UI", 9),
                  background=C["surface"], foreground=C["text_light"]).pack(anchor="w", padx=16, pady=(2, 0))
        url_inner = tk.Frame(c, bg=C["border"])
        url_inner.pack(fill="x", padx=16, pady=(10, 14))
        ttk.Entry(url_inner, textvariable=self.url_input, width=52).pack(fill="x", padx=1, pady=1)

        c2 = self._card(tab, "输出设置", fill="x", padx=0, pady=(0, 10))
        row1 = tk.Frame(c2, bg=C["surface"])
        row1.pack(fill="x", padx=16, pady=(10, 8))
        ttk.Label(row1, text="格式", background=C["surface"]).pack(side="left")
        ttk.Combobox(row1, textvariable=self.url_format, width=5, state="readonly",
                     values=self.FORMATS).pack(side="left", padx=(6, 18))
        ttk.Label(row1, text="音质", background=C["surface"]).pack(side="left")
        q = ttk.Combobox(row1, textvariable=self.url_quality, width=10, state="readonly",
                         values=["\u4f4e (128k)", "\u4e2d (192k)", "\u9ad8 (320k)"])
        q.pack(side="left", padx=(6, 0))
        q.set("\u4e2d (192k)")

        row2 = tk.Frame(c2, bg=C["surface"])
        row2.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Label(row2, text="保存至", background=C["surface"]).pack(side="left")
        ttk.Entry(row2, textvariable=self.url_output_dir, width=42).pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Button(row2, text="\u2026", style="Small.TButton", command=self.select_dir).pack(side="left", padx=(6, 0))

        self._build_bottom(tab, self._start_url_extract)

    def _build_bottom(self, parent, extract_cmd):
        # Progress card
        prog_card = self._card(parent, "进度", fill="x", padx=0, pady=(0, 10))
        pbar_frame = tk.Frame(prog_card, bg=C["surface"])
        pbar_frame.pack(fill="x", padx=16, pady=(8, 4))
        self.progress_bar = ttk.Progressbar(pbar_frame, variable=self.progress, maximum=100)
        self.progress_bar.pack(fill="x")

        status_row = tk.Frame(prog_card, bg=C["surface"])
        status_row.pack(fill="x", padx=16, pady=(4, 6))
        tk.Frame(status_row, bg=C["success" if False else C["success"]], width=8, height=8).pack(side="left")
        self.status_indicator = tk.Frame(status_row, bg=C["text_light"], width=8, height=8)
        self.status_indicator.pack(side="left")
        self.status_label = ttk.Label(status_row, textvariable=self.status, font=("Microsoft YaHei UI", 10),
                                      background=C["surface"], foreground=C["text_sub"])
        self.status_label.pack(side="left", padx=(8, 0))

        self.result_frame = tk.Frame(prog_card, bg=C["surface"])
        self.result_label = tk.Label(self.result_frame, text="", font=("Microsoft YaHei UI", 9, "underline"),
                                     bg=C["surface"], fg=C["primary"], cursor="hand2")
        self.result_label.pack(anchor="w", padx=16, pady=(0, 8))
        self.result_label.bind("<Button-1>", lambda e: self._open_folder(self.last_output))

        # Action button
        btn_frame = tk.Frame(parent, bg=C["bg"])
        btn_frame.pack(fill="x", padx=0, pady=(0, 0))
        self.extract_btn = tk.Button(
            btn_frame, text="\u25b6  提取音频", command=extract_cmd,
            font=("Microsoft YaHei UI", 13, "bold"),
            bg=C["primary"], fg="#ffffff", activebackground=C["primary_h"], activeforeground="#ffffff",
            relief="flat", padx=28, pady=10, cursor="hand2",
            borderwidth=0, highlightthickness=0
        )
        self.extract_btn.pack()

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

    def _show_result_link(self, path):
        self.last_output = path
        folder = os.path.dirname(path)
        short = folder
        if len(folder) > 55:
            short = folder[:25] + "..." + folder[-27:]
        self.result_label.config(text=f"\u2197 \u6253\u5f00\u6587\u4ef6\u5939: {short}")
        self.result_frame.pack(fill="x", padx=0, pady=(0, 0))

    def _update_status(self, text, state="idle"):
        colors = {"idle": C["text_light"], "working": C["warning"], "done": C["success"], "error": C["error"]}
        self.status_indicator.config(bg=colors.get(state, C["text_light"]))
        self.status.set(f"\u25cf  {text}")

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

        self.cancelled = False
        self.result_frame.pack_forget()
        self.extract_btn.config(text="\u25cf\u25cf\u25cf  提取中 ...", state="disabled",
                                bg=C["text_light"], activebackground=C["text_light"])
        self._update_status("正在解析视频 ...", "working")
        self.progress.set(0)

        threading.Thread(target=self._extract_file, args=(input_path, output_path, fmt, quality), daemon=True).start()

    def _extract_file(self, input_path, output_path, fmt, quality):
        codec = self.CODEC_MAP.get(fmt, "libmp3lame")
        bitrate = self._get_quality_bitrate(quality)
        duration = self._get_duration(input_path)
        self.window.after(0, lambda d=duration: self._update_status(
            f"正在提取 ... 时长 {d:.0f}s" if d else "正在提取 ...", "working"))
        ffmpeg = self._get_tool_path("ffmpeg.exe")
        cmd = [ffmpeg, "-i", input_path, "-vn", "-acodec", codec, "-b:a", bitrate, "-y", output_path]
        self._run_process(cmd, duration)
        if not self.cancelled:
            self.window.after(0, lambda: self._update_status("提取完成", "done"))
            self.window.after(0, lambda p=output_path: self._show_result_link(p))
            self.window.after(0, self.on_complete)

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
        self.cancelled = False
        self.result_frame.pack_forget()
        self.extract_btn.config(text="\u25cf\u25cf\u25cf  提取中 ...", state="disabled",
                                bg=C["text_light"], activebackground=C["text_light"])
        self._update_status("正在解析链接 ...", "working")
        self.progress.set(0)
        threading.Thread(target=self._extract_url, args=(url,), daemon=True).start()

    def _extract_url(self, url):
        if 'douyin.com' in url or 'iesdouyin.com' in url:
            if not HAS_REQUESTS:
                self._update_status("缺少 requests 库", "error")
                self.window.after(0, self.on_complete)
                return
            try:
                video_url, title = self._resolve_douyin(url)
                if video_url:
                    self._douyin_download(video_url, title)
                    return
                self.window.after(0, lambda: self._update_status("解析失败，尝试 yt-dlp ...", "working"))
            except Exception:
                self.window.after(0, lambda: self._update_status("解析失败，尝试 yt-dlp ...", "working"))
        self._ytdlp_fallback(url)

    def _douyin_download(self, video_url, title):
        self.window.after(0, lambda t=title or "": self._update_status(
            f"正在下载: {t[:40]}..." if t else "正在下载 ...", "working"))
        fmt = self.url_format.get()
        codec = self.CODEC_MAP.get(fmt, "libmp3lame")
        bitrate = self._get_quality_bitrate(self.url_quality.get())
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', title or "audio")
        output_dir = self.url_output_dir.get()
        output_path = os.path.join(output_dir, f"{safe_title}.{fmt}")
        ffmpeg = self._get_tool_path("ffmpeg.exe")
        cmd = [ffmpeg, "-headers", f"User-Agent: {self.MOBILE_UA}\r\nReferer: https://www.iesdouyin.com/",
               "-i", video_url, "-vn", "-acodec", codec, "-b:a", bitrate, "-y", output_path]
        self._run_process(cmd, None)
        if not self.cancelled:
            self.window.after(0, lambda: self._update_status("提取完成", "done"))
            self.window.after(0, lambda p=output_path: self._show_result_link(p))
            self.window.after(0, self.on_complete)

    def _resolve_douyin(self, url):
        s = requests.Session()
        s.headers.update({
            'User-Agent': self.MOBILE_UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        s.get('https://www.douyin.com', timeout=10)
        r = s.get(url, timeout=15)
        html = r.text
        title = ""
        m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if m:
            title = m.group(1).strip()
        vid_match = re.search(r'video_id=([a-zA-Z0-9]+)', html)
        if vid_match:
            video_id = vid_match.group(1)
            return f'https://aweme.snssdk.com/aweme/v1/playwm/?video_id={video_id}', title or video_id[:20]
        for pattern in [
            r'window\._ROUTER_DATA\s*=\s*({.*?});\s*</script>',
            r'"url_list":\["(https?://[^"]+\.mp4[^"]*)"\]',
            r'"download_addr".*?url_list.*?\["(https?://[^"]+)"\]',
        ]:
            m = re.search(pattern, html, re.DOTALL)
            if m:
                found = m.group(1)
                if found.startswith('http'):
                    return found, title or "video"
                try:
                    data = json.loads(found)
                    item_list = data.get('loaderData', {}).get('video_(id)_page', {}).get('videoInfoRes', {}).get('item_list', [])
                    if not item_list:
                        item_list = self._deep_search(data, 'item_list')
                    if item_list and isinstance(item_list, list) and len(item_list) > 0:
                        video = item_list[0].get('video', {})
                        urls = video.get('play_addr', {}).get('url_list', [])
                        if urls:
                            return urls[0], item_list[0].get('desc', title) or title
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
        except Exception as e:
            self.window.after(0, lambda: self._update_status(f"yt-dlp 下载失败", "error"))
            self.window.after(0, self.on_complete)
            return

        fmt = self.url_format.get()
        quality = self.url_quality.get()
        output_dir = self.url_output_dir.get()
        bitrate = self._get_quality_bitrate(quality).replace("k", "")
        cmd = [self.ytdlp_path, "-x", "--audio-format", fmt, "--audio-quality", bitrate,
               "-o", os.path.join(output_dir, "%(title)s.%(ext)s"), "--no-playlist", url]
        self.window.after(0, lambda: self._update_status("yt-dlp 下载中 ...", "working"))
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace")
        last_line = ""
        for line in self.process.stdout:
            if self.cancelled:
                self.process.terminate()
                break
            if "%" in line:
                try:
                    pct = float(line.split("%")[0].split()[-1])
                    self.window.after(0, lambda p=pct: self.progress.set(p))
                except (ValueError, IndexError):
                    pass
            line_stripped = line.strip()
            if line_stripped:
                last_line = line_stripped[:60]
                self.window.after(0, lambda l=last_line: self._update_status(l, "working"))
            if "[download] Destination:" in line:
                dest = line.split("Destination:")[-1].strip()
                self.window.after(0, lambda d=dest: self._show_result_link(d))
        self.process.wait()
        if self.process.returncode != 0 and not self.cancelled:
            self.window.after(0, lambda: self._update_status("下载失败", "error"))
        else:
            self.window.after(0, lambda: self._update_status("提取完成", "done"))
        self.window.after(0, self.on_complete)

    # ==================== Utilities ====================

    def _extract_url_from_text(self, text):
        urls = re.findall(r'https?://[^\s]+', text)
        return urls[0].rstrip(".,;:!?'\"") if urls else None

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
        self._update_status("首次使用，下载 ffmpeg 中 (~50MB) ...", "working")
        return False

    def _ensure_ytdlp(self):
        p = self._get_tool_path("yt-dlp.exe")
        if p:
            self.ytdlp_path = p
        else:
            self._download_ytdlp()

    def _download_ytdlp(self):
        local = os.path.join(self._exe_dir(), "yt-dlp.exe")
        self.window.after(0, lambda: self._update_status("下载 yt-dlp 中 (~10MB) ...", "working"))
        urllib.request.urlretrieve(self.YTDLP_URL, local)
        self.ytdlp_path = local
        self.window.after(0, lambda: self._update_status("就绪", "idle"))

    def _download_ffmpeg(self):
        exe_dir = self._exe_dir()
        self.window.after(0, lambda: self._update_status("下载 ffmpeg 中 (~50MB) ...", "working"))
        zp = os.path.join(exe_dir, "ffmpeg-temp.zip")
        urllib.request.urlretrieve(self.FFMPEG_URL, zp)
        self.window.after(0, lambda: self._update_status("解压 ffmpeg ...", "working"))
        with zipfile.ZipFile(zp, 'r') as zf:
            for m in zf.namelist():
                name = os.path.basename(m)
                if name in ('ffmpeg.exe', 'ffprobe.exe'):
                    with zf.open(m) as src, open(os.path.join(exe_dir, name), 'wb') as dst:
                        dst.write(src.read())
        os.remove(zp)
        self.window.after(0, lambda: self._update_status("就绪", "idle"))

    def _exe_dir(self):
        return os.path.dirname(os.path.abspath(sys.argv[0])) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

    def _get_tool_path(self, name):
        local = os.path.join(self._exe_dir(), name)
        return local if os.path.isfile(local) else shutil.which(name.replace(".exe", ""))

    def _run_process(self, cmd, duration):
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
                except (ValueError, IndexError):
                    pass
            elif duration is None and "Duration:" in line:
                try:
                    h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
                    duration = float(h) * 3600 + float(m) * 60 + float(s)
                except (ValueError, IndexError):
                    pass
        self.process.wait()

    def on_complete(self):
        self.extract_btn.config(text="\u25b6  提取音频", state="normal",
                                bg=C["primary"], activebackground=C["primary_h"])
        self.progress.set(100)

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
