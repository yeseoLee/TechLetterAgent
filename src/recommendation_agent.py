"""Recommendation Agent — Top-K 후보를 LLM 으로 재검토해 강추/혹시나를 확정한다.

0~100 스코어링은 쓰지 않는다. 임계값 캘리브레이션이 번거로워서, LLM 에게 개수를
직접 지정해 정확히 N개 구조로 받는다.

프로필 구조화 필드와 누적 메모를 함께 넣어 종합 판단하게 한다. 메모가 더 최신이고
구체적이라 충돌하면 메모를 우선한다.
"""
import logging

from . import config, llm

log = logging.getLogger(__name__)

# 후보 목록에 넣을 요약 길이. 30개를 넣으므로 건당 길이가 전체 프롬프트를 좌우한다.
SUMMARY_LIMIT = 300

_SYSTEM = """당신은 개발자 한 명을 위한 영상 큐레이터입니다.
아래 프로필을 가진 사람에게 후보 영상 중 무엇을 볼지 골라주세요.

판단 기준 두 가지입니다.
1. 주제 적합성 — 이 사람의 포지션·기술스택·관심주제와 맞는가
2. 난이도 적합성 — 이 사람의 연차에 너무 쉽거나 어렵지 않은가

프로필의 구조화 필드와 메모가 충돌하면 메모를 우선하세요. 메모가 더 최신이고 구체적입니다.

정확히 strong {n_strong}개, maybe {n_maybe}개를 고르세요. 개수를 반드시 맞추세요.
- strong: 이 사람에게 자신 있게 추천하는 것
- maybe: 확신은 덜하지만 취향이 넓어질 수 있는 것

아래 JSON 형식으로만 답하세요.
{{
  "strong": [{{"id": "video_001", "reason": "왜 이 사람에게 맞는지 한국어 2문장. 프로필의 어떤 점과 연결되는지 구체적으로."}}],
  "maybe": [{{"id": "video_002", "reason": "한국어 1~2문장"}}]
}}"""


def _format_profile(profile: dict, notes: list[dict]) -> str:
    lines = [
        f"포지션: {profile.get('position', '')}",
        f"기술 스택: {', '.join(profile.get('tech_stack') or [])}",
        f"관심 주제: {', '.join(profile.get('interests') or [])}",
        f"연차: {profile.get('level', '')}",
        f"언어: {', '.join(profile.get('language') or [])}",
    ]
    if notes:
        lines.append("\n메모 (본인이 답장으로 남긴 것, 오래된 것부터):")
        lines += [f"  - {n['text']}" for n in notes if n.get("text")]
    return "\n".join(lines)


def _format_candidates(candidates: list[dict]) -> str:
    blocks = []
    for video in candidates:
        blocks.append(
            f"[{video['id']}] {video.get('title', '')}\n"
            f"  채널: {video.get('channel', '')} / 난이도: {video.get('difficulty', '')}"
            f" / 길이: {round((video.get('duration_sec') or 0) / 60)}분\n"
            f"  대상: {video.get('target_audience', '')}\n"
            f"  요약: {(video.get('summary') or '')[:SUMMARY_LIMIT]}"
        )
    return "\n\n".join(blocks)


def recommend(profile: dict, notes: list[dict], candidates: list[dict],
              n_strong: int = config.N_STRONG,
              n_maybe: int = config.N_MAYBE) -> list[dict]:
    """반환: [{video_id, tier, reason_text}, ...]. tier 는 "strong" | "maybe".

    LLM 이 개수를 틀리거나 없는 id 를 지어내는 경우가 있어, 후보 안의 id 인지
    확인하고 부족분은 유사도 순으로 채운다.
    """
    if not candidates:
        return []

    prompt = (
        f"=== 프로필 ===\n{_format_profile(profile, notes)}\n\n"
        f"=== 후보 영상 {len(candidates)}개 ===\n{_format_candidates(candidates)}"
    )
    result = llm.complete_json(
        prompt,
        model=config.MODEL_SMART,
        system=_SYSTEM.format(n_strong=n_strong, n_maybe=n_maybe),
        max_tokens=2000,
        temperature=0.4,
    )

    valid_ids = {v["id"] for v in candidates}
    picks: list[dict] = []
    used: set[str] = set()

    for tier, wanted in (("strong", n_strong), ("maybe", n_maybe)):
        for item in (result.get(tier) or [])[:wanted] if isinstance(result, dict) else []:
            video_id = (item or {}).get("id")
            if video_id in valid_ids and video_id not in used:
                used.add(video_id)
                picks.append({
                    "video_id": video_id,
                    "tier": tier,
                    "reason_text": str(item.get("reason", "")).strip(),
                })

    _backfill(picks, used, candidates, n_strong, n_maybe)
    return picks


def _backfill(picks: list[dict], used: set[str], candidates: list[dict],
              n_strong: int, n_maybe: int) -> None:
    """LLM 이 개수를 못 맞췄을 때 유사도 상위 순으로 채운다."""
    for tier, wanted in (("strong", n_strong), ("maybe", n_maybe)):
        have = sum(1 for p in picks if p["tier"] == tier)
        for video in candidates:
            if have >= wanted:
                break
            if video["id"] in used:
                continue
            used.add(video["id"])
            picks.append({
                "video_id": video["id"],
                "tier": tier,
                "reason_text": "유사도 상위 후보입니다.",
            })
            have += 1
            log.warning("%s 개수 부족으로 %s 를 유사도 순으로 채움", tier, video["id"])
