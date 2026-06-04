"""YouTube video parser: extract audio streams from video page HTML."""

import re
import json
import urllib.parse
from typing import Optional, Tuple

try:
    import requests as req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def resolve(url: str) -> Tuple[Optional[str], str]:
    """Resolve a YouTube video URL to a direct audio stream URL + title.
    Parses ytInitialPlayerResponse from the watch page HTML."""
    if not HAS_REQUESTS:
        return None, ""

    video_id = _extract_video_id(url)
    if not video_id:
        return None, ""

    try:
        html = req.get(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=15
        ).text

        # Extract ytInitialPlayerResponse JSON
        m = re.search(r"ytInitialPlayerResponse\s*=\s*({.+?});\s*var\s+", html, re.DOTALL)
        if not m:
            m = re.search(r"ytInitialPlayerResponse\s*=\s*({.+?});</script>", html, re.DOTALL)
        if not m:
            return None, ""

        player = json.loads(m.group(1))
        details = player.get("videoDetails", {})
        title = details.get("title", "")

        # Get adaptive formats and pick best audio
        formats = player.get("streamingData", {}).get("adaptiveFormats", [])
        audio_formats = [f for f in formats if "audio" in (f.get("mimeType", ""))]
        if not audio_formats:
            return None, title

        best = max(audio_formats, key=lambda f: int(f.get("bitrate", 0)))
        audio_url = best.get("url", "")
        if not audio_url:
            # Try cipher/signatureCipher
            cipher = best.get("signatureCipher") or best.get("cipher", "")
            if cipher:
                params = dict(urllib.parse.parse_qsl(cipher))
                audio_url = params.get("url", "")
                if "s" in params:
                    audio_url += "&sig=" + params["s"]

        return audio_url or None, title

    except Exception:
        return None, ""


def _extract_video_id(url: str) -> Optional[str]:
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None
