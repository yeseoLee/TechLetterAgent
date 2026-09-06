"""Cluster Agent — 프로필 임베딩 vs 영상 임베딩 코사인 유사도로 후보 Top-30 추출.

이미 추천했던 영상(recommendations.json 의 video_id)은 후보에서 제외한다.
"""


def profile_text(profile: dict, notes: list[dict]) -> str:
    """프로필 + 최근 메모를 임베딩용 한 덩어리 텍스트로 만든다."""
    raise NotImplementedError


def top_candidates(profile: dict, notes: list[dict], videos: list[dict],
                   already_sent: set[str], k: int) -> list[dict]:
    """numpy 코사인 유사도로 상위 k개 영상을 반환."""
    raise NotImplementedError
