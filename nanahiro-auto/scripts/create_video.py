import os
import requests
import random
from datetime import datetime
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, TextClip, ColorClip
)

PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]


def search_pexels_videos(query: str, count: int = 5) -> list:
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": count, "orientation": "landscape"}
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    videos = []
    for video in data.get("videos", []):
        for file in video.get("video_files", []):
            if file.get("quality") == "hd" and file.get("width", 0) >= 1280:
                videos.append(file["link"])
                break
    return videos


def download_video(url: str, path: str) -> str:
    response = requests.get(url, stream=True)
    with open(path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return path


def create_video(script_data: dict, audio_path: str) -> str:
    title = script_data.get("title", "動画")
    theme = script_data.get("theme_selected", "感動")

    print(f"[動画合成] テーマ: {theme}")

    # Pexelsから映像を取得
    search_queries = [theme, "emotional story", "family love", "sunset nature"]
    video_urls = []
    for query in search_queries:
        urls = search_pexels_videos(query, count=3)
        video_urls.extend(urls)
        if len(video_urls) >= 6:
            break

    os.makedirs("temp", exist_ok=True)
    video_paths = []
    for i, url in enumerate(video_urls[:6]):
        path = f"temp/clip_{i}.mp4"
        print(f"[動画合成] 映像をダウンロード中 ({i+1}/{min(6, len(video_urls))})...")
        download_video(url, path)
        video_paths.append(path)

    # 音声の長さを取得
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    print(f"[動画合成] 音声の長さ: {total_duration:.1f}秒")

    # 映像クリップを結合して音声の長さに合わせる
    clips = []
    current_duration = 0
    clip_duration = total_duration / len(video_paths)

    for path in video_paths:
        try:
            clip = VideoFileClip(path).subclip(0, min(clip_duration, VideoFileClip(path).duration))
            clip = clip.resize((1280, 720))
            clips.append(clip)
            current_duration += clip.duration
        except Exception as e:
            print(f"[警告] クリップ読み込みエラー: {e}")

    if not clips:
        # フォールバック: 黒背景
        clips = [ColorClip(size=(1280, 720), color=(0, 0, 0), duration=total_duration)]

    final_video = concatenate_videoclips(clips, method="compose")

    # 音声の長さに合わせてループ or トリム
    if final_video.duration < total_duration:
        loops = int(total_duration / final_video.duration) + 1
        final_video = concatenate_videoclips([final_video] * loops).subclip(0, total_duration)
    else:
        final_video = final_video.subclip(0, total_duration)

    # 音声を合成
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
        preset="medium",
        logger=None,
    )

    # 一時ファイルを削除
    for path in video_paths:
        if os.path.exists(path):
            os.remove(path)

    print(f"[動画合成完了] 保存先: {filename}")
    return filename


if __name__ == "__main__":
    print("動画合成モジュールの単体テストです。main.pyから呼び出してください。")
