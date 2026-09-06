"""Content Agent — YouTube Data API 로 화이트리스트 채널·재생목록의 신규 영상을 수집한다.

분석 입력은 발표자가 직접 쓴 영상 설명이고, 자막을 받을 수 있으면 앞부분을 함께 쓴다.
GitHub Actions 의 데이터센터 IP 에서는 자막이 RequestBlocked 로 막히므로(실측)
그 경우 설명만으로 진행한다. 로컬(주거용 IP)에서는 자막이 정상적으로 붙는다.
"""
import logging

from . import config, content_store, youtube_api

log = logging.getLogger(__name__)

SUBTITLE_LANGS = ("ko", "en")

# 자막이 IP 차단된 실행에서 영상마다 재시도하지 않도록 하는 플래그.
_transcripts_blocked = False


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


def fetch_transcript(youtube_id: str, max_seconds: int = config.TRANSCRIPT_SECONDS
                     ) -> tuple[str, str] | None:
    """자막 앞부분을 받아 평문으로 만든다. 반환: (transcript, language_code).

    발표는 도입부에 주제·대상·목차가 몰려 있어서 앞 몇 분이면 무엇을 다루는지
    판단하기에 충분하다. 전체를 넣으면 프롬프트만 커지고 요약 품질은 흔들린다.

    GitHub Actions 의 데이터센터 IP 에서는 RequestBlocked 로 막힌다(실측).
    막히면 None 을 돌려주고 호출부가 설명만으로 진행한다. config 에 프록시가
    설정돼 있으면 그쪽으로 우회한다.
    """
    global _transcripts_blocked
    if _transcripts_blocked:
        return None

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            CouldNotRetrieveTranscript, RequestBlocked,
        )
    except ImportError:
        log.warning("youtube-transcript-api 가 설치돼 있지 않습니다")
        _transcripts_blocked = True
        return None

    try:
        fetched = _api().fetch(youtube_id, languages=SUBTITLE_LANGS)
    except RequestBlocked:
        # 한 번 막히면 남은 영상도 전부 막힌다. 매번 재시도하지 않는다.
        _transcripts_blocked = True
        log.info("자막 접근이 차단되어(IP 제한) 이번 실행에서는 설명만 사용합니다")
        return None
    except CouldNotRetrieveTranscript as exc:
        log.info("자막 없음 (%s): %s", youtube_id, type(exc).__name__)
        return None
    except Exception as exc:
        log.warning("자막 조회 실패 (%s): %s", youtube_id, str(exc)[:120])
        return None

    head_text = " ".join(
        snippet.text.strip()
        for snippet in fetched.snippets
        if snippet.start < max_seconds and snippet.text.strip()
    )
    text = " ".join(head_text.split())
    if not text:
        return None

    log.info("자막 %s %d자 (앞 %d초)", fetched.language_code, len(text), max_seconds)
    return text, fetched.language_code


def reset_transcript_state() -> None:
    """차단 플래그를 되돌린다. 테스트에서 쓴다."""
    global _transcripts_blocked
    _transcripts_blocked = False


def _api():
    """프록시가 설정돼 있으면 그쪽으로 우회하는 클라이언트를 만든다.

    Actions 에서 자막을 쓰려면 주거용 프록시가 필요하다. 설정하지 않으면
    프록시 없이 동작하고, 차단되면 설명만으로 진행한다.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    if config.PROXY_URL:
        from youtube_transcript_api.proxies import GenericProxyConfig

        return YouTubeTranscriptApi(proxy_config=GenericProxyConfig(
            http_url=config.PROXY_URL, https_url=config.PROXY_URL))

    if config.WEBSHARE_PROXY_USERNAME and config.WEBSHARE_PROXY_PASSWORD:
        from youtube_transcript_api.proxies import WebshareProxyConfig

        return YouTubeTranscriptApi(proxy_config=WebshareProxyConfig(
            proxy_username=config.WEBSHARE_PROXY_USERNAME,
            proxy_password=config.WEBSHARE_PROXY_PASSWORD))

    return YouTubeTranscriptApi()
