# AGENTS.md

Guide for coding agents working on this repo. Human-facing docs: `README.ko.md` / `README.md`.

## What this is

A weekly newsletter bot that sends each recipient (up to 10) three developer-conference YouTube talks.
It runs **only on GitHub Actions**: no server, no DB. All state lives in `data/*.json` and gets committed.
The feedback loop runs through **email replies**, read over IMAP.

## Runtime flow

```
collect.yml (Mon KST 05:00)  src/run_collect.py   — shared across users
  YouTube Data API (content_agent) + blog RSS/Atom (blog_agent, config/blogs.json)
  → prefilter (rules → LLM) → article_analyzer (summary/difficulty/embedding)
  → data/videos.json, data/embeddings.json

send.yml (Mon KST 07:00)     src/run_send.py      — loops over each user in RECIPIENT_EMAILS
  config.set_user(email)
  → _apply_feedback: IMAP (FROM=user) → feedback_agent.parse_reply → profile diff/notes/feedback_log
  → _consolidate_memory: fold new feedback into long_term_memory.json (memory_agent.update_long_term)
  → cluster_agent.top_candidates (profile + long-term preferences + recent notes embedding, cosine Top-30)
  → recommendation_agent.recommend (near 2 by similarity + far 1 picked by LLM)
  → discovery_agent.discover (one new channel proposal)
  → newsletter_agent.render → email_client.send → recommendations.json / discoveries.json
```

## Data layout

| Scope | Path | Notes |
| --- | --- | --- |
| Shared | `data/videos.json`, `data/embeddings.json` | Videos and embeddings are shared by all users |
| Shared | `config/channels.json` | YouTube source whitelist. Any user's `channel-yes` adds to it |
| Shared | `config/blogs.json` | Tech blog RSS/Atom sources. Blog entries share `videos.json` with `kind: "blog"`, no `youtube_id`, dedup by `url` |
| Shared | `config/seed_profile.json` | Initial profile for new users |
| Per user | `data/users/<user_key>/` | `user_profile`, `user_notes`, `recommendations`, `feedback_log`, `discoveries`, `long_term_memory` |

- `user_key = sha256(lower(email))[:12]` (`config.user_key`). The repo can be public, so raw emails never go into paths or logs (`run_send._mask`).
- Per-user path constants (`config.USER_PROFILE`, etc.) are **swapped in by `config.set_user()`**. Modules must read `config.X` at call time. Don't bind them as default arguments or module-level copies, or you'll write to the wrong user's files.
- Because of that, processing users in parallel is not possible (marked with a `ponytail:` comment).
- `memory_agent.migrate_legacy_data`: a one-time migration that moves old single-user `data/*.json` into the first recipient's directory.

## Memory model

- **Short-term memory**: the latest `config.SHORT_TERM_N` notes (`user_notes.json`) and likes/dislikes (`feedback_log.json`), passed as raw text.
- **Long-term memory**: `long_term_memory.json` = `{preferences, avoid, context, last_feedback_id, updated_at}`.
  Every time new feedback lands, the LLM merges it into the existing memory. Each list is capped at `LONG_TERM_MAX_ITEMS`.
- `last_feedback_id` is the cursor. If the LLM call fails, the cursor stays put and the update retries on the next run. Channel-answer-only feedback moves the cursor without an LLM call.
- The embedding query includes only `preferences` (including `avoid` would pull results toward those topics).
- Prompt priority: profile fields < long-term memory < recent notes/reactions.

## Feedback identification

- Every user replies to the same `FEEDBACK_ADDRESS` (a plus address is recommended); the reply's **From** identifies the user.
- Structured replies: subjects like `[TLA] like rec_004` / `[TLA] channel-yes UC...` are parsed with a regex and no LLM call. `rec_*` IDs are only unique within a user.
- Free-text replies: the LLM turns them into a profile diff (incremental `+item`/`-item`) and a note.

## Commands

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -q                       # no network or API keys needed
RECIPIENT_EMAILS=a@x.com python -m src.run_send --dry-run   # no sending; requires OPENROUTER_API_KEY
python -m src.run_collect --limit 3
```

Environment variables: `OPENROUTER_API_KEY`, `YOUTUBE_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`,
`RECIPIENT_EMAILS` (comma-separated, max 10; falls back to `RECIPIENT_EMAIL` → `GMAIL_ADDRESS`), `FEEDBACK_ADDRESS`.

## Conventions

- Code comments, logs, and LLM prompts are in **Korean**. Comments explain *why*.
- Model IDs, token budgets, and counts all live as constants in `src/config.py`. `deepseek-v4-flash` is a reasoning model, so keep `max_tokens` generous.
- LLM responses are never trusted: validate IDs/fields and backfill (see `recommendation_agent._take/_backfill`, `feedback_agent._sanitize`).
- Tests replace LLM/network calls with `monkeypatch`. File I/O uses `tmp_path` plus a `monkeypatch` of the `config` paths.
- JSON is saved with `content_store.save` (`ensure_ascii=False`, indent=2) so git diffs stay readable.
- Don't hand-edit `data/`: the workflows commit it. Watch out for conflicts: collect and send share a concurrency group.
- Minimal dependencies: stdlib first (smtplib/imaplib), plus only openai/numpy/requests.
