"""Feedback Agent — 답장을 읽어 프로필 diff 와 메모를 만든다.

두 종류의 답장을 모두 처리한다.
  1. 정형 — 뉴스레터의 👍/👎 링크로 온 것. 제목이 "[TLA] like rec_004".
     LLM 없이 제목만 파싱한다.
  2. 자유 텍스트 — "프론트엔드보다 백엔드가 더 궁금해요" 같은 것.
     LLM 이 읽고 프로필 필드 변경을 제안하고, 원문은 메모로 보존한다.

프로필 변경은 증분("+항목" / "-항목")으로 제안하게 한다. 전체 교체면 답장 한 줄로
기존 관심사가 통째로 날아간다.
"""
import logging
import re

from . import config, llm
from .memory_agent import EDITABLE

log = logging.getLogger(__name__)

# "[TLA] like rec_004" 형태의 정형 피드백.
# 메일 클라이언트가 "Re:", "RE:", "Fwd:" 를 여러 겹 붙이므로 앞에서 걷어낸다.
_TAGGED = re.compile(
    r"^(?:\s*(?:re|fwd|fw)\s*:\s*)*\[TLA\]\s+(like|dislike)\s+(rec_\d+)",
    re.IGNORECASE,
)

_SYSTEM = """당신은 개발자 뉴스레터의 피드백을 해석합니다.
사용자가 답장으로 남긴 내용을 읽고, 다음 추천에 반영할 프로필 변경을 제안하세요.

수정 가능한 필드: position, tech_stack, interests, level, language
- tech_stack / interests / language 는 리스트입니다. "+항목"(추가), "-항목"(제거) 형태로
  증분만 쓰세요. 전체를 다시 쓰지 마세요.
- position, level 은 문자열이라 새 값으로 교체합니다.
- 근거가 분명한 것만 넣으세요. 확실하지 않으면 profile_diff 를 비우세요.

아래 JSON 형식으로만 답하세요.
{
  "profile_diff": {"interests": ["+분산시스템", "-프론트엔드"]},
  "note_text": "메모로 남길 한 줄 요약. 원문의 의도를 보존하세요.",
  "likes": ["rec_001"],
  "dislikes": [],
  "recommendation_id": "언급된 추천 id 가 있으면, 없으면 null"
}"""


def parse_reply(reply: dict, profile: dict) -> dict:
    """답장 하나를 해석한다.

    반환: {type, profile_diff, note_text, likes, dislikes, recommendation_id}
    """
    if tagged := _TAGGED.match(reply.get("subject", "")):
        verdict, rec_id = tagged.group(1).lower(), tagged.group(2)
        log.info("정형 피드백: %s %s", verdict, rec_id)
        return {
            "type": verdict,
            "profile_diff": {},
            "note_text": None,
            "likes": [rec_id] if verdict == "like" else [],
            "dislikes": [rec_id] if verdict == "dislike" else [],
            "recommendation_id": rec_id,
        }

    body = (reply.get("body") or "").strip()
    if not body:
        return _empty()

    prompt = (
        f"=== 현재 프로필 ===\n"
        f"포지션: {profile.get('position', '')}\n"
        f"기술 스택: {', '.join(profile.get('tech_stack') or [])}\n"
        f"관심 주제: {', '.join(profile.get('interests') or [])}\n"
        f"연차: {profile.get('level', '')}\n\n"
        f"=== 사용자 답장 ===\n{body[:4000]}"
    )
    try:
        result = llm.complete_json(prompt, model=config.MODEL_CHEAP, system=_SYSTEM,
                                  max_tokens=config.TOKENS_ANALYZE, temperature=0.2)
    except Exception as exc:
        # 해석에 실패해도 원문은 메모로 남긴다. 다음 추천 때 LLM 이 직접 읽는다.
        log.warning("답장 해석 실패, 원문만 메모로 남깁니다: %s", exc)
        return {**_empty(), "note_text": body[:500]}

    if not isinstance(result, dict):
        return {**_empty(), "note_text": body[:500]}

    return {
        "type": "reply_text",
        "profile_diff": _sanitize(result.get("profile_diff")),
        "note_text": (result.get("note_text") or body)[:500],
        "likes": [str(x) for x in (result.get("likes") or [])],
        "dislikes": [str(x) for x in (result.get("dislikes") or [])],
        "recommendation_id": result.get("recommendation_id") or None,
    }


def _sanitize(diff) -> dict:
    """LLM 이 수정 불가 필드를 건드리거나 이상한 타입을 주는 경우를 막는다."""
    if not isinstance(diff, dict):
        return {}
    return {k: v for k, v in diff.items() if k in EDITABLE and v not in (None, "", [])}


def _empty() -> dict:
    return {"type": "reply_text", "profile_diff": {}, "note_text": None,
            "likes": [], "dislikes": [], "recommendation_id": None}
