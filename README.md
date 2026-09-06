# TechLetterAgent

넘쳐나는 개발자 컨퍼런스·발표 영상 중에서 **내 포지션 / 기술스택 / 관심주제 / 난이도 / 언어**에 맞는 것만 골라서 메일로 보내주는 개인용 뉴스레터 봇.

- 사용자: 1인 (개인용)
- 실행: GitHub Actions cron — 상시 서버 없음
- 상태 저장: 레포 안 `data/*.json` (외부 DB 없음)
- 이메일: Gmail API (발송 + 답장 수신 모두)

## 동작 방식

```
collect.yml (매일)
  YouTube Data API → 신규 영상 + 길이 + 설명 → 사전 필터(비발표 콘텐츠 제거)
  → OpenRouter 무료 모델로 요약/난이도/타겟대상 생성 → 임베딩 → data/videos.json 커밋

send.yml (월/수/금)
  1. Gmail 답장 조회 → LLM 파싱 → 프로필/메모 갱신
  2. 프로필 임베딩 vs 영상 임베딩 코사인 유사도 → 후보 Top-30 (기추천 영상 제외)
  3. reasoning 모델 재검토 → 강추 3개 + 혹시나 2개 확정 + 추천 이유 생성
  4. 이메일 포맷팅 (제목 + 1~2줄 요약 + 추천 이유 + 👍/👎 mailto)
  5. Gmail API 발송 → data/recommendations.json 커밋
```

피드백 루프는 **답장 기반**입니다. 오픈/클릭 트래킹은 상시 응답 서버가 필요해 1차 범위에서 제외했습니다.

## 모델

LLM 호출과 임베딩을 전부 **OpenRouter** 하나로 처리합니다. 외부 API 키는 OpenRouter 와
YouTube 두 개뿐입니다.

임베딩 모델 목록은 chat 모델과 분리되어 있습니다 — `/api/v1/models` 가 아니라
`/api/v1/embeddings/models` 를 봐야 합니다. 슬러그는 `src/config.py` 상수라 언제든 교체 가능합니다.

| 용도 | 모델 | 비고 |
| --- | --- | --- |
| 요약 · 난이도 · 답장 파싱 | `deepseek/deepseek-v4-flash-0731` | 1.31M ctx. $0.05/M in, $0.10/M out |
| Top-30 추천 재검토 | `deepseek/deepseek-v4-flash-0731` | 같은 모델. 추천 품질이 아쉬우면 이쪽만 더 센 모델로 올립니다 |
| 임베딩 | `qwen/qwen3-embedding-8b` | 멀티링구얼, 32K ctx. $0.01/M 토큰 |

### 비용

유료 슬러그라 **OpenRouter 계정에 크레딧이 있어야** 동작합니다. 무료 티어의 분당/일일
요청 수 제한은 없습니다.

영상 1건 분석에 입력 1~2K 토큰, 출력 300 토큰, 임베딩 1K 토큰 수준이라 100건을 돌려도 몇 센트입니다.
`MAX_ANALYSIS_PER_RUN`(기본 50)은 비용 제한이 아니라 한 번에 과하게 도는 것을 막는
안전장치입니다.

## 초기 설정

### 1. 프로필 채우기

`config/seed_profile.json` 의 플레이스홀더를 본인 값으로 수정합니다. `data/user_profile.json` 이
없을 때 최초 1회만 이 파일로 초기화되고, 이후에는 답장 피드백으로 갱신됩니다.

`few_shot_videos` 에는 "내가 좋아했던 발표 영상" URL 3~5개를 넣습니다. 초기 취향 추론에 쓰입니다.

### 2. 수집 소스

`config/channels.json` 에 채널과 재생목록을 등록합니다. 채널 ID 는 다음으로 확인합니다.

```bash
python scripts/resolve_channel_id.py https://www.youtube.com/@naver_d2
```

재생목록 ID 는 URL 의 `list=` 뒤 문자열을 그대로 씁니다.

**사전 필터** — 화이트리스트 채널에도 발표가 아닌 영상이 섞입니다(BGM 플레이리스트,
채용 웨비나, 행사 스케치 등). `src/prefilter.py` 가 2단계로 걸러냅니다.

1. 규칙 판정 — 무료. 제목 키워드 + 영상 길이(8분~3시간)로 명백한 것만 제거
2. LLM 판정 — 1단계 통과분만. 무료 모델 요청 한도를 아끼기 위한 순서

잘못 걸러지는 영상이 보이면 `prefilter.py` 의 `TITLE_DENY` / `TITLE_ALLOW` 를 조정하세요.
`TITLE_ALLOW` 가 `TITLE_DENY` 보다 우선합니다.

### 3. YouTube Data API 키

