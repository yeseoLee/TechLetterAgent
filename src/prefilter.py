"""사전 필터 — 수집된 영상 중 '기술 발표/강연'이 아닌 것을 걸러낸다.

화이트리스트 채널이라도 비발표 콘텐츠가 섞인다(당근의 BGM 플레이리스트,
토스 챌린저스의 채용 웨비나, 우아콘 재생목록의 현장 스케치 등).
자막 추출과 LLM 분석은 둘 다 비싼 단계라 그 앞에서 쳐낸다.

2단계 구성:
  stage 1 (`rule_check`)  — 무료. 길이 + 제목 키워드로 명백한 것만 제거.
  stage 2 (`llm_check`)   — stage 1 통과분만. 무료 모델 요청 한도를 아끼기 위한 순서.
"""
import re

from . import config

# 제목에 들어가면 발표가 아니라고 보는 키워드.
TITLE_DENY = [
    # 음악 / 분위기 콘텐츠
    "플레이리스트", "playlist", "bgm", "asmr", "브이로그", "vlog",
    # 행사 홍보 / 스케치
    "현장 스케치", "스케치", "티저", "teaser", "예고", "하이라이트", "highlight",
    "메이킹", "비하인드", "behind", "다시 보기 안내", "사전등록", "모집 안내",
    # 채용 / 브랜딩
    "채용", "리크루팅", "recruit", "웨비나", "인터뷰", "컬처", "culture",
    "회사 소개", "오피스 투어", "office tour", "신입사원", "온보딩 후기",
    # 짧은 포맷
    "#shorts", "shorts",
]

# 위 키워드가 있어도 발표일 가능성이 높으면 살려두는 예외.
TITLE_ALLOW = [
    "발표", "세션", "session", "talk", "keynote", "키노트",
    "튜토리얼", "tutorial", "라이브 코딩",
]

# 발표로 보기엔 너무 짧거나 긴 영상 (초).
MIN_DURATION_SEC = 8 * 60
MAX_DURATION_SEC = 3 * 60 * 60

_NORMALIZE = re.compile(r"[\s\-_·|/\[\]()]+")


def _normalized(text: str) -> str:
    return _NORMALIZE.sub(" ", text.lower())


def rule_check(video: dict) -> tuple[bool, str]:
    """규칙 기반 1차 판정. 반환: (통과 여부, 사유)."""
    title = _normalized(video.get("title", ""))

    if any(a in title for a in TITLE_ALLOW):
        pass  # 명시적으로 발표라고 표시된 영상은 키워드 검사를 건너뛴다.
    elif hit := next((d for d in TITLE_DENY if d in title), None):
        return False, f"제목 키워드: {hit}"

    duration = video.get("duration_sec")
    if duration is None:
        return True, "길이 정보 없음, 통과"
    if duration < MIN_DURATION_SEC:
        return False, f"너무 짧음: {duration}초"
    if duration > MAX_DURATION_SEC:
        return False, f"너무 김: {duration}초"

    return True, "통과"


def llm_check(video: dict) -> tuple[bool, str]:
    """규칙으로 판단이 안 되는 영상을 config.MODEL_CHEAP 로 판정한다.

    제목 + 채널명 + 설명 앞부분만 넣는다 (자막 추출 전 단계이므로).
    반환: (기술 발표인지 여부, 사유).
    """
    raise NotImplementedError


def is_talk(video: dict, *, use_llm: bool = True) -> tuple[bool, str]:
    """rule_check → llm_check 순으로 판정한다."""
    passed, reason = rule_check(video)
    if not passed:
        return False, reason
    if not use_llm:
        return True, reason
    return llm_check(video)
