"""Article Analyzer — 자막 기반으로 요약/난이도/타겟대상을 생성하고 임베딩을 만든다.

요약/난이도/타겟 생성: OpenRouter 무료 모델 (config.MODEL_CHEAP).
임베딩/STT: OpenRouter 에 해당 모델이 없어 OpenAI 를 직접 호출한다.
"""


def openai_client():
    """임베딩/Whisper 전용 OpenAI 클라이언트 (OpenRouter 가 아님)."""
    raise NotImplementedError


def transcribe_with_whisper(video_url: str) -> str | None:
    """자막이 없는 영상의 오디오를 Whisper API 로 STT.

    유료라서 config.ENABLE_WHISPER_FALLBACK 이 켜져 있을 때만 동작하고,
    꺼져 있으면 None 을 반환해 해당 영상을 건너뛰게 한다.
    """
    raise NotImplementedError


def analyze(video: dict) -> dict:
    """llm.complete_json 으로 summary / difficulty / target_audience 를 생성해 채운다."""
    raise NotImplementedError


def embed(text: str) -> list[float]:
    """OpenAI text-embedding-3-small 임베딩."""
    raise NotImplementedError
