# AudioExtract — 视频提取音频工具

从视频中提取音频的桌面工具，支持本地文件和在线链接（抖音、B站）。

**Web 前端 + Python 后端，双击即用，自动打开浏览器。**

## 功能

- **本地文件**：选择视频文件，提取为 MP3/WAV/AAC/FLAC 等格式
- **在线链接**：粘贴抖音/B站分享链接，自动下载并提取音频
- 三档音质：低(128k) / 中(192k) / 高(320k)
- 抖音直链解析，无需登录/Cookie
- 实时进度显示

## 快速开始

### 方式一：下载 EXE（推荐）

从 [Releases](../../releases) 下载 `AudioExtract.exe`，双击运行。

首次使用自动下载 ffmpeg (~50MB) 和 yt-dlp (~10MB)，之后即开即用。

### 方式二：源码运行

```bash
pip install flask requests
python app.py
```

## 技术栈

- **前端**：HTML5 + CSS3 + JavaScript（现代暗色 UI，抖音风格）
- **后端**：Python Flask + Server-Sent Events（实时进度）
- **引擎**：ffmpeg（音频转换）+ yt-dlp（在线下载）

## 构建

```bash
pip install pyinstaller flask requests
pyinstaller --onefile --noconsole --name AudioExtract --add-data "templates;templates" app.py
```

## License

MIT
