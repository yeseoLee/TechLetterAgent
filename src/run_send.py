"""send.yml 진입점.

순서:
  1) Gmail 답장 확인 → 프로필/메모 반영
  2) 임베딩 유사도로 후보 Top-30 (기추천 제외)
  3) LLM 재검토로 강추 3 + 혹시나 2 확정
  4) 이메일 포맷팅
  5) Gmail 발송
  6) recommendations.json 갱신

--dry-run 은 1·5·6 을 건너뛰고 추천 결과만 출력한다. Gmail 설정 없이
매칭 품질을 확인할 때 쓴다.
"""
import argparse
import logging
from datetime import datetime, timezone

from . import (cluster_agent, config, content_store, discovery_agent,
               memory_agent, recommendation_agent)

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main(dry_run: bool = False, feedback_only: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    profile = memory_agent.bootstrap_profile()
    notes = content_store.load(config.USER_NOTES, []) or []
    videos = content_store.load(config.VIDEOS, []) or []

    # 답장만 읽어 프로필에 반영하고 끝낸다. 발송 없이 피드백 루프만 확인할 때 쓴다.
    if feedback_only:
        before = dict(profile)
        profile, notes = _apply_feedback(profile, notes)
        if profile != before:
            log.info("프로필 변경: %s", _diff_summary(before, profile))
        else:
            log.info("프로필 변경 없음")
        return

    if not videos:
        log.error("분석된 영상이 없습니다. 먼저 collect 를 돌리세요.")
        return

    # 1) 지난 발송 이후의 답장을 반영한다.
    if not dry_run:
        profile, notes = _apply_feedback(profile, notes)

    # 2) 후보 Top-K.
    candidates = cluster_agent.top_candidates(
        profile, notes, videos,
        exclude=cluster_agent.already_recommended(),
        k=config.TOP_K_CANDIDATES,
    )
    if not candidates:
        log.error("추천할 후보가 없습니다.")
        return

    # 3) LLM 재검토. 지난 좋아요/싫어요를 함께 넘겨 루프를 닫는다.
    by_id = {v["id"]: v for v in videos}
    signals = recommendation_agent.collect_signals(
        content_store.load(config.FEEDBACK_LOG, []) or [],
        content_store.load(config.RECOMMENDATIONS, []) or [],
        by_id,
    )
    if signals["liked"] or signals["disliked"]:
        log.info("반영할 반응: 좋아요 %d건, 싫어요 %d건",
                 len(signals["liked"]), len(signals["disliked"]))
    picks = recommendation_agent.recommend(profile, notes, candidates, signals)

    # 주간 신규 채널 제안. 실패해도 뉴스레터 발송은 막지 않는다.
    proposal = None
    try:
        proposal = discovery_agent.discover(profile)
        if proposal:
            log.info("새 채널 제안: %s (%s)", proposal["name"], proposal["channel_id"])
    except Exception as exc:
        log.warning("채널 탐색 실패, 이번 회차는 건너뜁니다: %s", exc)

    _print_picks(picks, by_id, candidates)

    if dry_run:
        log.info("dry-run: 발송과 이력 저장을 건너뜁니다.")
        return

    # 4~6) 포맷팅 → 발송 → 이력 저장.
    from . import email_client, newsletter_agent

    # 추천 이력 id 를 먼저 확정해야 mailto 피드백 링크에 넣을 수 있다.
    history = content_store.load(config.RECOMMENDATIONS, []) or []
    sent_at = _now()
    for pick in picks:
        pick["id"] = content_store.next_id(history + picks, "rec")

    # mailto 피드백 링크와 Reply-To 는 피드백 주소를 쓴다. 답장이 태그를 달고
    # 돌아와야 일상 메일과 구분해서 골라낼 수 있다.
    subject, html_body, text_body = newsletter_agent.render(
        picks, by_id, config.FEEDBACK_ADDRESS, proposal)
    message_id = email_client.send(subject, html_body, text_body,
                                   config.RECIPIENT_EMAIL, config.FEEDBACK_ADDRESS)

    for pick in picks:
        history.append({
            "id": pick["id"],
            "video_id": pick["video_id"],
            "tier": pick["tier"],
            "reason_text": pick["reason_text"],
            "sent_at": sent_at,
            "gmail_message_id": message_id,
        })
    content_store.save(config.RECOMMENDATIONS, history)

    # 제안한 채널을 기록해 두면 답장이 왔을 때 이름/언어를 되짚을 수 있고,
    # 답이 없어도 같은 채널을 다시 제안하지 않는다.
    if proposal:
        discoveries = content_store.load(config.DISCOVERIES, []) or []
        discoveries.append({**proposal, "proposed_at": sent_at, "answer": None})
        content_store.save(config.DISCOVERIES, discoveries)

    log.info("발송 완료. 추천 %d건을 이력에 기록했습니다.", len(picks))


def _apply_feedback(profile: dict, notes: list[dict]) -> tuple[dict, list[dict]]:
    """Gmail 답장을 읽어 프로필과 메모에 반영한다."""
    from . import email_client, feedback_agent

    history = content_store.load(config.RECOMMENDATIONS, []) or []
    last_sent = max((r.get("sent_at", "") for r in history), default="")
    known_ids = {r.get("gmail_message_id") for r in history if r.get("gmail_message_id")}

    feedback_log = content_store.load(config.FEEDBACK_LOG, []) or []
    seen = {f.get("message_id") for f in feedback_log if f.get("message_id")}

    try:
        replies = email_client.fetch_replies_since(
            last_sent, known_ids, seen, config.FEEDBACK_ADDRESS)
    except Exception as exc:
        log.warning("답장 조회 실패, 이번 회차는 건너뜁니다: %s", exc)
        return profile, notes

    if not replies:
        log.info("새 답장 없음")
        return profile, notes

    for reply in replies:
        parsed = feedback_agent.parse_reply(reply, profile)

        if channel_id := parsed.get("channel_id"):
            memory_agent.apply_channel_answer(
                channel_id, parsed["type"] == "channel-yes")

        profile = memory_agent.apply_diff(profile, parsed.get("profile_diff"))
        if note_text := parsed.get("note_text"):
            notes = memory_agent.add_note(notes, note_text, parsed.get("recommendation_id"))
        feedback_log.append({
            "id": content_store.next_id(feedback_log, "fb"),
            "message_id": reply.get("message_id"),
            "recommendation_id": parsed.get("recommendation_id"),
            "type": parsed.get("type", "reply_text"),
            "raw_text": reply.get("body", ""),
            "applied_profile_diff": parsed.get("profile_diff"),
            "created_at": _now(),
        })

    content_store.save(config.USER_PROFILE, profile)
    content_store.save(config.USER_NOTES, notes)
    content_store.save(config.FEEDBACK_LOG, feedback_log)
    log.info("답장 %d건 반영 완료", len(replies))
    return profile, notes


def _diff_summary(before: dict, after: dict) -> str:
    """어떤 필드가 어떻게 바뀌었는지 한 줄로 요약한다."""
    changes = []
    for field in ("position", "tech_stack", "interests", "level", "language"):
        if before.get(field) != after.get(field):
            changes.append(f"{field}: {before.get(field)} → {after.get(field)}")
    return " | ".join(changes) or "(타임스탬프만)"


def _print_picks(picks: list[dict], by_id: dict, candidates: list[dict]) -> None:
    similarity = {c["id"]: c.get("similarity") for c in candidates}
    for pick in picks:
        video = by_id.get(pick["video_id"], {})
        mark = "강추" if pick["tier"] == "strong" else "혹시나"
        log.info("[%s] %s (유사도 %.3f, 난이도 %s)",
                 mark, video.get("title", "?")[:55],
                 similarity.get(pick["video_id"]) or 0.0, video.get("difficulty", "?"))
        log.info("       %s", pick["reason_text"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="추천 산출 및 뉴스레터 발송")
    parser.add_argument("--dry-run", action="store_true",
                        help="발송/이력 저장 없이 추천 결과만 출력 (Gmail 설정 불필요)")
    parser.add_argument("--feedback-only", action="store_true",
                        help="답장만 읽어 프로필에 반영하고 종료 (발송 없음)")
    args = parser.parse_args()
    main(dry_run=args.dry_run, feedback_only=args.feedback_only)
