"""Article Analyzer — 영상 설명 기반으로 요약/난이도/타겟대상을 생성하고 임베딩을 만든다.

분석 입력은 발표자가 직접 쓴 영상 설명이다. 컨퍼런스 채널은 여기에 세션 초록,
발표 대상, 목차를 구조화해 넣는 경우가 많다. 자막을 쓰지 않는 이유는
content_agent 의 모듈 주석 참고. 자막이 있으면(로컬 실행) 함께 넣는다.

요약/난이도/타겟 생성과 임베딩 모두 OpenRouter 를 경유한다.
"""
import logging

from . import config, llm

log = logging.getLogger(__name__)

# 자막을 함께 넣는 경우, 전체를 넣으면 무료 모델의 컨텍스트와 응답 품질이
# 모두 흔들린다. 발표는 도입부와 마무리에 주제가 몰려 있어 앞뒤를 잘라 쓴다.
TRANSCRIPT_HEAD = 6000
TRANSCRIPT_TAIL = 2000

DESCRIPTION_LIMIT = 3000

DIFFICULTIES = ["입문", "초급", "중급", "고급"]

_SYSTEM = """당신은 개발자 컨퍼런스 발표 영상을 분석합니다.
주어진 정보를 읽고 아래 JSON 형식으로만 답하세요. 모든 값은 한국어로 씁니다.
영어 발표라도 요약과 대상은 한국어로 씁니다.

{
  "summary": "이 발표가 무엇을 다루는지 2문장. 구체적인 기술명을 포함할 것",
  "difficulty": "입문|초급|중급|고급 중 하나",
  "target_audience": "어떤 사람에게 맞는지 한 줄 (예: 3년차 이하 백엔드, 프론트엔드 전반)",
  "topics": ["핵심 주제 키워드 3~6개"]
}"""


def _trim(transcript: str) -> str:
    """자막이 길면 앞뒤만 남긴다."""
    if len(transcript) <= TRANSCRIPT_HEAD + TRANSCRIPT_TAIL:
        return transcript
    return f"{transcript[:TRANSCRIPT_HEAD]}\n\n[...중략...]\n\n{transcript[-TRANSCRIPT_TAIL:]}"


def analyze(video: dict) -> dict:
    """summary / difficulty / target_audience / topics 를 생성해 video 에 채워 넣는다."""
    parts = [
        f"제목: {video.get('title', '')}",
        f"채널: {video.get('channel', '')}",
        f"길이: {video.get('duration_sec', '?')}초",
    ]
    if tags := video.get("tags"):
        parts.append(f"태그: {', '.join(tags)}")
    parts.append(f"\n영상 설명:\n{(video.get('description') or '')[:DESCRIPTION_LIMIT]}")
    if transcript := video.get("transcript"):
        parts.append(f"\n자막:\n{_trim(transcript)}")
    prompt = "\n".join(parts)
    result = llm.complete_json(
        prompt, model=config.MODEL_CHEAP, system=_SYSTEM, max_tokens=config.TOKENS_ANALYZE, temperature=0.2
    )
    if not isinstance(result, dict):
        raise ValueError(f"분석 응답이 객체가 아님: {type(result)}")

    difficulty = str(result.get("difficulty", "")).strip()
    video["summary"] = str(result.get("summary", "")).strip()
    video["difficulty"] = difficulty if difficulty in DIFFICULTIES else "중급"
    video["target_audience"] = str(result.get("target_audience", "")).strip()
    video["topics"] = [str(t) for t in (result.get("topics") or [])][:6]
    return video


def embed(text: str) -> list[float]:
    """OpenRouter 임베딩. 목록은 /api/v1/embeddings/models 에 따로 있다."""
    response = llm.client().embeddings.create(
        model=config.EMBEDDING_MODEL, input=text[:config.EMBEDDING_INPUT_LIMIT]
    )
    return response.data[0].embedding


def embed_video(video: dict) -> list[float]:
    """매칭에 쓸 영상 임베딩. 제목/요약/타겟/주제를 합쳐서 만든다."""
    parts = [
        video.get("title", ""),
        video.get("summary", ""),
        f"난이도: {video.get('difficulty', '')}",
        f"대상: {video.get('target_audience', '')}",
        " ".join(video.get("topics") or []),
    ]
    return embed("\n".join(p for p in parts if p))
