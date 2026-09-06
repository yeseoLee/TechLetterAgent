"""Content Agent — YouTube Data API 로 화이트리스트 채널·재생목록의 신규 영상을 수집한다.

자막은 쓰지 않는다. GitHub Actions 의 데이터센터 IP 에서 yt-dlp 가 전면 봇 차단되어
자막도 오디오도 받을 수 없기 때문이다(진단 결과는 scripts/diagnose_youtube_access.py).
대신 발표자가 직접 쓴 영상 설명을 분석 입력으로 쓴다. 컨퍼런스 채널은 설명에
세션 초록·발표 대상·목차를 구조화해 넣는 경우가 많아 자동 자막보다 정확하다.

로컬(주거용 IP)에서는 yt-dlp 가 동작하므로 자막 보강 경로를 opt-in 으로 남겨둔다.
"""
import logging

from . import config, content_store, youtube_api

log = logging.getLogger(__name__)

SUBTITLE_LANGS = ["ko", "ko-KR", "en", "en-US"]


def collect_new_videos(per_source: int = 20) -> list[dict]:
    """화이트리스트의 전 채널·재생목록에서 videos.json 에 없는 영상만 반환한다.

    2단계로 나눈다. 목록 조회(playlistItems)로 후보를 모으고, 상세 조회(videos)로
    길이와 전체 설명을 한 번에 채운다. 둘 다 50개당 1 quota unit 이다.
    """
    sources = content_store.load(config.CHANNELS, {})
    known = {v.get("youtube_id") for v in content_store.load(config.VIDEOS, [])}

    feeds = [
        (youtube_api.uploads_playlist_id(c["channel_id"]), c["name"], c.get("language", "ko"))
        for c in sources.get("channels", [])
        if c.get("channel_id") and c["channel_id"] != "REPLACE_ME"
    ] + [
        (p["playlist_id"], p["name"], p.get("language", "ko"))
        for p in sources.get("playlists", [])
        if p.get("playlist_id")
    ]

    seen: set[str] = set()
    fresh: list[dict] = []

    for playlist_id, name, language in feeds:
        try:
            entries = youtube_api.list_playlist_videos(playlist_id, limit=per_source)
        except Exception as exc:  # 소스 하나가 죽어도 나머지는 계속 수집한다.
            log.warning("목록 조회 실패 (%s): %s", name, exc)
            continue

        added = 0
        for entry in entries:
            youtube_id = entry["youtube_id"]
            if youtube_id in known or youtube_id in seen:
                continue
            seen.add(youtube_id)
            entry.update({"source": name, "language": language})
            fresh.append(entry)
            added += 1
        log.info("%s: %d개 조회, 신규 %d개", name, len(entries), added)

    if not fresh:
        log.info("신규 영상 없음")
        return []

    # 길이와 전체 설명을 채운다. 길이는 사전 필터에, 설명은 분석에 쓴다.
    try:
        details = youtube_api.fetch_details([v["youtube_id"] for v in fresh])
    except Exception as exc:
        log.error("상세 조회 실패: %s", exc)
        return []

    enriched = []
    for entry in fresh:
        detail = details.get(entry["youtube_id"])
        if not detail:
            continue
        entry.update(detail)
        enriched.append(entry)

    log.info("신규 영상 %d개 (상세 조회 완료)", len(enriched))
    return enriched


def fetch_transcript(video_url: str) -> tuple[str, str] | None:
    """yt-dlp 로 자동 자막을 받아 평문으로 만든다. 반환: (transcript, language).

    GitHub Actions 에서는 봇 차단으로 항상 실패한다. 로컬 실행에서 분석 품질을
    높이고 싶을 때만 `run_collect --with-transcript` 로 켠다.
    """
    import requests
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except Exception as exc:
        log.info("자막 조회 실패 (%s): %s", video_url, str(exc)[:100])
        return None

    picked = _pick_subtitle_url(info.get("subtitles") or {}, info.get("automatic_captions") or {})
    if not picked:
        return None
    url, language = picked

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        log.info("자막 다운로드 실패: %s", exc)
        return None

    text = _parse_json3(response.text) if "json3" in url else _parse_vtt(response.text)
    return (text, language) if text else None


def _pick_subtitle_url(manual: dict, auto: dict) -> tuple[str, str] | None:
    """수동 자막을 자동 자막보다, 한국어를 영어보다 우선한다."""
    for tracks in (manual, auto):
        for lang in SUBTITLE_LANGS:
            for key in (lang, f"{lang}-orig"):
                for track in tracks.get(key) or []:
                    if track.get("ext") in ("json3", "vtt"):
                        return track["url"], lang.split("-")[0]
    return None


def _parse_json3(raw: str) -> str:
    """유튜브 json3 자막을 평문으로 편다."""
    import json

    try:
        events = json.loads(raw).get("events") or []
    except json.JSONDecodeError:
        return ""
    parts = [seg.get("utf8", "") for e in events for seg in (e.get("segs") or [])]
    return " ".join("".join(parts).split())


def _parse_vtt(raw: str) -> str:
    """WebVTT 에서 타임코드와 태그를 걷어내고 평문만 남긴다."""
    import re

    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or "-->" in line or line.isdigit():
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and (not lines or lines[-1] != line):  # 자동 자막의 중복 행 제거
            lines.append(line)
    return " ".join(" ".join(lines).split())
