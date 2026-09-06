# TechLetterAgent

한국어·영어 개발자 컨퍼런스 채널을 훑어서, 매주 볼 만한 발표 3편만 메일로 보내주는
개인용 뉴스레터 봇.

**English: [README.md](README.md)**

GitHub Actions 위에서만 돕니다. 서버도, DB도, 이메일 서비스도 없습니다.

---

## 핵심 아이디어: 메일 답장으로 만든 피드백 루프

추천 시스템에는 피드백이 필요하고, 피드백을 받으려면 보통 인프라가 따라옵니다.
좋아요 버튼이 있는 웹앱, 클릭을 추적하는 리다이렉트, 그걸 받아줄 상시 응답 엔드포인트,
결과를 담을 데이터베이스. 사용자가 한 명인데 장치가 너무 많습니다.

이 프로젝트는 그 전부를 **메일에 답장하기**로 대체합니다.

```
뉴스레터  ──▶  답장  ──▶  IMAP 이 읽음  ──▶  프로필 갱신
   ▲                                            │
   └────────────────────────────────────────────┘
```

답장은 두 종류이고, 둘 다 같은 받은편지함으로 들어옵니다.

| 답장 | 만들어지는 방식 | 읽는 방식 |
| --- | --- | --- |
| 영상 평가 | 메일의 `👍` 링크가 `mailto:` 라서, 누르면 `[TLA] like rec_004` 제목의 메일이 열림 | 제목만 파싱. LLM 호출 없음 |
| 그 외 전부 | 그냥 씁니다 — *"프론트엔드보다 백엔드가 더 궁금해요"* | LLM 이 프로필 diff 와 메모로 변환 |

서버 없이 이게 되는 이유:

- **클릭이 메일 한 통이 됩니다.** 클릭 추적은 보통 리다이렉트를 받아줄 살아있는
  엔드포인트가 필요합니다. `mailto:` 는 아무것도 필요 없습니다 — 메일 클라이언트가
  대신 일하고, 클릭은 다음 정기 실행이 집어가는 메시지로 도착합니다.
- **받은편지함이 데이터베이스입니다.** 답장은 워크플로우가 돌 때까지 거기서 기다립니다.
  받아줄 웹훅도, 실행 사이에 켜둘 것도 없습니다.
- **정형·비정형 피드백이 한 통로를 씁니다.** 태그 붙은 제목은 파싱이 싸고, 자유
  텍스트는 LLM 이 읽습니다. 둘 다 같은 방식으로 도착합니다.
- **플러스 주소가 일상 메일과 갈라놓습니다.** `Reply-To` 헤더가
  `you+techletter@gmail.com` 이라, IMAP 은 정확히 그 주소만 검색하고 다른 메일은
  건드리지 않습니다.

이 루프 전체의 비용은 **주 1회 IMAP 검색 한 번**입니다.

---

## 동작

```
collect.yml — 매주 월요일 KST 05:00
  YouTube Data API 로 소스별 목록을 깊게 훑음 (신규 업로드 + 예전 발표)
  → 이미 저장한 영상 제외 → 발표가 아닌 것 제거
  → 요약/난이도/대상 생성 → 임베딩 → data/videos.json 커밋
  목표: 주당 새 영상 10편

send.yml — 매주 월요일 KST 07:00
  1. IMAP 으로 답장 조회 → 프로필·메모·채널 승인 반영
  2. 프로필 임베딩과 코사인 유사도 → 후보 30편
     (이미 추천한 것은 id 와 정규화된 제목 양쪽으로 제외)
  3. 3편 확정
       추천 2편   — 유사도 상위. 코드가 고르고 LLM 은 이유만 씀
       넓혀보기 1편 — 유사도는 낮지만 볼 가치가 있다고 LLM 이 판단한 것
  4. 새 채널 후보 1개 탐색
  5. 렌더링 → SMTP 발송 → data/*.json 커밋
```

### 넓혀보기 1편을 두는 이유

유사도만 따르면 추천이 수렴합니다. 이미 좋아한 것과 비슷한 게 계속 나오고 프로필은
넓어지지 않습니다. 세 번째 자리는 순위 중간에서, 그럼에도 볼 가치가 있다고 모델이
논증할 수 있는 발표에 내줍니다. 최상위는 추천 2편과 겹치고 최하위는 아예 무관하므로,
후보 풀은 중간 구간에서 뽑습니다 — "낯설지만 연결점은 있는" 것이 거기 모입니다.

---

## 알아둘 설계 결정

**상태는 레포 안에 있습니다.** 실행할 때마다 `data/*.json` 을 읽고 갱신하고 커밋합니다.
Postgres 도 Supabase 도 없습니다. 사용자 한 명과 발표 수백 편에는 이걸로 충분하고,
git 히스토리가 프로필이 어떻게 변해왔는지에 대한 감사 로그가 됩니다.

