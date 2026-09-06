"""이메일 렌더링 테스트."""
from urllib.parse import parse_qs, unquote, urlparse

from src.newsletter_agent import SUBJECT_TAG, feedback_mailto, render

VIDEOS = {
    "video_001": {"id": "video_001", "title": "테스트 하네스 구축하기",
                  "url": "https://youtu.be/aaa", "channel": "NAVER D2",
                  "difficulty": "중급", "duration_sec": 1931, "summary": "요약입니다."},
    "video_002": {"id": "video_002", "title": "PDF & <script>alert(1)</script>",
                  "url": "https://youtu.be/bbb", "channel": "kakao",
                  "difficulty": "고급", "duration_sec": 600, "summary": "다른 요약."},
}
PICKS = [
    {"id": "rec_001", "video_id": "video_001", "tier": "strong", "reason_text": "잘 맞습니다."},
    {"id": "rec_002", "video_id": "video_002", "tier": "maybe", "reason_text": "혹시 몰라서."},
]


def test_mailto_encodes_subject():
    link = feedback_mailto("rec_004", "like", "me@example.com")
    parsed = urlparse(link)
    assert parsed.path == "me@example.com"
    subject = parse_qs(parsed.query)["subject"][0]
    assert subject == f"{SUBJECT_TAG} like rec_004"
    # 공백과 대괄호가 인코딩되어 메일 클라이언트가 제목을 온전히 받는다.
    assert " " not in parsed.query and "[" not in parsed.query


def test_render_includes_every_pick():
    _, html, text = render(PICKS, VIDEOS, "me@example.com")
    for body in (html, text):
        assert "테스트 하네스 구축하기" in body
        assert "잘 맞습니다." in body
        assert "혹시 몰라서." in body


def test_render_separates_tiers():
    _, html, _ = render(PICKS, VIDEOS, "me@example.com")
    assert html.index("추천") < html.index("함께 볼 만한")


def test_render_escapes_html_in_titles():
    _, html, _ = render(PICKS, VIDEOS, "me@example.com")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_subject_mentions_top_pick():
    subject, _, _ = render(PICKS, VIDEOS, "me@example.com")
    assert "테스트 하네스" in subject


def test_both_feedback_links_present_per_card():
    _, html, _ = render(PICKS, VIDEOS, "me@example.com")
    for rec_id in ("rec_001", "rec_002"):
        assert unquote(html).count(f"{SUBJECT_TAG} like {rec_id}") == 1
        assert unquote(html).count(f"{SUBJECT_TAG} dislike {rec_id}") == 1


def test_handles_missing_video_gracefully():
    _, html, text = render([{"id": "rec_009", "video_id": "없음",
                             "tier": "strong", "reason_text": "이유"}], {}, "me@example.com")
    assert "이유" in html and "이유" in text


def test_handles_missing_duration():
    video = {**VIDEOS["video_001"], "duration_sec": None}
    _, html, _ = render(PICKS[:1], {"video_001": video}, "me@example.com")
    assert "길이 미상" in html
