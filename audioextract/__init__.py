"""AudioExtract: extract audio from video files and online platforms."""
from .state import store, _cancel, _proc, _cache
from .engine import CODEC_MAP, BITRATE, MOBILE_UA, tool, ensure_ffmpeg, \
    ensure_ytdlp, can_pass_through, get_duration, run_ffmpeg, \
    extract_url, start_job, batch_extract

__all__ = [
    "store", "_cancel", "_proc", "_cache",
    "CODEC_MAP", "BITRATE", "MOBILE_UA",
    "tool", "ensure_ffmpeg", "ensure_ytdlp",
    "can_pass_through", "get_duration", "run_ffmpeg",
    "extract_url", "start_job", "batch_extract",
]
