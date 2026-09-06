"""Content Agent — 유튜브 채널/재생목록 RSS + 컨퍼런스 소스에서 신규 영상을 수집한다.

수집 방식(확정): RSS 피드로 신규 영상을 감지하고, 자막은 yt-dlp 로 추출한다.
YouTube Data API 키는 사용하지 않는다.

  채널   : https://www.youtube.com/feeds/videos.xml?channel_id=<ID>
  재생목록: https://www.youtube.com/feeds/videos.xml?playlist_id=<ID>

RSS 는 제목/URL/게시일만 주고 영상 길이는 주지 않는다. 길이는 prefilter 의
규칙 판정에 필요하므로 yt-dlp 메타데이터 조회로 채운다.
"""

CHANNEL_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={id}"
PLAYLIST_FEED = "https://www.youtube.com/feeds/videos.xml?playlist_id={id}"


def fetch_feed(url: str, source_name: str) -> list[dict]:
    """RSS 피드를 파싱해 영상 목록을 반환한다."""
    raise NotImplementedError


def fetch_metadata(video_url: str) -> dict:
    """yt-dlp 로 길이/설명 등 RSS 에 없는 메타데이터를 채운다."""
    raise NotImplementedError


def collect_new_videos() -> list[dict]:
    """화이트리스트의 전 채널·재생목록을 순회하며 videos.json 에 없는 신규 영상만 반환.

    반환 전에 prefilter.is_talk 로 비발표 콘텐츠를 제거한다.
    """
    raise NotImplementedError


def fetch_transcript(video_url: str) -> tuple[str, str] | None:
    """yt-dlp 로 자동 자막을 받아온다. 반환: (transcript, language). 자막이 없으면 None."""
    raise NotImplementedError
