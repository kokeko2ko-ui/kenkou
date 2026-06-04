# CLAUDE.md — Kenkou / 人生は七色 Auto-Post Pipeline

## Project Overview

This repository contains an automated daily video generation and YouTube upload pipeline for the Japanese YouTube channel **「人生は七色」** (Life is Seven Colors). It produces inspiring, emotionally-driven narrative videos using AI-generated scripts, TTS audio, and stock video footage — fully unattended via GitHub Actions.

## Repository Structure

```
kenkou/
├── .github/
│   └── workflows/
│       └── daily_post.yml        # GitHub Actions scheduler (daily 20:00 JST)
└── nanahiro-auto/
    ├── README.md                 # Japanese setup guide
    ├── requirements.txt          # Python dependencies
    └── scripts/
        ├── main.py               # Pipeline orchestrator (entry point)
        ├── generate_script.py    # Claude API script generation
        ├── review_script.py      # 7-reviewer evaluation system
        ├── generate_voice.py     # ElevenLabs TTS
        ├── create_video.py       # Video synthesis (Pexels + FFmpeg)
        └── upload_youtube.py     # YouTube Data API v3 upload
```

Runtime-created directories (not committed):
- `nanahiro-auto/output/` — generated scripts (JSON), audio (MP3), video (MP4)
- `nanahiro-auto/logs/` — machine-readable JSON logs + human-readable `.txt` reports
- `nanahiro-auto/temp/` — temporary video clip downloads (auto-deleted)

## Technology Stack

- **Language:** Python 3.11
- **AI:** Anthropic Claude (`claude-opus-4-6` for generation, `claude-haiku-4-5-20251001` for review)
- **TTS:** ElevenLabs v2 multilingual model
- **Video:** MoviePy 1.0.3 + FFmpeg + ImageMagick
- **Stock footage:** Pexels API
- **YouTube:** Google API Python Client (OAuth2, YouTube Data API v3)
- **CI/CD:** GitHub Actions (ubuntu-latest, 90-min timeout)

## Running the Pipeline

### Local execution
```bash
cd nanahiro-auto
pip install -r requirements.txt
# Set required env vars (see Environment Variables section)
python scripts/main.py              # random theme
python scripts/main.py "親子の絆"   # specific theme
```

### Automated (GitHub Actions)
- **Schedule:** Daily at 11:00 UTC (= 20:00 JST), cron: `0 11 * * *`
- **Manual trigger:** Actions tab → `毎日自動投稿` → `Run workflow`
- **Timeout:** 90 minutes

## Environment Variables

All secrets are stored as GitHub repository secrets. For local development, set them as environment variables or in a `.env` file (not committed).

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API authentication |
| `ELEVENLABS_API_KEY` | Yes | ElevenLabs TTS API key |
| `ELEVENLABS_VOICE_ID` | Yes | ElevenLabs voice character ID |
| `PEXELS_API_KEY` | Yes | Pexels stock video search |
| `YOUTUBE_CREDENTIALS` | Yes | YouTube OAuth2 JSON (token, refresh_token, client_id, client_secret) |

## Pipeline Phases

### ① Script Generation (`generate_script.py`)
- Model: `claude-opus-4-6`, max_tokens=6000
- Picks a random theme from `THEMES` list (7 options) unless a CLI arg is provided
- System prompt enforces narration-only text (no symbols, no stage directions)
- Output: JSON with `title`, `subtitle`, `theme`, `script`, `tags`, `description`, `thumbnail_prompt`
- Post-processing: strips symbols (`☆◆●■▶︎①②③④⑤`), removes `【…】` and `〈…〉` headings, trims to 5000 chars
- Saves to `output/script_YYYYMMDD_HHMMSS.json`

### ② Review & Feedback Loop (`review_script.py`)
- Model: `claude-haiku-4-5-20251001`, max_tokens=300 per reviewer
- 7 reviewers with weighted scoring (see table below)
- Max 3 feedback loops before force-proceeding or skipping
- **Pass condition:** `total_score >= 50` AND judge verdict == `"投稿OK"`
- If failing: top-3 lowest-scoring guides + judge's `improvements` list fed back into `improve_script()` in `main.py`
- If `verdict == "再生成"` after 3 loops: pipeline exits (skips upload)

**Reviewer weights:**