1. [Google Cloud Console](https://console.cloud.google.com/) 에서 프로젝트 생성 (Gmail 과 같은 프로젝트를 써도 됩니다)
2. **API 및 서비스 → 라이브러리** 에서 *YouTube Data API v3* 사용 설정
3. **사용자 인증 정보 → API 키** 생성 후 `YOUTUBE_API_KEY` secret 에 등록

무료 quota 는 하루 10,000 units 입니다. 이 프로젝트는 소스 8개 기준 하루 20 units
내외를 쓰므로 여유가 큽니다.

### 4. Gmail OAuth 설정

1. [Google Cloud Console](https://console.cloud.google.com/) 에서 프로젝트 생성
2. **API 및 서비스 → 라이브러리** 에서 *Gmail API* 사용 설정
3. **OAuth 동의 화면** 구성 — User Type `외부`, 테스트 사용자에 본인 Gmail 주소 추가
   (게시하지 않고 테스트 모드로 두면 refresh token 이 7일마다 만료되므로, **앱을 "프로덕션"으로 게시**하세요. 개인 용도라 심사 없이 게시 가능합니다.)
4. **사용자 인증 정보 → OAuth 클라이언트 ID** 생성 후 JSON 을 레포 루트에 `credentials.json` 으로 저장

   애플리케이션 유형은 반드시 **데스크톱 앱** 이어야 합니다. 웹 애플리케이션으로 만들면
   `Access blocked: This app's request is invalid` 로 막힙니다 — 인증 스크립트가
   `http://localhost:<포트>/` 로 콜백을 받는데 웹 클라이언트에는 그 리디렉션 URI 가
   등록돼 있지 않기 때문입니다. (`scripts/gmail_oauth_setup.py` 가 실행 전에 검사합니다.)
5. 로컬에서 1회 인증:

```bash
pip install -r requirements.txt
python scripts/gmail_oauth_setup.py
```

출력된 세 값을 GitHub Secrets 에 등록합니다.

### 5. GitHub Secrets

| Secret | 용도 |
| --- | --- |
| `OPENROUTER_API_KEY` | LLM 호출과 임베딩 전부. [openrouter.ai/keys](https://openrouter.ai/keys) 에서 발급 |
| `YOUTUBE_API_KEY` | YouTube Data API v3. 영상 발견 + 길이 + 설명 |
| `GMAIL_CLIENT_ID` | Gmail OAuth |
| `GMAIL_CLIENT_SECRET` | Gmail OAuth |
| `GMAIL_REFRESH_TOKEN` | Gmail OAuth |
| `RECIPIENT_EMAIL` | 뉴스레터 수신 주소 (공개 레포이므로 Secret 으로 관리) |

레포 Settings → Secrets and variables → Actions 에서 등록합니다.

### 6. Actions 쓰기 권한

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

테스트는 API 키 없이 돌아갑니다.

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

## 레포 구조

| 경로 | 역할 |
| --- | --- |
| `src/content_agent.py` | 채널·재생목록 RSS 수집 + yt-dlp 자막 추출 |
| `src/prefilter.py` | 비발표 콘텐츠 제거 (규칙 → LLM 2단계) |
| `src/llm.py` | OpenRouter 호출 래퍼 (스로틀·재시도·JSON 파싱) |
| `src/article_analyzer.py` | LLM 요약/난이도/타겟 생성, Whisper 폴백, 임베딩 |
| `src/content_store.py` | `data/*.json` 읽기/쓰기 |
| `src/embedding_store.py` | 임베딩 저장 (float32 base64, 별도 파일) |
| `src/cluster_agent.py` | 코사인 유사도 Top-30 후보 추출 |
| `src/recommendation_agent.py` | Sonnet 5 재검토 → 강추 3 / 혹시나 2 |
| `src/newsletter_agent.py` | 이메일 본문 포맷팅 (mailto 피드백 버튼 포함) |
| `src/email_client.py` | Gmail API 발송/답장 조회 |
| `src/feedback_agent.py` | 답장 파싱 → 프로필 diff 제안 |
| `src/memory_agent.py` | 프로필/메모 갱신 |

## 데이터 저장

상태는 전부 레포 안 `data/*.json` 에 있고, 워크플로우가 실행될 때마다 커밋됩니다.

| 파일 | 내용 |
| --- | --- |
| `videos.json` | 영상 메타데이터 + 요약/난이도/대상/주제 |
| `embeddings.json` | `video_id` → float32 base64 임베딩 |
| `user_profile.json` | 구조화 프로필 |
| `user_notes.json` | 답장에서 뽑은 자유 텍스트 메모 |
| `recommendations.json` | 추천 이력 (중복 추천 방지) |
| `feedback_log.json` | 피드백 로그 |

**임베딩을 왜 분리했나** — 인라인으로 넣으면 영상 1건당 임베딩 90KB, 나머지 1.2KB 로
파일의 99%가 임베딩입니다. 매 실행마다 파일 전체를 다시 커밋하는 구조라 git 히스토리가
실행 횟수만큼 누적됩니다. 별도 파일 + float32 base64 로 바꿔서 전체 크기를 20%로 줄이고,
`videos.json` 은 git diff 로 실제 내용 변화를 읽을 수 있게 유지했습니다.

## 알려진 제약

- **자막을 쓰지 않습니다.** GitHub Actions 의 데이터센터 IP 에서 yt-dlp 는 전면 봇 차단되고
  (`Sign in to confirm you're not a bot`, player_client 4종 모두 실패), RSS 도 404 로
  스로틀링됩니다. 진단 결과는 `scripts/diagnose_youtube_access.py` 로 재현할 수 있습니다.
  그래서 발견·길이·설명을 YouTube Data API 로 받고, **발표자가 직접 쓴 영상 설명**을
  분석 입력으로 씁니다. 컨퍼런스 채널은 설명에 세션 초록·발표 대상·목차를 구조화해 넣는
  경우가 많고, 자동 자막보다 오히려 정확합니다.
  로컬(주거용 IP)에서는 yt-dlp 가 동작하므로 `--with-transcript` 로 자막을 함께 넣을 수 있습니다.
- **설명이 부실한 영상은 건너뜁니다.** 설명 40자 미만이면 분석 근거가 없다고 보고 제외합니다.
- **공개 레포**: `data/` 에 프로필·관심사·피드백 답장 원문이 커밋되어 공개됩니다.
  비공개로 바꾸려면 `gh repo edit --visibility private --accept-visibility-change-consequences`.

## 라이선스

MIT
