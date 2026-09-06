"""LLM 래퍼 테스트 (실제 API 호출 없음)."""
import types

import pytest

from src import config, llm


# --- JSON 파싱 -----------------------------------------------------------

def test_parses_plain_json():
    assert llm.parse_json('{"a": 1}') == {"a": 1}


def test_parses_fenced_json():
    assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('```\n[1, 2]\n```') == [1, 2]


def test_parses_json_with_surrounding_prose():
    assert llm.parse_json('네, 결과입니다:\n{"a": 1}\n확인해보세요.') == {"a": 1}


def test_raises_on_unparseable():
    with pytest.raises(ValueError):
        llm.parse_json("JSON 이 전혀 없는 문장")


# --- 응답 처리 -----------------------------------------------------------

def _response(content, reasoning=None, finish_reason="stop"):
    message = types.SimpleNamespace(content=content, reasoning=reasoning)
    return types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=types.SimpleNamespace(completion_tokens=100),
    )


class _FakeClient:
    """create() 호출을 기록하고 정해진 응답을 돌려준다."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.chat = types.SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


@pytest.fixture
def fake(monkeypatch):
    def install(*responses):
        client = _FakeClient(*responses)
        monkeypatch.setattr(llm, "client", lambda: client)
        monkeypatch.setattr(config, "LLM_RETRY_BASE_SECONDS", 0)
        return client
    return install


def test_complete_returns_content(fake):
    client = fake(_response("안녕하세요"))
    assert llm.complete("q", model="m") == "안녕하세요"


def test_complete_json_requests_json_mode(fake):
    """이 테스트가 없었다면 json_mode 인자 누락을 실행 시점에야 알았다."""
    client = fake(_response('{"ok": true}'))
    assert llm.complete_json("q", model="m") == {"ok": True}
    assert client.calls[0]["response_format"] == {"type": "json_object"}


def test_falls_back_to_reasoning_when_content_empty(fake):
    fake(_response("", reasoning='결론은 이렇습니다 {"a": 1}'))
    assert llm.complete_json("q", model="m") == {"a": 1}


def test_retries_on_empty_response(fake):
    client = fake(_response(""), _response('{"a": 1}'))
    assert llm.complete_json("q", model="m") == {"a": 1}
    assert len(client.calls) == 2


def test_gives_up_after_max_retries(fake):
    fake(*[_response("") for _ in range(config.LLM_MAX_RETRIES)])
    with pytest.raises(RuntimeError, match="호출 실패"):
        llm.complete("q", model="m")


def test_uses_configured_token_budget(fake):
    client = fake(_response("ok"))
    llm.complete("q", model="m")
    assert client.calls[0]["max_tokens"] == config.TOKENS_ANALYZE
