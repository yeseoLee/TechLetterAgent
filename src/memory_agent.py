"""Memory Agent — 프로필·메모·장기 기억의 영속화를 담당한다.

feedback_agent 가 제안한 diff 를 user_profile.json / user_notes.json 에 반영하고,
최초 실행 시 config/seed_profile.json 으로 프로필을 초기화한다.

기억은 두 층이다.
  단기 기억 — feedback_log / user_notes 의 최근 n개 (config.SHORT_TERM_N). 원문 그대로.
  장기 기억 — long_term_memory.json. 새 피드백이 쌓일 때마다 LLM 이 기존 장기 기억에
             새 피드백을 녹여 다시 쓴다. 로그가 길어져도 크기가 일정하다.
"""
import logging
from datetime import datetime, timezone

from . import config, content_store, llm

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


def apply_channel_answer(channel_id: str, approved: bool) -> bool:
    """채널 제안에 대한 예/아니오를 반영한다.

    예 -> config/channels.json 화이트리스트에 추가.
    아니오 -> discoveries.json 에만 남긴다. _known_channel_ids 가 이를 읽어
              같은 채널을 다시 제안하지 않는다.
    반환: 화이트리스트가 실제로 바뀌었는지.
    """
    discoveries = content_store.load(config.DISCOVERIES, []) or []
    for entry in discoveries:
        if entry.get("channel_id") == channel_id:
            entry["answer"] = "yes" if approved else "no"
            entry["answered_at"] = _now()
            break
    else:
        discoveries.append({"channel_id": channel_id,
                            "answer": "yes" if approved else "no",
                            "answered_at": _now()})
    content_store.save(config.DISCOVERIES, discoveries)

    if not approved:
        log.info("채널 제안 거절: %s", channel_id)
        return False

    proposal = next((d for d in discoveries if d.get("channel_id") == channel_id), {})
    sources = content_store.load(config.CHANNELS, {}) or {}
    channels = sources.setdefault("channels", [])
    if any(c.get("channel_id") == channel_id for c in channels):
        return False

    channels.append({
        "name": proposal.get("name", channel_id),
        "channel_id": channel_id,
        "language": proposal.get("language", "ko"),
        "added_by": "discovery",
    })
    content_store.save(config.CHANNELS, sources)
    log.info("채널 추가: %s (%s)", proposal.get("name", ""), channel_id)
    return True


# --- 장기 기억 -----------------------------------------------------------

MEMORY_FIELDS = ("preferences", "avoid", "context")

_MEMORY_SYSTEM = """당신은 개발자 뉴스레터 구독자 한 명의 장기 기억을 관리합니다.
기존 장기 기억과 새로 들어온 피드백을 읽고, 갱신된 장기 기억 전체를 돌려주세요.

- preferences: 꾸준히 원하는 주제·발표 스타일 (예: "실무 사례 중심의 LLM 평가 발표")
- avoid: 피하고 싶어하는 주제·스타일
- context: 추천에 영향을 주는 본인 상황 (예: "이직 준비 중", "팀에서 k8s 도입 예정")

규칙:
- 한 번의 반응을 일반화하지 말고, 반복되거나 본인이 명시한 것만 남기세요.
- 새 피드백이 기존 항목과 충돌하면 새 피드백을 따르세요.
- 비슷한 항목은 합치고, 각 목록은 {max_items}개 이하의 짧은 한국어 문장으로 유지하세요.

아래 JSON 형식으로만 답하세요.
{{"preferences": ["..."], "avoid": ["..."], "context": ["..."]}}"""


def pending_feedback(feedback_log: list[dict], memory: dict) -> list[dict]:
    """장기 기억에 아직 반영되지 않은 피드백. last_feedback_id 이후 전부."""
    ids = [f.get("id") for f in feedback_log]
    last = memory.get("last_feedback_id")
    return feedback_log[ids.index(last) + 1:] if last in ids else list(feedback_log)


def update_long_term(memory: dict, feedback_log: list[dict], recommendations: list[dict],
                     videos_by_id: dict[str, dict]) -> dict:
    """새 피드백을 장기 기억에 반영한 새 dict 를 반환한다.

    LLM 이 실패하면 기존 기억을 그대로 돌려준다. 커서(last_feedback_id)를 옮기지
    않으므로 다음 실행에서 같은 피드백으로 다시 시도한다.
    """
    new = pending_feedback(feedback_log, memory)
    if not new:
        return memory

    video_of_rec = {r["id"]: r["video_id"] for r in recommendations if r.get("id")}
    lines = []
    for entry in new:
        title = (videos_by_id.get(video_of_rec.get(entry.get("recommendation_id"))) or {}).get("title")
        kind = entry.get("type")
        if kind in ("like", "dislike") and title:
            lines.append(f"- {'좋아요' if kind == 'like' else '싫어요'}: {title}")
        elif kind == "reply_text" and (text := (entry.get("raw_text") or "").strip()):
            lines.append(f"- 답장: {text[:1000]}")

    advanced = {**memory, "last_feedback_id": new[-1].get("id")}
    if not lines:  # 채널 응답처럼 취향 정보가 없는 피드백뿐이면 커서만 옮긴다.
        return advanced

    current = "\n".join(f"{field}: {memory.get(field) or []}" for field in MEMORY_FIELDS)
    prompt = f"=== 기존 장기 기억 ===\n{current}\n\n=== 새 피드백 ===\n" + "\n".join(lines)
    try:
        result = llm.complete_json(
            prompt, model=config.MODEL_CHEAP,
            system=_MEMORY_SYSTEM.format(max_items=config.LONG_TERM_MAX_ITEMS),
            max_tokens=config.TOKENS_MEMORY, temperature=0.2)
    except Exception as exc:
        log.warning("장기 기억 갱신 실패, 다음 실행에서 재시도합니다: %s", exc)
        return memory
    if not isinstance(result, dict):
        log.warning("장기 기억 응답 형식 오류, 다음 실행에서 재시도합니다")
        return memory

    for field in MEMORY_FIELDS:
        items = result.get(field)
        if isinstance(items, list):
            advanced[field] = [str(i).strip() for i in items if str(i).strip()][:config.LONG_TERM_MAX_ITEMS]
    advanced["updated_at"] = _now()
    log.info("장기 기억 갱신: 피드백 %d건 반영", len(new))
    return advanced


def migrate_legacy_data(email: str) -> None:
    """단일 유저 시절의 data/*.json 을 첫 유저 디렉터리로 옮긴다.

    # ponytail: 1회성 이전. 모든 배포가 data/users/ 구조로 넘어가면 삭제.
    """
    legacy = [config.DATA_DIR / name for name in config.USER_FILES.values()]
    if not any(p.exists() for p in legacy):
        return
    target = config.USERS_DIR / config.user_key(email)
    if target.exists():
        log.warning("기존 단일 유저 데이터가 있지만 %s 가 이미 있어 옮기지 않습니다", target)
        return
    target.mkdir(parents=True)
    for path in legacy:
        if path.exists():
            path.rename(target / path.name)
    log.info("단일 유저 데이터를 %s 로 옮겼습니다", target)
