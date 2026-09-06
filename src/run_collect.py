"""collect.yml 진입점: 신규 영상 수집 → 사전 필터 → 분석 → videos.json 갱신.

무료 모델 요청 한도를 아끼기 위해 비싼 단계를 뒤로 미룬다:
  RSS 수집 → 규칙 필터 → 메타데이터 → 규칙 필터(길이) → LLM 필터
  → 자막 추출 → LLM 분석 → 임베딩
분석 건수는 config.MAX_ANALYSIS_PER_RUN 으로 제한하고, 초과분은 다음 실행으로 밀린다.
"""
import argparse
import logging
from datetime import datetime, timezone

from . import article_analyzer, config, content_agent, content_store, prefilter

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main(limit: int | None = None, use_llm_filter: bool = True) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    limit = limit or config.MAX_ANALYSIS_PER_RUN

    videos = content_store.load(config.VIDEOS, [])
    fresh = content_agent.collect_new_videos()
    if not fresh:
        log.info("신규 영상 없음")
        return

    stats = {"규칙 제외": 0, "LLM 제외": 0, "메타 실패": 0, "자막 없음": 0, "분석 실패": 0, "추가": 0}
    added = 0

    for entry in fresh:
        if added >= limit:
            log.info("이번 실행 한도(%d) 도달. 나머지는 다음 실행으로.", limit)
            break

        # 1) 제목만으로 거를 수 있는 것부터. 여기서 걸리면 네트워크 요청이 없다.
        passed, reason = prefilter.rule_check(entry)
        if not passed:
            log.info("제외 [%s] %s", reason, entry["title"][:50])
            stats["규칙 제외"] += 1
            continue

        # 2) 길이·설명·자막 URL 을 한 번에 가져온다.
        meta = content_agent.fetch_metadata(entry["url"])
        if not meta:
            stats["메타 실패"] += 1
            continue
        entry.update({k: v for k, v in meta.items() if not k.startswith("_")})

        # 3) 길이를 알게 됐으니 규칙 필터를 한 번 더.
        passed, reason = prefilter.rule_check(entry)
        if not passed:
            log.info("제외 [%s] %s", reason, entry["title"][:50])
            stats["규칙 제외"] += 1
            continue

        # 4) 규칙으로 못 거른 것만 LLM 에 물어본다.
        if use_llm_filter:
            passed, reason = prefilter.llm_check(entry)
            if not passed:
                log.info("제외 [LLM: %s] %s", reason, entry["title"][:50])
                stats["LLM 제외"] += 1
                continue

        # 5) 자막. 없으면 Whisper 폴백(기본 비활성), 그마저 없으면 건너뛴다.
        got = content_agent.fetch_transcript(meta)
        if got:
            transcript, language = got
        else:
            transcript = article_analyzer.transcribe_with_whisper(entry["url"])
            language = entry.get("language", "ko")
            if not transcript:
                log.info("자막 없음, 건너뜀: %s", entry["title"][:50])
                stats["자막 없음"] += 1
                continue

        entry["transcript"] = transcript
        entry["language"] = language

        # 6) 요약/난이도/타겟 생성 후 임베딩.
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
    args = parser.parse_args()
    main(limit=args.limit, use_llm_filter=not args.no_llm_filter)
