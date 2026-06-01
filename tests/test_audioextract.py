import pytest
import re
import json
from pathlib import Path
from audioextract.engine import extract_url, CODEC_MAP, BITRATE, MOBILE_UA
from audioextract.history import load, save, add, history_path
from audioextract.config import load as config_load, save as config_save
from audioextract import store


class TestEngine:
    def test_extract_url_basic(self):
        assert extract_url("https://v.douyin.com/abc/") == "https://v.douyin.com/abc/"
        assert extract_url("text https://bilibili.com/video/BV123 more") == "https://bilibili.com/video/BV123"
        assert extract_url("no url here") is None
        assert extract_url("复制文字 https://youtu.be/abc 直接看") == "https://youtu.be/abc"

    def test_codec_map(self):
        assert CODEC_MAP["mp3"] == "libmp3lame"
        assert CODEC_MAP["wav"] == "pcm_s16le"
        assert CODEC_MAP["flac"] == "flac"

    def test_bitrate_map(self):
        assert BITRATE["low"] == "128k"
        assert BITRATE["medium"] == "192k"
        assert BITRATE["high"] == "320k"

    def test_mobile_ua(self):
        assert "iPhone" in MOBILE_UA
        assert "AppleWebKit" in MOBILE_UA


class TestHistory:
    def test_history_cycle(self, tmp_path):
        import os
        os.environ["APPDATA"] = str(tmp_path)
        # reload module-level path
        import audioextract.history as hist
        entries = load()
        assert entries == []

        add("/test/video.mp4", "file", "/test/video.mp3")
        entries = load()
        assert len(entries) == 1
        assert entries[0]["kind"] == "file"
        assert entries[0]["source"] == "video.mp4"

        add("https://example.com/v/123", "url", "/test/audio.mp3")
        entries = load()
        assert len(entries) == 2
        assert entries[0]["kind"] == "url"

        save([])
        assert load() == []


class TestConfig:
    def test_config_cycle(self, tmp_path):
        import os
        os.environ["APPDATA"] = str(tmp_path)
        data = {"fmt": "wav", "qual": "high", "dir": "C:/out"}
        config_save(data)
        loaded = config_load()
        assert loaded["fmt"] == "wav"
        assert loaded["qual"] == "high"


class TestStore:
    def test_store_defaults(self):
        assert store["pct"] == 0
        assert store["done"] is False
        assert store["file_i"] == 0
        assert store["file_n"] == 0
        assert store["done_seq"] == 0


class TestDouyin:
    def test_video_id_regex(self):
        html = 'video_id=v0300fg10000d6ol487og65uk476vf20'
        m = re.search(r"video_id=([a-zA-Z0-9]+)", html)
        assert m is not None
        assert m.group(1) == "v0300fg10000d6ol487og65uk476vf20"
