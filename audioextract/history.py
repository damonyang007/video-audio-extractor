import os
import json
from pathlib import Path
from datetime import datetime


def _dir() -> Path:
    p = Path(os.environ.get("APPDATA", str(Path.home()))) / "audioextract"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_path() -> Path:
    return _dir() / "config.json"


def history_path() -> Path:
    return _dir() / "history.json"


def load() -> list:
    try:
        if history_path().is_file():
            return json.loads(history_path().read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save(entries: list):
    try:
        history_path().write_text(
            json.dumps(entries[-50:], ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def delete_at(index: int):
    h = load()
    if 0 <= index < len(h):
        h.pop(index)
        save(h)


def add(source: str, kind: str, output: str):
    h = load()
    h.insert(0, {
        "source": Path(source).name if kind == "file" else source[:60],
        "kind": kind,
        "output": output,
        "time": datetime.now().strftime("%m-%d %H:%M")
    })
    save(h)
