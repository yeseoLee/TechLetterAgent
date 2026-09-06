"""Newsletter Agent — 추천 결과를 이메일 본문(HTML + 텍스트)으로 포맷팅한다.

영상별 구성: 제목 + 1~2줄 요약 + 추천 이유 + 👍/👎 mailto 링크.
영어 영상이라도 요약/추천 이유는 한국어로 생성된 값을 그대로 쓴다.
"""


def feedback_mailto(recommendation_id: str, verdict: str, to_addr: str) -> str:
    """클릭하면 `[TLA] like rec_004` 같은 제목의 답장 메일이 열리는 mailto 링크."""
    raise NotImplementedError


def render(recommendations: list[dict], videos_by_id: dict[str, dict]) -> tuple[str, str, str]:
    """반환: (subject, html_body, text_body)."""
    raise NotImplementedError
