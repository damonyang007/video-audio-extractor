import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import sys
import shutil
import threading
import re
import urllib.request
import tempfile
import http.cookiejar
import ssl
import urllib.parse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class AudioExtractorApp:
    FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

    def __init__(self):
        self.window = tk.Tk()
        self.window.title("视频提取音频")
        self.window.geometry("560x500")
        self.window.resizable(False, False)
        self.window.configure(bg="#f0f0f0")

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TLabel", background="#f0f0f0")
        self.style.configure("TLabelframe", background="#f0f0f0")
        self.style.configure("TLabelframe.Label", font=("Microsoft YaHei", 10), background="#f0f0f0")
        self.style.configure("TCombobox", font=("Microsoft YaHei", 10))
        self.style.configure("TEntry", font=("Microsoft YaHei", 10))
        self.style.configure("TButton", font=("Microsoft YaHei", 10), padding=6)
        self.style.configure("green.Horizontal.TProgressbar", troughcolor="#e0e0e0", background="#4caf50")
        self.style.configure("Title.TLabel", font=("Microsoft YaHei", 16, "bold"), background="#f0f0f0")
        self.style.configure("Hint.TLabel", font=("Microsoft YaHei", 9), background="#f0f0f0", foreground="#888888")

        self.file_input = tk.StringVar()
        self.file_output = tk.StringVar()
        self.file_format = tk.StringVar(value="mp3")
        self.file_quality = tk.StringVar(value="medium")

        self.url_input = tk.StringVar()
        self.url_output_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self.url_format = tk.StringVar(value="mp3")
        self.url_quality = tk.StringVar(value="medium")

        self.status = tk.StringVar(value="就绪")
        self.progress = tk.DoubleVar(value=0)
        self.process = None
        self.cancelled = False

        self.build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self):
        ttk.Label(self.window, text="视频提取音频", style="Title.TLabel").pack(pady=(16, 12))
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        self.build_local_tab()
        self.build_url_tab()

    def build_local_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  本地文件  ")
        self._build_file_frame(tab)
        self._build_output_frame(tab, self.file_format, self.file_quality, self.file_output, self.select_file_output)
        self._build_bottom(tab, self._start_file_extract)

    def build_url_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  在线链接  ")

        input_frame = ttk.LabelFrame(tab, text="视频链接", padding=10)
        input_frame.pack(fill="x", padx=4, pady=(10, 8))
        ttk.Entry(input_frame, textvariable=self.url_input).pack(fill="x")
        ttk.Label(input_frame, text="粘贴抖音、B站等平台的分享链接，自动识别",
                  style="Hint.TLabel").pack(anchor="w", pady=(4, 0))

        self._build_output_frame(tab, self.url_format, self.url_quality, None, None,
                                 extra_row=self._build_dir_row)
        self._build_bottom(tab, self._start_url_extract)

    def _build_dir_row(self, parent):
        row = ttk.Frame(parent)
        row.pack(fill="x")
        ttk.Label(row, text="保存目录:").pack(side="left")
        ttk.Entry(row, textvariable=self.url_output_dir).pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Button(row, text="浏览", command=self.select_dir, width=6).pack(side="left", padx=(8, 0))

    def _build_file_frame(self, tab):
        input_frame = ttk.LabelFrame(tab, text="输入文件", padding=10)
        input_frame.pack(fill="x", padx=4, pady=(10, 8))
        row = ttk.Frame(input_frame)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.file_input, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="选择文件", command=self.select_file, width=10).pack(side="left", padx=(8, 0))

    def _build_output_frame(self, tab, fmt_var, q_var, out_var, out_cmd, extra_row=None):
        frame = ttk.LabelFrame(tab, text="输出设置", padding=10)
        frame.pack(fill="x", padx=4, pady=(0, 8))

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="输出格式:").pack(side="left")
        ttk.Combobox(row, textvariable=fmt_var, width=6, state="readonly",
                     values=["mp3", "wav", "aac", "m4a", "ogg", "flac", "wma"]).pack(side="left", padx=(6, 20))
        ttk.Label(row, text="音质:").pack(side="left")
        q = ttk.Combobox(row, textvariable=q_var, width=8, state="readonly",
                         values=["low (128k)", "medium (192k)", "high (320k)"])
        q.pack(side="left", padx=(6, 0))
        q.set("medium (192k)")

        if out_var is not None:
            row2 = ttk.Frame(frame)
            row2.pack(fill="x")
            ttk.Label(row2, text="输出路径:").pack(side="left")
            ttk.Entry(row2, textvariable=out_var).pack(side="left", fill="x", expand=True, padx=(6, 0))
            ttk.Button(row2, text="浏览", command=out_cmd, width=6).pack(side="left", padx=(8, 0))

        if extra_row:
            extra_row(frame)

    def _build_bottom(self, parent, extract_cmd):
        progress_frame = ttk.LabelFrame(parent, text="进度", padding=10)
        progress_frame.pack(fill="x", padx=4, pady=(0, 8))
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress, maximum=100,
                                            style="green.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x")
        self.status_label = ttk.Label(progress_frame, textvariable=self.status)
        self.status_label.pack(pady=(6, 0))
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", padx=4, pady=(4, 0))
        self.extract_btn = tk.Button(
            btn_frame, text="提取音频", command=extract_cmd,
            font=("Microsoft YaHei", 12, "bold"),
            bg="#4a90d9", fg="white", activebackground="#357abd", activeforeground="white",
            relief="flat", padx=40, pady=8, cursor="hand2"
        )
        self.extract_btn.pack()

    def select_file(self):
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.rmvb *.3gp"),
                       ("所有文件", "*.*")]
        )
        if path:
            self.file_input.set(path)
            base, _ = os.path.splitext(path)
            self.file_output.set(f"{base}.{self.file_format.get()}")

    def select_file_output(self):
        path = filedialog.asksaveasfilename(
            title="保存音频文件",
            defaultextension=f".{self.file_format.get()}",
            filetypes=[("音频文件", f"*.{self.file_format.get()}"), ("所有文件", "*.*")]
        )
        if path:
            self.file_output.set(path)

    def select_dir(self):
        path = filedialog.askdirectory(title="选择保存目录")
        if path:
            self.url_output_dir.set(path)

    def _extract_url_from_text(self, text):
        urls = re.findall(r'https?://[^\s]+', text)
        if urls:
            return urls[0].rstrip(".,;:!?'\"")
        return None

    def _get_quality_bitrate(self, quality_str):
        if "(" in quality_str:
            quality_str = quality_str.split("(")[0].strip()
        return {"low": "128k", "medium": "192k", "high": "320k"}.get(quality_str, "192k")

    # ---- File extraction ----
    def _start_file_extract(self):
        input_path = self.file_input.get()
        if not input_path:
            messagebox.showwarning("提示", "请先选择视频文件")
            return
        if not os.path.isfile(input_path):
            messagebox.showerror("错误", "文件不存在")
            return
        if not self._get_tool_path("ffmpeg.exe"):
            threading.Thread(target=self._download_ffmpeg, daemon=True).start()
            self.window.after(0, lambda: self.status.set("首次使用，正在下载 ffmpeg (约50MB)...下载完成后请重试"))
            return

        output_path = self.file_output.get()
        fmt = self.file_format.get()
        quality = self.file_quality.get()
        if not output_path:
            base, _ = os.path.splitext(input_path)
            output_path = f"{base}.{fmt}"
            self.file_output.set(output_path)

        self.cancelled = False
        self.extract_btn.config(text="提取中...", state="disabled")
        self.status.set("正在解析视频...")
        self.progress.set(0)

        threading.Thread(target=self._extract_file, args=(input_path, output_path, fmt, quality), daemon=True).start()

    def _extract_file(self, input_path, output_path, fmt, quality):
        codec = {"mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac",
                 "m4a": "aac", "ogg": "libvorbis", "flac": "flac", "wma": "wmav2"}.get(fmt, "libmp3lame")
        bitrate = self._get_quality_bitrate(quality)

        duration = None
        try:
            result = subprocess.run(
                [self._get_tool_path("ffprobe.exe"), "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", input_path],
                capture_output=True, text=True
            )
            duration = float(result.stdout.strip())
        except Exception:
            pass

        self.window.after(0, lambda d=duration: self.status.set(
            f"正在提取... 时长: {d:.0f}秒" if d else "正在提取..."))

        ffmpeg = self._get_tool_path("ffmpeg.exe")
        cmd = [ffmpeg, "-i", input_path, "-vn", "-acodec", codec, "-b:a", bitrate, "-y", output_path]
        self._run_process(cmd, duration)

        if not self.cancelled:
            self.window.after(0, lambda p=output_path: self.status.set(f"完成! {os.path.basename(p)}"))
            self.window.after(0, self.on_finish)

    # ---- URL extraction (Douyin) ----
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

        if not self._get_tool_path("ffmpeg.exe"):
            threading.Thread(target=self._download_ffmpeg, daemon=True).start()
            self.window.after(0, lambda: self.status.set("首次使用，正在下载 ffmpeg (约50MB)...下载完成后请重试"))
            return

        self.cancelled = False
        self.extract_btn.config(text="提取中...", state="disabled")
        self.status.set("正在解析链接...")
        self.progress.set(0)

        threading.Thread(target=self._extract_url, args=(url,), daemon=True).start()

    def _extract_url(self, url):
        is_douyin = 'douyin.com' in url or 'iesdouyin.com' in url

        if is_douyin:
            if not HAS_REQUESTS:
                self.window.after(0, lambda: self.status.set("需要requests库，请运行: pip install requests"))
                self.window.after(0, self.on_finish)
                return

        if is_douyin:
            try:
                video_url, title = self._resolve_douyin(url)
                if video_url:
                    self.window.after(0, lambda t=title or "": self.status.set(f"正在下载: {t}" if t else "正在下载..."))
                    fmt = self.url_format.get()
                    quality = self.url_quality.get()
                    codec = {"mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac",
                             "m4a": "aac", "ogg": "libvorbis", "flac": "flac"}.get(fmt, "libmp3lame")
                    bitrate = self._get_quality_bitrate(quality)
                    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title or "audio")
                    output_dir = self.url_output_dir.get()
                    output_path = os.path.join(output_dir, f"{safe_title}.{fmt}")
                    ffmpeg = self._get_tool_path("ffmpeg.exe")
                    cmd = [ffmpeg,
                           "-headers", "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15\r\nReferer: https://www.iesdouyin.com/",
                           "-i", video_url, "-vn", "-acodec", codec, "-b:a", bitrate, "-y", output_path]
                    self._run_process(cmd, None)
                    if not self.cancelled:
                        self.window.after(0, lambda p=output_path: self.status.set(f"完成! {os.path.basename(p)}"))
                        self.window.after(0, self.on_finish)
                    return
                else:
                    self.window.after(0, lambda: self.status.set("抖音解析失败，尝试yt-dlp..."))
            except Exception:
                self.window.after(0, lambda: self.status.set("抖音解析失败，尝试yt-dlp..."))

        self._ytdlp_fallback(url)

    def _resolve_douyin(self, url):
        s = requests.Session()
        s.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })

        # Step 1: Visit douyin.com for initial cookies
        s.get('https://www.douyin.com', timeout=10)

        # Step 2: Follow short link
        r = s.get(url, timeout=15)
        final_url = r.url

        # Step 3: Parse page for video data
        html = r.text
        title = ""

        # Extract title
        m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if m:
            title = m.group(1).strip()

        # Extract video_id and play URL
        vid_match = re.search(r'video_id=([a-zA-Z0-9]+)', html)
        if vid_match:
            video_id = vid_match.group(1)
            # Use the aweme play URL
            play_url = f'https://aweme.snssdk.com/aweme/v1/playwm/?video_id={video_id}'
            return play_url, title or video_id[:20]

        # Alternative: look in _ROUTER_DATA or embedded JSON
        json_patterns = [
            r'window\._ROUTER_DATA\s*=\s*({.*?});\s*</script>',
            r'"url_list":\["(https?://[^"]+\.mp4[^"]*)"\]',
            r'"download_addr".*?url_list.*?\["(https?://[^"]+)"\]',
        ]
        for pattern in json_patterns:
            m = re.search(pattern, html, re.DOTALL)
            if m:
                found = m.group(1)
                if found.startswith('http'):
                    return found, title or "video"
                try:
                    import json
                    data = json.loads(found)
                    # Navigate the nested structure
                    item_list = data.get('loaderData', {}).get('video_(id)_page', {}).get('videoInfoRes', {}).get('item_list', [])
                    if not item_list:
                        item_list = self._deep_search(data, 'item_list')
                    if item_list and isinstance(item_list, list) and len(item_list) > 0:
                        video = item_list[0].get('video', {})
                        urls = video.get('play_addr', {}).get('url_list', [])
                        if urls:
                            title = item_list[0].get('desc', title) or title
                            return urls[0], title
                except Exception:
                    pass

        return None, None

    def _deep_search(self, obj, key):
        if isinstance(obj, dict):
            if key in obj:
                return obj[key]
            for v in obj.values():
                result = self._deep_search(v, key)
                if result is not None:
                    return result
        elif isinstance(obj, list):
            for v in obj:
                result = self._deep_search(v, key)
                if result is not None:
                    return result
        return None

    def _ytdlp_fallback(self, url):
        try:
            self._ensure_ytdlp()
            ytdlp_path = self.ytdlp_path
        except Exception as e:
            self.window.after(0, lambda: self.status.set(f"yt-dlp下载失败: {e}"))
            self.window.after(0, self.on_finish)
            return

        fmt = self.url_format.get()
        quality = self.url_quality.get()
        output_dir = self.url_output_dir.get()
        bitrate = self._get_quality_bitrate(quality).replace("k", "")

        cmd = [ytdlp_path, "-x", "--audio-format", fmt, "--audio-quality", bitrate,
               "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
               "--no-playlist", url]

        self.window.after(0, lambda: self.status.set("yt-dlp 正在下载..."))
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
                last_line = line_stripped[:80]
                self.window.after(0, lambda l=last_line: self.status.set(l))

        self.process.wait()

        if self.process.returncode != 0 and not self.cancelled:
            self.window.after(0, lambda: self.status.set(f"下载失败 (错误码:{self.process.returncode})"))
        self.window.after(0, self.on_finish)

    def _find_ytdlp(self):
        return self._get_tool_path("yt-dlp.exe")

    def _ensure_ytdlp(self):
        ytdlp_path = self._find_ytdlp()
        if ytdlp_path:
            self.ytdlp_path = ytdlp_path
        else:
            self._download_ytdlp()

    def _download_ytdlp(self):
        local = os.path.join(self._exe_dir(), "yt-dlp.exe")
        self.window.after(0, lambda: self.status.set("正在下载 yt-dlp (约10MB)..."))
        urllib.request.urlretrieve(self.YTDLP_URL, local)
        self.ytdlp_path = local
        self.window.after(0, lambda: self.status.set("就绪"))

    def _download_ffmpeg(self):
        exe_dir = self._exe_dir()
        ffmpeg_exe = os.path.join(exe_dir, "ffmpeg.exe")
        ffprobe_exe = os.path.join(exe_dir, "ffprobe.exe")

        self.window.after(0, lambda: self.status.set("首次使用，正在下载 ffmpeg (约50MB)..."))
        zip_path = os.path.join(exe_dir, "ffmpeg-temp.zip")
        urllib.request.urlretrieve(self.FFMPEG_URL, zip_path)

        self.window.after(0, lambda: self.status.set("正在解压 ffmpeg..."))
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                name = os.path.basename(member)
                if name in ('ffmpeg.exe', 'ffprobe.exe'):
                    with zf.open(member) as src, open(os.path.join(exe_dir, name), 'wb') as dst:
                        dst.write(src.read())
        os.remove(zip_path)

        self.window.after(0, lambda: self.status.set("就绪"))

    def _exe_dir(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(os.path.abspath(sys.argv[0]))
        return os.path.dirname(os.path.abspath(__file__))

    def _run_process(self, cmd, duration):
        self.process = subprocess.Popen(
            cmd, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace"
        )
        for line in self.process.stderr:
            if self.cancelled:
                self.process.terminate()
                break
            if "time=" in line:
                try:
                    time_str = line.split("time=")[1].split()[0]
                    h, m, s = time_str.split(":")
                    seconds = float(h) * 3600 + float(m) * 60 + float(s)
                    if duration:
                        pct = min(seconds / duration * 100, 100)
                        self.window.after(0, lambda p=pct: self.progress.set(p))
                except (ValueError, IndexError):
                    pass
            elif "Duration:" in line and not duration:
                try:
                    dur_str = line.split("Duration:")[1].split(",")[0].strip()
                    h, m, s = dur_str.split(":")
                    duration = float(h) * 3600 + float(m) * 60 + float(s)
                except (ValueError, IndexError):
                    pass
        self.process.wait()

    def on_finish(self):
        self.extract_btn.config(text="提取音频", state="normal")
        self.progress.set(100)

    def on_close(self):
        self.cancelled = True
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.window.destroy()

    def _get_tool_path(self, name):
        local = os.path.join(self._exe_dir(), name)
        if os.path.isfile(local):
            return local
        system = shutil.which(name.replace(".exe", ""))
        return system

    def run(self):
        self.window.mainloop()


def main():
    app = AudioExtractorApp()
    app.run()


if __name__ == "__main__":
    main()
