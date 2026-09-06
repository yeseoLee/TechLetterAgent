"""공통 설정: 경로, 환경변수, 모델 ID."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"

USER_PROFILE = DATA_DIR / "user_profile.json"
USER_NOTES = DATA_DIR / "user_notes.json"
VIDEOS = DATA_DIR / "videos.json"
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

# collect 1회당 분석할 영상 수 상한. 한 번에 과하게 도는 것을 막는 안전장치.
MAX_ANALYSIS_PER_RUN = 50

# --- 임베딩 --------------------------------------------------------------
# OpenRouter 는 임베딩 모델을 제공하지 않아(2026-09 기준 무료/유료 모두 0건)
# OpenAI 를 직접 호출한다. $0.02/1M 토큰으로 사실상 무시할 만한 비용.
EMBEDDING_MODEL = "text-embedding-3-small"

# --- 수집 ----------------------------------------------------------------
# 소스당 조회할 최근 영상 수. YouTube Data API 는 50개까지 1 quota unit 이다.
PER_SOURCE_LIMIT = 20

# 추천 구성
TOP_K_CANDIDATES = 30
N_STRONG = 3
N_MAYBE = 2

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

GMAIL_CLIENT_ID = os.environ.get("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.environ.get("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.environ.get("GMAIL_REFRESH_TOKEN")

# OpenRouter 랭킹 페이지에 노출되는 선택 헤더.
OPENROUTER_REFERER = "https://github.com/yeseoLee/TechLetterAgent"
OPENROUTER_TITLE = "TechLetterAgent"
