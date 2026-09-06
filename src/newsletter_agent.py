"""Newsletter Agent — 추천 결과를 이메일 본문(HTML + 플레인텍스트)으로 만든다.

영상별 구성: 제목 + 요약 + 추천 이유 + 👍/👎 피드백 링크.
"왜 나한테 추천됐는지"가 이 뉴스레터의 핵심 가치라 추천 이유를 항상 넣는다.

피드백은 mailto 링크로 받는다. 서버가 없어 클릭 트래킹을 할 수 없으므로,
클릭하면 정해진 제목의 답장 메일이 열리고 그 답장을 feedback_agent 가 읽는다.
"""
from datetime import datetime, timezone
from urllib.parse import quote

# 답장 제목 규칙. feedback_agent 가 이 접두사로 정형 피드백을 알아본다.
SUBJECT_TAG = "[TLA]"

TIER_NEAR, TIER_FAR = "near", "far"

TIER_LABEL = {"near": "추천", "far": "넓혀보기"}

_CSS = """
body { margin:0; padding:0; background:#f6f7f9;
       font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
       color:#1a1d21; }
.wrap { max-width:640px; margin:0 auto; padding:24px 16px 40px; }
h1 { font-size:20px; margin:0 0 4px; }
.sub { color:#6b7280; font-size:13px; margin:0 0 24px; }
.section { font-size:13px; font-weight:700; color:#6b7280; letter-spacing:.04em;
           margin:28px 0 12px; text-transform:uppercase; }
.card { background:#fff; border:1px solid #e5e7eb; border-radius:10px;
        padding:18px 20px; margin-bottom:14px; }
.card h2 { font-size:16px; line-height:1.45; margin:0 0 8px; }
.card h2 a { color:#111827; text-decoration:none; }
.meta { font-size:12px; color:#6b7280; margin:0 0 12px; }
.meta span { margin-right:10px; }
.summary { font-size:14px; line-height:1.65; margin:0 0 12px; color:#374151; }
.reason { font-size:14px; line-height:1.65; margin:0; padding:12px 14px;
          background:#f0f4ff; border-left:3px solid #4f6ef7; border-radius:0 6px 6px 0;
          color:#25314d; }
.reason b { color:#1e293b; }
.actions { margin-top:14px; font-size:13px; }
.actions a { display:inline-block; padding:6px 14px; margin-right:8px;
             border:1px solid #d1d5db; border-radius:6px;
             text-decoration:none; color:#374151; background:#fafafa; }
.footer { margin-top:32px; font-size:12px; color:#6b7280; line-height:1.7; }
.discover { margin-top:28px; padding:18px 20px; background:#fff;
            border:1px dashed #cbd5e1; border-radius:10px; }
.discover h3 { font-size:14px; margin:0 0 8px; color:#111827; }
.discover p { font-size:13px; line-height:1.65; margin:0 0 12px; color:#4b5563; }
"""


def feedback_mailto(target_id: str, verdict: str, to_addr: str) -> str:
    """클릭하면 정해진 제목의 답장 메일이 열리는 mailto 링크.

    서버가 없어 클릭 트래킹을 못 하므로, 클릭 자체를 메일 한 통으로 바꾼다.
    verdict 는 like / dislike / channel-yes / channel-no.
    """
    subject = f"{SUBJECT_TAG} {verdict} {target_id}"
    return f"mailto:{to_addr}?subject={quote(subject)}"


def _minutes(video: dict) -> str:
    seconds = video.get("duration_sec") or 0
    return f"{round(seconds / 60)}분" if seconds else "길이 미상"


