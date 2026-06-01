# AudioExtract

从视频中提取音频的 Windows 桌面工具。双击即用，自动打开浏览器。

支持本地文件、抖音直链解析、B站/YouTube 等平台。

## 功能

- **本地文件** — 多选视频，批量提取为 MP3/WAV/AAC/FLAC
- **在线链接** — 粘贴分享链接，支持抖音/B站/YouTube
- **音频裁剪** — 可视化选择起止时间，只提取片段
- **格式转换** — 纯音频格式互转
- **三档音质** — 低 128k / 中 192k / 高 320k
- **暗色/亮色主题** — 一键切换
- **历史记录** — 最近提取列表，点击打开文件夹

## 快速开始

### 下载使用

从 [Releases](https://github.com/damonyang007/video-audio-extractor/releases) 下载 `AudioExtract.zip`，解压后双击 `AudioExtract.bat` 或 `AudioExtract/AudioExtract.exe`。

首次使用自动下载 ffmpeg (~50MB) 和 yt-dlp (~10MB)。

### 源码运行

```bash
pip install -r requirements.txt
python app.py
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | HTML5 + CSS3 + Alpine.js 3.x |
| 后端 | Python Flask + Server-Sent Events |
| 引擎 | ffmpeg + yt-dlp |
| 打包 | PyInstaller (onedir) |

## 项目结构

```
video-audio-extractor/
├── app.py                    # Flask entry point
├── audioextract/             # Backend package
│   ├── __init__.py
│   ├── state.py              # Shared state
│   ├── engine.py             # ffmpeg/yt-dlp engine
│   ├── douyin.py             # Douyin parser
│   ├── bilibili.py           # Bilibili parser
│   ├── youtube.py            # YouTube parser
│   ├── history.py            # History persistence
│   ├── config.py             # Preferences
│   └── dialogs.py            # Native file dialogs
├── templates/
│   ├── index.html            # Layout shell
│   └── partials/             # UI components (10 files)
├── static/
│   ├── css/style.css
│   └── js/
│       ├── store.js          # Alpine store + SSE
│       ├── app.js            # Alpine component
│       └── utils.js          # Helpers
├── tests/                    # pytest tests
├── .github/workflows/        # CI/CD
├── requirements.txt
├── pyproject.toml
├── LICENSE                   # MIT
├── CHANGELOG.md
└── CONTRIBUTING.md
```

## 构建

```bash
pip install pyinstaller
pyinstaller --onedir --noconsole --name AudioExtract \
  --add-data "templates;templates" \
  --add-data "static;static" \
  app.py
```

## License

MIT
