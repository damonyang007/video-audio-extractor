"""Bilibili video parser: resolve BV/av IDs to direct audio stream URLs."""

import re
from typing import Optional, Tuple

try:
    import requests as req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def resolve(url: str) -> Tuple[Optional[str], str]:
    """Resolve a Bilibili video URL to a direct audio stream URL + title.
    Uses the public Bilibili API without authentication."""
    if not HAS_REQUESTS:
        return None, ""

    bvid_match = re.search(r'(BV[a-zA-Z0-9]{8,12})|(av\d+)', url)
    if not bvid_match:
        return None, ""

    bvid = bvid_match.group(0)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/",
    }

    try:
        # Step 1: Get video info (cid + title)
        r = req.get(
            f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
            headers=headers, timeout=10
        )
        data = r.json()
        if data.get("code") != 0:
            return None, ""
        cid = data["data"]["cid"]
        title = data["data"]["title"]

        # Step 2: Get play URLs (dash format for audio-only streams)
        r2 = req.get(
            f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=16&qn=0",
            headers=headers, timeout=10
        )
        dash = r2.json()
        audio_streams = (dash.get("data") or {}).get("dash") or {}
        audios = audio_streams.get("audio", [])

        if not audios:
            return None, title

        # Pick highest quality audio stream
        best = max(audios, key=lambda a: a.get("bandwidth", 0))
        audio_url = best.get("base_url", "")
        if not audio_url:
            return None, title

        return audio_url, title

    except Exception:
        return None, ""
