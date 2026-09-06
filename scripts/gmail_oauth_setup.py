"""Gmail refresh token 을 로컬에서 1회 발급받는 스크립트.

사전 준비: Google Cloud Console 에서 OAuth 클라이언트(데스크톱 앱)를 만들고
credentials.json 을 이 디렉토리에 내려받는다. README 의 "Gmail OAuth 설정" 참고.

    python scripts/gmail_oauth_setup.py

출력된 refresh token 을 GitHub Secret `GMAIL_REFRESH_TOKEN` 에 등록한다.
credentials.json / token.json 은 .gitignore 로 제외되어 있다.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        sys.exit("refresh token 이 발급되지 않았습니다. 앱 권한을 해제하고 다시 시도하세요.")
    print("\n--- GitHub Secrets 에 등록할 값 ---")
    print(f"GMAIL_CLIENT_ID={creds.client_id}")
    print(f"GMAIL_CLIENT_SECRET={creds.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