| # | Persona | Role | Weight |
|---|---|---|---|
| 1 | 30代会社員・男性（倍速視聴） | guide | 1.2 |
| 2 | 50代主婦（感動・共感層） | guide | 1.5 |
| 3 | 20代大学生（即離脱テスト） | guide | 0.8 |
| 4 | 感動系YouTubeヘビーユーザー | guide | 1.3 |
| 5 | 感動に懐疑的な視聴者 | guide | 1.0 |
| 6 | YouTube構成担当 | guide | 1.2 |
| 7 | プロ編集者・最終判定 | **judge** | **5.0** |

**Score formula:** `ACTION_BONUS (3) + Σ(stars × weight)` — max ≈ 65 points

> **Note:** `README.md` states "105点以上" as the pass threshold, but the actual code uses `PASS_SCORE = 50` (maximum possible ≈ 65). The README is outdated; trust the code.

### ③ Voice Generation (`generate_voice.py`)
- ElevenLabs v2 multilingual model
- Voice settings: `stability=0.5`, `similarity_boost=0.8`, `style=0.3`
- 4000-character API limit per request
- Output: MP3 to `output/`

### ④ Video Synthesis (`create_video.py`)
- Splits script into ≤20 scenes
- Per scene: Claude Haiku extracts keywords → Pexels video search → alignment score (1–5)
- Min alignment score: 3/5; below that uses TextCard fallback (dark bg + white text)
- Output: MP4 at 1280×720, H.264, AAC, with burned-in subtitles (35-char wrap, 34px, white stroke)
- Short video clips are looped to match scene duration

### ⑤ YouTube Upload (`upload_youtube.py`)
- OAuth2 from `YOUTUBE_CREDENTIALS` env var (JSON string)
- Uploaded as **"private"** — manual publish is required after review
- Category: 22 (People & Blogs)
- Up to 30 tags from generated metadata
- Returns video URL

## Output & Logging

Every run saves two log files under `nanahiro-auto/logs/`:

| File | Format | Contents |
|---|---|---|
| `log_YYYYMMDD_HHMMSS.json` | JSON | date, status, title, script, score, verdict, video_url |
| `script_YYYYMMDD_HHMMSS.txt` | Plain text | Human-readable report with reviewer breakdown and feedback |

GitHub Actions uploads `logs/` and `output/*.json` as artifacts (30-day retention).

## Code Conventions

- **Naming:** `snake_case` for files and functions; timestamp suffix `YYYYMMDD_HHMMSS` for artifacts
- **Language:** Japanese in print statements, comments, and user-facing log output
- **Error handling:** try/except with print-and-fallback (not raised exceptions); 3 retry attempts on reviewer API calls
- **JSON I/O:** always `ensure_ascii=False` to preserve Unicode
- **No tests, no linting config** — the reviewer loop serves as quality gating
- **No database** — stateless; all state in JSON files per run
- **Config via env vars only** — no hardcoded secrets anywhere

## Editing the Pipeline

When modifying scripts, keep these constraints in mind:

1. **`PASS_SCORE`** is defined in both `main.py` (line 14) and `review_script.py` (line 36) — keep them in sync.
2. **Script cleanup regex** appears in both `generate_script.py` (lines 92–96) and `main.py` (lines 122–125) — if you change the symbol set, update both.
3. **Model IDs** — use `claude-opus-4-6` for generation/improvement (quality-critical), `claude-haiku-4-5-20251001` for reviewer evaluation (cost/speed-critical).
4. **Video output path** — `create_video.py` writes to `output/`; `main.py` passes that path directly to `upload_youtube.py`. Don't change without updating both.
5. **YouTube privacy** — uploads land as `"private"`. Do not change to `"public"` without explicit intent.

## CI/CD (`.github/workflows/daily_post.yml`)

Key steps performed by the workflow:
1. Checkout + Python 3.11 setup
2. `pip install -r nanahiro-auto/requirements.txt`
3. `sudo apt-get install ffmpeg imagemagick`
4. ImageMagick PDF policy fix (removes `<policy domain="coder" rights="none" pattern="PDF"/>`)
5. `cd nanahiro-auto/scripts && python main.py`
6. Upload artifacts: `nanahiro-auto/logs/` and `nanahiro-auto/output/*.json`

The workflow uses all 5 secrets listed under Environment Variables above.
