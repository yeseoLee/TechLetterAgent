"""Gmail refresh token 을 로컬에서 1회 발급받는 스크립트.

사전 준비: Google Cloud Console 에서 OAuth 클라이언트를 **데스크톱 앱** 유형으로
만들고 credentials.json 을 레포 루트에 내려받는다. README 의 "Gmail OAuth 설정" 참고.

    python scripts/gmail_oauth_setup.py

출력된 값들을 GitHub Secrets 에 등록한다.
credentials.json / token.json 은 .gitignore 로 제외되어 있다.
"""
import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

CREDENTIALS = Path(__file__).resolve().parent.parent / "credentials.json"


def check_credentials() -> None:
    """흔한 설정 실수를 인증 시도 전에 잡는다."""
    if not CREDENTIALS.exists():
        sys.exit(
            f"{CREDENTIALS} 가 없습니다.\n"
            "Google Cloud Console → 사용자 인증 정보 → OAuth 클라이언트 ID →\n"
            "애플리케이션 유형 '데스크톱 앱' 으로 만들고 JSON 을 내려받으세요."
        )

    data = json.loads(CREDENTIALS.read_text())
    if "web" in data:
        sys.exit(
            "credentials.json 이 '웹 애플리케이션' 클라이언트입니다.\n"
            "이 스크립트는 http://localhost:<포트>/ 로 콜백을 받는데 웹 클라이언트에는\n"
            "그 리디렉션 URI 가 등록돼 있지 않아 Google 이 요청을 거부합니다\n"
            "(Access blocked: This app's request is invalid).\n\n"
            "해결: OAuth 클라이언트를 '데스크톱 앱' 유형으로 새로 만들어 받으세요."
        )
    if "installed" not in data:
        sys.exit(f"credentials.json 형식을 알 수 없습니다. 최상위 키: {list(data)}")


def main() -> None:
    check_credentials()

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    if not creds.refresh_token:
        sys.exit(
            "refresh token 이 발급되지 않았습니다.\n"
            "https://myaccount.google.com/permissions 에서 이 앱의 권한을 제거하고"
            " 다시 실행하세요."
        )

    print("\n--- GitHub Secrets 에 등록할 값 ---")
    print(f"GMAIL_CLIENT_ID={creds.client_id}")
    print(f"GMAIL_CLIENT_SECRET={creds.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("\n등록 명령:")
    for name in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        print(f"  gh secret set {name} --repo yeseoLee/TechLetterAgent")


if __name__ == "__main__":
    main()
