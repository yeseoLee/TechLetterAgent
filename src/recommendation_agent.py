"""Recommendation Agent — 매주 3편을 확정한다.

  near 2편 — 임베딩 유사도 상위. 확실히 취향에 맞는 것. 코드가 고르고 LLM 은 이유만 쓴다.
  far  1편 — 유사도는 낮지만 볼 가치가 있다고 LLM 이 판단한 것(LLM as a Judge).
             유사도만 따르면 추천이 한 방향으로 굳어서, 취향을 넓힐 여지를 남긴다.

0~100 스코어링은 쓰지 않는다. 임계값 캘리브레이션이 번거로워서, 개수를 직접 지정한다.
"""
import logging

from . import config, llm

log = logging.getLogger(__name__)

# 후보 목록에 넣을 요약 길이. 건당 길이가 전체 프롬프트를 좌우한다.
SUMMARY_LIMIT = 300

TIER_NEAR = "near"
TIER_FAR = "far"

_SYSTEM = """당신은 개발자 한 명을 위한 영상 큐레이터입니다.

할 일이 두 가지입니다.

1. [확실한 추천] 목록의 영상 {n_near}개 각각에 대해, 이 사람에게 왜 맞는지 이유를 쓰세요.
   이미 선정된 영상이므로 고르지 말고 이유만 쓰면 됩니다.

2. [넓혀볼 후보] 목록에서 정확히 {n_far}개를 고르세요.
   이 목록은 프로필과 유사도가 낮은 영상들입니다. 그중에서 지금 당장 취향에 맞진
   않아도 이 사람이 보면 시야가 넓어질 만한 것을 고르세요.
   단순히 유명하거나 좋은 발표라서가 아니라, 이 사람의 현재 관심사와 어떻게
   연결되는지 설명할 수 있는 것을 고르세요. 연결점이 전혀 없으면 가장 덜 동떨어진
   것을 고르고 그렇게 말하세요.

이유는 한국어 2문장 이내로, 프로필의 어떤 점과 연결되는지 구체적으로 쓰세요.
프로필의 구조화 필드와 메모가 충돌하면 메모를 우선하세요. 메모가 더 최신이고 구체적입니다.
지난 추천에 대한 반응(좋아요/싫어요)이 주어지면 가장 강한 신호로 취급하세요.

아래 JSON 형식으로만 답하세요.
{{
  "near": [{{"id": "video_001", "reason": "..."}}],
  "far": [{{"id": "video_020", "reason": "..."}}]
}}"""


def collect_signals(feedback_log: list[dict], recommendations: list[dict],
                    videos_by_id: dict[str, dict], limit: int = 8) -> dict[str, list[str]]:
    """좋아요/싫어요한 영상 제목을 모은다.

    피드백을 기록만 하고 쓰지 않으면 루프가 닫히지 않는다. "이 발표가 좋았다" 는
    프로필 필드로 표현할 수 없어서 제목을 그대로 넘긴다.
    """
    video_of_rec = {r["id"]: r["video_id"] for r in recommendations if r.get("id")}
    liked, disliked = [], []

    for entry in reversed(feedback_log):  # 최근 것부터
        video_id = video_of_rec.get(entry.get("recommendation_id"))
        title = (videos_by_id.get(video_id) or {}).get("title")
        if not title:
            continue
        bucket = (liked if entry.get("type") == "like"
                  else disliked if entry.get("type") == "dislike" else None)
        if bucket is not None and title not in bucket and len(bucket) < limit:
            bucket.append(title)

    return {"liked": liked, "disliked": disliked}


def split_pools(candidates: list[dict], n_near: int = config.N_NEAR
                ) -> tuple[list[dict], list[dict]]:
    """유사도 순 후보를 near 확정분과 far 판정 풀로 나눈다.

    far 풀은 중간~하위 구간에서 뽑는다. 최상위는 near 와 겹치고 최하위는 아예
    무관한 영상이라, 그 사이에 "낯설지만 연결점은 있는" 것이 모인다.
    """
    near = candidates[:n_near]
    start = max(n_near, int(len(candidates) * config.FAR_POOL_START))
    far_pool = candidates[start:start + config.FAR_POOL_SIZE]
    return near, far_pool


