"""Content Agent — 유튜브 채널/재생목록 RSS 에서 신규 영상을 수집한다.

수집 방식(확정): RSS 피드로 신규 영상을 감지하고, 메타데이터와 자막은 yt-dlp 로 얻는다.
YouTube Data API 키는 사용하지 않는다.

  채널   : https://www.youtube.com/feeds/videos.xml?channel_id=<ID>
  재생목록: https://www.youtube.com/feeds/videos.xml?playlist_id=<ID>

RSS 는 제목/URL/게시일만 준다. 사전 필터에 필요한 영상 길이와 설명은 yt-dlp 의
메타데이터 조회로 채우는데, 이때 자막 URL 도 같이 나오므로 한 번의 조회로 둘 다 얻는다.
"""
import logging
import random
import time

import feedparser
import requests
import yt_dlp

from . import config, content_store

log = logging.getLogger(__name__)

CHANNEL_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={id}"
PLAYLIST_FEED = "https://www.youtube.com/feeds/videos.xml?playlist_id={id}"

# 자막 언어 선호 순서. 프로필의 language 와 무관하게 원문 자막을 우선한다.
SUBTITLE_LANGS = ["ko", "ko-KR", "en", "en-US"]

_FEED_HEADERS = {"User-Agent": "TechLetterAgent/0.1 (+https://github.com/yeseoLee/TechLetterAgent)"}

# 유튜브 RSS 엔드포인트는 IP 단위로 스로틀링을 걸고, 그때 404/500 을 돌려준다.
# (같은 URL 이 몇 분 전에는 200 이었다가 404 가 되는 식.) 데이터센터 IP 에서 도는
# GitHub Actions 는 더 자주 걸리므로 백오프 재시도로 흡수한다.
FEED_MAX_RETRIES = 4
FEED_RETRY_BASE_SECONDS = 3
FEED_INTERVAL_SECONDS = 1.5

_YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "extract_flat": False,
}


def fetch_feed(url: str, source_name: str) -> list[dict]:
    """RSS 피드를 파싱해 영상 목록을 반환한다. 실패해도 예외를 올리지 않는다.

    feedparser 에 URL 을 직접 넘기지 않고 requests 로 받아서 넘긴다. feedparser 는
    자체 urllib 로 받는데 그 경로가 시스템 인증서 저장소에 의존해 환경을 탄다.
    """
    response = _get_with_retry(url, source_name)
    if response is None:
        return []

    feed = feedparser.parse(response.content)
    if feed.bozo and not feed.entries:
        log.warning("피드 파싱 실패 (%s): %s", source_name, feed.get("bozo_exception"))
        return []

    videos = []
    for entry in feed.entries:
        video_id = entry.get("yt_videoid")
        if not video_id:
            continue
        videos.append({
            "youtube_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": entry.get("title", ""),
            "channel": entry.get("author", source_name),
            "source": source_name,
            "published_at": entry.get("published"),
        })
    return videos


def _get_with_retry(url: str, source_name: str) -> requests.Response | None:
    """스로틀링(404/500)과 네트워크 오류를 백오프로 재시도한다."""
    for attempt in range(FEED_MAX_RETRIES):
        try:
            response = requests.get(url, headers=_FEED_HEADERS, timeout=20)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last = exc
        if attempt < FEED_MAX_RETRIES - 1:
            time.sleep(FEED_RETRY_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 1.5))

    log.warning("피드 요청 실패 (%s, %d회 시도): %s", source_name, FEED_MAX_RETRIES, last)
    return None


def fetch_metadata(video_url: str) -> dict | None:
    """yt-dlp 로 길이·설명·자막 URL 을 가져온다. 미디어는 내려받지 않는다."""
    try:
        with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except Exception as exc:  # yt-dlp 는 다양한 예외를 올린다. 한 영상 실패로 전체를 멈추지 않는다.
        log.warning("메타데이터 조회 실패 (%s): %s", video_url, exc)
        return None

    return {
        "duration_sec": info.get("duration"),
        "description": (info.get("description") or "")[:2000],
        "view_count": info.get("view_count"),
        "upload_date": info.get("upload_date"),
        # 수동 자막을 자동 자막보다 우선한다.
        "_subtitles": info.get("subtitles") or {},
        "_auto_captions": info.get("automatic_captions") or {},
    }


def _pick_subtitle_url(meta: dict) -> tuple[str, str] | None:
    """선호 언어 순으로 자막 트랙을 고른다. 반환: (url, language)."""
    for tracks in (meta.get("_subtitles"), meta.get("_auto_captions")):
        if not tracks:
            continue
        for lang in SUBTITLE_LANGS:
            for key in (lang, f"{lang}-orig"):
                for track in tracks.get(key) or []:
                    if track.get("ext") in ("json3", "vtt"):
                        return track["url"], lang.split("-")[0]
    return None


def fetch_transcript(meta: dict) -> tuple[str, str] | None:
    """fetch_metadata 결과에서 자막을 받아 평문으로 만든다.

    반환: (transcript, language). 자막 트랙이 없거나 내려받기에 실패하면 None.
    """
    picked = _pick_subtitle_url(meta)
    if not picked:
        return None
    url, language = picked

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        log.warning("자막 다운로드 실패: %s", exc)
        return None

    text = _parse_json3(response.text) if "json3" in url else _parse_vtt(response.text)
    return (text, language) if text else None


def _parse_json3(raw: str) -> str:
    """유튜브 json3 자막을 평문으로 편다."""
    import json

    try:
        events = json.loads(raw).get("events") or []
    except json.JSONDecodeError:
        return ""
    parts = [
        seg.get("utf8", "")
        for event in events
        for seg in (event.get("segs") or [])
    ]
    return " ".join("".join(parts).split())


def _parse_vtt(raw: str) -> str:
    """WebVTT 에서 타임코드와 태그를 걷어내고 평문만 남긴다."""
    import re

    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and (not lines or lines[-1] != line):  # 자동 자막의 중복 행 제거
            lines.append(line)
    return " ".join(" ".join(lines).split())


def collect_new_videos() -> list[dict]:
    """화이트리스트의 전 채널·재생목록을 순회하며 videos.json 에 없는 영상만 반환한다.

    메타데이터 조회와 사전 필터는 run_collect 에서 이어서 수행한다.
    """
    sources = content_store.load(config.CHANNELS, {})
    known = {v.get("youtube_id") for v in content_store.load(config.VIDEOS, [])}

    seen: set[str] = set()
    fresh: list[dict] = []

    feeds = [
        (CHANNEL_FEED.format(id=c["channel_id"]), c["name"], c.get("language", "ko"))
        for c in sources.get("channels", [])
        if c.get("channel_id") and c["channel_id"] != "REPLACE_ME"
    ] + [
        (PLAYLIST_FEED.format(id=p["playlist_id"]), p["name"], p.get("language", "ko"))
        for p in sources.get("playlists", [])
        if p.get("playlist_id")
    ]

    for index, (url, name, language) in enumerate(feeds):
        if index:
            time.sleep(FEED_INTERVAL_SECONDS)  # 연속 요청이 스로틀링을 부른다.
        entries = fetch_feed(url, name)
        log.info("%s: %d개 조회", name, len(entries))
        for entry in entries:
            youtube_id = entry["youtube_id"]
            if youtube_id in known or youtube_id in seen:
                continue
            seen.add(youtube_id)
            entry["language"] = language
            fresh.append(entry)

    log.info("신규 영상 %d개", len(fresh))
    return fresh
