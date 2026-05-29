import queue
import tkinter as tk
from tkinter import filedialog

_dialogs: queue.Queue = queue.Queue()
_results: queue.Queue = queue.Queue()
_root = None


def start():
    global _root
    _root = tk.Tk()
    _root.withdraw()

    def check():
        try:
            act = _dialogs.get(timeout=0.1)
            if act == "file":
                p = filedialog.askopenfilename(
                    parent=_root, title="\u9009\u62e9\u89c6\u9891\u6587\u4ef6",
                    filetypes=[("\u89c6\u9891", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.rmvb *.3gp"),
                               ("\u6240\u6709", "*.*")]
                )
                _results.put(p or "")
            elif act == "dir":
                p = filedialog.askdirectory(parent=_root, title="\u9009\u62e9\u4fdd\u5b58\u76ee\u5f55")
                _results.put(p or "")
            elif act == "save":
                p = filedialog.asksaveasfilename(
                    parent=_root, title="\u4fdd\u5b58\u97f3\u9891\u6587\u4ef6",
                    filetypes=[("\u97f3\u9891 (mp3)", "*.mp3"), ("\u97f3\u9891 (wav)", "*.wav"),
                               ("\u97f3\u9891 (aac)", "*.aac"), ("\u97f3\u9891 (m4a)", "*.m4a"),
                               ("\u6240\u6709", "*.*")],
                    defaultextension=".mp3"
                )
                _results.put(p or "")
        except queue.Empty:
            pass
        _root.after(100, check)

    _root.after(100, check)
    _root.mainloop()
