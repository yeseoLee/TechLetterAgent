"""추천 결과 정규화 테스트 (LLM 호출은 대체한다)."""
import pytest

from src import recommendation_agent as ra

CANDIDATES = [
    {"id": f"video_{i:03d}", "title": f"발표 {i}", "channel": "테스트",
     "difficulty": "중급", "duration_sec": 1800, "target_audience": "백엔드",
     "summary": "요약", "similarity": 1.0 - i * 0.01}
    for i in range(1, 11)
]


def _patch(monkeypatch, payload):
    monkeypatch.setattr(ra.llm, "complete_json", lambda *a, **k: payload)


def test_returns_exact_counts(monkeypatch):
    _patch(monkeypatch, {
        "strong": [{"id": "video_001", "reason": "a"}, {"id": "video_002", "reason": "b"},
                   {"id": "video_003", "reason": "c"}],
        "maybe": [{"id": "video_004", "reason": "d"}, {"id": "video_005", "reason": "e"}],
    })
    picks = ra.recommend({}, [], CANDIDATES)
    assert len(picks) == 5
    assert sum(p["tier"] == "strong" for p in picks) == 3
    assert sum(p["tier"] == "maybe" for p in picks) == 2


def test_drops_hallucinated_ids_and_backfills(monkeypatch):
    _patch(monkeypatch, {
        "strong": [{"id": "video_999", "reason": "없는 영상"}, {"id": "video_002", "reason": "b"}],
        "maybe": [],
    })
    picks = ra.recommend({}, [], CANDIDATES)
    assert len(picks) == 5
    assert "video_999" not in {p["video_id"] for p in picks}
    assert sum(p["tier"] == "strong" for p in picks) == 3


def test_deduplicates_across_tiers(monkeypatch):
    _patch(monkeypatch, {
        "strong": [{"id": "video_001", "reason": "a"}] * 3,
        "maybe": [{"id": "video_001", "reason": "a"}, {"id": "video_002", "reason": "b"}],
    })
    picks = ra.recommend({}, [], CANDIDATES)
    ids = [p["video_id"] for p in picks]
    assert len(ids) == len(set(ids)) == 5


def test_truncates_when_llm_returns_too_many(monkeypatch):
    _patch(monkeypatch, {
        "strong": [{"id": c["id"], "reason": "x"} for c in CANDIDATES[:8]],
        "maybe": [{"id": c["id"], "reason": "y"} for c in CANDIDATES[8:]],
    })
    picks = ra.recommend({}, [], CANDIDATES)
    assert sum(p["tier"] == "strong" for p in picks) == 3
    assert sum(p["tier"] == "maybe" for p in picks) == 2


def test_handles_garbage_response(monkeypatch):
    _patch(monkeypatch, ["예상 못 한 리스트"])
    picks = ra.recommend({}, [], CANDIDATES)
    assert len(picks) == 5  # 전부 유사도 순으로 채워진다


def test_empty_candidates_returns_empty(monkeypatch):
    _patch(monkeypatch, {"strong": [], "maybe": []})
    assert ra.recommend({}, [], []) == []


# --- 좋아요/싫어요 신호 ----------------------------------------------------

VIDEOS_BY_ID = {
    "video_001": {"title": "Playwright E2E 테스트 하네스"},
    "video_002": {"title": "프롬프트 자동화 파이프라인"},
    "video_003": {"title": "쿠버네티스 네트워킹 심화"},
}
RECS = [
    {"id": "rec_001", "video_id": "video_001"},
    {"id": "rec_002", "video_id": "video_002"},
    {"id": "rec_003", "video_id": "video_003"},
]


def test_collect_signals_splits_like_and_dislike():
    log = [
        {"recommendation_id": "rec_001", "type": "like"},
        {"recommendation_id": "rec_003", "type": "dislike"},
    ]
    signals = ra.collect_signals(log, RECS, VIDEOS_BY_ID)
    assert signals["liked"] == ["Playwright E2E 테스트 하네스"]
    assert signals["disliked"] == ["쿠버네티스 네트워킹 심화"]


def test_collect_signals_ignores_free_text_type():
    log = [{"recommendation_id": "rec_001", "type": "reply_text"}]
    signals = ra.collect_signals(log, RECS, VIDEOS_BY_ID)
    assert signals == {"liked": [], "disliked": []}


def test_collect_signals_skips_unknown_recommendation():
    log = [{"recommendation_id": "rec_999", "type": "like"}]
    assert ra.collect_signals(log, RECS, VIDEOS_BY_ID)["liked"] == []


def test_collect_signals_deduplicates_and_caps():
    log = [{"recommendation_id": "rec_001", "type": "like"} for _ in range(5)]
    assert ra.collect_signals(log, RECS, VIDEOS_BY_ID, limit=2)["liked"] == [
        "Playwright E2E 테스트 하네스"]


def test_signals_reach_the_prompt(monkeypatch):
    captured = {}

    def fake(prompt, **kwargs):
        captured["prompt"] = prompt
        return {"strong": [], "maybe": []}

    monkeypatch.setattr(ra.llm, "complete_json", fake)
    ra.recommend({}, [], CANDIDATES,
                 {"liked": ["좋았던 발표"], "disliked": ["싫었던 발표"]})
    assert "좋았던 발표" in captured["prompt"]
    assert "싫었던 발표" in captured["prompt"]


def test_no_signal_section_when_empty(monkeypatch):
    captured = {}

    def fake(prompt, **kwargs):
        captured["prompt"] = prompt
        return {"strong": [], "maybe": []}

    monkeypatch.setattr(ra.llm, "complete_json", fake)
    ra.recommend({}, [], CANDIDATES, {"liked": [], "disliked": []})
    assert "지난 추천에 대한 반응" not in captured["prompt"]
