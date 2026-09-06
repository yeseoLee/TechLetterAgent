"""Article Analyzer — 자막 기반으로 요약/난이도/타겟대상을 LLM 으로 생성하고 임베딩을 만든다.

자막이 없는 영상만 OpenAI Whisper API 로 STT 폴백.
"""


def transcribe_with_whisper(video_url: str) -> str:
    """자동 자막이 없는 영상의 오디오를 내려받아 Whisper API 로 STT."""
    raise NotImplementedError


def analyze(video: dict) -> dict:
    """Haiku 4.5 로 summary / difficulty / target_audience 를 생성해 video 딕셔너리를 채운다."""
    raise NotImplementedError


def embed(text: str) -> list[float]:
    """OpenAI text-embedding-3-small 임베딩."""
    raise NotImplementedError
