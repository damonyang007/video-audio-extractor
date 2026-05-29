import tkinter as tk
from tkinter import filedialog
import threading
import json

_action = None
_result = ""
_event = threading.Event()


def start():
    root = tk.Tk()
    root.withdraw()

    def check():
        global _action, _result
        if _action:
            act = _action
            _action = None
            if act == "files":
                paths = filedialog.askopenfilenames(
                    parent=root, title="选择文件",
                    filetypes=[("媒体", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.rmvb *.3gp *.mp3 *.wav *.aac *.m4a *.ogg *.flac"),
                               ("所有", "*.*")]
                )
                _result = json.dumps(list(paths)) if paths else "[]"
            elif act == "save":
                p = filedialog.asksaveasfilename(
                    parent=root, title="保存文件",
                    filetypes=[("音频 (mp3)", "*.mp3"), ("音频 (wav)", "*.wav"),
                               ("音频 (aac)", "*.aac"), ("音频 (m4a)", "*.m4a"),
                               ("所有", "*.*")],
                    defaultextension=".mp3"
                )
                _result = p or ""
            elif act == "dir":
                p = filedialog.askdirectory(parent=root, title="选择保存目录")
                _result = p or ""
            _event.set()
        root.after(100, check)

    root.after(100, check)
    root.mainloop()


def request_dialog(action: str) -> str:
    global _action
    _event.clear()
    _action = action
    _event.wait()
    return _result
