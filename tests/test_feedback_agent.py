"""답장 해석 테스트."""
import pytest

from src import feedback_agent as fa

PROFILE = {"position": "AI/ML 엔지니어", "tech_stack": ["Python"],
           "interests": ["AI 에이전트 / LLM 앱"], "level": "취준·주니어 (0-2년차)"}


def test_tagged_like_parsed_without_llm(monkeypatch):
    monkeypatch.setattr(fa.llm, "complete_json",
                        lambda *a, **k: pytest.fail("정형 피드백은 LLM 을 부르면 안 된다"))
    result = fa.parse_reply({"subject": "[TLA] like rec_004", "body": ""}, PROFILE)
    assert result["type"] == "like"
    assert result["likes"] == ["rec_004"]
    assert result["recommendation_id"] == "rec_004"


@pytest.mark.parametrize("subject", [
    "[TLA] dislike rec_007",
    "Re: [TLA] dislike rec_007",
    "RE: Re: [TLA] dislike rec_007",   # 여러 겹 붙는 경우
    "Fwd: [TLA] DISLIKE rec_007",
])
def test_tagged_dislike_survives_reply_prefixes(subject):
    result = fa.parse_reply({"subject": subject, "body": ""}, PROFILE)
    assert result["type"] == "dislike"
    assert result["dislikes"] == ["rec_007"]


def test_free_text_applies_profile_diff(monkeypatch):
    monkeypatch.setattr(fa.llm, "complete_json", lambda *a, **k: {
        "profile_diff": {"interests": ["+분산시스템"]},
        "note_text": "분산시스템에 관심이 생겼다", "likes": [], "dislikes": [],
        "recommendation_id": None,
    })
    result = fa.parse_reply({"subject": "Re: 오늘의 발표", "body": "분산시스템도 보고 싶어요"}, PROFILE)
    assert result["profile_diff"] == {"interests": ["+분산시스템"]}
    assert result["note_text"] == "분산시스템에 관심이 생겼다"


def test_drops_uneditable_fields(monkeypatch):
    monkeypatch.setattr(fa.llm, "complete_json", lambda *a, **k: {
        "profile_diff": {"interests": ["+Go"], "salary": "1억", "id": "해킹"},
        "note_text": "메모",
    })
    result = fa.parse_reply({"subject": "Re:", "body": "본문"}, PROFILE)
    assert set(result["profile_diff"]) == {"interests"}


def test_keeps_raw_text_when_llm_fails(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("모델 장애")
    monkeypatch.setattr(fa.llm, "complete_json", boom)
    result = fa.parse_reply({"subject": "Re:", "body": "백엔드가 궁금해요"}, PROFILE)
    # 해석에 실패해도 원문은 메모로 남는다 — 다음 추천 때 LLM 이 직접 읽는다.
    assert result["note_text"] == "백엔드가 궁금해요"
    assert result["profile_diff"] == {}


def test_empty_body_returns_empty(monkeypatch):
    result = fa.parse_reply({"subject": "Re:", "body": "   "}, PROFILE)
    assert result["note_text"] is None and result["profile_diff"] == {}


def test_handles_non_dict_llm_response(monkeypatch):
    monkeypatch.setattr(fa.llm, "complete_json", lambda *a, **k: ["리스트가 왔다"])
    result = fa.parse_reply({"subject": "Re:", "body": "본문"}, PROFILE)
    assert result["note_text"] == "본문"
