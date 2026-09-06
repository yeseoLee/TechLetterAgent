"""Cluster Agent — 프로필 임베딩 vs 영상 임베딩 코사인 유사도로 후보 Top-30 추출.

임베딩은 data/embeddings.json 에서 읽는다(embedding_store 참고).
이미 추천했던 영상(recommendations.json 의 video_id)은 후보에서 제외한다.
"""


def profile_text(profile: dict, notes: list[dict]) -> str:
    """프로필 + 누적 메모를 임베딩용 한 덩어리 텍스트로 만든다.

    메모를 함께 넣는 이유는 구조화 필드가 담지 못하는 맥락이 거기 있기 때문이다
    (예: "프론트엔드보다 백엔드가 더 궁금해요").
    """
    raise NotImplementedError


def already_recommended() -> set[str]:
    """recommendations.json 에서 이미 추천한 video_id 집합을 만든다."""
    raise NotImplementedError


def top_candidates(profile: dict, notes: list[dict], videos: list[dict],
                   exclude: set[str], k: int) -> list[dict]:
    """코사인 유사도 상위 k개 영상을 반환한다.

    embedding_store.matrix 로 (id 목록, 행렬)을 받아 numpy 로 한 번에 계산한다.
    임베딩이 없는 영상은 자동으로 후보에서 빠진다.
    """
    raise NotImplementedError