def recommend(profile: dict, notes: list[dict], candidates: list[dict],
              signals: dict | None = None,
              n_near: int = config.N_NEAR, n_far: int = config.N_FAR) -> list[dict]:
    """반환: [{video_id, tier, reason_text}, ...]. tier 는 "near" | "far"."""
    if not candidates:
        return []

    near, far_pool = split_pools(candidates, n_near)
    log.info("near %d편 확정, far 판정 풀 %d편 (유사도 %.3f ~ %.3f)",
             len(near), len(far_pool),
             far_pool[-1]["similarity"] if far_pool else 0,
             far_pool[0]["similarity"] if far_pool else 0)

    blocks = [f"=== 프로필 ===\n{_format_profile(profile, notes)}"]
    if signal_text := _format_signals(signals or {}):
        blocks.append(f"=== 지난 추천에 대한 반응 ===\n{signal_text}")
    blocks.append(f"=== 확실한 추천 (이유만 쓸 것) ===\n{_format_candidates(near)}")
    if far_pool:
        blocks.append(f"=== 넓혀볼 후보 (여기서 {n_far}개 고를 것) ===\n"
                      f"{_format_candidates(far_pool)}")

    result = llm.complete_json(
        "\n\n".join(blocks),
        model=config.MODEL_SMART,
        system=_SYSTEM.format(n_near=n_near, n_far=n_far),
        max_tokens=config.TOKENS_RECOMMEND,
        temperature=0.4,
    )
    if not isinstance(result, dict):
        result = {}

    picks: list[dict] = []
    used: set[str] = set()
    _take(picks, used, result.get(TIER_NEAR), {v["id"] for v in near}, TIER_NEAR, n_near)
    _take(picks, used, result.get(TIER_FAR), {v["id"] for v in far_pool}, TIER_FAR, n_far)

    # LLM 이 개수를 못 맞추거나 없는 id 를 지어낸 경우를 순위로 메운다.
    _backfill(picks, used, near, TIER_NEAR, n_near)
    _backfill(picks, used, far_pool or candidates, TIER_FAR, n_far)
    return picks


def _take(picks: list[dict], used: set[str], items, valid_ids: set[str],
          tier: str, wanted: int) -> None:
    for item in (items or [])[:wanted]:
        video_id = (item or {}).get("id")
        if video_id in valid_ids and video_id not in used:
            used.add(video_id)
            picks.append({"video_id": video_id, "tier": tier,
                          "reason_text": str(item.get("reason", "")).strip()})


def _backfill(picks: list[dict], used: set[str], pool: list[dict],
              tier: str, wanted: int) -> None:
    have = sum(1 for p in picks if p["tier"] == tier)
    for video in pool:
        if have >= wanted:
            return
        if video["id"] in used:
            continue
        used.add(video["id"])
        picks.append({"video_id": video["id"], "tier": tier,
                      "reason_text": "유사도 순으로 채운 후보입니다."})
        have += 1
        log.warning("%s 개수 부족으로 %s 를 순위로 채움", tier, video["id"])


def _format_signals(signals: dict) -> str:
    lines = []
    if liked := signals.get("liked"):
        lines.append("좋아요를 누른 발표 (이런 걸 더 원함):")
        lines += [f"  - {t}" for t in liked]
    if disliked := signals.get("disliked"):
        lines.append("싫어요를 누른 발표 (이런 건 피할 것):")
        lines += [f"  - {t}" for t in disliked]
    return "\n".join(lines)


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
    return "\n\n".join(
        f"[{v['id']}] {v.get('title', '')}\n"
        f"  채널: {v.get('channel', '')} / 난이도: {v.get('difficulty', '')}"
        f" / 길이: {round((v.get('duration_sec') or 0) / 60)}분\n"
        f"  대상: {v.get('target_audience', '')}\n"
        f"  요약: {(v.get('summary') or '')[:SUMMARY_LIMIT]}"
        for v in candidates
    )
