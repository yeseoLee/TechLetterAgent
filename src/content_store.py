"""data/*.json 읽기/쓰기 유틸. 모든 상태는 레포 안 JSON 파일로 영속화된다."""
import json
import re
from pathlib import Path
from typing import Any

_ID = re.compile(r"_(\d+)$")


def load(path: Path, default: Any = None) -> Any:
    """JSON 파일을 읽는다. 파일이 없거나 비어 있으면 default 를 반환한다."""
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return default
    return json.loads(text)


def save(path: Path, payload: Any) -> None:
    """JSON 파일을 UTF-8 / indent=2 로 덮어쓴다.

    git diff 를 읽을 수 있게 유지하려고 ensure_ascii 를 끄고 개행으로 끝낸다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def next_id(items: list[dict], prefix: str) -> str:
    """`video_001` 같은 순번 ID 를 만든다. 기존 최대 번호 + 1."""
    highest = 0
    for item in items:
        if match := _ID.search(str(item.get("id", ""))):
            highest = max(highest, int(match.group(1)))
    return f"{prefix}_{highest + 1:03d}"
