# 视频提取音频工具

从视频中提取音频的 Windows 桌面工具，支持本地文件、抖音、B站等平台。

## 功能

- **本地文件**：选择视频文件，提取为 MP3/WAV/AAC 等格式
- **在线链接**：粘贴抖音/B站分享链接，自动下载并提取音频
- 支持多格式输出：mp3, wav, aac, m4a, ogg, flac, wma
- 三档音质：低(128k) / 中(192k) / 高(320k)

## 使用方式

### 方式一：直接下载 EXE（推荐）

从 [Releases](../../releases) 下载 `ExtractAudio-GUI.exe`，双击运行。

首次提取在线链接时，程序会自动下载所需组件（ffmpeg ~50MB、yt-dlp ~10MB），之后无需重复下载。

### 方式二：源码运行

```bash
# 安装依赖
pip install requests

# 运行
python extract_audio_gui.py
```

需要系统已安装 [ffmpeg](https://ffmpeg.org/download.html)。

## 打包

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole extract_audio_gui.py
```

## 技术栈

- Python 3 + tkinter（界面）
- ffmpeg（音频转换引擎，自动下载）
- yt-dlp（在线视频下载，自动下载）
- requests（抖音页面解析）

## License

MIT
