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
