"""프로필 갱신 로직 테스트."""
from src.memory_agent import add_note, apply_diff

PROFILE = {
    "position": "AI/ML 엔지니어",
    "tech_stack": ["Python"],
    "interests": ["AI 에이전트 / LLM 앱", "테스트 / 품질 자동화"],
    "level": "취준·주니어 (0-2년차)",
    "language": ["ko", "en"],
}


def test_adds_and_removes_list_items():
    updated = apply_diff(PROFILE, {"interests": ["+분산시스템", "-테스트 / 품질 자동화"]})
    assert "분산시스템" in updated["interests"]
    assert "테스트 / 품질 자동화" not in updated["interests"]
    # 언급되지 않은 항목은 그대로 남는다 — 답장 한 줄로 관심사가 통째로 날아가면 안 된다.
    assert "AI 에이전트 / LLM 앱" in updated["interests"]


def test_scalar_field_is_replaced():
    assert apply_diff(PROFILE, {"level": "3-5년차"})["level"] == "3-5년차"


def test_ignores_unknown_fields():
    updated = apply_diff(PROFILE, {"salary": "비밀", "position": "백엔드"})
    assert "salary" not in updated
    assert updated["position"] == "백엔드"


def test_does_not_duplicate_existing_item():
    updated = apply_diff(PROFILE, {"tech_stack": ["+Python"]})
    assert updated["tech_stack"] == ["Python"]


def test_bare_item_is_treated_as_addition():
    assert "Go" in apply_diff(PROFILE, {"tech_stack": ["Go"]})["tech_stack"]


def test_empty_diff_only_bumps_timestamp():
    updated = apply_diff(PROFILE, {})
    assert updated["interests"] == PROFILE["interests"]
    assert "updated_at" in updated


def test_original_profile_is_not_mutated():
    apply_diff(PROFILE, {"interests": ["-AI 에이전트 / LLM 앱"]})
    assert "AI 에이전트 / LLM 앱" in PROFILE["interests"]


def test_add_note_assigns_sequential_ids():
    notes = add_note([], "백엔드가 더 궁금해요", "rec_001")
    notes = add_note(notes, "두 번째")
    assert [n["id"] for n in notes] == ["note_001", "note_002"]
    assert notes[0]["source_recommendation_id"] == "rec_001"
    assert notes[1]["source_recommendation_id"] is None
