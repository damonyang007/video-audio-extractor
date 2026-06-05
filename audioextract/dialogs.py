"""File dialog bridge using tkinter in a dedicated system thread."""

import tkinter as tk
from tkinter import filedialog
import threading
import json

_result = None
_done = threading.Event()


def _dialog_thread(action: str):
    global _result
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    root.update()
    root.attributes('-topmost', False)

    if action == "files":
        paths = filedialog.askopenfilenames(
            parent=root, title="选择文件",
            filetypes=[("媒体", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.rmvb *.3gp *.mp3 *.wav *.aac *.m4a *.ogg *.flac"),
                       ("所有", "*.*")]
        )
        _result = json.dumps(list(paths)) if paths else "[]"
    elif action == "save":
        p = filedialog.asksaveasfilename(
            parent=root, title="保存文件",
            defaultextension=".mp3",
            filetypes=[("MP3", "*.mp3"), ("WAV", "*.wav"), ("所有", "*.*")]
        )
        _result = p or ""
    elif action == "dir":
        p = filedialog.askdirectory(parent=root, title="选择保存目录")
        _result = p or ""

    root.destroy()
    _done.set()


def request_dialog(action: str) -> str:
    global _result, _done
    _result = None
    _done.clear()

    thread = threading.Thread(target=_dialog_thread, args=(action,), daemon=True)
    thread.start()
    _done.wait(timeout=300)

    return _result if _result is not None else "[]" if action == "files" else ""
