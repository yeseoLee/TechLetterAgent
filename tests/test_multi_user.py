"""유저별 데이터 분리와 단일 유저 데이터 이전 테스트."""
import pytest

from src import config, content_store, memory_agent


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "USERS_DIR", tmp_path / "users")
    # set_user 가 바꿔 끼우는 전역을 테스트 후 원복한다.
    for name in [*config.USER_FILES, "USER_DIR", "RECIPIENT_EMAIL"]:
        monkeypatch.setattr(config, name, getattr(config, name))
    return tmp_path


def test_set_user_points_paths_to_separate_dirs(data_dir):
    config.set_user("a@example.com")
    a = config.USER_PROFILE
    config.set_user("B@Example.com ")
    b = config.USER_PROFILE
    assert a.parent != b.parent
    assert a.parent.parent == b.parent.parent == data_dir / "users"
    assert "example" not in str(a)  # 이메일 원문이 경로에 드러나지 않는다
    assert config.user_key("b@example.com") == b.parent.name


def test_migrates_legacy_files_to_first_user(data_dir):
    content_store.save(data_dir / "user_profile.json", {"position": "백엔드"})
    content_store.save(data_dir / "feedback_log.json", [])
    content_store.save(data_dir / "videos.json", [])  # 공통 파일은 그대로

    memory_agent.migrate_legacy_data("a@example.com")

    config.set_user("a@example.com")
    assert content_store.load(config.USER_PROFILE) == {"position": "백엔드"}
    assert not (data_dir / "user_profile.json").exists()
    assert (data_dir / "videos.json").exists()


def test_migration_does_not_overwrite_existing_user_dir(data_dir):
    content_store.save(data_dir / "user_profile.json", {"position": "옛날"})
    config.set_user("a@example.com")
    content_store.save(config.USER_PROFILE, {"position": "현재"})

    memory_agent.migrate_legacy_data("a@example.com")
    assert content_store.load(config.USER_PROFILE) == {"position": "현재"}
