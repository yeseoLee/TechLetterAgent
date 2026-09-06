"""Discovery Agent — 주 1회 새로운 채널/재생목록 후보를 찾아 제안한다.

화이트리스트를 손으로만 늘리면 결국 아는 채널 안에서만 돌게 된다. 매주 한 개씩
후보를 제안하고, 사용자가 메일에서 예/아니오로 답하면 반영한다.

검색 도구는 YouTube Data API 의 search.list 를 쓴다. 범용 웹 검색보다 채널을
직접 찾기에 정확하고, 이미 가진 키로 호출할 수 있다. search.list 는 100 quota
units 라 다른 호출(1 unit)보다 비싸지만 주 1회면 부담이 없다.
"""
import logging

from . import config, content_store, llm, youtube_api

log = logging.getLogger(__name__)

# 프로필에서 검색어를 만들 때 붙이는 접미사. 개인 브이로그 채널이 아니라
# 컨퍼런스/테크 채널이 잡히게 유도한다.
_KO_SUFFIXES = ["개발자 컨퍼런스", "기술 컨퍼런스 발표", "테크 세미나"]
_EN_SUFFIXES = ["developer conference talks", "engineering tech talks"]

# 후보에서 걸러낼 최소 기준. 영상이 거의 없는 채널은 소스로 쓸 수 없다.
MIN_VIDEOS = 15
MIN_SUBSCRIBERS = 1000

_SYSTEM = """당신은 개발자 한 명을 위해 새로운 유튜브 채널을 발굴합니다.
아래 프로필을 가진 사람이 구독할 만한 채널을 후보 중에서 정확히 1개만 고르세요.

기준:
- 개발자 대상의 기술 발표·강연이 꾸준히 올라오는 채널일 것
  (개인 브이로그, 강의 판매, 뉴스 요약 채널은 제외)
- 이미 구독 중인 채널과 겹치지 않을 것
- 이 사람의 포지션·기술스택·관심주제와 연결될 것

한국어 채널과 영어 채널 모두 후보입니다. 좋은 후보가 없으면 selected 를 null 로 두세요.

아래 JSON 형식으로만 답하세요.
{
  "selected": "채널의 channel_id 또는 null",
  "reason": "왜 이 사람에게 맞는지 한국어 2문장",
  "language": "ko 또는 en"
}"""


def _queries(profile: dict) -> list[tuple[str, str]]:
    """프로필에서 검색어를 만든다. 반환: [(검색어, 언어), ...]"""
    interests = profile.get("interests") or []
    stack = profile.get("tech_stack") or []
    seeds = (interests + stack)[:3] or [profile.get("position", "개발")]

    queries = []
    for seed in seeds[:2]:
        queries.append((f"{seed} {_KO_SUFFIXES[0]}", "ko"))
        queries.append((f"{seed} {_EN_SUFFIXES[0]}", "en"))
    return queries


def _known_channel_ids() -> set[str]:
    sources = content_store.load(config.CHANNELS, {}) or {}
    known = {c.get("channel_id") for c in sources.get("channels", [])}
    # 거절했던 채널을 매주 다시 제안하지 않는다.
    for entry in content_store.load(config.DISCOVERIES, []) or []:
        known.add(entry.get("channel_id"))
    return {cid for cid in known if cid}


def discover(profile: dict) -> dict | None:
    """후보를 검색하고 LLM 판정으로 1개를 고른다. 없으면 None."""
    known = _known_channel_ids()
    found: dict[str, dict] = {}

    for query, language in _queries(profile):
        try:
            results = youtube_api.search_channels(
                query, config.DISCOVERY_SEARCH_RESULTS, language)
        except Exception as exc:
            log.warning("채널 검색 실패 (%s): %s", query, exc)
            continue
        log.info("검색 '%s' (%s): %d건", query, language, len(results))
        for item in results:
            if item["channel_id"] not in known:
                found.setdefault(item["channel_id"], item)

    if not found:
        log.info("새 후보 없음")
        return None

    # 활동이 없는 채널을 먼저 걸러낸다. LLM 에 넘기는 수를 줄이는 효과도 있다.
    try:
        stats = youtube_api.fetch_channel_stats(list(found))
    except Exception as exc:
        log.warning("채널 통계 조회 실패: %s", exc)
        return None

    viable = {
        cid: {**found[cid], **stat}
        for cid, stat in stats.items()
        if stat["video_count"] >= MIN_VIDEOS and stat["subscriber_count"] >= MIN_SUBSCRIBERS
    }
    log.info("후보 %d개 중 활동 기준 통과 %d개", len(found), len(viable))
    if not viable:
        return None

    selected = _judge(profile, viable)
    if not selected:
        return None

    channel = viable[selected["channel_id"]]
    return {
        "channel_id": selected["channel_id"],
        "name": channel["name"],
        "language": selected.get("language", "ko"),
        "subscriber_count": channel["subscriber_count"],
        "video_count": channel["video_count"],
        "reason": selected.get("reason", ""),
    }


def _judge(profile: dict, viable: dict[str, dict]) -> dict | None:
    """LLM 이 후보 중 하나를 고른다."""
    listing = "\n\n".join(
        f"[{cid}] {c['name']}\n"
        f"  구독자 {c['subscriber_count']:,} / 영상 {c['video_count']:,}개\n"
        f"  소개: {c['description'][:300]}"
        for cid, c in viable.items()
    )
    prompt = (
        f"=== 프로필 ===\n"
        f"포지션: {profile.get('position', '')}\n"
        f"기술 스택: {', '.join(profile.get('tech_stack') or [])}\n"
        f"관심 주제: {', '.join(profile.get('interests') or [])}\n"
        f"연차: {profile.get('level', '')}\n\n"
        f"=== 이미 구독 중인 채널 ===\n"
        f"{', '.join(c['name'] for c in (content_store.load(config.CHANNELS, {}) or {}).get('channels', []))}\n\n"
        f"=== 후보 채널 {len(viable)}개 ===\n{listing}"
    )
    try:
        result = llm.complete_json(prompt, model=config.MODEL_SMART, system=_SYSTEM,
                                   max_tokens=config.TOKENS_ANALYZE, temperature=0.5)
    except Exception as exc:
        log.warning("채널 판정 실패: %s", exc)
        return None

    if not isinstance(result, dict):
        return None
    channel_id = result.get("selected")
    if not channel_id or channel_id not in viable:
        log.info("LLM 이 적합한 후보를 고르지 못했습니다")
        return None
    return {"channel_id": channel_id, "reason": result.get("reason", ""),
            "language": result.get("language", "ko")}
