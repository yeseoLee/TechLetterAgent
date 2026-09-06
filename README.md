# TechLetterAgent

A personal newsletter bot that watches Korean and English developer conference
channels and sends me the three talks worth my time each week.

**한국어 문서: [README.ko.md](README.ko.md)**

Runs entirely on GitHub Actions. No server, no database, no email service.

---

## The idea: a feedback loop built out of email replies

Recommenders need feedback, and feedback usually means infrastructure — a web app
with thumbs-up buttons, click-tracking redirects, an always-on endpoint to receive
them, and a database to store the results. That is a lot of machinery for one user.

This project replaces all of it with **replying to an email**.

```
newsletter  ──▶  you reply  ──▶  IMAP reads it  ──▶  profile updates
   ▲                                                        │
   └────────────────────────────────────────────────────────┘
```

Two kinds of replies, both landing in the same inbox:

| Reply | How it is produced | How it is read |
| --- | --- | --- |
| Rating a talk | A `👍` link in the email is a `mailto:` that opens a pre-filled message titled `[TLA] like rec_004` | Parsed from the subject line. No LLM call |
| Anything else | You just type — *"I'd rather see backend than frontend"* | An LLM turns it into a profile diff and a note |

Why this works without a server:

- **A click becomes an email.** Click-tracking normally needs a live endpoint to
  redirect through. A `mailto:` link needs nothing — the mail client does the work,
  and the click arrives as a message the next scheduled run picks up.
- **The inbox is the database.** Replies wait there until the workflow runs. No
  webhook to receive them, nothing to keep online between runs.
- **Structured and unstructured feedback share one channel.** A tagged subject line
  is cheap to parse; free text goes to the LLM. Both arrive the same way.
- **Plus-addressing keeps it out of the way.** The `Reply-To` header is
  `you+techletter@gmail.com`, so IMAP filters on exactly that address and never
  touches everyday mail.

The cost of the whole loop is one IMAP search per week.

---

## What it does

```
collect.yml — Mondays 05:00 KST
  YouTube Data API walks each source deep (new uploads and older talks alike)
  → skip anything already stored → drop non-talks
  → generate summary / difficulty / audience → embed → commit data/videos.json
  Target: 10 new talks per week

send.yml — Mondays 07:00 KST
  1. Read replies over IMAP → update profile, notes, channel approvals
  2. Cosine similarity against the profile embedding → top 30 candidates
     (already-recommended talks excluded, by id and by normalized title)
  3. Pick 3
       2 × near — highest similarity. Code picks them; the LLM only writes the reason
       1 × far  — low similarity, but the LLM judged it worth watching anyway
  4. Search for one new channel to propose
  5. Render → send over SMTP → commit data/*.json
```

### Why one "far" pick

Ranking by similarity alone makes recommendations converge: you get more of what
you already liked, and the profile never grows. The third slot is reserved for a
talk from the middle of the ranking that the model can argue is worth your time
anyway. The top of the list overlaps with the near picks and the bottom is simply
unrelated, so the pool is drawn from the middle — where "unfamiliar but connected"
lives.

---

## Design decisions worth knowing

**State lives in the repo.** Every run reads `data/*.json`, updates it, and commits.
No Postgres, no Supabase. For one user and a few hundred talks this is enough, and
the git history doubles as an audit log of how the profile evolved.

**Embeddings are stored separately, base64-encoded.** Inline in `videos.json` they
were 90 KB per talk against 1.2 KB of everything else — 99% of the file, rewritten
and committed on every run. Splitting them out and packing float32 as base64 cut the
total to 20%, and `videos.json` stayed small enough to read in a diff.

**No transcripts.** On GitHub Actions' datacenter IPs, yt-dlp is blocked outright
(`Sign in to confirm you're not a bot`, every player client) and the RSS feeds return
404s. So the analysis input is the video description instead. That turned out to be
an upgrade, not a compromise: conference channels put a structured abstract there —
NAVER D2 literally includes a `[발표 대상]` (target audience) line — while
auto-generated captions are full of transcription errors.
Reproduce the finding with `scripts/diagnose_youtube_access.py`.

**Everything goes through OpenRouter.** One key covers both chat and embeddings.
The embedding models are listed at `/api/v1/embeddings/models`, not the usual
`/api/v1/models`.

**App passwords instead of Gmail OAuth.** For a single user, an OAuth consent screen,
Google verification, and 7-day refresh-token expiry buy nothing. SMTP and IMAP with an
app password need two secrets, never expire, and use only the standard library.

---

## Models

Swap any of these by editing the constants in `src/config.py`.

| Job | Model | Notes |
| --- | --- | --- |
| Summary, difficulty, reply parsing | `deepseek/deepseek-v4-flash-0731` | $0.05/M in, $0.10/M out |
| Recommendation review, channel judging | `deepseek/deepseek-v4-flash-0731` | Raise this one alone if the picks disappoint |
| Embeddings | `qwen/qwen3-embedding-8b` | Multilingual, 32K context, $0.01/M |

DeepSeek v4 flash is a **reasoning model**, so `max_tokens` covers reasoning tokens
too. Budget it generously — a stingy limit means the model spends the whole budget
thinking and returns empty content with `finish_reason=length`. The per-call budgets
live in `config.TOKENS_*`.

Cost is a few cents per week at this volume.

---

