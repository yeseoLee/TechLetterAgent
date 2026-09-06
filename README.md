# TechLetterAgent

넘쳐나는 개발자 컨퍼런스·발표 영상 중에서 **내 포지션 / 기술스택 / 관심주제 / 난이도 / 언어**에 맞는 것만 골라서 메일로 보내주는 개인용 뉴스레터 봇.

- 사용자: 1인 (개인용)
- 실행: GitHub Actions cron — 상시 서버 없음
- 상태 저장: 레포 안 `data/*.json` (외부 DB 없음)
- 이메일: Gmail API (발송 + 답장 수신 모두)

## 동작 방식

```
collect.yml (매일)
  채널 RSS → 신규 영상 감지 → yt-dlp 자막 추출 (없으면 Whisper STT)
  → Haiku 4.5 로 요약/난이도/타겟대상 생성 → 임베딩 → data/videos.json 커밋

send.yml (월/수/금)
  1. Gmail 답장 조회 → Haiku 4.5 파싱 → 프로필/메모 갱신
  2. 프로필 임베딩 vs 영상 임베딩 코사인 유사도 → 후보 Top-30 (기추천 영상 제외)
  3. Sonnet 5 재검토 → 강추 3개 + 혹시나 2개 확정 + 추천 이유 생성
  4. 이메일 포맷팅 (제목 + 1~2줄 요약 + 추천 이유 + 👍/👎 mailto)
  5. Gmail API 발송 → data/recommendations.json 커밋
```

피드백 루프는 **답장 기반**입니다. 오픈/클릭 트래킹은 상시 응답 서버가 필요해 1차 범위에서 제외했습니다.

## 초기 설정

### 1. 프로필 채우기

`config/seed_profile.json` 의 플레이스홀더를 본인 값으로 수정합니다. `data/user_profile.json` 이
없을 때 최초 1회만 이 파일로 초기화되고, 이후에는 답장 피드백으로 갱신됩니다.

`few_shot_videos` 에는 "내가 좋아했던 발표 영상" URL 3~5개를 넣습니다. 초기 취향 추론에 쓰입니다.

### 2. 채널 화이트리스트 채우기

`config/channels.json` 의 `channel_id` 를 채웁니다.

```bash
python scripts/resolve_channel_id.py https://www.youtube.com/@woowatech
```

### 3. Gmail OAuth 설정

1. [Google Cloud Console](https://console.cloud.google.com/) 에서 프로젝트 생성
2. **API 및 서비스 → 라이브러리** 에서 *Gmail API* 사용 설정
3. **OAuth 동의 화면** 구성 — User Type `외부`, 테스트 사용자에 본인 Gmail 주소 추가
   (게시하지 않고 테스트 모드로 두면 refresh token 이 7일마다 만료되므로, **앱을 "프로덕션"으로 게시**하세요. 개인 용도라 심사 없이 게시 가능합니다.)
4. **사용자 인증 정보 → OAuth 클라이언트 ID → 데스크톱 앱** 생성 후 JSON 을 레포 루트에 `credentials.json` 으로 저장
5. 로컬에서 1회 인증:

```bash
pip install -r requirements.txt
python scripts/gmail_oauth_setup.py
```

출력된 세 값을 GitHub Secrets 에 등록합니다.

### 4. GitHub Secrets

| Secret | 용도 |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude API (Haiku 4.5 요약·파싱, Sonnet 5 추천 재검토) |
| `OPENAI_API_KEY` | 임베딩(`text-embedding-3-small`) + Whisper STT |
| `GMAIL_CLIENT_ID` | Gmail OAuth |
| `GMAIL_CLIENT_SECRET` | Gmail OAuth |
| `GMAIL_REFRESH_TOKEN` | Gmail OAuth |
| `RECIPIENT_EMAIL` | 뉴스레터 수신 주소 (공개 레포이므로 Secret 으로 관리) |

레포 Settings → Secrets and variables → Actions 에서 등록합니다.

### 5. Actions 쓰기 권한

Settings → Actions → General → Workflow permissions 를 **Read and write permissions** 로 설정해야
워크플로우가 `data/` 변경을 커밋할 수 있습니다.

## 로컬 테스트

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 키 채우기
set -a && source .env && set +a
python -m src.run_collect
python -m src.run_send
```

`workflow_dispatch` 가 열려 있어 GitHub UI 에서 수동 실행도 가능합니다.

## 레포 구조

| 경로 | 역할 |
| --- | --- |
| `src/content_agent.py` | 채널 RSS 수집 + yt-dlp 자막 추출 |
| `src/article_analyzer.py` | LLM 요약/난이도/타겟 생성, Whisper 폴백, 임베딩 |
| `src/content_store.py` | `data/*.json` 읽기/쓰기 |
| `src/cluster_agent.py` | 코사인 유사도 Top-30 후보 추출 |
| `src/recommendation_agent.py` | Sonnet 5 재검토 → 강추 3 / 혹시나 2 |
| `src/newsletter_agent.py` | 이메일 본문 포맷팅 (mailto 피드백 버튼 포함) |
| `src/email_client.py` | Gmail API 발송/답장 조회 |
| `src/feedback_agent.py` | 답장 파싱 → 프로필 diff 제안 |
| `src/memory_agent.py` | 프로필/메모 갱신 |

## 알려진 제약

- **GitHub Actions IP 차단**: 유튜브가 데이터센터 IP 에서의 자막 요청을 막는 경우가 있습니다.
  자막 추출 실패 시 Whisper STT 로 폴백하며, 그마저 막히면 해당 영상은 건너뜁니다.
- **공개 레포**: `data/` 에 프로필·관심사·피드백 답장 원문이 커밋되어 공개됩니다.
  비공개로 바꾸려면 `gh repo edit --visibility private --accept-visibility-change-consequences`.

## 라이선스

MIT
