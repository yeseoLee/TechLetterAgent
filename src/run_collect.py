"""collect.yml 진입점: 신규 영상 수집 → 사전 필터 → 분석 → videos.json 갱신.

무료 모델 요청 한도를 아끼기 위해 싼 단계부터 순서대로 거른다:
  Data API 수집(길이·설명 포함) → 규칙 필터 → LLM 필터 → LLM 분석 → 임베딩
분석 건수는 config.MAX_ANALYSIS_PER_RUN 으로 제한하고, 초과분은 다음 실행으로 밀린다.
"""
import argparse
import logging
from datetime import datetime, timezone

from . import article_analyzer, config, content_agent, content_store, prefilter

log = logging.getLogger(__name__)

# 설명이 이보다 짧으면 분석 근거가 부족하다고 보고 건너뛴다.
MIN_DESCRIPTION_CHARS = 40


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main(limit: int | None = None, use_llm_filter: bool = True,
         with_transcript: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    limit = limit or config.MAX_ANALYSIS_PER_RUN

    videos = content_store.load(config.VIDEOS, [])
    fresh = content_agent.collect_new_videos(per_source=config.PER_SOURCE_LIMIT)
    if not fresh:
        return

    stats = {"규칙 제외": 0, "LLM 제외": 0, "설명 부족": 0, "분석 실패": 0, "추가": 0}
    added = 0

    for entry in fresh:
        if added >= limit:
            log.info("이번 실행 한도(%d) 도달. 나머지는 다음 실행으로.", limit)
            break

        # 1) 제목·길이 규칙. 여기서 걸리면 LLM 호출이 없다.
        passed, reason = prefilter.rule_check(entry)
        if not passed:
            log.info("제외 [%s] %s", reason, entry["title"][:50])
            stats["규칙 제외"] += 1
            continue

        # 2) 설명이 분석 근거가 될 만큼 있는지. 자막이 없으니 설명이 유일한 본문이다.
        if len((entry.get("description") or "").strip()) < MIN_DESCRIPTION_CHARS:
            log.info("제외 [설명 부족] %s", entry["title"][:50])
            stats["설명 부족"] += 1
            continue

        # 3) 규칙으로 못 거른 것만 LLM 에 물어본다.
        if use_llm_filter:
            passed, reason = prefilter.llm_check(entry)
            if not passed:
                log.info("제외 [LLM: %s] %s", reason, entry["title"][:50])
                stats["LLM 제외"] += 1
                continue

        # 4) 로컬 실행에서만. Actions 에서는 봇 차단으로 항상 None 이다.
        if with_transcript and (got := content_agent.fetch_transcript(entry["url"])):
            entry["transcript"], entry["language"] = got

        # 5) 요약/난이도/타겟 생성 후 임베딩.
        try:
            article_analyzer.analyze(entry)
            entry["embedding"] = article_analyzer.embed_video(entry)
        except Exception as exc:
            log.warning("분석 실패 (%s): %s", entry["title"][:40], exc)
            stats["분석 실패"] += 1
            continue

        entry["id"] = content_store.next_id(videos, "video")
        entry["created_at"] = _now()
        videos.append(entry)
        added += 1
        stats["추가"] += 1
        log.info("추가 [%s] %s", entry["difficulty"], entry["title"][:50])

    content_store.save(config.VIDEOS, videos)
    log.info("결과: %s | 저장된 영상 총 %d개", stats, len(videos))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="신규 영상 수집·분석")
    parser.add_argument("--limit", type=int, help="이번 실행에서 분석할 최대 영상 수")
    parser.add_argument("--no-llm-filter", action="store_true", help="LLM 사전 필터 건너뛰기")
    parser.add_argument("--with-transcript", action="store_true",
                        help="자막도 함께 분석에 넣는다 (로컬 실행 전용, Actions 에서는 차단됨)")
    args = parser.parse_args()
    main(limit=args.limit, use_llm_filter=not args.no_llm_filter,
         with_transcript=args.with_transcript)
