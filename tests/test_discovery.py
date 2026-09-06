"""채널 탐색과 제안 응답 처리 테스트 (네트워크 없음)."""
import pytest

from src import discovery_agent as da
from src import feedback_agent as fa
from src.newsletter_agent import SUBJECT_TAG, discovery_block, render

PROFILE = {"position": "AI/ML 엔지니어", "tech_stack": ["Python"],
           "interests": ["AI 에이전트 / LLM 앱"], "level": "0-2년차"}
PROPOSAL = {"channel_id": "UCabc123", "name": "Test Tech Channel",
            "language": "en", "subscriber_count": 50000, "video_count": 120,
            "reason": "LLM 앱 관련 발표가 꾸준히 올라옵니다."}


# --- 검색어 생성 -----------------------------------------------------------

def test_queries_cover_korean_and_english():
    languages = {lang for _, lang in da._queries(PROFILE)}
    assert languages == {"ko", "en"}


def test_queries_use_profile_terms():
    queries = [q for q, _ in da._queries(PROFILE)]
    assert any("AI 에이전트" in q for q in queries)


def test_queries_fall_back_to_position():
    queries = [q for q, _ in da._queries({"position": "백엔드"})]
    assert any("백엔드" in q for q in queries)


# --- 제안 응답 -------------------------------------------------------------

@pytest.mark.parametrize("verdict,expected", [
    ("channel-yes", "channel-yes"),
    ("channel-no", "channel-no"),
])
def test_channel_answer_parsed_without_llm(monkeypatch, verdict, expected):
    monkeypatch.setattr(fa.llm, "complete_json",
                        lambda *a, **k: pytest.fail("정형 응답은 LLM 을 부르면 안 된다"))
    result = fa.parse_reply({"subject": f"Re: [TLA] {verdict} UCabc123", "body": ""}, PROFILE)
    assert result["type"] == expected
    assert result["channel_id"] == "UCabc123"


def test_normal_feedback_has_no_channel_id():
    result = fa.parse_reply({"subject": "[TLA] like rec_001", "body": ""}, PROFILE)
    assert result["channel_id"] is None
    assert result["recommendation_id"] == "rec_001"


# --- 메일 렌더링 -----------------------------------------------------------

def test_discovery_block_has_both_links():
    html = discovery_block(PROPOSAL, "me@example.com")
    from urllib.parse import unquote
    decoded = unquote(html)
    assert f"{SUBJECT_TAG} channel-yes UCabc123" in decoded
    assert f"{SUBJECT_TAG} channel-no UCabc123" in decoded
    assert "Test Tech Channel" in html


def test_render_omits_discovery_when_no_proposal():
    _, html, text = render([], {}, "me@example.com", None)
    assert "새 채널 추가할까요?" not in html
    assert "새 채널" not in text


def test_render_includes_discovery_in_both_bodies():
    _, html, text = render([], {}, "me@example.com", PROPOSAL)
    assert "Test Tech Channel" in html
    assert "Test Tech Channel" in text
    assert "channel-yes UCabc123" in text