**임베딩은 별도 파일에 base64 로 넣습니다.** `videos.json` 에 인라인으로 두니 영상
1건당 임베딩 90KB, 나머지 전부가 1.2KB — 파일의 99%가 임베딩인데 매 실행마다 전체를
다시 쓰고 커밋했습니다. 분리하고 float32 를 base64 로 담아 전체 크기를 20%로 줄였고,
`videos.json` 은 diff 로 읽을 수 있는 크기를 유지했습니다.

**자막을 쓰지 않습니다.** GitHub Actions 의 데이터센터 IP 에서 yt-dlp 는 전면 차단되고
(`Sign in to confirm you're not a bot`, player client 4종 모두), RSS 는 404 를 돌려줍니다.
그래서 분석 입력을 영상 설명으로 바꿨는데, 이건 타협이 아니라 개선이었습니다. 컨퍼런스
채널은 설명에 구조화된 초록을 넣습니다 — NAVER D2 는 `[발표 대상]` 을 아예 명시합니다 —
반면 자동 자막은 오인식투성이입니다.
`scripts/diagnose_youtube_access.py` 로 재현할 수 있습니다.

**전부 OpenRouter 를 거칩니다.** 키 하나로 채팅과 임베딩을 모두 씁니다. 임베딩 모델
목록은 흔히 보는 `/api/v1/models` 가 아니라 `/api/v1/embeddings/models` 에 있습니다.

**Gmail OAuth 대신 앱 비밀번호.** 사용자가 한 명이면 OAuth 동의 화면, Google 심사,
7일짜리 refresh token 만료가 아무것도 벌어주지 못합니다. 앱 비밀번호로 쓰는 SMTP/IMAP
은 secret 2개면 되고, 만료되지 않고, 표준 라이브러리만 씁니다.

---

## 모델

`src/config.py` 의 상수만 바꾸면 교체됩니다.

| 용도 | 모델 | 비고 |
| --- | --- | --- |
| 요약·난이도·답장 파싱 | `deepseek/deepseek-v4-flash-0731` | $0.05/M in, $0.10/M out |
| 추천 재검토·채널 판정 | `deepseek/deepseek-v4-flash-0731` | 추천이 아쉬우면 이쪽만 올리세요 |
| 임베딩 | `qwen/qwen3-embedding-8b` | 멀티링구얼, 32K ctx, $0.01/M |

DeepSeek v4 flash 는 **reasoning 모델**이라 `max_tokens` 에 추론 토큰이 포함됩니다.
넉넉히 잡으세요 — 짜게 잡으면 추론에만 예산을 다 쓰고 `finish_reason=length` 로
빈 응답이 돌아옵니다. 호출별 예산은 `config.TOKENS_*` 에 있습니다.

이 정도 양이면 주당 몇 센트입니다.

---

## 설정

### 1. 프로필 채우기

`config/seed_profile.json` 에 포지션·기술스택·관심주제·연차, 그리고 실제로 좋았던
`few_shot_videos` 3~5개를 넣습니다. 최초 실행 때 `data/user_profile.json` 을
초기화하고, 이후에는 답장이 갱신합니다.

### 2. 소스 추가

`config/channels.json` 에 채널과 재생목록을 넣습니다. 채널 ID 는:

```bash
python scripts/resolve_channel_id.py https://www.youtube.com/@naver_d2
```

재생목록 ID 는 URL 의 `list=` 값을 그대로 씁니다.

**사전 필터.** 화이트리스트 채널에도 발표가 아닌 게 섞입니다 — BGM 플레이리스트,
채용 웨비나, 행사 스케치. `src/prefilter.py` 가 2단계로 거릅니다. 제목 키워드와
길이(무료)로 먼저 걸러내고, 살아남은 것만 LLM 에 넘깁니다. 순서가 중요합니다 —
싼 검사를 먼저 돌려야 비싼 쪽이 볼 게 줄어듭니다. `TITLE_ALLOW` 가 `TITLE_DENY` 보다
우선해서, 제목에 "인터뷰"가 들어간 키노트도 통과합니다.

### 3. YouTube Data API 키

