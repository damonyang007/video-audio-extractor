import tkinter as tk
from tkinter import filedialog
import threading

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
            if act == "file":
                p = filedialog.askopenfilename(
                    parent=root, title="\u9009\u62e9\u89c6\u9891\u6587\u4ef6",
                    filetypes=[("\u89c6\u9891", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.rmvb *.3gp"),
                               ("\u6240\u6709", "*.*")]
                )
                _result = p or ""
            elif act == "dir":
                p = filedialog.askdirectory(parent=root, title="\u9009\u62e9\u4fdd\u5b58\u76ee\u5f55")
                _result = p or ""
            elif act == "save":
                p = filedialog.asksaveasfilename(
                    parent=root, title="\u4fdd\u5b58\u97f3\u9891\u6587\u4ef6",
                    filetypes=[("\u97f3\u9891 (mp3)", "*.mp3"), ("\u97f3\u9891 (wav)", "*.wav"),
                               ("\u97f3\u9891 (aac)", "*.aac"), ("\u97f3\u9891 (m4a)", "*.m4a"),
                               ("\u6240\u6709", "*.*")],
                    defaultextension=".mp3"
                )
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
