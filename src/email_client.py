"""Gmail API 래퍼 — 발송과 답장 조회 모두 담당한다.

인증: GitHub Secrets 의 GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN 으로
액세스 토큰을 갱신해서 사용한다 (scripts/gmail_oauth_setup.py 로 최초 1회 발급).
"""

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def build_service():
    """refresh token 으로 Gmail API 서비스 객체를 만든다."""
    raise NotImplementedError


def send(subject: str, html_body: str, text_body: str, to_addr: str) -> str:
    """뉴스레터를 발송하고 gmail message id 를 반환."""
    raise NotImplementedError


def fetch_replies_since(last_sent_at: str) -> list[dict]:
    """이전 발송 스레드에 달린 새 답장을 조회한다. 반환: [{thread_id, body, received_at}, ...]"""
    raise NotImplementedError
