"""Article Analyzer — 자막 기반으로 요약/난이도/타겟대상을 생성하고 임베딩을 만든다.

요약/난이도/타겟 생성: OpenRouter 무료 모델 (config.MODEL_CHEAP).
임베딩/STT: OpenRouter 가 해당 모델을 제공하지 않아 OpenAI 를 직접 호출한다.
"""
import logging
from functools import lru_cache

from openai import OpenAI

from . import config, llm

log = logging.getLogger(__name__)

# 자막 전체를 넣으면 무료 모델의 컨텍스트와 응답 품질이 모두 흔들린다.
# 발표는 도입부와 마무리에 주제가 몰려 있어 앞뒤를 잘라 쓴다.
TRANSCRIPT_HEAD = 6000
TRANSCRIPT_TAIL = 2000

DIFFICULTIES = ["입문", "초급", "중급", "고급"]

_SYSTEM = """당신은 개발자 컨퍼런스 발표 영상을 분석합니다.
자막을 읽고 아래 JSON 형식으로만 답하세요. 모든 값은 한국어로 씁니다.

{
  "summary": "이 발표가 무엇을 다루는지 2문장. 구체적인 기술명을 포함할 것",
  "difficulty": "입문|초급|중급|고급 중 하나",
  "target_audience": "어떤 사람에게 맞는지 한 줄 (예: 3년차 이하 백엔드, 프론트엔드 전반)",
  "topics": ["핵심 주제 키워드 3~6개"]
}"""


@lru_cache(maxsize=1)
def openai_client() -> OpenAI:
    """임베딩/Whisper 전용 OpenAI 클라이언트 (OpenRouter 가 아님)."""
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 가 설정되지 않았습니다.")
    return OpenAI(api_key=config.OPENAI_API_KEY)


def _trim(transcript: str) -> str:
    """자막이 길면 앞뒤만 남긴다."""
    if len(transcript) <= TRANSCRIPT_HEAD + TRANSCRIPT_TAIL:
        return transcript
    return f"{transcript[:TRANSCRIPT_HEAD]}\n\n[...중략...]\n\n{transcript[-TRANSCRIPT_TAIL:]}"


def analyze(video: dict) -> dict:
    """summary / difficulty / target_audience / topics 를 생성해 video 에 채워 넣는다."""
    prompt = (
        f"제목: {video.get('title', '')}\n"
        f"채널: {video.get('channel', '')}\n"
        f"길이: {video.get('duration_sec', '?')}초\n\n"
        f"자막:\n{_trim(video.get('transcript', ''))}"
    )
    result = llm.complete_json(
        prompt, model=config.MODEL_CHEAP, system=_SYSTEM, max_tokens=1200, temperature=0.2
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
    """OpenAI text-embedding-3-small 임베딩."""
    response = openai_client().embeddings.create(
        model=config.EMBEDDING_MODEL, input=text[:8000]
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


def transcribe_with_whisper(video_url: str) -> str | None:
    """자막이 없는 영상의 오디오를 Whisper API 로 STT.

    유료라서 config.ENABLE_WHISPER_FALLBACK 이 켜져 있을 때만 동작한다.
    """
    if not config.ENABLE_WHISPER_FALLBACK:
        return None

    import tempfile
    from pathlib import Path

    import yt_dlp

    with tempfile.TemporaryDirectory() as tmp:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "outtmpl": f"{tmp}/audio.%(ext)s",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([video_url])
            audio = next(Path(tmp).glob("audio.*"))
            with audio.open("rb") as fh:
                return openai_client().audio.transcriptions.create(
                    model=config.STT_MODEL, file=fh
                ).text
        except Exception as exc:
            log.warning("Whisper STT 실패 (%s): %s", video_url, exc)
            return None
