"""Content Agent — 유튜브 채널 RSS + 컨퍼런스 소스에서 신규 영상/소식을 수집한다.

수집 방식(확정): 채널 RSS 피드로 신규 영상을 감지하고, 자막은 yt-dlp 로 추출한다.
YouTube Data API 키는 사용하지 않는다.
"""


def fetch_channel_feed(channel_id: str) -> list[dict]:
    """https://www.youtube.com/feeds/videos.xml?channel_id=... 를 파싱해 최근 영상 목록 반환."""
    raise NotImplementedError


def collect_new_videos() -> list[dict]:
    """화이트리스트 전 채널을 순회하며 videos.json 에 없는 신규 영상만 반환."""
    raise NotImplementedError


def fetch_transcript(video_url: str) -> tuple[str, str] | None:
    """yt-dlp 로 자동 자막을 받아온다. 반환: (transcript, language). 자막이 없으면 None."""
    raise NotImplementedError
