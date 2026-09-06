"""임베딩 저장소 — data/embeddings.json 에 video_id → base64 로 보관한다.

videos.json 에 인라인으로 넣으면 임베딩이 파일의 99%를 차지한다(1건당 임베딩
90KB, 나머지 1.2KB). 매 실행마다 파일 전체를 다시 커밋하는 구조라 git 히스토리가
실행 횟수만큼 누적된다. 그래서 두 가지를 한다.

  1. 별도 파일로 분리 — videos.json 이 1.2KB/건으로 가벼워져 git diff 로 실제
     내용 변화를 읽을 수 있다.
  2. float32 base64 인코딩 — JSON 실수 배열의 24% 크기다. float64 를 float32 로
     낮추지만 코사인 유사도 계산에는 영향이 없는 수준이다.
"""
import base64
import struct

import numpy as np

from . import config, content_store


def encode(vector: list[float] | np.ndarray) -> str:
    """실수 벡터를 float32 리틀엔디언 base64 문자열로 만든다."""
    values = [float(x) for x in vector]
    return base64.b64encode(struct.pack(f"<{len(values)}f", *values)).decode("ascii")


def decode(encoded: str) -> np.ndarray:
    """base64 문자열을 float32 numpy 배열로 되돌린다."""
    return np.frombuffer(base64.b64decode(encoded), dtype="<f4")


def load_all() -> dict[str, str]:
    """{video_id: base64} 전체를 읽는다."""
    return content_store.load(config.EMBEDDINGS, {}) or {}


def save_all(store: dict[str, str]) -> None:
    content_store.save(config.EMBEDDINGS, store)


def matrix(video_ids: list[str], store: dict[str, str] | None = None) -> tuple[list[str], np.ndarray]:
    """주어진 id 중 임베딩이 있는 것만 모아 행렬로 만든다.

    반환: (실제로 임베딩이 있던 id 목록, shape (n, dim) 행렬).
    id 목록과 행렬의 행 순서는 일치한다.
    """
    store = load_all() if store is None else store
    found = [vid for vid in video_ids if vid in store]
    if not found:
        return [], np.zeros((0, 0), dtype="float32")
    return found, np.vstack([decode(store[vid]) for vid in found])
