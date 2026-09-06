"""답장 파싱 유틸 테스트 (네트워크 없음)."""
from email.message import EmailMessage

from src.email_client import _decode, _imap_date, _plain_text, strip_quoted


def test_strips_gmail_english_quote():
    body = "1번 좋았어요\n\nOn Mon, Sep 7, 2026 at 9:00 AM TechLetterAgent wrote:\n> 원본 내용"
    assert strip_quoted(body) == "1번 좋았어요"


def test_strips_gmail_korean_quote():
    body = "백엔드가 더 궁금해요\n\n2026년 9월 7일 (월) 오전 9:00, TechLetterAgent 작성:\n> 원본"
    assert strip_quoted(body) == "백엔드가 더 궁금해요"


def test_strips_bare_quote_lines():
    assert strip_quoted("짧은 답장\n> 인용된 원본") == "짧은 답장"


def test_keeps_body_without_quotes():
    assert strip_quoted("인용 없는 답장입니다") == "인용 없는 답장입니다"


def test_decodes_mime_encoded_subject():
    encoded = "=?UTF-8?B?7YWM7Iqk7Yq4?="  # "테스트"
    assert _decode(encoded) == "테스트"


def test_decode_handles_none():
    assert _decode(None) == ""


def test_extracts_plain_text_from_multipart():
    message = EmailMessage()
    message.set_content("평문 본문")
    message.add_alternative("<p>HTML 본문</p>", subtype="html")
    assert "평문 본문" in _plain_text(message)


def test_falls_back_to_html_when_no_plain_part():
    message = EmailMessage()
    message.set_content("<p>HTML만 있음</p>", subtype="html")
    assert "HTML만 있음" in _plain_text(message)


def test_imap_date_format():
    assert _imap_date("2026-09-07T00:00:00+00:00") == "06-Sep-2026"  # 하루 앞으로


def test_imap_date_falls_back_when_empty():
    # 형식이 깨져도 예외 없이 기본값(30일 전)을 쓴다.
    assert len(_imap_date("")) == 11
