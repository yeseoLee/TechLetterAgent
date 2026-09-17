"""장기 기억 갱신과 단기 기억(최근 n개) 사용 테스트 (LLM 은 대체한다)."""
import pytest

from src import cluster_agent, config, memory_agent
from src import recommendation_agent as ra

RECS = [{"id": "rec_001", "video_id": "video_001"}, {"id": "rec_002", "video_id": "video_002"}]
VIDEOS = {"video_001": {"title": "LLM 평가 파이프라인"}, "video_002": {"title": "CSS 애니메이션"}}
LOG = [
    {"id": "fb_001", "recommendation_id": "rec_001", "type": "like"},
    {"id": "fb_002", "recommendation_id": "rec_002", "type": "dislike"},
    {"id": "fb_003", "type": "reply_text", "raw_text": "이직 준비 중이라 시스템 설계가 궁금해요"},
]


def test_pending_is_everything_after_cursor():
    assert [f["id"] for f in memory_agent.pending_feedback(LOG, {})] == ["fb_001", "fb_002", "fb_003"]
    assert [f["id"] for f in memory_agent.pending_feedback(LOG, {"last_feedback_id": "fb_002"})] == ["fb_003"]
    assert memory_agent.pending_feedback(LOG, {"last_feedback_id": "fb_003"}) == []


def test_update_sends_new_feedback_and_advances_cursor(monkeypatch):
    captured = {}

    def fake(prompt, **kwargs):
        captured["prompt"] = prompt
        return {"preferences": ["LLM 평가"], "avoid": ["프론트엔드 스타일링"], "context": ["이직 준비 중"]}

    monkeypatch.setattr(memory_agent.llm, "complete_json", fake)
    memory = memory_agent.update_long_term({"preferences": ["기존 선호"]}, LOG, RECS, VIDEOS)

    assert "좋아요: LLM 평가 파이프라인" in captured["prompt"]
    assert "싫어요: CSS 애니메이션" in captured["prompt"]
    assert "시스템 설계" in captured["prompt"]
    assert "기존 선호" in captured["prompt"]  # 기존 기억 위에 덮어 쓴다
    assert memory["last_feedback_id"] == "fb_003"
    assert memory["avoid"] == ["프론트엔드 스타일링"]


def test_no_llm_call_when_nothing_new(monkeypatch):
    monkeypatch.setattr(memory_agent.llm, "complete_json",
                        lambda *a, **k: pytest.fail("새 피드백이 없으면 LLM 을 부르면 안 된다"))
    memory = {"last_feedback_id": "fb_003", "preferences": ["x"]}
    assert memory_agent.update_long_term(memory, LOG, RECS, VIDEOS) is memory


def test_llm_failure_keeps_cursor_for_retry(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("모델 장애")
    monkeypatch.setattr(memory_agent.llm, "complete_json", boom)
    memory = {"last_feedback_id": "fb_001"}
    assert memory_agent.update_long_term(memory, LOG, RECS, VIDEOS) == memory


def test_items_are_capped(monkeypatch):
    monkeypatch.setattr(memory_agent.llm, "complete_json",
                        lambda *a, **k: {"preferences": [f"p{i}" for i in range(50)]})
    memory = memory_agent.update_long_term({}, LOG, RECS, VIDEOS)
    assert len(memory["preferences"]) == config.LONG_TERM_MAX_ITEMS


def test_channel_only_feedback_moves_cursor_without_llm(monkeypatch):
    monkeypatch.setattr(memory_agent.llm, "complete_json",
                        lambda *a, **k: pytest.fail("취향 정보가 없으면 LLM 을 부르면 안 된다"))
    log = [{"id": "fb_001", "type": "channel-yes"}]
    assert memory_agent.update_long_term({}, log, [], {})["last_feedback_id"] == "fb_001"


def test_prompt_uses_long_term_plus_recent_notes_only(monkeypatch):
    captured = {}
    monkeypatch.setattr(ra.llm, "complete_json",
                        lambda prompt, **k: captured.update(prompt=prompt) or {})
    notes = [{"text": f"메모{i:02d}"} for i in range(20)]
    candidates = [{"id": f"video_{i:03d}", "similarity": 1 - i / 10} for i in range(5)]
    ra.recommend({}, notes, candidates, memory={"avoid": ["프론트엔드 스타일링"]})

    assert "프론트엔드 스타일링" in captured["prompt"]
    assert "메모19" in captured["prompt"]
    assert f"메모{19 - config.SHORT_TERM_N:02d}" not in captured["prompt"]


def test_embedding_text_includes_preferences_not_avoid():
    text = cluster_agent.profile_text({}, [], {"preferences": ["LLM 평가"], "avoid": ["CSS"]})
    assert "LLM 평가" in text and "CSS" not in text
