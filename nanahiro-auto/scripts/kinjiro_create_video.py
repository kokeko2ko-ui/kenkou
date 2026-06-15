"""
金次郎プロモ動画合成モジュール
シーン画像 + ナレーション音声 → MP4動画
"""
import os
import json
import numpy as np
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

try:
    from moviepy.editor import (
        ImageClip, AudioFileClip, CompositeVideoClip,
        concatenate_videoclips, TextClip, ColorClip,
    )
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("[警告] moviepy が未インストール: pip install moviepy==1.0.3")

TARGET_W, TARGET_H = 1280, 720


def _get_font(size: int):
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_subtitle_clip(text: str, duration: float) -> ImageClip:
    """字幕オーバーレイクリップを生成"""
    try:
        text = text[:40]
        font = _get_font(32)
        bar_w, bar_h = TARGET_W - 60, 60

        img = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        overlay = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 160))
        img.paste(overlay, (0, 0))

        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
        except AttributeError:
            tw, _ = draw.textsize(text, font=font)

        x = (bar_w - tw) // 2
        y = (bar_h - 36) // 2

        for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

        arr = np.array(img)
        clip = ImageClip(arr, ismask=False)
        clip = clip.set_duration(max(duration - 0.3, 0.5))
        return clip
    except Exception as e:
        print(f"  [字幕エラー] {e}")
        return None


def make_title_card(text: str, duration: float, sub_text: str = "") -> ImageClip:
    """タイトル/テロップカードを生成"""
    img = Image.new("RGB", (TARGET_W, TARGET_H), (10, 10, 30))
    draw = ImageDraw.Draw(img)

    font_main = _get_font(52)
    font_sub = _get_font(32)

    try:
        bbox = draw.textbbox((0, 0), text, font=font_main)
        tw = bbox[2] - bbox[0]
    except AttributeError:
        tw, _ = draw.textsize(text, font=font_main)

    x = (TARGET_W - tw) // 2
    y = TARGET_H // 2 - 60
    draw.text((x + 3, y + 3), text, font=font_main, fill=(0, 0, 0))
    draw.text((x, y), text, font=font_main, fill=(255, 220, 100))

    if sub_text:
        try:
            bbox2 = draw.textbbox((0, 0), sub_text, font=font_sub)
            tw2 = bbox2[2] - bbox2[0]
        except AttributeError:
            tw2, _ = draw.textsize(sub_text, font=font_sub)
        x2 = (TARGET_W - tw2) // 2
        draw.text((x2, y + 80), sub_text, font=font_sub, fill=(200, 200, 200))

    arr = np.array(img)
    return ImageClip(arr).set_duration(duration)


def load_scene_image(image_path: str, duration: float) -> ImageClip:
    """シーン画像をImageClipとして読み込み"""
    if not image_path or not os.path.exists(image_path):
        return make_title_card("（画像なし）", duration)
    try:
        img = Image.open(image_path).convert("RGB")
        img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
        arr = np.array(img)
        clip = ImageClip(arr).set_duration(duration)
        return clip
    except Exception as e:
        print(f"  [画像読み込みエラー] {e}: {image_path}")
        return make_title_card("（読み込みエラー）", duration)


def build_scene_clips(scenes: list, image_paths: list, total_audio_duration: float) -> list:
    """シーンごとのビデオクリップを構築"""
    if not scenes:
        return []

    total_scene_duration = sum(s.get("duration_seconds", 10) for s in scenes)
    time_scale = total_audio_duration / total_scene_duration if total_scene_duration > 0 else 1.0

    clips = []
    subtitle_clips = []
    current_time = 0.0

    for i, (scene, img_path) in enumerate(zip(scenes, image_paths), start=1):
        raw_duration = scene.get("duration_seconds", 10)
        duration = raw_duration * time_scale

        print(f"  [シーン{i}] {scene['name']} ({duration:.1f}秒)")

        scene_clip = load_scene_image(img_path, duration)
        scene_clip = scene_clip.set_start(current_time)
        clips.append(scene_clip)

        dialogues = scene.get("dialogue", [])
        key_dialogue = next(
            (d["line"] for d in dialogues if d.get("speaker") not in ("narrator",)),
            next((d["line"] for d in dialogues), None),
        )
        if key_dialogue and len(key_dialogue) > 2:
            sub = make_subtitle_clip(key_dialogue[:40], duration)
            if sub:
                sub = sub.set_start(current_time + 0.5)
                sub = sub.set_pos(("center", TARGET_H - 90))
                subtitle_clips.append(sub)

        current_time += duration

    return clips + subtitle_clips


def add_teaser_card(teaser_text: str, start_time: float, duration: float = 5.0) -> ImageClip:
    """最終テロップカードを追加"""
    card = make_title_card(
        "Izakaya Kinjiro",
        duration,
        sub_text=teaser_text,
    )
    return card.set_start(start_time)


def create_kinjiro_video(script_data: dict, image_paths: list, audio_path: str) -> str:
    """メイン動画合成関数"""
    if not MOVIEPY_AVAILABLE:
        raise ImportError("moviepy が必要です: pip install moviepy==1.0.3")

    title = script_data.get("title", "LAサバイバル・レース")
    teaser = script_data.get("teaser_text", "ご予約はお早めに！ Izakaya Kinjiro")
    scenes = script_data.get("scenes", [])

    print(f"\n[動画合成] 開始: {title}")

    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    print(f"[動画合成] 音声長: {total_duration:.1f}秒")

    # イントロカード（3秒）
    intro = make_title_card(title, 3.0, sub_text="〜金次郎、至高の宴〜")
    intro = intro.set_start(0)
    video_duration_after_intro = total_duration - 3.0 - 5.0

    # シーンクリップ生成
    scene_clips = build_scene_clips(scenes, image_paths, max(video_duration_after_intro, 10))
    adjusted_scene_clips = []
    for clip in scene_clips:
        adjusted_scene_clips.append(clip.set_start(clip.start + 3.0))

    # アウトロ（テロップカード）
    outro_start = total_duration - 5.0
    outro = add_teaser_card(teaser, outro_start, duration=5.0)

    all_clips = [intro] + adjusted_scene_clips + [outro]

    print(f"[動画合成] {len(all_clips)}クリップを合成中...")
    final = CompositeVideoClip(all_clips, size=(TARGET_W, TARGET_H))
    final = final.set_duration(total_duration).set_audio(audio)

    os.makedirs("output", exist_ok=True)
    output_path = f"output/kinjiro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

    print(f"[動画合成] MP4書き出し中... → {output_path}")
    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=24,
        preset="fast",
        logger=None,
    )

    print(f"[動画合成完了] {output_path}")
    return output_path


if __name__ == "__main__":
    import glob
    script_path = os.path.join(os.path.dirname(__file__), "kinjiro_script.json")
    with open(script_path, encoding="utf-8") as f:
        script_data = json.load(f)

    image_paths = sorted(glob.glob("output/kinjiro_images/scene_*.jpg"))
    audio_files = sorted(glob.glob("output/kinjiro_voice_*.mp3"))

    if not image_paths:
        print("画像ファイルが見つかりません。先に kinjiro_generate_images.py を実行してください。")
    elif not audio_files:
        print("音声ファイルが見つかりません。先に kinjiro_generate_voice.py を実行してください。")
    else:
        video = create_kinjiro_video(script_data, image_paths, audio_files[-1])
        print(f"動画: {video}")
