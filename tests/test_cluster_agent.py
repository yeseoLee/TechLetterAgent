"""매칭 로직 테스트 (임베딩 API 호출 없음)."""
import numpy as np

from src.cluster_agent import _cosine, profile_text

PROFILE = {
    "position": "AI/ML 엔지니어",
    "tech_stack": ["Python"],
    "interests": ["AI 에이전트 / LLM 앱", "테스트 / 품질 자동화"],
    "level": "취준·주니어 (0-2년차)",
}


def test_profile_text_includes_all_fields():
    text = profile_text(PROFILE, [])
    for expected in ["AI/ML 엔지니어", "Python", "AI 에이전트", "0-2년차"]:
        assert expected in text


def test_profile_text_appends_recent_notes():
    notes = [{"text": f"메모{i}"} for i in range(15)]
    text = profile_text(PROFILE, notes)
    assert "메모14" in text          # 최근 메모는 들어가고
    assert "메모0" not in text        # 오래된 메모는 잘린다


def test_profile_text_without_notes_has_no_feedback_line():
    assert "피드백" not in profile_text(PROFILE, [])


def test_cosine_ranks_identical_vector_highest():
    query = np.array([1.0, 0.0, 0.0], dtype="float32")
    matrix = np.array([
        [1.0, 0.0, 0.0],   # 동일 방향
        [0.0, 1.0, 0.0],   # 직교
        [-1.0, 0.0, 0.0],  # 반대
    ], dtype="float32")
    scores = _cosine(query, matrix)
    np.testing.assert_allclose(scores, [1.0, 0.0, -1.0], atol=1e-6)


def test_cosine_ignores_magnitude():
    query = np.array([1.0, 1.0], dtype="float32")
    matrix = np.array([[1.0, 1.0], [100.0, 100.0]], dtype="float32")
    scores = _cosine(query, matrix)
    assert abs(scores[0] - scores[1]) < 1e-6


def test_cosine_survives_zero_vector():
    scores = _cosine(np.array([1.0, 0.0], dtype="float32"),
                     np.array([[0.0, 0.0]], dtype="float32"))
    assert np.isfinite(scores).all()


# --- 제목 중복 제거 ---------------------------------------------------------

from src.cluster_agent import _dedupe_by_title, normalize_title


def test_normalize_ignores_brackets_and_spacing():
    assert normalize_title("[PyCon 2025] 발표 A") == normalize_title("PyCon 2025 발표 A")
    assert normalize_title("Kafka 사용법 (5)") == normalize_title("Kafka 사용법(5)")


def test_normalize_keeps_different_titles_apart():
    assert normalize_title("Kafka 입문") != normalize_title("Kafka 심화")


def test_dedupe_keeps_first_occurrence():
    """유사도 순으로 들어오므로 먼저 오는(더 잘 맞는) 쪽을 남긴다."""
    candidates = [
        {"id": "video_001", "title": "같은 발표 (5)", "similarity": 0.9},
        {"id": "video_002", "title": "같은 발표(5)", "similarity": 0.8},
        {"id": "video_003", "title": "다른 발표", "similarity": 0.7},
    ]
    kept = _dedupe_by_title(candidates, set())
    assert [v["id"] for v in kept] == ["video_001", "video_003"]


def test_dedupe_respects_already_seen_titles():
    candidates = [{"id": "video_001", "title": "이미 추천함", "similarity": 0.9}]
    assert _dedupe_by_title(candidates, {normalize_title("이미 추천함")}) == []


def test_dedupe_drops_empty_titles():
    assert _dedupe_by_title([{"id": "v", "title": "", "similarity": 0.5}], set()) == []
