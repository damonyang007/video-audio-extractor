# AudioExtract

从视频中提取音频的 Windows 桌面工具。双击即用，自动打开浏览器。

支持本地文件、抖音直链解析、B站/YouTube 等平台。

## 功能

### 本地文件
- 多选 + 拖拽添加视频文件，批量提取
- 视频预览播放器 + 可视化裁剪（设为起始/结束 + 预览片段）
- 8 种输出格式：mp3 / wav / aac / m4a / m4r / ogg / flac
- 三档音质：低 128k / 中 192k / 高 320k
- 音频效果器：速度调节(0.5~2x)、淡入淡出、低音增强
- EBU R128 音量归一化
- 可选下载完整视频（非仅音频）

### 在线链接
- 支持抖音直链解析（无需 Cookie）+ B站/YouTube（API + yt-dlp 双通道）
- 单链接 / 批量链接（多行文本框，每行一个）
- 播放列表 / 合集下载
- 同步下载字幕（SRT 格式）
- B站原生 API 解析，自动选最高音质

### 格式转换
- 纯音频文件格式互转（mp3 ↔ wav ↔ aac ↔ flac 等）
- 支持所有音频效果器

### 交互
- 暗色 / 亮色主题，手动切换 + 跟随系统
- `?` 键快捷键面板，Ctrl+1/2/3 切换标签
- 首次使用 3 步引导
- 历史记录（重提 + 单条删除）
- 格式预设（保存 / 加载常用组合）
- 提取后内嵌播放音频
- 系统通知 + 浏览器标签页进度百分比
- 实时预估剩余时间 (ETA)

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
│   └── partials/             # UI components + shared macro
│       └── macro-fmt.html     # Format option list (shared)
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
