"""Article Analyzer — 영상 설명 기반으로 요약/난이도/타겟대상을 생성하고 임베딩을 만든다.

분석 입력은 두 가지다.
  설명 — 발표자가 직접 쓴 초록. 컨퍼런스 채널은 여기에 세션 요약, 발표 대상,
         목차를 구조화해 넣는 경우가 많아 신뢰도가 높다.
  자막 — 발표 앞부분. 발표자가 실제로 무엇을 어떤 깊이로 말하는지 보여준다.
         설명이 부실하거나 홍보성일 때 이쪽이 실질을 채운다.

자막은 데이터센터 IP 에서 차단되므로 없을 수 있다. 그 경우 설명만으로 진행한다.

요약/난이도/타겟 생성과 임베딩 모두 OpenRouter 를 경유한다.
"""
import logging

from . import config, llm

log = logging.getLogger(__name__)

# 자막은 content_agent 가 앞 3분만 잘라서 넘긴다. 여기서는 그것도 길면 자른다.
TRANSCRIPT_LIMIT = 4000
DESCRIPTION_LIMIT = 3000

DIFFICULTIES = ["입문", "초급", "중급", "고급"]

_SYSTEM = """당신은 개발자 컨퍼런스 발표 영상을 분석합니다.
주어진 정보를 읽고 아래 JSON 형식으로만 답하세요. 모든 값은 한국어로 씁니다.
영어 발표라도 요약과 대상은 한국어로 씁니다.

자막이 주어지면 발표 앞부분입니다. 발표자가 실제로 무엇을 어떤 깊이로 말하는지
드러나므로, 설명이 홍보성이거나 부실할 때 자막을 더 신뢰하세요.
자막에는 음성 인식 오류가 섞여 있습니다. 문맥으로 바로잡아 읽고, 확실하지 않은
고유명사는 요약에 쓰지 마세요.

{
  "summary": "이 발표가 무엇을 다루는지 3~4문장, 200~350자. 어떤 문제를 왜 풀었고 어떤 방법을 썼는지 순서로 쓰세요. 구체적인 기술명과 수치를 포함하고, '~를 소개합니다' 같은 뭉뚱그린 표현 대신 실제 내용을 쓰세요",
  "difficulty": "입문|초급|중급|고급 중 하나",
  "target_audience": "어떤 사람에게 맞는지 한 줄 (예: 3년차 이하 백엔드, 프론트엔드 전반)",
  "topics": ["핵심 주제 키워드 3~6개"]
}"""


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
        parts.append(f"\n자막 (발표 앞부분):\n{transcript[:TRANSCRIPT_LIMIT]}")
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
