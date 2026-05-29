# Shared state accessed by engine and routes

store = {"pct": 0, "status": "\u5f85\u547d", "output": "", "done": False,
         "file_i": 0, "file_n": 0}

_cancel = False
_proc = None
_cache = {}
