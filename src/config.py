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

# LLM: 저비용 반복 작업(요약/난이도/답장 파싱)은 Haiku, 추천 재검토는 Sonnet.
MODEL_CHEAP = "claude-haiku-4-5"
MODEL_SMART = "claude-sonnet-5"
EMBEDDING_MODEL = "text-embedding-3-small"

# 추천 구성
TOP_K_CANDIDATES = 30
N_STRONG = 3
N_MAYBE = 2

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

GMAIL_CLIENT_ID = os.environ.get("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.environ.get("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.environ.get("GMAIL_REFRESH_TOKEN")
