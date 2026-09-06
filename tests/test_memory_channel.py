"""채널 승인/거절이 화이트리스트에 반영되는지 (임시 디렉터리에서)."""
import json

import pytest

from src import config, content_store, memory_agent


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    channels = tmp_path / "channels.json"
    discoveries = tmp_path / "discoveries.json"
    content_store.save(channels, {"channels": [
        {"name": "기존 채널", "channel_id": "UCknown", "language": "ko"}]})
    content_store.save(discoveries, [
        {"channel_id": "UCnew", "name": "새 채널", "language": "en", "answer": None}])
    monkeypatch.setattr(config, "CHANNELS", channels)
    monkeypatch.setattr(config, "DISCOVERIES", discoveries)
    return channels, discoveries


def test_yes_appends_to_whitelist(sandbox):
    channels, _ = sandbox
    assert memory_agent.apply_channel_answer("UCnew", True) is True
    ids = [c["channel_id"] for c in json.loads(channels.read_text())["channels"]]
    assert ids == ["UCknown", "UCnew"]


def test_yes_preserves_name_and_language(sandbox):
    channels, _ = sandbox
    memory_agent.apply_channel_answer("UCnew", True)
    added = json.loads(channels.read_text())["channels"][-1]
    assert added["name"] == "새 채널" and added["language"] == "en"


def test_no_does_not_touch_whitelist(sandbox):
    channels, discoveries = sandbox
    assert memory_agent.apply_channel_answer("UCnew", False) is False
    assert len(json.loads(channels.read_text())["channels"]) == 1
    # 거절도 기록해야 같은 채널을 다시 제안하지 않는다.
    assert json.loads(discoveries.read_text())[0]["answer"] == "no"


def test_yes_is_idempotent(sandbox):
    channels, _ = sandbox
    memory_agent.apply_channel_answer("UCnew", True)
    assert memory_agent.apply_channel_answer("UCnew", True) is False
    assert len(json.loads(channels.read_text())["channels"]) == 2


def test_answer_for_unproposed_channel_is_recorded(sandbox):
    _, discoveries = sandbox
    memory_agent.apply_channel_answer("UCsurprise", False)
    ids = [d["channel_id"] for d in json.loads(discoveries.read_text())]
    assert "UCsurprise" in ids
