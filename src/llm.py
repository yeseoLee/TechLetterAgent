"""LLM 호출 래퍼 — 모든 텍스트 생성은 OpenRouter 를 경유한다.

429/5xx 와 빈 응답은 지수 백오프로 재시도한다.

임베딩은 OpenRouter 에 해당 모델이 없어 OpenAI 를 직접 호출한다
(article_analyzer.embed 참고).
"""
import json
import logging
import random
import re
import time
from functools import lru_cache

from openai import OpenAI, RateLimitError, APIError

from . import config

log = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


@lru_cache(maxsize=1)
def client() -> OpenAI:
    """OpenRouter 를 가리키는 OpenAI 호환 클라이언트."""
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY 가 설정되지 않았습니다.")
    return OpenAI(
        base_url=config.OPENROUTER_BASE_URL,
        api_key=config.OPENROUTER_API_KEY,
        timeout=config.LLM_TIMEOUT_SECONDS,
        max_retries=0,  # 재시도는 complete() 가 직접 관리한다.
        default_headers={
            "HTTP-Referer": config.OPENROUTER_REFERER,
            "X-Title": config.OPENROUTER_TITLE,
        },
    )


def complete(prompt: str, *, model: str, system: str | None = None,
             max_tokens: int = 4096, temperature: float = 0.3) -> str:
    """단일 턴 텍스트 생성. 429/일시적 오류는 지수 백오프로 재시도한다."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error: Exception | None = None
    for attempt in range(config.LLM_MAX_RETRIES):
        started = time.monotonic()
        try:
            response = client().chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = (response.choices[0].message.content or "").strip()
            if text:
                log.info("LLM %s %.1fs %d자", model, time.monotonic() - started, len(text))
                return text
            last_error = ValueError("빈 응답")
        except (RateLimitError, APIError) as exc:
            last_error = exc
        log.warning("LLM 시도 %d/%d 실패 (%.1fs): %s",
                    attempt + 1, config.LLM_MAX_RETRIES, time.monotonic() - started,
                    str(last_error)[:150])

        if attempt < config.LLM_MAX_RETRIES - 1:
            time.sleep(config.LLM_RETRY_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 1))

    raise RuntimeError(f"{model} 호출 실패 ({config.LLM_MAX_RETRIES}회 시도): {last_error}")


def complete_json(prompt: str, *, model: str, system: str | None = None,
                  max_tokens: int = 4096, temperature: float = 0.3) -> dict | list:
    """JSON 응답을 요구하고 파싱해서 반환한다.

    OpenRouter 는 `response_format` 지원이 프로바이더마다 제각각이라,
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
