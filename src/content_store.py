"""data/*.json 읽기/쓰기 유틸. 모든 상태는 레포 안 JSON 파일로 영속화된다."""
import json
from pathlib import Path
from typing import Any


def load(path: Path, default: Any = None) -> Any:
    """JSON 파일을 읽는다. 없으면 default 를 반환한다."""
    raise NotImplementedError


def save(path: Path, payload: Any) -> None:
    """JSON 파일을 UTF-8 / indent=2 로 덮어쓴다."""
    raise NotImplementedError


def next_id(items: list[dict], prefix: str) -> str:
    """`video_001` 같은 순번 ID 를 만든다."""
    raise NotImplementedError
