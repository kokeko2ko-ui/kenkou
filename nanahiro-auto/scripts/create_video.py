import os
import requests
import json
from datetime import datetime
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, TextClip, ColorClip
)

PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
TARGET_W, TARGET_H = 1280, 720


def search_pexels_videos(query: str, count: int = 5) -> list:
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": count, "orientation": "landscape"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        data = response.json()
        videos = []
        for video in data.get("videos", []):
            best = None
            for f in video.get("video_files", []):
                if f.get("width", 0) >= 1280 and f.get("height", 0) >= 720:
                    if best is None or f.get("width", 0) < best.get("width", 9999):
                        best = f
            if best:
                videos.append(best["link"])
        return videos
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


def make_text_clip(text: str, duration: float, fontsize: int = 36) -> TextClip:
    try:
        clip = TextClip(
            text,
            fontsize=fontsize,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(TARGET_W - 80, None),
            align="center",
        ).set_duration(duration)
        return clip
    except Exception as e:
        print(f"[テロップ生成エラー] {e}")
        return None


def create_video(script_data: dict, audio_path: str) -> str:
    title = script_data.get("title", "動画")
    theme = script_data.get("theme_selected", "感動 家族")
    script_text = script_data.get("script", "")

    print(f"[動画合成] テーマ: {theme}")

    # 音声読み込み
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    print(f"[動画合成] 音声の長さ: {total_duration:.1f}秒")

    # Pexelsから映像を取得
    search_queries = [
        theme,
        "family emotional story japan",
        "elderly people walking nature",
        "sunset mountain peaceful",
        "japanese town street",
    ]

    os.makedirs("temp", exist_ok=True)
    video_paths = []

    for i, query in enumerate(search_queries):
        urls = search_pexels_videos(query, count=2)
        for j, url in enumerate(urls):
            path = f"temp/clip_{i}_{j}.mp4"
            print(f"[動画合成] ダウンロード中: {query[:20]}...")
            if download_video(url, path):
                video_paths.append(path)
            if len(video_paths) >= 8:
                break
        if len(video_paths) >= 8:
            break

    print(f"[動画合成] 取得できた映像: {len(video_paths)}本")

    # 映像クリップを結合
    clips = []
    if video_paths:
        clip_duration = total_duration / max(len(video_paths), 1)
        for path in video_paths:
            try:
                clip = VideoFileClip(path)
                # リサイズ
                clip = clip.resize((TARGET_W, TARGET_H))
                # クリップの長さを調整
                use_duration = min(clip_duration, clip.duration)
                clip = clip.subclip(0, use_duration)
                clips.append(clip)
            except Exception as e:
                print(f"[クリップエラー] {path}: {e}")

    if not clips:
        print("[警告] 映像が取得できなかったため黒背景を使用します")
        clips = [ColorClip(size=(TARGET_W, TARGET_H), color=(10, 10, 30), duration=total_duration)]

    # 映像を結合
    base_video = concatenate_videoclips(clips, method="compose")

    # 音声の長さに合わせる
    if base_video.duration < total_duration:
        loops = int(total_duration / base_video.duration) + 1
        base_video = concatenate_videoclips([base_video] * loops, method="compose")
    base_video = base_video.subclip(0, total_duration)

    # テロップ生成
    print("[動画合成] テロップを生成中...")
    subtitle_clips = []
    try:
        sentences = [s.strip() for s in script_text.replace("。", "。\n").split("\n") if s.strip() and len(s.strip()) > 3]
        sentences = sentences[:int(total_duration / 4)]  # 4秒に1テロップ

        sub_duration = total_duration / max(len(sentences), 1)
        for i, sentence in enumerate(sentences):
            start_time = i * sub_duration
            # 35文字で折り返し
            if len(sentence) > 35:
                sentence = sentence[:35] + "\n" + sentence[35:70]

            txt_clip = make_text_clip(sentence, sub_duration - 0.3)
            if txt_clip:
                txt_clip = txt_clip.set_start(start_time).set_pos(("center", TARGET_H - 120))
                subtitle_clips.append(txt_clip)
    except Exception as e:
        print(f"[テロップエラー] {e}")

    # 合成
    print("[動画合成] 映像・音声・テロップを合成中...")
    all_clips = [base_video] + subtitle_clips
    final_video = CompositeVideoClip(all_clips, size=(TARGET_W, TARGET_H))
    final_video = final_video.set_audio(audio)

    # 出力
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

    # 一時ファイル削除
    for path in video_paths:
        try:
            os.remove(path)
        except:
            pass

    print(f"[動画合成完了] 保存先: {filename}")
    return filename


if __name__ == "__main__":
    print("動画合成モジュールです。main.pyから呼び出してください。")
