from typing import Optional, Tuple


def resolve(url: str) -> Tuple[Optional[str], str]:
    """Resolve Bilibili video to direct stream + title.
    Currently delegated to yt-dlp in app.py (no custom parser needed).
    Future: implement BV/av API for quality selection, subtitle extraction."""
    return None, ""
