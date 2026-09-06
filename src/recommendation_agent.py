"""Recommendation Agent — Top-30 후보를 Sonnet 5 로 재검토해 강추 3 + 혹시나 2 를 확정한다.

0~100 스코어링은 쓰지 않는다. LLM 에게 개수를 직접 지정해 정확히 5개 구조로 받는다.
프로필 구조화 필드와 누적 메모를 함께 넣어 종합 판단하게 한다(메모가 우선 참고자료).
"""


def recommend(profile: dict, notes: list[dict], candidates: list[dict]) -> list[dict]:
    """반환: [{video_id, tier: "strong"|"maybe", reason_text}, ...] 정확히 5개."""
    raise NotImplementedError