[Google Cloud Console](https://console.cloud.google.com/) 에서 *YouTube Data API v3*
를 사용 설정하고 API 키를 만들어 `YOUTUBE_API_KEY` 에 넣습니다.

무료 quota 는 하루 10,000 units 입니다. 목록·상세 조회는 50건당 1 unit, 주간 채널
검색은 100 units 입니다. 한 주를 통틀어 200 units 이 안 됩니다.

### 4. Gmail 앱 비밀번호

2단계 인증이 켜져 있어야 합니다.
[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) 에서
생성하고 `GMAIL_ADDRESS` 와 `GMAIL_APP_PASSWORD` 를 등록합니다.

**`FEEDBACK_ADDRESS` 에는 플러스 주소를 쓰세요** — 예: `you+techletter@gmail.com`.
이 주소가 `Reply-To` 헤더와 피드백 링크에 들어가서, 답장이 태그를 달고 돌아오고
IMAP 은 `TO "…+techletter@gmail.com"` 으로 검색해 다른 메일을 건드리지 않습니다.

`To` 에만 태그를 넣으면 안 됩니다. 답장하면 `To` 가 발신 주소로 바뀌면서 태그가
사라집니다. 살아남는 건 `Reply-To` 입니다.

받은편지함에서도 나누고 싶으면 그 수신자로 Gmail 필터를 만드세요. 단 "받은편지함
건너뛰기"는 켜지 마세요 — IMAP 이 `INBOX` 를 검색합니다.

### 5. Secrets

| Secret | 용도 |
| --- | --- |
| `OPENROUTER_API_KEY` | LLM 호출과 임베딩 전부 |
| `YOUTUBE_API_KEY` | 영상 수집, 메타데이터, 채널 검색 |
| `GMAIL_ADDRESS` | 발송 계정 |
| `GMAIL_APP_PASSWORD` | 앱 비밀번호 16자리 |
| `FEEDBACK_ADDRESS` | 답장 받을 플러스 주소 (선택이지만 권장) |

### 6. 워크플로우 쓰기 권한

Settings → Actions → General → Workflow permissions → **Read and write**.
이게 없으면 `data/` 를 커밋하지 못합니다.

---

## 실행

두 워크플로우 모두 `workflow_dispatch` 가 열려 있습니다.

```bash
gh workflow run collect.yml -f limit=10
gh workflow run send.yml -f dry_run=true       # 추천만 출력, 발송 없음
gh workflow run send.yml -f feedback_only=true # 답장만 읽고 종료
```

`--dry-run` 은 Gmail 설정이 아예 필요 없어서, 추천 품질을 확인하는 가장 빠른 방법입니다.

로컬:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # 값 채우기
set -a && source .env && set +a
python -m src.run_send --dry-run
```

테스트는 API 키 없이 돕니다.

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

---

## 새 채널 탐색

손으로 관리하는 화이트리스트는 결국 이미 아는 것만 보여줍니다. 매 뉴스레터 하단에
새 채널 후보 하나와 **예 / 아니오** 링크가 붙습니다.

검색은 YouTube `search.list` 로 합니다 — 대상이 채널일 때는 범용 웹 검색보다 정확하고,
이미 가진 키를 재사용합니다. 후보를 활동 기준(영상 15편 이상, 구독자 1,000명 이상)으로
거른 뒤 LLM 이 하나를 고릅니다. 브이로그, 강의 판매, 뉴스 요약 채널은 제외하도록
지시합니다.

예는 `config/channels.json` 에 추가되고, 아니오는 `discoveries.json` 에 기록돼 같은
채널이 다시 제안되지 않습니다.

---

## 구조

| 경로 | 역할 |
| --- | --- |
| `src/youtube_api.py` | Data API 클라이언트 — 재생목록, 영상 상세, 채널 검색 |
| `src/content_agent.py` | 전 소스에서 신규 영상 수집 |
| `src/prefilter.py` | 발표가 아닌 것 제거 (규칙 → LLM) |
| `src/article_analyzer.py` | 요약·난이도·대상·주제 생성, 임베딩 |
| `src/cluster_agent.py` | 코사인 유사도, Top-K, 중복 제거 |
| `src/recommendation_agent.py` | near/far 선정과 추천 이유 |
| `src/discovery_agent.py` | 주간 채널 제안 |
| `src/newsletter_agent.py` | HTML·플레인텍스트 렌더링, 피드백 링크 |
| `src/email_client.py` | SMTP 발송, IMAP 답장 조회 |
| `src/feedback_agent.py` | 답장 → 프로필 diff + 메모 |
| `src/memory_agent.py` | diff·메모·채널 승인 반영 |
| `src/llm.py` | OpenRouter 래퍼 — 재시도, JSON 파싱 |
| `src/content_store.py` · `embedding_store.py` | `data/*.json` 영속화 |

### 데이터 파일

| 파일 | 내용 |
| --- | --- |
| `videos.json` | 메타데이터 + 생성된 요약·난이도·대상·주제 |
| `embeddings.json` | `video_id` → float32 base64 |
| `user_profile.json` | 구조화 프로필 |
| `user_notes.json` | 답장에서 뽑은 자유 텍스트 메모 |
| `recommendations.json` | 추천 이력이자 중복 방지 장치 |
| `feedback_log.json` | 모든 답장과 그로 인한 diff |
| `discoveries.json` | 채널 제안과 응답 |

---

## 알려진 제약

- **설명이 없는 발표는 건너뜁니다.** 40자 미만이면 분석할 근거가 없습니다. 로컬에서는
  `--with-transcript` 로 자막을 함께 넣을 수 있습니다 — 주거용 IP 에서는 yt-dlp 가
  정상 동작합니다.
- **공개 레포**라서 `data/` — 프로필, 관심사, 답장 원문 — 도 공개됩니다.
  `gh repo edit --visibility private --accept-visibility-change-consequences` 로
  바꿀 수 있습니다.

## 라이선스

MIT
