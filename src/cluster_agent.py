"""Cluster Agent — 프로필 임베딩 vs 영상 임베딩 코사인 유사도로 후보 Top-K 추출.

임베딩은 data/embeddings.json 에서 읽는다(embedding_store 참고).
이미 추천했던 영상은 후보에서 제외한다.
"""
import logging
import re

import numpy as np

from . import article_analyzer, config, content_store, embedding_store

log = logging.getLogger(__name__)

# 프로필 임베딩에 넣을 최근 메모 수. 오래된 메모까지 다 넣으면 최신 취향이 묻힌다.
RECENT_NOTES = 10

# 제목 정규화용. 같은 발표가 다른 영상 ID 로 올라오는 경우가 있어
# (채널 중복 업로드, 재업로드) 제목으로 한 번 더 거른다.
_NORMALIZE_TITLE = re.compile(r"[\s\-_·•|/\[\]()#!?.,:;\"'~]+")


def profile_text(profile: dict, notes: list[dict]) -> str:
    """프로필 + 최근 메모를 임베딩용 한 덩어리 텍스트로 만든다.

    메모를 함께 넣는 이유는 구조화 필드가 담지 못하는 맥락이 거기 있기 때문이다
    (예: "프론트엔드보다 백엔드가 더 궁금해요").
    """
    parts = [
        f"포지션: {profile.get('position', '')}",
        f"기술 스택: {', '.join(profile.get('tech_stack') or [])}",
        f"관심 주제: {', '.join(profile.get('interests') or [])}",
        f"연차: {profile.get('level', '')}",
    ]
    if recent := [n.get("text", "") for n in notes[-RECENT_NOTES:] if n.get("text")]:
        parts.append("추가 관심사와 피드백: " + " / ".join(recent))
    return "\n".join(parts)


def already_recommended() -> set[str]:
    """recommendations.json 에서 이미 추천한 video_id 집합을 만든다."""
    history = content_store.load(config.RECOMMENDATIONS, []) or []
    return {r["video_id"] for r in history if r.get("video_id")}


def normalize_title(title: str) -> str:
    """공백·기호·이모지를 걷어내고 비교용 키를 만든다."""
    return _NORMALIZE_TITLE.sub("", (title or "").lower())


def _dedupe_by_title(candidates: list[dict], seen_titles: set[str]) -> list[dict]:
    """같은 발표가 다른 영상 ID 로 중복 추천되는 것을 막는다.

    유사도 순으로 들어오므로 먼저 오는 쪽(더 잘 맞는 쪽)을 남긴다.
    """
    unique = []
    for video in candidates:
        key = normalize_title(video.get("title", ""))
        if not key or key in seen_titles:
            log.info("제목 중복 제외: %s", video.get("title", "")[:50])
            continue
        seen_titles.add(key)
        unique.append(video)
    return unique


def top_candidates(profile: dict, notes: list[dict], videos: list[dict],
                   exclude: set[str] | None = None,
                   k: int = config.TOP_K_CANDIDATES) -> list[dict]:
    """코사인 유사도 상위 k개 영상을 반환한다.

    각 영상 딕셔너리에 `similarity` 를 채워서 돌려준다. 임베딩이 없는 영상은
    embedding_store.matrix 단계에서 자동으로 빠진다.
    """
    exclude = exclude or set()
    pool = {v["id"]: v for v in videos if v.get("id") and v["id"] not in exclude}
    if not pool:
        log.info("후보 없음 (전체 %d개, 기추천 제외 후 0개)", len(videos))
        return []

    found_ids, embeddings = embedding_store.matrix(list(pool))
    if not found_ids:
        log.warning("임베딩이 있는 영상이 없습니다")
        return []

    query = np.asarray(article_analyzer.embed(profile_text(profile, notes)), dtype="float32")
    scores = _cosine(query, embeddings)

    ranked = sorted(zip(found_ids, scores), key=lambda pair: pair[1], reverse=True)
    scored = [{**pool[vid], "similarity": round(float(score), 4)} for vid, score in ranked]

    # 이미 추천한 영상과 제목이 같은 것도 제외한다. video_id 만으로는 같은 발표의
    # 재업로드를 걸러내지 못한다.
    all_videos = {v["id"]: v for v in videos}
    seen_titles = {normalize_title(all_videos[vid].get("title", ""))
                   for vid in exclude if vid in all_videos}
    top = _dedupe_by_title(scored, seen_titles)[:k]

    log.info("후보 %d개 중 상위 %d개 추출 (유사도 %.3f ~ %.3f)",
             len(found_ids), len(top), top[-1]["similarity"], top[0]["similarity"])
    return top


def _cosine(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """쿼리 벡터와 행렬 각 행 사이의 코사인 유사도."""
    query_norm = np.linalg.norm(query)
    row_norms = np.linalg.norm(matrix, axis=1)
    # 0 벡터가 섞여도 0으로 나누지 않게 한다.
    denominator = np.where(row_norms == 0, 1.0, row_norms) * (query_norm or 1.0)
    return (matrix @ query) / denominator
