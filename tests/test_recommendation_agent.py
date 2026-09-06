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


def test_returns_two_near_and_one_far(monkeypatch):
    _patch(monkeypatch, {
        "near": [{"id": "video_001", "reason": "a"}, {"id": "video_002", "reason": "b"}],
        "far": [{"id": "video_005", "reason": "c"}],
    })
    picks = ra.recommend({}, [], CANDIDATES)
    assert len(picks) == 3
    assert sum(p["tier"] == "near" for p in picks) == 2
    assert sum(p["tier"] == "far" for p in picks) == 1


def test_near_is_chosen_by_similarity_not_llm(monkeypatch):
    """near 는 코드가 유사도 순으로 고른다. LLM 이 다른 id 를 줘도 무시된다."""
    _patch(monkeypatch, {
        "near": [{"id": "video_009", "reason": "엉뚱한 선택"},
                 {"id": "video_010", "reason": "엉뚱한 선택"}],
        "far": [],
    })
    picks = ra.recommend({}, [], CANDIDATES)
    near_ids = [p["video_id"] for p in picks if p["tier"] == "near"]
    assert near_ids == ["video_001", "video_002"]  # 유사도 상위 2개


def test_far_pool_excludes_near(monkeypatch):
    near, far_pool = ra.split_pools(CANDIDATES)
    assert [v["id"] for v in near] == ["video_001", "video_002"]
    assert not set(v["id"] for v in near) & set(v["id"] for v in far_pool)


def test_drops_hallucinated_ids_and_backfills(monkeypatch):
    _patch(monkeypatch, {
        "near": [{"id": "video_999", "reason": "없는 영상"}],
        "far": [{"id": "video_888", "reason": "없는 영상"}],
    })
    picks = ra.recommend({}, [], CANDIDATES)
    assert len(picks) == 3
    assert not {"video_999", "video_888"} & {p["video_id"] for p in picks}


def test_deduplicates_across_tiers(monkeypatch):
    _patch(monkeypatch, {
        "near": [{"id": "video_001", "reason": "a"}] * 2,
        "far": [{"id": "video_001", "reason": "a"}],
    })
    picks = ra.recommend({}, [], CANDIDATES)
    ids = [p["video_id"] for p in picks]
    assert len(ids) == len(set(ids)) == 3


def test_truncates_when_llm_returns_too_many(monkeypatch):
    _patch(monkeypatch, {
        "near": [{"id": c["id"], "reason": "x"} for c in CANDIDATES[:8]],
        "far": [{"id": c["id"], "reason": "y"} for c in CANDIDATES[8:]],
    })
    picks = ra.recommend({}, [], CANDIDATES)
    assert sum(p["tier"] == "near" for p in picks) == 2
    assert sum(p["tier"] == "far" for p in picks) == 1


def test_handles_garbage_response(monkeypatch):
    _patch(monkeypatch, ["예상 못 한 리스트"])
    picks = ra.recommend({}, [], CANDIDATES)
    assert len(picks) == 3  # 전부 순위로 채워진다


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
        return {"near": [], "far": []}

    monkeypatch.setattr(ra.llm, "complete_json", fake)
    ra.recommend({}, [], CANDIDATES,
                 {"liked": ["좋았던 발표"], "disliked": ["싫었던 발표"]})
    assert "좋았던 발표" in captured["prompt"]
    assert "싫었던 발표" in captured["prompt"]


def test_no_signal_section_when_empty(monkeypatch):
    captured = {}

    def fake(prompt, **kwargs):
        captured["prompt"] = prompt
        return {"near": [], "far": []}

    monkeypatch.setattr(ra.llm, "complete_json", fake)
    ra.recommend({}, [], CANDIDATES, {"liked": [], "disliked": []})
    assert "지난 추천에 대한 반응" not in captured["prompt"]
