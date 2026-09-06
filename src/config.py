"""공통 설정: 경로, 환경변수, 모델 ID."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"

USER_PROFILE = DATA_DIR / "user_profile.json"
USER_NOTES = DATA_DIR / "user_notes.json"
VIDEOS = DATA_DIR / "videos.json"
EMBEDDINGS = DATA_DIR / "embeddings.json"  # video_id -> float32 base64
RECOMMENDATIONS = DATA_DIR / "recommendations.json"
FEEDBACK_LOG = DATA_DIR / "feedback_log.json"

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

# collect 1회당 분석할 영상 수 상한. 한 번에 과하게 도는 것을 막는 안전장치.
MAX_ANALYSIS_PER_RUN = 50

# --- 임베딩 --------------------------------------------------------------
# 임베딩도 OpenRouter 를 쓴다. 목록은 /api/v1/embeddings/models 에 따로 있다
# (chat 모델 목록인 /api/v1/models 에는 나오지 않는다).
# Qwen3 임베딩은 멀티링구얼이라 한/영 혼재 텍스트에 맞고 $0.01/M 토큰이다.
EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
EMBEDDING_INPUT_LIMIT = 8000

# --- 수집 ----------------------------------------------------------------
# 소스당 조회할 최근 영상 수. YouTube Data API 는 50개까지 1 quota unit 이다.
PER_SOURCE_LIMIT = 20

# 추천 구성
TOP_K_CANDIDATES = 30
N_STRONG = 3
N_MAYBE = 2

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
# 수신 주소. 지정하지 않으면 발송 계정 자신에게 보낸다.
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL") or os.environ.get("GMAIL_ADDRESS")

# 피드백을 받을 주소. Gmail 플러스 주소(you+techletter@gmail.com)를 쓰면 일상
# 메일과 섞이지 않고, IMAP 에서 이 주소로 정확히 필터링할 수 있다.
# Reply-To 헤더와 mailto 링크에 이 주소를 넣어야 답장이 태그를 달고 돌아온다
# (그냥 To 에만 넣으면 답장 시 To 가 발신 주소로 바뀌면서 태그가 사라진다).
FEEDBACK_ADDRESS = os.environ.get("FEEDBACK_ADDRESS") or RECIPIENT_EMAIL

# 앱 비밀번호 방식. OAuth 동의 화면/심사/토큰 만료가 없고 secret 이 2개로 끝난다.
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

# OpenRouter 랭킹 페이지에 노출되는 선택 헤더.
OPENROUTER_REFERER = "https://github.com/yeseoLee/TechLetterAgent"
OPENROUTER_TITLE = "TechLetterAgent"
