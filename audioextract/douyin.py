import re
from typing import Optional, Tuple

try:
    import requests as req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from .engine import MOBILE_UA


def resolve(url: str) -> Tuple[Optional[str], str]:
    if not HAS_REQUESTS:
        return None, ""
    s = req.Session()
    s.headers.update({"User-Agent": MOBILE_UA, "Accept": "text/html,application/xhtml+xml"})
    try:
        s.get("https://www.douyin.com", timeout=10)
        r = s.get(url, timeout=15)
    except Exception:
        return None, ""
    html = r.text
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        title = m.group(1).strip()
    vid = re.search(r"video_id=([a-zA-Z0-9]+)", html)
    if vid:
        return f"https://aweme.snssdk.com/aweme/v1/playwm/?video_id={vid.group(1)}", title or "video"
    return None, title
