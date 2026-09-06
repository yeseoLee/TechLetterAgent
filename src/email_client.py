"""이메일 송수신 — 본인 Gmail 계정에 앱 비밀번호로 SMTP/IMAP 접속한다.

Gmail API(OAuth) 대신 이 방식을 쓰는 이유: 사용자가 한 명이라 OAuth 동의 화면,
심사, refresh token 7일 만료를 감수할 이유가 없다. 앱 비밀번호는 secret 하나로
끝나고 만료되지 않으며, 표준 라이브러리만 쓴다.

답장 식별: 발송할 때 Message-ID 를 직접 만들어 recommendations.json 에 남기고,
답장의 In-Reply-To / References 헤더에서 그 값을 찾는다. 헤더가 없는 클라이언트도
있어서 제목의 [TLA] 접두사로도 잡는다.
"""
import email
import imaplib
import logging
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import make_msgid, parsedate_to_datetime

from . import config

log = logging.getLogger(__name__)

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465
IMAP_HOST = "imap.gmail.com"

# 인용문 시작 지점. 이 뒤는 원본 메일이라 피드백에서 잘라낸다.
_QUOTE_MARKERS = [
    re.compile(r"^\s*>"),
    re.compile(r"^On .+ wrote:\s*$"),
    re.compile(r"^\d{4}년 .+ 작성:\s*$"),
    re.compile(r"^-+\s*(Original Message|원본 메일)\s*-+", re.IGNORECASE),
]


def _credentials() -> tuple[str, str]:
    if not (config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD):
        raise RuntimeError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD 가 설정되지 않았습니다.")
    return config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD


def send(subject: str, html_body: str, text_body: str, to_addr: str | None = None) -> str:
    """뉴스레터를 발송하고 Message-ID 를 반환한다.

    반환값을 recommendations.json 에 남겨두면 나중에 답장을 스레드로 되짚을 수 있다.
    """
    address, password = _credentials()
    to_addr = to_addr or address

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"TechLetterAgent <{address}>"
    message["To"] = to_addr
    message_id = make_msgid(domain="techletteragent.local")
    message["Message-ID"] = message_id

    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.login(address, password)
        smtp.send_message(message)

    log.info("발송 완료 → %s (%s)", to_addr, message_id)
    return message_id


def fetch_replies_since(since_iso: str = "", known_message_ids: set[str] | None = None,
                        seen_reply_ids: set[str] | None = None) -> list[dict]:
    """지난 발송 이후 도착한 답장을 가져온다.

    반환: [{message_id, subject, body, received_at, in_reply_to}, ...]
    """
    address, password = _credentials()
    known_message_ids = known_message_ids or set()
    seen_reply_ids = seen_reply_ids or set()

    since = _imap_date(since_iso)
    replies: list[dict] = []

    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(address, password)
        imap.select("INBOX", readonly=True)

        # 본인이 본인에게 보낸 답장이므로 FROM 으로 좁힌다.
        status, data = imap.search(None, "FROM", f'"{address}"', "SINCE", since)
        if status != "OK":
            log.warning("IMAP 검색 실패: %s", status)
            return []

        for uid in (data[0].split() if data and data[0] else []):
            status, raw = imap.fetch(uid, "(RFC822)")
            if status != "OK" or not raw or not raw[0]:
                continue

            message = email.message_from_bytes(raw[0][1])
            message_id = (message.get("Message-ID") or "").strip()
            if message_id in seen_reply_ids:
                continue

            subject = _decode(message.get("Subject"))
            references = f"{message.get('In-Reply-To', '')} {message.get('References', '')}"

            is_reply = any(mid and mid in references for mid in known_message_ids)
            is_tagged = subject.strip().startswith("[TLA]")
            if not (is_reply or is_tagged):
                continue

            replies.append({
                "message_id": message_id,
                "subject": subject,
                "body": strip_quoted(_plain_text(message)),
                "received_at": _received_at(message),
                "in_reply_to": (message.get("In-Reply-To") or "").strip(),
            })

    log.info("답장 %d건 수집", len(replies))
    return replies


def _imap_date(since_iso: str) -> str:
    """IMAP SINCE 는 DD-Mon-YYYY 형식만 받는다. 경계 누락을 막으려 하루 앞으로 잡는다."""
    try:
        moment = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        moment = datetime.now(timezone.utc) - timedelta(days=30)
    return (moment - timedelta(days=1)).strftime("%d-%b-%Y")


def _decode(value: str | None) -> str:
    """MIME 인코딩된 헤더를 사람이 읽는 문자열로 되돌린다."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (UnicodeDecodeError, LookupError):
        return value


def _plain_text(message: email.message.Message) -> str:
    """멀티파트에서 text/plain 을 꺼낸다. 없으면 text/html 에서 태그를 걷어낸다."""
    plain, html = "", ""
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get_filename():
            continue
        try:
            content = part.get_payload(decode=True) or b""
            text = content.decode(part.get_content_charset() or "utf-8", errors="replace")
        except (LookupError, ValueError):
            continue
        if part.get_content_type() == "text/plain" and not plain:
            plain = text
        elif part.get_content_type() == "text/html" and not html:
            html = text

    if plain:
        return plain
    return re.sub(r"<[^>]+>", " ", html)


def strip_quoted(body: str) -> str:
    """인용된 원본 메일을 잘라내고 사용자가 새로 쓴 부분만 남긴다."""
    lines = []
    for line in body.splitlines():
        if any(marker.match(line) for marker in _QUOTE_MARKERS):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _received_at(message: email.message.Message) -> str:
    try:
        return parsedate_to_datetime(message.get("Date")).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
