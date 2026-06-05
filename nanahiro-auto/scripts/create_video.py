import os
import json
import requests
import anthropic
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, ColorClip, ImageClip
)

PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TARGET_W, TARGET_H = 1280, 720
MIN_ALIGNMENT_SCORE = 3


def get_alignment_score(sentence: str, video_description: str) -> int:
    """台本のセリフと映像の一致度を1-5でスコアリング"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            system="数字1つだけ返してください。",
            messages=[{
                "role": "user",
                "content": f"""台本のセリフ：「{sentence[:100]}」
映像の内容：「{video_description}」

このセリフにこの映像は合っていますか？1-5で評価してください。
5=完全一致 4=よく合う 3=関連あり 2=弱い関連 1=無関係
数字1つだけ答えてください。"""
            }]
        )
        score = int(response.content[0].text.strip()[0])
        return min(max(score, 1), 5)
    except:
        return 2


def search_pexels_videos(query: str, count: int = 5) -> list:
    """Pexelsから映像を検索"""
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": count, "orientation": "landscape"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        data = response.json()
        results = []
        for video in data.get("videos", []):
            for f in video.get("video_files", []):
                if f.get("width", 0) >= 1280 and f.get("height", 0) >= 720:
                    results.append({
                        "url": f["link"],
                        "description": video.get("url", ""),
                    })
                    break
        return results
    except Exception as e:
        print(f"[Pexels検索エラー] {e}")
        return []


def download_video(url: str, path: str) -> bool:
    try:
        response = requests.get(url, stream=True, timeout=60)
        with open(path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return os.path.getsize(path) > 10000
    except Exception as e:
        print(f"[ダウンロードエラー] {e}")
        return False


def extract_keywords(sentence: str) -> str:
    """台本から検索キーワードを抽出"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=30,
            system="英語のキーワードのみ返してください。",
            messages=[{
                "role": "user",
                "content": f"この文章に合う映像を検索するための英語キーワードを3語以内で：「{sentence[:80]}」"
            }]
        )
        return response.content[0].text.strip()
    except:
        return "emotional story japan"


def find_aligned_video(sentence: str, temp_dir: str, index: int) -> str:
    """アライメントスコア3以上の映像を探す"""
    keywords = extract_keywords(sentence)
    print(f"  [検索] '{keywords}' でPexels検索中...")

    videos = search_pexels_videos(keywords, count=5)

    for i, video in enumerate(videos):
        path = f"{temp_dir}/clip_{index}_{i}.mp4"
        if download_video(video["url"], path):
            score = get_alignment_score(sentence, keywords)
            print(f"  [スコア] {score}/5 - {keywords}")
            if score >= MIN_ALIGNMENT_SCORE:
                return path
            else:
                os.remove(path)

    print(f"  [フォールバック] スコア不足 → テキストカードを使用")
    return None


def _get_font(size: int):
    """利用可能な日本語フォントを取得"""
    font_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_text_card(text: str, duration: float) -> ImageClip:
    """テキストカードを生成（Pillow方式・ImageMagick不使用）"""
    img = Image.new("RGB", (TARGET_W, TARGET_H), color=(20, 20, 40))
    draw = ImageDraw.Draw(img)
    font = _get_font(40)

    display_text = text[:50]
    try:
        bbox = draw.textbbox((0, 0), display_text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(display_text, font=font)

    x = (TARGET_W - tw) // 2
    y = (TARGET_H - th) // 2

    draw.text((x + 2, y + 2), display_text, font=font, fill=(80, 80, 80))
    draw.text((x, y), display_text, font=font, fill=(255, 255, 255))

    arr = np.array(img)
    return ImageClip(arr).set_duration(duration)


def make_subtitle(text: str, duration: float) -> ImageClip:
    """字幕クリップを生成（Pillow方式・ImageMagick不使用）"""
    try:
        if len(text) > 35:
            text = text[:35] + "\n" + text[35:70]

        font = _get_font(34)
        line_h = 44
        lines = text.split("\n")
        total_h = line_h * len(lines) + 16
        bar_w = TARGET_W - 80

        img = Image.new("RGBA", (bar_w, total_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        for li, line in enumerate(lines):
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                tw = bbox[2] - bbox[0]
            except AttributeError:
                tw, _ = draw.textsize(line, font=font)
            x = (bar_w - tw) // 2
            y = li * line_h + 8

            for dx in (-2, 0, 2):
                for dy in (-2, 0, 2):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

        arr = np.array(img)
        clip = ImageClip(arr, ismask=False).set_duration(duration - 0.2)
        return clip
    except Exception as e:
        print(f"[字幕エラー] {e}")
        return None


def create_video(script_data: dict, audio_path: str) -> str:
    title = script_data.get("title", "動画")
    script_text = script_data.get("script", "")

    print(f"[動画合成] アライメントスコアモードで開始")

    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    print(f"[動画合成] 音声の長さ: {total_duration:.1f}秒")

    sentences = []
    for line in script_text.replace("。", "。\n").split("\n"):
        line = line.strip()
        if len(line) > 5:
            sentences.append(line)

    max_scenes = min(20, len(sentences))
    scene_sentences = sentences[:max_scenes]
    scene_duration = total_duration / max(len(scene_sentences), 1)

    print(f"[動画合成] {len(scene_sentences)}シーンに分割 (各{scene_duration:.1f}秒)")

    os.makedirs("temp", exist_ok=True)

    video_clips = []
    subtitle_clips = []

    for i, sentence in enumerate(scene_sentences):
        start_time = i * scene_duration
        print(f"\n[シーン {i+1}/{len(scene_sentences)}] {sentence[:30]}...")

        video_path = find_aligned_video(sentence, "temp", i)

        if video_path and os.path.exists(video_path):
            try:
                clip = VideoFileClip(video_path)
                clip = clip.resize((TARGET_W, TARGET_H))
                use_dur = min(scene_duration, clip.duration)
                clip = clip.subclip(0, use_dur)
                if use_dur < scene_duration:
                    loops = int(scene_duration / use_dur) + 1
                    clip = concatenate_videoclips([clip] * loops).subclip(0, scene_duration)
                clip = clip.set_start(start_time)
                video_clips.append(clip)
            except Exception as e:
                print(f"  [クリップエラー] {e} → テキストカードを使用")
                card = make_text_card(sentence, scene_duration).set_start(start_time)
                video_clips.append(card)
        else:
            card = make_text_card(sentence, scene_duration).set_start(start_time)
            video_clips.append(card)

        sub = make_subtitle(sentence, scene_duration)
        if sub:
            sub = sub.set_start(start_time).set_pos(("center", TARGET_H - 120))
            subtitle_clips.append(sub)

    if not video_clips:
        video_clips = [ColorClip(size=(TARGET_W, TARGET_H), color=(10, 10, 30), duration=total_duration)]

    print("\n[動画合成] 全クリップを合成中...")
    all_clips = video_clips + subtitle_clips
    final_video = CompositeVideoClip(all_clips, size=(TARGET_W, TARGET_H))
    final_video = final_video.set_duration(total_duration).set_audio(audio)

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

    print(f"[動画合成] MP4を書き出し中...")
    final_video.write_videofile(
        filename,
        codec="libx264",
        audio_codec="aac",
        fps=24,
        preset="fast",
        logger=None,
    )

    import glob
    for f in glob.glob("temp/*.mp4"):
        try:
            os.remove(f)
        except:
            pass

    print(f"[動画合成完了] 保存先: {filename}")
    return filename
