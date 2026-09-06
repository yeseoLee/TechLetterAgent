"""LLM 호출 래퍼 — 모든 텍스트 생성은 OpenRouter 무료 모델을 경유한다.

무료 티어는 분당/일일 요청 수 제한이 걸리므로 호출 간 최소 간격을 두고,
429 와 빈 응답에 대해 지수 백오프로 재시도한다.

임베딩과 STT 는 OpenRouter 에 해당 모델이 없어 OpenAI 를 직접 호출한다
(`article_analyzer` 참고).
"""
import json
import random
import re
import time
from functools import lru_cache

from openai import OpenAI, RateLimitError, APIError

from . import config

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_last_call_at = 0.0


@lru_cache(maxsize=1)
def client() -> OpenAI:
    """OpenRouter 를 가리키는 OpenAI 호환 클라이언트."""
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY 가 설정되지 않았습니다.")
    return OpenAI(
        base_url=config.OPENROUTER_BASE_URL,
        api_key=config.OPENROUTER_API_KEY,
        default_headers={
            "HTTP-Referer": config.OPENROUTER_REFERER,
            "X-Title": config.OPENROUTER_TITLE,
        },
    )


def _throttle() -> None:
    """무료 티어 분당 한도에 걸리지 않도록 호출 간 최소 간격을 지킨다."""
    global _last_call_at
    wait = config.LLM_MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call_at)
    if wait > 0:
        time.sleep(wait)
    _last_call_at = time.monotonic()


def complete(prompt: str, *, model: str, system: str | None = None,
             max_tokens: int = 4096, temperature: float = 0.3) -> str:
    """단일 턴 텍스트 생성. 429/일시적 오류는 지수 백오프로 재시도한다."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error: Exception | None = None
    for attempt in range(config.LLM_MAX_RETRIES):
        _throttle()
        try:
            response = client().chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = (response.choices[0].message.content or "").strip()
            if text:
                return text
            last_error = ValueError("빈 응답")
        except (RateLimitError, APIError) as exc:
            last_error = exc

        # 무료 모델은 프로바이더 혼잡 시 429 가 잦다. 지터를 섞어 백오프.
        time.sleep(config.LLM_RETRY_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 2))

    raise RuntimeError(f"{model} 호출 실패 ({config.LLM_MAX_RETRIES}회 시도): {last_error}")


def complete_json(prompt: str, *, model: str, system: str | None = None,
                  max_tokens: int = 4096, temperature: float = 0.3) -> dict | list:
    """JSON 응답을 요구하고 파싱해서 반환한다.

    무료 모델은 `response_format` 지원이 프로바이더마다 제각각이라,
    스키마 파라미터 대신 프롬프트로 JSON 을 요구하고 코드펜스를 벗겨 파싱한다.
    """
    guard = "반드시 JSON 만 출력하세요. 설명, 인사말, 코드펜스 밖의 텍스트를 넣지 마세요."
    raw = complete(
        prompt,
        model=model,
        system=f"{system}\n\n{guard}" if system else guard,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return parse_json(raw)


def parse_json(raw: str) -> dict | list:
    """코드펜스나 앞뒤 잡텍스트가 섞여 있어도 JSON 본문을 뽑아낸다."""
    text = raw.strip()
    if fenced := _JSON_BLOCK.search(text):
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 첫 여는 괄호부터 마지막 닫는 괄호까지 잘라 재시도.
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    ends = [text.rfind("}"), text.rfind("]")]
    if starts and max(ends) > min(starts):
        return json.loads(text[min(starts):max(ends) + 1])
    raise ValueError(f"JSON 파싱 실패: {raw[:300]}")
