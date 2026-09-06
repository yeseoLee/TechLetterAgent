"""규칙 기반 사전 필터 테스트 (LLM 호출 없음)."""
from src.prefilter import rule_check

TALK = 40 * 60


def _v(title, duration=TALK):
    return {"title": title, "duration_sec": duration}


def test_rejects_non_talk_titles():
    for title in [
        "[Playlist] 커피 향 가득☕️ Park BGM 카페 플레이리스트",
        "WOOWACON 2025 현장 스케치 #우아콘2025",
        "[토스] 2026 토스 Frontend 대규모 채용 웨비나",
    ]:
        passed, reason = rule_check(_v(title))
        assert not passed, f"걸러졌어야 함: {title} ({reason})"


def test_keeps_real_talks():
    for title in [
        "AI 에이전트를 위한 Playwright E2E 테스트 하네스 구축하기",
        "[PyCon Korea 2025] CodeStrike: 사이버 공격을 위한 Python",
        "토스ㅣSLASH 22 - 물 흐르듯 자연스러운 ML 서비스 만들기",
    ]:
        passed, reason = rule_check(_v(title))
        assert passed, f"통과했어야 함: {title} ({reason})"


def test_allow_keyword_overrides_deny():
    # '인터뷰'는 deny 지만 '키노트'가 있으면 살린다.
    passed, _ = rule_check(_v("Tech-Verse 2026 Keynote 인터뷰 세션"))
    assert passed


def test_duration_bounds():
    assert not rule_check(_v("좋은 발표", duration=90))[0]
    assert not rule_check(_v("좋은 발표", duration=5 * 60 * 60))[0]
    assert rule_check(_v("좋은 발표", duration=None))[0]


def test_real_feed_samples():
    """실제 피드에서 확인한 케이스 (수집 검증 때 얻은 실제 제목/길이)."""
    drops = [
        ("공익을 위해 공개하는 청음회 현장 모먼트🧡", 12),
        ("[ifkakao2021] if(kakao)2021 Overview", 107),
        ("WOOWACON 2025 현장 스케치 #우아콘2025", 119),
        ("[당근X박브금] 찐당근 비하인드 대방출🔥🥕🔥", 140),
        ("[Playlist] 커피 향 가득☕️ Park BGM 카페 플레이리스트", 1283),
    ]
    for title, duration in drops:
        assert not rule_check(_v(title, duration))[0], f"걸러졌어야 함: {title}"

    keeps = [
        ("오프닝 키노트 #우아콘2025 #우아한형제들", 1003),
        ("AI 네이티브 회사를 향한 새로운 항해 #우아콘2025", 2126),
        ("[ifkakao2021] 카카오지갑 지갑서비스의 현황", 688),
        ("AI 에이전트를 위한 Playwright E2E 테스트 하네스 구축하기", 1931),
    ]
    for title, duration in keeps:
        assert rule_check(_v(title, duration))[0], f"통과했어야 함: {title}"
