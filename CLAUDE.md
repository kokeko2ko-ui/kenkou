# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A single automated content pipeline, `nanahiro-auto/`, that generates and publishes one Japanese-language "emotional story" video per day to the YouTube channel「人生は七色」. It runs unattended via a GitHub Actions cron job — there is no application server, frontend, or test suite. The repo currently contains just this one pipeline.

## Running the pipeline

There is no build step, package manifest beyond `requirements.txt`, linter, or test suite configured. Development consists of running the Python scripts directly.

```bash
cd nanahiro-auto
pip install -r requirements.txt

# System deps the video step needs (already present in the GitHub Actions runner,
# must be installed manually on a dev machine):
#   ffmpeg, imagemagick (with policy.xml PDF rights relaxed — see daily_post.yml)

cd scripts
python main.py                 # run the full pipeline, random theme
python main.py "テーマ名"       # run with an explicit theme
```

Each stage can also be invoked standalone for iterating on one part of the pipeline:

```bash
python generate_script.py    # script generation only, prints title/length/preview
python generate_voice.py     # requires a script already generated; also used to list
                              # available ElevenLabs voices when picking ELEVENLABS_VOICE_ID
python upload_youtube.py     # prints usage note only — meant to be called from main.py
```

`review_script.py` and `create_video.py` have no `__main__` entry point; exercise them through `main.py` or by importing the function in a REPL.

### Required environment variables

Set these before running any stage that calls an external API (mirrors the GitHub Secrets used in `.github/workflows/daily_post.yml`):

| Variable | Used by |
|---|---|
| `ANTHROPIC_API_KEY` | `generate_script.py`, `review_script.py`, `create_video.py` (keyword/alignment scoring), `main.py` (`improve_script`) |
| `ELEVENLABS_API_KEY` | `generate_voice.py` |
| `ELEVENLABS_VOICE_ID` | `generate_voice.py` |
| `PEXELS_API_KEY` | `create_video.py` |
| `YOUTUBE_CREDENTIALS` | `upload_youtube.py` — JSON blob with `token`, `refresh_token`, `client_id`, `client_secret` for a Google OAuth2 credential scoped to `youtube.upload` |

## Pipeline architecture

`scripts/main.py` (`run_pipeline`) drives five stages in sequence, each implemented in its own module and imported as a plain function — there is no class hierarchy or plugin system:

1. **`generate_script.py`** (`generate_script`) — calls Claude (`claude-opus-4-6`) with a fixed system prompt to write a narration-only script (no stage directions/symbols) from one of the `THEMES`, and returns a dict with `title`, `script`, `tags`, `description`, `thumbnail_prompt`, etc. Strips decorative symbols/headings with regex and hard-trims to 5000 chars. Saves a snapshot JSON to `output/script_*.json`.

2. **`review_script.py`** (`review_script`) — sends the script to 7 simulated reviewer personas (`REVIEWERS`, `claude-haiku-4-5-20251001`), 6 "guide" reviewers (weighted 0.8–1.5) plus one "judge" (weight 5.0, also returns a `verdict` and `improvements`). Score = 3-point action bonus + Σ(stars × weight). `PASS_SCORE = 50` (duplicated as a constant in both `review_script.py` and `main.py` — keep them in sync if it changes). Passes only if `total >= PASS_SCORE` **and** judge verdict is `投稿OK`.

3. **`main.py`** loops the generate→review cycle up to `MAX_REVIEW_LOOPS = 3` times. On failure it takes the 3 lowest-starred guide reviews plus the judge's `improvements` (`get_improvement_feedback`) and asks Claude to revise the script (`main.improve_script`, also `claude-opus-4-6`). If still failing after 3 loops: post anyway unless the judge's verdict is literally `再生成` (regenerate), in which case the run is skipped entirely and logged with `status="skipped"`.

4. **`generate_voice.py`** (`generate_voice`) — strips remaining bracket/parenthetical annotations, truncates to ElevenLabs' 4000-char request limit, calls the ElevenLabs TTS API (`eleven_multilingual_v2`), saves MP3 to `output/voice_*.mp3`.

5. **`create_video.py`** (`create_video`) — splits the script into sentences (by `。`), caps at 20 scenes, and for each scene: asks Claude for English search keywords (`extract_keywords`), searches Pexels stock video (`search_pexels_videos`), downloads a candidate clip, and asks Claude to score sentence/video alignment 1–5 (`get_alignment_score`); only clips scoring ≥ `MIN_ALIGNMENT_SCORE = 3` are kept, otherwise it falls back to a generated text card (Pillow, not ImageMagick — a hand-rolled font search in `_get_font` looks for Noto CJK on the runner since the sentences are Japanese). Burns in subtitles per scene, composites with `moviepy`, muxes the ElevenLabs audio, and writes `output/video_*.mp4`. Deletes the downloaded Pexels clips in `temp/` afterward but leaves the rendered video/audio/JSON in `output/`.

6. **`upload_youtube.py`** (`upload_to_youtube`) — builds a YouTube client from the `YOUTUBE_CREDENTIALS` OAuth2 token (no interactive auth flow — the refresh token must already be baked into the secret), uploads resumably, and **always publishes as `privacyStatus: "private"`** — someone has to manually flip it to public after reviewing.

`main.py` also writes two logs per run in `logs/` (not committed; uploaded as a workflow artifact): a machine-readable `log_*.json` and a human-readable `script_*.txt` report (`_save_human_report`) with the full script text, per-reviewer star breakdown, and editor comments.

### Data flow / conventions to preserve

- Scripts pass a single `script_data` dict through every stage (`title`, `script`, `tags`, `description`, `theme`, etc.) — new fields should be added to this dict rather than introduced as separate parallel state.
- Narration text must stay free of stage directions and symbols; every stage that touches `script` re-applies its own regex cleanup (`generate_script.py`, `main.py:improve_script`, `generate_voice.py:clean_script`) rather than relying on a shared sanitizer — if you add a new symbol to strip, update all of them.
- `output/` and `temp/` are working directories created on demand (`os.makedirs(..., exist_ok=True)`) and are not meant to be committed; don't assume they pre-exist. (`output/kinjiro_images/` currently checked into the repo is leftover sample data from an earlier iteration and is not read by any script.)
- Model choice is deliberately split by cost/quality needs: `claude-opus-4-6` for script writing/rewriting (creative, long-form), `claude-haiku-4-5-20251001` for the cheap, high-volume scoring calls (7 reviewers × up to 3 loops, plus per-scene keyword extraction and alignment scoring).

## CI / scheduled execution

`.github/workflows/daily_post.yml` runs the whole pipeline daily at 20:00 JST (`cron: "0 11 * * *"`, UTC) and is also manually triggerable (`workflow_dispatch`). It installs `ffmpeg`/`imagemagick` and relaxes ImageMagick's PDF policy (needed for Pillow/moviepy text rendering) before running `python main.py` from `nanahiro-auto/scripts`, then uploads `nanahiro-auto/logs/` and `output/*.json` as a build artifact regardless of success (`if: always()`). Timeout is 90 minutes — video rendering and multiple Pexels downloads are the slow steps.
