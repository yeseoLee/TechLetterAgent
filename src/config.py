"""공통 설정: 경로, 환경변수, 모델 ID."""
import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"

# 전 유저 공통: 영상 메타데이터와 임베딩.
VIDEOS = DATA_DIR / "videos.json"
EMBEDDINGS = DATA_DIR / "embeddings.json"  # video_id -> float32 base64

# 유저별 상태는 data/users/<user_key>/ 아래에 둔다. 아래 경로는 set_user() 가
# 현재 처리 중인 유저 것으로 바꿔 끼운다. 실행은 유저 단위로 순차 진행된다.
USERS_DIR = DATA_DIR / "users"
USER_FILES = {
    "USER_PROFILE": "user_profile.json",
    "USER_NOTES": "user_notes.json",
    "RECOMMENDATIONS": "recommendations.json",
    "FEEDBACK_LOG": "feedback_log.json",
    "DISCOVERIES": "discoveries.json",        # 주간 채널 탐색 제안과 응답
    "LONG_TERM_MEMORY": "long_term_memory.json",  # 피드백을 누적 요약한 장기 기억
}
USER_DIR = DATA_DIR
USER_PROFILE = DATA_DIR / "user_profile.json"
USER_NOTES = DATA_DIR / "user_notes.json"
RECOMMENDATIONS = DATA_DIR / "recommendations.json"
FEEDBACK_LOG = DATA_DIR / "feedback_log.json"
DISCOVERIES = DATA_DIR / "discoveries.json"
LONG_TERM_MEMORY = DATA_DIR / "long_term_memory.json"

SEED_PROFILE = CONFIG_DIR / "seed_profile.json"
CHANNELS = CONFIG_DIR / "channels.json"

# --- LLM: OpenRouter (OpenAI 호환 API) -----------------------------------
# 유료 슬러그라 무료 티어의 분당/일일 요청 수 제한이 없다. 대신 계정 크레딧이
# 필요하다. 가격은 $0.05/M in, $0.10/M out 으로 이 용도에는 무시할 수준.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# 요약/난이도/답장 파싱처럼 양 많고 단순한 작업.
MODEL_CHEAP = "deepseek/deepseek-v4-flash-0731"
# Top-30 재검토처럼 추론 품질이 중요한 작업. 지금은 같은 모델을 쓰지만,
# 추천 품질이 아쉬우면 이쪽만 더 센 모델로 올린다.
MODEL_SMART = "deepseek/deepseek-v4-flash-0731"

# 일시적 429/5xx 대응. 요청 수 제한이 아니라 순수 재시도용이다.
LLM_MAX_RETRIES = 4
LLM_RETRY_BASE_SECONDS = 1.5

# SDK 기본 타임아웃은 10분이라 응답 없는 요청 하나가 워크플로우 전체를 잡아먹는다.
LLM_TIMEOUT_SECONDS = 120

# max_tokens 예산. deepseek-v4-flash 는 reasoning 모델이라 max_tokens 에 추론
# 토큰이 포함된다. 짜게 잡으면 추론만 하다 예산이 끝나 content 가 빈 채로
# finish_reason=length 가 돌아온다(실측: 판정 하나에 추론 7,000자 이상 소비).
# 출력 $0.10/M 이라 넉넉히 잡아도 호출당 0.2센트 수준이다.
TOKENS_FILTER = 4000        # 발표 여부 yes/no 판정
TOKENS_ANALYZE = 8000       # 요약·난이도·대상·주제 생성
TOKENS_RECOMMEND = 16000    # 후보 30개 재검토

TOKENS_MEMORY = 8000        # 장기 기억 갱신

# 추천 프롬프트·프로필 임베딩에 넣는 단기 기억 크기: 최근 메모 n개, 최근 좋아요/싫어요 n개.
# 그보다 오래된 피드백은 장기 기억(long_term_memory.json)에 요약돼 들어간다.
SHORT_TERM_N = 5
# 장기 기억 항목별 최대 개수. 무한히 자라면 프롬프트가 커지고 최신 취향이 묻힌다.
LONG_TERM_MAX_ITEMS = 10

# 주 1회 실행에서 새로 분석할 영상 수 목표.
MAX_ANALYSIS_PER_RUN = 10

# --- 임베딩 --------------------------------------------------------------
# 임베딩도 OpenRouter 를 쓴다. 목록은 /api/v1/embeddings/models 에 따로 있다
# (chat 모델 목록인 /api/v1/models 에는 나오지 않는다).
# Qwen3 임베딩은 멀티링구얼이라 한/영 혼재 텍스트에 맞고 $0.01/M 토큰이다.
EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
EMBEDDING_INPUT_LIMIT = 8000

