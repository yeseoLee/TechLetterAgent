"""Memory Agent — feedback_agent 의 제안을 user_profile.json / user_notes.json 에 반영한다."""


def apply_feedback(profile: dict, notes: list[dict], parsed: dict) -> tuple[dict, list[dict]]:
    """프로필 필드를 갱신하고 원문 맥락을 메모 이력에 누적한다."""
    raise NotImplementedError


def bootstrap_profile_if_needed() -> dict:
    """data/user_profile.json 이 없으면 config/seed_profile.json 으로 초기화한다."""
    raise NotImplementedError
