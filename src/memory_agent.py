"""Memory Agent — 프로필과 메모의 영속화를 담당한다.

feedback_agent 가 제안한 diff 를 user_profile.json / user_notes.json 에 반영하고,
최초 실행 시 config/seed_profile.json 으로 프로필을 초기화한다.
"""
import logging
from datetime import datetime, timezone

from . import config, content_store

log = logging.getLogger(__name__)

# 프로필에서 피드백으로 갱신 가능한 필드. 이 외의 키는 무시한다.
EDITABLE = ("position", "tech_stack", "interests", "level", "language")
LIST_FIELDS = ("tech_stack", "interests", "language")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def bootstrap_profile() -> dict:
    """data/user_profile.json 이 없으면 config/seed_profile.json 으로 초기화한다."""
    profile = content_store.load(config.USER_PROFILE)
    if profile:
        return profile

    seed = content_store.load(config.SEED_PROFILE, {})
    profile = {
        "position": seed.get("position", ""),
        "tech_stack": list(seed.get("tech_stack") or []),
        "interests": list(seed.get("interests") or []),
        "level": seed.get("level", ""),
        "language": list(seed.get("language") or ["ko"]),
        "updated_at": _now(),
    }
    content_store.save(config.USER_PROFILE, profile)
    log.info("seed_profile.json 으로 프로필을 초기화했습니다")
    return profile


def apply_diff(profile: dict, diff: dict) -> dict:
    """프로필 필드를 갱신한다.

    리스트 필드는 "+항목" / "-항목" 형태의 증분 지시를 받는다. 전체 교체가 아니라
    증분인 이유는, 답장 한 줄("프론트엔드보다 백엔드가 더 궁금해요")로 기존 관심사가
    통째로 날아가면 안 되기 때문이다.
    """
    updated = dict(profile)

    for field, value in (diff or {}).items():
        if field not in EDITABLE or value is None:
            continue

        if field not in LIST_FIELDS:
            updated[field] = str(value)
            continue

        current = list(updated.get(field) or [])
        for item in value if isinstance(value, list) else [value]:
            item = str(item).strip()
            if item.startswith("-"):
                target = item[1:].strip()
                current = [c for c in current if c != target]
            else:
                target = item[1:].strip() if item.startswith("+") else item
                if target and target not in current:
                    current.append(target)
        updated[field] = current

    updated["updated_at"] = _now()
    return updated


def add_note(notes: list[dict], text: str, recommendation_id: str | None = None) -> list[dict]:
    """답장 원문을 메모 이력에 누적한다. 구조화 필드가 담지 못하는 맥락을 보존한다."""
    notes = list(notes)
    notes.append({
        "id": content_store.next_id(notes, "note"),
        "text": text.strip(),
        "source_recommendation_id": recommendation_id,
        "created_at": _now(),
    })
    return notes
