import os
import json
import requests
import anthropic
from datetime import datetime
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, TextClip, ColorClip, ImageClip
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

    # フォールバック：テキストカードを使用
    print(f"  [フォールバック] スコア不足 → テキストカードを使用")
    return None


def make_text_card(text: str, duration: float) -> ColorClip:
    """テキストカードを生成（映像が見つからない場合のフォールバック）"""
    bg = ColorClip(size=(TARGET_W, TARGET_H), color=(20, 20, 40), duration=duration)
    try:
        txt = TextClip(
            text[:50],
            fontsize=40,
            color="white",
            stroke_color="gray",
            stroke_width=1,
            method="caption",
            size=(TARGET_W - 120, None),
            align="center",
        ).set_duration(duration).set_pos("center")
        return CompositeVideoClip([bg, txt], size=(TARGET_W, TARGET_H))
    except:
        return bg


def make_subtitle(text: str, duration: float) -> TextClip:
    """字幕クリップを生成"""
    try:
        # 35文字で折り返し
        if len(text) > 35:
            text = text[:35] + "\n" + text[35:70]
        clip = TextClip(
            text,
            fontsize=34,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(TARGET_W - 80, None),
            align="center",
        ).set_duration(duration - 0.2)
        return clip
    except Exception as e:
        print(f"[字幕エラー] {e}")
        return None


def create_video(script_data: dict, audio_path: str) -> str:
    title = script_data.get("title", "動画")
    script_text = script_data.get("script", "")

    print(f"[動画合成] アライメントスコアモードで開始")

    # 音声読み込み
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    print(f"[動画合成] 音声の長さ: {total_duration:.1f}秒")

    # 台本を文に分割
    sentences = []
    for line in script_text.replace("。", "。\n").split("\n"):
        line = line.strip()
        if len(line) > 5:
            sentences.append(line)

    # 最大20シーンに分割
    max_scenes = min(20, len(sentences))
    scene_sentences = sentences[:max_scenes]
    scene_duration = total_duration / max(len(scene_sentences), 1)

    print(f"[動画合成] {len(scene_sentences)}シーンに分割 (各{scene_duration:.1f}秒)")

    os.makedirs("temp", exist_ok=True)

    # 各シーンに映像を割り当て
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
                    # 短い場合はループ
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

        # 字幕追加
        sub = make_subtitle(sentence, scene_duration)
        if sub:
            sub = sub.set_start(start_time).set_pos(("center", TARGET_H - 120))
            subtitle_clips.append(sub)

    # 映像が空の場合のフォールバック
    if not video_clips:
        video_clips = [ColorClip(size=(TARGET_W, TARGET_H), color=(10, 10, 30), duration=total_duration)]

    # 合成
    print("\n[動画合成] 全クリップを合成中...")
    all_clips = video_clips + subtitle_clips
    final_video = CompositeVideoClip(all_clips, size=(TARGET_W, TARGET_H))
    final_video = final_video.set_duration(total_duration).set_audio(audio)

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
    import glob
    for f in glob.glob("temp/*.mp4"):
        try:
            os.remove(f)
        except:
            pass

    print(f"[動画合成完了] 保存先: {filename}")
    return filename