## Setup

### 1. Fill in the profile

Edit `config/seed_profile.json` — position, stack, interests, level, and 3–5
`few_shot_videos` you actually enjoyed. It seeds `data/user_profile.json` on the
first run; after that, replies drive it.

### 2. Add sources

`config/channels.json` holds channels and playlists. Resolve a channel id with:

```bash
python scripts/resolve_channel_id.py https://www.youtube.com/@naver_d2
```

Playlist ids are the `list=` value from the URL.

**Pre-filtering.** Whitelisted channels still carry non-talks — BGM playlists,
recruiting webinars, event sketches. `src/prefilter.py` removes them in two stages:
title keywords and duration (free), then an LLM call for whatever survives. The
order matters: the cheap check runs first so the expensive one sees less.
`TITLE_ALLOW` wins over `TITLE_DENY`, so a keynote whose title mentions an interview
still gets through.

### 3. YouTube Data API key

Enable *YouTube Data API v3* in [Google Cloud Console](https://console.cloud.google.com/),
create an API key, and store it as `YOUTUBE_API_KEY`.

The free quota is 10,000 units/day. Listing and detail calls cost 1 unit per 50 items;
the weekly channel search costs 100. A full week runs well under 200.

### 4. Gmail app password

Requires 2-Step Verification. Generate one at
[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) and
store `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`.

**Use a plus address for `FEEDBACK_ADDRESS`** — e.g. `you+techletter@gmail.com`. It
goes into the `Reply-To` header and the feedback links, so replies come back tagged
and IMAP can search `TO "…+techletter@gmail.com"` without ever touching your other
mail.

Putting the tag only in `To` does not work: replying rewrites `To` to the sender
address and the tag disappears. `Reply-To` is what survives.

To also separate it in the UI, add a Gmail filter on that recipient — but leave
"Skip the Inbox" off, since IMAP searches `INBOX`.

### 5. Secrets

| Secret | Purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | All LLM calls and embeddings |
| `YOUTUBE_API_KEY` | Video discovery, metadata, channel search |
| `GMAIL_ADDRESS` | Sending account |
| `GMAIL_APP_PASSWORD` | 16-character app password |
| `FEEDBACK_ADDRESS` | Plus address for replies (optional but recommended) |

### 6. Workflow write permission

Settings → Actions → General → Workflow permissions → **Read and write**. Without it
the runs cannot commit `data/`.

---

## Running it

Both workflows expose `workflow_dispatch`:

```bash
gh workflow run collect.yml -f limit=10
gh workflow run send.yml -f dry_run=true       # recommend, print, send nothing
gh workflow run send.yml -f feedback_only=true # read replies only, no send
```

`--dry-run` needs no Gmail configuration at all, which makes it the fastest way to
check recommendation quality.

Locally:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # fill in
set -a && source .env && set +a
python -m src.run_send --dry-run
```

Tests need no API keys:

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

---

## Discovering new channels

A hand-maintained whitelist only ever surfaces what you already know about. Each
newsletter ends with one new channel proposal and **yes / no** links.

Search runs through YouTube's `search.list` — more precise than general web search
when the target is a channel, and it reuses the key you already have. Candidates are
filtered by activity (≥15 videos, ≥1,000 subscribers), then an LLM picks one, with
instructions to skip vlogs, course-selling channels, and news roundups.

Yes appends to `config/channels.json`. No is recorded in `discoveries.json` so the
same channel is never proposed twice.

---

## Layout

| Path | Role |
| --- | --- |
| `src/youtube_api.py` | Data API client — playlists, video details, channel search |
| `src/content_agent.py` | Collects new videos from every source |
| `src/prefilter.py` | Drops non-talks (rules, then LLM) |
| `src/article_analyzer.py` | Summary / difficulty / audience / topics, plus embeddings |
| `src/cluster_agent.py` | Cosine similarity, top-K, duplicate removal |
| `src/recommendation_agent.py` | Near/far selection and reasons |
| `src/discovery_agent.py` | Weekly channel proposal |
| `src/newsletter_agent.py` | HTML and plain-text rendering, feedback links |
| `src/email_client.py` | SMTP send, IMAP reply fetch |
| `src/feedback_agent.py` | Reply → profile diff + note |
| `src/memory_agent.py` | Applies diffs, notes, channel approvals |
| `src/llm.py` | OpenRouter wrapper — retries, JSON parsing |
| `src/content_store.py` · `embedding_store.py` | `data/*.json` persistence |

### Data files

| File | Contents |
| --- | --- |
| `videos.json` | Metadata plus generated summary, difficulty, audience, topics |
| `embeddings.json` | `video_id` → float32 base64 |
| `user_profile.json` | Structured profile |
| `user_notes.json` | Free-text notes extracted from replies |
| `recommendations.json` | History, which is also the duplicate guard |
| `feedback_log.json` | Every reply, with the diff it produced |
| `discoveries.json` | Channel proposals and answers |

---

## Known limits

- **Talks without a usable description are skipped.** Under 40 characters, there is
  nothing to analyze. Running locally, `--with-transcript` adds captions to the
  analysis, since yt-dlp works fine from a residential IP.
- **The repo is public**, so `data/` — profile, interests, reply text — is public
  too. `gh repo edit --visibility private --accept-visibility-change-consequences`
  changes that.

## License

MIT
