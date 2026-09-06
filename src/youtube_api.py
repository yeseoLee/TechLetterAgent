"""YouTube Data API v3 클라이언트.

RSS + yt-dlp 스크래핑에서 공식 API 로 옮긴 이유: GitHub Actions 의 데이터센터
IP 에서 yt-dlp 는 전면 봇 차단("Sign in to confirm you're not a bot")되고,
RSS 는 404 로 스로틀링된다(재생목록 피드는 재시도해도 복구 불가). 공식 API 는
IP 제한 없이 동작하고 무료 quota 10,000 units/일로 이 용도에는 충분하다.

quota 소모: playlistItems.list 1 unit, videos.list 1 unit (각각 50개까지).
소스 8개 기준 하루 20 units 내외.
"""
import logging
import re

import requests

from . import config

log = logging.getLogger(__name__)

BASE = "https://www.googleapis.com/youtube/v3"
PAGE_SIZE = 50

# PT1H2M3S 형태의 ISO 8601 duration.
_DURATION = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def _get(endpoint: str, params: dict) -> dict:
    if not config.YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY 가 설정되지 않았습니다.")
    response = requests.get(
        f"{BASE}/{endpoint}", params={**params, "key": config.YOUTUBE_API_KEY}, timeout=20
    )
    if response.status_code == 403:
        # quota 초과와 키 오류가 둘 다 403 이라 본문을 그대로 올린다.
        raise RuntimeError(f"YouTube API 403: {response.text[:300]}")
    response.raise_for_status()
    return response.json()


def parse_duration(iso: str | None) -> int | None:
    """ISO 8601 duration 을 초로 바꾼다."""
    if not iso or not (m := _DURATION.fullmatch(iso)):
        return None
    hours, minutes, seconds = (int(g or 0) for g in m.groups())
    return hours * 3600 + minutes * 60 + seconds


def uploads_playlist_id(channel_id: str) -> str:
    """채널의 업로드 재생목록 ID. UC... → UU... 로 접두사만 바뀐다."""
    return "UU" + channel_id[2:]


def list_playlist_videos(playlist_id: str, limit: int = PAGE_SIZE) -> list[dict]:
    """재생목록의 최근 영상 목록. 반환 항목은 youtube_id / title / published_at."""
    items: list[dict] = []
    page_token = None

    while len(items) < limit:
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": min(PAGE_SIZE, limit - len(items)),
        }
        if page_token:
            params["pageToken"] = page_token

        payload = _get("playlistItems", params)
        for item in payload.get("items", []):
            snippet = item.get("snippet") or {}
            video_id = (snippet.get("resourceId") or {}).get("videoId")
            if not video_id:
                continue
            items.append({
                "youtube_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": snippet.get("title", ""),
                "channel": snippet.get("videoOwnerChannelTitle") or snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt"),
            })

        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return items


def fetch_details(youtube_ids: list[str]) -> dict[str, dict]:
    """영상 상세(길이·전체 설명·태그·조회수)를 한 번에 가져온다. 50개씩 묶어 호출."""
    details: dict[str, dict] = {}

    for start in range(0, len(youtube_ids), PAGE_SIZE):
        chunk = youtube_ids[start:start + PAGE_SIZE]
        payload = _get("videos", {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(chunk),
        })
        for item in payload.get("items", []):
            snippet = item.get("snippet") or {}
            details[item["id"]] = {
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "description": snippet.get("description", ""),
                "tags": (snippet.get("tags") or [])[:15],
                "published_at": snippet.get("publishedAt"),
                "duration_sec": parse_duration((item.get("contentDetails") or {}).get("duration")),
                "view_count": int((item.get("statistics") or {}).get("viewCount", 0)),
            }

    missing = set(youtube_ids) - set(details)
    if missing:
        log.warning("상세 조회 누락 %d건 (비공개/삭제 추정)", len(missing))
    return details
