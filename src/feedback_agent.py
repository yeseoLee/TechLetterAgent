"""Feedback Agent — 답장 텍스트를 OpenRouter 무료 모델(config.MODEL_CHEAP)로 파싱해 프로필 diff 와 메모를 제안한다.

두 종류의 답장을 모두 처리한다:
  1) mailto 버튼으로 온 정형 답장 (제목: `[TLA] like rec_004`)
  2) 자유 텍스트 답장 ("프론트엔드보다 백엔드가 더 궁금해요")
"""


def parse_reply(reply: dict, profile: dict) -> dict:
    """반환: {profile_diff: {...}, note_text: str|None, likes: [...], dislikes: [...]}"""
    raise NotImplementedError
