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

# --- LLM: 전부 OpenRouter 무료 모델 (OpenAI 호환 API) ---------------------
# `:free` 슬러그는 토큰 과금이 0 인 대신 계정 단위 rate limit 이 걸린다
# (분당 요청 수 + 일일 요청 수). README 의 "무료 모델 rate limit" 참고.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# 요약/난이도/답장 파싱처럼 양 많고 단순한 작업.
MODEL_CHEAP = "google/gemma-4-31b-it:free"
# Top-30 재검토처럼 추론 품질이 중요한 작업.
MODEL_SMART = "z-ai/glm-5.2:free"

# 429 대응. 무료 티어는 분당 한도가 낮아 호출 간 간격을 둔다.
LLM_MAX_RETRIES = 5
LLM_RETRY_BASE_SECONDS = 4
LLM_MIN_INTERVAL_SECONDS = 3.5

# 일일 요청 한도를 넘기지 않도록 collect 1회당 분석할 영상 수를 제한한다.
MAX_ANALYSIS_PER_RUN = 15

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