def _card(pick: dict, video: dict, to_addr: str) -> str:
    rec_id = pick.get("id") or pick["video_id"]
    like = feedback_mailto(rec_id, "like", to_addr)
    dislike = feedback_mailto(rec_id, "dislike", to_addr)
    return f"""
    <div class="card">
      <h2><a href="{video.get('url', '#')}">{_escape(video.get('title', ''))}</a></h2>
      <p class="meta">
        <span>{_escape(video.get('channel', ''))}</span>
        <span>{_escape(video.get('difficulty', ''))}</span>
        <span>{_minutes(video)}</span>
      </p>
      <p class="summary">{_escape(video.get('summary', ''))}</p>
      <p class="reason"><b>추천 이유</b><br>{_escape(pick.get('reason_text', ''))}</p>
      <p class="actions">
        <a href="{like}">👍 좋아요</a>
        <a href="{dislike}">👎 별로예요</a>
      </p>
    </div>"""


def _escape(text: str) -> str:
    return (str(text or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def discovery_block(proposal: dict, to_addr: str) -> str:
    """새 채널 제안과 예/아니오 링크."""
    channel_id = proposal["channel_id"]
    yes = feedback_mailto(channel_id, "channel-yes", to_addr)
    no = feedback_mailto(channel_id, "channel-no", to_addr)
    return f"""
    <div class="discover">
      <h3>새 채널 추가할까요?</h3>
      <p>
        <b>{_escape(proposal['name'])}</b>
        · 구독자 {proposal.get('subscriber_count', 0):,}
        · 영상 {proposal.get('video_count', 0):,}개<br>
        {_escape(proposal.get('reason', ''))}
      </p>
      <p class="actions">
        <a href="{yes}">예, 추가할게요</a>
        <a href="{no}">아니오</a>
      </p>
    </div>"""


def render(picks: list[dict], videos_by_id: dict[str, dict],
           to_addr: str = "", proposal: dict | None = None) -> tuple[str, str, str]:
    """반환: (subject, html_body, text_body)."""
    today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
    subject = f"Weekly Tech Session {len(picks)}편"

    sections = []
    for tier in (TIER_NEAR, TIER_FAR):
        tier_picks = [p for p in picks if p["tier"] == tier]
        if not tier_picks:
            continue
        cards = "".join(_card(p, videos_by_id.get(p["video_id"], {}), to_addr)
                        for p in tier_picks)
        sections.append(f'<p class="section">{TIER_LABEL[tier]}</p>{cards}')

    discover = discovery_block(proposal, to_addr) if proposal else ""

    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><style>{_CSS}</style></head>
<body><div class="wrap">
  <h1>Weekly Tech Session</h1>
  <p class="sub">{today} · {len(picks)}편</p>
  {"".join(sections)}
  {discover}
  <p class="footer">
    답장으로 의견을 남기면 다음 추천에 반영합니다.
  </p>
</div></body></html>"""

    return subject, html, _text_body(picks, videos_by_id, today, proposal)


def _text_body(picks: list[dict], videos_by_id: dict[str, dict], today: str,
               proposal: dict | None = None) -> str:
    """HTML 을 못 보는 클라이언트를 위한 대체 본문."""
    lines = [f"Weekly Tech Session · {today} · {len(picks)}편", ""]
    for tier in (TIER_NEAR, TIER_FAR):
        tier_picks = [p for p in picks if p["tier"] == tier]
        if not tier_picks:
            continue
        lines.append(f"[{TIER_LABEL[tier]}]")
        for pick in tier_picks:
            video = videos_by_id.get(pick["video_id"], {})
            lines += [
                f"  {video.get('title', '')}",
                f"  {video.get('channel', '')} · {video.get('difficulty', '')} · {_minutes(video)}",
                f"  {video.get('summary', '')}",
                f"  추천 이유: {pick.get('reason_text', '')}",
                f"  {video.get('url', '')}",
                "",
            ]
    if proposal:
        lines += [
            "[새 채널 추가할까요?]",
            f"  {proposal['name']} · 영상 {proposal.get('video_count', 0):,}개",
            f"  {proposal.get('reason', '')}",
            f"  예: 제목에 '{SUBJECT_TAG} channel-yes {proposal['channel_id']}' 로 답장",
            f"  아니오: '{SUBJECT_TAG} channel-no {proposal['channel_id']}'",
            "",
        ]
    lines.append("답장으로 의견을 남기면 다음 추천에 반영합니다.")
    return "\n".join(lines)