# --- 수집 ----------------------------------------------------------------
# 소스당 훑을 영상 수. 신규 업로드만이 아니라 예전 발표까지 후보에 넣으려면
# 목록을 깊게 봐야 한다. 50개당 1 quota unit 이라 넉넉히 잡아도 부담이 없다.
PER_SOURCE_LIMIT = 150

# 주간 신규 채널/재생목록 탐색에서 검색할 키워드 후보 수.
DISCOVERY_SEARCH_RESULTS = 25

# 분석에 넣을 자막 구간(초). 발표는 도입부에 주제·대상·목차가 몰려 있어
# 앞 몇 분이면 무엇을 다루는지 판단하기에 충분하다.
TRANSCRIPT_SECONDS = 180

# 자막은 데이터센터 IP 에서 차단된다. Actions 에서도 쓰려면 주거용 프록시가 필요하다.
# 설정하지 않으면 자막 없이 설명만으로 동작한다.
PROXY_URL = os.environ.get("PROXY_URL")
WEBSHARE_PROXY_USERNAME = os.environ.get("WEBSHARE_PROXY_USERNAME")
WEBSHARE_PROXY_PASSWORD = os.environ.get("WEBSHARE_PROXY_PASSWORD")

# 추천 구성: 매주 3편.
#   near — 임베딩 유사도 상위 2편. 확실히 취향에 맞는 것.
#   far  — 유사도는 낮지만 볼 가치가 있다고 LLM 이 판단한 1편. 취향이 굳는 것을 막는다.
TOP_K_CANDIDATES = 30
N_NEAR = 2
N_FAR = 1

# far 후보 풀: 유사도 순위에서 이 구간을 뽑아 LLM 에게 판정을 맡긴다.
# 최상위는 near 와 겹치고, 최하위는 아예 무관한 영상이라 중간 구간을 본다.
FAR_POOL_START = 0.35   # 전체 후보의 35% 지점부터
FAR_POOL_SIZE = 15

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
# 수신자 목록. RECIPIENT_EMAILS 에 쉼표로 여러 개(최대 MAX_USERS). 없으면 예전
# 단일 변수 RECIPIENT_EMAIL, 그것도 없으면 발송 계정 자신에게 보낸다.
MAX_USERS = 10
RECIPIENT_EMAILS = [
    e.strip().lower()
    for e in (os.environ.get("RECIPIENT_EMAILS") or os.environ.get("RECIPIENT_EMAIL")
              or os.environ.get("GMAIL_ADDRESS") or "").split(",")
    if e.strip()
]
# 현재 처리 중인 유저의 수신 주소. set_user() 가 채운다.
RECIPIENT_EMAIL = RECIPIENT_EMAILS[0] if RECIPIENT_EMAILS else None

# 피드백을 받을 주소. Gmail 플러스 주소(you+techletter@gmail.com)를 쓰면 일상
# 메일과 섞이지 않고, IMAP 에서 이 주소로 정확히 필터링할 수 있다.
# Reply-To 헤더와 mailto 링크에 이 주소를 넣어야 답장이 태그를 달고 돌아온다
# (그냥 To 에만 넣으면 답장 시 To 가 발신 주소로 바뀌면서 태그가 사라진다).
# 모든 유저가 같은 피드백 주소로 답장하고, 답장의 From 으로 유저를 구분한다.
FEEDBACK_ADDRESS = os.environ.get("FEEDBACK_ADDRESS") or os.environ.get("GMAIL_ADDRESS") or RECIPIENT_EMAIL

# 앱 비밀번호 방식. OAuth 동의 화면/심사/토큰 만료가 없고 secret 이 2개로 끝난다.
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")


def user_key(email: str) -> str:
    """유저 디렉터리 이름. 레포가 공개일 수 있어 이메일 원문 대신 해시를 쓴다."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:12]


def set_user(email: str) -> None:
    """유저별 경로 상수를 이 유저 것으로 바꿔 끼운다.

    각 모듈이 config.USER_PROFILE 등을 호출 시점에 읽으므로, 이 한 번으로
    기존 코드가 그대로 유저 단위로 동작한다.
    # ponytail: 모듈 전역 교체라 유저 병렬 처리는 불가. 필요해지면 경로를 인자로 넘길 것.
    """
    global USER_DIR, RECIPIENT_EMAIL
    RECIPIENT_EMAIL = email
    USER_DIR = USERS_DIR / user_key(email)
    for name, filename in USER_FILES.items():
        globals()[name] = USER_DIR / filename


# OpenRouter 랭킹 페이지에 노출되는 선택 헤더.
OPENROUTER_REFERER = "https://github.com/yeseoLee/TechLetterAgent"
OPENROUTER_TITLE = "TechLetterAgent"
